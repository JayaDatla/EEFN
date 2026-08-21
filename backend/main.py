import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.logging_config import configure_logging
from app.config import settings
from app.api import endpoints

configure_logging()
logger = logging.getLogger(__name__)

# Schema is managed by Alembic (see backend/alembic/), not by create_all() -- run
# `alembic upgrade head` before starting the app against a fresh database.
# UPGRADE_PLAN.md D.1.

app = FastAPI(
    title="Exoplanet Evidence Fusion Network (EEFN) API",
    description="Scientific API backend for aggregating exoplanet catalogs, entity resolution, and fusion.",
    version="1.0.0"
)

# UPGRADE_PLAN.md D.3: origins now come from settings instead of a hardcoded "*" --
# a wildcard origin combined with allow_credentials=True is actually rejected by
# browsers per the CORS spec (they forbid that combination), on top of being wide open.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # X-Total-Count isn't in the CORS response-header safelist by default, so the
    # frontend's server-side pagination (candidates/page.tsx) can't read it without
    # this -- the request would otherwise silently succeed with an unreadable header.
    expose_headers=["X-Total-Count"],
)

if not settings.API_KEY:
    logger.warning(
        "API_KEY is not set -- write endpoints (/pipeline/run, /pipeline/runs/*/cancel, "
        "resolution override) are UNAUTHENTICATED. This is fine for local dev only; set "
        "API_KEY in the environment before deploying anywhere reachable by anyone else. "
        "See UPGRADE_PLAN.md D.3."
    )

app.include_router(endpoints.router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "EEFN Backend",
        "docs": "/docs",
        "config": {
            "database": "Relational DB connected",
            "catalogs_supported": ["NASA Exoplanet Archive", "Gaia DR3", "TOI Catalog", "CTOI Catalog", "Exoplanet.eu", "ExoFOP"]
        }
    }
