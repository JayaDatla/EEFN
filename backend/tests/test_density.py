import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from app.science.density import (
    compute_transit_density_cgs,
    compute_gaia_density_cgs,
    compute_density_discrepancy_sigma,
)


def test_transit_density_uses_period_and_resolves_to_gcm3():
    """UPGRADE_PLAN.md A.4: the old formula never used pl_orbper at all. Doubling the
    period at fixed duration must change the result -- if it doesn't, period still isn't
    part of the computation."""
    density_short_period = compute_transit_density_cgs(period_days=2.0, duration_hours=2.5)
    density_long_period = compute_transit_density_cgs(period_days=4.0, duration_hours=2.5)

    assert density_short_period is not None
    assert density_long_period is not None
    assert density_short_period != density_long_period
    # Sun-like density is order-of-magnitude ~1 g/cm^3; a 2-day-period, 2.5h-duration
    # transit should land in a physically plausible stellar-density ballpark.
    assert 0.01 < density_short_period < 200.0


def test_transit_density_matches_trappist1b_once_the_radius_ratio_is_included():
    """TRAPPIST-1b: P=1.51087081 d, T14=36.40 min, depth ~0.727% (k ~ 0.085). Actual stellar
    density from M=0.0898 Msun, R=0.1192 Rsun is ~74.6 g/cm^3. Without k the formula read ~23% low,
    which an earlier version blamed on the impact parameter; the omitted (1+k)^3 factor accounts
    for essentially all of it."""
    from app.science.density import radius_ratio_from_depth_ppm
    actual = 74.6
    k = radius_ratio_from_depth_ppm(7270.0)
    with_k = compute_transit_density_cgs(1.51087081, 36.40 / 60.0, radius_ratio=k)
    without_k = compute_transit_density_cgs(1.51087081, 36.40 / 60.0)
    assert abs(with_k - actual) / actual < 0.05
    assert 0.20 < (actual - without_k) / actual < 0.26          # the old, biased-low behaviour
    assert with_k / without_k == pytest.approx((1 + k) ** 3, rel=0.02)


def test_larger_planets_need_the_radius_ratio_more():
    small = compute_transit_density_cgs(4.0, 3.0, radius_ratio=0.02)
    large = compute_transit_density_cgs(4.0, 3.0, radius_ratio=0.15)
    base = compute_transit_density_cgs(4.0, 3.0)
    assert small / base == pytest.approx(1.02 ** 3, rel=0.01)
    assert large / base == pytest.approx(1.15 ** 3, rel=0.01)


def test_unphysical_duration_returns_none():
    assert compute_transit_density_cgs(1.0, 14.0, radius_ratio=0.1) is None   # T14 > P/2


def test_transit_density_none_when_inputs_missing():
    assert compute_transit_density_cgs(None, 2.0) is None
    assert compute_transit_density_cgs(2.0, None) is None
    assert compute_transit_density_cgs(0.0, 2.0) is None


def test_gaia_density_none_when_inputs_missing():
    assert compute_gaia_density_cgs(None, 1.0) is None
    assert compute_gaia_density_cgs(1.0, None) is None
    assert compute_gaia_density_cgs(1.0, 0.0) is None


def test_gaia_density_sun_like():
    # Sun: M=1 Msun, R=1 Rsun -> density should equal SOLAR_DENSITY_CGS (1.408 g/cm^3)
    density = compute_gaia_density_cgs(mass_solar=1.0, radius_solar=1.0)
    assert density == pytest.approx(1.408)


def test_discrepancy_sigma_uses_real_per_target_radius_error_when_available():
    """Two targets with identical density mismatch but different measured radius
    precision must get different sigma values -- the old code used a fixed /0.3 divisor
    for every target regardless of how well-characterized it was (A.4/C.4)."""
    sigma_precise = compute_density_discrepancy_sigma(
        density_transit=2.0, density_gaia=1.0,
        radius_solar=1.0, radius_err_lower=0.98, radius_err_upper=1.02,  # tight, ~2%
    )
    sigma_loose = compute_density_discrepancy_sigma(
        density_transit=2.0, density_gaia=1.0,
        radius_solar=1.0, radius_err_lower=0.7, radius_err_upper=1.3,  # loose, ~30%
    )
    assert sigma_precise is not None and sigma_loose is not None
    assert sigma_precise > sigma_loose  # same absolute gap, but more sigma when better-measured


def test_discrepancy_sigma_falls_back_to_default_when_no_radius_error():
    sigma = compute_density_discrepancy_sigma(
        density_transit=2.0, density_gaia=1.0,
        radius_solar=1.0, radius_err_lower=None, radius_err_upper=None,
    )
    assert sigma is not None
    assert sigma > 0


def test_discrepancy_sigma_none_when_densities_missing():
    assert compute_density_discrepancy_sigma(None, 1.0, 1.0, 0.9, 1.1) is None
    assert compute_density_discrepancy_sigma(1.0, None, 1.0, 0.9, 1.1) is None
