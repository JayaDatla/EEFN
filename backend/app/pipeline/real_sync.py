"""
Incremental, schedulable versions of the real MAST centroid (F.6), APOGEE-2 spectroscopy
(F.7) and real-light-curve vetting enrichments. Previously these only ran from one-off
validation scripts against a hand-picked handful of candidates.

Each function processes a bounded batch of targets that have never been tried (or were last
tried long enough ago), records the attempt either way, and returns a summary. `app.worker`
runs them nightly; validation scripts call them too, so there is exactly one implementation.

Failure semantics (all three functions):
* **Nothing found / unusable data** (no TPF, no APOGEE match, no 2-minute light curve) is a
  property of the target: recorded with a descriptive status and not retried for
  `retry_after_days`.
* **Transient failure** (MAST/NASA/VizieR unreachable -> `TransientCatalogError`, or any
  unexpected exception) says nothing about the target: recorded as status "error" and
  retried after `ERROR_RETRY_AFTER_DAYS` -- one bad night must not shelve a target for 90
  days, and one bad target must not abort (or, by rolling back before it commits its attempt
  timestamp, permanently stall) the rest of the batch.
"""
import logging
from datetime import datetime, timedelta
from typing import Callable, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.db.models import ExoplanetCandidate, HostStar
from app.pipeline import sync_status as S
from app.pipeline.rate_limiter import NullRateLimiter
from app.pipeline.mast_centroid import compute_real_centroid_offset, fetch_transit_epoch
from app.pipeline.spectroscopy import APOGEE_DR17_CATALOG, fetch_real_spectroscopy

logger = logging.getLogger(__name__)

BTJD_OFFSET = 2457000.0   # TESS BTJD = BJD_TDB - 2457000
ERROR_RETRY_AFTER_DAYS = 1



def _due(attempted_col, status_col, retry_after_days: int):
    """Never attempted, OR attempted long enough ago, OR errored recently-enough-to-retry."""
    now = datetime.utcnow()
    clauses = [
        attempted_col.is_(None),
        and_(attempted_col < now - timedelta(days=ERROR_RETRY_AFTER_DAYS), status_col == S.ERROR) if status_col is not None else None,
        attempted_col < now - timedelta(days=retry_after_days),
    ]
    return or_(*[c for c in clauses if c is not None])


def _record_error(db: Session, obj, attempted_attr: str, status_attr: Optional[str], exc: Exception) -> None:
    """Undo whatever the failed target half-wrote, then durably record the failed attempt."""
    db.rollback()
    setattr(obj, attempted_attr, datetime.utcnow())
    if status_attr:
        setattr(obj, status_attr, S.ERROR)
    db.commit()
    logger.warning("Sync error for %s (%s): %s", getattr(obj, "pl_name", None) or getattr(obj, "hostname", obj),
                   type(exc).__name__, exc)


# --------------------------------------------------------------------------- centroids

def sync_real_centroids(
    db: Session, limit: int = 15, retry_after_days: int = 90,
    measure: Callable = compute_real_centroid_offset, epoch_lookup: Callable = fetch_transit_epoch,
    rate_limiter=None,
) -> dict:
    rate_limiter = rate_limiter or NullRateLimiter()
    candidates = (
        db.query(ExoplanetCandidate)
        .filter(ExoplanetCandidate.tic_id.isnot(None))
        .filter(ExoplanetCandidate.orbper.isnot(None))
        .filter(ExoplanetCandidate.trandurh.isnot(None))
        .filter(ExoplanetCandidate.centroid_is_real.is_(False))
        .filter(_due(ExoplanetCandidate.centroid_attempted_at, ExoplanetCandidate.centroid_status, retry_after_days))
        .order_by(ExoplanetCandidate.centroid_attempted_at.asc().nullsfirst(), ExoplanetCandidate.toi_id.asc())
        .limit(limit)
        .all()
    )

    results = []
    for cand in candidates:
        try:
            rate_limiter.acquire()
            results.append(_sync_one_centroid(db, cand, measure, epoch_lookup))
        except Exception as e:  # TransientCatalogError or anything unexpected: isolate this target
            _record_error(db, cand, "centroid_attempted_at", "centroid_status", e)
            results.append({"toi_id": cand.toi_id, "status": S.ERROR, "error": type(e).__name__})

    return {
        "attempted": len(results),
        S.MEASURED: sum(1 for r in results if r["status"] == S.MEASURED),
        "errors": sum(1 for r in results if r["status"] == S.ERROR),
        "results": results,
    }


def _sync_one_centroid(db, cand, measure, epoch_lookup) -> dict:
    cand.centroid_attempted_at = datetime.utcnow()
    # tranmid is already stored by ingestion; only hit NASA TAP when it's missing. The
    # fallback is filtered to THIS planet (a star can host several TOIs with different epochs).
    epoch_bjd = cand.tranmid
    if epoch_bjd is None:
        epoch_row = epoch_lookup(cand.tic_id, toi_id=cand.toi_id)
        epoch_bjd = epoch_row.get("pl_tranmid") if epoch_row else None
    if epoch_bjd is None:
        cand.centroid_status = S.NO_EPOCH
        db.commit()
        return {"toi_id": cand.toi_id, "status": S.NO_EPOCH}

    result = measure(tic_id=cand.tic_id, period_days=cand.orbper,
                     duration_hours=cand.trandurh, epoch_bjd=epoch_bjd)
    if result is None:
        cand.centroid_status = S.NO_MEASUREMENT
        db.commit()
        return {"toi_id": cand.toi_id, "status": S.NO_MEASUREMENT}

    cand.centroid_shift_max = result.offset_arcsec
    cand.centroid_significance_sigma = result.significance_sigma
    # None, not False, when the depth needed for the implied offset could not be measured:
    # "the dip test could not run" must not read as "measured clean".
    cand.has_centroid_dip = result.is_dip if result.implied_offset_arcsec is not None else None
    cand.centroid_implied_offset_arcsec = result.implied_offset_arcsec
    cand.centroid_implied_offset_err_arcsec = result.implied_offset_err_arcsec
    cand.centroid_is_real = True
    cand.centroid_status = S.MEASURED
    cand.centroid_sector = result.sector
    cand.centroid_computed_at = datetime.utcnow()
    cand.centroid_dx_json = result.dx_binned
    cand.centroid_dy_json = result.dy_binned
    db.commit()
    logger.info("TOI-%s centroid offset %.4f arcsec (%.1f sigma, %s events)",
                cand.toi_id, result.offset_arcsec, result.significance_sigma, result.n_events)
    return {
        "toi_id": cand.toi_id, "status": S.MEASURED, "offset_arcsec": result.offset_arcsec,
        "significance_sigma": result.significance_sigma, "sector": result.sector,
        "n_events": result.n_events, "n_sectors": result.n_sectors,
        "implied_offset_arcsec": result.implied_offset_arcsec, "is_dip": cand.has_centroid_dip,
    }


# ------------------------------------------------------------------------- spectroscopy

def sync_real_spectroscopy(
    db: Session, limit: int = 100, retry_after_days: int = 90,
    lookup: Callable = fetch_real_spectroscopy, rate_limiter=None,
) -> dict:
    rate_limiter = rate_limiter or NullRateLimiter()
    stars = (
        db.query(HostStar)
        .filter(HostStar.spectroscopy_is_real.is_(False))
        .filter(HostStar.ra.isnot(None), HostStar.dec.isnot(None))
        .filter(_due(HostStar.spectroscopy_attempted_at, None, retry_after_days))
        .order_by(HostStar.spectroscopy_attempted_at.asc().nullsfirst(), HostStar.hostname.asc())
        .limit(limit)
        .all()
    )

    results = []
    for star in stars:
        try:
            rate_limiter.acquire()
            star.spectroscopy_attempted_at = datetime.utcnow()
            spec = lookup(star.ra, star.dec)
            if not spec:
                db.commit()
                results.append({"hostname": star.hostname, "status": S.NO_MATCH})
                continue
            # A matched host is marked real, so EVERY spectroscopy field must now be real or
            # empty: seed_db.py's fabricated demo values (teff_spec = Gaia Teff + jitter, rad_spec
            # 100% invented) would otherwise ride along behind spectroscopy_is_real=True.
            star.teff_spec = spec.teff_spec
            star.fe_h = spec.fe_h
            star.rad_spec = None
            star.alpha_fe = None
            star.spectroscopy_is_real = True
            star.spectroscopy_source = f"APOGEE-2 DR17 (VizieR {APOGEE_DR17_CATALOG})"
            star.spectroscopy_computed_at = datetime.utcnow()
            db.commit()
            results.append({"hostname": star.hostname, "status": S.MATCHED,
                            "teff_spec": spec.teff_spec, "fe_h": spec.fe_h})
        except Exception as e:
            # Host rows have no status column; the attempt timestamp alone records the error,
            # so back it off by the short retry window instead of the long one.
            db.rollback()
            star.spectroscopy_attempted_at = datetime.utcnow() - timedelta(days=retry_after_days - ERROR_RETRY_AFTER_DAYS)
            db.commit()
            logger.warning("Spectroscopy sync error for %s (%s): %s", star.hostname, type(e).__name__, e)
            results.append({"hostname": star.hostname, "status": S.ERROR, "error": type(e).__name__})

    return {
        "attempted": len(results),
        S.MATCHED: sum(1 for r in results if r["status"] == S.MATCHED),
        "errors": sum(1 for r in results if r["status"] == S.ERROR),
        "results": results,
    }


# ------------------------------------------------------------------ light-curve vetting

def sync_real_lightcurve_vetting(
    db: Session, limit: int = 10, retry_after_days: int = 90, fetch: Optional[Callable] = None,
    vetter=None, rate_limiter=None,
) -> dict:
    """Vets each pending candidate against its REAL SPOC TESS light curve and stores the
    result. This is what replaces classifying the /transit_pipeline simulation."""
    from app.ml.lightcurve_vetter import fetch_tess_lightcurve, lightcurve_vetter

    rate_limiter = rate_limiter or NullRateLimiter()
    fetch = fetch or fetch_tess_lightcurve
    vetter = vetter or lightcurve_vetter
    if not vetter.available:
        return {"attempted": 0, S.VETTED: 0, "errors": 0, "results": [],
                "skipped": f"model unavailable: {vetter.load_error}"}

    candidates = (
        db.query(ExoplanetCandidate)
        .filter(ExoplanetCandidate.tic_id.isnot(None))
        .filter(ExoplanetCandidate.orbper.isnot(None), ExoplanetCandidate.trandurh.isnot(None))
        .filter(or_(ExoplanetCandidate.lc_vetting_status.is_(None), ExoplanetCandidate.lc_vetting_status != S.VETTED))
        .filter(_due(ExoplanetCandidate.lc_vetting_attempted_at, ExoplanetCandidate.lc_vetting_status, retry_after_days))
        .order_by(ExoplanetCandidate.lc_vetting_attempted_at.asc().nullsfirst(), ExoplanetCandidate.toi_id.asc())
        .limit(limit)
        .all()
    )

    results = []
    for cand in candidates:
        try:
            rate_limiter.acquire()
            results.append(_vet_one(db, cand, fetch, vetter))
        except Exception as e:
            _record_error(db, cand, "lc_vetting_attempted_at", "lc_vetting_status", e)
            results.append({"toi_id": cand.toi_id, "status": S.ERROR, "error": type(e).__name__})
    return {"attempted": len(results), S.VETTED: sum(1 for r in results if r["status"] == S.VETTED),
            "errors": sum(1 for r in results if r["status"] == S.ERROR), "results": results}


def _vet_one(db, cand, fetch, vetter) -> dict:
    cand.lc_vetting_attempted_at = datetime.utcnow()
    if cand.tranmid is None:
        cand.lc_vetting_status = S.NO_EPOCH
        db.commit()
        return {"toi_id": cand.toi_id, "status": S.NO_EPOCH}
    lc = fetch(cand.tic_id)
    if lc is None:
        cand.lc_vetting_status = S.NO_LIGHTCURVE
        db.commit()
        return {"toi_id": cand.toi_id, "status": S.NO_LIGHTCURVE}
    time_arr, flux, sectors = lc
    host = cand.host
    stellar = {
        "teff": host.teff if host else None, "rstar": host.rad if host else None,
        "depth_ppm": cand.trandep,
        "j_mag": host.j_mag if host else None, "k_mag": host.k_mag if host else None,
        "g_mag": host.g_mag if host else None, "r_mag": host.r_mag if host else None,
    }
    out = vetter.vet(time_arr, flux, cand.orbper, cand.tranmid - BTJD_OFFSET, cand.trandurh, stellar)
    if out.get("model_status") != "trained":
        cand.lc_vetting_status = S.UNUSABLE
        db.commit()
        return {"toi_id": cand.toi_id, "status": S.UNUSABLE}
    out["sectors"] = sectors
    out["input_source"] = "real_tess_spoc_2min"
    cand.lc_vetting_json = out
    cand.lc_vetting_status = S.VETTED
    cand.lc_vetting_at = datetime.utcnow()
    db.commit()
    return {"toi_id": cand.toi_id, "status": S.VETTED, "best_class": out["best_class"],
            "confidence": out["confidence"], "sectors": sectors}
