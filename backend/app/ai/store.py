"""Storing ai-service results (B8, docs/ai-contract.md).

ai-service decides setups and their states; the backend only records them:

- ``apply_evaluation`` writes one evaluate response in one transaction and returns the state
  changes (B11 turns them into notifications). Re-applying the same response changes nothing
  and reports no state change.
- Final states (CLOSED, EXPIRED, INVALIDATED) never change again. A transition that is not in
  ``ALLOWED``, that starts from another state than the stored one, or that names an unknown
  setup is rejected and logged; the rest of the response is still applied.
- ``open_setups`` gives the next request's ``open_setups``: the last payload of every
  non-final setup, in a stable order.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contract import (
    FINAL_STATES,
    EvaluateRequest,
    EvaluateResponse,
    EvaluateStatus,
    Setup,
    SetupState,
    Transition,
    Versions,
)
from app.models.ai import AIModelVersion, AISetup, AISetupEvent, AISetupTake
from app.models.instrument import Instrument

logger = logging.getLogger(__name__)

S = SetupState
# The only state changes the backend records (to agree with Fadi, docs/ai-contract.md)
ALLOWED: dict[SetupState, frozenset[SetupState]] = {
    S.DEVELOPING: frozenset({S.ARMED, S.EXPIRED, S.INVALIDATED}),
    S.ARMED: frozenset({S.ACTIVE, S.EXPIRED, S.INVALIDATED}),
    S.ACTIVE: frozenset({S.CLOSED, S.INVALIDATED}),
}
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


def _reject(result: ApplyResult, setup_id: str, reason: str) -> None:
    result.rejected.append(Rejection(setup_id, reason))
    logger.warning(
        "ai-service result rejected: setup %s: %s (%s)", setup_id, reason, result.request_id
    )


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

    for setup in resp.new_setups:
        await _apply_setup(session, result, instrument, req, setup, rows, versions, now)
    for transition in sorted(resp.transitions, key=lambda t: t.at):
        await _apply_transition(session, result, instrument, req, transition, rows, known, now)
    await session.commit()
    logger.info(
        "ai-service %s applied: inserted=%d updated=%d unchanged=%d transitions=%d "
        "known=%d rejected=%d",
        req.request_id,
        result.inserted,
        result.updated,
        result.unchanged,
        result.transitions_applied,
        result.transitions_known,
        len(result.rejected),
    )
    return result


async def _apply_setup(
    session: AsyncSession,
    result: ApplyResult,
    instrument: Instrument,
    req: EvaluateRequest,
    setup: Setup,
    rows: dict[str, AISetup],
    versions: dict[str, str | None],
    now: datetime,
) -> None:
    payload = setup.payload()
    row = rows.get(setup.setup_id)
    if row is None:
        row = AISetup(
            setup_id=setup.setup_id,
            instrument_id=instrument.id,
            profile=req.profile,
            direction=setup.direction.value,
            state=setup.state.value,
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
        await _event(session, setup.setup_id, None, row.state, req.bar_close_ts, req.request_id)
        result.inserted += 1
        result.state_changes.append(
            StateChange(setup.setup_id, None, row.state, req.bar_close_ts, "new")
        )
        return
    if row.instrument_id != instrument.id or row.profile != req.profile:
        _reject(result, setup.setup_id, "the setup_id belongs to another instrument or profile")
        return
    if row.state in FINAL:
        result.unchanged += 1  # final: never changes again
        if payload.get("state") != row.state:
            logger.info(
                "ai-service sent %s as %s, it is already %s (kept)",
                setup.setup_id,
                payload.get("state"),
                row.state,
            )
        return
    if setup.state.value != row.state:
        if setup.state in ALLOWED[SetupState(row.state)]:
            # a forward move reported through new_setups: recorded like a transition
            if await _event(
                session,
                row.setup_id,
                row.state,
                setup.state.value,
                req.bar_close_ts,
                req.request_id,
                reason="new_setups",
            ):
                result.state_changes.append(
                    StateChange(
                        row.setup_id, row.state, setup.state.value, req.bar_close_ts, "new_setups"
                    )
                )
                await _close_takes(
                    session, row.setup_id, setup.state.value, req.bar_close_ts, None, "new_setups"
                )
            row.state = setup.state.value
        else:
            logger.info(
                "ai-service sent %s as %s, it stays %s (never backwards)",
                setup.setup_id,
                setup.state.value,
                row.state,
            )
            payload = {**payload, "state": row.state}
    if row.last_payload == payload:
        result.unchanged += 1
        return
    for name, value in {**_values(setup), **versions}.items():
        setattr(row, name, value)
    row.last_payload = payload
    row.last_request_id = req.request_id
    row.updated_at = now
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
