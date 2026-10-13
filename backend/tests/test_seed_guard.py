"""seed_db.py used to drop_all() on whatever database the engine pointed at, unconditionally, then
fill it with random data. It must now refuse to touch a database that holds real ingested rows."""
import os
import sys
import uuid
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import seed_db
from app.db.models import CatalogSource, ExoplanetCandidate, HostStar, MeasurementHistory
from app.db.session import Base


@pytest.fixture()
def patched_session(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(seed_db, "SessionLocal", factory)
    return factory


def test_refuses_when_provenance_history_exists(patched_session):
    db = patched_session()
    host = HostStar(hostname="TIC 1", ra=1.0, dec=1.0)
    db.add(host)
    db.flush()
    cand = ExoplanetCandidate(host_id=host.id, pl_name="TOI-1.01", disposition="PC")
    src = CatalogSource(name="NASA Exoplanet Archive", version="x", last_sync=datetime.utcnow())
    db.add_all([cand, src])
    db.flush()
    db.add(MeasurementHistory(candidate_id=cand.id, source_id=src.id, parameter_name="stellar_radius", value=1.0,
                              measured_at=datetime.utcnow()))
    db.commit()
    with pytest.raises(SystemExit, match="Refusing to erase"):
        seed_db._refuse_if_real_data_present()


def test_refuses_when_toi_side_host_values_exist(patched_session):
    db = patched_session()
    db.add(HostStar(hostname="TIC 2", ra=1.0, dec=1.0, toi_teff=5700.0))
    db.commit()
    with pytest.raises(SystemExit, match="Refusing to erase"):
        seed_db._refuse_if_real_data_present()


def test_allows_an_empty_or_fabricated_only_database(patched_session):
    db = patched_session()
    db.add(HostStar(hostname="TIC 3", ra=1.0, dec=1.0))      # seed-style: no provenance, no TOI-side values
    db.commit()
    seed_db._refuse_if_real_data_present()                    # must not raise
