"""
Trains the production light-curve vetter: LightGBM on the physics-motivated features in
app/ml/lightcurve_features.py, using real Kepler light curves and real KOI dispositions
(validation/scripts/fetch_real_kepler_dataset.py). Chosen over the CNN by
validation/scripts/dl_architecture_study.py -- see backend/app/ml/dl_architecture_study.json.

Writes:
    backend/app/ml/lightcurve_vetter.pkl          model + feature order + provenance
    backend/app/ml/lightcurve_vetter_report.json  star-grouped CV metrics (honest numbers)

    python validation/scripts/train_lightcurve_vetter.py [--per-class 100]
"""
import argparse
import json
import os
import pickle
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
import sklearn  # noqa: E402
from sklearn.metrics import accuracy_score, brier_score_loss, confusion_matrix, f1_score  # noqa: E402
from sklearn.model_selection import StratifiedGroupKFold  # noqa: E402

from app.ml import lightcurve_features as LF  # noqa: E402
from dl_architecture_study import build_table  # noqa: E402

OUT_MODEL = os.path.join(BACKEND, "app", "ml", "lightcurve_vetter.pkl")
OUT_REPORT = os.path.join(BACKEND, "app", "ml", "lightcurve_vetter_report.json")
MODEL_VERSION = "lightcurve-vetter-gbm-1.1.0"

# Catalog-derived inputs whose absence must carry no label information. In the Kepler training
# set a missing stellar radius/Teff occurred only for "Not Transit-Like" stars (7/39 vs 0/166
# for the other classes), so an unaugmented model learned "no stellar radius -> Not Transit-Like"
# -- and ~20% of production hosts have none (a known planet, TOI-104.01, scored 90% Not
# Transit-Like for that reason alone). Every class therefore also trains on copies with these
# masked, so missingness is equally likely under every label.
STELLAR_GROUP = ["teff", "rstar", "implied_rp_earth", "dur_ratio", "j_k", "g_r", "g_k"]
PHOTOMETRY_GROUP = ["j_k", "g_r", "g_k"]


def _mask(X, names):
    Xm = X.copy()
    for n in names:
        Xm[:, LF.FEATURE_NAMES.index(n)] = np.nan
    return Xm


def augment_missingness(X, y):
    """Original rows + a copy with the whole stellar group missing (host with no TIC/Gaia
    parameters) + a copy with only photometry missing (e.g. Pan-STARRS south of Dec -30)."""
    return (np.vstack([X, _mask(X, STELLAR_GROUP), _mask(X, PHOTOMETRY_GROUP)]), np.concatenate([y, y, y]))


PARAMS = dict(
    n_estimators=300, learning_rate=0.03, num_leaves=7, min_child_samples=5, subsample=0.8,
    subsample_freq=1, colsample_bytree=0.6, reg_lambda=3.0, class_weight="balanced", verbose=-1,
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-class", type=int, default=100)
    ap.add_argument("--repeats", type=int, default=10)
    args = ap.parse_args()

    T, _meta = build_table(args.per_class)
    X, y, groups = T["feats"], T["y"], T["groups"]
    n_stars = len(set(groups.tolist()))
    print(f"{len(y)} KOIs from {n_stars} stars, classes {np.bincount(y).tolist()}")

    accs, f1s, masked_accs = [], [], []
    oof = np.zeros((args.repeats, len(y), 3))
    for rep in range(args.repeats):
        for tr, te in StratifiedGroupKFold(5, shuffle=True, random_state=rep).split(X, y, groups):
            Xa, ya = augment_missingness(X[tr], y[tr])
            m = lgb.LGBMClassifier(**PARAMS, random_state=rep).fit(Xa, ya)
            p = m.predict_proba(X[te])
            masked_accs.append(accuracy_score(y[te], m.predict(_mask(X[te], STELLAR_GROUP))))
            oof[rep, te] = p
            accs.append(accuracy_score(y[te], p.argmax(1)))
            f1s.append(f1_score(y[te], p.argmax(1), average="macro"))
    mean_oof = oof.mean(axis=0)
    pred = mean_oof.argmax(1)
    cm = confusion_matrix(y, pred, labels=[0, 1, 2])
    onehot = np.eye(3)[y]
    brier = float(np.mean(np.sum((mean_oof - onehot) ** 2, axis=1)))
    majority = float(np.bincount(y).max() / len(y))

    print(f"CV accuracy with the stellar inputs masked on the TEST fold: {np.mean(masked_accs):.3f}")
    print(f"CV accuracy {np.mean(accs):.3f} ± {np.std(accs):.3f} (majority-class baseline {majority:.3f}); "
          f"macro-F1 {np.mean(f1s):.3f}; multiclass Brier {brier:.3f}")
    print("confusion (rows=true, cols=pred):\n", cm)

    Xa, ya = augment_missingness(X, y)
    final = lgb.LGBMClassifier(**PARAMS, random_state=0).fit(Xa, ya)
    imp = dict(zip(LF.FEATURE_NAMES, [int(v) for v in final.booster_.feature_importance("gain")]))
    artifact = {
        "model": final, "feature_names": LF.FEATURE_NAMES, "class_names": LF.CLASS_NAMES,
        "model_version": MODEL_VERSION, "trained_at": datetime.now(timezone.utc).isoformat(),
        "n_kois": int(len(y)), "n_stars": n_stars,
        "lightgbm_version": lgb.__version__, "sklearn_version": sklearn.__version__,
    }
    with open(OUT_MODEL, "wb") as f:
        pickle.dump(artifact, f)

    report = {
        "model_version": MODEL_VERSION, "trained_at": artifact["trained_at"],
        "n_kois": int(len(y)), "n_stars": n_stars,
        "class_counts": dict(zip(LF.CLASS_NAMES, np.bincount(y).tolist())),
        "protocol": f"StratifiedGroupKFold(5) x {args.repeats} repeats, grouped by KIC star id",
        "cv_accuracy_mean": float(np.mean(accs)), "cv_accuracy_std": float(np.std(accs)),
        "cv_macro_f1_mean": float(np.mean(f1s)), "majority_class_baseline": majority,
        "cv_accuracy_with_stellar_inputs_missing": float(np.mean(masked_accs)),
        "missingness_augmentation": "stellar group and photometry group masked in training copies, identical across classes",
        "multiclass_brier_oof": brier,
        "confusion_matrix_oof": {"labels": LF.CLASS_NAMES, "rows_true_cols_pred": cm.tolist()},
        "per_class_recall": dict(zip(LF.CLASS_NAMES, [round(float(cm[i, i] / max(cm[i].sum(), 1)), 3) for i in range(3)])),
        "feature_gain_importance": dict(sorted(imp.items(), key=lambda kv: -kv[1])),
        "data_source": "Kepler long-cadence light curves (MAST) + NASA Exoplanet Archive cumulative KOI table "
                       "dispositions/false-positive flags; 2MASS + Pan-STARRS DR1 colours via CDS X-Match.",
        "known_gaps": [
            "Trained on Kepler, served on TESS: SNR-type features scale with the number of observed transits, "
            "so outputs are not calibrated the same way on a single 27-day TESS sector. See tess_transfer_check.",
            "No centroid information: Kepler's 'Eclipsing Binary' label includes its centroid-offset flag, which this "
            "model cannot see. Real TESS centroid offsets are reported separately (has_centroid_dip).",
            "Small sample: the CV spread above is the honest uncertainty on the headline accuracy.",
        ],
    }
    with open(OUT_REPORT, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Wrote {OUT_MODEL}\nWrote {OUT_REPORT}")


if __name__ == "__main__":
    main()
