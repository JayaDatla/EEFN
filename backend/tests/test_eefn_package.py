"""UPGRADE_PLAN.md D.4: `eefn` must be importable as a library
(`from eefn import audit_candidate`) and must not duplicate the candidate-report
assembly logic that GET /api/v1/candidates/{toi_id} already implements."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.db.models import HostStar, ExoplanetCandidate
from app.audit import build_candidate_profile


@pytest.fixture()
def isolated_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_build_candidate_profile_returns_none_for_unknown_toi(isolated_db):
    assert build_candidate_profile(isolated_db, 999999.01) is None


def test_build_candidate_profile_matches_stored_candidate(isolated_db):
    star = HostStar(hostname="TIC 42", ra=10.0, dec=-5.0, teff=5000.0)
    isolated_db.add(star)
    isolated_db.commit()
    isolated_db.refresh(star)

    cand = ExoplanetCandidate(
        host_id=star.id, tic_id=42, toi_id=7001.01, pl_name="TOI-7001.01", disposition="PC",
    )
    isolated_db.add(cand)
    isolated_db.commit()

    profile = build_candidate_profile(isolated_db, 7001.01)
    assert profile is not None
    assert profile["planet"]["pl_name"] == "TOI-7001.01"
    assert profile["planet"]["disposition"] == "PC"
    assert profile["star"]["hostname"] == "TIC 42"


def test_eefn_audit_candidate_raises_clear_error_for_unknown_toi(monkeypatch, isolated_db):
    """eefn.audit_candidate opens its own session via SessionLocal -- point that at
    the isolated in-memory DB for this test rather than the real dev DB."""
    import eefn
    from app.db import session as db_session

    monkeypatch.setattr(db_session, "SessionLocal", lambda: isolated_db)
    monkeypatch.setattr(eefn, "SessionLocal", lambda: isolated_db)

    with pytest.raises(ValueError, match="No candidate with TOI ID"):
        eefn.audit_candidate(toi=424242.01)
