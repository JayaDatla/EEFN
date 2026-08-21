import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from app.science.radius import (
    compute_derived_planet_radius_earth,
    compute_derived_planet_radius_uncertainty,
)


def test_derived_radius_matches_known_earth_analog():
    """Earth transiting the Sun: depth = (R_Earth/R_Sun)^2 ~= 84 ppm -- the derived
    radius should recover ~1.0 R_Earth."""
    depth_ppm = (1.0 / 109.2) ** 2 * 1e6
    rp = compute_derived_planet_radius_earth(radius_solar=1.0, transit_depth_ppm=depth_ppm)
    assert rp == pytest.approx(1.0, rel=0.01)


def test_derived_radius_none_when_inputs_missing():
    assert compute_derived_planet_radius_earth(None, 1000.0) is None
    assert compute_derived_planet_radius_earth(1.0, None) is None
    assert compute_derived_planet_radius_earth(1.0, -5.0) is None


def test_uncertainty_scales_with_radius_precision():
    """UPGRADE_PLAN.md E.3: a target with a tightly-measured stellar radius must get a
    smaller propagated uncertainty than an otherwise-identical target with a loosely
    measured one -- never a fixed value regardless of actual measurement quality."""
    tight = compute_derived_planet_radius_uncertainty(
        radius_solar=1.0, radius_err_lower=0.98, radius_err_upper=1.02,
        transit_depth_ppm=1000.0, transit_depth_err=50.0,
    )
    loose = compute_derived_planet_radius_uncertainty(
        radius_solar=1.0, radius_err_lower=0.8, radius_err_upper=1.2,
        transit_depth_ppm=1000.0, transit_depth_err=50.0,
    )
    assert tight is not None and loose is not None
    assert tight < loose


def test_uncertainty_none_without_stellar_radius_error():
    """Must not fabricate an uncertainty when no real per-target radius error is
    available -- unlike density.py's discrepancy-sigma (which has a disclosed
    fallback), this derived value has no established default and returns None rather
    than inventing one."""
    result = compute_derived_planet_radius_uncertainty(
        radius_solar=1.0, radius_err_lower=None, radius_err_upper=None,
        transit_depth_ppm=1000.0, transit_depth_err=50.0,
    )
    assert result is None


def test_uncertainty_falls_back_to_default_depth_error_when_unmeasured():
    with_measured_depth_err = compute_derived_planet_radius_uncertainty(
        radius_solar=1.0, radius_err_lower=0.95, radius_err_upper=1.05,
        transit_depth_ppm=1000.0, transit_depth_err=10.0,
    )
    with_default_depth_err = compute_derived_planet_radius_uncertainty(
        radius_solar=1.0, radius_err_lower=0.95, radius_err_upper=1.05,
        transit_depth_ppm=1000.0, transit_depth_err=None,
    )
    assert with_measured_depth_err is not None and with_default_depth_err is not None
    assert with_measured_depth_err != with_default_depth_err
