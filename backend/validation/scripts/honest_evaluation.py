"""
Honest evaluation of the tabular evidence-consistency model.

The published held-out numbers (acc 0.854 / AUC 0.927) come from one random stratified split of
the TOIs. That protocol answers "how well does it recover labels for TOIs like the training ones",
which flatters a model whose real job is scoring *new* candidates. This script reports, for the
shipped model configuration and for a TOI-table-only baseline:

  * random stratified 5-fold CV (the published protocol, for reference),
  * star-grouped CV (no star appears on both sides of a split),
  * time-forward splits (train on TOIs created up to a cutoff, test on later ones),

each with 95% bootstrap confidence intervals resampled BY STAR, plus the paired AUC difference
"full model minus TOI-only", which is the number that says what the cross-catalog features add.

    python validation/scripts/honest_evaluation.py [--repeats 5] [--boot 1000]

Writes backend/app/ml/honest_evaluation_report.json (served by /api/v1/predictions/honest_evaluation).
"""
import argparse
import json
import os
import sys
import warnings
from datetime import datetime, timezone

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(os.path.dirname(HERE))
REPO = os.path.dirname(BACKEND)
sys.path.insert(0, os.path.join(REPO, "validation", "scripts"))

import lightgbm as lgb  # noqa: E402
from sklearn.impute import SimpleImputer  # noqa: E402
from sklearn.metrics import accuracy_score, brier_score_loss, roc_auc_score  # noqa: E402
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402

from train_and_serialize_model import DATA_PATH, LGBM_PARAMS, build_features  # noqa: E402

OUT = os.path.join(BACKEND, "app", "ml", "honest_evaluation_report.json")

# Columns that exist in the TOI table itself (no Gaia / 2MASS / Pan-STARRS involvement).
TOI_ONLY = ["pl_orbper", "pl_trandurh", "pl_trandep", "pl_rade", "pl_insol", "pl_eqt",
            "st_teff", "st_rad", "st_logg", "st_dist"]
TIME_CUTOFFS = ["2020-12-31", "2021-12-31", "2022-12-31"]


def make_model(seed=42):
    return make_pipeline(SimpleImputer(strategy="median"), lgb.LGBMClassifier(**{**LGBM_PARAMS, "random_state": seed}))


def metrics(y, p):
    return {"accuracy": float(accuracy_score(y, p >= 0.5)), "roc_auc": float(roc_auc_score(y, p)),
            "brier": float(brier_score_loss(y, p))}


def star_bootstrap(y, p_full, p_base, stars, n_boot, seed=0):
    """95% CIs from resampling whole stars (siblings stay together), incl. the paired AUC difference."""
    rng = np.random.RandomState(seed)
    uniq = np.unique(stars)
    idx_by_star = {s: np.flatnonzero(stars == s) for s in uniq}
    keys = ["acc_full", "auc_full", "brier_full", "acc_base", "auc_base", "auc_diff"]
    draws = {k: [] for k in keys}
    for _ in range(n_boot):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([idx_by_star[s] for s in pick])
        yy = y[idx]
        if yy.min() == yy.max():
            continue
        a_f, a_b = roc_auc_score(yy, p_full[idx]), roc_auc_score(yy, p_base[idx])
        draws["acc_full"].append(accuracy_score(yy, p_full[idx] >= 0.5))
        draws["auc_full"].append(a_f)
        draws["brier_full"].append(brier_score_loss(yy, p_full[idx]))
        draws["acc_base"].append(accuracy_score(yy, p_base[idx] >= 0.5))
        draws["auc_base"].append(a_b)
        draws["auc_diff"].append(a_f - a_b)
    return {k: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] for k, v in draws.items()}


def summarise(y, p_full, p_base, stars, n_boot):
    return {
        "n": int(len(y)), "n_stars": int(len(np.unique(stars))), "positive_rate": float(y.mean()),
        "full_model": metrics(y, p_full), "toi_only_baseline": metrics(y, p_base),
        "auc_gain_from_cross_catalog_features": float(roc_auc_score(y, p_full) - roc_auc_score(y, p_base)),
        "ci95_by_star": star_bootstrap(y, p_full, p_base, stars, n_boot),
    }


def oof_predictions(splitter, X, y, groups, cols_full, cols_base, repeats):
    """Out-of-fold probabilities averaged over repeats (different shuffles)."""
    p_full, p_base = np.zeros(len(y)), np.zeros(len(y))
    for rep in range(repeats):
        for tr, te in splitter(rep).split(X, y, groups):
            for cols, out in ((cols_full, p_full), (cols_base, p_base)):
                m = make_model(rep).fit(X.iloc[tr][cols], y[tr])
                out[te] += m.predict_proba(X.iloc[te][cols])[:, 1] / repeats
    return p_full, p_base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--boot", type=int, default=1000)
    args = ap.parse_args()

    df = pd.read_csv(DATA_PATH)
    df = df[df["tfopwg_disp"].isin(["CP", "KP", "FP", "FA"])].copy().reset_index(drop=True)
    df["label"] = df["tfopwg_disp"].map({"CP": 1, "KP": 1, "FP": 0, "FA": 0})
    feats, cols_full = build_features(df)
    X, y, stars = feats[cols_full], df["label"].values, df["tid"].values
    created = pd.to_datetime(df["toi_created"], errors="coerce")
    print(f"{len(y)} labelled TOIs, {len(np.unique(stars))} stars, positive rate {y.mean():.3f}; "
          f"{(pd.Series(stars).value_counts() > 1).sum()} stars have >1 TOI.")

    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "n_labelled_tois": int(len(y)),
              "baseline_definition": "TOI-table columns only: " + ", ".join(TOI_ONLY),
              "full_model_features": cols_full, "protocols": {}}

    # 1. random stratified (the protocol the published numbers came from)
    p_f, p_b = oof_predictions(lambda r: StratifiedKFold(5, shuffle=True, random_state=r), X, y, None,
                               cols_full, TOI_ONLY, args.repeats)
    report["protocols"]["random_stratified_5fold"] = summarise(y, p_f, p_b, stars, args.boot)

    # 2. star-grouped: no star on both sides
    p_f, p_b = oof_predictions(lambda r: StratifiedGroupKFold(5, shuffle=True, random_state=r), X, y, stars,
                               cols_full, TOI_ONLY, args.repeats)
    report["protocols"]["star_grouped_5fold"] = summarise(y, p_f, p_b, stars, args.boot)

    # 3. time-forward: train on TOIs created up to the cutoff, test on later ones
    for cut in TIME_CUTOFFS:
        tr = np.flatnonzero((created <= cut).values)
        te = np.flatnonzero((created > cut).values)
        if len(te) < 100 or y[te].min() == y[te].max():
            continue
        # a star appearing on both sides is still possible across time; drop test TOIs whose star is in train
        te = te[~np.isin(stars[te], stars[tr])]
        pf = make_model().fit(X.iloc[tr][cols_full], y[tr]).predict_proba(X.iloc[te][cols_full])[:, 1]
        pb = make_model().fit(X.iloc[tr][TOI_ONLY], y[tr]).predict_proba(X.iloc[te][TOI_ONLY])[:, 1]
        s = summarise(y[te], pf, pb, stars[te], args.boot)
        s["train_n"] = int(len(tr))
        s["train_positive_rate"] = float(y[tr].mean())
        report["protocols"][f"time_forward_train_to_{cut}"] = s

    g = report["protocols"]["star_grouped_5fold"]
    t = report["protocols"][f"time_forward_train_to_{TIME_CUTOFFS[0]}"]
    report["headline"] = (
        f"Star-grouped CV: AUC {g['full_model']['roc_auc']:.3f} "
        f"(95% CI {g['ci95_by_star']['auc_full'][0]:.3f}-{g['ci95_by_star']['auc_full'][1]:.3f}); "
        f"TOI-table-only baseline {g['toi_only_baseline']['roc_auc']:.3f}; the cross-catalog features add "
        f"{g['auc_gain_from_cross_catalog_features']:+.3f} AUC "
        f"(95% CI {g['ci95_by_star']['auc_diff'][0]:+.3f} to {g['ci95_by_star']['auc_diff'][1]:+.3f}). "
        f"Time-forward (train to {TIME_CUTOFFS[0]}): AUC {t['full_model']['roc_auc']:.3f}, "
        f"Brier {t['full_model']['brier']:.3f}.")
    with open(OUT, "w") as f:
        json.dump(report, f, indent=2)

    print("\n" + report["headline"] + "\n")
    for name, s in report["protocols"].items():
        print(f"{name:42s} n={s['n']:5d} full AUC {s['full_model']['roc_auc']:.3f} acc {s['full_model']['accuracy']:.3f} "
              f"Brier {s['full_model']['brier']:.3f} | TOI-only AUC {s['toi_only_baseline']['roc_auc']:.3f} "
              f"| gain {s['auc_gain_from_cross_catalog_features']:+.3f} "
              f"[{s['ci95_by_star']['auc_diff'][0]:+.3f}, {s['ci95_by_star']['auc_diff'][1]:+.3f}]")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
