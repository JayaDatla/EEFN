"""
EEFN as an installable library (UPGRADE_PLAN.md D.4):

    from eefn import audit_candidate
    report = audit_candidate(toi=1017.01)

This converts EEFN from "a repo you clone and run main.py in" into "a tool you
`pip install -e backend` and import" -- high leverage for adoption relative to
effort, per the plan. `audit_candidate` and `sync_candidates` are thin wrappers that
open their own DB session and call straight into the same `app.audit`/
`app.pipeline.ingest` functions the FastAPI service uses, so the library, the CLI
(`eefn.cli`), and the API never compute a candidate's report by two different code
paths.
"""
from typing import Any, Dict, Optional

from app.db.session import SessionLocal
from app.audit import build_candidate_profile
from app.pipeline.ingest import ingest_and_fuse_data

__version__ = "0.1.0"

__all__ = ["audit_candidate", "sync_candidates"]


def audit_candidate(toi: float) -> Dict[str, Any]:
    """
    Returns the full cross-catalog evidence report for one already-ingested
    candidate (the same data GET /api/v1/candidates/{toi_id} serves), or raises
    ValueError if no candidate with this TOI ID exists in the DB.

    This reads from the local database; it does not itself go fetch a target that
    hasn't been ingested yet -- use `sync_candidates()` (or the API's /pipeline/run)
    to populate the DB first.
    """
    db = SessionLocal()
    try:
        profile = build_candidate_profile(db, float(toi))
        if profile is None:
            raise ValueError(f"No candidate with TOI ID {toi} found in the database. "
                              f"Run sync_candidates() first to ingest it.")
        return profile
    finally:
        db.close()


def sync_candidates(limit: int = 100) -> Dict[str, Any]:
    """
    Runs the ingestion/cross-match/fusion pipeline synchronously against the local
    DB, without going through the API's Arq job queue (UPGRADE_PLAN.md D.2) -- useful
    for scripts and the `eefn sync` CLI command. For a deployed instance, prefer
    POST /api/v1/pipeline/run so the run is tracked and rate-limited across workers.
    """
    db = SessionLocal()
    try:
        return ingest_and_fuse_data(db, limit=limit)
    finally:
        db.close()
