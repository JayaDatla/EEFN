"""
Minimum-viable API-key auth for write endpoints (UPGRADE_PLAN.md D.3). Proper
per-user accounts are explicitly deferred by the plan ("can come later") -- this is
the shared-secret check that stands between a deployed instance and anyone who finds
its URL being able to trigger unbounded external API load or overwrite curator
decisions.
"""
import secrets
from typing import Optional

from fastapi import Header, HTTPException

from app.config import settings


def require_api_key(x_api_key: Optional[str] = Header(default=None)):
    """
    If API_KEY is unset (the local-dev default), this is a deliberate no-op -- see
    the warning app.main prints at startup. Once API_KEY is set (required for any
    non-local deployment), every request must present a matching X-API-Key header.
    """
    if not settings.API_KEY:
        return
    if not x_api_key or not secrets.compare_digest(x_api_key, settings.API_KEY):
        raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key header")
