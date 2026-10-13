"""Train/serve parity for the tabular evidence-consistency model.

The feature set is implemented twice: pandas in validation/scripts/train_and_serialize_model.py
(training) and scalar Python in app/ml/predict.py (serving). A drift between them is silent --
the model just gets different inputs -- and one already shipped: serving fed Gaia values into
both the "TOI" and "Gaia" slots, so every catalog-disagreement feature was 0 in production while
training saw real differences (AUC 0.927 -> 0.900 when recomputed serving-style).

These tests feed the SAME real rows through both paths and require identical features, and check
the DB-record -> inputs mapping that production actually uses.
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(BACKEND)
sys.path.append(BACKEND)
sys.path.append(os.path.join(REPO, "validation", "scripts"))

from app.db.models import ExoplanetCandidate, HostStar
from app.ml.predict import PredictionEngine, predictor

DATA = os.path.join(REPO, "validation", "data", "validation_dataset.csv")

pytestmark = pytest.mark.skipif(not (os.path.exists(DATA) and predictor.loaded), reason="dataset or model artifact missing")

RAW_COLUMNS = [
    "st_teff", "Teff", "st_rad", "Rad", "st_dist", "Dist", "st_logg", "pl_orbper", "pl_trandurh",
    "pl_trandep", "pl_rade", "pl_insol", "pl_eqt", "RUWE", "Plx", "Jmag", "Hmag", "Kmag", "PS_gmag", "PS_rmag",
]


def _none_if_nan(v):
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else float(v)


def test_serving_features_equal_training_features_on_real_rows():
    from train_and_serialize_model import build_features

    df = pd.read_csv(DATA)
    df = df[df["tfopwg_disp"].isin(["CP", "KP", "FP", "FA"])].sample(400, random_state=0)
    train_df, feature_cols = build_features(df)
    assert list(predictor.feature_names) == list(feature_cols), "artifact and training feature lists differ"

    engine = PredictionEngine.__new__(PredictionEngine)   # build_feature_row needs no model files
    mismatches = []
    for idx, row in df.iterrows():
        served = engine.build_feature_row({c: _none_if_nan(row[c]) for c in RAW_COLUMNS})
        for col in feature_cols:
            t = train_df.loc[idx, col]
            v = served[col]
            v = np.nan if v is None else float(v)
            if not np.isclose(float(t), v, rtol=1e-6, atol=1e-9, equal_nan=True):
                mismatches.append((int(row["tid"]), col, float(t), v))
    assert not mismatches, f"{len(mismatches)} train/serve feature mismatches, e.g. {mismatches[:5]}"


def _host(**kw):
    base = dict(hostname="TIC 1", ra=1.0, dec=1.0)
    base.update(kw)
    return HostStar(**base)


def _cand():
    return ExoplanetCandidate(pl_name="TOI-1.01", disposition="PC", orbper=3.0, trandep=1000.0, trandurh=2.0, rade=2.0)


def test_db_inputs_keep_toi_and_gaia_values_in_separate_slots():
    host = _host(toi_teff=5700.0, teff=5400.0, toi_rad=1.0, rad=1.2, toi_dist=100.0, distance=110.0, toi_logg=4.4)
    data = PredictionEngine.inputs_from_records(_cand(), host)
    assert (data["st_teff"], data["Teff"]) == (5700.0, 5400.0)
    assert (data["st_rad"], data["Rad"]) == (1.0, 1.2)
    assert (data["st_dist"], data["Dist"]) == (100.0, 110.0)
    assert data["st_logg"] == 4.4          # the TOI table's logg, as in training -- not Gaia's

    engine = PredictionEngine.__new__(PredictionEngine)
    row = engine.build_feature_row(data)
    assert row["teff_diff"] == pytest.approx(300.0) and row["rad_diff"] == pytest.approx(0.2)
    assert row["dist_diff"] == pytest.approx(10.0)


def test_missing_gaia_values_give_missing_disagreement_not_zero():
    host = _host(toi_teff=5700.0, toi_rad=1.0, toi_dist=100.0)       # Gaia astro-params never matched
    row = PredictionEngine.__new__(PredictionEngine).build_feature_row(PredictionEngine.inputs_from_records(_cand(), host))
    assert row["teff_diff"] is None and row["rad_diff"] is None and row["dist_diff"] is None
    assert row["derived_rp_gaia"] is None and row["is_unphysical_rp_gaia"] == 0
    assert "completeness" not in row         # no label-informative count of populated fields


def test_not_yet_backfilled_host_is_all_missing_rather_than_fabricated():
    host = _host(teff=5400.0, rad=1.2, distance=110.0)               # Gaia only: TOI-side never stored
    row = PredictionEngine.__new__(PredictionEngine).build_feature_row(PredictionEngine.inputs_from_records(_cand(), host))
    assert row["teff_diff"] is None and row["st_teff"] is None


def test_spectroscopy_never_replaces_the_gaia_inputs():
    host = _host(toi_teff=5700.0, teff=5400.0, teff_spec=6500.0, rad_spec=3.0, spectroscopy_is_real=True)
    data = PredictionEngine.inputs_from_records(_cand(), host)
    assert data["Teff"] == 5400.0 and "teff_spec" not in data


def test_stored_prediction_records_the_model_version():
    assert predictor.model_version, "predictions must be attributable to the artifact that produced them"
