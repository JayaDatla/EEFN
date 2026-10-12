"""Scheduled centroid/spectroscopy sync: bookkeeping and honesty, with the network
calls injected so no MAST/VizieR access is needed."""
import os
import sys
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.db.models import ExoplanetCandidate, HostStar
from app.pipeline.mast_centroid import CentroidResult
from app.pipeline.real_sync import sync_real_centroids, sync_real_lightcurve_vetting, sync_real_spectroscopy
from app.pipeline.spectroscopy import SpectroscopyResult


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    yield session
    session.close()


def _cand(db, toi, tranmid=2458500.0):
    host = HostStar(hostname=f"TIC {toi}", ra=10.0 + toi, dec=5.0)
    db.add(host)
    db.flush()
    c = ExoplanetCandidate(host_id=host.id, tic_id=1000 + toi, toi_id=float(toi) + 0.01,
                           pl_name=f"TOI-{toi}.01", disposition="PC", orbper=3.0, trandurh=2.0,
                           tranmid=tranmid)
    db.add(c)
    db.commit()
    return c


def _result(sigma=1.0, implied=0.5, err=0.2):
    return CentroidResult(offset_arcsec=0.02, significance_sigma=sigma, sector=5, n_in_transit=40,
                          n_out_of_transit=200, dx_binned=[0.0] * 201, dy_binned=[0.0] * 201, n_events=6,
                          implied_offset_arcsec=implied, implied_offset_err_arcsec=err)


def test_measured_candidate_is_flagged_real_and_not_retried(db):
    c = _cand(db, 1)
    calls = []
    measure = lambda **kw: calls.append(kw) or _result(sigma=4.2, implied=7.0, err=1.0)
    out = sync_real_centroids(db, limit=5, measure=measure)
    db.refresh(c)
    assert out["measured"] == 1
    assert c.centroid_is_real and c.centroid_status == "measured" and c.has_centroid_dip
    assert c.centroid_implied_offset_arcsec == 7.0
    assert calls[0]["epoch_bjd"] == 2458500.0          # stored tranmid used, no TAP lookup
    assert sync_real_centroids(db, limit=5, measure=measure)["attempted"] == 0


def test_failed_candidate_is_not_marked_real_and_is_backed_off(db):
    c = _cand(db, 2)
    out = sync_real_centroids(db, limit=5, measure=lambda **kw: None)
    db.refresh(c)
    assert out["measured"] == 0
    assert c.centroid_is_real is False and c.centroid_status == "no_measurement"
    assert c.centroid_attempted_at is not None
    assert sync_real_centroids(db, limit=5, measure=lambda **kw: None)["attempted"] == 0   # backed off
    c.centroid_attempted_at = datetime.utcnow() - timedelta(days=120)
    db.commit()
    assert sync_real_centroids(db, limit=5, measure=lambda **kw: None)["attempted"] == 1   # eligible again


def test_missing_epoch_falls_back_to_lookup_then_gives_up(db):
    c = _cand(db, 3, tranmid=None)
    out = sync_real_centroids(db, limit=5, measure=lambda **kw: _result(), epoch_lookup=lambda tic, toi_id=None: None)
    db.refresh(c)
    assert out["attempted"] == 1 and c.centroid_status == "no_epoch" and not c.centroid_is_real


def test_batch_limit_respected_and_never_attempted_first(db):
    for i in range(1, 6):
        _cand(db, i)
    assert sync_real_centroids(db, limit=2, measure=lambda **kw: None)["attempted"] == 2
    assert sync_real_centroids(db, limit=10, measure=lambda **kw: None)["attempted"] == 3


def test_spectroscopy_only_real_on_match(db):
    a, b = _cand(db, 10), _cand(db, 11)
    lookup = lambda ra, dec: SpectroscopyResult(5600.0, -0.1, 4.4) if ra == 20.0 else None
    out = sync_real_spectroscopy(db, limit=10, lookup=lookup)
    ha, hb = db.get(HostStar, a.host_id), db.get(HostStar, b.host_id)
    assert out["attempted"] == 2 and out["matched"] == 1
    assert ha.spectroscopy_is_real is True and ha.teff_spec == 5600.0
    assert hb.spectroscopy_is_real is False and hb.spectroscopy_attempted_at is not None


def test_significant_but_tiny_shift_is_measured_yet_not_flagged(db):
    c = _cand(db, 20)
    sync_real_centroids(db, limit=5, measure=lambda **kw: _result(sigma=6.0, implied=0.9, err=0.1))
    db.refresh(c)
    assert c.centroid_is_real is True and c.has_centroid_dip is False


# ------------------------------------------------- failure isolation (from the standards review)

from app.pipeline.errors import TransientCatalogError  # noqa: E402


def test_one_bad_candidate_does_not_abort_or_stall_the_batch(db):
    a, b = _cand(db, 30), _cand(db, 31)

    def measure(**kw):
        if kw["tic_id"] == 1030:
            raise RuntimeError("boom")
        return _result()

    out = sync_real_centroids(db, limit=5, measure=measure)
    db.refresh(a), db.refresh(b)
    assert out["errors"] == 1 and out["measured"] == 1
    assert a.centroid_status == "error" and a.centroid_attempted_at is not None and a.centroid_is_real is False
    assert b.centroid_is_real is True


def test_transient_error_is_retried_within_a_day_not_banned_for_90(db):
    c = _cand(db, 32)

    def down(**kw):
        raise TransientCatalogError("MAST unreachable")

    sync_real_centroids(db, limit=5, measure=down)
    db.refresh(c)
    assert c.centroid_status == "error"
    assert sync_real_centroids(db, limit=5, measure=down)["attempted"] == 0          # not instantly
    c.centroid_attempted_at = datetime.utcnow() - timedelta(days=2)
    db.commit()
    assert sync_real_centroids(db, limit=5, measure=lambda **kw: _result())["measured"] == 1


def test_lightcurve_sync_error_is_isolated_and_retried(db):
    from tests.test_lightcurve_vetter import _FakeVetter
    c = _cand(db, 33)

    def down(tic):
        raise TransientCatalogError("MAST unreachable")

    out = sync_real_lightcurve_vetting(db, fetch=down, vetter=_FakeVetter())
    db.refresh(c)
    assert out["errors"] == 1 and c.lc_vetting_status == "error"
    c.lc_vetting_attempted_at = datetime.utcnow() - timedelta(days=2)
    db.commit()
    ok = sync_real_lightcurve_vetting(db, fetch=lambda t: (np.arange(10.0), np.ones(10), [5]), vetter=_FakeVetter())
    assert ok["vetted"] == 1


def test_centroid_without_a_measurable_depth_is_unknown_not_clean(db):
    c = _cand(db, 34)
    sync_real_centroids(db, limit=5, measure=lambda **kw: _result(implied=None, err=None))
    db.refresh(c)
    assert c.centroid_is_real is True and c.has_centroid_dip is None


def test_epoch_fallback_is_looked_up_for_this_toi(db):
    c = _cand(db, 35, tranmid=None)
    seen = {}

    def lookup(tic, toi_id=None):
        seen["toi_id"] = toi_id
        return {"pl_tranmid": 2458500.0}

    sync_real_centroids(db, limit=5, measure=lambda **kw: _result(), epoch_lookup=lookup)
    assert seen["toi_id"] == c.toi_id


def test_spectroscopy_match_clears_every_fabricated_seed_value(db):
    cand = _cand(db, 36)
    host = db.get(HostStar, cand.host_id)
    host.teff_spec, host.rad_spec, host.fe_h, host.alpha_fe = 5555.0, 1.234, 0.3, 0.1   # seed_db.py-style fabrications
    db.commit()
    sync_real_spectroscopy(db, limit=5, lookup=lambda ra, dec: SpectroscopyResult(None, -0.2, 4.4))
    db.refresh(host)
    assert host.spectroscopy_is_real is True
    assert host.teff_spec is None and host.rad_spec is None and host.alpha_fe is None   # not left behind
    assert host.fe_h == -0.2


def test_every_target_takes_a_shared_rate_limit_token_before_network_work(db):
    for i in (40, 41, 42):
        _cand(db, i)

    class Counting:
        n = 0

        def acquire(self):
            Counting.n += 1

    sync_real_centroids(db, limit=5, measure=lambda **kw: None, rate_limiter=Counting())
    assert Counting.n == 3
