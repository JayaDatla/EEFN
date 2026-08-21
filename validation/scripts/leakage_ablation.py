"""
UPGRADE_PLAN.md E.1: measures how much of the RF model's held-out performance depends
on Gaia DR3-informed disposition labels (see LIMITATIONS.md Section 1.1 -- labels come
from human astronomers who used Gaia RUWE/distance to classify candidates, so a model
trained on them partly learns to reproduce human categorization, not to independently
confirm planets).

Compares held-out performance on the full dataset against a subset of TOIs whose
`toi_created` timestamp predates the Gaia EDR3 release (2020-12-03) -- these targets'
initial catalog entry could not have been informed by Gaia (E)DR3 astrometry/RUWE.
"""
import json
import os
import sys
from datetime import datetime, timezone

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, roc_auc_score, f1_score, brier_score_loss

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from train_and_serialize_model import build_features, DATA_PATH, REPO_ROOT  # noqa: E402

GAIA_EDR3_RELEASE = pd.Timestamp("2020-12-03")
OUTPUT_PATH = os.path.join(REPO_ROOT, "backend", "app", "ml", "leakage_ablation_report.json")


def evaluate_subset(df: pd.DataFrame, feature_cols: list, label: str, seed: int = 42) -> dict:
    X = df[feature_cols]
    y = df["label"].values
    if len(df) < 40 or y.sum() == 0 or y.sum() == len(y):
        return {"subset": label, "n": int(len(df)), "skipped": True,
                "reason": "too small or single-class to split meaningfully"}

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=seed, stratify=y
    )
    imputer = SimpleImputer(strategy="median")
    X_train_i = imputer.fit_transform(X_train)
    X_test_i = imputer.transform(X_test)

    model = RandomForestClassifier(n_estimators=100, random_state=seed)
    model.fit(X_train_i, y_train)
    y_pred = model.predict(X_test_i)
    y_proba = model.predict_proba(X_test_i)[:, 1]

    return {
        "subset": label,
        "n": int(len(df)),
        "test_size": int(len(y_test)),
        "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "roc_auc": round(float(roc_auc_score(y_test, y_proba)), 4),
        "f1_score": round(float(f1_score(y_test, y_pred)), 4),
        "brier_score": round(float(brier_score_loss(y_test, y_proba)), 4),
    }


def main():
    df = pd.read_csv(DATA_PATH)
    df = df[df["tfopwg_disp"].isin(["CP", "KP", "FP", "FA"])].copy()
    df["label"] = df["tfopwg_disp"].map({"CP": 1, "KP": 1, "FP": 0, "FA": 0})
    df, feature_cols = build_features(df)
    df["toi_created_dt"] = pd.to_datetime(df["toi_created"])

    full_result = evaluate_subset(df, feature_cols, "full_dataset")

    pre_edr3 = df[df["toi_created_dt"] < GAIA_EDR3_RELEASE]
    pre_edr3_result = evaluate_subset(pre_edr3, feature_cols, "pre_gaia_edr3_toi_created")

    post_edr3 = df[df["toi_created_dt"] >= GAIA_EDR3_RELEASE]
    post_edr3_result = evaluate_subset(post_edr3, feature_cols, "post_gaia_edr3_toi_created")

    report = {
        "methodology": (
            "Compares RF held-out performance on the full labeled dataset against a "
            "subset of TOIs whose `toi_created` timestamp predates the Gaia EDR3 "
            "release (2020-12-03) -- these targets' initial TOI catalog entry could not "
            "have been informed by Gaia (E)DR3 astrometry/RUWE. Each subset is "
            "independently split 80/20 (same methodology, seed, and RF hyperparameters "
            "as train_and_serialize_model.py) and evaluated on its own held-out test "
            "fold, not a shared test set reused across subsets."
        ),
        "caveat": (
            "`tfopwg_disp` in this dataset snapshot reflects the CURRENT disposition "
            "value, not the disposition at the time of TOI creation -- a target created "
            "before Gaia EDR3 may have had its disposition revised afterward using Gaia "
            "data. This ablation measures a real but imperfect proxy for the leakage "
            "question, not a guarantee that pre-EDR3-created targets were never touched "
            "by Gaia-informed vetting. A clean-label holdout using only RV-mass-confirmed "
            "planets (attempted separately -- see leakage_rv_confirmed_report.json if "
            "present) is the stronger test the plan also asks for. See LIMITATIONS.md "
            "Section 1.1."
        ),
        "gaia_edr3_release_date": "2020-12-03",
        "results": [full_result, pre_edr3_result, post_edr3_result],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
