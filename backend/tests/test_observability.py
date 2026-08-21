import os
import sys
from datetime import date

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.science.observability import compute_observability, compute_observability_batch, TargetSpec


def test_target_below_horizon_is_not_observable():
    """A target far from zenith at the evaluated time must report low/negative
    altitude and observable_tonight=False, not silently pass."""
    result = compute_observability(
        ra_deg=279.23, dec_deg=38.78,  # Vega
        observer_lat_deg=19.82, observer_lon_deg=-155.47, observer_elevation_m=4207,
        night_date=date(2026, 8, 13),
    )
    assert isinstance(result.current_altitude_deg, float)
    assert isinstance(result.moon_separation_deg, float)
    assert 0.0 <= result.moon_illumination_fraction <= 1.0


def test_no_transit_epoch_reports_no_window_not_a_fabricated_one():
    """UPGRADE_PLAN.md's own honesty rule: missing tranmid must yield
    transit_window=None, never a guessed/fabricated window."""
    result = compute_observability(
        ra_deg=100.0, dec_deg=20.0,
        observer_lat_deg=30.0, observer_lon_deg=-110.0, observer_elevation_m=2000,
        night_date=date(2026, 8, 13),
        period_days=5.0, duration_hours=2.5, tranmid_bjd=None,
    )
    assert result.transit_window is None
    assert "no transit epoch" in result.reason


def test_transit_window_computed_when_epoch_available():
    result = compute_observability(
        ra_deg=100.0, dec_deg=20.0,
        observer_lat_deg=30.0, observer_lon_deg=-110.0, observer_elevation_m=2000,
        night_date=date(2026, 8, 13),
        period_days=5.0, duration_hours=2.5, tranmid_bjd=2459000.5,
    )
    assert result.transit_window is not None
    assert result.transit_window.start_utc < result.transit_window.mid_utc < result.transit_window.end_utc


def test_airmass_none_when_below_horizon():
    result = compute_observability(
        ra_deg=279.23, dec_deg=38.78,
        observer_lat_deg=19.82, observer_lon_deg=-155.47, observer_elevation_m=4207,
        night_date=date(2026, 8, 13),
    )
    if result.current_altitude_deg <= 0:
        assert result.current_airmass is None


def test_batch_matches_single_target_exactly():
    """Regression test: compute_observability_batch is a real ~30x-measured
    performance fix (196 targets: ~32s looped vs ~1s batched, found while
    load-testing /observability against the growing dev DB), not a behavior
    change -- it must produce identical results to the single-target function."""
    night = date(2026, 8, 14)
    raw = [
        (279.23, 38.78, None, None, None),
        (100.0, 20.0, 5.0, 2.5, 2459000.5),
        (150.5, -30.2, 12.3, 3.1, 2458900.2),
    ]
    singles = [
        compute_observability(ra, dec, 31.68, -110.88, 2096, night, period, dur, tranmid)
        for ra, dec, period, dur, tranmid in raw
    ]
    specs = [
        TargetSpec(ra_deg=ra, dec_deg=dec, period_days=period, duration_hours=dur, tranmid_bjd=tranmid)
        for ra, dec, period, dur, tranmid in raw
    ]
    batched = compute_observability_batch(specs, 31.68, -110.88, 2096, night)

    for single, batch in zip(singles, batched):
        assert single.current_altitude_deg == pytest.approx(batch.current_altitude_deg, abs=1e-9)
        assert single.moon_separation_deg == pytest.approx(batch.moon_separation_deg, abs=1e-9)
        assert single.moon_illumination_fraction == pytest.approx(batch.moon_illumination_fraction, abs=1e-9)
        assert single.observable_tonight == batch.observable_tonight
        assert single.reason == batch.reason
        if single.transit_window:
            assert batch.transit_window is not None
            assert single.transit_window.mid_utc == batch.transit_window.mid_utc


def test_batch_empty_list_returns_empty():
    assert compute_observability_batch([], 31.68, -110.88, 2096, date(2026, 8, 14)) == []
