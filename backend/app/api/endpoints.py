from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc
from typing import List, Dict, Any, Optional
from app.pipeline import sync_status as S
from app.db.session import get_db, SessionLocal
from app.db.models import ExoplanetCandidate, HostStar, AgreementMetrics, MLPrediction, CatalogSource, PipelineRun, DispositionChangeEvent
from pydantic import BaseModel
from datetime import datetime, date as date_type, timedelta
import json
import os
import uuid
import numpy as np
from arq.connections import ArqRedis, RedisSettings, create_pool
from arq.jobs import Job as ArqJob
from app.config import settings
from app.api.auth import require_api_key
from app.audit import build_candidate_profile
from app.science.tiers import compute_model_tier
from app.science.observability import compute_observability, compute_observability_batch, TargetSpec
from app.export import build_candidates_votable_bytes
from app.resolve import resolve_identifier
from app.ml.transit_pipeline import transit_pipeline
from app.ml.deep_learning_pipeline import dl_vetting_engine

from services.alert_engine import AlertEngine
from services.audit_timeline import EntityResolutionAudit, EvidenceTimeline

router = APIRouter()

_arq_pool: Optional[ArqRedis] = None

async def get_arq_pool() -> ArqRedis:
    """Lazily-created, process-wide Arq connection pool (UPGRADE_PLAN.md D.2)."""
    global _arq_pool
    if _arq_pool is None:
        _arq_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    return _arq_pool

# Schema structures for request/responses
class PlanetResponse(BaseModel):
    pl_name: str
    tic_id: Optional[int]
    toi_id: Optional[float]
    disposition: str
    orbper: Optional[float]
    rade: Optional[float]
    rade_err_upper: Optional[float] = None
    rade_err_lower: Optional[float] = None
    trandep: Optional[float]
    trandurh: Optional[float]
    insol: Optional[float]
    eqt: Optional[float]
    evidence_consistency_score: Optional[float] = None
    followup_priority_score: Optional[float] = None
    health_score: Optional[float] = None
    health_grade: Optional[str] = None
    model_tier: Optional[int] = None
    catalogs_available_count: Optional[int] = None
    catalogs_total: Optional[int] = None

    class Config:
        from_attributes = True

class StarResponse(BaseModel):
    hostname: str
    ra: float
    dec: float
    parallax: Optional[float]
    distance: Optional[float]
    teff: Optional[float]
    logg: Optional[float]
    rad: Optional[float]
    mass: Optional[float]

class MetricsResponse(BaseModel):
    # Optional, not defaulted: None means "one catalog never matched this star,"
    # a genuinely different claim from 0.0 ("matched, and the values agree exactly").
    teff_disagreement: Optional[float]
    rad_disagreement: Optional[float]
    dist_disagreement: Optional[float]
    ruwe: Optional[float]
    derived_rp_diff: Optional[float]
    derived_rp_gaia: Optional[float] = None
    derived_rp_gaia_err: Optional[float] = None
    is_unphysical_rp: bool
    completeness_score: float
    catalog_agreement_score: float

class PredictionResponse(BaseModel):
    evidence_consistency_score: float
    followup_priority_score: float
    feature_importance: Optional[Dict[str, float]]
    calculated_at: datetime

class ModelTierResponse(BaseModel):
    tier: int
    tier_name: str
    catalogs_available: List[str]
    catalogs_missing: List[str]
    catalogs_total: int
    coverage_fraction: float

class HealthBreakdownResponse(BaseModel):
    score: float
    grade: str
    version: str
    factors: Dict[str, float]

class CandidateProfileResponse(BaseModel):
    planet: PlanetResponse
    star: StarResponse
    sources: List[str]
    measurement_history: Dict[str, Any]
    agreement_metrics: MetricsResponse
    prediction: PredictionResponse
    model_tier: ModelTierResponse
    health: HealthBreakdownResponse
    real_observations: Dict[str, Any] = {}
    data_quality: Dict[str, Any] = {}

_CANDIDATE_SORT_FIELDS = {
    "toi_id": ExoplanetCandidate.toi_id,
    "tic_id": ExoplanetCandidate.tic_id,
    "health_score": ExoplanetCandidate.health_score,
    "health_grade": ExoplanetCandidate.health_grade,
    "evidence_consistency_score": MLPrediction.evidence_consistency_score,
    "followup_priority_score": MLPrediction.followup_priority_score,
}


@router.get("/candidates", response_model=List[PlanetResponse])
def get_candidates(
    response: Response,
    disposition: Optional[str] = None,
    health_grade: Optional[str] = None,
    min_prob: Optional[float] = None,
    sort_by: str = Query("toi_id"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Server-side pagination/filtering/sorting (UPGRADE_PLAN.md D.3) -- the previous
    version pulled up to `limit` rows unordered and did an extra per-row MLPrediction
    query (N+1), which doesn't scale to the full ~7,000-row TOI table (H.4 notes the
    frontend needs a virtualized table backed by real server-side paging, not a
    client-side slice of a fixed-size pull). The total match count (pre-pagination) is
    returned via the X-Total-Count header so a client can build page controls.
    """
    if sort_by not in _CANDIDATE_SORT_FIELDS:
        raise HTTPException(status_code=400, detail=f"sort_by must be one of: {', '.join(_CANDIDATE_SORT_FIELDS)}")

    query = db.query(ExoplanetCandidate, MLPrediction, HostStar).outerjoin(
        MLPrediction, MLPrediction.candidate_id == ExoplanetCandidate.id
    ).outerjoin(
        HostStar, HostStar.id == ExoplanetCandidate.host_id
    )

    if disposition:
        query = query.filter(ExoplanetCandidate.disposition == disposition)
    if health_grade:
        query = query.filter(ExoplanetCandidate.health_grade == health_grade)
    if min_prob is not None:
        # A candidate with no prediction yet can't satisfy a minimum-probability
        # threshold, so this behaves like an inner join for that case.
        query = query.filter(MLPrediction.evidence_consistency_score >= min_prob)

    response.headers["X-Total-Count"] = str(query.count())

    sort_col = _CANDIDATE_SORT_FIELDS[sort_by]
    order_fn = desc if sort_dir == "desc" else asc
    rows = query.order_by(order_fn(sort_col)).offset(offset).limit(limit).all()

    results = []
    for c, pred, host in rows:
        tier_result = compute_model_tier(
            c, host, has_real_light_curve=False,
            has_real_centroid=c.centroid_is_real,
            has_real_spectroscopy=bool(host and host.spectroscopy_is_real),
        )
        results.append(PlanetResponse(
            pl_name=c.pl_name,
            tic_id=c.tic_id,
            toi_id=c.toi_id,
            disposition=c.disposition,
            orbper=c.orbper,
            rade=c.rade,
            rade_err_upper=c.rade_err_upper,
            rade_err_lower=c.rade_err_lower,
            trandep=c.trandep,
            trandurh=c.trandurh,
            insol=c.insol,
            eqt=c.eqt,
            evidence_consistency_score=pred.evidence_consistency_score if pred else None,
            followup_priority_score=pred.followup_priority_score if pred else None,
            health_score=c.health_score,
            health_grade=c.health_grade,
            model_tier=tier_result.tier,
            catalogs_available_count=len(tier_result.catalogs_available),
            catalogs_total=tier_result.catalogs_total,
        ))
    return results


class TransitWindowResponse(BaseModel):
    start_utc: str
    end_utc: str
    mid_utc: str
    altitude_at_mid_deg: Optional[float]
    airmass_at_mid: Optional[float]
    sun_altitude_at_mid_deg: float
    is_dark_at_mid: bool

class ObservabilityDetailResponse(BaseModel):
    current_altitude_deg: float
    current_airmass: Optional[float]
    moon_separation_deg: float
    moon_illumination_fraction: float
    transit_window: Optional[TransitWindowResponse]
    observable_tonight: bool
    reason: str

class ObservabilityCandidateResponse(BaseModel):
    pl_name: str
    toi_id: Optional[float]
    tic_id: Optional[int]
    disposition: str
    health_grade: Optional[str] = None
    followup_priority_score: Optional[float] = None
    observability: Optional[ObservabilityDetailResponse] = None
    observability_unavailable_reason: Optional[str] = None


@router.get("/observability", response_model=List[ObservabilityCandidateResponse])
def get_observability(
    lat: float = Query(..., ge=-90, le=90, description="Observer latitude, degrees"),
    lon: float = Query(..., ge=-180, le=180, description="Observer longitude, degrees"),
    elevation_m: float = Query(0.0, description="Observer elevation, meters"),
    obs_date: date_type = Query(..., alias="date", description="Observing night, YYYY-MM-DD (UTC)"),
    only_observable: bool = Query(False),
    disposition: Optional[str] = None,
    sort_by: str = Query("followup_priority_score"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    UPGRADE_PLAN.md H.3.1: real astropy positional astronomy (app/science/observability.py)
    for every candidate in the current page -- altitude, airmass, moon separation, sky
    darkness, and (when a real transit epoch exists) the actual transit window for the
    given night. A candidate with no host star match or no transit epoch on record
    reports `observability=None` with an explicit reason, never a fabricated value.
    Uses `compute_observability_batch` (a single vectorized astropy call across the
    whole page) rather than one Python-level call per candidate -- a real, measured
    ~30x speedup found while load-testing this endpoint as the dev DB grew (196
    candidates: ~32s looped vs ~1s batched). Still O(candidates on this page) per
    request, not cached/precomputed -- would need a batch/cache layer at the full
    ~7,000-row catalog scale (disclosed, not built here).
    """
    if sort_by not in _CANDIDATE_SORT_FIELDS:
        raise HTTPException(status_code=400, detail=f"sort_by must be one of: {', '.join(_CANDIDATE_SORT_FIELDS)}")

    query = db.query(ExoplanetCandidate, MLPrediction, HostStar).outerjoin(
        MLPrediction, MLPrediction.candidate_id == ExoplanetCandidate.id
    ).join(
        HostStar, HostStar.id == ExoplanetCandidate.host_id
    )
    if disposition:
        query = query.filter(ExoplanetCandidate.disposition == disposition)

    sort_col = _CANDIDATE_SORT_FIELDS[sort_by]
    order_fn = desc if sort_dir == "desc" else asc
    rows = query.order_by(order_fn(sort_col)).offset(offset).limit(limit).all()

    try:
        specs = [
            TargetSpec(ra_deg=host.ra, dec_deg=host.dec, period_days=c.orbper, duration_hours=c.trandurh, tranmid_bjd=c.tranmid)
            for c, pred, host in rows
        ]
        observabilities = compute_observability_batch(specs, lat, lon, elevation_m, obs_date)
        batch_error = None
    except Exception as e:
        observabilities = [None] * len(rows)
        batch_error = str(e)

    results = []
    for (c, pred, host), obs in zip(rows, observabilities):
        if obs is None:
            results.append(ObservabilityCandidateResponse(
                pl_name=c.pl_name, toi_id=c.toi_id, tic_id=c.tic_id, disposition=c.disposition,
                health_grade=c.health_grade,
                followup_priority_score=pred.followup_priority_score if pred else None,
                observability=None, observability_unavailable_reason=f"computation failed: {batch_error}",
            ))
            continue

        if only_observable and not obs.observable_tonight:
            continue

        results.append(ObservabilityCandidateResponse(
            pl_name=c.pl_name, toi_id=c.toi_id, tic_id=c.tic_id, disposition=c.disposition,
            health_grade=c.health_grade,
            followup_priority_score=pred.followup_priority_score if pred else None,
            observability=ObservabilityDetailResponse(
                current_altitude_deg=obs.current_altitude_deg,
                current_airmass=obs.current_airmass,
                moon_separation_deg=obs.moon_separation_deg,
                moon_illumination_fraction=obs.moon_illumination_fraction,
                transit_window=TransitWindowResponse(**obs.transit_window.__dict__) if obs.transit_window else None,
                observable_tonight=obs.observable_tonight,
                reason=obs.reason,
            ),
        ))
    return results


@router.get("/candidates/export")
def export_candidates_votable(disposition: Optional[str] = None, limit: int = Query(5000, ge=1, le=20000),
                               db: Session = Depends(get_db)):
    """
    VOTable export (UPGRADE_PLAN.md G, Phase 4) -- how astronomers already consume
    tabular data (TOPCAT, Aladin, astroquery), not a proprietary JSON blob they'd have
    to write custom parsing for. Registered before /candidates/{toi_id} deliberately:
    that route's toi_id is float-typed, and Starlette does not fall through to a later
    route on a failed path-type conversion, so "export" would 422 against {toi_id} if
    this route were registered second.
    """
    votable_bytes = build_candidates_votable_bytes(db, disposition=disposition, limit=limit)
    return Response(
        content=votable_bytes,
        media_type="application/x-votable+xml",
        headers={"Content-Disposition": "attachment; filename=eefn_candidates.vot"},
    )


@router.get("/resolve")
def resolve(id: str = Query(..., description="TOI-101.01, 101.01, TIC 231663901, 231663901, or Gaia DR3 <source_id>"),
            db: Session = Depends(get_db)):
    """
    Identifier resolution (UPGRADE_PLAN.md G.2) -- never make a caller hand-translate
    TIC <-> TOI <-> Gaia source_id themselves.
    """
    matches = resolve_identifier(db, id)
    if not matches:
        raise HTTPException(status_code=404, detail=f"No candidate found matching identifier {id!r}")
    return {"query": id, "matches": matches}


class BatchAuditRequest(BaseModel):
    toi_ids: List[float]

class BatchAuditResultItem(BaseModel):
    toi_id: float
    found: bool
    pl_name: Optional[str] = None
    disposition: Optional[str] = None
    health_score: Optional[float] = None
    health_grade: Optional[str] = None
    evidence_consistency_score: Optional[float] = None
    followup_priority_score: Optional[float] = None
    model_tier: Optional[int] = None
    catalogs_available_count: Optional[int] = None

class BatchAuditResponse(BaseModel):
    requested_count: int
    found_count: int
    not_found: List[float]
    results: List[BatchAuditResultItem]

_BATCH_MAX_TARGETS = 500


@router.post("/batch/audit", response_model=BatchAuditResponse)
def batch_audit(request: BatchAuditRequest, db: Session = Depends(get_db)):
    """
    UPGRADE_PLAN.md H.3.4: upload a target list (TOI IDs), receive a ranked real
    audit -- "this matches how observers actually work; single-target browsing is
    the exception, not the rule." Reuses the same `build_candidate_profile`/
    `compute_model_tier` real data path as the single-candidate endpoint, so a
    batch result can never show a different number than looking the same TOI up
    individually. A requested TOI with no match is reported honestly in
    `not_found`, never silently dropped or backfilled with a placeholder row.
    """
    if not request.toi_ids:
        raise HTTPException(status_code=400, detail="toi_ids must not be empty")
    if len(request.toi_ids) > _BATCH_MAX_TARGETS:
        raise HTTPException(status_code=400, detail=f"At most {_BATCH_MAX_TARGETS} TOIs per batch request")

    results = []
    not_found = []
    for toi_id in request.toi_ids:
        profile = build_candidate_profile(db, toi_id)
        if profile is None:
            not_found.append(toi_id)
            results.append(BatchAuditResultItem(toi_id=toi_id, found=False))
            continue
        results.append(BatchAuditResultItem(
            toi_id=toi_id,
            found=True,
            pl_name=profile["planet"]["pl_name"],
            disposition=profile["planet"]["disposition"],
            health_score=profile["health"]["score"],
            health_grade=profile["health"]["grade"],
            evidence_consistency_score=profile["prediction"]["evidence_consistency_score"],
            followup_priority_score=profile["prediction"]["followup_priority_score"],
            model_tier=profile["model_tier"]["tier"],
            catalogs_available_count=len(profile["model_tier"]["catalogs_available"]),
        ))

    results.sort(key=lambda r: (not r.found, -(r.followup_priority_score or 0.0)))

    return BatchAuditResponse(
        requested_count=len(request.toi_ids),
        found_count=len(request.toi_ids) - len(not_found),
        not_found=not_found,
        results=results,
    )


@router.post("/batch/export")
def batch_export(request: BatchAuditRequest, db: Session = Depends(get_db)):
    """VOTable export of exactly the batch's matched TOIs (UPGRADE_PLAN.md H.3.4) --
    the same real astropy VOTable writer as /candidates/export, filtered to this list."""
    if not request.toi_ids:
        raise HTTPException(status_code=400, detail="toi_ids must not be empty")
    votable_bytes = build_candidates_votable_bytes(db, toi_ids=request.toi_ids, limit=len(request.toi_ids))
    return Response(
        content=votable_bytes,
        media_type="application/x-votable+xml",
        headers={"Content-Disposition": "attachment; filename=eefn_batch_audit.vot"},
    )


class ChangeEventResponse(BaseModel):
    toi_id: Optional[float]
    pl_name: str
    field_name: str
    old_value: Optional[str]
    new_value: Optional[str]
    changed_at: datetime


@router.get("/changes", response_model=List[ChangeEventResponse])
def get_changes(
    since: Optional[datetime] = Query(None, description="Only changes strictly after this UTC timestamp"),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """
    UPGRADE_PLAN.md H.3.5: the diff/"what changed" view -- a real, timestamped ledger
    of disposition/health_grade transitions (app/db/models.py::DispositionChangeEvent),
    written by ingest.py's upsert path only when a re-ingested candidate's value
    genuinely differs from what was already stored. An empty result honestly means
    "no real transitions have been recorded yet" (e.g. before this feature existed,
    or if nothing has actually changed), never a fabricated list of changes.
    """
    query = db.query(DispositionChangeEvent)
    if since is not None:
        query = query.filter(DispositionChangeEvent.changed_at > since)
    rows = query.order_by(DispositionChangeEvent.changed_at.desc()).limit(limit).all()
    return [
        ChangeEventResponse(
            toi_id=r.toi_id, pl_name=r.pl_name, field_name=r.field_name,
            old_value=r.old_value, new_value=r.new_value, changed_at=r.changed_at,
        )
        for r in rows
    ]


@router.get("/candidates/{toi_id}", response_model=CandidateProfileResponse)
def get_candidate_detail(toi_id: float, db: Session = Depends(get_db)):
    profile = build_candidate_profile(db, toi_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Candidate with TOI ID {toi_id} not found")

    return CandidateProfileResponse(
        planet=PlanetResponse(**profile["planet"]),
        star=StarResponse(**profile["star"]),
        sources=profile["sources"],
        measurement_history=profile["measurement_history"],
        agreement_metrics=MetricsResponse(**profile["agreement_metrics"]),
        prediction=PredictionResponse(**profile["prediction"]),
        model_tier=ModelTierResponse(**profile["model_tier"]),
        health=HealthBreakdownResponse(**profile["health"]),
        real_observations=profile.get("real_observations", {}),
        data_quality=profile.get("data_quality", {}),
    )

class PipelineRunResponse(BaseModel):
    id: str
    arq_job_id: Optional[str]
    status: str
    limit_requested: int
    catalogs_used: Optional[List[str]]
    catalog_versions: Optional[Dict[str, str]]
    targets_processed: Optional[int]
    failures: Optional[List[Dict[str, Any]]]
    error_detail: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    duration_seconds: Optional[float]

    class Config:
        from_attributes = True


def _to_run_response(run: PipelineRun) -> PipelineRunResponse:
    return PipelineRunResponse(
        id=str(run.id),
        arq_job_id=run.arq_job_id,
        status=run.status,
        limit_requested=run.limit_requested,
        catalogs_used=run.catalogs_used,
        catalog_versions=run.catalog_versions,
        targets_processed=run.targets_processed,
        failures=run.failures,
        error_detail=run.error_detail,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        duration_seconds=run.duration_seconds,
    )


@router.post("/pipeline/run", response_model=PipelineRunResponse, dependencies=[Depends(require_api_key)])
async def run_pipeline(
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """
    Enqueues the data ingestion, cross-matching, fusion, and ML prediction pipeline as
    a real background job (Arq/Redis) instead of a fire-and-forget FastAPI
    BackgroundTask -- this fixes A.9 (closed DB session) properly and gives status,
    retry, and history that a bare BackgroundTask can't (UPGRADE_PLAN.md D.2).
    """
    run = PipelineRun(status="queued", limit_requested=limit)
    db.add(run)
    db.commit()
    db.refresh(run)

    pool = await get_arq_pool()
    job = await pool.enqueue_job("run_pipeline_task", str(run.id), limit)
    run.arq_job_id = job.job_id
    db.commit()
    db.refresh(run)

    return _to_run_response(run)


@router.get("/pipeline/runs", response_model=List[PipelineRunResponse])
def list_pipeline_runs(
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Run history for the admin/ops view (UPGRADE_PLAN.md D.2/H.3.8) -- per-source
    catalog health and past sync status, not just a "run pipeline" button."""
    runs = db.query(PipelineRun).order_by(PipelineRun.created_at.desc()).limit(limit).all()
    return [_to_run_response(r) for r in runs]


def _parse_run_id(run_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Pipeline run {run_id} not found")


@router.get("/pipeline/runs/{run_id}", response_model=PipelineRunResponse)
def get_pipeline_run(run_id: str, db: Session = Depends(get_db)):
    run = db.query(PipelineRun).filter(PipelineRun.id == _parse_run_id(run_id)).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"Pipeline run {run_id} not found")
    return _to_run_response(run)


@router.post("/pipeline/runs/{run_id}/cancel", response_model=PipelineRunResponse, dependencies=[Depends(require_api_key)])
async def cancel_pipeline_run(run_id: str, db: Session = Depends(get_db)):
    """
    Best-effort cancellation. Arq's `Job.abort()` can prevent a still-queued job from
    ever starting, and can interrupt a running job's *awaits* -- but
    ingest_and_fuse_data runs inside `asyncio.to_thread`, so a job already mid-run
    keeps executing in its OS thread until its next natural checkpoint; this call
    still marks the row cancellation-requested immediately rather than lying about
    completion. See UPGRADE_PLAN.md D.2.
    """
    run = db.query(PipelineRun).filter(PipelineRun.id == _parse_run_id(run_id)).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"Pipeline run {run_id} not found")
    if run.status in ("success", "partial_failure", "error", "cancelled"):
        raise HTTPException(status_code=409, detail=f"Pipeline run {run_id} already finished with status={run.status}")

    if run.arq_job_id:
        pool = await get_arq_pool()
        job = ArqJob(run.arq_job_id, pool)
        aborted = await job.abort()
        if aborted:
            run.status = "cancelled"
            run.finished_at = datetime.utcnow()
            db.commit()
            db.refresh(run)
    return _to_run_response(run)

_MODEL_METRICS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ml", "model_metrics.json")
_CALIBRATION_REPORT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ml", "calibration_report.json")
_DL_TRAINING_REPORT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ml", "dl_training_report.json")

@router.get("/predictions/metrics")
def get_model_metrics():
    """
    Serves the evaluation-metrics artifact written by
    validation/scripts/train_and_serialize_model.py at training time -- never a
    hardcoded dict (UPGRADE_PLAN.md A.8/C.8). If no artifact exists, this returns an
    explicit unavailable state rather than inventing plausible-looking numbers.
    """
    metrics_path = os.path.normpath(_MODEL_METRICS_PATH)
    if not os.path.exists(metrics_path):
        raise HTTPException(
            status_code=503,
            detail="No model_metrics.json artifact found. Run "
                   "validation/scripts/train_and_serialize_model.py to generate one; "
                   "this endpoint never fabricates evaluation metrics.",
        )
    with open(metrics_path, "r") as f:
        return json.load(f)


@router.get("/predictions/dl_training")
def get_dl_training_report():
    """
    Serves the deep-learning training report written by app/ml/train_deep_learning.py.

    Exists because the /ai-analysis page previously HARDCODED its training statistics
    (1,182 samples / 99.58% accuracy / 0.0114 loss / a 4-class sample distribution).
    Those numbers came from an old synthetic-data training run and silently went stale
    -- they survived a model retrain, a metadata-vector expansion (16 -> 28 dims), and
    a class-count change, all while still being displayed as current fact. That is the
    exact A.8/A.14 failure this project exists to eliminate, sitting on the page most
    likely to be shown to a reviewer.

    Same honesty contract as /predictions/metrics: 503 with an explicit message if no
    artifact exists, never a fabricated or fallback number.
    """
    report_path = os.path.normpath(_DL_TRAINING_REPORT_PATH)
    if not os.path.exists(report_path):
        raise HTTPException(
            status_code=503,
            detail="No dl_training_report.json artifact found. Run "
                   "`python -m app.ml.train_deep_learning` to generate one; "
                   "this endpoint never fabricates training statistics.",
        )
    with open(report_path, "r") as f:
        return json.load(f)


_ML_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ml")


@router.get("/predictions/lightcurve_vetter")
def get_lightcurve_vetter_report():
    """
    Real evaluation of the production light-curve vetter (star-grouped cross-validation on
    real Kepler data) plus the architecture study that chose it over the CNN. Same honesty
    contract as /predictions/metrics: 503 if the artifact is missing, never a fallback number.
    """
    report_path = os.path.normpath(os.path.join(_ML_DIR, "lightcurve_vetter_report.json"))
    if not os.path.exists(report_path):
        raise HTTPException(
            status_code=503,
            detail="No lightcurve_vetter_report.json artifact found. Run "
                   "validation/scripts/train_lightcurve_vetter.py to generate one.",
        )
    with open(report_path, "r") as f:
        report = json.load(f)
    study_path = os.path.normpath(os.path.join(_ML_DIR, "dl_architecture_study.json"))
    if os.path.exists(study_path):
        with open(study_path, "r") as f:
            report["architecture_study"] = json.load(f)
    abl_path = os.path.normpath(os.path.join(_ML_DIR, "lightcurve_vetter_ablation.json"))
    if os.path.exists(abl_path):
        with open(abl_path, "r") as f:
            report["ablation"] = json.load(f)
    tess_path = os.path.normpath(os.path.join(_ML_DIR, "tess_transfer_report.json"))
    if os.path.exists(tess_path):
        with open(tess_path, "r") as f:
            report["tess_transfer"] = json.load(f)
    return report


@router.get("/predictions/honest_evaluation")
def get_honest_evaluation():
    """
    Star-grouped and time-forward evaluation of the tabular model, against a TOI-table-only
    baseline, with 95% bootstrap CIs resampled by star (validation/scripts/honest_evaluation.py).
    The random-split numbers in /predictions/metrics answer "how well does it recover labels for
    TOIs like the training ones"; this answers "how well does it score new candidates, and what do
    the cross-catalog features actually add". 503 if the artifact is missing -- never a fallback.
    """
    path = os.path.normpath(os.path.join(_ML_DIR, "honest_evaluation_report.json"))
    if not os.path.exists(path):
        raise HTTPException(
            status_code=503,
            detail="No honest_evaluation_report.json artifact found. Run "
                   "backend/validation/scripts/honest_evaluation.py to generate one.",
        )
    with open(path, "r") as f:
        return json.load(f)


@router.get("/catalog/coverage")
def get_catalog_coverage(db: Session = Depends(get_db)):
    """Live counts of how many candidates / hosts each catalog and real-data enrichment actually covers,
    so no page has to hardcode (and then silently outlive) these numbers."""
    from sqlalchemy import func
    n_cand = db.query(func.count(ExoplanetCandidate.id)).scalar() or 0
    n_host = db.query(func.count(HostStar.id)).scalar() or 0

    def cand_where(*conds):
        return (db.query(func.count(ExoplanetCandidate.id)).join(HostStar, ExoplanetCandidate.host_id == HostStar.id)
                .filter(*conds).scalar() or 0)

    def host_where(*conds):
        return db.query(func.count(HostStar.id)).filter(*conds).scalar() or 0

    return {
        "candidates": n_cand, "hosts": n_host,
        "candidates_with_gaia_params": cand_where(HostStar.teff.isnot(None)),
        "hosts_with_gaia_params": host_where(HostStar.teff.isnot(None)),
        "candidates_with_2mass": cand_where(HostStar.j_mag.isnot(None)),
        "candidates_with_panstarrs": cand_where(HostStar.g_mag.isnot(None)),
        "hosts_with_real_spectroscopy": host_where(HostStar.spectroscopy_is_real.is_(True)),
        "candidates_with_real_centroid": db.query(func.count(ExoplanetCandidate.id)).filter(ExoplanetCandidate.centroid_is_real.is_(True)).scalar() or 0,
        "candidates_with_lightcurve_vetting": db.query(func.count(ExoplanetCandidate.id)).filter(ExoplanetCandidate.lc_vetting_status == "vetted").scalar() or 0,
    }


@router.get("/health/validation")
def get_health_validation(db: Session = Depends(get_db)):
    """How well the A-F health grade separates confirmed planets from false positives, computed live
    from the labelled candidates in the database (see app/science/health_validation.py)."""
    from app.science.health_validation import validate_health
    rows = [{"disposition": c.disposition, "health_score": c.health_score, "health_grade": c.health_grade}
            for c in db.query(ExoplanetCandidate).all()]
    return validate_health(rows)


@router.get("/predictions/calibration")
def get_model_calibration():
    """
    Serves the reliability-diagram/Brier-score artifact from the same training run as
    /predictions/metrics (UPGRADE_PLAN.md E.2) -- what a working scientist actually
    checks before trusting a stated probability, not just accuracy. 503s with an
    explicit message if no artifact exists yet, same honesty contract as C.8.
    """
    calibration_path = os.path.normpath(_CALIBRATION_REPORT_PATH)
    if not os.path.exists(calibration_path):
        raise HTTPException(
            status_code=503,
            detail="No calibration_report.json artifact found. Run "
                   "validation/scripts/train_and_serialize_model.py to generate one; "
                   "this endpoint never fabricates calibration data.",
        )
    with open(calibration_path, "r") as f:
        return json.load(f)

@router.get("/graph/nodes")
def get_graph_nodes(db: Session = Depends(get_db)):
    # Simple dynamic node generator from DB for visualization fallback
    candidates = db.query(ExoplanetCandidate).limit(10).all()
    nodes = []
    
    # Add Catalog nodes
    nodes.append({"id": "cat_nasa", "label": "Catalog", "name": "NASA Archive"})
    nodes.append({"id": "cat_gaia", "label": "Catalog", "name": "Gaia DR3"})
    nodes.append({"id": "cat_toi", "label": "Catalog", "name": "TOI Catalog"})
    
    for c in candidates:
        star_id = f"star_{c.tic_id}"
        cand_id = f"toi_{c.toi_id}"
        
        # Add host star and candidate
        nodes.append({"id": star_id, "label": "Star", "name": c.host.hostname})
        nodes.append({"id": cand_id, "label": "Exoplanet", "name": c.pl_name})
        
    return nodes

@router.get("/graph/edges")
def get_graph_edges(db: Session = Depends(get_db)):
    candidates = db.query(ExoplanetCandidate).limit(10).all()
    edges = []
    for c in candidates:
        star_id = f"star_{c.tic_id}"
        cand_id = f"toi_{c.toi_id}"
        
        edges.append({"source": star_id, "target": cand_id, "type": "HOSTS"})
        
        # Inconsistencies connect to catalogs
        edges.append({"source": cand_id, "target": "cat_nasa", "type": "RECORDED_IN"})
        edges.append({"source": cand_id, "target": "cat_toi", "type": "RECORDED_IN"})
        edges.append({"source": star_id, "target": "cat_gaia", "type": "RECORDED_IN"})
        
    return edges

@router.get("/candidates/{toi_id}/alerts")
def get_candidate_alerts(toi_id: float, db: Session = Depends(get_db)):
    cand = db.query(ExoplanetCandidate).filter(ExoplanetCandidate.toi_id == toi_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail=f"Candidate with TOI ID {toi_id} not found")
    engine = AlertEngine(db)
    return engine.generate_alerts(cand.id)

@router.get("/candidates/{toi_id}/health")
def get_candidate_health(toi_id: float, db: Session = Depends(get_db)):
    cand = db.query(ExoplanetCandidate).filter(ExoplanetCandidate.toi_id == toi_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail=f"Candidate with TOI ID {toi_id} not found")
    engine = AlertEngine(db)
    return engine.calculate_health_score(cand.id)

@router.get("/candidates/{toi_id}/resolution")
def get_candidate_resolution(toi_id: float, db: Session = Depends(get_db)):
    cand = db.query(ExoplanetCandidate).filter(ExoplanetCandidate.toi_id == toi_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail=f"Candidate with TOI ID {toi_id} not found")
    audit = EntityResolutionAudit(db)
    return audit.get_entity_profile(cand.id)

class OverrideRequest(BaseModel):
    gaia_id: str

@router.post("/candidates/{toi_id}/resolution/override", dependencies=[Depends(require_api_key)])
def override_candidate_resolution(toi_id: float, request: OverrideRequest, db: Session = Depends(get_db)):
    cand = db.query(ExoplanetCandidate).filter(ExoplanetCandidate.toi_id == toi_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail=f"Candidate with TOI ID {toi_id} not found")
    audit = EntityResolutionAudit(db)
    return audit.manual_override_link(cand.id, request.gaia_id)

@router.get("/candidates/{toi_id}/timeline")
def get_candidate_timeline(toi_id: float, db: Session = Depends(get_db)):
    cand = db.query(ExoplanetCandidate).filter(ExoplanetCandidate.toi_id == toi_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail=f"Candidate with TOI ID {toi_id} not found")
    timeline = EvidenceTimeline(db)
    return timeline.get_timeline(cand.id)

@router.get("/catalog/health")
def get_catalog_health(db: Session = Depends(get_db)):
    """
    UPGRADE_PLAN.md H.3.8 / A.8-class fix: `ingestion_success_rate`,
    `cross_match_success_rate`, and `stale_record_rate` used to be hardcoded
    constants (0.995, 0.984, 0.05) -- a real bug found while rebuilding the admin
    page, the same "static number presented as measured performance" pattern C.8
    already fixed for /predictions/metrics. All three are now computed from real
    rows: success rates from `ExoplanetCandidate.query_failed` (set by ingest.py
    when a catalog cross-match genuinely failed) and staleness from `updated_at`.
    """
    total = db.query(ExoplanetCandidate).count()
    conflict_count = db.query(AgreementMetrics).filter(AgreementMetrics.is_unphysical_rp == True).count()
    high_ruwe_count = db.query(AgreementMetrics).filter(AgreementMetrics.ruwe > 1.4).count()
    query_failed_count = db.query(ExoplanetCandidate).filter(ExoplanetCandidate.query_failed == True).count()

    conflict_rate = (conflict_count / total) if total > 0 else 0.0
    success_rate = ((total - query_failed_count) / total) if total > 0 else 1.0

    stale_cutoff = datetime.utcnow() - timedelta(days=30)
    stale_count = db.query(ExoplanetCandidate).filter(ExoplanetCandidate.updated_at < stale_cutoff).count()
    stale_rate = (stale_count / total) if total > 0 else 0.0

    # Fetch actual sync times
    nasa_src = db.query(CatalogSource).filter(CatalogSource.name == "NASA Exoplanet Archive").first()
    gaia_src = db.query(CatalogSource).filter(CatalogSource.name == "Gaia DR3").first()
    toi_src = db.query(CatalogSource).filter(CatalogSource.name == "TOI Catalog").first()

    return {
        "conflict_rate": conflict_rate,
        "ingestion_success_rate": success_rate,
        "cross_match_success_rate": success_rate,
        "stale_record_rate": stale_rate,
        "unresolved_alert_count": conflict_count + high_ruwe_count,
        "resolved_conflict_count": total - (conflict_count + high_ruwe_count),
        "total_candidates": total,
        "last_sync": {
            "nasa": nasa_src.last_sync.isoformat() if nasa_src and nasa_src.last_sync else None,
            "gaia": gaia_src.last_sync.isoformat() if gaia_src and gaia_src.last_sync else None,
            "toi": toi_src.last_sync.isoformat() if toi_src and toi_src.last_sync else None
        }
    }

@router.get("/candidates/{toi_id}/transit_pipeline")
def get_candidate_transit_pipeline(
    toi_id: float,
    noise_std: float = Query(0.002, ge=0.0001, le=0.02),
    blending_factor: float = Query(0.15, ge=0.0, le=0.9),
    has_starspots: bool = Query(True),
    db: Session = Depends(get_db)
):
    cand = db.query(ExoplanetCandidate).filter(ExoplanetCandidate.toi_id == toi_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail=f"Candidate with TOI ID {toi_id} not found")
    
    # Extract physical host star radius (default to 1.0 solar radii if missing)
    rstar_solar = cand.host.rad if cand.host and cand.host.rad else 1.0
    
    seed_val = int(cand.toi_id * 100 + 0.5) if cand.toi_id else 42
    
    sim = transit_pipeline.generate_simulated_lightcurve(
        period=cand.orbper or 3.0,
        depth_ppm=cand.trandep or 1500.0,
        duration_hours=cand.trandurh or 2.5,
        noise_std=noise_std,
        blending_factor=blending_factor,
        has_starspots=has_starspots,
        seed=seed_val
    )
    
    time_arr = np.array(sim["time"])
    raw_flux_arr = np.array(sim["raw_flux"])
    detrended = transit_pipeline.detrend_lightcurve(
        time=time_arr,
        raw_flux=raw_flux_arr,
        period=cand.orbper or 3.0,
        duration_hours=cand.trandurh or 2.5
    )
    
    results = transit_pipeline.run_ai_classification(
        time=time_arr,
        detrended_flux=detrended,
        period=cand.orbper or 3.0,
        duration_hours=cand.trandurh or 2.5,
        blending_factor=blending_factor,
        rstar_solar=rstar_solar
    )
    
    # The light curve above is a SIMULATION built from this candidate's own catalog
    # period/depth/duration (a what-if playground for the noise/blending/starspot
    # sliders). Classifying it would just reflect those catalog numbers back as if they
    # were evidence, so the vetting model is never run on it. The vetting result served
    # here comes from the candidate's REAL SPOC TESS light curve, computed by the
    # scheduled sync (app/pipeline/real_sync.py::sync_real_lightcurve_vetting) and stored
    # on the candidate; if none exists yet we say so instead of faking one.
    vet = cand.lc_vetting_json if cand.lc_vetting_status == S.VETTED and cand.lc_vetting_json else None
    if vet:
        dl_view_global, dl_view_local = vet["global_view"], vet["local_view"]
        dl_classification = vet["classification"]
        dl_status, dl_degraded, dl_source = "trained", False, "real_tess_spoc_2min"
        dl_note = None
    else:
        g_view, l_view = dl_vetting_engine.preprocess_lightcurve(
            time=time_arr, flux=detrended, period=cand.orbper or 3.0, duration_hours=cand.trandurh or 2.5,
        )
        dl_view_global, dl_view_local = (g_view - 1.0).tolist(), (l_view - 1.0).tolist()
        dl_classification = {}
        dl_status, dl_degraded, dl_source = "no_real_lightcurve", True, "simulated_not_classified"
        dl_note = (
            "No real TESS light curve has been vetted for this candidate yet "
            f"(status: {cand.lc_vetting_status or 'not attempted'}). The views shown are of the simulated "
            "curve above and are not classified."
        )

    return {
        "time": sim["time"],
        "raw_flux": sim["raw_flux"],
        "detrended_flux": detrended.tolist(),
        "transit_fit": sim["clean_transit_fit"],
        "starspot_signal": sim["starspot_signal"],
        "true_depth_ppm": sim["true_depth_ppm"],
        "diluted_depth_ppm": sim["diluted_depth_ppm"],
        "metrics": {
            "snr": results["snr"],
            "v_shape_factor": results["v_shape_factor"],
            "noise_level_ppm": results["noise_level_ppm"],
            "observed_depth_ppm": results["observed_depth_ppm"],
            "derived_rp_earth": results["derived_rp_earth"]
        },
        "classification": results["classification"],
        # Light-curve vetting (real data only) -- see the comment above.
        "dl_global_view": dl_view_global,
        "dl_local_view": dl_view_local,
        "dl_classification": dl_classification,
        "dl_model_status": dl_status,
        "dl_model_degraded": dl_degraded,
        "dl_input_source": dl_source,
        "dl_model_version": vet["model_version"] if vet else None,
        "dl_vetted_sectors": vet.get("sectors") if vet else None,
        "dl_features": vet["features"] if vet else None,
        "dl_vetted_at": cand.lc_vetting_at.isoformat() if vet and cand.lc_vetting_at else None,
        "dl_note": dl_note,
        # Reported separately from the classification: the vetter does not consume the centroid,
        # so this must not read as "the classifier used it".
        "centroid_measured": bool(cand.centroid_is_real),
    }
