"""
Reproduce the tabular model's published held-out metrics and FAIL if they do not match.

Earlier versions of this script printed a fixed "PASS" report with hardcoded numbers regardless
of what the code produced, which is the opposite of reproducibility. This one recomputes:

  1. the SHA-256 prefix of validation/data/validation_dataset.csv  vs  model_metrics.json,
  2. the held-out accuracy / ROC-AUC / F1 / Brier of the shipped configuration (same split,
     same seed, same LightGBM parameters)  vs  model_metrics.json and calibration_report.json,
  3. the library versions recorded in model_metrics.json  vs  the installed ones (warning only:
     a different version can legitimately change a metric in the 4th decimal),

and exits non-zero on any mismatch beyond TOLERANCE. It writes nothing.

    python reproduce_results.py

What it does NOT do: re-download any catalog or re-run the light-curve vetter (those need hours of
MAST access; see backend/validation/scripts/). The dataset CSV is the frozen input.
"""
import hashlib
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "validation", "scripts"))

import lightgbm as lgb
import pandas as pd
import sklearn
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, brier_score_loss, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split

from train_and_serialize_model import DATA_PATH, LGBM_PARAMS, build_features

TOLERANCE = 0.002
ML_DIR = os.path.join(ROOT, "backend", "app", "ml")


def main() -> int:
    with open(os.path.join(ML_DIR, "model_metrics.json")) as f:
        published = json.load(f)
    with open(os.path.join(ML_DIR, "calibration_report.json")) as f:
        calib = json.load(f)

    failures = []

    with open(DATA_PATH, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()[:16]
    if digest != published["dataset_sha256_16"]:
        failures.append(f"dataset hash {digest} != published {published['dataset_sha256_16']} "
                        "(the CSV changed since the model was trained; retrain and republish)")

    for lib, key in ((sklearn, "sklearn_version"), (lgb, "lightgbm_version")):
        if published.get(key) and published[key] != lib.__version__:
            print(f"WARNING: {key} published {published[key]}, installed {lib.__version__} "
                  "(metrics may move in the 4th decimal)")

    df = pd.read_csv(DATA_PATH)
    df = df[df["tfopwg_disp"].isin(["CP", "KP", "FP", "FA"])].copy()
    df["label"] = df["tfopwg_disp"].map({"CP": 1, "KP": 1, "FP": 0, "FA": 0})
    df, feature_cols = build_features(df)
    y = df["label"].values
    X_tr, X_te, y_tr, y_te = train_test_split(df[feature_cols], y, test_size=0.2, random_state=42, stratify=y)

    imputer = SimpleImputer(strategy="median")
    model = lgb.LGBMClassifier(**LGBM_PARAMS).fit(imputer.fit_transform(X_tr), y_tr)
    proba = model.predict_proba(imputer.transform(X_te))[:, 1]
    got = {
        "accuracy": accuracy_score(y_te, proba >= 0.5), "roc_auc": roc_auc_score(y_te, proba),
        "f1_score": f1_score(y_te, proba >= 0.5), "brier": brier_score_loss(y_te, proba),
    }
    want = {**published["metrics"], "brier": calib["brier_score"]}

    print(f"{'metric':10s} {'recomputed':>11s} {'published':>10s}")
    for k in ("accuracy", "roc_auc", "f1_score", "brier"):
        ok = abs(got[k] - want[k]) <= TOLERANCE
        print(f"{k:10s} {got[k]:11.4f} {want[k]:10.4f}  {'ok' if ok else 'MISMATCH'}")
        if not ok:
            failures.append(f"{k}: recomputed {got[k]:.4f} vs published {want[k]:.4f}")

    if failures:
        print("\nREPRODUCTION FAILED:")
        for line in failures:
            print("  -", line)
        return 1
    print(f"\nReproduced within +/-{TOLERANCE} (dataset {digest}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
