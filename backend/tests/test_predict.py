import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
    assert row["teff_diff"] == 0.0  # Teff falls back to st_teff per _extract_raw_inputs -> no discrepancy
    assert row["RUWE"] is None
    assert row["st_tmag"] is None
