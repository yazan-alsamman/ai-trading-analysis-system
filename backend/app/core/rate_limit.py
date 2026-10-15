"""Rate limiting in Redis: GCRA (generic cell rate algorithm) in one atomic Lua script.

A bucket allows ``limit`` units per ``period`` with a burst of the full ``limit``: an idle
client may spend its whole minute at once, then gets one unit every ``period / limit``. Redis
stores a single number per bucket, the theoretical arrival time (TAT) of the next request, and
the script reads the clock with ``TIME`` so several API processes agree on "now".

The same round trip also counts the request in an API key's daily usage hash and, when it is
rejected, in the per-minute rejection stats (tier and route group) for the admin endpoint.

Redis errors are reported to the caller as :class:`LimiterUnavailable`; the caller decides
whether to fail open (normal endpoints) or closed (login). Fail-open events are counted here.
"""

import logging
import math
import time
import uuid
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings

logger = logging.getLogger(__name__)

PERIOD_SECONDS = 60
USAGE_TTL_SECONDS = 8 * 24 * 3600  # daily usage hashes are kept 8 days
STATS_TTL_SECONDS = 2 * 3600  # per-minute rejection stats are kept 2 hours
STATS_WINDOW_MINUTES = 60
USAGE_DAYS = 7
RATE_LIMIT_HEADERS = ("RateLimit-Limit", "RateLimit-Remaining", "RateLimit-Reset", "Retry-After")

# KEYS[1] bucket, KEYS[2] usage hash or "", KEYS[3] rejection stats hash or ""
# ARGV[1] limit, ARGV[2] period (ms), ARGV[3] cost, ARGV[4] stats field,
# ARGV[5] usage TTL (s), ARGV[6] stats TTL (s), ARGV[7] now (ms) or "" for Redis TIME
# Returns {allowed (0/1), remaining, reset (ms until the bucket is full), retry after (ms)}.
GCRA_LUA = """
local limit = tonumber(ARGV[1])
local period = tonumber(ARGV[2])
local cost = tonumber(ARGV[3])
local now
if ARGV[7] ~= '' then
  now = tonumber(ARGV[7])
else
  local t = redis.call('TIME')
  now = tonumber(t[1]) * 1000 + tonumber(t[2]) / 1000
end
local interval = period / limit
local eps = 0.01
local tat = tonumber(redis.call('GET', KEYS[1]))
if tat == nil or tat < now then tat = now end
local new_tat = tat + interval * cost
local allowed, remaining, reset, retry
if new_tat - period <= now + eps then
  allowed = 1
  redis.call('SET', KEYS[1], string.format('%.3f', new_tat), 'PX', math.ceil(new_tat - now))
  remaining = math.floor((now + period - new_tat) / interval + eps)
  reset = new_tat - now
  retry = 0
else
  allowed = 0
  remaining = math.floor((now + period - tat) / interval + eps)
  reset = tat - now
  retry = new_tat - period - now
  if KEYS[3] ~= '' then
    redis.call('HINCRBY', KEYS[3], ARGV[4], 1)
    redis.call('EXPIRE', KEYS[3], tonumber(ARGV[6]))
  end
end
if KEYS[2] ~= '' then
  if allowed == 1 then
    redis.call('HINCRBY', KEYS[2], 'requests', 1)
  else
    redis.call('HINCRBY', KEYS[2], 'rejected', 1)
  end
  redis.call('EXPIRE', KEYS[2], tonumber(ARGV[5]))
end
if remaining < 0 then remaining = 0 end
return {allowed, remaining, math.ceil(reset), math.ceil(retry)}
"""


class LimiterUnavailable(Exception):
    """Redis could not be reached; the caller fails open or closed."""


@dataclass(frozen=True)
class Decision:
    allowed: bool
    limit: int
    remaining: int
    reset_seconds: int  # until the bucket is full again
    retry_after: int  # seconds until this request would be allowed (0 when allowed)

    def headers(self) -> dict[str, str]:
        headers = {
            "RateLimit-Limit": str(self.limit),
            "RateLimit-Remaining": str(self.remaining),
            "RateLimit-Reset": str(self.reset_seconds),
        }
        if not self.allowed:
            headers["Retry-After"] = str(self.retry_after)
        return headers


class RateLimitExceeded(Exception):
    """Turned into a 429 by the handler in app.main."""

    def __init__(self, decision: Decision) -> None:
        super().__init__("Rate limit exceeded")
        self.decision = decision


def _ceil_seconds(ms: int) -> int:
    return max(0, math.ceil(ms / 1000))


class FailOpenMetrics:
    """Process-local count of requests let through because Redis was down (kept in memory:
    Redis is exactly what is unavailable when this happens)."""

    def __init__(self) -> None:
        self.total = 0
        self._recent: deque[float] = deque(maxlen=100_000)
        self._last_log = 0.0

    def record(self, what: str, exc: BaseException) -> None:
        now = time.monotonic()
        self.total += 1
        self._recent.append(now)
        if now - self._last_log >= 10:  # one warning per 10 s, not one per request
            self._last_log = now
            logger.warning("Rate limiter unavailable (%s), failing open: %r", what, exc)

    def last_hour(self) -> int:
        cutoff = time.monotonic() - 3600
        while self._recent and self._recent[0] < cutoff:
            self._recent.popleft()
        return len(self._recent)


fail_open = FailOpenMetrics()

# Tests freeze the limiter's clock (milliseconds); None = Redis' own clock (TIME).
clock_ms: Callable[[], float] | None = None


def key(*parts: object) -> str:
    return ":".join([get_settings().rate_limit_key_prefix, *(str(p) for p in parts)])


def usage_key(api_key_id: uuid.UUID, day: date) -> str:
    return key("usage", api_key_id, day.isoformat())


def stats_key(minute: int) -> str:
    return key("stats", minute)


def _current_minute() -> int:
    return int(time.time() // 60)


async def hit(
    redis: Redis,
    bucket: str,
    limit: int,
    *,
    cost: int = 1,
    tier: str,
    group: str,
    api_key_id: uuid.UUID | None = None,
) -> Decision:
    """Spend ``cost`` units of ``bucket`` (``limit`` per minute). A cost above the limit is
    capped at the limit, so an expensive request is still possible with a tiny custom limit."""
    cost = max(1, min(cost, limit))
    keys = [
        key("b", bucket),
        usage_key(api_key_id, datetime.now(UTC).date()) if api_key_id else "",
        stats_key(_current_minute()),
    ]
    args = [limit, PERIOD_SECONDS * 1000, cost, f"{tier}|{group}"]
    args += [USAGE_TTL_SECONDS, STATS_TTL_SECONDS, "" if clock_ms is None else repr(clock_ms())]
    try:
        script = redis.register_script(GCRA_LUA)  # EVALSHA, loading the script when missing
        allowed, remaining, reset_ms, retry_ms = await script(keys=keys, args=args)
    except (RedisError, OSError) as exc:
        raise LimiterUnavailable(str(exc)) from exc
    return Decision(
        allowed=bool(allowed),
        limit=limit,
        remaining=int(remaining),
        reset_seconds=_ceil_seconds(reset_ms),
        retry_after=max(1, _ceil_seconds(retry_ms)) if not allowed else 0,
    )


async def record_rejection(redis: Redis, tier: str, group: str) -> None:
    """Count a rejection that did not go through :func:`hit` (e.g. WebSocket concurrency)."""
    stats = stats_key(_current_minute())
    try:
        async with redis.pipeline(transaction=False) as pipe:
            pipe.hincrby(stats, f"{tier}|{group}", 1)
            pipe.expire(stats, STATS_TTL_SECONDS)
            await pipe.execute()
    except (RedisError, OSError):
        pass  # stats only


async def rejection_stats(redis: Redis) -> dict:
    """429s of the last hour by tier and route group (all API processes)."""
    now = _current_minute()
    async with redis.pipeline(transaction=False) as pipe:
        for minute in range(now - STATS_WINDOW_MINUTES + 1, now + 1):
            pipe.hgetall(stats_key(minute))
        buckets = await pipe.execute()
    pairs: dict[tuple[str, str], int] = {}
    for bucket in buckets:
        for field, count in bucket.items():
            tier, _, group = field.partition("|")
            pairs[tier, group] = pairs.get((tier, group), 0) + int(count)
    by_tier: dict[str, int] = {}
    by_group: dict[str, int] = {}
    for (tier, group), count in pairs.items():
        by_tier[tier] = by_tier.get(tier, 0) + count
        by_group[group] = by_group.get(group, 0) + count
    return {
        "total": sum(pairs.values()),
        "by_tier": by_tier,
        "by_group": by_group,
        "by_tier_and_group": [
            {"tier": tier, "group": group, "count": count}
            for (tier, group), count in sorted(pairs.items())
        ],
    }


async def daily_usage(redis: Redis, api_key_id: uuid.UUID, today: date | None = None) -> list:
    """``[{date, requests, rejected}]`` of the last 7 days, oldest first."""
    today = today or datetime.now(UTC).date()
    days = [today - timedelta(days=n) for n in range(USAGE_DAYS - 1, -1, -1)]
    async with redis.pipeline(transaction=False) as pipe:
        for day in days:
            pipe.hgetall(usage_key(api_key_id, day))
        rows = await pipe.execute()
    return [
        {
            "date": day.isoformat(),
            "requests": int(row.get("requests", 0)),
            "rejected": int(row.get("rejected", 0)),
        }
        for day, row in zip(days, rows, strict=True)
    ]


# --- login lockout -------------------------------------------------------------------------

# KEYS[1] failure counter, KEYS[2] lock; ARGV[1] max failures, ARGV[2] window (s), ARGV[3] lock (s)
# Returns 1 when this failure locked the email.
LOGIN_FAILURE_LUA = """
local n = redis.call('INCR', KEYS[1])
if n == 1 then redis.call('EXPIRE', KEYS[1], tonumber(ARGV[2])) end
if n >= tonumber(ARGV[1]) then
  redis.call('SET', KEYS[2], '1', 'EX', tonumber(ARGV[3]))
  redis.call('DEL', KEYS[1])
  return 1
end
return 0
"""

# --- WebSocket connections per identity ----------------------------------------------------

# A sorted set per identity: member = connection id, score = last heartbeat (ms). Entries of
# connections whose process died stop being refreshed and expire after ``stale`` ms.
# KEYS[1] set; ARGV[1] max, ARGV[2] member, ARGV[3] stale (ms). Returns 1 if the slot was taken.
WS_ACQUIRE_LUA = """
local t = redis.call('TIME')
local now = tonumber(t[1]) * 1000 + math.floor(tonumber(t[2]) / 1000)
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - tonumber(ARGV[3]))
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[1]) then return 0 end
redis.call('ZADD', KEYS[1], now, ARGV[2])
redis.call('PEXPIRE', KEYS[1], tonumber(ARGV[3]))
return 1
"""

WS_TOUCH_LUA = """
local t = redis.call('TIME')
local now = tonumber(t[1]) * 1000 + math.floor(tonumber(t[2]) / 1000)
redis.call('ZADD', KEYS[1], 'XX', now, ARGV[1])
redis.call('PEXPIRE', KEYS[1], tonumber(ARGV[2]))
return 1
"""
