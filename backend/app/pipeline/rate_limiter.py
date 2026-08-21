"""
Shared, cross-process token-bucket rate limiter for external catalog calls
(UPGRADE_PLAN.md D.2). Backed by Redis so every worker process enforces the same
budget -- a per-process in-memory limiter would let N workers each independently
believe they have the full rate available, multiplying the actual request rate by N
and defeating the point. Getting IP-banned from CDS/VizieR is flagged in the plan's
own risk register as an existential risk to the whole project at scale.
"""
import time
from typing import Optional

import redis

# Atomic: read bucket state, refill by elapsed time, decide/consume in one round trip.
# Without this running server-side, a check-then-consume from Python would race across
# concurrent worker processes and let more than `rate` requests/sec through.
_TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local rate = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local bucket = redis.call("HMGET", key, "tokens", "timestamp")
local tokens = tonumber(bucket[1])
local timestamp = tonumber(bucket[2])

if tokens == nil then
    tokens = capacity
    timestamp = now
end

local delta = now - timestamp
if delta < 0 then delta = 0 end
tokens = math.min(capacity, tokens + delta * rate)

local allowed = 0
local wait = 0
if tokens >= 1 then
    tokens = tokens - 1
    allowed = 1
else
    wait = (1 - tokens) / rate
end

redis.call("HMSET", key, "tokens", tokens, "timestamp", now)
redis.call("EXPIRE", key, 60)

return {allowed, tostring(wait)}
"""


class TokenBucketRateLimiter:
    """Blocking `acquire()`: sleeps as needed, then returns once a slot is granted."""

    def __init__(self, redis_client: "redis.Redis", key: str, rate_per_second: float,
                 capacity: Optional[float] = None):
        self._redis = redis_client
        self._key = key
        self._rate = rate_per_second
        self._capacity = capacity if capacity is not None else max(rate_per_second, 1.0)
        self._script = self._redis.register_script(_TOKEN_BUCKET_LUA)

    def acquire(self) -> None:
        while True:
            allowed, wait_str = self._script(
                keys=[self._key],
                args=[self._rate, self._capacity, time.time()],
            )
            if int(allowed):
                return
            time.sleep(max(float(wait_str), 0.01))


def build_catalog_rate_limiter(settings) -> TokenBucketRateLimiter:
    client = redis.Redis.from_url(settings.REDIS_URL)
    return TokenBucketRateLimiter(
        client,
        key="eefn:ratelimit:catalog",
        rate_per_second=settings.CATALOG_RATE_LIMIT_PER_SECOND,
    )


class NullRateLimiter:
    """No-op limiter for tests and offline scripts that don't need real pacing."""

    def acquire(self) -> None:
        return None
