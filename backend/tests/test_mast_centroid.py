"""measure_centroid_offset is a pure function, so the estimator's two claims are
tested against synthetic series with known truth: it recovers an injected in-transit
offset, and it does NOT report one for a red-noise + slow-drift series that has none
(the failure mode of the white-noise, single-global-baseline version it replaced)."""
import os
import sys

import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.pipeline.mast_centroid import measure_centroid_offset

PERIOD, DUR_H, EPOCH = 3.0, 3.0, 1.0


def _series(seed, offset_px=0.0, drift_px=0.05, rw=0.002):
    rng = np.random.RandomState(seed)
    t = np.arange(0.0, 27.0, 2.0 / 1440.0)
    walk = np.cumsum(rng.normal(0, rw / 10, t.size))               # red noise
    slow = drift_px * np.sin(2 * np.pi * t / 20.0)                    # slow pointing drift
    col = 4.0 + slow + walk + rng.normal(0, 0.004, t.size)
    walk_r = np.cumsum(rng.normal(0, rw / 10, t.size))
    row = 5.0 - slow + walk_r + rng.normal(0, 0.004, t.size)
    phase = ((t - EPOCH + PERIOD / 2) % PERIOD) - PERIOD / 2
    in_tr = np.abs(phase) < DUR_H / 24.0 / 2
    col = col + offset_px * in_tr
    return t, col, row


def test_recovers_injected_offset():
    t, c, r = _series(1, offset_px=0.03)
    m = measure_centroid_offset(t, c, r, PERIOD, EPOCH, DUR_H)
    assert m is not None
    assert abs(m.dx - 0.03) < 0.01
    assert np.hypot(m.dx / m.sigma_x, m.dy / m.sigma_y) > 4


def test_no_false_detection_on_drift_and_red_noise():
    sig = []
    for seed in range(8):
        t, c, r = _series(100 + seed)
        m = measure_centroid_offset(t, c, r, PERIOD, EPOCH, DUR_H)
        assert m is not None
        sig.append(np.hypot(m.dx / m.sigma_x, m.dy / m.sigma_y))
    # Under the null the statistic is ~chi(2); a >4 sigma value in 8 trials would mean
    # the null estimate is badly miscalibrated.
    assert max(sig) < 4.0, sig


def test_returns_none_without_coverage():
    t = np.arange(0.0, 1.0, 2.0 / 1440.0)   # never reaches a second transit
    assert measure_centroid_offset(t, np.zeros_like(t), np.zeros_like(t), PERIOD, EPOCH, DUR_H) is None


def _with_flux(seed, depth=0.005, source_offset_px=0.0):
    """Dip of fractional `depth` in an aperture flux series; the dimming source sits
    `source_offset_px` from the target, so the photocentre moves by ~ offset x depth."""
    t, c, r = _series(seed)
    rng = np.random.RandomState(seed + 7)
    flux = 1.0 + rng.normal(0, 0.0005, t.size)
    phase = ((t - EPOCH + PERIOD / 2) % PERIOD) - PERIOD / 2
    in_tr = np.abs(phase) < DUR_H / 24.0 / 2
    flux[in_tr] -= depth
    c = c + source_offset_px * depth * in_tr
    return t, c, r, flux


def test_implied_source_offset_recovers_the_separation_of_the_dimming_source():
    from app.pipeline.mast_centroid import TESS_PIXEL_SCALE_ARCSEC
    t, c, r, f = _with_flux(3, depth=0.005, source_offset_px=0.5)      # 10.5 arcsec away
    m = measure_centroid_offset(t, c, r, PERIOD, EPOCH, DUR_H, flux=f)
    assert m is not None and abs(m.depth - 0.005) < 0.0007
    implied = np.hypot(m.dx, m.dy) * TESS_PIXEL_SCALE_ARCSEC / m.depth
    assert 0.5 * 10.5 < implied < 1.6 * 10.5


def test_on_target_transit_has_near_zero_implied_offset():
    from app.pipeline.mast_centroid import TESS_PIXEL_SCALE_ARCSEC
    t, c, r, f = _with_flux(4, depth=0.005, source_offset_px=0.0)
    m = measure_centroid_offset(t, c, r, PERIOD, EPOCH, DUR_H, flux=f)
    implied = np.hypot(m.dx, m.dy) * TESS_PIXEL_SCALE_ARCSEC / m.depth
    err = np.hypot(m.sigma_x, m.sigma_y) * TESS_PIXEL_SCALE_ARCSEC / m.depth
    assert implied < 3.0 * err          # consistent with zero offset given its own uncertainty


def test_a_significant_but_tiny_shift_is_not_flagged_as_a_dip():
    """Millipixel shifts can be statistically significant at high SNR yet be entirely
    benign (faint neighbour); CentroidResult.is_dip must also require a physical size."""
    from app.pipeline.mast_centroid import CentroidResult
    base = dict(offset_arcsec=0.01, significance_sigma=6.0, sector=1, n_in_transit=1, n_out_of_transit=1,
                dx_binned=[], dy_binned=[])
    assert CentroidResult(**base, implied_offset_arcsec=0.8, implied_offset_err_arcsec=0.1).is_dip is False
    assert CentroidResult(**base, implied_offset_arcsec=6.0, implied_offset_err_arcsec=1.0).is_dip is True
    assert CentroidResult(**base, implied_offset_arcsec=6.0, implied_offset_err_arcsec=4.0).is_dip is False


def test_long_transit_still_gets_a_null_distribution():
    """A 5.6 h transit on a 4.1 d period used to leave zero null phase space and silently
    return None (found on TOI-104.01)."""
    rng = np.random.RandomState(5)
    t = np.arange(0.0, 27.0, 2.0 / 1440.0)
    c = 4.0 + rng.normal(0, 0.004, t.size)
    r = 5.0 + rng.normal(0, 0.004, t.size)
    assert measure_centroid_offset(t, c, r, 4.0873, 1.3, 5.59) is not None
