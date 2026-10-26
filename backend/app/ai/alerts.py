"""AI setup alerts (B11, docs/notifications.md#ai-setup-alerts).

``store.apply_evaluation`` writes one ``ai_setup_outbox`` row per state change (never
DEVELOPING) in the evaluation's own transaction, so no alert is lost on a crash. The
``ai_alerts.dispatch`` task (beat every 30 s, and :func:`kick` after an evaluation) sends them:

- each row is claimed with ``FOR UPDATE SKIP LOCKED`` and handled in one transaction: the inbox
  and delivery rows (``notifications.prepare``) and the row's new status commit together; the
  sends and the live frame follow the commit;
- the inbox ``dedup_key`` is ``ai:{setup_id}:{to_state}``: handling a row twice (a crash
  between the commit of the inbox and the row's status) cannot notify anyone twice;
- a failure counts an attempt and retries with backoff; after ``AI_ALERTS_MAX_ATTEMPTS`` the
  row is ``failed`` (ERROR log, admins notified) until an admin retries it.

Who gets what is :func:`recipients`; what is skipped as too late is :func:`stale_reason`.
"""

from __future__ import annotations

import logging
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai import explain, sizing
from app.ai.client import AIContractError, AIServiceClient, AIUnavailableError
from app.ai.contract import ExplainRequest, Setup, iso_z
from app.core.config import get_settings
from app.core.redis import get_redis
from app.models.ai import AIAlertFollow, AISetup, AISetupExplanation, AISetupOutbox, AISetupTake
from app.models.instrument import Instrument
from app.models.notification import NotificationType, Severity
from app.models.user import User, UserRole
from app.notifications import preferences as prefs_mod
from app.notifications import service as notifications
from app.realtime import publisher
from app.realtime.topics import ai_setups_topic
from app.services import strategy_resolver

logger = logging.getLogger(__name__)

ARMED = "ARMED"
FINAL = frozenset({"CLOSED", "EXPIRED", "INVALIDATED"})
GRADES = ("A", "B", "C", "D")  # A best
EXPLAIN_TIMEOUT = 8.0  # seconds; one attempt (an alert must not wait for an explanation)
FAILED_NAMESPACE = uuid.UUID("0b5c4d8e-6a0f-4f5e-9e43-1c1f8ad0b511")


def kick() -> None:
    """Enqueue a dispatch now (the caller of ``apply_evaluation`` calls it after its commit).
    Never raises: the beat task picks the rows up within 30 s anyway."""
    try:
        from app.tasks import celery_app  # noqa: PLC0415

        celery_app.send_task("ai_alerts.dispatch", queue=notifications.QUEUE)
    except Exception:  # noqa: BLE001
        logger.exception("ai alerts: could not enqueue a dispatch")


# --- rules ---------------------------------------------------------------------------------------


def meets_grade(grade: str | None, min_grade: str | None) -> bool:
    """A setup meets a follow's ``min_grade`` (A best; no minimum: every grade, none too)."""
    if min_grade is None:
        return True
    if grade not in GRADES:
        return False
    return GRADES.index(grade) <= GRADES.index(min_grade)


def min_grade_active() -> bool:
    """Whether follows' ``min_grade`` is applied (``AI_GRADES_ENABLED``). Off in v1: the rules
    run without a model and every grade is null, so a minimum would silence every alert; the
    follower's choice stays stored and applies once grades are turned on."""
    return get_settings().ai_grades_enabled


async def recipients(session: AsyncSession, setup: AISetup, to_state: str) -> list[User]:
    """Who is told about a state change:

    - ``ARMED`` (also a setup born ARMED): the active users who follow the setup's instrument
      and profile, whose ``min_grade`` the setup meets, and who may read it. While
      ``AI_GRADES_ENABLED`` is off (v1: no grades) ``min_grade`` is not applied: every
      follower, as with no minimum;
    - ``ACTIVE``, ``CLOSED``, ``EXPIRED``, ``INVALIDATED``: only the users who took it.

    Followers who did not take a setup hear nothing after ARMED."""
    if to_state == ARMED:
        rows = await session.execute(
            select(User, AIAlertFollow.min_grade)
            .join(AIAlertFollow, AIAlertFollow.user_id == User.id)
            .where(
                AIAlertFollow.instrument_id == setup.instrument_id,
                AIAlertFollow.profile == setup.profile,
                User.is_active.is_(True),
            )
            .order_by(User.id)
        )
        graded = min_grade_active()
        return [
            user
            for user, min_grade in rows.all()
            if (not graded or meets_grade(setup.grade, min_grade))
            and strategy_resolver.may_read_ai_setup(user, setup)
        ]
    users = await session.scalars(
        select(User)
        .join(AISetupTake, AISetupTake.user_id == User.id)
        .where(AISetupTake.setup_id == setup.setup_id, User.is_active.is_(True))
        .order_by(User.id)
    )
    return [u for u in users if strategy_resolver.may_read_ai_setup(u, setup)]


def stale_reason(row: AISetupOutbox, setup: AISetup, now: datetime) -> str | None:
    """Why an ARMED alert is not sent any more (no late alerts); None: send it."""
    if row.to_state != ARMED:
        return None
    if setup.state != ARMED:
        return f"stale: the setup is {setup.state} now"
    if setup.valid_until is not None and setup.valid_until <= now:
        return "stale: valid_until has passed"
    age = (now - row.created_at).total_seconds()
    if age > get_settings().ai_alerts_max_age_seconds:
        return f"stale: {age:.0f} s old"
    return None


# --- content -------------------------------------------------------------------------------------


@dataclass
class _Run:
    """State of one dispatcher run: the ai-service client (made when first needed; one attempt
    per call) and, once ai-service failed to explain, no more explain calls in this run."""

    client: AIServiceClient | None = None
    own: bool = False
    explain_down: bool = False

    def get(self) -> AIServiceClient:
        if self.client is None:
            self.client, self.own = AIServiceClient(max_retries=0), True
        return self.client

    async def close(self) -> None:
        if self.own and self.client is not None:
            await self.client.aclose()


def _base_data(row: AISetupOutbox, setup: AISetup, instrument: Instrument, late: bool) -> dict:
    return {
        "setup_id": setup.setup_id,
        "state": row.to_state,
        "transition": {
            "from": row.from_state,
            "to": row.to_state,
            "at": iso_z(row.at),
            "reason": row.reason,
            "realized_r": row.realized_r,
        },
        "direction": setup.direction,
        "instrument": {
            "id": str(instrument.id),
            "symbol": instrument.symbol,
            "source": instrument.source,
            "price_precision": instrument.price_precision,
            "quantity_precision": instrument.quantity_precision,
        },
        "profile": setup.profile,
        "entry": setup.entry,
        "sl": setup.sl,
        "tp": setup.tp,
        "r_multiple": setup.r_multiple,
        "probability": setup.probability,
        "ev_r": setup.ev_r,
        "grade": setup.grade,
        "valid_until": iso_z(setup.valid_until) if setup.valid_until else None,
        "reason": row.reason,
        "realized_r": row.realized_r,
        "late": late,
    }


def _size_data(result: Any) -> dict[str, Any]:
    if isinstance(result, sizing.SizeResult):
        return {
            "lots": result.lots,
            "risk_amount": result.risk_amount,
            "currency": result.inputs["account"]["currency"],
            "margin_required": result.margin_required,
            "feasible": result.feasible,
            "warnings": result.warnings,
            "source": result.source,
        }
    return {"error": str(result) or type(result).__name__}


async def _sizes(
    factory: async_sessionmaker[AsyncSession],
    setup_id: str,
    users: list[User],
    run: _Run,
) -> dict[uuid.UUID, dict[str, Any]]:
    """Each recipient's size (B10), in a session of its own (sizes are a cache: they commit on
    their own). A failure is reported per user and never blocks the alert."""
    try:
        async with factory() as session:
            setup = await session.get(AISetup, setup_id)
            results = await sizing.size_setup_for_users(
                session, setup, [u.id for u in users], client=run.get()
            )
    except Exception as exc:  # noqa: BLE001 - e.g. no specs: every user gets the error
        logger.warning("ai alerts: sizing %s failed: %s", setup_id, exc)
        return {u.id: {"error": str(exc) or type(exc).__name__} for u in users}
    return {u.id: _size_data(results.get(u.id, "not sized")) for u in users}


async def _explanations(
    factory: async_sessionmaker[AsyncSession], setup_id: str, langs: list[str], run: _Run
) -> dict[str, str]:
    """The explanation of the setup a user may see, per language (Fadi's rule,
    ``explain.visible``: verified, else the template text): stored ones are reused; missing
    ones are asked of ai-service once (short timeout, no retry; ``ai.explain`` has usually
    stored them already). Unavailable or 404: none, and the run stops asking. Neither verified
    nor a template: not stored, never sent."""
    out: dict[str, str] = {}
    async with factory() as session:
        stored = {
            r.lang: r
            for r in await session.scalars(
                select(AISetupExplanation).where(
                    AISetupExplanation.setup_id == setup_id, AISetupExplanation.lang.in_(langs)
                )
            )
        }
        setup = await session.get(AISetup, setup_id)
        for lang in langs:
            row = stored.get(lang)
            if row is None and not run.explain_down:
                try:
                    answer = await run.get().explain(
                        ExplainRequest(setup=Setup.model_validate(setup.last_payload), lang=lang),
                        timeout=EXPLAIN_TIMEOUT,
                    )
                except AIUnavailableError as exc:
                    run.explain_down = True
                    logger.warning("ai alerts: no explanation (%s); template text only", exc)
                    continue
                except AIContractError as exc:
                    if exc.status == 404:
                        run.explain_down = True
                        logger.info("ai alerts: ai-service has no /v1/explain yet (404)")
                    else:
                        logger.error("ai alerts: /v1/explain contract error: %s", exc)
                    continue
                await explain.store_answer(session, setup_id, lang, answer)
                row = await session.get(AISetupExplanation, (setup_id, lang))
            shown = explain.visible(row)
            if shown.text is not None:
                out[lang] = shown.text
            elif row is not None:
                logger.warning(
                    "ai alerts: explanation %s/%s is neither verified nor a template: not sent",
                    setup_id,
                    lang,
                )
    return out


async def _items(
    session: AsyncSession,
    factory: async_sessionmaker[AsyncSession],
    row: AISetupOutbox,
    setup: AISetup,
    users: list[User],
    now: datetime,
    run: _Run,
) -> list[notifications.NotifyItem]:
    instrument = await session.get(Instrument, setup.instrument_id)
    late = (
        row.to_state != ARMED
        and (now - row.created_at).total_seconds() > get_settings().ai_alerts_max_age_seconds
    )
    base = _base_data(row, setup, instrument, late)
    extra: dict[uuid.UUID, dict[str, Any]] = {u.id: {} for u in users}
    if row.to_state == ARMED:
        for user_id, size in (await _sizes(factory, setup.setup_id, users, run)).items():
            extra[user_id]["size"] = size
        prefs = await prefs_mod.load(session, [u.id for u in users])
        wanted = {prefs[u.id].language for u in users}
        langs = [lang for lang in get_settings().ai_explain_lang_list if lang in wanted]
        explained = await _explanations(factory, setup.setup_id, langs, run) if langs else {}
        for user in users:
            text = explained.get(prefs[user.id].language)
            if text:
                extra[user.id]["explanation"] = text
            extra[user.id]["explanation_status"] = "available" if text else "unavailable"
    elif row.to_state in FINAL:
        takes = await session.scalars(
            select(AISetupTake).where(AISetupTake.setup_id == setup.setup_id)
        )
        for take in takes:
            if take.user_id in extra:
                extra[take.user_id]["take"] = {
                    "lots": take.lots,
                    "risk_amount": take.risk_amount,
                    "pnl": take.pnl,
                    "realized_r": take.realized_r,
                }
                extra[take.user_id]["pnl"] = take.pnl
    severity = Severity.warning if row.to_state == ARMED else Severity.info
    return [
        notifications.NotifyItem(
            user_id=user.id,
            type=NotificationType.ai_setup,
            data={**base, **extra[user.id]},
            dedup_key=f"ai:{setup.setup_id}:{row.to_state}",
            severity=severity,
        )
        for user in users
    ]


def _frame(row: AISetupOutbox, setup: AISetup) -> dict[str, Any]:
    return {
        "type": "ai_setup",
        "setup": setup.last_payload,
        "transition": {
            "setup_id": setup.setup_id,
            "from": row.from_state,
            "to": row.to_state,
            "at": iso_z(row.at),
            "reason": row.reason,
            "realized_r": row.realized_r,
        },
    }


# --- dispatching ---------------------------------------------------------------------------------


async def _handle(
    session: AsyncSession,
    factory: async_sessionmaker[AsyncSession],
    redis: Redis,
    row: AISetupOutbox,
    now: datetime,
    run: _Run,
) -> tuple[str, notifications.Prepared | None, tuple[str, dict] | None]:
    """(outcome, prepared notifications, live frame) of one claimed row; the row's status is
    set here and committed by the caller."""
    setup = await session.get(AISetup, row.setup_id)
    row.processed_at = now
    reason = stale_reason(row, setup, now)
    if reason is not None:
        row.status, row.last_error = "skipped", reason
        return "skipped", None, None
    users = await recipients(session, setup, row.to_state)
    prepared = None
    if users:
        items = await _items(session, factory, row, setup, users, now, run)
        prepared = await notifications.prepare(session, redis, items, now)
    row.status, row.last_error = "done", None
    return "done", prepared, (ai_setups_topic(setup.instrument_id), _frame(row, setup))


async def _alert_admins(
    factory: async_sessionmaker[AsyncSession], redis: Redis, row_id: int, error: str
) -> None:
    try:
        await notifications.broadcast(
            factory,
            redis,
            uuid.uuid5(FAILED_NAMESPACE, f"ai-outbox:{row_id}"),
            f"AI alert {row_id} failed",
            f"Outbox row {row_id} failed {get_settings().ai_alerts_max_attempts} times: "
            f"{error}. Retry it with POST /api/v1/admin/ai/outbox/{row_id}/retry.",
            Severity.warning,
            [UserRole.admin],
        )
    except Exception:  # noqa: BLE001
        logger.exception("ai alerts: could not notify the admins about row %s", row_id)


async def _process_next(
    factory: async_sessionmaker[AsyncSession], redis: Redis, now: datetime, run: _Run
) -> str | None:
    settings = get_settings()
    failed = None
    async with factory() as session:
        row = await session.scalar(
            select(AISetupOutbox)
            .where(AISetupOutbox.status == "pending", AISetupOutbox.next_attempt_at <= now)
            .order_by(AISetupOutbox.next_attempt_at, AISetupOutbox.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if row is None:
            return None
        try:
            async with session.begin_nested():
                outcome, prepared, frame = await _handle(session, factory, redis, row, now, run)
        except Exception as exc:  # noqa: BLE001 - counted, retried with backoff
            error = f"{type(exc).__name__}: {exc}"[:500]
            await session.refresh(row)  # the savepoint's rollback expired it (still locked)
            row.attempts += 1
            row.last_error = error
            if row.attempts >= settings.ai_alerts_max_attempts:
                row.status = "failed"
                failed = (row.id, error)
                outcome = "failed"
            else:
                delay = notifications.backoff(row.attempts)
                row.next_attempt_at = now + timedelta(seconds=delay)
                outcome = "retry"
            logger.warning("ai alerts: row %s attempt %d failed: %s", row.id, row.attempts, error)
            prepared = frame = None
        await session.commit()
    if failed is not None:
        logger.error("ai alerts: row %s failed for good: %s", *failed)
        await _alert_admins(factory, redis, *failed)
    if prepared is not None:
        await notifications.after_commit(redis, prepared)
    if frame is not None:
        try:
            await publisher.publish(frame[0], frame[1], redis)
        except Exception:  # noqa: BLE001 - the inbox has it; the live view is best effort
            logger.exception("ai alerts: publishing on %s failed", frame[0])
    return outcome


async def dispatch(
    factory: async_sessionmaker[AsyncSession],
    redis: Redis | None = None,
    *,
    now: datetime | None = None,
    client: AIServiceClient | None = None,
) -> dict[str, int]:
    """Handle up to ``AI_ALERTS_BATCH`` due outbox rows, oldest first (the beat task)."""
    settings = get_settings()
    if not settings.ai_alerts_enabled:
        return {}
    redis = redis or get_redis()
    counts: Counter[str] = Counter()
    run = _Run(client=client)
    try:
        for _ in range(max(1, settings.ai_alerts_batch)):
            outcome = await _process_next(factory, redis, now or datetime.now(UTC), run)
            if outcome is None:
                break
            counts[outcome] += 1
    finally:
        await run.close()
    if counts:
        logger.info("ai_alerts.dispatch %s", dict(counts))
    return dict(counts)
