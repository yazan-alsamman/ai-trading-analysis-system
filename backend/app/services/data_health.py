"""Data-quality state (B5): the latest :class:`~app.services.data_quality.QualityReport` of
every monitored instrument (``DATA_QUALITY_INSTRUMENTS``), kept in Redis.

The ``data_quality.check`` beat task stores one report per instrument every minute (5-minute
TTL). ``GET /api/v1/health/data`` and ``GET /admin/system/status`` read them and compute a
missing one on the spot. A status change is logged once; when an instrument turns bad
(``degraded``/``no_data``) or recovers, admins get one ``system`` notification.

Flapping (B9): after an alert, no other alert about the same instrument for
``DATA_QUALITY_ALERT_COOLDOWN_SECONDS`` (default 1800). The state itself (``/health/data``)
still changes at once; what the admins were last told is kept, and a change held back by the
cooldown is sent when it ends if the instrument is still in that state.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.models.instrument import Instrument
from app.models.notification import Severity
from app.models.user import UserRole
from app.notifications import service as notifications
from app.services import data_quality
from app.services.data_quality import BAD_STATUSES, QualityReport, QualityStatus

logger = logging.getLogger(__name__)

REPORT_KEY = "dq:report:"  # + source:symbol -> the latest report (JSON)
STATUS_KEY = "dq:status:"  # + source:symbol -> the last status the beat task saw
ALERTED_KEY = "dq:alerted:"  # + source:symbol -> "bad" | "good": what admins were last told
COOLDOWN_KEY = "dq:alert-cooldown:"  # + source:symbol -> set while no other alert is sent
REPORT_TTL = 300
STATUS_TTL = 7 * 24 * 3600
# worst first: the overall status of /health/data and the "data" field of /health/ready
_RANK = {
    QualityStatus.no_data: 3,
    QualityStatus.degraded: 2,
    QualityStatus.closed: 1,
    QualityStatus.ok: 0,
}


def monitored() -> list[str]:
    """``source:symbol`` of every monitored instrument (empty when the gate is off)."""
    settings = get_settings()
    if not settings.data_quality_enabled:
        return []
    return [f"{source}:{symbol}" for source, symbol in settings.data_quality_instrument_list]


def worst(reports: list[QualityReport]) -> QualityStatus | None:
    return max((r.status for r in reports), key=_RANK.__getitem__, default=None)


async def compute(
    session: AsyncSession, names: list[str], now: datetime | None = None
) -> list[QualityReport]:
    """Assess ``names`` now: one query for the instruments, two per instrument."""
    now = (now or datetime.now(UTC)).astimezone(UTC)
    pairs = [tuple(name.split(":", 1)) for name in names]
    found = {
        (i.source, i.symbol): i
        for i in await session.scalars(
            select(Instrument).where(tuple_(Instrument.source, Instrument.symbol).in_(pairs))
        )
    }
    thresholds = data_quality.Thresholds.from_settings()
    reports = []
    for name, pair in zip(names, pairs, strict=True):
        instrument = found.get(pair)
        if instrument is None:
            reports.append(data_quality.missing_instrument(name, now))
        else:
            reports.append(
                await data_quality.load_and_assess(
                    session, instrument, now=now, thresholds=thresholds
                )
            )
    return reports


async def cached(redis: Redis, names: list[str]) -> dict[str, QualityReport]:
    """The stored reports of ``names`` that have not expired."""
    if not names:
        return {}
    values = await redis.mget([REPORT_KEY + name for name in names])
    return {
        name: QualityReport.model_validate_json(raw)
        for name, raw in zip(names, values, strict=True)
        if raw
    }


async def current(
    session: AsyncSession, redis: Redis, now: datetime | None = None
) -> list[QualityReport]:
    """Every monitored instrument's report: the stored one, or computed now (and stored, so a
    burst of requests computes once). Never touches the transition state."""
    names = monitored()
    try:
        stored = await cached(redis, names)
    except Exception:  # noqa: BLE001 - Redis down: compute everything
        logger.warning("data quality: reading the stored reports failed", exc_info=True)
        stored = {}
    missing = [name for name in names if name not in stored]
    if missing:
        for report in await compute(session, missing, now):
            stored[report.instrument] = report
            try:
                await redis.set(REPORT_KEY + report.instrument, report.model_dump_json(), ex=60)
            except Exception:  # noqa: BLE001
                pass
    return [stored[name] for name in names]


async def _notify_admins(
    factory: async_sessionmaker[AsyncSession], redis: Redis, report: QualityReport
) -> None:
    bad = report.status in BAD_STATUSES
    failed = "; ".join(f"{c.name}: {c.detail}" for c in report.failed)
    title = f"Data quality: {report.instrument} is {report.status.value}"
    body = (
        f"Failed checks: {failed}. The AI engine is not called until it is ok again."
        if bad
        else f"{report.instrument} is {report.status.value} again."
    )
    try:
        await notifications.broadcast(
            factory,
            redis,
            uuid.uuid4(),
            title,
            body,
            Severity.warning if bad else Severity.success,
            [UserRole.admin],
        )
    except Exception:  # noqa: BLE001 - an alert must never break the check
        logger.exception("data quality: notifying admins about %s failed", report.instrument)


def _transition(report: QualityReport, previous: str | None) -> None:
    bad = report.status in BAD_STATUSES
    failed = ", ".join(f"{c.name} ({c.detail})" for c in report.failed) or "-"
    logger.log(
        logging.WARNING if bad else logging.INFO,
        "data quality %s: %s -> %s (failed: %s; last closed bar %s, lag %s s)",
        report.instrument,
        previous or "unknown",
        report.status.value,
        failed,
        report.last_closed_bar.isoformat() if report.last_closed_bar else None,
        report.lag_seconds,
    )


def _text(value: str | bytes | None) -> str | None:
    return value.decode() if isinstance(value, bytes) else value


async def _alert(
    factory: async_sessionmaker[AsyncSession],
    redis: Redis,
    report: QualityReport,
    previous: str | None,
) -> None:
    """Admins hear about an instrument turning bad or recovering, once; not about every
    ok <-> closed of the daily break, nor about the first check after a fresh start, and at
    most once per ``DATA_QUALITY_ALERT_COOLDOWN_SECONDS`` (checked on every run, so a change
    held back is sent when the cooldown ends, if it still holds)."""
    name = report.instrument
    state = "bad" if report.status in BAD_STATUSES else "good"
    told = _text(await redis.get(ALERTED_KEY + name))
    if told is None:
        if previous is None:  # the first check after a fresh start: nothing to tell
            await redis.set(ALERTED_KEY + name, state, ex=STATUS_TTL)
            return
        told = "bad" if QualityStatus(previous) in BAD_STATUSES else "good"
    if told == state:
        return
    cooldown = get_settings().data_quality_alert_cooldown_seconds
    if cooldown > 0 and not await redis.set(COOLDOWN_KEY + name, "1", nx=True, ex=cooldown):
        if previous != report.status.value:
            logger.info(
                "data quality %s: %s, the admins' alert waits for the cooldown (%d s)",
                name,
                report.status.value,
                cooldown,
            )
        return
    await redis.set(ALERTED_KEY + name, state, ex=STATUS_TTL)
    await _notify_admins(factory, redis, report)


async def run(
    factory: async_sessionmaker[AsyncSession], redis: Redis, now: datetime | None = None
) -> list[QualityReport]:
    """The beat task: assess every monitored instrument, store the reports and handle status
    transitions (atomically, so overlapping runs report a change once)."""
    names = monitored()
    if not names:
        return []
    async with factory() as session:
        reports = await compute(session, names, now)
    for report in reports:
        pipe = redis.pipeline(transaction=False)
        pipe.set(REPORT_KEY + report.instrument, report.model_dump_json(), ex=REPORT_TTL)
        pipe.set(STATUS_KEY + report.instrument, report.status.value, ex=STATUS_TTL, get=True)
        _, previous = await pipe.execute()
        if isinstance(previous, bytes):
            previous = previous.decode()
        if previous != report.status.value:
            _transition(report, previous)
        try:
            await _alert(factory, redis, report, previous)
        except Exception:  # noqa: BLE001 - an alert must never break the check
            logger.exception("data quality: alerting about %s failed", report.instrument)
    return reports
