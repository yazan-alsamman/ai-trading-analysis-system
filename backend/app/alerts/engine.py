"""Price alert evaluation on every closed 1m bar.

``alerts.tick`` (beat, every minute) schedules ``alerts.evaluate`` for ``boundary + 10 s``, the
same moment as the signal engine, for the 1m bar that just closed (the still-forming bucket is
never read). One run:

1. deactivates expired alerts;
2. loads every active alert in one query and groups them by instrument;
3. per instrument, one query returns the closed bar, the previous close and the reference close
   of every ``change_pct`` window; the conditions are checked for all alerts at once (numpy);
   **Catch-up**: the run also evaluates the 4 bars before, when they were not evaluated yet
   (their candle arrived after their own run); each evaluated (instrument, bar) is marked in
   Redis for 15 minutes, so a bar is normally checked once;
4. stores one ``price_alert`` notification per fired alert (dedup
   ``price_alert:<alert_id>:<bar_time>``, so a re-run never notifies twice), updates the alerts
   (``once`` -> inactive) in the same transaction, then publishes and enqueues the sends.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
from redis.asyncio import Redis
from sqlalchemy import bindparam, case, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.instrument import Instrument
from app.models.notification import NotificationType, Severity
from app.models.price_alert import AlertCondition, AlertRepeat, PriceAlert
from app.notifications import service as notifications
from app.realtime import publisher
from app.realtime.topics import channel_for, user_topic

logger = logging.getLogger(__name__)

MINUTE = timedelta(minutes=1)
CATCH_UP_BARS = 5  # the closed bar and the 4 before it
BAR_DONE_TTL = 900  # seconds a bar stays marked as evaluated
PREVIOUS_LOOKBACK_MINUTES = 60  # a gap longer than this: crosses cannot be evaluated
LOCK_TTL = timedelta(seconds=120)
DONE_TTL = timedelta(hours=6)
CODES = {c: i for i, c in enumerate(AlertCondition)}

_BARS = text(
    """
    (SELECT 'bar' AS kind, 0 AS w, ts, high, low, close FROM candles_1m
     WHERE instrument_id = :iid AND ts <= :bar
       AND ts > CAST(:bar AS timestamptz) - make_interval(mins => :lookback)
     ORDER BY ts DESC LIMIT 2)
    UNION ALL
    SELECT 'ref', w, c.ts, NULL, NULL, c.close
    FROM unnest(CAST(:windows AS integer[])) AS w
    JOIN LATERAL (
        SELECT ts, close FROM candles_1m
        WHERE instrument_id = :iid
          AND ts <= CAST(:bar AS timestamptz) - make_interval(mins => w)
          AND ts > CAST(:bar AS timestamptz) - make_interval(mins => 2 * w)
        ORDER BY ts DESC LIMIT 1
    ) AS c ON true
    """
)


@dataclass
class AlertRun:
    bar_time: datetime
    status: str = "done"  # done | locked | already_done
    expired: int = 0
    alerts: int = 0
    instruments: int = 0
    no_bar: int = 0  # instruments without a candle for the bar (gap)
    fired: int = 0
    notifications: int = 0
    deactivated: int = 0
    caught_up: int = 0  # earlier bars evaluated late (their candle arrived after their run)
    done_marks: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duration_ms: float = 0.0


@dataclass(frozen=True)
class Bars:
    high: float
    low: float
    close: float
    previous_close: float | None
    references: dict[int, float]  # window minutes -> close that long ago


async def _bars(
    session: AsyncSession, instrument_id: uuid.UUID, bar_time: datetime, windows: list[int]
) -> Bars | None:
    rows = (
        await session.execute(
            _BARS,
            {
                "iid": instrument_id,
                "bar": bar_time,
                "lookback": PREVIOUS_LOOKBACK_MINUTES,
                "windows": windows,
            },
        )
    ).all()
    bars = sorted((r for r in rows if r.kind == "bar"), key=lambda r: r.ts, reverse=True)
    if not bars or bars[0].ts != bar_time:
        return None  # no candle for this bar (yet): nothing can fire
    previous = bars[1].close if len(bars) > 1 else None
    refs = {r.w: r.close for r in rows if r.kind == "ref"}
    return Bars(bars[0].high, bars[0].low, bars[0].close, previous, refs)


def check(alerts: list[dict[str, Any]], bars: Bars, bar_end: datetime) -> np.ndarray:
    """Boolean mask of the alerts that fire on this bar (conditions, cooldown, creation)."""
    n = len(alerts)
    code = np.fromiter((CODES[a["condition"]] for a in alerts), dtype=np.int8, count=n)
    value = np.fromiter((a["value"] for a in alerts), dtype=np.float64, count=n)
    ref = np.fromiter(
        (bars.references.get(a["window_minutes"] or 0, np.nan) for a in alerts),
        dtype=np.float64,
        count=n,
    )
    prev = np.nan if bars.previous_close is None else bars.previous_close
    with np.errstate(invalid="ignore", divide="ignore"):
        move = np.abs(bars.close / ref - 1.0) * 100.0
        hit = np.select(
            [
                code == CODES[AlertCondition.above],
                code == CODES[AlertCondition.below],
                code == CODES[AlertCondition.crosses_above],
                code == CODES[AlertCondition.crosses_below],
                code == CODES[AlertCondition.change_pct],
            ],
            [
                bars.high >= value,
                bars.low <= value,
                (prev < value) & (bars.close >= value),
                (prev > value) & (bars.close <= value),
                move >= value - 1e-9,
            ],
            default=False,
        )
    ready = np.fromiter(
        (
            a["created_at"] < bar_end
            and (
                a["repeat"] == AlertRepeat.once
                or a["last_triggered_at"] is None
                or bar_end >= a["last_triggered_at"] + timedelta(minutes=a["cooldown_minutes"])
            )
            for a in alerts
        ),
        dtype=bool,
        count=n,
    )
    return hit & ready


def _payload(alert: dict[str, Any], instrument: Instrument, bars: Bars, bar_time: datetime):
    condition = AlertCondition(alert["condition"])
    price = {
        AlertCondition.above: bars.high,
        AlertCondition.below: bars.low,
    }.get(condition, bars.close)
    data: dict[str, Any] = {
        "alert_id": str(alert["id"]),
        "instrument": {
            "id": str(instrument.id),
            "symbol": instrument.symbol,
            "price_precision": instrument.price_precision,
        },
        "condition": condition.value,
        "value": alert["value"],
        "window_minutes": alert["window_minutes"],
        "repeat": AlertRepeat(alert["repeat"]).value,
        "price": price,
        "bar": {"high": bars.high, "low": bars.low, "close": bars.close},
        "bar_time": bar_time.isoformat(),
        "note": alert["note"],
        "deactivated": AlertRepeat(alert["repeat"]) == AlertRepeat.once,
    }
    if condition in (AlertCondition.crosses_above, AlertCondition.crosses_below):
        data["previous_close"] = bars.previous_close
    if condition == AlertCondition.change_pct:
        reference = bars.references[alert["window_minutes"]]
        data["reference_close"] = reference
        data["change_pct"] = round((bars.close / reference - 1.0) * 100.0, 4)
    return data


def _done_key(instrument_id: uuid.UUID, bar: datetime) -> str:
    return f"alerts:bar:{instrument_id}:{bar.isoformat()}"


async def _acquire(redis: Redis, key: str, token: str) -> str | None:
    if await redis.set(key, token, nx=True, px=int(LOCK_TTL.total_seconds() * 1000)):
        return None
    return "already_done" if await redis.get(key) == "done" else "locked"


async def evaluate(
    factory: async_sessionmaker[AsyncSession],
    redis: Redis,
    bar_time: datetime,
    now: datetime | None = None,
) -> AlertRun:
    """Evaluate every active alert on the closed 1m bar starting at ``bar_time``."""
    started = time.perf_counter()
    now = now or datetime.now(UTC)
    bar_time = bar_time.astimezone(UTC)
    bar_end = bar_time + MINUTE
    run = AlertRun(bar_time)
    key, token = f"lock:alerts:{bar_time.isoformat()}", uuid.uuid4().hex
    busy = await _acquire(redis, key, token)
    if busy:
        run.status = busy
        return _done(run, started)
    try:
        prepared, fired_messages = await _evaluate(factory, redis, run, bar_time, bar_end, now)
        if run.done_marks:
            pipe = redis.pipeline(transaction=False)
            for mark in run.done_marks:
                pipe.set(mark, "1", ex=BAR_DONE_TTL)
            await pipe.execute()
        await notifications.after_commit(redis, prepared)
        await _publish(redis, fired_messages)
        await redis.set(key, "done", px=int(DONE_TTL.total_seconds() * 1000))
    except BaseException:
        if await redis.get(key) == token:
            await redis.delete(key)
        raise
    return _done(run, started)


async def _evaluate(factory, redis, run: AlertRun, bar_time, bar_end, now):
    fired_messages: list[tuple[uuid.UUID, dict[str, Any]]] = []
    async with factory() as session:
        expired = await session.execute(
            update(PriceAlert)
            .where(PriceAlert.is_active.is_(True), PriceAlert.expires_at <= now)
            .values(is_active=False)
            .returning(PriceAlert.id)
        )
        run.expired = len(expired.all())
        rows = (
            await session.execute(
                select(
                    PriceAlert.id,
                    PriceAlert.user_id,
                    PriceAlert.instrument_id,
                    PriceAlert.condition,
                    PriceAlert.value,
                    PriceAlert.window_minutes,
                    PriceAlert.repeat,
                    PriceAlert.cooldown_minutes,
                    PriceAlert.note,
                    PriceAlert.last_triggered_at,
                    PriceAlert.created_at,
                )
                .join(Instrument, Instrument.id == PriceAlert.instrument_id)
                .where(PriceAlert.is_active.is_(True), Instrument.is_active.is_(True))
            )
        ).all()
        run.alerts = len(rows)
        by_instrument: dict[uuid.UUID, list[dict[str, Any]]] = defaultdict(list)
        for r in rows:
            by_instrument[r.instrument_id].append(dict(r._mapping))
        run.instruments = len(by_instrument)
        items: list[notifications.NotifyItem] = []
        by_key: dict[str, tuple[dict[str, Any], datetime]] = {}
        # the closed bar, plus the previous ones not evaluated yet (their candle came late)
        candidates = [bar_time - MINUTE * k for k in range(CATCH_UP_BARS - 1, -1, -1)]
        for instrument_id, alerts in by_instrument.items():
            windows = sorted({a["window_minutes"] for a in alerts if a["window_minutes"]})
            flags = await redis.mget([_done_key(instrument_id, b) for b in candidates])
            instrument = None
            for bar, flag in zip(candidates, flags, strict=True):
                if flag:
                    continue
                bars = await _bars(session, instrument_id, bar, windows)
                if bars is None:
                    if bar == bar_time:
                        run.no_bar += 1
                    continue
                run.done_marks.append(_done_key(instrument_id, bar))
                if bar != bar_time:
                    run.caught_up += 1
                end = bar + MINUTE
                live = [a for a in alerts if not a.get("_fired_once")]
                if not live:
                    continue
                mask = check(live, bars, end)
                if not mask.any():
                    continue
                instrument = instrument or await session.get(Instrument, instrument_id)
                for alert in (a for a, hit in zip(live, mask, strict=True) if hit):
                    data = _payload(alert, instrument, bars, bar)
                    dedup = f"price_alert:{alert['id']}:{bar.isoformat()}"
                    items.append(
                        notifications.NotifyItem(
                            user_id=alert["user_id"],
                            type=NotificationType.price_alert,
                            data=data,
                            dedup_key=dedup,
                            severity=Severity.warning,
                        )
                    )
                    by_key[dedup] = (alert, end)
                    # later bars of this run see the alert as it will be after this one
                    if alert["repeat"] == AlertRepeat.once:
                        alert["_fired_once"] = True
                    else:
                        alert["last_triggered_at"] = end
        run.fired = len(items)
        prepared = notifications.Prepared()
        if items:
            prepared = await notifications.prepare(session, redis, items)
            fired: dict[uuid.UUID, list] = {}
            for note in prepared.notifications:
                alert, end = by_key[note["dedup_key"]]
                last, count = fired.get(alert["id"], (end, 0))
                fired[alert["id"]] = [max(last, end), count + 1]
            if fired:
                table = PriceAlert.__table__
                await session.execute(
                    update(table)
                    .where(table.c.id == bindparam("b_id"))
                    .values(
                        last_triggered_at=bindparam("b_at"),
                        trigger_count=table.c.trigger_count + bindparam("b_n"),
                        is_active=case(
                            (table.c.repeat == AlertRepeat.once.value, False),
                            else_=table.c.is_active,
                        ),
                    ),
                    [{"b_id": i, "b_at": at, "b_n": n} for i, (at, n) in fired.items()],
                )
            stored = [by_key[n["dedup_key"]][0] for n in prepared.notifications]
            run.notifications = len(prepared.notifications)
            run.deactivated = len({a["id"] for a in stored if a["repeat"] == AlertRepeat.once})
            for note in prepared.notifications:
                fired_messages.append(
                    (note["user_id"], {**note["data"], "notification_id": str(note["id"])})
                )
        await session.commit()
    return prepared, fired_messages


async def _publish(redis: Redis, messages: list[tuple[uuid.UUID, dict[str, Any]]]) -> None:
    """``{"type": "price_alert", ...}`` on ``user:{id}`` (next to the ``notification`` message
    that ``after_commit`` already sent), in one pipeline."""
    if not messages:
        return
    try:
        pipe = redis.pipeline(transaction=False)
        for user_id, data in messages:
            topic = user_topic(user_id)
            pipe.publish(
                channel_for(topic), publisher.encode(topic, {"type": "price_alert", **data})
            )
        await pipe.execute()
    except Exception:  # noqa: BLE001 - the inbox has them
        logger.exception("price alerts: publishing %d messages failed", len(messages))


def _done(run: AlertRun, started: float) -> AlertRun:
    run.duration_ms = round((time.perf_counter() - started) * 1000, 1)
    if run.status != "done" or run.alerts or run.expired:
        logger.info(
            "alerts.evaluate bar=%s status=%s alerts=%d instruments=%d no_bar=%d fired=%d "
            "notifications=%d deactivated=%d expired=%d caught_up=%d duration_ms=%.1f",
            run.bar_time.isoformat(),
            run.status,
            run.alerts,
            run.instruments,
            run.no_bar,
            run.fired,
            run.notifications,
            run.deactivated,
            run.expired,
            run.caught_up,
            run.duration_ms,
        )
    return run
