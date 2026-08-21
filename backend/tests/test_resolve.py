import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.db.models import HostStar, ExoplanetCandidate
from app.resolve import resolve_identifier


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


@pytest.fixture()
def seeded_db(isolated_db):
    star = HostStar(hostname="TIC 231663901", ra=1.0, dec=1.0, gaia_dr3_source_id=4622062372804801408)
    isolated_db.add(star)
    isolated_db.commit()
    isolated_db.refresh(star)
    cand = ExoplanetCandidate(
        host_id=star.id, tic_id=231663901, toi_id=101.01, pl_name="TOI-101.01", disposition="KP",
    )
    isolated_db.add(cand)
    isolated_db.commit()
    return isolated_db


@pytest.mark.parametrize("query", [
    "TOI-101.01", "toi-101.01", "TOI 101.01", "101.01",
])
def test_resolve_by_toi_variants(seeded_db, query):
    results = resolve_identifier(seeded_db, query)
    assert len(results) == 1
    assert results[0]["pl_name"] == "TOI-101.01"
    assert results[0]["tic_id"] == 231663901
    assert results[0]["gaia_dr3_source_id"] == 4622062372804801408


@pytest.mark.parametrize("query", [
    "TIC 231663901", "tic231663901", "231663901",
])
def test_resolve_by_tic_variants(seeded_db, query):
    results = resolve_identifier(seeded_db, query)
    assert len(results) == 1
    assert results[0]["toi_id"] == pytest.approx(101.01)


@pytest.mark.parametrize("query", [
    "Gaia DR3 4622062372804801408", "gaia 4622062372804801408",
])
def test_resolve_by_gaia_source_id_with_explicit_prefix(seeded_db, query):
    results = resolve_identifier(seeded_db, query)
    assert len(results) == 1
    assert results[0]["toi_id"] == pytest.approx(101.01)


def test_resolve_unknown_identifier_returns_empty(seeded_db):
    assert resolve_identifier(seeded_db, "TOI-999999.01") == []
    assert resolve_identifier(seeded_db, "TIC 1") == []


def test_toi_prefix_never_matches_a_tic_id_with_the_same_digits():
    """A candidate query must not silently cross-resolve TOI and TIC just because
    they happen to share numeric digits -- UPGRADE_PLAN.md G.2's whole point is
    unambiguous resolution, not a guess."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    star = HostStar(hostname="TIC 101", ra=1.0, dec=1.0)
    db.add(star)
    db.commit()
    db.refresh(star)
    # A different candidate whose TIC ID happens to equal another's TOI-like digits.
    cand = ExoplanetCandidate(host_id=star.id, tic_id=101, toi_id=999.01, pl_name="TOI-999.01", disposition="PC")
    db.add(cand)
    db.commit()

    assert resolve_identifier(db, "TOI-101") == []  # no TOI 101 exists
    assert len(resolve_identifier(db, "TIC 101")) == 1  # but TIC 101 does
