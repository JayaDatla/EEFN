import requests
import io
import logging
import pandas as pd
import numpy as np
import uuid
import time
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from app.db.models import HostStar, ExoplanetCandidate, CatalogSource, MeasurementHistory, AgreementMetrics, MLPrediction, PipelineRun, DispositionChangeEvent
from app.ml.predict import predictor
from app.science.health import compute_health_score_from_values, HEALTH_SCORE_VERSION
from app.science.density import compute_transit_density_cgs, compute_gaia_density_cgs, compute_density_discrepancy_sigma
from app.science.radius import compute_derived_planet_radius_earth, compute_derived_planet_radius_uncertainty
from app.pipeline import catalog_registry as catalog
from app.pipeline.rate_limiter import NullRateLimiter

logger = logging.getLogger(__name__)

NASA_TAP_URL = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"
CDS_XMATCH_URL = "http://cdsxmatch.u-strasbg.fr/xmatch/api/v1/sync"

def post_with_retry(url: str, data: dict, files: dict, rate_limiter, max_retries: int = 3, backoff: float = 6.0, timeout: float = 10.0):
    """
    Asynchronous-style retry wrapper with strict 10s timeout to prevent thread blocking.
    Every attempt -- including retries -- goes through the shared rate limiter first
    (UPGRADE_PLAN.md D.2), since a retry storm across concurrent pipeline runs is
    exactly the scenario that gets a project's IP banned from CDS.
    """
    for attempt in range(max_retries):
        try:
            rate_limiter.acquire()
            r = requests.post(url, data=data, files=files, timeout=timeout)
            if r.status_code == 200 and "Too many jobs are being processed" in r.text:
                logger.warning("CDS rate limit hit. Retrying in %s seconds (attempt %s/%s).", backoff, attempt + 1, max_retries)
                time.sleep(backoff)
                continue
            return r
        except Exception as e:
            logger.warning("Query attempt %s failed: %s", attempt + 1, e)
            time.sleep(backoff / 2.0)
    return None


def xmatch_catalog(spec, csv_data: str, rate_limiter, columns: list) -> pd.DataFrame:
    """
    Shared CDS X-Match fetch/retry/dedupe logic for a `catalog_registry.CatalogSpec`
    (UPGRADE_PLAN.md F.5) -- the Gaia Source/AstroParams calls above predate this
    helper and are left as-is to avoid an unrelated diff, but 2MASS/Pan-STARRS use it
    so a third recoverable catalog doesn't mean a third copy of this same block.
    Returns an empty (but correctly-columned) DataFrame on any failure, matching the
    existing graceful-degradation behavior for the other catalogs.
    """
    try:
        files = {'cat1': ('data.csv', csv_data)}
        payload = {
            'request': 'xmatch',
            'distMaxArcsec': spec.distance_arcsec,
            'RESPONSEFORMAT': 'csv',
            'cat2': spec.vizier_table,
            'colRA1': 'ra',
            'colDec1': 'dec',
        }
        r = post_with_retry(CDS_XMATCH_URL, data=payload, files=files, rate_limiter=rate_limiter)
        if r is None or r.status_code != 200 or "Too many jobs are being processed" in r.text:
            logger.warning("%s xmatch failed/timed out.", spec.name)
            return pd.DataFrame(columns=columns)
        df = pd.read_csv(io.StringIO(r.text))
        df_clean = df.sort_values("angDist").drop_duplicates(subset=["toi"], keep="first")
        logger.info("Matched %s stars in %s.", len(df_clean), spec.name)
        return df_clean[[c for c in columns if c in df_clean.columns]]
    except Exception as e:
        logger.warning("%s xmatch exception: %s.", spec.name, e)
        return pd.DataFrame(columns=columns)


def record_measurement(db: Session, candidate: ExoplanetCandidate, source: CatalogSource, parameter_name: str,
                        value, error_upper=None, error_lower=None):
    """
    Append-only provenance ledger (UPGRADE_PLAN.md D.1): every value ingestion pulls
    from a catalog gets one MeasurementHistory row, so a candidate's evidence card can
    show every source's value side by side with a query timestamp. A new row is only
    written when the value actually changed since the last recorded one for this
    (candidate, source, parameter) triple -- otherwise re-running the pipeline daily
    against unchanged upstream data would grow this table unbounded for no reason.
    """
    if value is None:
        return
    last = (
        db.query(MeasurementHistory)
        .filter(
            MeasurementHistory.candidate_id == candidate.id,
            MeasurementHistory.source_id == source.id,
            MeasurementHistory.parameter_name == parameter_name,
        )
        .order_by(MeasurementHistory.measured_at.desc())
        .first()
    )
    if last is not None and last.value == value:
        return
    db.add(MeasurementHistory(
        candidate_id=candidate.id,
        source_id=source.id,
        parameter_name=parameter_name,
        value=value,
        error_upper=error_upper,
        error_lower=error_lower,
        measured_at=datetime.utcnow(),
    ))


def propagate_proper_motion(ra_deg: float, dec_deg: float, pm_ra_mas: float = 0.0, pm_dec_mas: float = 0.0, dt_years: float = 16.0) -> tuple:
    """
    Propagate J2000 coordinates to target catalog epoch (Gaia DR3 J2016.0).
    """
    if pm_ra_mas is None: pm_ra_mas = 0.0
    if pm_dec_mas is None: pm_dec_mas = 0.0
    
    d_ra_deg = (pm_ra_mas * dt_years) / (3600.0 * 1000.0)
    d_dec_deg = (pm_dec_mas * dt_years) / (3600.0 * 1000.0)
    
    return ra_deg + d_ra_deg, dec_deg + d_dec_deg

def _finalize_pipeline_run(db: Session, run: Optional[PipelineRun], status: str, started: float,
                            targets_processed: int = 0, failures: Optional[list] = None,
                            error_detail: Optional[str] = None):
    """Stamp final status/timing on the PipelineRun row (UPGRADE_PLAN.md D.2), if one
    was provided -- callers that don't need history tracking (e.g. ad hoc scripts,
    most existing tests) can pass run=None and this is a no-op."""
    if run is None:
        return
    run.status = status
    run.targets_processed = targets_processed
    run.failures = failures or []
    run.error_detail = error_detail
    run.finished_at = datetime.utcnow()
    run.duration_seconds = round(time.monotonic() - started, 3)
    db.commit()


def ingest_and_fuse_data(db: Session, limit: int = 100, rate_limiter=None,
                          pipeline_run: Optional[PipelineRun] = None) -> dict:
    """
    Ingest data from NASA Exoplanet Archive, cross-match with Gaia DR3, 2MASS, Pan-STARRS, and Spectroscopy,
    compute catalog agreement metrics, transit density invariants, health grades (A-F), and run ML models.

    `rate_limiter` defaults to a no-op (NullRateLimiter) so existing tests and ad hoc
    scripts don't need a live Redis just to call this function -- the Arq worker task
    (app/worker.py) is the one production caller and always passes a real
    Redis-backed TokenBucketRateLimiter built from settings (UPGRADE_PLAN.md D.2).

    `pipeline_run`, if given, is a PipelineRun row (already committed with
    status="running") that gets stamped with final status/targets/failures/duration on
    every exit path, including early-return error paths -- see _finalize_pipeline_run.

    Idempotent, not yet resumable (UPGRADE_PLAN.md D.2 asks for both): re-running this
    against an already-populated DB is safe (every write is an upsert, C.10) and won't
    duplicate data, but a run killed mid-loop restarts from the first target on its
    next invocation rather than skipping the ones it already committed in the killed
    run. True resumability would need per-run, per-target progress tracked on
    PipelineRun (or a resumable target cursor) -- not implemented here; disclosed as a
    known gap rather than silently claimed.
    """
    rate_limiter = rate_limiter or NullRateLimiter()
    started = time.monotonic()
    logger.info("Starting ExoFusion-Net v2 ingestion pipeline for limit=%s...", limit)

    # 1. Fetch from NASA Exoplanet Archive TOI table
    nasa_query = f"""
    SELECT TOP {limit}
        toi, tid, tfopwg_disp, ra, dec,
        st_tmag, st_teff, st_tefferr1, st_tefferr2,
        st_rad, st_raderr1, st_raderr2,
        st_logg, st_dist, st_disterr1, st_disterr2,
        pl_orbper, pl_trandurh, pl_trandep, pl_trandeperr1, pl_trandeperr2,
        pl_rade, pl_radeerr1, pl_radeerr2, pl_insol, pl_eqt, pl_tranmid
    FROM toi
    WHERE tfopwg_disp IN ('CP', 'KP', 'FP', 'FA', 'PC')
    ORDER BY toi+0 ASC
    """
    # `toi+0` forces numeric ordering. NASA's TAP service sorts a bare `ORDER BY toi ASC`
    # lexically (verified live: "1000.01" < "101.01" < "1010.01" ...), so a limited/
    # incremental sync using plain `toi ASC` silently skips most real low-numbered TOIs
    # in the 100s-900s range in favor of the entire 1000-9999 block sorting first --
    # e.g. TOI-104.01 never got re-processed by any `limit`-bounded sync while its
    # numeric neighbors 101-103/105+ did, purely because of where "104.01" fell in
    # string sort order. Found while investigating why a full re-sync didn't reach
    # every existing candidate.

    params = {"query": nasa_query, "format": "json"}

    try:
        rate_limiter.acquire()
        r_nasa = requests.get(NASA_TAP_URL, params=params, timeout=12.0)
        if r_nasa.status_code != 200:
            detail = f"NASA TAP error: {r_nasa.text}"
            _finalize_pipeline_run(db, pipeline_run, "error", started, error_detail=detail)
            return {"status": "error", "detail": detail}

        raw_data = r_nasa.json()
        if not raw_data:
            _finalize_pipeline_run(db, pipeline_run, "success", started, targets_processed=0)
            return {"status": "success", "detail": "No candidates found to ingest"}

        df_resolved = pd.DataFrame(raw_data)
        logger.info("Fetched %s candidates from NASA Archive.", len(df_resolved))
    except Exception as e:
        detail = f"NASA Ingestion Exception: {str(e)}"
        _finalize_pipeline_run(db, pipeline_run, "error", started, error_detail=detail)
        return {"status": "error", "detail": detail}

    # Convert dataframe to CSV string for upload to CDS X-Match
    csv_buf = io.StringIO()
    df_resolved.to_csv(csv_buf, index=False)
    csv_data = csv_buf.getvalue()

    # 2. Cross-match with Gaia DR3 Source Catalog
    logger.info("Cross-matching with Gaia DR3 Source Catalog (%s)...", catalog.GAIA_SOURCE.version)
    payload_gaia = {
        'request': 'xmatch',
        'distMaxArcsec': catalog.GAIA_SOURCE.distance_arcsec,
        'RESPONSEFORMAT': 'csv',
        'cat2': catalog.GAIA_SOURCE.vizier_table,
        'colRA1': 'ra',
        'colDec1': 'dec'
    }

    query_failed = False
    try:
        files = {'cat1': ('data.csv', csv_data)}
        r_gaia = post_with_retry(CDS_XMATCH_URL, data=payload_gaia, files=files, rate_limiter=rate_limiter)
        if r_gaia is None or r_gaia.status_code != 200 or "Too many jobs are being processed" in r_gaia.text:
            logger.warning("Gaia Source xmatch failed/timed out. Flagging query_failed = True.")
            df_gaia_clean = pd.DataFrame(columns=['toi', 'Source', 'Plx', 'e_Plx', 'RUWE', 'Gmag', 'BPmag', 'RPmag', 'PM', 'pmRA', 'pmDE'])
            query_failed = True
        else:
            df_gaia = pd.read_csv(io.StringIO(r_gaia.text))
            df_gaia_clean = df_gaia.sort_values("angDist").drop_duplicates(subset=["toi"], keep="first")
            logger.info("Matched %s stars in Gaia DR3 Source Catalog.", len(df_gaia_clean))
    except Exception as e:
        logger.warning("Gaia Source xmatch exception: %s. Flagging query_failed.", e)
        df_gaia_clean = pd.DataFrame(columns=['toi', 'Source', 'Plx', 'e_Plx', 'RUWE', 'Gmag', 'BPmag', 'RPmag', 'PM', 'pmRA', 'pmDE'])
        query_failed = True

    # 3. Cross-match with Gaia DR3 Astrophysical Parameters
    logger.info("Cross-matching with Gaia DR3 Astrophysical Parameters (%s)...", catalog.GAIA_ASTROPARAMS.version)
    payload_param = {
        'request': 'xmatch',
        'distMaxArcsec': catalog.GAIA_ASTROPARAMS.distance_arcsec,
        'RESPONSEFORMAT': 'csv',
        'cat2': catalog.GAIA_ASTROPARAMS.vizier_table,
        'colRA1': 'ra',
        'colDec1': 'dec'
    }

    try:
        files = {'cat1': ('data.csv', csv_data)}
        r_param = post_with_retry(CDS_XMATCH_URL, data=payload_param, files=files, rate_limiter=rate_limiter)
        if r_param is None or r_param.status_code != 200 or "Too many jobs are being processed" in r_param.text:
            logger.warning("Gaia Param xmatch failed/timed out.")
            df_param_clean = pd.DataFrame(columns=['toi', 'Source', 'Teff', 'b_Teff', 'B_Teff', 'logg', 'b_logg', 'B_logg', 'Dist', 'b_Dist', 'B_Dist', 'Rad', 'b_Rad', 'B_Rad', 'Rad-Flame', 'Mass-Flame', 'Lum-Flame', 'Age-Flame'])
        else:
            df_param = pd.read_csv(io.StringIO(r_param.text))
            df_param_clean = df_param.sort_values("angDist").drop_duplicates(subset=["toi"], keep="first")
            logger.info("Matched %s stars in Gaia DR3 Astrophysical Parameters.", len(df_param_clean))
    except Exception as e:
        df_param_clean = pd.DataFrame(columns=['toi', 'Source', 'Teff', 'b_Teff', 'B_Teff', 'logg', 'b_logg', 'B_logg', 'Dist', 'b_Dist', 'B_Dist', 'Rad', 'b_Rad', 'B_Rad', 'Rad-Flame', 'Mass-Flame', 'Lum-Flame', 'Age-Flame'])

    # 3b/3c. Cross-match with 2MASS and Pan-STARRS (UPGRADE_PLAN.md F.5 -- recoverable
    # catalogs 4 and 5 of 7, ported from scratch/download_real_sample_data.py's working
    # CDS X-Match calls into the live pipeline, following the exact same
    # fetch/retry/rate-limit/fallback pattern as the Gaia calls above).
    df_2mass_clean = xmatch_catalog(catalog.TWO_MASS, csv_data, rate_limiter,
                                     ['toi', 'Jmag', 'e_Jmag', 'Hmag', 'e_Hmag', 'Kmag', 'e_Kmag'])
    df_ps_clean = xmatch_catalog(catalog.PAN_STARRS, csv_data, rate_limiter,
                                  ['toi', 'gmag', 'e_gmag', 'rmag', 'e_rmag', 'imag', 'e_imag',
                                   'zmag', 'e_zmag', 'ymag', 'e_ymag'])

    # 4. Merge catalogs in Pandas
    cols_gaia = ['toi', 'Source', 'Plx', 'e_Plx', 'RUWE', 'Gmag', 'BPmag', 'RPmag', 'PM', 'pmRA', 'pmDE']
    df_gaia_sub = df_gaia_clean[[c for c in cols_gaia if c in df_gaia_clean.columns]].copy()
    df_gaia_sub.rename(columns={'Source': 'source_id'}, inplace=True)

    cols_param = ['toi', 'Source', 'Teff', 'b_Teff', 'B_Teff', 'logg', 'b_logg', 'B_logg', 'Dist', 'b_Dist', 'B_Dist', 'Rad', 'b_Rad', 'B_Rad', 'Rad-Flame', 'Mass-Flame', 'Lum-Flame', 'Age-Flame']
    df_param_sub = df_param_clean[[c for c in cols_param if c in df_param_clean.columns]].copy()
    df_param_sub.rename(columns={'Source': 'source_id_param'}, inplace=True)

    df_resolved['toi'] = df_resolved['toi'].astype(str)
    df_gaia_sub['toi'] = df_gaia_sub['toi'].astype(str)
    df_param_sub['toi'] = df_param_sub['toi'].astype(str)
    df_2mass_clean = df_2mass_clean.copy()
    df_2mass_clean['toi'] = df_2mass_clean['toi'].astype(str)
    df_ps_clean = df_ps_clean.copy()
    df_ps_clean['toi'] = df_ps_clean['toi'].astype(str)

    df_merged = pd.merge(df_resolved, df_gaia_sub, on='toi', how='left')
    df_merged = pd.merge(df_merged, df_param_sub, on='toi', how='left')
    df_merged = pd.merge(df_merged, df_2mass_clean, on='toi', how='left')
    df_merged = pd.merge(df_merged, df_ps_clean, on='toi', how='left')
    df_merged = df_merged.replace({np.nan: None})

    # 5. Populate relational database tables
    sources_dict = {}
    catalogs_used = ["NASA Exoplanet Archive", "Gaia DR3", "TOI Catalog", "2MASS Photometry", "Pan-STARRS", "Spectroscopy Survey"]
    for name in catalogs_used:
        # Version comes from the catalog registry (UPGRADE_PLAN.md D.2) for catalogs
        # that are actually registered; "2.0" is a placeholder for the remaining
        # sources that don't have live ingestion yet (2MASS/Spectroscopy -- A.13/F.5/F.7).
        version = catalog.ALL_CATALOGS[name].version if name in catalog.ALL_CATALOGS else "2.0"
        src = db.query(CatalogSource).filter(CatalogSource.name == name).first()
        if not src:
            src = CatalogSource(name=name, version=version, last_sync=datetime.utcnow())
            db.add(src)
        else:
            src.version = version
            src.last_sync = datetime.utcnow()
        db.commit()
        db.refresh(src)
        sources_dict[name] = src

    if pipeline_run is not None:
        pipeline_run.catalogs_used = catalogs_used
        pipeline_run.catalog_versions = {name: sources_dict[name].version for name in catalogs_used}
        db.commit()

    records_processed = 0
    failures = []

    for idx, row in df_merged.iterrows():
        hostname = f"TIC {row['tid']}"
        star = db.query(HostStar).filter(HostStar.hostname == hostname).first()
        
        # Calculate proper motion position update
        pm_ra_val = row['pmRA'] if row.get('pmRA') is not None else 0.0
        pm_dec_val = row['pmDE'] if row.get('pmDE') is not None else 0.0
        ra_j2016, dec_j2016 = propagate_proper_motion(row['ra'], row['dec'], pm_ra_val, pm_dec_val)

        # Upsert HostStar: a re-run against updated NASA/Gaia data must refresh existing
        # rows, not just skip them once created (UPGRADE_PLAN.md A.10/C.10).
        if not star:
            star = HostStar(hostname=hostname)
            db.add(star)

        star.ra = ra_j2016
        star.dec = dec_j2016
        star.parallax = row['Plx']
        star.distance = row['Dist']
        star.teff = row['Teff']
        star.logg = row['logg']
        star.rad = row['Rad']
        star.mass = row['Mass-Flame']
        # TOI-table (TIC-derived) values, kept beside the Gaia ones so the disagreement features
        # can be recomputed at serving time from the same two sources used in training.
        star.toi_teff = row.get('st_teff')
        star.toi_rad = row.get('st_rad')
        star.toi_dist = row.get('st_dist')
        star.toi_logg = row.get('st_logg')
        star.pm_ra = pm_ra_val
        star.pm_dec = pm_dec_val
        star.ruwe = row['RUWE']
        # Gaia DR3 source_id (UPGRADE_PLAN.md G.2) -- fetched by the Gaia Source
        # X-Match since C.1 but never persisted until now; int() guards against pandas
        # upcasting this column to float64 when some rows in the batch have no match.
        star.gaia_dr3_source_id = int(row['source_id']) if row.get('source_id') is not None else None
        # 2MASS + Pan-STARRS photometry (UPGRADE_PLAN.md F.5 -- 3/7 -> 5/7 live catalogs).
        star.j_mag = row.get('Jmag')
        star.h_mag = row.get('Hmag')
        star.k_mag = row.get('Kmag')
        star.g_mag = row.get('gmag')
        star.r_mag = row.get('rmag')
        star.i_mag = row.get('imag')
        star.z_mag = row.get('zmag')
        star.y_mag = row.get('ymag')
        db.commit()
        db.refresh(star)

        pl_name = f"TOI-{row['toi']}"
        cand = db.query(ExoplanetCandidate).filter(ExoplanetCandidate.pl_name == pl_name).first()
        
        # Calculate transit density and ExoFusion-Net v2 Evidence Health Grade
        st_teff = row.get('st_teff')
        gaia_teff = row.get('Teff')
        st_rad = row.get('st_rad')
        gaia_rad = row.get('Rad')
        st_dist = row.get('st_dist')
        gaia_dist = row.get('Dist')
        trandep = row.get('pl_trandep')
        trandurh = row.get('pl_trandurh')
        orbper = row.get('pl_orbper')
        pl_rade = row.get('pl_rade')
        ruwe_val = row.get('RUWE')

        # Transit-derived vs Gaia-evolutionary stellar density -- see app.science.density
        # for the full Seager & Mallen-Ornelas (2003) derivation (C.4: the previous
        # formula never used the orbital period and did not resolve to g/cm^3).
        density_transit = compute_transit_density_cgs(period_days=orbper, duration_hours=trandurh)
        if density_transit is not None:
            density_transit = round(density_transit, 3)

        density_gaia = compute_gaia_density_cgs(mass_solar=row.get('Mass-Flame'), radius_solar=gaia_rad)
        if density_gaia is not None:
            density_gaia = round(density_gaia, 3)

        density_sigma = compute_density_discrepancy_sigma(
            density_transit=density_transit,
            density_gaia=density_gaia,
            radius_solar=gaia_rad,
            radius_err_lower=row.get('b_Rad'),
            radius_err_upper=row.get('B_Rad'),
        )
        if density_sigma is not None:
            density_sigma = round(density_sigma, 2)
        
        # Recalculated planet size & unphysical check -- shared with predict.py via
        # app.science.radius so the two can never compute a different derived radius
        # for the same inputs (UPGRADE_PLAN.md E.3).
        # None when there is no Gaia radius. The previous `pl_rade or 1.0` fallback stored the
        # catalog's own radius (or an invented 1.0) as the "Gaia-derived" one, so a star Gaia never
        # characterised read as "perfect agreement" (derived_rp_diff = 0) and could never trip the
        # unphysical-radius check. Missing stays missing.
        calc_rp_gaia = compute_derived_planet_radius_earth(gaia_rad, trandep)

        trandep_err1, trandep_err2 = row.get('pl_trandeperr1'), row.get('pl_trandeperr2')
        trandep_err = (abs(trandep_err1) + abs(trandep_err2)) / 2.0 if trandep_err1 is not None and trandep_err2 is not None else None
        derived_rp_gaia_err = compute_derived_planet_radius_uncertainty(
            radius_solar=gaia_rad,
            radius_err_lower=row.get('b_Rad'),
            radius_err_upper=row.get('B_Rad'),
            transit_depth_ppm=trandep,
            transit_depth_err=trandep_err,
        )
        if derived_rp_gaia_err is not None:
            derived_rp_gaia_err = round(derived_rp_gaia_err, 3)

        # None when either side is missing -- never 0.0. A prior version of this
        # function used `if a and b else 0.0`, which made "Gaia never matched this
        # star" render identically to "measured, perfect agreement" everywhere this
        # value is displayed (fusion/compare pages, evidence card). 0.0 is a real,
        # specific claim ("we measured both and they match exactly"); it must never
        # stand in for "we don't have one of the two measurements to compare."
        # Mirrors predict.py's own diff() helper so the two code paths can't disagree
        # about what "missing" means.
        def diff(a, b):
            return abs(a - b) if a is not None and b is not None else None

        derived_rp_diff = diff(pl_rade, calc_rp_gaia)
        is_unphysical = bool(calc_rp_gaia is not None and calc_rp_gaia > 22.0)

        # Real catalog disagreements (also reused below for AgreementMetrics -- computed
        # once here so ingest.py and the health score can never see different numbers).
        teff_diff = diff(st_teff, gaia_teff)
        rad_diff = diff(st_rad, gaia_rad)
        dist_diff = diff(st_dist, gaia_dist)

        # Completeness: real fraction of the core stellar-parameter fields actually
        # populated for this candidate, not a hardcoded 1.0 (fixes part of A.10/C.10).
        completeness_fields = [st_teff, gaia_teff, st_rad, gaia_rad, st_dist, gaia_dist, ruwe_val]
        completeness_score = sum(1 for v in completeness_fields if v is not None) / len(completeness_fields)

        # Health Score (0-100): the one shared formula, see app.science.health (C.3).
        health_result = compute_health_score_from_values(
            teff_disagreement=teff_diff,
            rad_disagreement=rad_diff,
            dist_disagreement=dist_diff,
            ruwe=ruwe_val,
            is_unphysical_rp=is_unphysical,
            completeness_score=completeness_score,
            query_failed=query_failed,
        )
        h_score = health_result.score
        h_grade = health_result.grade

        # Upsert ExoplanetCandidate. Structural identity fields (host_id/tic_id/toi_id/
        # pl_name) are only ever set at creation; every science-derived field is
        # refreshed on every run so a disposition flip (e.g. PC -> FP) or an updated
        # catalog value actually reaches the DB on re-ingestion (A.10/C.10).
        is_new_candidate = cand is None
        if not cand:
            cand = ExoplanetCandidate(
                host_id=star.id,
                tic_id=int(row['tid']),
                toi_id=float(row['toi']),
                pl_name=pl_name,
                disposition=row['tfopwg_disp'],
            )
            db.add(cand)

        # UPGRADE_PLAN.md H.3.5: capture the real prior values before overwriting, so
        # a genuine transition (not a new candidate's first-ever value) can be logged
        # to disposition_change_events for the diff/"what changed" view.
        prev_disposition = cand.disposition if not is_new_candidate else None
        prev_health_grade = cand.health_grade if not is_new_candidate else None

        cand.disposition = row['tfopwg_disp']
        cand.orbper = row['pl_orbper']
        cand.rade = row['pl_rade']
        cand.rade_err_upper = row.get('pl_radeerr1')
        cand.rade_err_lower = row.get('pl_radeerr2')
        cand.trandep = row['pl_trandep']
        cand.trandurh = row['pl_trandurh']
        cand.insol = row['pl_insol']
        cand.eqt = row['pl_eqt']
        cand.tranmid = row.get('pl_tranmid')
        cand.density_transit = density_transit
        cand.density_gaia = density_gaia
        cand.density_discrepancy_sigma = density_sigma
        cand.health_score = h_score
        cand.health_grade = h_grade
        cand.health_score_version = health_result.version
        cand.query_failed = query_failed
        db.commit()
        db.refresh(cand)

        if not is_new_candidate:
            change_time = datetime.utcnow()
            if prev_disposition is not None and prev_disposition != cand.disposition:
                db.add(DispositionChangeEvent(
                    candidate_id=cand.id, toi_id=cand.toi_id, pl_name=cand.pl_name,
                    field_name="disposition", old_value=prev_disposition, new_value=cand.disposition,
                    changed_at=change_time,
                ))
            if prev_health_grade is not None and prev_health_grade != cand.health_grade:
                db.add(DispositionChangeEvent(
                    candidate_id=cand.id, toi_id=cand.toi_id, pl_name=cand.pl_name,
                    field_name="health_grade", old_value=prev_health_grade, new_value=cand.health_grade,
                    changed_at=change_time,
                ))
            db.commit()

        # Provenance ledger: one row per source per parameter, only on real change
        # (see record_measurement above; UPGRADE_PLAN.md D.1). TOI err1/err2 are
        # already +/- deltas around the value; Gaia FLAME b_*/B_* are asymmetric
        # absolute bounds around the value, not deltas -- both are stored as-is under
        # error_upper/error_lower, matching what each catalog actually publishes.
        toi_source = sources_dict["TOI Catalog"]
        gaia_source = sources_dict["Gaia DR3"]
        record_measurement(db, cand, toi_source, "stellar_teff", st_teff,
                            row.get('st_tefferr1'), row.get('st_tefferr2'))
        record_measurement(db, cand, gaia_source, "stellar_teff", gaia_teff,
                            row.get('B_Teff'), row.get('b_Teff'))
        record_measurement(db, cand, toi_source, "stellar_radius", st_rad,
                            row.get('st_raderr1'), row.get('st_raderr2'))
        record_measurement(db, cand, gaia_source, "stellar_radius", gaia_rad,
                            row.get('B_Rad'), row.get('b_Rad'))
        record_measurement(db, cand, toi_source, "distance", st_dist,
                            row.get('st_disterr1'), row.get('st_disterr2'))
        record_measurement(db, cand, gaia_source, "distance", gaia_dist,
                            row.get('B_Dist'), row.get('b_Dist'))

        # 2MASS + Pan-STARRS photometry provenance (UPGRADE_PLAN.md F.5).
        two_mass_source = sources_dict["2MASS Photometry"]
        pan_starrs_source = sources_dict["Pan-STARRS"]
        record_measurement(db, cand, two_mass_source, "j_mag", row.get('Jmag'), row.get('e_Jmag'), row.get('e_Jmag'))
        record_measurement(db, cand, two_mass_source, "h_mag", row.get('Hmag'), row.get('e_Hmag'), row.get('e_Hmag'))
        record_measurement(db, cand, two_mass_source, "k_mag", row.get('Kmag'), row.get('e_Kmag'), row.get('e_Kmag'))
        record_measurement(db, cand, pan_starrs_source, "g_mag", row.get('gmag'), row.get('e_gmag'), row.get('e_gmag'))
        record_measurement(db, cand, pan_starrs_source, "r_mag", row.get('rmag'), row.get('e_rmag'), row.get('e_rmag'))
        record_measurement(db, cand, pan_starrs_source, "i_mag", row.get('imag'), row.get('e_imag'), row.get('e_imag'))
        record_measurement(db, cand, pan_starrs_source, "z_mag", row.get('zmag'), row.get('e_zmag'), row.get('e_zmag'))
        record_measurement(db, cand, pan_starrs_source, "y_mag", row.get('ymag'), row.get('e_ymag'), row.get('e_ymag'))
        db.commit()

        metrics = db.query(AgreementMetrics).filter(AgreementMetrics.candidate_id == cand.id).first()
        if not metrics:
            metrics = AgreementMetrics(candidate_id=cand.id)
            db.add(metrics)

        metrics.teff_disagreement = teff_diff
        metrics.rad_disagreement = rad_diff
        metrics.dist_disagreement = dist_diff
        metrics.ruwe = ruwe_val
        metrics.derived_rp_diff = derived_rp_diff
        metrics.derived_rp_gaia = round(calc_rp_gaia, 3) if calc_rp_gaia is not None else None
        metrics.derived_rp_gaia_err = derived_rp_gaia_err
        metrics.is_unphysical_rp = is_unphysical
        metrics.completeness_score = completeness_score
        # (teff_diff or 0.0)/(rad_diff or 0.0): a missing measurement contributes no
        # disagreement to this score (same convention as app/science/health.py's
        # `or 0.0` handling) rather than crashing on None -- completeness_score is
        # the separate, correct place a missing catalog match is penalized.
        metrics.catalog_agreement_score = max(0.0, 1.0 - ((teff_diff or 0.0)/500.0 + (rad_diff or 0.0)/0.5)/2.0)
        db.commit()

        # Run model predictor
        try:
            predictor.predict_confirmation(cand.id, db)
            records_processed += 1
        except Exception as e:
            logger.error("Error predicting candidate %s: %s", cand.pl_name, e)
            failures.append({"target": cand.pl_name, "error": str(e)})

    logger.info("Ingestion completed. Processed and evaluated %s candidates.", records_processed)
    final_status = "success" if not failures else "partial_failure"
    _finalize_pipeline_run(db, pipeline_run, final_status, started,
                            targets_processed=records_processed, failures=failures)
    return {
        "status": "success",
        "records_processed": records_processed,
        "failures": failures,
        "detail": f"Successfully ingested {records_processed} candidate records with v2 Evidence Health Scoring."
    }

