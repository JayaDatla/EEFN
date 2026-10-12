import os
from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Resolve eefn.db absolutely relative to the backend directory
    DATABASE_URL: str = f"sqlite:///{os.path.abspath(os.path.join(os.path.dirname(__file__), '../eefn.db')).replace('\\\\', '/')}"

    # Backs both the Arq job queue (D.2) and the shared cross-worker rate limiter.
    REDIS_URL: str = "redis://localhost:6379/0"

    # Shared token-bucket ceiling for all CDS/VizieR/MAST calls, across every worker
    # process -- see UPGRADE_PLAN.md D.2 ("existential risk to the whole project" if
    # CDS bans this project's IP for exceeding their informal rate limits).
    CATALOG_RATE_LIMIT_PER_SECOND: float = 2.0

    # UPGRADE_PLAN.md D.3: shared-secret auth for write endpoints (/pipeline/run,
    # /pipeline/runs/*/cancel, resolution override). Left unset by default so local
    # dev keeps working without extra setup -- main.py prints a loud startup warning
    # when this is unset. Any non-local deployment MUST set this via the environment;
    # an unauthenticated write endpoint on a reachable instance lets anyone trigger
    # unbounded external API load or overwrite curator decisions.
    API_KEY: Optional[str] = None

    # Comma-separated list of allowed CORS origins. The previous `allow_origins=["*"]`
    # combined with `allow_credentials=True` is actually rejected by browsers (the CORS
    # spec forbids a wildcard origin alongside credentials) as well as being wide open.
    # Default covers both `next dev`'s standard port (3000) and the port it falls back
    # to when 3000 is already taken (3001, common when running two EEFN checkouts or a
    # leftover dev server) -- any non-local deployment must still override this.
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001"

    # UPGRADE_PLAN.md G.3: optional webhook fired when a pipeline run finishes, so a
    # TFOP triage channel (Slack or otherwise) gets pushed a notification instead of
    # needing to poll GET /pipeline/runs. Comma-separated list; empty means disabled.
    # The payload includes a top-level "text" summary field so it renders sensibly if
    # pointed directly at a Slack incoming-webhook URL, without a Slack-specific path.
    WEBHOOK_URLS: str = ""

    # Scheduled real-data enrichment (Arq cron, app/worker.py). Each nightly run only
    # attempts this many never-/long-ago-attempted targets: TPF downloads are the
    # expensive part, so the whole catalog is covered incrementally, not in one pass.
    CENTROID_SYNC_BATCH: int = 15
    SPECTROSCOPY_SYNC_BATCH: int = 100
    LIGHTCURVE_SYNC_BATCH: int = 10
    # A target with no TPF / no APOGEE match is not retried until this many days later.
    SYNC_RETRY_AFTER_DAYS: int = 90

    class Config:
        env_file = ".env"

    @property
    def allowed_origins_list(self) -> list:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def webhook_urls_list(self) -> list:
        return [u.strip() for u in self.WEBHOOK_URLS.split(",") if u.strip()]

settings = Settings()
