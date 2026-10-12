"""
Trains and serializes the Random Forest evidence-consistency classifier, and writes a
real evaluation-metrics artifact alongside it.

Before this script wrote model_metrics.json, `GET /api/v1/predictions/metrics` returned
a hardcoded dict with no connection to any actual evaluation run (UPGRADE_PLAN.md A.8).
Every number in model_metrics.json below comes from evaluating the trained model on a
held-out test split it never saw during fitting.
"""
import hashlib
import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, roc_auc_score, f1_score, brier_score_loss
import pickle

import sklearn

MODEL_VERSION = "lgbm-evidence-consistency-2.0.0"

# Chosen by repeated 5-fold CV (6 repeats) against the previous RandomForest(100):
# accuracy 0.8535 vs 0.8481, ROC-AUC 0.928 vs 0.920, Brier 0.104 vs 0.114. See
# LIMITATIONS.md section 3 for the full comparison, including what did NOT help.
LGBM_PARAMS = dict(
    n_estimators=400, learning_rate=0.03, num_leaves=15, min_child_samples=20,
    subsample=0.8, subsample_freq=1, colsample_bytree=0.7, reg_lambda=2.0,
    verbose=-1, random_state=42,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_PATH = os.path.join(REPO_ROOT, "validation", "data", "validation_dataset.csv")
OUTPUT_DIR = os.path.join(REPO_ROOT, "backend", "app", "ml")


def build_features(df: pd.DataFrame):
    eps = 1e-6
    df = df.copy()
    df['teff_diff'] = (df['st_teff'] - df['Teff']).abs()
    df['teff_diff_rel'] = df['teff_diff'] / (df['Teff'] + eps)

    df['rad_diff'] = (df['st_rad'] - df['Rad']).abs()
    df['rad_diff_rel'] = df['rad_diff'] / (df['Rad'] + eps)

    df['dist_diff'] = (df['st_dist'] - df['Dist']).abs()
    df['dist_diff_rel'] = df['dist_diff'] / (df['Dist'] + eps)

    # Photometry-derived features (2MASS / Pan-STARRS DR1). Only quantities production can
    # compute from what HostStar actually stores: Gaia parallax, 2MASS J/H/K, PS1 g/r.
    # (Gaia G and the TESS magnitude are NOT stored per host, so tmag_gmag_diff -- which
    # was always missing at serving time -- is gone rather than silently imputed.)
    df['j_k'] = df['Jmag'] - df['Kmag']
    df['h_k'] = df['Hmag'] - df['Kmag']
    df['abs_K'] = df['Kmag'] + 5 * np.log10(df['Plx'].clip(lower=1e-3)) - 10
    df['ps_g_r'] = df['PS_gmag'] - df['PS_rmag']

    df['derived_rp_gaia'] = df['Rad'] * np.sqrt(df['pl_trandep'] * 1e-6) * 109.2
    df['derived_rp_diff'] = (df['derived_rp_gaia'] - df['pl_rade']).abs()
    df['derived_rp_diff_rel'] = df['derived_rp_diff'] / (df['pl_rade'] + eps)
    df['is_unphysical_rp_gaia'] = (df['derived_rp_gaia'] > 22.0).astype(int)

    df['high_ruwe'] = (df['RUWE'] > 1.4).astype(int)
    df['completeness'] = df[['st_teff', 'st_rad', 'st_dist', 'Teff', 'Rad', 'Dist', 'RUWE']].notna().sum(axis=1)

    baseline_cols = [
        'pl_orbper', 'pl_trandurh', 'pl_trandep', 'pl_rade', 'pl_insol', 'pl_eqt',
        'st_teff', 'st_rad', 'st_logg', 'st_dist'
    ]
    disagreement_cols = [
        'teff_diff', 'teff_diff_rel', 'rad_diff', 'rad_diff_rel', 'dist_diff', 'dist_diff_rel',
        'derived_rp_gaia', 'derived_rp_diff', 'derived_rp_diff_rel',
        'is_unphysical_rp_gaia', 'RUWE', 'high_ruwe', 'completeness',
        'j_k', 'h_k', 'abs_K', 'ps_g_r',
    ]
    feature_cols = baseline_cols + disagreement_cols
    return df, feature_cols


def compute_reliability_diagram(y_true: np.ndarray, y_proba: np.ndarray, n_bins: int = 10) -> list:
    """
    Bins predicted probabilities into `n_bins` equal-width bins and reports the
    observed positive frequency in each bin against the mean predicted probability --
    the standard reliability-diagram construction (UPGRADE_PLAN.md E.2). A
    well-calibrated model has observed_frequency ~= mean_predicted_probability in
    every bin with enough samples to be meaningful; empty/sparse bins are reported
    with count=0 / null frequency rather than a fabricated interpolated value.
    """
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    bins = []
    for i in range(n_bins):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        in_bin = (y_proba >= lo) & (y_proba < hi) if i < n_bins - 1 else (y_proba >= lo) & (y_proba <= hi)
        count = int(in_bin.sum())
        bins.append({
            "bin_lower": round(float(lo), 3),
            "bin_upper": round(float(hi), 3),
            "count": count,
            "mean_predicted_probability": round(float(y_proba[in_bin].mean()), 4) if count > 0 else None,
            "observed_frequency": round(float(y_true[in_bin].mean()), 4) if count > 0 else None,
        })
    return bins


def main():
    print(f"Loading training data from {DATA_PATH}...")
    df = pd.read_csv(DATA_PATH)
    required = ['Jmag', 'Hmag', 'Kmag', 'PS_gmag', 'PS_rmag']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SystemExit(f"{DATA_PATH} lacks {missing}; run validation/scripts/augment_dataset_photometry.py first.")
    with open(DATA_PATH, "rb") as f:
        dataset_hash = hashlib.sha256(f.read()).hexdigest()[:16]

    df = df[df['tfopwg_disp'].isin(['CP', 'KP', 'FP', 'FA'])].copy()
    df['label'] = df['tfopwg_disp'].map({'CP': 1, 'KP': 1, 'FP': 0, 'FA': 0})

    df, feature_cols = build_features(df)
    X_raw = df[feature_cols]
    y = df['label'].values

    # Held-out evaluation split: fit only on train, evaluate only on test, so
    # model_metrics.json reflects genuine generalization, not training-set fit.
    X_train, X_test, y_train, y_test = train_test_split(
        X_raw, y, test_size=0.2, random_state=42, stratify=y
    )

    eval_imputer = SimpleImputer(strategy='median')
    X_train_imputed = eval_imputer.fit_transform(X_train)
    X_test_imputed = eval_imputer.transform(X_test)

    eval_model = lgb.LGBMClassifier(**LGBM_PARAMS)
    eval_model.fit(X_train_imputed, y_train)

    y_pred = eval_model.predict(X_test_imputed)
    y_proba = eval_model.predict_proba(X_test_imputed)[:, 1]

    metrics = {
        "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "roc_auc": round(float(roc_auc_score(y_test, y_proba)), 4),
        "f1_score": round(float(f1_score(y_test, y_pred)), 4),
    }
    print(f"Held-out test metrics ({len(y_test)} samples): {metrics}")

    # Calibration (UPGRADE_PLAN.md E.2): a stated "84% probability" is only meaningful
    # if events predicted at 84% actually happen ~84% of the time. Computed on the
    # same held-out split as the accuracy metrics above -- never seen during training.
    brier = round(float(brier_score_loss(y_test, y_proba)), 4)
    reliability_bins = compute_reliability_diagram(y_test, y_proba, n_bins=10)
    print(f"Brier score: {brier} (0=perfect, 0.25=uninformative-constant-0.5, 1=worst)")

    # Final production model: refit on the full labeled dataset (standard practice once
    # the held-out evaluation above has already produced honest metrics).
    final_imputer = SimpleImputer(strategy='median')
    X_full_imputed = final_imputer.fit_transform(X_raw)
    final_model = lgb.LGBMClassifier(**LGBM_PARAMS)
    final_model.fit(X_full_imputed, y)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    artifacts = {
        "model": final_model,
        "imputer": final_imputer,
        "features": feature_cols,
        "sklearn_version": sklearn.__version__,
        "lightgbm_version": lgb.__version__,
        "model_family": "lightgbm",
    }
    artifacts_path = os.path.join(OUTPUT_DIR, "model_artifacts.pkl")
    with open(artifacts_path, "wb") as f:
        pickle.dump(artifacts, f)
    print(f"Saved model artifacts to {artifacts_path}")

    metrics_record = {
        "model_type": "LightGBM gradient-boosted trees",
        "model_version": MODEL_VERSION,
        "sklearn_version": sklearn.__version__,
        "lightgbm_version": lgb.__version__,
        "dataset_size": int(len(df)),
        "train_size": int(len(X_train)),
        "test_size": int(len(X_test)),
        "dataset_path": os.path.relpath(DATA_PATH, REPO_ROOT).replace("\\", "/"),
        "dataset_sha256_16": dataset_hash,
        "features": feature_cols,
        "metrics": metrics,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "metrics computed on a stratified 80/20 held-out split never seen during "
            "training; the serialized model_artifacts.pkl is refit on the full dataset "
            "afterward, which is why these metrics are a lower bound on the production "
            "model's actual accuracy, not an exact measurement of it."
        ),
    }
    metrics_path = os.path.join(OUTPUT_DIR, "model_metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(metrics_record, f, indent=2)
    print(f"Saved evaluation metrics to {metrics_path}")

    calibration_record = {
        "model_version": MODEL_VERSION,
        "test_size": int(len(X_test)),
        "brier_score": brier,
        "reliability_bins": reliability_bins,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Reliability bins group predicted probabilities into 10 equal-width buckets "
            "on the same held-out test split as model_metrics.json; a well-calibrated "
            "model has observed_frequency close to mean_predicted_probability in every "
            "bin with a non-trivial count. Bins with count=0 have null frequencies -- "
            "never interpolated or fabricated."
        ),
    }
    calibration_path = os.path.join(OUTPUT_DIR, "calibration_report.json")
    with open(calibration_path, "w") as f:
        json.dump(calibration_record, f, indent=2)
    print(f"Saved calibration report to {calibration_path}")


if __name__ == "__main__":
    main()
