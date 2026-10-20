"""Economic calendar (B6): versioned storage, point-in-time reads, the live refresh.

docs/economic-calendar.md describes the rules. In short:

- every row is one *version* of an event as known at ``fetched_at``; a new row is inserted only
  when the version hash changes (``UNIQUE (event_key, content_hash)`` + ``ON CONFLICT DO
  NOTHING``), so fetching the same data again inserts nothing;
- what was known at T is, per ``event_key``, the newest row with ``fetched_at <= T``;
- the live refresh makes one request per ``CALENDAR_FETCH_INTERVAL_MINUTES`` under a Redis
  lock, and none at all for ``CALENDAR_BACKOFF_HOURS`` after a 429/403.
"""

from __future__ import annotations

import json
import logging
import secrets
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import DateTime, Select, and_, cast, func, or_, select, text
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import aliased

from app.calendar import forexfactory
from app.calendar.events import (
    EventIn,
    calendar_date,
    impacts_at_least,
    normalise_title,
    source_family,
    week_start,
)
from app.core.config import get_settings
from app.models.economic_event import EconomicEvent, EventSource

logger = logging.getLogger(__name__)

# Redis state of the live refresh (shown by GET /admin/system/status); the clients decode
# responses to str
LOCK_KEY = "cal:lock"
DUE_KEY = "cal:attempted"  # set on every attempt, expires after the interval: no key = due
BACKOFF_KEY = "cal:backoff_until"
ETAG_KEY = "cal:etag"
LAST_OK_KEY = "cal:last_ok"
LAST_ERROR_KEY = "cal:last_error"
LOCK_SECONDS = 120
INSERT_CHUNK = 5000
STATE_TTL = 30 * 24 * 3600
# A revision moves an event at most within its week: the read query looks this far around the
# asked range for versions whose newest one may have moved into it.
MOVE_SLACK = timedelta(days=8)
RELEASE_LOCK = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) end return 0"
)


# --- writing ---------------------------------------------------------------------------------

# One statement per chunk with an array per column: the SQL text never changes, so it is
# prepared once (a multi-row VALUES, or the ORM bulk path, rebuilds or repeats it per chunk).
_COLUMNS = {
    "event_key": "varchar",
    "source": "varchar",
    "currency": "varchar",
    "title": "varchar",
    "impact": "varchar",
    "scheduled_at": "timestamptz",
    "scheduled_date": "date",
    "time_label": "varchar",
    "actual": "varchar",
    "forecast": "varchar",
    "previous": "varchar",
    "actual_value": "double precision",
    "forecast_value": "double precision",
    "previous_value": "double precision",
    "fetched_at": "timestamptz",
    "content_hash": "varchar",
}
_INSERT = text(
    f"INSERT INTO economic_events ({', '.join(_COLUMNS)}) "
    "SELECT * FROM unnest("
    + ", ".join(f"CAST(:{name} AS {kind}[])" for name, kind in _COLUMNS.items())
    + ") ON CONFLICT (event_key, content_hash) DO NOTHING RETURNING id"
)


async def _assign_keys(session: AsyncSession, events: Sequence[EventIn]) -> list[str]:
    """The ``event_key`` of every event. Live events whose natural key is unknown are matched to
    an existing event of the same currency and title in the same week that this fetch no longer
    shows at its old time (it moved). History rows use their natural key."""
    keys = [e.natural_key for e in events]
    live = [i for i, e in enumerate(events) if e.source == EventSource.forexfactory_live]
    if not live:
        return keys
    days = [events[i].scheduled_date for i in live]
    first, last = week_start(min(days)), week_start(max(days)) + timedelta(days=6)
    family = [s.value for s in EventSource if source_family(s.value) == "forexfactory"]
    latest = (
        select(
            EconomicEvent.event_key,
            EconomicEvent.currency,
            EconomicEvent.title,
            EconomicEvent.scheduled_date,
            EconomicEvent.scheduled_at,
        )
        .where(
            EconomicEvent.source.in_(family),
            EconomicEvent.scheduled_date.between(
                first - timedelta(days=7), last + timedelta(days=7)
            ),
        )
        .ext(distinct_on(EconomicEvent.event_key))
        .order_by(EconomicEvent.event_key, EconomicEvent.fetched_at.desc())
    )
    existing = {row.event_key: row for row in (await session.execute(latest)).all()}
    claimed = {keys[i] for i in live if keys[i] in existing}
    for i in live:
        if keys[i] in existing:
            continue
        event = events[i]
        title, week = normalise_title(event.title), week_start(event.scheduled_date)
        candidates = [
            row
            for key, row in existing.items()
            if key not in claimed
            and row.currency == event.currency
            and normalise_title(row.title) == title
            and week_start(row.scheduled_date) == week
        ]
        if candidates:
            nearest = min(
                candidates, key=lambda r: abs((r.scheduled_date - event.scheduled_date).days)
            )
            keys[i] = nearest.event_key
            claimed.add(nearest.event_key)
    return keys


async def upsert_versions(
    session: AsyncSession, events: Sequence[EventIn], fetched_at: datetime | None = None
) -> dict[str, int]:
    """Store the versions that are new; one transaction, idempotent. ``fetched_at`` applies to
    the events that do not carry their own (history rows do)."""
    fetched_at = fetched_at or datetime.now(UTC)
    if not events:
        return {"inserted": 0, "unchanged": 0}
    keys = await _assign_keys(session, events)
    rows, seen = [], set()
    for event, key in zip(events, keys, strict=True):
        row = event.row(key, fetched_at)
        if (key, row["content_hash"]) in seen:
            continue
        seen.add((key, row["content_hash"]))
        rows.append(row)
    inserted = 0
    for i in range(0, len(rows), INSERT_CHUNK):
        chunk = rows[i : i + INSERT_CHUNK]
        result = await session.execute(
            _INSERT, {name: [r[name] for r in chunk] for name in _COLUMNS}
        )
        inserted += len(result.all())
    await session.commit()
    return {"inserted": inserted, "unchanged": len(events) - inserted}


# --- reading ---------------------------------------------------------------------------------


def _latest(as_of: datetime, start: datetime, end: datetime) -> Select:
    """Per event, the newest version known at ``as_of``, among the events with a version
    near the range (a revision moves an event at most within its week)."""
    near = select(EconomicEvent.event_key).where(
        EconomicEvent.scheduled_date.between(
            calendar_date(start - MOVE_SLACK), calendar_date(end + MOVE_SLACK)
        )
    )
    return (
        select(EconomicEvent)
        .where(EconomicEvent.fetched_at <= as_of, EconomicEvent.event_key.in_(near))
        .ext(distinct_on(EconomicEvent.event_key))
        .order_by(
            EconomicEvent.event_key,
            EconomicEvent.fetched_at.desc(),
            EconomicEvent.content_hash,
        )
    )


async def latest_as_of(
    session: AsyncSession,
    start: datetime,
    end: datetime,
    *,
    as_of: datetime | None = None,
    currencies: Sequence[str] | None = None,
    min_impact: str = "low",
    timed_only: bool = False,
) -> list[EconomicEvent]:
    """What was known at ``as_of`` (default now) about the events scheduled in
    ``[start, end]``: per ``event_key`` the newest version with ``fetched_at <= as_of``, with
    the range, currency and impact filters applied to that version. One query. Events without
    a time (All Day, Tentative) are included by their New York day unless ``timed_only``."""
    as_of = as_of or datetime.now(UTC)
    latest = aliased(EconomicEvent, _latest(as_of, start, end).subquery())
    in_range = latest.scheduled_at.between(start, end)
    if not timed_only:
        in_range = or_(
            in_range,
            and_(
                latest.scheduled_at.is_(None),
                latest.scheduled_date.between(calendar_date(start), calendar_date(end)),
            ),
        )
    conditions = [in_range, latest.impact.in_(impacts_at_least(min_impact))]
    if currencies:
        conditions.append(latest.currency.in_([c.upper() for c in currencies]))
    # events without a time sort at the start of their New York day
    day_start = func.timezone("America/New_York", cast(latest.scheduled_date, DateTime()))
    statement = (
        select(latest)
        .where(*conditions)
        .order_by(func.coalesce(latest.scheduled_at, day_start), latest.currency, latest.title)
    )
    return list((await session.scalars(statement)).all())


def evaluate_item(event: EconomicEvent) -> dict[str, str]:
    """The shape the AI engine reads in ``POST /v1/evaluate`` (``calendar`` items)."""
    return {
        "ts": event.scheduled_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "currency": event.currency,
        "impact": event.impact,
        "title": event.title,
    }


async def for_evaluate(
    session: AsyncSession,
    bar_ts: datetime,
    *,
    window: timedelta = timedelta(hours=6),
    as_of: datetime | None = None,
    min_impact: str = "medium",
    currencies: Sequence[str] | None = None,
) -> list[dict[str, str]]:
    """The ``calendar`` list of an evaluate request (B9): the events with a time between
    ``bar_ts - window`` and ``bar_ts + window``, as known at ``as_of`` (default now; a backtest
    passes the bar's time), of ``CALENDAR_CURRENCIES`` and at least ``min_impact``. The AI
    engine abstains within ±30 minutes of a ``high`` event; ``medium`` is passed too so it can
    use them as features."""
    events = await latest_as_of(
        session,
        bar_ts - window,
        bar_ts + window,
        as_of=as_of,
        currencies=currencies or get_settings().calendar_currency_list,
        min_impact=min_impact,
        timed_only=True,
    )
    return [evaluate_item(e) for e in events]


async def history(session: AsyncSession, key: str) -> list[EconomicEvent]:
    """Every version of an event, oldest first."""
    rows = await session.scalars(
        select(EconomicEvent)
        .where(EconomicEvent.event_key == key)
        .order_by(EconomicEvent.fetched_at, EconomicEvent.content_hash)
    )
    return list(rows.all())


async def table_stats(session: AsyncSession) -> dict[str, Any]:
    count, newest = (
        await session.execute(
            select(func.count(), func.max(EconomicEvent.fetched_at)).select_from(EconomicEvent)
        )
    ).one()
    return {"rows": count, "newest_fetched_at": newest.isoformat() if newest else None}


# --- the live refresh ------------------------------------------------------------------------


async def _get_json(redis: Redis, key: str) -> Any:
    raw = await redis.get(key)
    return json.loads(raw) if raw else None


async def state(redis: Redis) -> dict[str, Any]:
    """The refresh state kept in Redis (admin system status)."""
    return {
        "enabled": get_settings().calendar_enabled,
        "interval_minutes": get_settings().calendar_fetch_interval_minutes,
        "last_success": await _get_json(redis, LAST_OK_KEY),
        "last_error": await _get_json(redis, LAST_ERROR_KEY),
        "backoff_until": await redis.get(BACKOFF_KEY),
        "next_due_in_seconds": max(0, await redis.ttl(DUE_KEY)),
    }


async def refresh(
    factory: async_sessionmaker[AsyncSession],
    redis: Redis,
    *,
    now: datetime | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """One live fetch if due (``force``: now, still not during a back-off) and store the new
    versions. Never raises for a fetch problem: the answer says what happened."""
    settings = get_settings()
    now = now or datetime.now(UTC)
    if not settings.calendar_enabled:
        return {"status": "disabled"}
    until = await redis.get(BACKOFF_KEY)
    if until and now < datetime.fromisoformat(until):
        logger.debug("calendar: backing off until %s", until)
        return {"status": "backoff", "until": until}
    if not force and await redis.exists(DUE_KEY):
        return {"status": "not_due", "next_in_seconds": max(0, await redis.ttl(DUE_KEY))}
    token = secrets.token_hex(8)
    if not await redis.set(LOCK_KEY, token, nx=True, ex=LOCK_SECONDS):
        return {"status": "locked"}
    try:
        interval = max(60, settings.calendar_fetch_interval_minutes * 60)
        await redis.set(DUE_KEY, now.isoformat(), ex=interval)
        return await _fetch_and_store(factory, redis, now)
    finally:
        await redis.eval(RELEASE_LOCK, 1, LOCK_KEY, token)


async def _fetch_and_store(
    factory: async_sessionmaker[AsyncSession], redis: Redis, now: datetime
) -> dict[str, Any]:
    settings = get_settings()
    try:
        week = await forexfactory.fetch_week(etag=await redis.get(ETAG_KEY))
    except forexfactory.Blocked as exc:
        until = now + timedelta(hours=settings.calendar_backoff_hours)
        seconds = max(60, int((until - now).total_seconds()))
        await redis.set(BACKOFF_KEY, until.isoformat(), ex=seconds)
        await _error(redis, now, f"{exc} (backing off until {until.isoformat()})")
        logger.warning("calendar: ForexFactory answered %s; no request until %s", exc.status, until)
        return {"status": "blocked", "http_status": exc.status, "until": until.isoformat()}
    except forexfactory.FetchError as exc:
        await _error(redis, now, str(exc))
        logger.warning("calendar: fetch failed: %s", exc)
        return {"status": "error", "error": str(exc)}
    if week.status == "not_modified":
        result = {"status": "not_modified", "inserted": 0, "unchanged": 0}
    else:
        try:
            async with factory() as session:
                counts = await upsert_versions(session, week.events, now)
        except Exception as exc:  # noqa: BLE001 - reported, the next run tries again
            logger.exception("calendar: storing the week failed")
            await _error(redis, now, f"store: {type(exc).__name__}")
            return {"status": "error", "error": f"store: {type(exc).__name__}"}
        if week.etag:
            await redis.set(ETAG_KEY, week.etag, ex=24 * 3600)
        result = {
            "status": "ok",
            "items": week.items,
            "skipped": len(week.skipped),
            **counts,
        }
    await redis.set(LAST_OK_KEY, json.dumps({"at": now.isoformat(), **result}), ex=STATE_TTL)
    logger.info(
        "calendar.refresh %s inserted=%d unchanged=%d skipped=%d",
        result["status"],
        result["inserted"],
        result["unchanged"],
        result.get("skipped", 0),
    )
    return result


async def _error(redis: Redis, now: datetime, error: str) -> None:
    await redis.set(
        LAST_ERROR_KEY, json.dumps({"at": now.isoformat(), "error": error}), ex=STATE_TTL
    )
