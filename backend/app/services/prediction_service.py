"""The prediction history and its accuracy (Y16, docs/predictions.md).

Two sources in one shape, as one SQL ``UNION ALL``; filters, pagination and every aggregate
run in the database:

- ``ai``: AI setups that were published (reached ARMED, ACTIVE or CLOSED), derived from
  ``ai_setups`` and ``ai_setup_events``. Outcome: ARMED/ACTIVE ``open``; CLOSED ``tp_hit``
  when ``realized_r > 0`` else ``sl_hit``; EXPIRED and INVALIDATED ``expired`` (INVALIDATED
  after ACTIVE should not happen, Fadi: it is shown ``expired`` and logged as a warning).
- ``strategy``: buy/sell rows of ``signals`` with their ``signal_outcomes`` row: none yet
  ``open``, ``correct`` true ``tp_hit``, false ``sl_hit``, null (a data gap) ``expired`` with
  the reason in ``note``. Gap rows are left out of every stat (``excluded_count``).

B12: each branch keeps only what the user may read (``strategy_resolver.visible_signal`` and
``readable_ai_setups``) in its WHERE clause, so totals and stats never count hidden rows.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import (
    Boolean,
    Double,
    String,
    and_,
    case,
    cast,
    exists,
    func,
    literal,
    null,
    or_,
    select,
    union_all,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.evaluate import DECISION
from app.models.ai import AISetup, AISetupEvent, AISetupTake
from app.models.instrument import Instrument
from app.models.prediction import SignalOutcome
from app.models.strategy import Signal
from app.models.user import User
from app.services import strategy_resolver

logger = logging.getLogger(__name__)

AI_PREFIX, SIGNAL_PREFIX = "ai:", "sig:"
PUBLISHED = ("ARMED", "ACTIVE", "CLOSED")
FINAL = ("CLOSED", "EXPIRED", "INVALIDATED")
DECIDED = ("tp_hit", "sl_hit")  # the outcomes the hit rate, Brier and calibration count
BINS = 10  # calibration bins of 0.1


@dataclass(frozen=True)
class Filters:
    source: str | None = None  # "ai" | "strategy" | None (both)
    instrument_id: uuid.UUID | None = None
    timeframe: str | None = None
    strategy_key: str | None = None  # the strategy key, or the profile of an AI setup
    profile: str | None = None  # AI setups only
    outcome: str | None = None
    from_: datetime | None = None  # generated_at >= from
    to: datetime | None = None  # generated_at <= to
    id: str | None = None


def _ai_branch(user: User):
    events = AISetupEvent
    published_at = (
        select(func.min(events.at))
        .where(events.setup_id == AISetup.setup_id, events.to_state.in_(PUBLISHED))
        .scalar_subquery()
    )
    final_at = (
        select(func.max(events.at))
        .where(events.setup_id == AISetup.setup_id, events.to_state == AISetup.state)
        .scalar_subquery()
    )
    outcome = case(
        (AISetup.state.in_(("ARMED", "ACTIVE")), "open"),
        (and_(AISetup.state == "CLOSED", func.coalesce(AISetup.realized_r, 0) > 0), "tp_hit"),
        (AISetup.state == "CLOSED", "sl_hit"),
        else_="expired",
    )
    return (
        select(
            func.concat(AI_PREFIX, AISetup.setup_id).label("id"),
            literal("ai", String).label("source"),
            AISetup.instrument_id.label("instrument_id"),
            Instrument.symbol.label("symbol"),
            literal(DECISION, String).label("timeframe"),
            AISetup.profile.label("strategy_key"),
            AISetup.direction.label("direction"),
            AISetup.probability.label("probability"),
            AISetup.r_multiple.label("risk_reward"),
            func.coalesce(published_at, AISetup.created_at).label("generated_at"),
            case(
                (AISetup.state.in_(FINAL), func.coalesce(final_at, AISetup.updated_at)),
                else_=null(),
            ).label("resolved_at"),
            outcome.label("outcome"),
            AISetup.realized_r.label("realized_r"),
            cast(null(), Double).label("return_pct"),
            AISetup.model_version.label("model_version"),
            exists()
            .where(AISetupTake.setup_id == AISetup.setup_id, AISetupTake.user_id == user.id)
            .label("taken_by_user"),
            cast(null(), String).label("note"),
            literal(False, Boolean).label("excluded"),
            AISetup.state.label("state"),
            exists()
            .where(events.setup_id == AISetup.setup_id, events.to_state.in_(("ACTIVE", "CLOSED")))
            .label("ever_active"),
        )
        .join(Instrument, Instrument.id == AISetup.instrument_id)
        .where(
            or_(
                AISetup.state.in_(PUBLISHED),
                exists().where(events.setup_id == AISetup.setup_id, events.to_state.in_(PUBLISHED)),
            ),
            strategy_resolver.readable_ai_setups(user),
        )
    )


def _signal_branch(user: User):
    out = SignalOutcome
    outcome = case(
        (out.signal_id.is_(None), "open"),
        (out.correct.is_(True), "tp_hit"),
        (out.correct.is_(False), "sl_hit"),
        else_="expired",
    )
    return (
        select(
            func.concat(SIGNAL_PREFIX, cast(Signal.id, String)).label("id"),
            literal("strategy", String).label("source"),
            Signal.instrument_id.label("instrument_id"),
            Instrument.symbol.label("symbol"),
            cast(Signal.timeframe, String).label("timeframe"),
            Signal.strategy_key.label("strategy_key"),
            cast(Signal.side, String).label("direction"),
            cast(null(), Double).label("probability"),  # strength is not a probability
            cast(null(), Double).label("risk_reward"),
            Signal.created_at.label("generated_at"),
            out.resolved_at.label("resolved_at"),
            outcome.label("outcome"),
            cast(null(), Double).label("realized_r"),
            out.return_pct.label("return_pct"),
            cast(null(), String).label("model_version"),
            literal(False, Boolean).label("taken_by_user"),
            out.note.label("note"),
            and_(out.signal_id.is_not(None), out.correct.is_(None)).label("excluded"),
            cast(null(), String).label("state"),
            literal(False, Boolean).label("ever_active"),
        )
        .select_from(Signal)
        .join(Instrument, Instrument.id == Signal.instrument_id)
        .outerjoin(out, out.signal_id == Signal.id)
        .where(strategy_resolver.visible_signal(Signal.strategy_key, user))
    )


def _union(user: User, f: Filters):
    """The visible predictions of ``user`` matching ``f``: (subquery, its WHERE conditions)."""
    branches = []
    if f.source in (None, "ai"):
        branches.append(_ai_branch(user))
    if f.source in (None, "strategy") and f.profile is None:
        branches.append(_signal_branch(user))
    if not branches:  # strategy rows filtered by an AI profile: nothing
        branches.append(_signal_branch(user).where(literal(False, Boolean)))
    u = (union_all(*branches) if len(branches) > 1 else branches[0]).subquery("predictions")
    conds = []
    if f.instrument_id is not None:
        conds.append(u.c.instrument_id == f.instrument_id)
    if f.timeframe is not None:
        conds.append(u.c.timeframe == f.timeframe)
    if f.strategy_key is not None:
        conds.append(u.c.strategy_key == f.strategy_key)
    if f.profile is not None:
        conds.append(and_(u.c.source == "ai", u.c.strategy_key == f.profile))
    if f.outcome is not None:
        conds.append(u.c.outcome == f.outcome)
    if f.from_ is not None:
        conds.append(u.c.generated_at >= f.from_)
    if f.to is not None:
        conds.append(u.c.generated_at <= f.to)
    if f.id is not None:
        conds.append(u.c.id == f.id)
    return u, conds


def _item(row: Any) -> dict[str, Any]:
    data = dict(row._mapping)
    if data.pop("state") == "INVALIDATED" and data.pop("ever_active"):
        logger.warning(
            "predictions: AI setup %s was INVALIDATED after ACTIVE (not expected): shown expired",
            data["id"].removeprefix(AI_PREFIX),
        )
    data.pop("ever_active", None)
    data.pop("excluded")
    return data


async def list_predictions(
    session: AsyncSession, user: User, f: Filters, limit: int, offset: int
) -> tuple[list[dict[str, Any]], int]:
    """Newest first (``generated_at``, then ``id``)."""
    u, conds = _union(user, f)
    total = await session.scalar(select(func.count()).select_from(u).where(*conds))
    rows = await session.execute(
        select(u)
        .where(*conds)
        .order_by(u.c.generated_at.desc(), u.c.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return [_item(row) for row in rows.all()], total


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "Prediction not found")


async def get_prediction(session: AsyncSession, user: User, prediction_id: str) -> dict[str, Any]:
    """One prediction the user may read, with its details: the AI setup's prices and state
    events, or the signal and its outcome row. 404 for an unknown or unreadable id."""
    if prediction_id.startswith(SIGNAL_PREFIX):
        try:
            signal_id = uuid.UUID(prediction_id.removeprefix(SIGNAL_PREFIX))
        except ValueError:
            raise _not_found() from None
        prediction_id = f"{SIGNAL_PREFIX}{signal_id}"  # the canonical spelling
    elif not prediction_id.startswith(AI_PREFIX) or len(prediction_id) > 128 + len(AI_PREFIX):
        raise _not_found()
    u, conds = _union(user, Filters(id=prediction_id))
    row = (await session.execute(select(u).where(*conds))).first()
    if row is None:
        raise _not_found()
    item = _item(row)
    if item["source"] == "ai":
        setup = await session.get(AISetup, prediction_id.removeprefix(AI_PREFIX))
        events = await session.scalars(
            select(AISetupEvent)
            .where(AISetupEvent.setup_id == setup.setup_id)
            .order_by(AISetupEvent.at, AISetupEvent.id)
        )
        item["ai"] = {
            "setup_id": setup.setup_id,
            "state": setup.state,
            "entry": setup.entry,
            "sl": setup.sl,
            "tp": setup.tp,
            "grade": setup.grade,
            "ev_r": setup.ev_r,
            "valid_until": setup.valid_until,
            "events": [
                {
                    "from_state": e.from_state,
                    "to_state": e.to_state,
                    "at": e.at,
                    "reason": e.reason,
                    "realized_r": e.realized_r,
                }
                for e in events
            ],
        }
    else:
        signal = await session.get(Signal, signal_id)
        outcome = await session.get(SignalOutcome, signal_id)
        item["signal"] = {
            "signal_id": signal.id,
            "bar_time": signal.bar_time,
            "price": signal.price,
            "strength": signal.strength,
            "reason": signal.reason,
            "outcome": None
            if outcome is None
            else {
                "horizon_bars": outcome.horizon_bars,
                "exit_ts": outcome.exit_ts,
                "exit_price": outcome.exit_price,
                "return_pct": outcome.return_pct,
                "mfe_pct": outcome.mfe_pct,
                "mae_pct": outcome.mae_pct,
                "correct": outcome.correct,
                "cost_per_unit": outcome.cost_per_unit,
                "note": outcome.note,
                "resolved_at": outcome.resolved_at,
            },
        }
    return item


def _rate(hits: int, misses: int) -> float | None:
    return hits / (hits + misses) if hits + misses else None


async def stats(session: AsyncSession, user: User, f: Filters) -> dict[str, Any]:
    """Aggregates over the same rows as the list (one query each, in SQL). Rows with a data
    gap are left out (``excluded_count``). ``hit_rate`` = tp_hit / (tp_hit + sl_hit): expired
    rows are counted in ``resolved`` and ``expired_count``, not in the rate. Brier score and
    calibration only over decided rows that have a probability (none in v1)."""
    u, conds = _union(user, f)
    included = ~u.c.excluded
    decided = u.c.outcome.in_(DECIDED)
    with_probability = and_(decided, u.c.probability.is_not(None))
    hit = case((u.c.outcome == "tp_hit", 1.0), else_=0.0)

    def count(*where):
        return func.count().filter(and_(*where))

    totals = (
        await session.execute(
            select(
                count(included).label("total"),
                count(u.c.outcome == "open").label("open"),
                count(included, u.c.outcome != "open").label("resolved"),
                count(u.c.outcome == "tp_hit").label("tp"),
                count(u.c.outcome == "sl_hit").label("sl"),
                count(included, u.c.outcome == "expired").label("expired"),
                count(u.c.excluded).label("excluded"),
                func.avg(u.c.realized_r).filter(and_(u.c.source == "ai", decided)).label("r"),
                func.avg(u.c.return_pct)
                .filter(and_(u.c.source == "strategy", decided))
                .label("ret"),
                count(with_probability).label("n_prob"),
                func.avg(u.c.probability).filter(with_probability).label("mean_predicted"),
                func.avg(func.power(u.c.probability - hit, 2))
                .filter(with_probability)
                .label("brier"),
            ).where(*conds)
        )
    ).one()

    bin_ = func.least(func.floor(u.c.probability * BINS), BINS - 1).label("bin")
    bins = await session.execute(
        select(bin_, func.count(), func.avg(u.c.probability), func.avg(hit))
        .where(*conds, with_probability)
        .group_by(bin_)
        .order_by(bin_)
    )
    by = await session.execute(
        select(
            u.c.source,
            u.c.strategy_key,
            count(included),
            count(included, u.c.outcome != "open"),
            count(u.c.outcome == "tp_hit"),
            count(u.c.outcome == "sl_hit"),
        )
        .where(*conds)
        .group_by(u.c.source, u.c.strategy_key)
        .order_by(u.c.source, u.c.strategy_key)
    )
    return {
        "total": totals.total,
        "resolved": totals.resolved,
        "open": totals.open,
        "hit_rate": _rate(totals.tp, totals.sl),
        "tp_hit_count": totals.tp,
        "sl_hit_count": totals.sl,
        "expired_count": totals.expired,
        "excluded_count": totals.excluded,
        "mean_realized_r": totals.r,
        "mean_return_pct": totals.ret,
        "with_probability": totals.n_prob,
        "mean_predicted": totals.mean_predicted,
        "brier_score": totals.brier,
        "calibration": [
            {
                "from": int(b) / BINS,
                "to": (int(b) + 1) / BINS,
                "count": n,
                "mean_predicted": mean_p,
                "observed_rate": rate,
            }
            for b, n, mean_p, rate in bins.all()
        ],
        "by_strategy": [
            {
                "source": source,
                "strategy_key": key,
                "total": total,
                "resolved": resolved,
                "hit_rate": _rate(tp, sl),
            }
            for source, key, total, resolved, tp, sl in by.all()
        ],
    }
