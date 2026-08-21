"""
Webhook notifications (UPGRADE_PLAN.md G.3): "Most TFOP groups already run a triage
channel; push into it rather than compete with it." Fires when a pipeline run
finishes -- the one already-tracked, batch-level event in the system (PipelineRun
rows). Alert-triggered webhooks are NOT implemented here: alerts (services/alert_engine.py)
are computed on demand when a candidate's detail page is viewed, not eagerly generated
or stored as a discrete event during ingestion, so there's no natural "an alert just
fired" moment to hook into yet -- that would need alert generation to become part of
the ingestion pipeline itself, a bigger change deliberately not bundled in here.
"""
import logging
from typing import Any, Dict

import requests

from app.config import settings
from app.db.models import PipelineRun

logger = logging.getLogger(__name__)

WEBHOOK_TIMEOUT_SECONDS = 5.0


def _pipeline_run_payload(run: PipelineRun) -> Dict[str, Any]:
    status_emoji = {"success": "✅", "partial_failure": "⚠️", "error": "❌", "cancelled": "🚫"}.get(run.status, "ℹ️")
    text = (
        f"{status_emoji} EEFN pipeline run {run.status}: "
        f"{run.targets_processed or 0}/{run.limit_requested} targets processed"
        + (f", {len(run.failures)} failure(s)" if run.failures else "")
        + (f" in {run.duration_seconds:.1f}s" if run.duration_seconds else "")
    )
    return {
        "event": "pipeline_run.completed",
        "text": text,  # top-level "text" so this also renders sensibly on a Slack incoming webhook
        "run_id": str(run.id),
        "status": run.status,
        "limit_requested": run.limit_requested,
        "targets_processed": run.targets_processed,
        "failures": run.failures,
        "catalogs_used": run.catalogs_used,
        "duration_seconds": run.duration_seconds,
        "error_detail": run.error_detail,
    }


def notify_pipeline_run_completed(run: PipelineRun) -> None:
    """
    Best-effort: a webhook delivery failure must never fail the pipeline run itself --
    logged and swallowed, matching the "loud failure, but not a crashing one" pattern
    used elsewhere for non-critical side effects in this codebase.
    """
    urls = settings.webhook_urls_list
    if not urls:
        return
    payload = _pipeline_run_payload(run)
    for url in urls:
        try:
            r = requests.post(url, json=payload, timeout=WEBHOOK_TIMEOUT_SECONDS)
            if r.status_code >= 400:
                logger.warning("Webhook POST to %s returned %s: %s", url, r.status_code, r.text[:200])
        except Exception as e:
            logger.warning("Webhook POST to %s failed: %s", url, e)
