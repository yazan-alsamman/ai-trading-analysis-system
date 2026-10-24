"""The periodic evaluation (B9, docs/ai-contract.md#8-the-evaluate-task).

At each 15m boundary the ``ai.evaluate_tick`` beat task schedules one ``ai.evaluate`` per
instrument (``AI_EVALUATE_INSTRUMENTS``) and profile (``AI_PROFILES``), ``AI_EVALUATE_DELAY_
SECONDS`` after the boundary. One run (:func:`run`):

1. **One run per key.** A Redis key ``(instrument, profile, bar_close_ts)`` set with NX and an
   expiry: a retried or duplicated task finds it and does nothing.
2. **The request** (:func:`build_request`), or a **skip** recorded as a local abstention (the
   shape of an ai-service answer with ``status: data_quality_failed``) without calling
   ai-service: no specs, the bars are not closed yet, the data-quality gate is not ok (closed
   market, degraded, no data), the decision bar is missing or has no spread.
   - bars cut at the last closed bar (the aggregates are ``materialized_only = false``): the
     counts from ``AI_BARS_*``, the spread of each bar the average of its 1m spreads;
   - ``1d``: New York trading days (17:00 to 17:00 America/New_York), built on the fly from
     the 1h aggregate (itself from the 1m data; the boundary is always on a UTC hour, so the
     result is the same as from 1m);
   - ``calendar`` (B6 ``for_evaluate``), ``open_setups`` (the store), ``instrument_spec`` (B4)
     and the deterministic ``request_id``.
3. **ai-service** ``/v1/evaluate`` through the client (timeouts, retries). A 404 or a refused
   connection means ai-service has no ``/v1/evaluate`` yet: ``unavailable``, logged at most
   once an hour, not an error. A 422 or a body outside the contract: ``contract_error``,
   logged as an error and flagged in ``/admin/system/status``.
4. ``store.apply_evaluation`` (one transaction), then, after its commit: ``alerts.kick()``,
   the sizes of the followers (setups that became ARMED) and of the takers (ACTIVE), and one
   ``ai.explain`` per newly ARMED setup and language. None of these can fail the run.
5. The run is stored in ``ai_evaluation_runs`` (status, reason, duration, request size, bar
   coverage, a summary of the answer).
"""

from __future__ import annotations

import json
import logging
import math
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai import alerts, sizing, store
from app.ai.client import AIContractError, AIServiceClient, AIUnavailableError
from app.ai.contract import (
    TIMEFRAMES,
    EvaluateRequest,
    EvaluateResponse,
    d1_open,
    iso_z,
    make_request_id,
)
from app.ai.specs import MissingSpecs, instrument_spec
from app.calendar import service as calendar_service
from app.core.config import get_settings
from app.models.ai import AIEvaluationRun, AISetup
from app.models.candle import Timeframe
from app.models.instrument import Instrument
from app.services import data_quality, market_service, sessions
from app.services.data_quality import QualityStatus
from app.services.market_service import floor_to_bucket

logger = logging.getLogger(__name__)

DECISION = "15m"  # the decision bar: the smallest timeframe, its close is bar_close_ts
STEP = TIMEFRAMES[DECISION]
LOCK_KEY = "ai:evaluate:run:"  # + instrument:profile:bar_close_ts -> set once per run
LOCK_SECONDS = 6 * 3600
UNREACHABLE_KEY = "ai:evaluate:unreachable-logged"  # set: logged within the hour
UNREACHABLE_LOG_SECONDS = 3600
CONTRACT_ERROR_KEY = "ai:evaluate:contract-error"  # the last contract error (JSON)
CONTRACT_ERROR_TTL = 7 * 24 * 3600
MAX_OPEN_SETUPS = 200
MAX_CALENDAR = 500
# what a local abstention says it comes from (the backend never claims a model)
LOCAL_VERSIONS = {"strategy": "backend", "model": None, "features": "none"}
REFUSED = "connection error (ConnectError)"


def contract_symbol(instrument: Instrument) -> str:
    """``XAU/USD`` -> ``XAUUSD`` (the contract's ``[A-Z0-9]{3,16}``)."""
    return re.sub(r"[^A-Z0-9]", "", instrument.symbol.upper())[:16]


def decision_bar_close(now: datetime) -> datetime:
    """The close of the last 15m bar at ``now`` (the boundary the tick fired on)."""
    return floor_to_bucket(now.astimezone(UTC), STEP)


# --- the request ---------------------------------------------------------------------------------


@dataclass
class Skip:
    """Why ai-service is not called; recorded as a local abstention."""

    reason: str
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class Built:
    request: EvaluateRequest | None
    coverage: dict[str, dict[str, Any]]
    skip: Skip | None = None
    body_bytes: int | None = None


def _bar(ts: datetime, o: float, h: float, lo: float, c: float, spread: float | None) -> dict:
    return {"ts": iso_z(ts), "o": o, "h": h, "l": lo, "c": c, "spread": spread}


async def _spreads(
    session: AsyncSession, instrument: Instrument, start: datetime, end: datetime
) -> dict[datetime, tuple[float, int]]:
    """15m bucket -> (sum, count) of the 1m spreads in ``[start, end)``: one query, the larger
    timeframes add up the 15m buckets they contain."""
    rows = await session.execute(
        text(
            "SELECT time_bucket(INTERVAL '15 minutes', ts) AS b, sum(spread), count(spread) "
            "FROM candles_1m WHERE instrument_id = :id AND ts >= :start AND ts < :end "
            "AND spread IS NOT NULL GROUP BY b"
        ),
        {"id": instrument.id, "start": start, "end": end},
    )
    return {b: (float(total), int(n)) for b, total, n in rows.all()}


def _spread(
    spreads: dict[datetime, tuple[float, int]], start: datetime, step: timedelta
) -> float | None:
    total = count = 0.0
    k = start
    while k < start + step:
        if k in spreads:
            total += spreads[k][0]
            count += spreads[k][1]
        k += STEP
    return None if not count else round(total / count, 10)


async def _closed_bars(
    session: AsyncSession, instrument: Instrument, tf: str, count: int, bar_close_ts: datetime
) -> list[market_service.CandleRow]:
    """The last ``count`` bars of ``tf`` closed at ``bar_close_ts``, oldest first (the
    forming bucket of a ``materialized_only = false`` aggregate is cut)."""
    step = TIMEFRAMES[tf]
    return await market_service.get_candles(
        session, instrument.id, Timeframe(tf), end=bar_close_ts - step, limit=count
    )


async def _daily_bars(
    session: AsyncSession, instrument: Instrument, count: int, bar_close_ts: datetime
) -> list[tuple]:
    """The last ``count`` New York trading days (17:00 to 17:00 America/New_York) closed at
    ``bar_close_ts``, from the 1h aggregate: ``(open_ts, o, h, l, c)``, oldest first."""
    end = d1_open(bar_close_ts)  # the trading day still running is left out
    start = end - timedelta(days=math.ceil(count * 7 / 5) + 14)  # weekends and holidays
    rows = await session.execute(
        text(
            "SELECT (date_trunc('day', (ts AT TIME ZONE 'America/New_York') "
            "+ INTERVAL '7 hours') - INTERVAL '7 hours') AT TIME ZONE 'America/New_York' AS d, "
            "first(open, ts), max(high), min(low), last(close, ts) "
            "FROM candles_1h WHERE instrument_id = :id AND ts >= :start AND ts < :end "
            "GROUP BY d ORDER BY d"
        ),
        {"id": instrument.id, "start": start, "end": end},
    )
    return [tuple(r) for r in rows.all()][-count:]


async def build_request(
    session: AsyncSession,
    instrument: Instrument,
    profile: str,
    bar_close_ts: datetime,
    now: datetime | None = None,
) -> Built:
    """The evaluate request of the bar closing at ``bar_close_ts``, or why there is none."""
    now = (now or datetime.now(UTC)).astimezone(UTC)
    settings = get_settings()
    counts = settings.ai_bar_counts
    coverage: dict[str, dict[str, Any]] = {}
    try:
        spec = instrument_spec(instrument)
    except MissingSpecs as exc:
        return Built(None, coverage, Skip("no_specs", {"message": str(exc)}))
    watermark = await market_service.closed_watermark(session, instrument, now)
    if watermark is None or watermark < bar_close_ts:
        detail = {"watermark": iso_z(watermark) if watermark else None}
        return Built(None, coverage, Skip("bars_not_closed", detail))
    report = await data_quality.load_and_assess(
        session, instrument, Timeframe.m15, now, bar=bar_close_ts - STEP
    )
    detail = {
        "status": report.status.value,
        "failed": [{"check": c.name, "detail": c.detail} for c in report.failed],
    }
    if report.status == QualityStatus.closed:
        # the market is closed now: a bar that traded before the break is still evaluated
        cal = (
            sessions.calendar_of(instrument.session_calendar)
            if instrument.session_calendar
            else data_quality.ALWAYS_OPEN
        )
        expected = sessions.expected_bar_starts(cal, bar_close_ts - STEP, bar_close_ts)
        if next(iter(expected), None) is None:
            return Built(None, coverage, Skip("market_closed", detail))
    if report.failed:
        return Built(None, coverage, Skip("data_quality_degraded", detail))

    rows = {
        tf: await _closed_bars(session, instrument, tf, n, bar_close_ts)
        for tf, n in counts.items()
        if tf != "1d"
    }
    decision = rows.get(DECISION) or []
    if not decision or decision[-1].ts != bar_close_ts - STEP:
        last = iso_z(decision[-1].ts) if decision else None
        return Built(None, coverage, Skip("decision_bar_missing", {"last_15m_bar": last}))
    oldest = min((r[0].ts for r in rows.values() if r), default=bar_close_ts - STEP)
    spreads = await _spreads(session, instrument, oldest, bar_close_ts)
    bars: dict[str, list[dict]] = {}
    for tf, candles in rows.items():
        step = TIMEFRAMES[tf]
        bars[tf] = [
            _bar(r.ts, r.open, r.high, r.low, r.close, _spread(spreads, r.ts, step))
            for r in candles
        ]
    if bars[DECISION][-1]["spread"] is None:
        detail = {"bar": bars[DECISION][-1]["ts"]}
        return Built(None, coverage, Skip("decision_bar_no_spread", detail))
    if counts.get("1d"):
        days = await _daily_bars(session, instrument, counts["1d"], bar_close_ts)
        if days:
            bars["1d"] = [_bar(d, o, h, lo, c, None) for d, o, h, lo, c in days]
    for tf, n in counts.items():
        sent = bars.get(tf, [])
        coverage[tf] = {
            "requested": n,
            "sent": len(sent),
            "from": sent[0]["ts"] if sent else None,
            "short": len(sent) < n,
        }
    short = {tf: c["sent"] for tf, c in coverage.items() if c["short"]}
    if short:
        logger.warning(
            "ai evaluate %s:%s %s: short history, sending what exists %s",
            instrument.source,
            instrument.symbol,
            iso_z(bar_close_ts),
            short,
        )
    bars = {tf: b for tf, b in bars.items() if b}

    open_setups = await store.open_setups(session, instrument, profile)
    if len(open_setups) > MAX_OPEN_SETUPS:
        logger.warning("ai evaluate: %d open setups, the newest 200 sent", len(open_setups))
        open_setups = open_setups[-MAX_OPEN_SETUPS:]
    calendar = await calendar_service.for_evaluate(session, bar_close_ts)
    symbol = contract_symbol(instrument)
    request = EvaluateRequest.model_validate(
        {
            "request_id": make_request_id(symbol, profile, bar_close_ts),
            "instrument": symbol,
            "profile": profile,
            "bar_close_ts": iso_z(bar_close_ts),
            "bars": bars,
            "open_setups": open_setups,
            "calendar": calendar[:MAX_CALENDAR],
            "instrument_spec": spec.model_dump(mode="json"),
        }
    )
    return Built(request, coverage, body_bytes=len(AIServiceClient.encode(request)))


def local_abstention(request_id: str, skip: Skip) -> dict[str, Any]:
    """A skip in the shape of an ai-service answer (the run stays visible)."""
    return {
        "request_id": request_id,
        "status": "data_quality_failed",
        "versions": LOCAL_VERSIONS,
        "new_setups": [],
        "transitions": [],
        "abstentions": [{"reason": skip.reason, "detail": skip.detail}],
        "source": "backend",
    }


# --- one run -------------------------------------------------------------------------------------


@dataclass
class RunResult:
    status: str  # ok | abstained | skipped | unavailable | contract_error | error | duplicate
    reason: str | None = None
    request_id: str | None = None
    duration_ms: int | None = None
    request_bytes: int | None = None
    coverage: dict[str, Any] = field(default_factory=dict)
    detail: dict[str, Any] = field(default_factory=dict)
    applied: store.ApplyResult | None = None
    after: dict[str, Any] = field(default_factory=dict)


def run_key(source: str, symbol: str, profile: str, bar_close_ts: datetime) -> str:
    return f"{LOCK_KEY}{source}:{symbol}:{profile}:{iso_z(bar_close_ts)}"


async def _log_unreachable(redis: Redis, message: str) -> None:
    """404 / connection refused: ai-service has no /v1/evaluate yet. At most once an hour."""
    try:
        first = await redis.set(UNREACHABLE_KEY, "1", nx=True, ex=UNREACHABLE_LOG_SECONDS)
    except Exception:  # noqa: BLE001 - Redis down: log it
        first = True
    if first:
        logger.warning("%s (logged at most once an hour)", message)
    else:
        logger.debug("%s", message)


async def _flag_contract_error(
    redis: Redis, instrument: str, profile: str, request_id: str, error: str, detail: Any
) -> None:
    value = {
        "at": iso_z(datetime.now(UTC)),
        "instrument": instrument,
        "profile": profile,
        "request_id": request_id,
        "error": error[:300],
        "detail": json.loads(json.dumps(detail, default=str))[:20]
        if isinstance(detail, list)
        else str(detail)[:500],
    }
    try:
        await redis.set(CONTRACT_ERROR_KEY, json.dumps(value), ex=CONTRACT_ERROR_TTL)
    except Exception:  # noqa: BLE001
        logger.exception("ai evaluate: could not flag the contract error")


def _summary(resp: EvaluateResponse, applied: store.ApplyResult) -> dict[str, Any]:
    return {
        "response_status": resp.status.value,
        "versions": resp.versions.model_dump(),
        "abstentions": [a.model_dump() for a in resp.abstentions][:20],
        "new_setups": len(resp.new_setups),
        "transitions": len(resp.transitions),
        "inserted": applied.inserted,
        "updated": applied.updated,
        "transitions_applied": applied.transitions_applied,
        "rejected": [{"setup_id": r.setup_id, "reason": r.reason} for r in applied.rejected][:20],
        "contract_errors": [
            {"setup_id": r.setup_id, "reason": r.reason} for r in applied.contract_errors
        ][:20],
        "state_changes": [
            {"setup_id": c.setup_id, "from": c.from_state, "to": c.to_state, "at": iso_z(c.at)}
            for c in applied.state_changes
        ][:50],
    }


async def _record(
    factory: async_sessionmaker[AsyncSession],
    instrument: Instrument,
    profile: str,
    bar_close_ts: datetime,
    result: RunResult,
    started: datetime,
) -> None:
    values = {
        "request_id": result.request_id
        or make_request_id(contract_symbol(instrument), profile, bar_close_ts),
        "status": result.status,
        "reason": (result.reason or None) and result.reason[:64],
        "request_bytes": result.request_bytes,
        "coverage": result.coverage,
        "detail": json.loads(json.dumps(result.detail, default=str)),
        "duration_ms": result.duration_ms,
        "started_at": started,
        "finished_at": datetime.now(UTC),
    }
    try:
        async with factory() as session:
            await session.execute(
                insert(AIEvaluationRun)
                .values(
                    instrument_id=instrument.id,
                    profile=profile,
                    bar_close_ts=bar_close_ts,
                    **values,
                )
                .on_conflict_do_update(
                    index_elements=["instrument_id", "profile", "bar_close_ts"], set_=values
                )
            )
            await session.commit()
    except Exception:  # noqa: BLE001 - the run itself is done; its record is best effort
        logger.exception("ai evaluate: recording the run failed")


async def after_commit(
    factory: async_sessionmaker[AsyncSession],
    applied: store.ApplyResult,
    *,
    client: AIServiceClient | None = None,
    kick: Callable[[], None] | None = None,
    schedule_explain: Callable[[str, str], None] | None = None,
) -> dict[str, Any]:
    """What follows a committed evaluation; every step is isolated, none raises:

    - ``alerts.kick()``: the outbox rows are sent now rather than within 30 s;
    - sizes (B10) of the followers of each setup that became ARMED, and of the takers of each
      setup that became ACTIVE (stored; the alerts reuse them);
    - one ``ai.explain`` per newly ARMED setup and ``AI_EXPLAIN_LANGS`` language."""
    out: dict[str, Any] = {"kick": False, "sized": {}, "explain": [], "errors": []}
    if not applied.state_changes:
        return out
    try:
        (kick or alerts.kick)()
        out["kick"] = True
    except Exception as exc:  # noqa: BLE001
        logger.exception("ai evaluate: kick failed")
        out["errors"].append(f"kick: {type(exc).__name__}")
    targets: dict[str, str] = {}
    for change in applied.state_changes:
        if change.to_state in ("ARMED", "ACTIVE"):
            targets[change.setup_id] = change.to_state
    for setup_id, state in targets.items():
        try:
            async with factory() as session:
                setup = await session.get(AISetup, setup_id)
                if setup is None or setup.state != state:
                    continue  # moved on in the same response (e.g. ARMED then ACTIVE)
                users = await alerts.recipients(session, setup, state)
                if users:
                    results = await sizing.size_setup_for_users(
                        session, setup, [u.id for u in users], client=client
                    )
                    out["sized"][setup_id] = sum(
                        isinstance(r, sizing.SizeResult) for r in results.values()
                    )
        except Exception as exc:  # noqa: BLE001 - e.g. no specs; the alert reports it per user
            logger.warning("ai evaluate: sizing %s failed: %s", setup_id, exc)
            out["errors"].append(f"size {setup_id}: {type(exc).__name__}")
    armed = [c.setup_id for c in applied.state_changes if c.to_state == "ARMED"]
    for setup_id in dict.fromkeys(armed):
        for lang in get_settings().ai_explain_lang_list:
            try:
                (schedule_explain or _schedule_explain)(setup_id, lang)
                out["explain"].append(f"{setup_id}/{lang}")
            except Exception as exc:  # noqa: BLE001
                logger.exception("ai evaluate: scheduling the explanation failed")
                out["errors"].append(f"explain {setup_id}/{lang}: {type(exc).__name__}")
    return out


def _schedule_explain(setup_id: str, lang: str) -> None:
    from app.tasks import celery_app  # noqa: PLC0415 - the tasks import this module

    celery_app.send_task("ai.explain", (setup_id, lang))


async def run(
    factory: async_sessionmaker[AsyncSession],
    redis: Redis,
    source: str,
    symbol: str,
    profile: str,
    bar_close_ts: datetime,
    *,
    now: datetime | None = None,
    client: AIServiceClient | None = None,
    kick: Callable[[], None] | None = None,
    schedule_explain: Callable[[str, str], None] | None = None,
) -> RunResult:
    """One evaluation of ``source:symbol`` / ``profile`` on the bar closing at
    ``bar_close_ts``. Never raises for ai-service or data problems: the outcome is the
    result's ``status`` (and its ``ai_evaluation_runs`` row)."""
    if not await redis.set(
        run_key(source, symbol, profile, bar_close_ts), "1", nx=True, ex=LOCK_SECONDS
    ):
        logger.info(
            "ai evaluate %s:%s/%s %s: already run (duplicate task)",
            source,
            symbol,
            profile,
            iso_z(bar_close_ts),
        )
        return RunResult("duplicate")
    started_at = datetime.now(UTC)
    clock = time.perf_counter()
    async with factory() as session:
        instrument = await session.scalar(
            select(Instrument).where(Instrument.source == source, Instrument.symbol == symbol)
        )
        if instrument is None:
            logger.warning("ai evaluate: unknown instrument %s:%s", source, symbol)
            return RunResult("skipped", "unknown_instrument")
        try:
            built = await build_request(session, instrument, profile, bar_close_ts, now)
        except Exception as exc:  # noqa: BLE001 - our bug: recorded, never retried blindly
            logger.exception("ai evaluate: building the request failed")
            built = None
            error = f"{type(exc).__name__}: {exc}"[:300]
    name = f"{source}:{symbol}"
    request_id = make_request_id(contract_symbol(instrument), profile, bar_close_ts)
    if built is None:
        result = RunResult("error", "request_build_failed", request_id, detail={"error": error})
    elif built.skip is not None:
        result = RunResult(
            "skipped",
            built.skip.reason,
            request_id,
            coverage=built.coverage,
            detail=local_abstention(request_id, built.skip),
        )
        logger.info("ai evaluate %s/%s %s: skipped (%s)", name, profile, request_id, built.skip)
    else:
        try:
            result = await _call_and_apply(
                factory, redis, instrument, profile, built, client=client, name=name
            )
        except Exception as exc:  # noqa: BLE001 - e.g. the database: recorded, not lost
            logger.exception("ai evaluate %s/%s %s: failed", name, profile, request_id)
            detail = {"error": f"{type(exc).__name__}: {exc}"[:300]}
            result = RunResult(
                "error",
                "apply_failed",
                request_id,
                request_bytes=built.body_bytes,
                coverage=built.coverage,
                detail=detail,
            )
    result.duration_ms = round((time.perf_counter() - clock) * 1000)
    await _record(factory, instrument, profile, bar_close_ts, result, started_at)
    if result.applied is not None:
        result.after = await after_commit(
            factory, result.applied, client=client, kick=kick, schedule_explain=schedule_explain
        )
    return result


async def _call_and_apply(
    factory: async_sessionmaker[AsyncSession],
    redis: Redis,
    instrument: Instrument,
    profile: str,
    built: Built,
    *,
    client: AIServiceClient | None,
    name: str,
) -> RunResult:
    req = built.request
    assert req is not None
    base = {
        "request_id": req.request_id,
        "request_bytes": built.body_bytes,
        "coverage": built.coverage,
    }
    own = client is None
    client = client or AIServiceClient()
    try:
        resp = await client.evaluate(req)
    except AIContractError as exc:
        if exc.status == 404:
            await _log_unreachable(redis, "ai-service has no /v1/evaluate yet (404)")
            return RunResult("unavailable", "no_evaluate_endpoint", **base)
        logger.error(
            "ai evaluate %s/%s %s: contract error: %s (%s)",
            name,
            profile,
            req.request_id,
            exc,
            exc.detail,
        )
        await _flag_contract_error(redis, name, profile, req.request_id, str(exc), exc.detail)
        detail = {"error": str(exc), "status": exc.status, "detail": exc.detail}
        return RunResult("contract_error", f"http_{exc.status}", detail=detail, **base)
    except AIUnavailableError as exc:
        if exc.last_error == REFUSED:
            await _log_unreachable(redis, "ai-service refuses connections (no /v1/evaluate yet?)")
            return RunResult("unavailable", "connection_refused", **base)
        logger.warning("ai evaluate %s/%s %s: %s", name, profile, req.request_id, exc)
        return RunResult("unavailable", exc.last_error[:64], detail={"error": str(exc)}, **base)
    finally:
        if own:
            await client.aclose()
    async with factory() as session:
        fresh = await session.get(Instrument, instrument.id)
        applied = await store.apply_evaluation(session, fresh, req, resp)
    if applied.contract_errors:
        reasons = [f"{e.setup_id}: {e.reason}" for e in applied.contract_errors]
        await _flag_contract_error(
            redis, name, profile, req.request_id, "state went backwards", reasons
        )
    status = "ok" if resp.status.value == "ok" else "abstained"
    reason = None if status == "ok" else resp.status.value
    result = RunResult(status, reason, detail=_summary(resp, applied), **base)
    result.applied = applied
    logger.info(
        "ai evaluate %s/%s %s: %s (%d bytes, %d new, %d transitions)",
        name,
        profile,
        req.request_id,
        resp.status.value,
        built.body_bytes or 0,
        applied.inserted,
        applied.transitions_applied,
    )
    return result


# --- the schedule --------------------------------------------------------------------------------


def targets() -> list[tuple[str, str, str]]:
    """``(source, symbol, profile)`` of every scheduled evaluation (empty when disabled)."""
    settings = get_settings()
    if not settings.ai_evaluate_enabled:
        return []
    return [
        (source, symbol, profile)
        for source, symbol in settings.ai_evaluate_instrument_list
        for profile in settings.ai_profile_list
    ]


def schedule(
    now: datetime, apply_async: Callable[..., Any]
) -> list[tuple[str, str, str, datetime]]:
    """The beat tick: one ``ai.evaluate`` per target for the bar closing at the boundary,
    ``AI_EVALUATE_DELAY_SECONDS`` after it. Returns what was scheduled."""
    bar_close_ts = decision_bar_close(now)
    eta = bar_close_ts + timedelta(seconds=get_settings().ai_evaluate_delay_seconds)
    out = []
    for source, symbol, profile in targets():
        apply_async((source, symbol, profile, iso_z(bar_close_ts)), eta=eta, expires=eta + STEP)
        out.append((source, symbol, profile, bar_close_ts))
    return out


# --- status --------------------------------------------------------------------------------------


async def status(session: AsyncSession, redis: Redis) -> dict[str, Any]:
    """The ``ai_evaluate`` block of ``/admin/system/status``: settings, the last run of every
    instrument and profile, counts of the last 24 h, and the last contract error."""
    settings = get_settings()
    rows = await session.execute(
        text(
            "SELECT DISTINCT ON (r.instrument_id, r.profile) i.source, i.symbol, r.profile, "
            "r.bar_close_ts, r.finished_at, r.status, r.reason, r.duration_ms, "
            "r.request_bytes, r.coverage "
            "FROM ai_evaluation_runs r JOIN instruments i ON i.id = r.instrument_id "
            "ORDER BY r.instrument_id, r.profile, r.bar_close_ts DESC"
        )
    )
    last = [
        {
            "instrument": f"{source}:{symbol}",
            "profile": profile,
            "bar_close_ts": iso_z(bar),
            "at": iso_z(at),
            "status": state,
            "reason": reason,
            "duration_ms": duration,
            "request_bytes": size,
            "coverage": {tf: c.get("sent") for tf, c in (coverage or {}).items()},
            "coverage_short": sorted(tf for tf, c in (coverage or {}).items() if c.get("short")),
        }
        for source, symbol, profile, bar, at, state, reason, duration, size, coverage in rows.all()
    ]
    counts = dict(
        (
            await session.execute(
                text(
                    "SELECT status, count(*) FROM ai_evaluation_runs "
                    "WHERE finished_at > clock_timestamp() - INTERVAL '24 hours' GROUP BY status"
                )
            )
        ).all()
    )
    try:
        raw = await redis.get(CONTRACT_ERROR_KEY)
        contract_error = json.loads(raw) if raw else None
    except Exception:  # noqa: BLE001
        contract_error = None
    return {
        "enabled": settings.ai_evaluate_enabled,
        "instruments": [f"{s}:{y}" for s, y in settings.ai_evaluate_instrument_list],
        "profiles": settings.ai_profile_list,
        "delay_seconds": settings.ai_evaluate_delay_seconds,
        "bars": settings.ai_bar_counts,
        "last_runs": last,
        "runs_last_24h": counts,
        "last_contract_error": contract_error,
    }
