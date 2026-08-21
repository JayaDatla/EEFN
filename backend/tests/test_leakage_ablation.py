"""UPGRADE_PLAN.md E.1: sanity-check the leakage-ablation scripts' core logic without
a live network call in the regular test suite (both scripts are still runnable
standalone against the real validation dataset / NASA Exoplanet Archive)."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                              "validation", "scripts"))

import leakage_ablation  # noqa: E402
import leakage_rv_confirmed_holdout as rv_holdout  # noqa: E402
from train_and_serialize_model import build_features  # noqa: E402


def _synthetic_labeled_df(n=200, seed=0):
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "toi": np.arange(n),
        "tid": np.arange(1000, 1000 + n),
        "tfopwg_disp": rng.choice(["CP", "KP", "FP", "FA"], size=n, p=[0.3, 0.2, 0.4, 0.1]),
        "ra": rng.uniform(0, 360, n),
        "dec": rng.uniform(-90, 90, n),
        "st_tmag": rng.uniform(8, 14, n),
        "st_teff": rng.uniform(4000, 7000, n),
        "st_rad": rng.uniform(0.5, 2.0, n),
        "st_logg": rng.uniform(3.5, 5.0, n),
        "st_dist": rng.uniform(10, 500, n),
        "pl_orbper": rng.uniform(0.5, 30, n),
        "pl_trandurh": rng.uniform(0.5, 6, n),
        "pl_trandep": rng.uniform(100, 20000, n),
        "pl_rade": rng.uniform(0.5, 20, n),
        "pl_insol": rng.uniform(1, 2000, n),
        "pl_eqt": rng.uniform(200, 2000, n),
        "Teff": rng.uniform(4000, 7000, n),
        "Rad": rng.uniform(0.5, 2.0, n),
        "Dist": rng.uniform(10, 500, n),
        "Gmag": rng.uniform(8, 14, n),
        "RUWE": rng.uniform(0.8, 2.0, n),
    })
    return df


def test_evaluate_subset_returns_real_metrics_for_a_large_enough_sample():
    df = _synthetic_labeled_df(n=200)
    df["label"] = df["tfopwg_disp"].map({"CP": 1, "KP": 1, "FP": 0, "FA": 0})
    df, feature_cols = build_features(df)

    result = leakage_ablation.evaluate_subset(df, feature_cols, "synthetic_test")
    assert result["subset"] == "synthetic_test"
    assert result.get("skipped") is not True
    assert 0.0 <= result["accuracy"] <= 1.0
    assert 0.0 <= result["roc_auc"] <= 1.0
    assert 0.0 <= result["brier_score"] <= 1.0


def test_evaluate_subset_skips_too_small_a_sample():
    df = _synthetic_labeled_df(n=10)
    df["label"] = df["tfopwg_disp"].map({"CP": 1, "KP": 1, "FP": 0, "FA": 0})
    df, feature_cols = build_features(df)

    result = leakage_ablation.evaluate_subset(df, feature_cols, "tiny")
    assert result["skipped"] is True


def test_fetch_rv_confirmed_tic_ids_parses_nasa_tap_csv_response(requests_mock):
    """UPGRADE_PLAN.md E.1: the RV-confirmed holdout depends on correctly stripping the
    'TIC ' prefix NASA's archive returns -- verify that parsing, not the live network call."""
    csv_body = "tic_id\nTIC 230061010\nTIC 333225860\n"
    requests_mock.get(rv_holdout.NASA_TAP_URL, text=csv_body)

    tic_ids = rv_holdout.fetch_rv_confirmed_tic_ids()
    assert tic_ids == {230061010, 333225860}
