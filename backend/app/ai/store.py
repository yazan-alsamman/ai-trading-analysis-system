"""Storing ai-service results (B8, docs/ai-contract.md).

ai-service decides setups and their states; the backend only records them:

- ``apply_evaluation`` writes one evaluate response in one transaction and returns the state
  changes (B11 turns them into notifications). Re-applying the same response changes nothing
  and reports no state change.
- Contract 0.2.0 (Fadi, points 9-11): a response carries the current state of every setup in
  ``new_setups`` and its full history in ``transitions``. Transitions are applied first, in
  ``(at, state order)`` order (ARMED and ACTIVE may share an ``at``) and deduped by
  ``(setup_id, to, at)``; history the setup has already passed is skipped silently. Then each
  setup is reconciled with its current state. A state never goes backwards: a setup sent back
  in an earlier state is a **contract error** (logged, listed in the result), and ours is kept.
- A new setup's first event is at its ``created_at`` when ai-service sends it, otherwise at
  ``bar_close_ts``; it starts in the state its history starts from.
- Final states (CLOSED, EXPIRED, INVALIDATED) never change again. A transition that is not in
  ``ALLOWED`` (ACTIVE -> INVALIDATED is not, any more; rows that already made it keep it as
  history), that starts from another state than the stored one, or that names an unknown setup
  is rejected and logged; the rest of the response is still applied.
- Every state change except to DEVELOPING is also written to ``ai_setup_outbox`` in the same
  transaction (B11): the alerts survive a crash and are sent by ``ai_alerts.dispatch``.
- ``open_setups`` gives the next request's ``open_setups``: the last payload of every
  non-final setup, in a stable order.
"""

from __future__ import annotations

import copy
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contract import (
    ALLOWED_TRANSITIONS,
    FINAL_STATES,
    STATE_RANK,
    EvaluateRequest,
    EvaluateResponse,
    EvaluateStatus,
    Setup,
    SetupState,
    Transition,
    Versions,
)
from app.models.ai import AIModelVersion, AISetup, AISetupEvent, AISetupOutbox, AISetupTake
from app.models.instrument import Instrument

logger = logging.getLogger(__name__)

# The only state changes the backend records (contract 0.2.0, docs/ai-contract.md)
ALLOWED = ALLOWED_TRANSITIONS
MUTABLE = (
    "entry",
    "sl",
    "tp",
    "r_multiple",
    "probability",
    "ev_r",
    "ev_r_lower",
    "grade",
    "valid_until",
    "horizon_until",
    "evidence",
    "features",
)
FINAL = frozenset(s.value for s in FINAL_STATES)


@dataclass(frozen=True)
class StateChange:
    setup_id: str
    from_state: str | None  # None: the setup appeared
    to_state: str
    at: datetime
    reason: str | None = None
    realized_r: float | None = None


@dataclass(frozen=True)
class Rejection:
    setup_id: str
    reason: str


@dataclass
class ApplyResult:
    request_id: str
    status: str
    versions: dict[str, str | None]
    inserted: int = 0  # new setups
    updated: int = 0  # existing setups whose fields changed
    unchanged: int = 0  # new_setups items already stored as they are
    transitions_applied: int = 0
    transitions_known: int = 0  # already recorded (a re-applied response)
    rejected: list[Rejection] = field(default_factory=list)
    # the response contradicts itself or our records (a state going backwards): logged as an
    # error and shown in /admin/system/status; our state is kept
    contract_errors: list[Rejection] = field(default_factory=list)
    state_changes: list[StateChange] = field(default_factory=list)


def _values(setup: Setup) -> dict[str, Any]:
    data = {name: getattr(setup, name) for name in MUTABLE}
    data["grade"] = setup.grade.value if setup.grade is not None else None
    return data


def _versions(versions: Versions) -> dict[str, str | None]:
    return {
        "strategy_version": versions.strategy,
        "model_version": versions.model,
        "features_version": versions.features,
    }


async def _record_model(session: AsyncSession, versions: Versions, request_id: str) -> None:
    """A model version ai-service reports is added to the registry (inactive) if unknown."""
    if not versions.model:
        return
    await session.execute(
        insert(AIModelVersion)
        .values(model_id=versions.model, notes=f"first reported by ai-service ({request_id})")
        .on_conflict_do_nothing(index_elements=["model_id"])
    )
    active = await session.scalar(
        select(AIModelVersion.model_id).where(AIModelVersion.is_active.is_(True))
    )
    if active is not None and active != versions.model:
        logger.warning(
            "ai-service reports model %s but the active model is %s (%s)",
            versions.model,
            active,
            request_id,
        )


async def _event(
    session: AsyncSession,
    setup_id: str,
    from_state: str | None,
    to_state: str,
    at: datetime,
    request_id: str,
    reason: str | None = None,
    realized_r: float | None = None,
) -> bool:
    inserted = await session.scalar(
        insert(AISetupEvent)
        .values(
            setup_id=setup_id,
            from_state=from_state,
            to_state=to_state,
            at=at,
            reason=reason,
            realized_r=realized_r,
            request_id=request_id,
        )
        .on_conflict_do_nothing(index_elements=["setup_id", "to_state", "at"])
        .returning(AISetupEvent.id)
    )
    return inserted is not None


async def _close_takes(
    session: AsyncSession,
    setup_id: str,
    to_state: str,
    at: datetime,
    realized_r: float | None,
    reason: str | None,
) -> None:
    """The setup ended: close its open takes (B10). CLOSED: ``realized_r`` and
    ``pnl = realized_r * risk_amount``; EXPIRED / INVALIDATED: 0. A take already closed is
    left as it is, so a replayed transition changes nothing."""
    if to_state not in FINAL:
        return
    if to_state == SetupState.CLOSED.value:
        r = realized_r
        values = {
            "realized_r": r,
            "pnl": (AISetupTake.risk_amount * r) if r is not None else None,
        }
    else:
        values = {"realized_r": 0.0, "pnl": 0.0}
    await session.execute(
        update(AISetupTake)
        .where(AISetupTake.setup_id == setup_id, AISetupTake.closed_at.is_(None))
        .values(closed_at=at, close_reason=(reason or to_state.lower())[:64], **values)
    )


async def enqueue_alerts(session: AsyncSession, changes: Sequence[StateChange]) -> int:
    """The outbox rows of the alerts (B11), in the caller's transaction: one per state change,
    never for DEVELOPING; a change already enqueued (same setup and state) adds nothing."""
    rows = [
        {
            "setup_id": c.setup_id,
            "from_state": c.from_state,
            "to_state": c.to_state,
            "at": c.at,
            "reason": (c.reason or None) and c.reason[:255],
            "realized_r": c.realized_r,
        }
        for c in changes
        if c.to_state != SetupState.DEVELOPING.value
    ]
    if not rows:
        return 0
    inserted = await session.scalars(
        insert(AISetupOutbox)
        .values(rows)
        .on_conflict_do_nothing(index_elements=["setup_id", "to_state"])
        .returning(AISetupOutbox.id)
    )
    return len(list(inserted))


def _reject(result: ApplyResult, setup_id: str, reason: str) -> None:
    result.rejected.append(Rejection(setup_id, reason))
    logger.warning(
        "ai-service result rejected: setup %s: %s (%s)", setup_id, reason, result.request_id
    )


def _contract_error(result: ApplyResult, setup_id: str, reason: str) -> None:
    result.contract_errors.append(Rejection(setup_id, reason))
    logger.error(
        "ai-service contract error: setup %s: %s (%s); our state is kept",
        setup_id,
        reason,
        result.request_id,
    )


def _order(t: Transition) -> tuple[datetime, int]:
    """Transitions in time order; at the same ``at`` (ARMED and ACTIVE in one response) in
    life-cycle order."""
    return t.at, STATE_RANK[t.from_]


async def apply_evaluation(
    session: AsyncSession, instrument: Instrument, req: EvaluateRequest, resp: EvaluateResponse
) -> ApplyResult:
    """Store one evaluate response (one transaction) and return what changed."""
    if resp.request_id != req.request_id:
        raise ValueError(f"response {resp.request_id!r} is not for request {req.request_id!r}")
    result = ApplyResult(
        request_id=req.request_id,
        status=resp.status.value,
        versions=resp.versions.model_dump(),
    )
    await _record_model(session, resp.versions, req.request_id)
    if resp.status != EvaluateStatus.ok:
        await session.commit()
        logger.info("ai-service %s: %s, nothing stored", req.request_id, resp.status.value)
        return result

    ids = {s.setup_id for s in resp.new_setups} | {t.setup_id for t in resp.transitions}
    rows: dict[str, AISetup] = {}
    known: set[tuple[str, str, datetime]] = set()
    if ids:
        found = await session.scalars(
            select(AISetup).where(AISetup.setup_id.in_(ids)).with_for_update()
        )
        rows = {row.setup_id: row for row in found}
        events = await session.execute(
            select(AISetupEvent.setup_id, AISetupEvent.to_state, AISetupEvent.at).where(
                AISetupEvent.setup_id.in_(ids)
            )
        )
        known = {(s, t, a) for s, t, a in events.all()}
    now = datetime.now(UTC)
    versions = _versions(resp.versions)
    transitions = sorted(resp.transitions, key=_order)
    first_from: dict[str, SetupState] = {}
    for t in transitions:
        first_from.setdefault(t.setup_id, t.from_)

    new: set[str] = set()
    for setup in resp.new_setups:
        if setup.setup_id not in rows and setup.setup_id not in new:
            start = first_from.get(setup.setup_id, setup.state)
            await _insert_setup(session, result, instrument, req, setup, start, rows, versions, now)
            new.add(setup.setup_id)
    for transition in transitions:
        await _apply_transition(session, result, instrument, req, transition, rows, known, now)
    for setup in resp.new_setups:
        await _reconcile(session, result, instrument, req, setup, rows, versions, now, new)
    await enqueue_alerts(session, result.state_changes)
    await session.commit()
    logger.info(
        "ai-service %s applied: inserted=%d updated=%d unchanged=%d transitions=%d "
        "known=%d rejected=%d contract_errors=%d",
        req.request_id,
        result.inserted,
        result.updated,
        result.unchanged,
        result.transitions_applied,
        result.transitions_known,
        len(result.rejected),
        len(result.contract_errors),
    )
    return result


async def _insert_setup(
    session: AsyncSession,
    result: ApplyResult,
    instrument: Instrument,
    req: EvaluateRequest,
    setup: Setup,
    start: SetupState,
    rows: dict[str, AISetup],
    versions: dict[str, str | None],
    now: datetime,
) -> None:
    """A setup seen for the first time, in ``start`` (where its history in ``transitions``
    starts, or its current state without history); the transitions then move it on. Its first
    event is at ``created_at`` when ai-service sends it, else at ``bar_close_ts``."""
    payload = {**setup.payload(), "state": start.value}
    at = setup.created_at or req.bar_close_ts
    row = AISetup(
        setup_id=setup.setup_id,
        instrument_id=instrument.id,
        profile=req.profile,
        direction=setup.direction.value,
        state=start.value,
        last_payload=payload,
        first_request_id=req.request_id,
        last_request_id=req.request_id,
        created_at=now,
        updated_at=now,
        **_values(setup),
        **versions,
    )
    session.add(row)
    await session.flush()
    rows[setup.setup_id] = row
    await _event(session, setup.setup_id, None, row.state, at, req.request_id)
    result.inserted += 1
    result.state_changes.append(StateChange(setup.setup_id, None, row.state, at, "new"))


async def _reconcile(
    session: AsyncSession,
    result: ApplyResult,
    instrument: Instrument,
    req: EvaluateRequest,
    setup: Setup,
    rows: dict[str, AISetup],
    versions: dict[str, str | None],
    now: datetime,
    new: set[str],
) -> None:
    """Bring a stored setup to the current state ai-service reports (after the transitions):
    the same state updates the fields; a later one missing from the history is recorded as a
    forward move when ``ALLOWED`` (else rejected, nothing taken); an earlier one is a contract
    error and nothing of the item is taken (our state and payload are kept)."""
    payload = setup.payload()
    row = rows[setup.setup_id]
    fresh = setup.setup_id in new
    if not fresh and (row.instrument_id != instrument.id or row.profile != req.profile):
        _reject(result, setup.setup_id, "the setup_id belongs to another instrument or profile")
        return
    ours, theirs = SetupState(row.state), setup.state
    if theirs != ours:
        if STATE_RANK[theirs] <= STATE_RANK[ours]:
            # backwards: nothing of this item is taken (its fields describe the earlier state)
            _contract_error(
                result, setup.setup_id, f"sent as {theirs.value} but it is {ours.value} already"
            )
            return
        if ours in FINAL_STATES or theirs not in ALLOWED[ours]:
            _reject(result, setup.setup_id, f"{ours.value} -> {theirs.value} is not allowed")
            return
        # a forward move without its transition: recorded like one, at bar_close_ts
        if await _event(
            session,
            row.setup_id,
            ours.value,
            theirs.value,
            req.bar_close_ts,
            req.request_id,
            reason="new_setups",
        ):
            result.state_changes.append(
                StateChange(row.setup_id, ours.value, theirs.value, req.bar_close_ts, "new_setups")
            )
            await _close_takes(
                session, row.setup_id, theirs.value, req.bar_close_ts, None, "new_setups"
            )
        row.state = theirs.value
        payload = {**payload, "state": row.state}
    if ours in FINAL_STATES:
        result.unchanged += 1  # final: never changes again
        return
    if row.last_payload == payload:
        if not fresh:
            result.unchanged += 1
        return
    for name, value in {**_values(setup), **versions}.items():
        setattr(row, name, value)
    row.last_payload = payload
    row.last_request_id = req.request_id
    row.updated_at = now
    if not fresh:
        result.updated += 1


async def _apply_transition(
    session: AsyncSession,
    result: ApplyResult,
    instrument: Instrument,
    req: EvaluateRequest,
    t: Transition,
    rows: dict[str, AISetup],
    known: set[tuple[str, str, datetime]],
    now: datetime,
) -> None:
    row = rows.get(t.setup_id)
    if row is None:
        _reject(result, t.setup_id, "unknown setup_id")
        return
    if row.instrument_id != instrument.id or row.profile != req.profile:
        _reject(result, t.setup_id, "the setup_id belongs to another instrument or profile")
        return
    if (t.setup_id, t.to.value, t.at) in known:
        result.transitions_known += 1  # already recorded: a re-applied response
        return
    current = SetupState(row.state)
    if STATE_RANK[t.from_] < STATE_RANK[current] and (
        t.to == current or STATE_RANK[t.to] < STATE_RANK[current]
    ):
        # history the setup has already passed (each response repeats the full history)
        result.transitions_known += 1
        return
    if current in FINAL_STATES:
        _reject(result, t.setup_id, f"{current.value} is final ({t.from_.value} -> {t.to.value})")
        return
    if t.from_ != current:
        _reject(result, t.setup_id, f"from {t.from_.value} but the setup is {current.value}")
        return
    if t.to not in ALLOWED[current]:
        _reject(result, t.setup_id, f"{current.value} -> {t.to.value} is not allowed")
        return
    await _event(
        session,
        t.setup_id,
        current.value,
        t.to.value,
        t.at,
        req.request_id,
        reason=t.reason,
        realized_r=t.realized_r,
    )
    known.add((t.setup_id, t.to.value, t.at))
    await _close_takes(session, t.setup_id, t.to.value, t.at, t.realized_r, t.reason)
    row.state = t.to.value
    if t.realized_r is not None:
        row.realized_r = t.realized_r
    payload = copy.deepcopy(row.last_payload)
    payload["state"] = t.to.value
    row.last_payload = payload
    row.last_request_id = req.request_id
    row.updated_at = now
    result.transitions_applied += 1
    result.state_changes.append(
        StateChange(t.setup_id, current.value, t.to.value, t.at, t.reason, t.realized_r)
    )


async def open_setups(
    session: AsyncSession, instrument: Instrument, profile: str
) -> list[dict[str, Any]]:
    """The ``open_setups`` of the next evaluate request: every non-final setup of this
    instrument and profile, as last returned (oldest first)."""
    rows = await session.scalars(
        select(AISetup.last_payload)
        .where(
            AISetup.instrument_id == instrument.id,
            AISetup.profile == profile,
            AISetup.state.not_in(FINAL),
        )
        .order_by(AISetup.created_at, AISetup.setup_id)
    )
    return list(rows.all())


# --- model registry ----------------------------------------------------------------------------


async def register_model(
    session: AsyncSession,
    model_id: str,
    *,
    training_from: datetime | None = None,
    training_to: datetime | None = None,
    data_hash: str | None = None,
    metrics: dict[str, Any] | None = None,
    notes: str | None = None,
) -> AIModelVersion:
    """Add a model to the registry (inactive), or update the description of a known one
    (e.g. a version ai-service reported first). Activation is separate."""
    values = {
        "training_from": training_from,
        "training_to": training_to,
        "data_hash": data_hash,
        "metrics": metrics or {},
        "notes": notes,
    }
    await session.execute(
        insert(AIModelVersion)
        .values(model_id=model_id, **values)
        .on_conflict_do_update(index_elements=["model_id"], set_=values)
    )
    await session.commit()
    row = await session.get(AIModelVersion, model_id, populate_existing=True)
    assert row is not None
    return row


async def activate_model(session: AsyncSession, model_id: str) -> AIModelVersion | None:
    """Make ``model_id`` the only active model (one transaction). None when it is unknown."""
    row = await session.get(AIModelVersion, model_id, with_for_update=True)
    if row is None:
        return None
    await session.execute(
        update(AIModelVersion)
        .where(AIModelVersion.is_active.is_(True), AIModelVersion.model_id != model_id)
        .values(is_active=False)
    )
    await session.execute(
        update(AIModelVersion).where(AIModelVersion.model_id == model_id).values(is_active=True)
    )
    await session.commit()
    return await session.get(AIModelVersion, model_id, populate_existing=True)
