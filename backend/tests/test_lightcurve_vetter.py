"""Featurizer physics + vetting sync, on synthetic light curves with known truth."""
import os
import sys
from datetime import datetime

import numpy as np
import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import ExoplanetCandidate, HostStar
from app.db.session import Base
from app.ml import lightcurve_features as LF
from app.ml.lightcurve_vetter import LightCurveVetter, lightcurve_vetter
from app.pipeline.real_sync import sync_real_lightcurve_vetting

PERIOD, DUR_H, T0 = 4.0, 3.0, 2.0


def _lc(depth=0.004, odd_extra=0.0, secondary=0.0, noise=0.0004, seed=0, days=120.0):
    rng = np.random.RandomState(seed)
    t = np.arange(0, days, LF.KEPLER_LONG_CADENCE_DAYS)
    f = np.ones_like(t) + rng.normal(0, noise, t.size) + 0.001 * np.sin(2 * np.pi * t / 9.0)
    phase = ((t - T0 + PERIOD / 2) % PERIOD) - PERIOD / 2
    epoch = np.round((t - T0) / PERIOD).astype(int)
    half = DUR_H / 24 / 2
    in_tr = np.abs(phase) < half
    f[in_tr] -= depth + odd_extra * (epoch[in_tr] % 2 == 1)
    sec = np.abs(np.abs(phase) - PERIOD / 2) < half
    f[sec] -= secondary
    return t, f


def _stats(**kw):
    t, f = _lc(**kw)
    out = LF.build_feature_vector(t, f, PERIOD, T0, DUR_H, {"teff": 5700, "rstar": 1.0, "depth_ppm": 4000})
    assert out is not None
    return dict(zip(LF.FEATURE_NAMES, out[0]))


def test_clean_planet_like_transit_has_no_eb_signatures():
    s = _stats()
    assert s["snr"] > 10
    assert s["odd_even_sigma"] < 3
    assert abs(s["secondary_sigma"]) < 3


def test_unequal_odd_even_depths_are_flagged():
    assert _stats(odd_extra=0.003)["odd_even_sigma"] > 8


def test_secondary_eclipse_is_flagged():
    s = _stats(secondary=0.002)
    assert s["secondary_sigma"] > 8 and s["secondary_ratio"] > 0.3


def test_flat_bottomed_box_transit_reads_flat():
    assert _stats()["flatness"] > 0.85


def test_rebin_matches_kepler_cadence_and_is_noop_on_coarse_data():
    t = np.arange(0, 10, 2.0 / 1440)
    f = np.ones_like(t)
    tb, fb = LF.rebin(t, f)
    assert abs(np.median(np.diff(tb)) - LF.KEPLER_LONG_CADENCE_DAYS) < 1e-3
    t2 = np.arange(0, 10, LF.KEPLER_LONG_CADENCE_DAYS)
    t3, _ = LF.rebin(t2, np.ones_like(t2))
    assert len(t3) == len(t2)


def test_unusable_inputs_return_none_not_a_guess():
    t, f = _lc(days=1.0)
    assert LF.build_feature_vector(t, f, PERIOD, T0, DUR_H) is None
    t, f = _lc()
    assert LF.build_feature_vector(t, f, 0.1, T0, DUR_H) is None   # period shorter than the transit allows


@pytest.mark.skipif(not lightcurve_vetter.available, reason="vetter artifact not present")
def test_vetter_returns_a_normalised_distribution_with_provenance():
    t, f = _lc()
    out = lightcurve_vetter.vet(t, f, PERIOD, T0, DUR_H, {"teff": 5700, "rstar": 1.0, "depth_ppm": 4000})
    assert out["model_status"] == "trained" and out["model_version"]
    assert abs(sum(out["classification"].values()) - 1.0) < 1e-6
    assert len(out["global_view"]) == 2001 and len(out["local_view"]) == 201


def test_missing_model_reports_unavailable_instead_of_guessing(tmp_path):
    v = LightCurveVetter(model_path=str(tmp_path / "nope.pkl"))
    assert v.available is False
    t, f = _lc()
    assert v.vet(t, f, PERIOD, T0, DUR_H)["model_status"] == "unavailable"


# ---------------------------------------------------------------------------- sync

class _FakeVetter:
    available = True
    load_error = None

    def vet(self, time, flux, period, t0, duration_h, stellar=None):
        return {"model_status": "trained", "model_version": "fake", "classification": {"Planet Transit": 1.0},
                "best_class": "Planet Transit", "confidence": 1.0, "features": {}, "global_view": [], "local_view": [],
                "_t0": t0}


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _cand(db, toi, tranmid=2458500.0):
    host = HostStar(hostname=f"TIC {toi}", ra=1.0, dec=1.0, teff=5700.0, rad=1.0)
    db.add(host)
    db.flush()
    c = ExoplanetCandidate(host_id=host.id, tic_id=toi, toi_id=float(toi) + 0.01, pl_name=f"TOI-{toi}.01",
                           disposition="PC", orbper=3.0, trandurh=2.0, trandep=1000.0, tranmid=tranmid)
    db.add(c)
    db.commit()
    return c


def test_sync_stores_real_vetting_and_converts_epoch_to_btjd(db):
    c = _cand(db, 1)
    out = sync_real_lightcurve_vetting(db, fetch=lambda tic: (np.arange(10.0), np.ones(10), [5]), vetter=_FakeVetter())
    db.refresh(c)
    assert out["vetted"] == 1 and c.lc_vetting_status == "vetted"
    assert c.lc_vetting_json["_t0"] == 1500.0                  # 2458500 - 2457000
    assert c.lc_vetting_json["sectors"] == [5] and c.lc_vetting_json["input_source"] == "real_tess_spoc_2min"
    assert sync_real_lightcurve_vetting(db, fetch=lambda t: None, vetter=_FakeVetter())["attempted"] == 0


def test_sync_records_missing_lightcurve_and_backs_off(db):
    c = _cand(db, 2)
    out = sync_real_lightcurve_vetting(db, fetch=lambda tic: None, vetter=_FakeVetter())
    db.refresh(c)
    assert out["vetted"] == 0 and c.lc_vetting_status == "no_lightcurve" and c.lc_vetting_json is None
    assert sync_real_lightcurve_vetting(db, fetch=lambda t: None, vetter=_FakeVetter())["attempted"] == 0


def test_sync_without_a_model_does_nothing(db):
    _cand(db, 3)
    class Down(_FakeVetter):
        available, load_error = False, "missing"
    out = sync_real_lightcurve_vetting(db, fetch=lambda t: None, vetter=Down())
    assert out["attempted"] == 0 and "skipped" in out
