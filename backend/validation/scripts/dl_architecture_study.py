"""
Architecture study for the light-curve vetting model (LIMITATIONS.md #7).

The production DeepExoFusionNet reached 60.9% on one 23-star held-out split with 100%
train accuracy: heavy overfitting, and a split far too small to rank anything by. This
script answers "is there a better architecture for this data?" with a protocol that can
actually distinguish candidates:

* **Star-grouped, repeated stratified K-fold** -- every KOI of a star stays on one side
  of the split (siblings share the star and often the systematics), repeated with
  different seeds, so differences are reported with a spread instead of one lucky split.
* **Same inputs for every model** -- identical real Kepler light curves, identical labels
  (see fetch_real_kepler_dataset.py), identical metadata incl. real 2MASS/Pan-STARRS.
* **Transit-masked detrending** before folding. The production views are built from
  quarter-normalised flux with no detrending at all, so stellar variability leaks into
  the global view; every model here (including the baseline) can be run on either.

Candidates:
    baseline_cnn      current DeepExoFusionNet (3.9M params), as trained in production
    compact_cnn       ~60k-param dual-view CNN, global-average pooling, augmentation
    features_gbm      LightGBM on physics-motivated features (odd/even, secondary,
                      shape, implied radius, ...) -- no deep learning
    hybrid            compact_cnn embedding + features, LightGBM on top

Usage:
    python validation/scripts/dl_architecture_study.py [--repeats 3] [--folds 5]
Writes backend/app/ml/dl_architecture_study.json.
"""
import argparse
import json
import os
import sys
import time
import warnings

import numpy as np

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, BACKEND)
sys.path.insert(0, HERE)

import fetch_real_kepler_dataset as F  # noqa: E402
from app.ml.deep_learning_pipeline import dl_vetting_engine  # noqa: E402
from app.ml import lightcurve_features as LF  # noqa: E402

def _feature_code_hash() -> str:
    """Hash of the shared featurizer's source: the cached study table is only valid for the exact
    code that built it, otherwise training silently uses stale features while serving uses new."""
    import hashlib
    with open(LF.__file__, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:16]


STUDY_CACHE = os.path.join(F.DATA_DIR, "kepler_study_table.npz")
STUDY_META = os.path.join(F.DATA_DIR, "kepler_study_table_meta.json")
REPORT_PATH = os.path.join(BACKEND, "app", "ml", "dl_architecture_study.json")
CLASS_NAMES = [F.LABEL_NAMES[i] for i in range(3)]

# --------------------------------------------------------------------------- data


def build_table(per_class, cache_only=True):
    """Builds (and caches) the study table from rows + the on-disk raw light-curve cache."""
    if os.path.exists(STUDY_CACHE) and os.path.exists(STUDY_META):
        d = np.load(STUDY_CACHE)
        with open(STUDY_META) as fh:
            meta = json.load(fh)
        n_cached = len([f for f in os.listdir(F.LC_CACHE_DIR) if f.endswith(".npz")])
        if (len(meta) and meta[0].get("_per_class") == per_class
                and list(d["feat_names"]) == LF.FEATURE_NAMES and meta[0].get("_n_cache") == n_cached
                and meta[0].get("_code_hash") == _feature_code_hash()):
            return {k: d[k] for k in d.files}, meta

    rows_all = []
    for label, where in F.LABEL_QUERIES:
        for r in F.fetch_koi_rows(label, where, per_class):
            r["_label"] = label
            rows_all.append(r)
    phot = {}
    for label in range(3):
        sub = [r for r in rows_all if r["_label"] == label]
        phot.update(F.crossmatch_photometry(sub))

    G, L, FE, Y, GRP, META = [], [], [], [], [], []
    for r in rows_all:
        cache = os.path.join(F.LC_CACHE_DIR, f"{r['kepid']}.npz")
        if not os.path.exists(cache):
            continue
        lc = np.load(cache)
        t, fl = lc["time"], lc["flux"]
        period, dur_h, t0 = float(r["koi_period"]), float(r["koi_duration"]), float(r["koi_time0bk"])
        p = phot.get(int(r["kepid"]), {})
        rs, teff = r.get("koi_srad"), r.get("koi_steff")
        built = LF.build_feature_vector(
            t, fl, period, t0, dur_h,
            {"teff": teff, "rstar": rs, "depth_ppm": r.get("koi_depth"), **p},
        )
        if built is None:
            continue
        vec, g, l = built
        feats = dict(zip(LF.FEATURE_NAMES, vec))
        G.append(g); L.append(l); FE.append(feats); Y.append(r["_label"]); GRP.append(int(r["kepid"]))
        META.append({"kepid": int(r["kepid"]), "st_teff": teff, "st_rad": rs, "trandep": r.get("koi_depth"),
                     "period": period, "duration_hours": dur_h, **p, "_per_class": per_class, "_code_hash": _feature_code_hash(),
                     "_n_cache": len([f for f in os.listdir(F.LC_CACHE_DIR) if f.endswith(".npz")])})

    names = list(LF.FEATURE_NAMES)
    table = {
        "global": np.stack(G).astype(np.float32), "local": np.stack(L).astype(np.float32),
        "feats": np.array([[f[n] for n in names] for f in FE], dtype=np.float64),
        "feat_names": np.array(names), "y": np.array(Y), "groups": np.array(GRP),
    }
    np.savez(STUDY_CACHE, **table)
    with open(STUDY_META, "w") as fh:
        json.dump(META, fh)
    return table, META


# ------------------------------------------------------------------------- models


def _scale_views(g, l):
    """Per-star robust scaling by the measured transit depth so the net sees shape, not
    amplitude (depth stays available through the feature/metadata path)."""
    d = np.maximum(-l.min(axis=1, keepdims=True), 1e-5)
    return np.clip(g / d, -3, 3)[:, None, :], np.clip(l / d, -3, 3)[:, None, :]


def make_compact_cnn():
    import torch.nn as nn

    class Branch(nn.Module):
        def __init__(self, ch=(8, 16, 32), k=5):
            super().__init__()
            layers, c_in = [], 1
            for c in ch:
                layers += [nn.Conv1d(c_in, c, k, padding=k // 2), nn.BatchNorm1d(c), nn.ReLU(), nn.MaxPool1d(2)]
                c_in = c
            self.net = nn.Sequential(*layers)

        def forward(self, x):
            h = self.net(x)
            return torch_cat_pool(h)

    import torch

    def torch_cat_pool(h):
        return torch.cat([h.mean(dim=2), h.amax(dim=2)], dim=1)   # global avg + max pooling

    class Net(nn.Module):
        def __init__(self, n_meta):
            super().__init__()
            self.g, self.l = Branch(), Branch(k=3)
            self.m = nn.Sequential(nn.Linear(n_meta, 16), nn.ReLU())
            self.head = nn.Sequential(nn.Dropout(0.4), nn.Linear(64 + 64 + 16, 32), nn.ReLU(), nn.Dropout(0.3), nn.Linear(32, 3))

        def embed(self, g, l, m):
            return torch.cat([self.g(g), self.l(l), self.m(m)], dim=1)

        def forward(self, g, l, m):
            return self.head(self.embed(g, l, m))

    return Net


def train_torch(model, G, L, M, y, epochs, lr, wd, augment, seed):
    import torch
    import torch.nn as nn
    torch.manual_seed(seed)
    rng = np.random.RandomState(seed)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=wd)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=lr, total_steps=epochs * ((len(y) + 31) // 32))
    counts = np.bincount(y, minlength=3).astype(float)
    crit = nn.CrossEntropyLoss(weight=torch.tensor(counts.sum() / (3 * np.maximum(counts, 1)), dtype=torch.float32))
    Gt, Lt, Mt = (torch.tensor(a, dtype=torch.float32) for a in (G, L, M))
    yt = torch.tensor(y)
    for _ in range(epochs):
        model.train()
        perm = rng.permutation(len(y))
        for i in range(0, len(y), 32):
            idx = perm[i:i + 32]
            if len(idx) < 2:
                continue
            g, l, m = Gt[idx].clone(), Lt[idx].clone(), Mt[idx].clone()
            if augment:
                flip = torch.rand(len(idx)) < 0.5            # transits are time-symmetric
                l[flip] = l[flip].flip(-1)
                g[flip] = g[flip].flip(-1)
                g = g + 0.03 * torch.randn_like(g)
                l = l + 0.03 * torch.randn_like(l)
                shift = int(rng.randint(-6, 7))              # small centre jitter of the local view
                l = torch.roll(l, shift, dims=-1)
                m = m + 0.05 * torch.randn_like(m)
            opt.zero_grad()
            loss = crit(model(g, l, m), yt[idx])
            loss.backward()
            opt.step()
            sched.step()
    return model


def predict_torch(model, G, L, M):
    import torch
    model.eval()
    with torch.no_grad():
        out = model(*(torch.tensor(a, dtype=torch.float32) for a in (G, L, M)))
    return torch.softmax(out, 1).numpy()


def meta_matrix(feats, names):
    """Standardised metadata for the CNN: log-depth, teff, rstar, colours, + presence bits."""
    cols = ["catalog_depth_ppm", "teff", "rstar", "j_k", "g_r", "g_k", "log_period", "dur_over_period"]
    idx = [list(names).index(c) for c in cols]
    X = feats[:, idx].copy()
    X[:, 0] = np.log10(np.maximum(X[:, 0], 1.0))
    X[:, 2] = np.log10(np.maximum(X[:, 2], 0.05))
    present = np.isfinite(X).astype(float)
    return X, present


def standardise(train, test):
    mu = np.nanmean(train, axis=0)
    sd = np.nanstd(train, axis=0) + 1e-6
    f = lambda a: np.nan_to_num((a - mu) / sd, nan=0.0)
    return f(train), f(test)


def evaluate_fold(name, tr, te, T):
    from sklearn.metrics import accuracy_score, f1_score
    y = T["y"]
    feats, names = T["feats"], T["feat_names"]
    Gs, Ls = _scale_views(T["global"], T["local"])
    Mraw, Mpres = meta_matrix(feats, names)
    out = {}
    if name in ("compact_cnn", "hybrid"):
        Mtr, Mte = standardise(Mraw[tr], Mraw[te])
        Mtr, Mte = np.hstack([Mtr, Mpres[tr]]), np.hstack([Mte, Mpres[te]])
        Net = make_compact_cnn()
        probs = []
        for s in range(3):   # small ensemble: cheap, and removes seed luck from the comparison
            net = Net(Mtr.shape[1])
            train_torch(net, Gs[tr], Ls[tr], Mtr, y[tr], epochs=60, lr=3e-3, wd=1e-2, augment=True, seed=s)
            probs.append(predict_torch(net, Gs[te], Ls[te], Mte))
        out["compact_cnn"] = np.mean(probs, axis=0)
        if name == "hybrid":
            import torch
            import lightgbm as lgb
            net = Net(Mtr.shape[1])
            train_torch(net, Gs[tr], Ls[tr], Mtr, y[tr], epochs=60, lr=3e-3, wd=1e-2, augment=True, seed=0)
            net.eval()
            with torch.no_grad():
                emb = lambda ix, M: net.embed(*(torch.tensor(a, dtype=torch.float32) for a in (Gs[ix], Ls[ix], M))).numpy()
                Etr, Ete = emb(tr, Mtr), emb(te, Mte)
            gb = lgb.LGBMClassifier(n_estimators=250, learning_rate=0.03, num_leaves=7, min_child_samples=5,
                                    subsample=0.8, subsample_freq=1, colsample_bytree=0.6, reg_lambda=3, verbose=-1, class_weight="balanced")
            gb.fit(np.hstack([feats[tr], Etr]), y[tr])
            out["hybrid"] = gb.predict_proba(np.hstack([feats[te], Ete]))
    if name == "features_gbm":
        import lightgbm as lgb
        gb = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.03, num_leaves=7, min_child_samples=5,
                                subsample=0.8, subsample_freq=1, colsample_bytree=0.6, reg_lambda=3, verbose=-1, class_weight="balanced")
        gb.fit(feats[tr], y[tr])
        out["features_gbm"] = gb.predict_proba(feats[te])
    if name == "baseline_cnn":
        out["baseline_cnn"] = run_baseline(tr, te, T)
    return out


def run_baseline(tr, te, T):
    """The production DeepExoFusionNet exactly as train_deep_learning.py trains it
    (Adam 1e-3, 35 epochs, 4x metadata-dropout augmentation), but fed the same raw views
    the production pipeline uses (quarter-normalised, NOT detrended) for a like-for-like
    baseline."""
    import torch
    import torch.nn as nn
    from app.ml.deep_learning_pipeline import DeepExoFusionNet
    meta = json.load(open(STUDY_META))
    raw = np.load(os.path.join(F.DATA_DIR, "kepler_study_raw_views.npz"))
    Graw, Lraw = raw["global"], raw["local"]
    y = T["y"]
    rng = np.random.RandomState(0)

    def meta_vec(i, drop):
        m = dict(meta[i])
        if drop:
            for k in ("st_teff", "st_rad", "j_mag", "k_mag", "h_mag", "g_mag", "r_mag"):
                if m.get(k) is not None and rng.uniform() < 0.25:
                    m[k] = None
        return dl_vetting_engine.build_metadata_vector(m)

    cen = np.zeros((3, 201), dtype=np.float32)

    def tens(idx, drop, reps):
        G = np.repeat(Graw[idx], reps, axis=0)
        L = np.repeat(Lraw[idx], reps, axis=0)
        M = np.array([meta_vec(i, drop) for i in idx for _ in range(reps)], dtype=np.float32)
        yy = np.repeat(y[idx], reps)
        C = np.repeat(cen[None], len(yy), axis=0)
        return [torch.tensor(a, dtype=torch.float32) for a in (G[:, None], L[:, None], C, M)], torch.tensor(yy)

    (Gt, Lt, Ct, Mt), yt = tens(tr, True, 4)
    model = DeepExoFusionNet(num_classes=3)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    crit = nn.CrossEntropyLoss()
    torch.manual_seed(0)
    for _ in range(35):
        model.train()
        perm = torch.randperm(len(yt))
        for i in range(0, len(yt), 16):
            idx = perm[i:i + 16]
            if len(idx) < 2:
                continue
            opt.zero_grad()
            crit(model(Gt[idx], Lt[idx], Ct[idx], Mt[idx]), yt[idx]).backward()
            opt.step()
    (Ge, Le, Ce, Me), _ = tens(te, False, 1)
    model.eval()
    with torch.no_grad():
        return torch.softmax(model(Ge, Le, Ce, Me), 1).numpy()


def build_raw_views(T, meta):
    """Raw (non-detrended, quarter-normalised) views exactly as the production fetch builds them."""
    out_path = os.path.join(F.DATA_DIR, "kepler_study_raw_views.npz")
    if os.path.exists(out_path) and len(np.load(out_path)["global"]) == len(meta):
        return
    rows = {}
    for label, where in F.LABEL_QUERIES:
        for r in F.fetch_koi_rows(label, where, meta[0]["_per_class"]):
            rows[(int(r["kepid"]), round(float(r["koi_period"]), 6))] = r
    G, L = [], []
    for m in meta:
        r = rows[(m["kepid"], round(m["period"], 6))]
        lc = np.load(os.path.join(F.LC_CACHE_DIR, f"{m['kepid']}.npz"))
        g, l = dl_vetting_engine.preprocess_lightcurve(lc["time"], lc["flux"], float(r["koi_period"]), float(r["koi_duration"]), float(r["koi_time0bk"]))
        G.append(g - 1.0); L.append(l - 1.0)
    np.savez(out_path, **{"global": np.stack(G).astype(np.float32), "local": np.stack(L).astype(np.float32)})


# --------------------------------------------------------------------------- main


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-class", type=int, default=150)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--models", default="features_gbm,compact_cnn,hybrid,baseline_cnn")
    args = ap.parse_args()

    T, meta = build_table(args.per_class)
    print(f"Study table: {len(T['y'])} KOIs from {len(set(T['groups'].tolist()))} stars; "
          f"classes {np.bincount(T['y']).tolist()}")
    if "baseline_cnn" in args.models:
        build_raw_views(T, meta)

    from sklearn.model_selection import StratifiedGroupKFold
    from sklearn.metrics import accuracy_score, f1_score
    results = {}
    for rep in range(args.repeats):
        skf = StratifiedGroupKFold(n_splits=args.folds, shuffle=True, random_state=rep)
        for fold, (tr, te) in enumerate(skf.split(T["feats"], T["y"], T["groups"])):
            for name in args.models.split(","):
                t0 = time.time()
                for k, p in evaluate_fold(name, tr, te, T).items():
                    pred = p.argmax(1)
                    results.setdefault(k, []).append({
                        "acc": accuracy_score(T["y"][te], pred),
                        "macro_f1": f1_score(T["y"][te], pred, average="macro"),
                        "per_class": [float(np.mean(pred[T["y"][te] == c] == c)) if (T["y"][te] == c).any() else None for c in range(3)],
                    })
                print(f"  rep {rep} fold {fold} {name:13s} {time.time()-t0:5.1f}s", flush=True)

    report = {"n_kois": int(len(T["y"])), "n_stars": int(len(set(T["groups"].tolist()))),
              "class_counts": dict(zip(CLASS_NAMES, np.bincount(T["y"]).tolist())),
              "protocol": f"StratifiedGroupKFold(k={args.folds}) x {args.repeats} repeats, grouped by KIC",
              "models": {}}
    print("\n=== Results (mean ± std over folds) ===")
    for k, rs in results.items():
        acc = np.array([r["acc"] for r in rs]); f1 = np.array([r["macro_f1"] for r in rs])
        pc = np.array([[x if x is not None else np.nan for x in r["per_class"]] for r in rs])
        report["models"][k] = {"accuracy_mean": float(acc.mean()), "accuracy_std": float(acc.std()),
                               "macro_f1_mean": float(f1.mean()), "macro_f1_std": float(f1.std()),
                               "per_class_recall": dict(zip(CLASS_NAMES, np.nanmean(pc, axis=0).round(3).tolist())),
                               "n_folds": len(rs)}
        print(f"{k:13s} acc {acc.mean():.3f}±{acc.std():.3f}  macroF1 {f1.mean():.3f}±{f1.std():.3f}  recall {np.nanmean(pc, axis=0).round(2)}")
    with open(REPORT_PATH, "w") as fh:
        json.dump(report, fh, indent=2)
    print(f"\nWrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
