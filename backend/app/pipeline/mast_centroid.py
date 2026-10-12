"""
UPGRADE_PLAN.md F.6: real MAST target-pixel-file centroid analysis -- the single best
discriminator against background eclipsing binaries (the largest false-positive class).

Two layers:

* `measure_centroid_offset` -- a pure function over (time, column, row) centroid series.
  No network, no lightkurve; unit-testable with injected signals.
* `compute_real_centroid_offset` -- downloads real TESS 2-minute-cadence TPFs from MAST,
  builds aperture-restricted flux-weighted centroids and hands them to the above.

What changed from the first version (which compared one global in-transit mean against
one global out-of-transit mean and divided by a white-noise standard error):

1. **Per-event local baseline.** Each transit event is compared against a linear fit to
   the out-of-transit cadences immediately around *that* event, so slow pointing drift
   and thermal trends across a sector no longer masquerade as an offset.
2. **Aperture-restricted centroid.** Moments are taken over the SPOC optimal aperture,
   not the whole postage stamp, so unrelated variable neighbours at the stamp edge don't
   dilute (or fake) the signal.
3. **Empirical significance.** TESS centroid series are strongly red (pointing jitter,
   momentum dumps), so a white-noise standard error overstates significance badly. The
   null distribution is instead measured from the data itself: the identical estimator
   is re-run at many fake epochs away from the real transit and secondary-eclipse
   phases, and the real offset is compared with that spread.
4. **Implied source offset, not raw photocentre shift.** A photocentre shift scales with the
   transit depth: a background source at separation d that supplies the whole dip moves the
   photocentre by ~ d x depth, so even a genuine background eclipsing binary produces only
   milli-arcsecond shifts on a 21"/pixel detector, and so does an on-target transit with a
   faint neighbour. Dividing the measured shift by the measured depth gives the separation
   of the dimming source from the target in arcseconds -- the quantity that distinguishes
   the two cases (~0 vs. a fraction of a pixel). `has_centroid_dip` is set from that, not
   from the raw shift.
5. **Up to MAX_SECTORS sectors**, inverse-variance combined, and the downloaded pixel
   files are deleted after use -- only the derived numbers are persisted (storage design
   for running this on a schedule rather than as a one-off script).

Every value is a genuine MAST download plus a genuine computation; a failure returns
None ("not measured"), never a default.
"""
import logging
import shutil
import tempfile
from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import requests

from app.pipeline.errors import TransientCatalogError

logger = logging.getLogger(__name__)

NASA_TAP_URL = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"

# TESS CCD pixel scale (Ricker et al. 2015) -- used to convert a photocentre offset
# measured in pixels into arcseconds.
TESS_PIXEL_SCALE_ARCSEC = 21.0

# Must match deep_learning_pipeline.py's CENTROID_BINS and the local-view phase
# window convention (duration_days * 3.5, per preprocess_lightcurve).
CENTROID_BINS = 201
LOCAL_WINDOW_DURATIONS = 3.5

MAX_SECTORS = 2
N_NULL_TRIALS = 60
MIN_EVENTS = 2
MIN_IN_PER_EVENT = 3
MIN_OUT_PER_EVENT = 8
IN_TRANSIT_FRACTION = 0.8   # of the full duration: skip ingress/egress where the dip is partial
# A dip is flagged only if the implied source offset is both statistically significant (the
# empirical null below) and physically large enough to matter. 2" (~0.1 TESS pixel) is a
# deliberately conservative engineering floor, NOT tuned on labelled data -- revisit once
# there is a labelled set of confirmed background-EB centroid cases.
MIN_IMPLIED_OFFSET_ARCSEC = 2.0
OUT_INNER_DURATIONS = 1.0   # baseline starts this many durations from mid-transit...
OUT_OUTER_DURATIONS = LOCAL_WINDOW_DURATIONS  # ...and ends at the local-view edge


@dataclass
class CentroidResult:
    offset_arcsec: float
    significance_sigma: float
    sector: int
    n_in_transit: int
    n_out_of_transit: int
    dx_binned: list  # length CENTROID_BINS, phase-folded offset in arcsec, feeds CentroidSpatialCNN
    dy_binned: list
    n_events: int = 0
    n_sectors: int = 1
    dx_arcsec: float = 0.0
    dy_arcsec: float = 0.0
    depth_fraction: Optional[float] = None
    implied_offset_arcsec: Optional[float] = None       # |photocentre shift| / depth
    implied_offset_err_arcsec: Optional[float] = None   # 1-sigma, from the empirical null

    @property
    def is_dip(self) -> bool:
        """Significant AND large enough to matter -- see MIN_IMPLIED_OFFSET_ARCSEC."""
        if self.implied_offset_arcsec is None or not self.implied_offset_err_arcsec:
            return False
        return (self.implied_offset_arcsec >= MIN_IMPLIED_OFFSET_ARCSEC
                and self.implied_offset_arcsec / self.implied_offset_err_arcsec >= 3.0)


@dataclass
class _SeriesMeasurement:
    depth: Optional[float]   # fractional aperture-flux depth (None if no flux supplied)
    dx: float            # pixels
    dy: float
    sigma_x: float       # empirical null std (pixels)
    sigma_y: float
    n_in: int
    n_out: int
    n_events: int
    phase_fold: tuple    # (phase_days, resid_col_px, resid_row_px) for the binned view


def fetch_transit_epoch(tic_id: int, toi_id: Optional[float] = None) -> Optional[dict]:
    """Real NASA TAP lookup for the transit midpoint (pl_tranmid) needed to phase-fold
    a downloaded TPF.

    A star can host several TOIs, each with its own epoch/period: pass `toi_id` so the row for
    the planet being analysed is returned, not whichever TOI of that star the archive lists
    first. Raises TransientCatalogError on a network failure (so "archive unreachable" is
    never confused with "no epoch published")."""
    where = f"tid = {int(tic_id)}"
    if toi_id is not None:
        where += f" and toi = {float(toi_id)}"
    query = f"select pl_tranmid, pl_orbper, pl_trandurh from toi where {where}"
    try:
        r = requests.get(NASA_TAP_URL, params={"query": query, "format": "json"}, timeout=12.0)
        r.raise_for_status()
        rows = r.json()
    except Exception as e:
        logger.exception("Failed to fetch transit epoch for TIC %s", tic_id)
        raise TransientCatalogError(f"NASA TAP epoch lookup failed: {e}") from e
    if not rows or rows[0].get("pl_tranmid") is None:
        return None
    return rows[0]


def _event_offsets(time, col, row, flux, period, epoch, dur_days, collect_fold=False):
    """Mean in-transit minus locally-detrended baseline, per axis, combined over events.
    Returns (dx, dy, depth, n_in, n_out, n_events, fold) or None if too few usable events.
    `depth` is the fractional dip of `flux` measured with the same local baselines (None
    when no flux series was supplied)."""
    phase = ((time - epoch + period / 2.0) % period) - period / 2.0
    event = np.round((time - epoch) / period).astype(int)
    half_in = 0.5 * dur_days * IN_TRANSIT_FRACTION
    out_in = OUT_INNER_DURATIONS * dur_days
    out_out = min(OUT_OUTER_DURATIONS * dur_days, 0.45 * period)
    if out_out <= out_in:
        return None

    dxs, dys, deps, weights = [], [], [], []
    n_in_tot = n_out_tot = 0
    fold_ph, fold_c, fold_r = [], [], []
    for ev in np.unique(event):
        sel = event == ev
        ph, c, r, t = phase[sel], col[sel], row[sel], time[sel]
        fl = flux[sel] if flux is not None else None
        m_in = np.abs(ph) < half_in
        m_out = (np.abs(ph) > out_in) & (np.abs(ph) < out_out)
        if m_in.sum() < MIN_IN_PER_EVENT or m_out.sum() < MIN_OUT_PER_EVENT:
            continue
        # Need baseline on both sides or the linear fit extrapolates through the transit.
        if (ph[m_out] < 0).sum() < 3 or (ph[m_out] > 0).sum() < 3:
            continue
        t0 = t[m_out].mean()
        try:
            pc = np.polyfit(t[m_out] - t0, c[m_out], 1)
            pr = np.polyfit(t[m_out] - t0, r[m_out], 1)
        except Exception:
            continue
        res_c_in = c[m_in] - np.polyval(pc, t[m_in] - t0)
        res_r_in = r[m_in] - np.polyval(pr, t[m_in] - t0)
        if fl is not None:
            pf = np.polyfit(t[m_out] - t0, fl[m_out], 1)
            base_in = np.polyval(pf, t[m_in] - t0)
            deps.append(float(-np.mean((fl[m_in] - base_in) / base_in)))
        dxs.append(float(np.mean(res_c_in)))
        dys.append(float(np.mean(res_r_in)))
        weights.append(float(m_in.sum()))
        n_in_tot += int(m_in.sum())
        n_out_tot += int(m_out.sum())
        if collect_fold:
            win = np.abs(ph) < LOCAL_WINDOW_DURATIONS * dur_days
            fold_ph.append(ph[win])
            fold_c.append(c[win] - np.polyval(pc, t[win] - t0))
            fold_r.append(r[win] - np.polyval(pr, t[win] - t0))

    if len(dxs) < MIN_EVENTS:
        return None
    w = np.asarray(weights)
    dx = float(np.average(dxs, weights=w))
    dy = float(np.average(dys, weights=w))
    depth = float(np.average(deps, weights=w)) if deps else None
    fold = None
    if collect_fold:
        fold = (np.concatenate(fold_ph), np.concatenate(fold_c), np.concatenate(fold_r))
    return dx, dy, depth, n_in_tot, n_out_tot, len(dxs), fold


def measure_centroid_offset(
    time: np.ndarray,
    col: np.ndarray,
    row: np.ndarray,
    period_days: float,
    epoch_btjd: float,
    duration_hours: float,
    n_null: int = N_NULL_TRIALS,
    seed: int = 12345,
    flux: Optional[np.ndarray] = None,
) -> Optional[_SeriesMeasurement]:
    """In-transit centroid offset (pixels) with an empirical, red-noise-aware null.

    Returns None when there is not enough coverage to measure -- callers must treat that
    as "not measured", never "measured clean"."""
    time, col, row = (np.asarray(a, dtype=float) for a in (time, col, row))
    flux = np.asarray(flux, dtype=float) if flux is not None else None
    ok = np.isfinite(time) & np.isfinite(col) & np.isfinite(row)
    if flux is not None:
        ok &= np.isfinite(flux)
        flux = flux[ok]
    time, col, row = time[ok], col[ok], row[ok]
    dur_days = duration_hours / 24.0
    if len(time) < 50 or period_days <= 0 or dur_days <= 0:
        return None
    # Not enough room between transits for a baseline + a null phase space.
    if period_days < 2.0 * (LOCAL_WINDOW_DURATIONS + 0.5) * dur_days + 2.0 * dur_days:
        return None

    obs = _event_offsets(time, col, row, flux, period_days, epoch_btjd, dur_days, collect_fold=True)
    if obs is None:
        return None
    dx, dy, depth, n_in, n_out, n_events, fold = obs

    # Null: same estimator at fake epochs, excluding windows around the real transit
    # (phase 0) and the secondary-eclipse position (phase 0.5) so neither contaminates it.
    rng = np.random.RandomState(seed)
    # A fake event's baseline window (+/- LOCAL_WINDOW durations) must not reach the real
    # in-transit cadences, hence the (LOCAL_WINDOW + 0.5)-duration guard. The secondary-eclipse
    # exclusion only needs to cover the eclipse itself (+/- 1 duration), NOT a whole baseline
    # window: excluding the latter left no null phase space at all for long transits.
    guard = (LOCAL_WINDOW_DURATIONS + 0.5) * dur_days
    sec_guard = 1.0 * dur_days
    lo, hi = guard, period_days - guard
    null_dx, null_dy = [], []
    attempts = 0
    while len(null_dx) < n_null and attempts < n_null * 6:
        attempts += 1
        shift = rng.uniform(lo, hi)
        if abs(shift - period_days / 2.0) < sec_guard:
            continue
        res = _event_offsets(time, col, row, None, period_days, epoch_btjd + shift, dur_days)
        if res is None:
            continue
        null_dx.append(res[0])
        null_dy.append(res[1])
    if len(null_dx) < 10:
        return None

    # Null spread. Fake-epoch trials overlap heavily (neighbouring phases share most of
    # their cadences), so there are only ~(P - 2*guard)/duration independent draws, not
    # n_null: a plain standard deviation of so few correlated draws is itself noisy and
    # biased low. Inflate by the Student-t factor for that effective sample size so the
    # reported sigma is conservative rather than flattering.
    n_eff = max(4.0, (hi - lo) / dur_days / 2.0)
    t_factor = float(np.sqrt(n_eff / (n_eff - 2.0)) * (1.0 + 1.0 / (4.0 * n_eff)))

    def _std(a):
        return float(np.sqrt(np.mean((np.asarray(a) - np.median(a)) ** 2)) * t_factor) or 1e-9

    return _SeriesMeasurement(
        depth=depth,
        dx=dx - float(np.median(null_dx)),   # remove the systematic mean the estimator has at a random phase
        dy=dy - float(np.median(null_dy)),
        sigma_x=_std(null_dx),
        sigma_y=_std(null_dy),
        n_in=n_in, n_out=n_out, n_events=n_events, phase_fold=fold,
    )


def _bin_fold(phase, cvals, rvals, dur_days) -> tuple:
    """Median-bin the baseline-subtracted offsets onto the model's 201-bin local grid.
    Empty interior bins are interpolated between real neighbours; the edges stay 0."""
    window = LOCAL_WINDOW_DURATIONS * dur_days
    edges = np.linspace(-window, window, CENTROID_BINS + 1)
    idx = np.clip(np.digitize(phase, edges) - 1, 0, CENTROID_BINS - 1)
    out = []
    for vals in (cvals, rvals):
        binned = np.full(CENTROID_BINS, np.nan)
        for b in np.unique(idx):
            binned[b] = np.median(vals[idx == b])
        good = np.isfinite(binned)
        if good.sum() < 5:
            out.append([0.0] * CENTROID_BINS)
            continue
        binned = np.interp(np.arange(CENTROID_BINS), np.flatnonzero(good), binned[good])
        out.append((binned * TESS_PIXEL_SCALE_ARCSEC).tolist())
    return out[0], out[1]


def _aperture_centroids(tpf):
    """Flux-weighted centroid per cadence restricted to the SPOC optimal aperture."""
    mask = np.asarray(tpf.pipeline_mask, dtype=bool)
    if not mask.any():
        mask = tpf.create_threshold_mask(threshold=3, reference_pixel="center")
    flux = np.asarray(tpf.flux.value, dtype=float)  # (T, rows, cols)
    rows_idx, cols_idx = np.indices(flux.shape[1:])
    f = np.where(mask[None, :, :], flux, 0.0)
    total = np.nansum(f, axis=(1, 2))
    with np.errstate(invalid="ignore", divide="ignore"):
        col = np.nansum(f * cols_idx[None], axis=(1, 2)) / total
        row = np.nansum(f * rows_idx[None], axis=(1, 2)) / total
    col[total <= 0] = np.nan
    row[total <= 0] = np.nan
    return col, row, total


def compute_real_centroid_offset(
    tic_id: int, period_days: float, duration_hours: float, epoch_bjd: float,
    max_sectors: int = MAX_SECTORS,
) -> Optional[CentroidResult]:
    """Downloads up to `max_sectors` real TESS 2-minute-cadence target pixel files for
    `tic_id`, measures the in-transit centroid offset in each and combines them.
    A significant offset is the classic signature of a blended background eclipsing
    binary rather than a genuine transit on the target star."""
    import lightkurve as lk

    try:
        search = lk.search_targetpixelfile(f"TIC {int(tic_id)}", mission="TESS", exptime=120)
    except Exception as e:
        logger.exception("MAST search failed for TIC %s", tic_id)
        raise TransientCatalogError(f"MAST TPF search failed: {e}") from e
    if len(search) == 0:
        logger.info("No TESS 2-minute-cadence target pixel file found for TIC %s", tic_id)
        return None

    epoch_btjd = epoch_bjd - 2457000.0
    dur_days = duration_hours / 24.0
    per_sector: List[tuple] = []  # (sector, measurement)
    download_errors = 0
    tmpdir = tempfile.mkdtemp(prefix=f"eefn_tpf_{int(tic_id)}_")
    try:
        # Prefer the sectors with the most transits: spread picks across the baseline.
        picks = list(range(len(search)))
        step = max(1, len(picks) // max(1, max_sectors))
        picks = picks[::step][:max_sectors]
        for i in picks:
            try:
                tpf = search[i].download(download_dir=tmpdir)
            except Exception:
                logger.exception("TPF download failed for TIC %s (item %s)", tic_id, i)
                download_errors += 1
                continue
            if tpf is None:
                continue
            try:
                col, row, ap_flux = _aperture_centroids(tpf)
                meas = measure_centroid_offset(
                    np.asarray(tpf.time.value), col, row, period_days, epoch_btjd, duration_hours, flux=ap_flux
                )
            except Exception:
                logger.exception("Centroid computation failed for TIC %s (item %s)", tic_id, i)
                continue
            if meas is not None:
                per_sector.append((int(getattr(tpf, "sector", 0) or 0), meas))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)  # derived numbers are persisted; pixels are not

    if not per_sector:
        if download_errors and download_errors == len(picks):
            raise TransientCatalogError(f"every TPF download failed for TIC {tic_id}")
        return None

    # Inverse-variance combine across sectors, per axis.
    wx = np.array([1.0 / m.sigma_x ** 2 for _, m in per_sector])
    wy = np.array([1.0 / m.sigma_y ** 2 for _, m in per_sector])
    dx = float(np.sum(wx * [m.dx for _, m in per_sector]) / wx.sum())
    dy = float(np.sum(wy * [m.dy for _, m in per_sector]) / wy.sum())
    sx, sy = float(1.0 / np.sqrt(wx.sum())), float(1.0 / np.sqrt(wy.sum()))
    sigma = float(np.hypot(dx / sx, dy / sy))

    depths = [(m.depth, m.n_in) for _, m in per_sector if m.depth is not None and m.depth > 0]
    depth = float(np.average([d for d, _ in depths], weights=[n for _, n in depths])) if depths else None
    shift_px = float(np.hypot(dx, dy))
    implied = implied_err = None
    if depth:
        implied = shift_px * TESS_PIXEL_SCALE_ARCSEC / depth
        implied_err = float(np.hypot(sx, sy) * TESS_PIXEL_SCALE_ARCSEC / depth)

    best_sector, best = max(per_sector, key=lambda sm: sm[1].n_events)
    ph, cv, rv = best.phase_fold
    dx_binned, dy_binned = _bin_fold(ph, cv, rv, dur_days)

    return CentroidResult(
        offset_arcsec=float(np.hypot(dx, dy) * TESS_PIXEL_SCALE_ARCSEC),
        significance_sigma=sigma,
        sector=best_sector,
        n_in_transit=sum(m.n_in for _, m in per_sector),
        n_out_of_transit=sum(m.n_out for _, m in per_sector),
        dx_binned=dx_binned,
        dy_binned=dy_binned,
        n_events=sum(m.n_events for _, m in per_sector),
        n_sectors=len(per_sector),
        dx_arcsec=dx * TESS_PIXEL_SCALE_ARCSEC,
        dy_arcsec=dy * TESS_PIXEL_SCALE_ARCSEC,
        depth_fraction=depth,
        implied_offset_arcsec=implied,
        implied_offset_err_arcsec=implied_err,
    )
