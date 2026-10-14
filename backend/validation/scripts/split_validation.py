"""
Held-out split validation of (A) the A-F health grade and (B) the catalog-hygiene flags.

Both were first measured on data the author had already seen. Here every number comes from rows that
were not used to fit anything:

  * star-grouped 5-fold CV (no star on both sides of a split),
  * time-forward splits (fit on TOIs created up to a cutoff, test on later TOIs of NEW stars).

(A) Grade. The shipped grade is a hand-weighted catalog-consistency score. The challenger is the tabular
    LightGBM planet probability cut at fixed bands (0.90/0.75/0.50/0.25). Per grade we report the share
    of labelled TOIs that are false positives, with Wilson 95% CIs; the model grade is always scored on
    folds the model did not train on.
(B) Flags. Thresholds that were literature-fixed stay fixed. The one data-calibrated threshold (the
    transit-vs-Gaia density band) is re-fitted on the TRAIN part only, then frozen and applied to the
    test part. Per flag: false-positive rate flagged vs unflagged, risk difference with Newcombe CI.

Limit this cannot remove: dispositions are partly decided from the same Gaia/RUWE evidence the flags
use (label circularity), so a retrospective split can flatter the flags. Only the frozen prospective
snapshot is free of that. Read this as a screening result.

    python validation/scripts/split_validation.py [--repeats 3]

Writes backend/app/ml/split_validation_report.json.
"""
import argparse
import json
import math
import os
import sys
import warnings
from datetime import datetime, timezone
from types import SimpleNamespace

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(os.path.dirname(HERE))
REPO = os.path.dirname(BACKEND)
sys.path.insert(0, BACKEND)
sys.path.insert(0, os.path.join(REPO, "validation", "scripts"))

import lightgbm as lgb  # noqa: E402
from sklearn.impute import SimpleImputer  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402
from sklearn.model_selection import StratifiedGroupKFold  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402

from app.science import flags as F  # noqa: E402
from app.science.health import compute_health_score_from_values, grade_from_probability  # noqa: E402
from app.science.prospective import evaluate, wilson_interval  # noqa: E402
from train_and_serialize_model import DATA_PATH, LGBM_PARAMS, build_features  # noqa: E402

OUT = os.path.join(BACKEND, "app", "ml", "split_validation_report.json")
TIME_CUTOFFS = ["2020-12-31", "2021-12-31", "2022-12-31"]
GRADES = "ABCDF"


def _nan_to_none(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)


def old_health(row) -> tuple:
    """The shipped hand-weighted grade, rebuilt from the dataset columns exactly as ingest.py feeds it."""
    def diff(a, b):
        return abs(a - b) if a is not None and b is not None else None
    st_teff, g_teff = _nan_to_none(row.st_teff), _nan_to_none(row.Teff)
    st_rad, g_rad = _nan_to_none(row.st_rad), _nan_to_none(row.Rad)
    st_dist, g_dist = _nan_to_none(row.st_dist), _nan_to_none(row.Dist)
    ruwe = _nan_to_none(row.RUWE)
    comp = sum(v is not None for v in [st_teff, g_teff, st_rad, g_rad, st_dist, g_dist, ruwe]) / 7
    rp = None
    if g_rad is not None and _nan_to_none(row.pl_trandep) is not None:
        rp = g_rad * math.sqrt(row.pl_trandep * 1e-6) * 109.2
    r = compute_health_score_from_values(diff(st_teff, g_teff), diff(st_rad, g_rad), diff(st_dist, g_dist),
                                         ruwe, bool(rp is not None and rp > 22.0), comp, False)
    return r.score, r.grade


def make_model(seed=42):
    return make_pipeline(SimpleImputer(strategy="median"), lgb.LGBMClassifier(**{**LGBM_PARAMS, "random_state": seed}))


def grade_table(y, grades):
    """FP share per grade (+Wilson CI). y: 1 = planet, 0 = false positive."""
    out = {}
    for g in GRADES:
        idx = [i for i, x in enumerate(grades) if x == g]
        fp = sum(1 for i in idx if y[i] == 0)
        out[g] = {"n": len(idx), "false_positive_share": (fp / len(idx)) if idx else None,
                  "ci95": wilson_interval(fp, len(idx)) if idx else None}
    return out


def grade_section(y, old_score, old_grade, p_model):
    new_grade = [grade_from_probability(p) for p in p_model]
    return {
        "n": int(len(y)), "base_rate_false_positive": float(1 - np.mean(y)),
        "auc_old_hand_grade": float(roc_auc_score(y, old_score)),
        "auc_model_probability": float(roc_auc_score(y, p_model)),
        "old_hand_grade": grade_table(y, old_grade),
        "model_grade": grade_table(y, new_grade),
    }


def calibration_bins(y, p, n_bins=10):
    edges = np.linspace(0, 1, n_bins + 1)
    out = []
    for i in range(n_bins):
        m = (p >= edges[i]) & ((p < edges[i + 1]) if i < n_bins - 1 else (p <= edges[i + 1]))
        out.append({"lo": round(float(edges[i]), 2), "hi": round(float(edges[i + 1]), 2), "n": int(m.sum()),
                    "mean_predicted": float(p[m].mean()) if m.any() else None,
                    "observed_planet_frequency": float(y[m].mean()) if m.any() else None})
    return out


# ---------------------------------------------------------------- flags
def row_objects(r):
    cand = SimpleNamespace(orbper=_nan_to_none(r.pl_orbper), trandurh=_nan_to_none(r.pl_trandurh),
                           trandep=_nan_to_none(r.pl_trandep))
    host = SimpleNamespace(ruwe=_nan_to_none(r.RUWE), rad=_nan_to_none(r.Rad), mass=_nan_to_none(r.gmass),
                           teff=_nan_to_none(r.Teff), toi_teff=_nan_to_none(r.st_teff), toi_rad=_nan_to_none(r.st_rad))
    return cand, host


def flags_for(df):
    """List of flag dicts for each row, using the CURRENT module THRESHOLDS."""
    out = []
    for r in df.itertuples(index=False):
        cand, host = row_objects(r)
        out.append(F.compute_flags(cand, host, None))
    return out


def fit_density_band(train_df):
    """Central 95% of ln(rho_transit/rho_gaia) over CONFIRMED planets in the TRAIN part only."""
    from app.science.density import compute_gaia_density_cgs, compute_transit_density_cgs, radius_ratio_from_depth_ppm
    vals = []
    for r in train_df[train_df.label == 1].itertuples(index=False):
        cand, host = row_objects(r)
        dt = compute_transit_density_cgs(cand.orbper, cand.trandurh, radius_ratio=radius_ratio_from_depth_ppm(cand.trandep))
        dg = compute_gaia_density_cgs(host.mass, host.rad)
        if dt and dg:
            vals.append(math.log(dt / dg))
    if len(vals) < 30:
        return None
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5)), len(vals)


def flag_test(train_df, test_df):
    band = fit_density_band(train_df)
    saved = dict(F.THRESHOLDS)
    try:
        if band:
            F.THRESHOLDS["density_log_ratio_low"], F.THRESHOLDS["density_log_ratio_high"] = band[0], band[1]
        fl = flags_for(test_df)
    finally:
        F.THRESHOLDS.clear()
        F.THRESHOLDS.update(saved)
    rows, disp = [], {}
    for i, (f, d) in enumerate(zip(fl, test_df.tfopwg_disp.tolist())):
        key = str(i)
        rows.append({"toi": key, "flags": f, "any_core_flag": F.any_core_flag(f)})
        disp[key] = d
    names = [k for k in fl[0] if k not in ("evidence_score_low", "crossmatch_suspect")]
    res = evaluate(rows, disp, names)
    return {"density_band_fitted_on_train": None if not band else {"low": band[0], "high": band[1], "n_confirmed": band[2]},
            "n_test": len(test_df), "base_rate_false_positive": res["base_rate_false_positive"],
            "per_flag": res["per_flag"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=3)
    args = ap.parse_args()

    df = pd.read_csv(DATA_PATH)
    df = df[df["tfopwg_disp"].isin(["CP", "KP", "FP", "FA"])].copy().reset_index(drop=True)
    df["label"] = df["tfopwg_disp"].map({"CP": 1, "KP": 1, "FP": 0, "FA": 0})
    df["gmass"] = df["Mass-Flame"]
    feats, cols = build_features(df)
    X, y, stars = feats[cols], df["label"].values, df["tid"].values
    created = pd.to_datetime(df["toi_created"], errors="coerce")
    old = [old_health(r) for r in df.itertuples(index=False)]
    old_score, old_grade = np.array([o[0] for o in old]), [o[1] for o in old]
    print(f"{len(y)} labelled TOIs, {len(np.unique(stars))} stars, FP base rate {1 - y.mean():.3f}")

    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "n_labelled": int(len(y)),
              "grade_bands_model": {"A": ">=0.90", "B": ">=0.75", "C": ">=0.50", "D": ">=0.25", "F": "<0.25"},
              "grade": {}, "flags": {}}

    # ---- (A) star-grouped OOF
    p_oof = np.zeros(len(y))
    for rep in range(args.repeats):
        for tr, te in StratifiedGroupKFold(5, shuffle=True, random_state=rep).split(X, y, stars):
            p_oof[te] += make_model(rep).fit(X.iloc[tr], y[tr]).predict_proba(X.iloc[te])[:, 1] / args.repeats
    report["grade"]["star_grouped_5fold"] = grade_section(y, old_score, old_grade, p_oof)
    report["grade"]["star_grouped_5fold"]["model_calibration_bins"] = calibration_bins(y, p_oof)

    # ---- (A) time-forward
    for cut in TIME_CUTOFFS:
        tr = np.flatnonzero((created <= cut).values)
        te = np.flatnonzero((created > cut).values)
        te = te[~np.isin(stars[te], stars[tr])]
        if len(te) < 100:
            continue
        p = make_model().fit(X.iloc[tr], y[tr]).predict_proba(X.iloc[te])[:, 1]
        sec = grade_section(y[te], old_score[te], [old_grade[i] for i in te], p)
        sec["train_n"] = int(len(tr))
        report["grade"][f"time_forward_train_to_{cut}"] = sec

    # ---- (B) flags: time-forward, density band refit on train only
    for cut in TIME_CUTOFFS:
        tr = np.flatnonzero((created <= cut).values)
        te = np.flatnonzero((created > cut).values)
        te = te[~np.isin(stars[te], stars[tr])]
        if len(te) < 100:
            continue
        report["flags"][f"time_forward_train_to_{cut}"] = flag_test(df.iloc[tr], df.iloc[te])
    # ---- (B) flags: star-grouped folds, pooled test parts
    pooled_rows, pooled_disp, k = [], {}, 0
    folds = list(StratifiedGroupKFold(5, shuffle=True, random_state=0).split(X, y, stars))
    for tr, te in folds:
        band = fit_density_band(df.iloc[tr])
        saved = dict(F.THRESHOLDS)
        try:
            if band:
                F.THRESHOLDS["density_log_ratio_low"], F.THRESHOLDS["density_log_ratio_high"] = band[0], band[1]
            fl = flags_for(df.iloc[te])
        finally:
            F.THRESHOLDS.clear()
            F.THRESHOLDS.update(saved)
        for f, d in zip(fl, df.iloc[te].tfopwg_disp.tolist()):
            pooled_rows.append({"toi": str(k), "flags": f, "any_core_flag": F.any_core_flag(f)})
            pooled_disp[str(k)] = d
            k += 1
    names = [n for n in pooled_rows[0]["flags"] if n not in ("evidence_score_low", "crossmatch_suspect")]
    res = evaluate(pooled_rows, pooled_disp, names)
    report["flags"]["star_grouped_5fold_pooled"] = {"n_test": len(pooled_rows),
                                                    "base_rate_false_positive": res["base_rate_false_positive"],
                                                    "per_flag": res["per_flag"]}

    with open(OUT, "w") as f:
        json.dump(report, f, indent=2)

    def pct(x):
        return "  n/a" if x is None else f"{100 * x:5.1f}%"
    for name, s in report["grade"].items():
        print(f"\n[grade] {name}  n={s['n']}  FP base {pct(s['base_rate_false_positive'])}  "
              f"AUC old {s['auc_old_hand_grade']:.3f}  model {s['auc_model_probability']:.3f}")
        for g in GRADES:
            o, m = s["old_hand_grade"][g], s["model_grade"][g]
            print(f"   {g}: old n={o['n']:4d} FP {pct(o['false_positive_share'])} | model n={m['n']:4d} FP {pct(m['false_positive_share'])}")
    for name, s in report["flags"].items():
        print(f"\n[flags] {name}  n_test={s['n_test']}  FP base {pct(s['base_rate_false_positive'])}  band={s.get('density_band_fitted_on_train')}")
        for fn, v in s["per_flag"].items():
            rd, ci = v["risk_difference"], v["risk_difference_ci95"]
            print(f"   {fn:24s} flagged n={v['n_flagged']:4d} FP {pct(v['fp_rate_flagged'])} | clean n={v['n_clean']:4d} FP {pct(v['fp_rate_clean'])} | "
                  f"diff {'n/a' if rd is None else f'{rd:+.2f}'} [{'n/a' if not ci else f'{ci[0]:+.2f},{ci[1]:+.2f}'}]")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
