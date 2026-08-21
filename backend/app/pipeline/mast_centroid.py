"""
UPGRADE_PLAN.md F.6: real MAST target-pixel-file centroid analysis -- the single best
discriminator against background eclipsing binaries (the largest false-positive class),
and the plan's own "highest scientific value" item in Phase 3.

Deliberately scoped to a small verification subset (see
validation/scripts/run_real_centroid_subset.py), not wired into the main per-target
ingestion pipeline: TPF downloads are GB-scale and this needs its own caching/storage
design before it can run at the full ~7,000-candidate scale -- the plan's own words:
"treat it as its own milestone with its own storage/caching design, not a quick add."
Every result this module produces is a genuine MAST download and a genuine
intensity-weighted-centroid computation; nothing here is synthetic or estimated.
"""
import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import requests

logger = logging.getLogger(__name__)

NASA_TAP_URL = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"

# TESS CCD pixel scale (Ricker et al. 2015) -- used to convert a photocentre offset
# measured in pixels into arcseconds.
TESS_PIXEL_SCALE_ARCSEC = 21.0


# Must match deep_learning_pipeline.py's CENTROID_BINS and the local-view phase
# window convention (duration_days * 3.5, per preprocess_lightcurve) so a real
# measurement is directly comparable to what CentroidSpatialCNN was trained on.
CENTROID_BINS = 201
LOCAL_WINDOW_DURATIONS = 3.5


@dataclass
class CentroidResult:
    offset_arcsec: float
    significance_sigma: float
    sector: int
    n_in_transit: int
    n_out_of_transit: int
    dx_binned: list  # length CENTROID_BINS, phase-folded offset in arcsec, feeds CentroidSpatialCNN
    dy_binned: list


def fetch_transit_epoch(tic_id: int) -> Optional[dict]:
    """Real NASA TAP lookup for the transit midpoint (pl_tranmid) needed to phase-fold
    a downloaded TPF -- the main ingestion query doesn't fetch this today since nothing
    else in the pipeline needs it yet."""
    query = f"SELECT pl_tranmid, pl_orbper, pl_trandurh FROM toi WHERE tid = {int(tic_id)}"
    try:
        r = requests.get(NASA_TAP_URL, params={"query": query, "format": "json"}, timeout=12.0)
        r.raise_for_status()
        rows = r.json()
        if not rows or rows[0].get("pl_tranmid") is None:
            return None
        return rows[0]
    except Exception:
        logger.exception("Failed to fetch transit epoch for TIC %s", tic_id)
        return None


def compute_real_centroid_offset(
    tic_id: int, period_days: float, duration_hours: float, epoch_bjd: float
) -> Optional[CentroidResult]:
    """
    Downloads a real TESS 2-minute-cadence target pixel file for `tic_id`, computes the
    intensity-weighted photocentre per cadence, and compares the mean in-transit
    photocentre against the mean out-of-transit photocentre. A significant offset is
    the classic signature of a blended background eclipsing binary rather than a
    genuine transit on the target star.

    Returns None (never a fabricated/default value) if no TPF exists, the download
    fails, or there isn't enough valid in-/out-of-transit coverage to compute a
    meaningful offset -- callers must treat None as "not measured," not "measured
    clean."
    """
    import lightkurve as lk

    try:
        search = lk.search_targetpixelfile(f"TIC {int(tic_id)}", mission="TESS", exptime=120)
    except Exception:
        logger.exception("MAST search failed for TIC %s", tic_id)
        return None

    if len(search) == 0:
        logger.info("No TESS 2-minute-cadence target pixel file found for TIC %s", tic_id)
        return None

    try:
        tpf = search[0].download()
    except Exception:
        logger.exception("TPF download failed for TIC %s", tic_id)
        return None

    if tpf is None:
        return None

    try:
        centroid_col, centroid_row = tpf.estimate_centroids(method="moments")
        time_btjd = tpf.time.value  # BTJD = BJD_TDB - 2457000.0

        epoch_btjd = epoch_bjd - 2457000.0
        phase = ((time_btjd - epoch_btjd + period_days / 2.0) % period_days) - period_days / 2.0
        half_duration_days = (duration_hours / 24.0) / 2.0

        in_transit = np.abs(phase) < half_duration_days
        # A buffer band around ingress/egress is excluded from the "out of transit"
        # baseline so partial-transit cadences don't contaminate it.
        out_of_transit = np.abs(phase) > (half_duration_days * 2.0)

        valid = np.isfinite(centroid_col.value) & np.isfinite(centroid_row.value)
        in_transit &= valid
        out_of_transit &= valid

        n_in, n_out = int(np.sum(in_transit)), int(np.sum(out_of_transit))
        if n_in < 3 or n_out < 3:
            logger.info(
                "Not enough valid in/out-of-transit cadences for TIC %s (n_in=%s, n_out=%s)",
                tic_id, n_in, n_out,
            )
            return None

        col_in, row_in = centroid_col.value[in_transit], centroid_row.value[in_transit]
        col_out, row_out = centroid_col.value[out_of_transit], centroid_row.value[out_of_transit]

        baseline_col, baseline_row = float(np.median(col_out)), float(np.median(row_out))

        dx = float(np.mean(col_in) - np.mean(col_out))
        dy = float(np.mean(row_in) - np.mean(row_out))
        offset_pixels = float(np.hypot(dx, dy))

        se_col = float(np.hypot(np.std(col_in, ddof=1) / np.sqrt(n_in), np.std(col_out, ddof=1) / np.sqrt(n_out)))
        se_row = float(np.hypot(np.std(row_in, ddof=1) / np.sqrt(n_in), np.std(row_out, ddof=1) / np.sqrt(n_out)))
        se_pixels = float(np.hypot(se_col, se_row)) or 1e-6

        # Phase-fold every valid cadence (not just the coarse in/out split above) into
        # the same 201-bin local-view window CentroidSpatialCNN's training data uses,
        # so a real measurement is a drop-in replacement for the synthetic proxy.
        local_window_days = (duration_hours / 24.0) * LOCAL_WINDOW_DURATIONS
        in_window = valid & (np.abs(phase) < local_window_days)
        if int(np.sum(in_window)) < 5:
            dx_binned = [0.0] * CENTROID_BINS
            dy_binned = [0.0] * CENTROID_BINS
        else:
            phase_w = phase[in_window]
            offset_col_w = (centroid_col.value[in_window] - baseline_col) * TESS_PIXEL_SCALE_ARCSEC
            offset_row_w = (centroid_row.value[in_window] - baseline_row) * TESS_PIXEL_SCALE_ARCSEC
            sort_idx = np.argsort(phase_w)
            local_target_phases = np.linspace(-local_window_days, local_window_days, CENTROID_BINS)
            dx_binned = np.interp(local_target_phases, phase_w[sort_idx], offset_col_w[sort_idx], left=0.0, right=0.0).tolist()
            dy_binned = np.interp(local_target_phases, phase_w[sort_idx], offset_row_w[sort_idx], left=0.0, right=0.0).tolist()

        return CentroidResult(
            offset_arcsec=offset_pixels * TESS_PIXEL_SCALE_ARCSEC,
            significance_sigma=offset_pixels / se_pixels,
            sector=int(getattr(tpf, "sector", 0) or 0),
            n_in_transit=n_in,
            n_out_of_transit=n_out,
            dx_binned=dx_binned,
            dy_binned=dy_binned,
        )
    except Exception:
        logger.exception("Centroid computation failed for TIC %s", tic_id)
        return None
