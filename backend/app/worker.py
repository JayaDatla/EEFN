"""
Arq worker process (UPGRADE_PLAN.md D.2): replaces FastAPI's `BackgroundTasks` for
/pipeline/run, which had no status, no retry, no cancellation, and ran against a DB
session that closed the moment the HTTP response returned (A.9). Run with:

    arq app.worker.WorkerSettings
"""
import asyncio
import logging
import uuid
from datetime import datetime

from arq.connections import RedisSettings

from app.logging_config import configure_logging
from app.config import settings
from app.db.session import SessionLocal
from app.db.models import PipelineRun
from app.pipeline.ingest import ingest_and_fuse_data
from app.pipeline.rate_limiter import build_catalog_rate_limiter
from app.webhooks import notify_pipeline_run_completed

configure_logging()
logger = logging.getLogger(__name__)


async def run_pipeline_task(ctx, pipeline_run_id: str, limit: int) -> dict:
    """
    ingest_and_fuse_data is synchronous/blocking (requests + pandas), so it runs in a
    worker thread via asyncio.to_thread rather than blocking this process's event
    loop, which Arq also needs for its own job-polling housekeeping.
    """
    run_uuid = uuid.UUID(pipeline_run_id)
    db = SessionLocal()
    try:
        run = db.query(PipelineRun).filter(PipelineRun.id == run_uuid).first()
        if run is not None:
            run.status = "running"
            run.started_at = datetime.utcnow()
            run.arq_job_id = ctx["job_id"]
            db.commit()

        rate_limiter = build_catalog_rate_limiter(settings)
        result = await asyncio.to_thread(ingest_and_fuse_data, db, limit, rate_limiter, run)
        if run is not None:
            notify_pipeline_run_completed(run)
        return result
    except Exception as e:
        # Safety net: ingest_and_fuse_data only finalizes the PipelineRun row on its
        # own known exit paths. If something else escapes (e.g. a DB error), still
        # mark the run failed instead of leaving it stuck in "running" forever.
        logger.exception("Pipeline run %s failed", pipeline_run_id)
        run = db.query(PipelineRun).filter(PipelineRun.id == run_uuid).first()
        if run is not None and run.status == "running":
            run.status = "error"
            run.error_detail = str(e)
            run.finished_at = datetime.utcnow()
            db.commit()
            notify_pipeline_run_completed(run)
        raise
    finally:
        db.close()


class WorkerSettings:
    functions = [run_pipeline_task]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs = 4
    # Ingesting a few hundred targets against real, sometimes-slow external APIs
    # (NASA TAP, CDS X-Match) can legitimately take minutes -- default Arq timeouts
    # are tuned for quick jobs.
    job_timeout = 1800
