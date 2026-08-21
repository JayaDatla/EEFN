import io
import os
import sys
import warnings

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.db.models import HostStar, ExoplanetCandidate, MLPrediction
from app.export import build_candidates_votable_bytes


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


def _seed_candidate(db):
    star = HostStar(hostname="TIC 1", ra=1.0, dec=1.0)
    db.add(star)
    db.commit()
    db.refresh(star)
    cand = ExoplanetCandidate(
        host_id=star.id, tic_id=1, toi_id=1001.01, pl_name="TOI-1001.01", disposition="PC",
        orbper=3.5, rade=2.1, rade_err_upper=0.1, rade_err_lower=-0.1,
        trandep=1000.0, trandurh=2.0, health_score=85.0, health_grade="B",
    )
    db.add(cand)
    db.commit()
    db.refresh(cand)
    db.add(MLPrediction(candidate_id=cand.id, evidence_consistency_score=0.7, followup_priority_score=0.6))
    db.commit()
    return cand


def test_votable_export_is_well_formed_and_round_trips(isolated_db):
    """UPGRADE_PLAN.md G.1: the VOTable export must actually be a valid VOTable a
    real client (TOPCAT, Aladin, astroquery) can parse -- verified here by round-
    tripping it through astropy's own VOTable reader, not just checking it's bytes."""
    _seed_candidate(isolated_db)

    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any astropy VOUnit/VOTable warning fails this test
        vot_bytes = build_candidates_votable_bytes(isolated_db)

        from astropy.io.votable import parse
        votable = parse(io.BytesIO(vot_bytes))
        table = votable.get_first_table().to_table()

    assert len(table) == 1
    assert table["pl_name"][0] == "TOI-1001.01"
    assert table["toi_id"][0] == pytest.approx(1001.01)
    assert table["health_grade"][0] == "B"
    assert str(table["orbper"].unit) == "d"


def test_votable_export_disposition_filter(isolated_db):
    cand = _seed_candidate(isolated_db)
    cand.disposition = "FP"
    isolated_db.commit()

    vot_bytes = build_candidates_votable_bytes(isolated_db, disposition="PC")
    from astropy.io.votable import parse
    table = parse(io.BytesIO(vot_bytes)).get_first_table().to_table()
    assert len(table) == 0

    vot_bytes = build_candidates_votable_bytes(isolated_db, disposition="FP")
    table = parse(io.BytesIO(vot_bytes)).get_first_table().to_table()
    assert len(table) == 1
