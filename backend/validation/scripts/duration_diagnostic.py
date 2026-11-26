"""
Does the light-curve vetter do worse on SHORT transits?  (reviewer concern, 2026-11)

The vetter sees light curves binned to 29.4 minutes. Kepler long cadence is natively 29.4 minutes, so
this measures how the model does on short transits AT THAT CADENCE, on held-out stars. It does not
measure what happens when a TESS 2-minute light curve is rebinned (that needs TESS truth labels; the
50-TOI check set is too small to split by duration, which this script reports rather than hides).

Writes backend/app/ml/duration_diagnostic_report.json.

    python validation/scripts/duration_diagnostic.py [--repeats 5]
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
from sklearn.model_selection import StratifiedGroupKFold  # noqa: E402

from app.ml import lightcurve_features as LF  # noqa: E402
from dl_architecture_study import build_table  # noqa: E402
from train_lightcurve_vetter import PARAMS, augment_missingness  # noqa: E402

OUT = os.path.join(BACKEND, "app", "ml", "duration_diagnostic_report.json")
BINS = [("< 2 h", 0.0, 2.0), ("2-4 h", 2.0, 4.0), ("> 4 h", 4.0, 1e9)]


def wilson(k, n, z=1.96):
    if n == 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [round(float((c - h) / d), 3), round(float((c + h) / d), 3)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-class", type=int, default=100)
    ap.add_argument("--repeats", type=int, default=5)
    args = ap.parse_args()

    T, _ = build_table(args.per_class)
    X, y, groups = T["feats"], T["y"], T["groups"]
    dur = X[:, LF.FEATURE_NAMES.index("duration_h")]

    oof = np.zeros((args.repeats, len(y), 3))
    for rep in range(args.repeats):
        for tr, te in StratifiedGroupKFold(5, shuffle=True, random_state=rep).split(X, y, groups):
            Xa, ya = augment_missingness(X[tr], y[tr])
            m = lgb.LGBMClassifier(**PARAMS, random_state=rep).fit(Xa, ya)
            oof[rep, te] = m.predict_proba(X[te])
    pred = oof.mean(axis=0).argmax(1)
    correct = pred == y
    planet = LF.CLASS_NAMES.index("Planet Transit")

    rows = []
    for name, lo, hi in BINS:
        s = (dur >= lo) & (dur < hi) & np.isfinite(dur)
        n, k = int(s.sum()), int(correct[s].sum())
        pl = s & (y == planet)
        npl, kpl = int(pl.sum()), int(correct[pl].sum())
        rows.append({
            "duration_bin": name, "n": n, "accuracy": round(k / n, 3) if n else None, "accuracy_ci95": wilson(k, n),
            "n_true_planets": npl, "planet_recall": round(kpl / npl, 3) if npl else None,
            "planet_recall_ci95": wilson(kpl, npl),
            "class_counts": {c: int((s & (y == i)).sum()) for i, c in enumerate(LF.CLASS_NAMES)},
        })
    overall = int(correct.sum())
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "protocol": f"StratifiedGroupKFold(5) x {args.repeats} repeats, grouped by KIC star; mean OOF probability",
        "cadence_note": "Kepler long cadence is natively 29.4 min, the same binning the vetter uses on TESS. "
                        "This shows short-transit performance at that cadence; it does not test rebinning TESS 2-min data.",
        "n_kois": int(len(y)), "overall_accuracy": round(overall / len(y), 3),
        "median_duration_h": round(float(np.nanmedian(dur)), 2), "min_duration_h": round(float(np.nanmin(dur)), 2),
        "by_duration": rows,
        "limits": ["Bins with few KOIs have wide intervals; read the CI, not the point value.",
                   "Duration correlates with period, star size and class, so a difference here is not proof that "
                   "duration itself is the cause.",
                   "The 50-TOI TESS check set has too few short-transit targets to split by duration."],
    }
    with open(OUT, "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report["by_duration"], indent=1))
    print("overall", report["overall_accuracy"], "->", OUT)


if __name__ == "__main__":
    main()
