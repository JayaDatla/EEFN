import time

import fakeredis
import pytest

from app.pipeline.rate_limiter import TokenBucketRateLimiter


def test_rate_limiter_paces_calls_to_configured_rate():
    """UPGRADE_PLAN.md D.2: the catalog rate limiter must actually throttle callers to
    the configured rate, not just exist as an unused class."""
    client = fakeredis.FakeRedis()
    limiter = TokenBucketRateLimiter(client, "test-bucket", rate_per_second=5.0, capacity=1.0)

    start = time.monotonic()
    for _ in range(4):
        limiter.acquire()
    elapsed = time.monotonic() - start

    # capacity=1 means the first call is immediate; the next 3 must each wait ~0.2s
    # (1/5 req/s), so 4 calls should take at least ~0.6s and not be near-instant.
    assert elapsed >= 0.55


def test_rate_limiter_is_shared_across_independent_client_instances():
    """A fresh limiter instance pointed at the same Redis key must see the state left
    by a previous instance -- this is what makes the limit actually cross-process
    (UPGRADE_PLAN.md D.2's "shared across all workers" requirement)."""
    client = fakeredis.FakeRedis()
    first = TokenBucketRateLimiter(client, "shared-bucket", rate_per_second=2.0, capacity=1.0)
    first.acquire()  # consumes the only immediately-available token

    second = TokenBucketRateLimiter(client, "shared-bucket", rate_per_second=2.0, capacity=1.0)
    start = time.monotonic()
    second.acquire()
    elapsed = time.monotonic() - start

    assert elapsed >= 0.4  # had to wait for a refill, proving state was shared
