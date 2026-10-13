"""
What does the light-curve vetter's accuracy actually depend on, and are its probabilities usable?

Uses the same real-Kepler study table as train_lightcurve_vetter.py (star-grouped folds) and answers
the questions an independent review raised:

  1. ABLATION -- is the score driven by the light curve, or by catalog inputs (stellar radius, Teff,
     catalog depth, the radius/duration plausibility features, colours)? A vetter that is really a
     catalog-prior would not transfer.
  2. PER-FLAG RECALL -- Kepler's "Eclipsing Binary" label is (fpflag_ss OR fpflag_co): a significant
     secondary eclipse (visible in the light curve) OR a centroid offset (invisible to this model).
     Recall on the secondary-eclipse subset vs the centroid-only subset says how much of that class
     the model can legitimately see.
  3. CALIBRATION -- fit multinomial temperature scaling on out-of-fold probabilities, evaluated
     out-of-sample (nested over stars) so the improvement is not self-graded.
  4. 95% CIs by star bootstrap for every accuracy.

    python validation/scripts/vetter_ablation.py [--repeats 5] [--boot 1000]
Writes backend/app/ml/lightcurve_vetter_ablation.json
"""
import argparse
import json
import os
import sys
import warnings
from datetime import datetime, timezone

import numpy as np

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, BACKEND)
sys.path.insert(0, HERE)

import lightgbm as lgb  # noqa: E402
from scipy.optimize import minimize_scalar  # noqa: E402
from sklearn.metrics import accuracy_score, log_loss  # noqa: E402
from sklearn.model_selection import StratifiedGroupKFold  # noqa: E402

import fetch_real_kepler_dataset as F  # noqa: E402
from app.ml import lightcurve_features as LF  # noqa: E402
from dl_architecture_study import build_table  # noqa: E402
from train_lightcurve_vetter import PARAMS, augment_missingness  # noqa: E402

OUT = os.path.join(BACKEND, "app", "ml", "lightcurve_vetter_ablation.json")
CATALOG_DEPENDENT = ["teff", "rstar", "catalog_depth_ppm", "implied_rp_earth", "dur_ratio", "j_k", "g_r", "g_k"]
LIGHT_CURVE_ONLY = [f for f in LF.FEATURE_NAMES if f not in CATALOG_DEPENDENT]


def oof(X, y, groups, cols, repeats, augment=True):
    idx = [LF.FEATURE_NAMES.index(c) for c in cols]
    P = np.zeros((len(y), 3))
    for rep in range(repeats):
        for tr, te in StratifiedGroupKFold(5, shuffle=True, random_state=rep).split(X, y, groups):
            Xtr, ytr = X[tr][:, idx], y[tr]
            if augment:   # the production recipe: mask the stellar/photometry groups in copies
                keep = [c for c in cols]
                full = np.full((len(tr), len(LF.FEATURE_NAMES)), np.nan)
                full[:, idx] = Xtr
                Xa, ya = augment_missingness(full, ytr)
                Xtr, ytr = Xa[:, idx], ya
            m = lgb.LGBMClassifier(**PARAMS, random_state=rep).fit(Xtr, ytr)
            P[te] += m.predict_proba(X[te][:, idx]) / repeats
    return P


def boot_ci(y, P, stars, n_boot, seed=0):
    rng = np.random.RandomState(seed)
    uniq = np.unique(stars)
    by = {s: np.flatnonzero(stars == s) for s in uniq}
    accs = []
    for _ in range(n_boot):
        idx = np.concatenate([by[s] for s in rng.choice(uniq, len(uniq), replace=True)])
        accs.append(accuracy_score(y[idx], P[idx].argmax(1)))
    return [float(np.percentile(accs, 2.5)), float(np.percentile(accs, 97.5))]


def temperature_fit(P, y):
    logp = np.log(np.clip(P, 1e-9, 1))
    def nll(t):
        z = logp / t
        z = z - z.max(1, keepdims=True)
        q = np.exp(z) / np.exp(z).sum(1, keepdims=True)
        return log_loss(y, q, labels=[0, 1, 2])
    return float(minimize_scalar(nll, bounds=(0.3, 5.0), method="bounded").x)


def apply_t(P, t):
    z = np.log(np.clip(P, 1e-9, 1)) / t
    z = z - z.max(1, keepdims=True)
    return np.exp(z) / np.exp(z).sum(1, keepdims=True)


def ece(P, y, bins=10):
    conf, pred = P.max(1), P.argmax(1)
    edges = np.linspace(0, 1, bins + 1)
    tot = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            tot += m.mean() * abs((pred[m] == y[m]).mean() - conf[m].mean())
    return float(tot)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-class", type=int, default=100)
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--boot", type=int, default=1000)
    args = ap.parse_args()

    T, meta = build_table(args.per_class)
    X, y, stars = T["feats"], T["y"], T["groups"]
    print(f"{len(y)} KOIs, {len(np.unique(stars))} stars")

    # ---- 1. ablation
    variants = {
        "all features (shipped)": LF.FEATURE_NAMES,
        "light-curve features only (no stellar/catalog inputs)": LIGHT_CURVE_ONLY,
        "without implied radius + duration ratio": [f for f in LF.FEATURE_NAMES if f not in ("implied_rp_earth", "dur_ratio")],
        "without catalog depth": [f for f in LF.FEATURE_NAMES if f != "catalog_depth_ppm"],
        "without stellar colours": [f for f in LF.FEATURE_NAMES if f not in ("j_k", "g_r", "g_k")],
    }
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "n_kois": int(len(y)),
              "n_stars": int(len(np.unique(stars))), "protocol": f"StratifiedGroupKFold(5) x {args.repeats}, by KIC",
              "ablation": {}}
    probs = {}
    for name, cols in variants.items():
        P = oof(X, y, stars, cols, args.repeats)
        probs[name] = P
        acc = float(accuracy_score(y, P.argmax(1)))
        report["ablation"][name] = {"accuracy": acc, "ci95_by_star": boot_ci(y, P, stars, args.boot), "n_features": len(cols)}
        print(f"  {name:55s} acc {acc:.3f}  CI {report['ablation'][name]['ci95_by_star']}")
    P_ship = probs["all features (shipped)"]

    # ---- 2. per-flag recall for the 'Eclipsing Binary' class
    flags = {}
    for label, where in F.LABEL_QUERIES:
        if label != 1:
            continue
        for r in F.fetch_koi_rows(label, where, args.per_class):
            flags[(int(r["kepid"]), round(float(r["koi_period"]), 6))] = (int(r["koi_fpflag_ss"] or 0), int(r["koi_fpflag_co"] or 0))
    ss = np.array([flags.get((m["kepid"], round(m["period"], 6)), (np.nan, np.nan))[0] for m in meta], float)
    co = np.array([flags.get((m["kepid"], round(m["period"], 6)), (np.nan, np.nan))[1] for m in meta], float)
    eb = (y == 1)
    pred = P_ship.argmax(1)
    subsets = {"secondary-eclipse flag only (visible in the light curve)": eb & (ss == 1) & (co == 0),
               "centroid-offset flag only (invisible to this model)": eb & (ss == 0) & (co == 1),
               "both flags": eb & (ss == 1) & (co == 1)}
    report["eclipsing_binary_recall_by_kepler_flag"] = {
        k: {"n": int(m.sum()), "recall": float((pred[m] == 1).mean()) if m.any() else None} for k, m in subsets.items()}
    for k, v in report["eclipsing_binary_recall_by_kepler_flag"].items():
        print(f"  EB recall, {k}: {v['recall']} (n={v['n']})")

    # ---- 3. calibration, evaluated out-of-sample (temperature fit on other stars' OOF probabilities)
    t_all = temperature_fit(P_ship, y)
    P_cal = np.zeros_like(P_ship)
    for tr, te in StratifiedGroupKFold(5, shuffle=True, random_state=99).split(P_ship, y, stars):
        P_cal[te] = apply_t(P_ship[te], temperature_fit(P_ship[tr], y[tr]))
    report["calibration"] = {
        "temperature_fit_on_all_oof": t_all,
        "ece_before": ece(P_ship, y), "ece_after_nested": ece(P_cal, y),
        "log_loss_before": float(log_loss(y, np.clip(P_ship, 1e-9, 1), labels=[0, 1, 2])),
        "log_loss_after_nested": float(log_loss(y, np.clip(P_cal, 1e-9, 1), labels=[0, 1, 2])),
        "note": "temperature scaling fit on out-of-fold probabilities of OTHER stars (nested), so 'after' is not self-graded",
    }
    print("  calibration:", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in report["calibration"].items() if k != "note"})

    with open(OUT, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
