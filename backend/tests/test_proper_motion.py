import math
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import pytest

from app.pipeline.ingest import positions_at_gaia_epoch, propagate_proper_motion

ARCSEC = 1.0 / 3600.0


def test_ra_shift_is_divided_by_cos_dec():
    """pmRA is mu_alpha* (already times cos dec): at dec=60 the coordinate moves twice as far."""
    ra, dec = propagate_proper_motion(100.0, 60.0, pm_ra_mas=1000.0, pm_dec_mas=0.0, dt_years=16.0)
    assert (ra - 100.0) / ARCSEC == pytest.approx(16.0 / math.cos(math.radians(60.0)), rel=1e-6)
    assert dec == 60.0
    # on the sky the displacement is mu_alpha* * dt regardless of declination
    assert (ra - 100.0) * math.cos(math.radians(60.0)) / ARCSEC == pytest.approx(16.0, rel=1e-6)


def test_dec_shift_and_equator_are_unchanged_by_the_cos_term():
    ra, dec = propagate_proper_motion(10.0, 0.0, pm_ra_mas=500.0, pm_dec_mas=-250.0)
    assert (ra - 10.0) / ARCSEC == pytest.approx(8.0)
    assert (dec - 0.0) / ARCSEC == pytest.approx(-4.0)


def test_missing_proper_motion_leaves_the_position_alone_and_ra_wraps():
    assert propagate_proper_motion(5.0, 5.0, None, float("nan")) == (5.0, 5.0)
    ra, _ = propagate_proper_motion(359.9999, 0.0, pm_ra_mas=10000.0)
    assert 0.0 <= ra < 360.0


def test_poles_do_not_blow_up():
    ra, dec = propagate_proper_motion(10.0, 90.0, pm_ra_mas=100.0)
    assert math.isfinite(ra) and math.isfinite(dec)


def test_a_fast_mover_is_brought_inside_the_match_radius():
    """A 600 mas/yr star drifts ~9.6 arcsec in 16 years -- outside a 5 arcsec match radius unless the
    upload position is propagated first."""
    df = pd.DataFrame({"toi": ["1.01", "2.01"], "ra": [50.0, 80.0], "dec": [10.0, -30.0],
                       "st_pmra": [600.0, None], "st_pmdec": [0.0, None]})
    moved = positions_at_gaia_epoch(df)
    drift_arcsec = (moved["ra"][0] - 50.0) * math.cos(math.radians(10.0)) / ARCSEC
    assert drift_arcsec == pytest.approx(9.6, rel=1e-3) and drift_arcsec > 5.0
    assert (moved["ra"][1], moved["dec"][1]) == (80.0, -30.0)            # no proper motion -> unchanged
    assert list(df["ra"]) == [50.0, 80.0]                                  # input not mutated


def test_works_when_the_catalog_has_no_proper_motion_columns():
    df = pd.DataFrame({"toi": ["1.01"], "ra": [50.0], "dec": [10.0]})
    moved = positions_at_gaia_epoch(df)
    assert (moved["ra"][0], moved["dec"][0]) == (50.0, 10.0)
