"""
UPGRADE_PLAN.md E.1: builds a clean-label holdout using only radial-velocity
mass-confirmed planets -- these are real planets confirmed by a method entirely
independent of TESS/TFOP/Gaia-informed vetting, so correctly classifying them is not
explainable by the model having learned to reproduce human categorization behavior
(LIMITATIONS.md Section 1.1).

Requires a live query against the NASA Exoplanet Archive TAP service (`ps` table) to
identify which TIC IDs host an RV-discovered confirmed planet, then cross-references
against validation_dataset.csv by `tid`.
"""
import io
import json
import os
import sys
from datetime import datetime, timezone

import pandas as pd
import requests
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from train_and_serialize_model import build_features, DATA_PATH, REPO_ROOT  # noqa: E402

NASA_TAP_URL = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"
OUTPUT_PATH = os.path.join(REPO_ROOT, "backend", "app", "ml", "leakage_rv_confirmed_report.json")


def fetch_rv_confirmed_tic_ids() -> set:
    # Lower-case and without "IS NOT NULL": the archive's web-application firewall started
    # answering HTTP 403 to the upper-case `... AND tic_id IS NOT NULL` form of this query
    # (the same query without that clause returns 200), so nulls are dropped client-side.
    query = "select distinct tic_id from ps where discoverymethod='Radial Velocity'"
    r = requests.get(NASA_TAP_URL, params={"query": query, "format": "csv"}, timeout=60)
    r.raise_for_status()
    tics = pd.read_csv(io.StringIO(r.text)).dropna(subset=["tic_id"])
    return set(tics["tic_id"].str.replace("TIC ", "", regex=False).astype(int))


def main():
    rv_tic_ids = fetch_rv_confirmed_tic_ids()
    print(f"Fetched {len(rv_tic_ids)} unique TIC IDs with an RV-discovered confirmed planet from NASA Exoplanet Archive.")

    df = pd.read_csv(DATA_PATH)
    df = df[df["tfopwg_disp"].isin(["CP", "KP", "FP", "FA"])].copy()
    df["label"] = df["tfopwg_disp"].map({"CP": 1, "KP": 1, "FP": 0, "FA": 0})
    df, feature_cols = build_features(df)

    is_rv_confirmed = df["tid"].isin(rv_tic_ids)
    holdout = df[is_rv_confirmed]
    train_pool = df[~is_rv_confirmed]

    if len(holdout) < 10:
        report = {
            "status": "insufficient_overlap",
            "detail": f"Only {len(holdout)} of our TOI candidates matched an RV-confirmed TIC ID -- "
                      "too few for a meaningful holdout evaluation.",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(OUTPUT_PATH, "w") as f:
            json.dump(report, f, indent=2)
        print(json.dumps(report, indent=2))
        return

    assert (holdout["label"] == 1).all(), "RV-confirmed matches should all carry a positive (CP/KP) disposition"

    # Model A: trained WITHOUT ever seeing the RV-confirmed rows -- a true held-out test.
    X_train = train_pool[feature_cols]
    y_train = train_pool["label"].values
    imputer_holdout = SimpleImputer(strategy="median")
    X_train_i = imputer_holdout.fit_transform(X_train)
    model_holdout = RandomForestClassifier(n_estimators=100, random_state=42)
    model_holdout.fit(X_train_i, y_train)

    X_holdout_i = imputer_holdout.transform(holdout[feature_cols])
    proba_holdout = model_holdout.predict_proba(X_holdout_i)[:, 1]
    recall_holdout = float((proba_holdout >= 0.5).mean())

    # Model B: trained on the FULL dataset (matches the production model_artifacts.pkl
    # methodology) -- for comparison, since these rows WERE in its training data.
    X_full = df[feature_cols]
    y_full = df["label"].values
    imputer_full = SimpleImputer(strategy="median")
    X_full_i = imputer_full.fit_transform(X_full)
    model_full = RandomForestClassifier(n_estimators=100, random_state=42)
    model_full.fit(X_full_i, y_full)
    proba_full_on_holdout = model_full.predict_proba(imputer_full.transform(holdout[feature_cols]))[:, 1]
    recall_full = float((proba_full_on_holdout >= 0.5).mean())

    report = {
        "methodology": (
            "`holdout` = TOI candidates whose TIC ID hosts a radial-velocity-discovered "
            "confirmed planet per the NASA Exoplanet Archive `ps` table -- ground truth "
            "entirely independent of TESS/TFOP/Gaia-informed disposition. "
            "`model_never_saw_holdout` is trained with these rows excluded entirely "
            "(a true generalization test); `model_trained_on_full_dataset` matches the "
            "production model_artifacts.pkl methodology and includes these rows in "
            "training, shown for comparison -- a large gap between the two would "
            "suggest the production model's apparent skill on similar targets is driven "
            "by memorization rather than genuine signal."
        ),
        "n_rv_confirmed_tic_ids_in_archive": len(rv_tic_ids),
        "n_holdout_candidates": int(len(holdout)),
        "holdout_all_positive_label": True,
        "model_never_saw_holdout": {
            "recall_on_rv_confirmed_planets": round(recall_holdout, 4),
            "mean_predicted_probability": round(float(proba_holdout.mean()), 4),
            "n_train": int(len(train_pool)),
        },
        "model_trained_on_full_dataset": {
            "recall_on_rv_confirmed_planets": round(recall_full, 4),
            "mean_predicted_probability": round(float(proba_full_on_holdout.mean()), 4),
        },
        "caveat": (
            "This checks recall on independently-confirmed real planets only -- it "
            "cannot by itself measure false-positive rate on this clean-label set, "
            "since RV-mass confirmation doesn't produce independently-verified negative "
            "examples the same way. See LIMITATIONS.md Section 1.1."
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
