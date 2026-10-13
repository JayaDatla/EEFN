import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.db.models import HostStar, ExoplanetCandidate
from app.ml.predict import predictor, PredictionEngine


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def _make_candidate(db_session, disposition: str) -> ExoplanetCandidate:
    """Two candidates with byte-identical stellar/transit parameters, differing only in
    `disposition` -- the exact scenario UPGRADE_PLAN.md C.1 calls out as the regression
    to guard against."""
    star = HostStar(
        hostname=f"TEST-STAR-{disposition}",
        ra=120.0, dec=-10.0,
        distance=150.0, teff=5600.0, logg=4.4, rad=1.05,
        ruwe=1.05, g_mag=10.4,
    )
    db_session.add(star)
    db_session.flush()

    cand = ExoplanetCandidate(
        host_id=star.id,
        tic_id=123456,
        toi_id=1000.01 if disposition == "FP" else 1000.02,
        pl_name=f"TEST-{disposition}.01",
        disposition=disposition,
        orbper=4.2, rade=2.1, trandep=1500.0, trandurh=2.3,
        insol=250.0, eqt=900.0,
    )
    db_session.add(cand)
    db_session.commit()
    db_session.refresh(cand)
    return cand


def test_model_artifacts_loaded():
    assert predictor.loaded, "model_artifacts.pkl must load for this regression test to be meaningful"


def test_prediction_is_invariant_to_disposition_label(db_session):
    """The Random Forest's output must depend only on the feature vector, never on the
    label (`disposition`) stored on the same row -- see UPGRADE_PLAN.md A.1/C.1."""
    fp_candidate = _make_candidate(db_session, "FP")
    cp_candidate = _make_candidate(db_session, "CP")

    result_fp = predictor.predict_confirmation(fp_candidate.id, db_session)
    result_cp = predictor.predict_confirmation(cp_candidate.id, db_session)

    assert result_fp["status"] == "success"
    assert result_cp["status"] == "success"
    assert result_fp["evidence_consistency_score"] == pytest.approx(result_cp["evidence_consistency_score"])
    assert result_fp["feature_contributions"] == result_cp["feature_contributions"]


def test_prediction_changes_when_features_actually_differ(db_session):
    """Sanity check on the invariance test above: the model must still be sensitive to
    real feature changes, otherwise test_prediction_is_invariant_to_disposition_label
    would pass trivially because the model is dead, not because it's honest."""
    baseline = _make_candidate(db_session, "PC")

    star2 = HostStar(
        hostname="TEST-STAR-EXTREME", ra=120.0, dec=-10.0,
        distance=150.0, teff=5600.0, logg=4.4, rad=8.0,  # giant star -> huge derived Rp
        ruwe=3.5, g_mag=10.4,
    )
    db_session.add(star2)
    db_session.flush()
    extreme = ExoplanetCandidate(
        host_id=star2.id, tic_id=654321, toi_id=1000.03, pl_name="TEST-EXTREME.01",
        disposition="PC", orbper=4.2, rade=2.1, trandep=1500.0, trandurh=2.3,
        insol=250.0, eqt=900.0,
    )
    db_session.add(extreme)
    db_session.commit()
    db_session.refresh(extreme)

    result_baseline = predictor.predict_confirmation(baseline.id, db_session)
    result_extreme = predictor.predict_confirmation(extreme.id, db_session)

    assert result_baseline["evidence_consistency_score"] != pytest.approx(
        result_extreme["evidence_consistency_score"]
    )


def test_build_feature_row_leaves_missing_inputs_as_none():
    engine = PredictionEngine.__new__(PredictionEngine)  # skip __init__'s file I/O
    row = engine.build_feature_row({"st_teff": 5500.0})
    assert row["st_teff"] == 5500.0
    assert row["teff_diff"] is None  # no Gaia Teff -> no disagreement can be computed (never a fake 0)
    assert row["RUWE"] is None
    assert row["j_k"] is None and row["abs_K"] is None and row["ps_g_r"] is None


def test_photometry_features_computed_from_host_catalog_values():
    engine = PredictionEngine.__new__(PredictionEngine)
    row = engine.build_feature_row({"st_teff": 5500.0, "Jmag": 10.5, "Hmag": 10.2, "Kmag": 10.1,
                                    "Plx": 10.0, "PS_gmag": 12.0, "PS_rmag": 11.5})
    assert row["j_k"] == 10.5 - 10.1 and row["h_k"] == 10.2 - 10.1
    assert row["ps_g_r"] == 0.5
    # M_K = K + 5*log10(plx_mas) - 10 -> a 10 mas (100 pc) star is K - 5.
    assert abs(row["abs_K"] - 5.1) < 1e-9


def test_feature_contributions_sum_to_probability_shift():
    from app.ml.predict import predictor
    if not predictor.loaded:
        pytest.skip("model artifacts unavailable")
    raw = {"st_teff": 5600.0, "st_rad": 1.0, "st_dist": 120.0, "pl_orbper": 4.0, "pl_trandurh": 2.5,
           "pl_trandep": 1500.0, "pl_rade": 2.0, "RUWE": 1.05, "Plx": 8.0, "Jmag": 10.0, "Kmag": 9.6}
    res = predictor.predict_confirmation(raw)
    X = pd.DataFrame([predictor.build_feature_row(raw)])[predictor.feature_names]
    contrib, bias = predictor._contributions(predictor.imputer.transform(X))
    assert abs((bias + contrib.sum()) - res["evidence_consistency_score"]) < 1e-6
