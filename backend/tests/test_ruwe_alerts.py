"""RUWE alerts are tiered (1.25 weak / 1.4 conventional) and must never read a quiet RUWE as 'no companion'."""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import AgreementMetrics, ExoplanetCandidate, HostStar
from app.db.session import Base
from services.alert_engine import AlertEngine


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _candidate(db, ruwe):
    host = HostStar(hostname="TIC 9", ra=1.0, dec=1.0, ruwe=ruwe)
    db.add(host)
    db.flush()
    cand = ExoplanetCandidate(host_id=host.id, pl_name="TOI-9.01", disposition="PC", rade=2.0)
    db.add(cand)
    db.flush()
    db.add(AgreementMetrics(candidate_id=cand.id, ruwe=ruwe, is_unphysical_rp=False, completeness_score=1.0,
                            catalog_agreement_score=1.0))
    db.commit()
    return cand


def _categories(db, cand):
    return {a["category"]: a["severity"] for a in AlertEngine(db).generate_alerts(cand.id)}


def test_ruwe_above_1p4_is_a_high_alert(db):
    assert _categories(db, _candidate(db, 1.8)).get("HIGH_RUWE_ANOMALY") == "HIGH"


def test_ruwe_between_1p25_and_1p4_is_only_a_low_elevated_alert(db):
    cats = _categories(db, _candidate(db, 1.3))
    assert cats.get("ELEVATED_RUWE") == "LOW" and "HIGH_RUWE_ANOMALY" not in cats


def test_quiet_ruwe_raises_no_alert_and_the_text_does_not_overclaim(db):
    assert not {"HIGH_RUWE_ANOMALY", "ELEVATED_RUWE"} & set(_categories(db, _candidate(db, 1.0)))
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "services", "alert_engine.py"), encoding="utf-8").read()
    assert 'NOT "no companion"' in src          # the limitation is documented where the rule lives
