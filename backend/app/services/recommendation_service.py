"""Recommendations (Y17, docs/recommendations.md): what a user should look at now, from their own
strategies and follows, and which strategies have actually worked on a market.

Advisory only: a score ranks what to look at first. It is not a forecast and never a guarantee.

- Outcomes and counts come from Y16 (``prediction_service``): the same outcome expressions and
  the same grouped stats (``track_records``), never a second definition.
- Track records are per (instrument, timeframe) and not user specific, so they are cached in
  Redis (``RECOMMENDATION_CACHE_SECONDS``). Each user only ever sees the keys they may read (B12).
- The plans shown are the stored ones (``signal_plans``, ``ai_setup_sizes``): no sizing here.
"""

from __future__ import annotations

import json
import logging
import math
import uuid
from datetime import UTC, datetime
from typing import Any

import trading_strategies as ts
from pydantic import ValidationError
from redis.asyncio import Redis
from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import alerts
from app.ai.evaluate import DECISION
from app.core.config import get_settings
from app.models.ai import AIAlertFollow, AISetup, AISetupSize
from app.models.backtest import Backtest, BacktestStatus
from app.models.candle import Timeframe
from app.models.custom_strategy import CustomStrategy, Visibility
from app.models.instrument import Instrument
from app.models.prediction import SignalOutcome
from app.models.risk import RiskProfile, SignalPlan
from app.models.strategy import Signal, UserStrategy
from app.models.user import User
from app.services import prediction_service, risk_service, strategy_resolver
from app.services.market_service import floor_to_bucket

logger = logging.getLogger(__name__)

Z = 1.96  # Wilson 95 %
PRIOR = 0.5  # the score's base without enough history
AGE_DECAY = 0.85  # x per bar of age
RISK_BONUS = 0.05  # a complete risk profile
CANDIDATES = 500  # safety cap of rows read per source
CACHE_PREFIX = "reco:track:"


# --- the numbers ---------------------------------------------------------------------------------


def wilson_lower(hits: int, n: int, z: float = Z) -> float:
    """Lower bound of the Wilson score interval of ``hits / n`` (0 when n = 0):

    ``(p + z²/2n − z·sqrt(p(1−p)/n + z²/4n²)) / (1 + z²/n)``. 5 of 10 → 0.2366,
    58 of 100 → 0.4821."""
    if n <= 0:
        return 0.0
    p = hits / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (centre - margin) / (1 + z * z / n))


def track_record(counts: dict[str, Any] | None) -> dict[str, Any]:
    """The public track record of one key: ``decided`` = tp_hit + sl_hit (the hit rate's n)."""
    counts = counts or {}
    tp, sl = counts.get("tp_hit", 0), counts.get("sl_hit", 0)
    n = tp + sl
    return {
        "resolved": counts.get("resolved", 0),
        "decided": n,
        "hit_rate": tp / n if n else None,
        "hit_rate_lower": wilson_lower(tp, n) if n else None,
        "mean_return_pct": counts.get("mean_return_pct"),
        "mean_realized_r": counts.get("mean_realized_r"),
    }


def score(record: dict[str, Any], age_bars: int, risk_complete: bool) -> tuple[float, list[str]]:
    """``min(1, base × 0.85^age_bars + bonus)``: base = the Wilson lower bound of the hit rate
    with at least ``RECOMMENDATION_MIN_SAMPLES`` decided predictions, else the neutral 0.5;
    bonus = 0.05 with a complete risk profile."""
    minimum = get_settings().recommendation_min_samples
    reasons = []
    n = record["decided"]
    if n >= minimum:
        base = record["hit_rate_lower"]
        reasons.append(
            f"track record: {round(record['hit_rate'] * n)} of {n} hit "
            f"({record['hit_rate']:.0%}), 95% lower bound {base:.0%}"
        )
    else:
        base = PRIOR
        reasons.append(f"not enough history ({n} of {minimum} decided): neutral prior 0.5")
    factor = AGE_DECAY**age_bars
    reasons.append(
        "on the last closed bar"
        if age_bars == 0
        else f"{age_bars} bar{'s' if age_bars > 1 else ''} old: x{factor:.2f}"
    )
    bonus = RISK_BONUS if risk_complete else 0.0
    reasons.append(
        f"risk profile complete: +{RISK_BONUS:g}"
        if risk_complete
        else "risk profile uses defaults: no bonus"
    )
    return round(min(1.0, base * factor + bonus), 4), reasons


def risk_profile_complete(profile: RiskProfile | None) -> bool:
    """Saved with a risk-based size and both guards: no AI risk input comes from a default."""
    if profile is None:
        return False
    try:
        sources = risk_service.ai_risk_inputs(profile).sources
    except ValidationError:
        return False
    return "default" not in sources.values()


# --- cached track records ------------------------------------------------------------------------


def _cache_key(instrument_id: uuid.UUID, timeframe: str) -> str:
    return f"{CACHE_PREFIX}{instrument_id}:{timeframe}"


async def cached_track_records(
    session: AsyncSession, redis: Redis, pairs: set[tuple[uuid.UUID, str]]
) -> dict[tuple[uuid.UUID, str], dict[str, dict[str, Any]]]:
    """Per (instrument, timeframe): ``"<source>:<key>"`` -> Y16 counts, from Redis when cached,
    else one grouped query for every missing pair (then cached). Not user specific."""
    pairs = sorted(pairs, key=lambda p: (str(p[0]), p[1]))
    out: dict[tuple[uuid.UUID, str], dict[str, dict[str, Any]]] = {}
    try:
        cached = await redis.mget([_cache_key(*p) for p in pairs]) if pairs else []
    except Exception:  # noqa: BLE001 - the cache is an optimisation
        logger.warning("recommendations: Redis unavailable, track records not cached")
        cached = [None] * len(pairs)
    for pair, raw in zip(pairs, cached, strict=True):
        if raw:
            out[pair] = json.loads(raw)
    missing = [p for p in pairs if p not in out]
    if missing:
        fresh = await prediction_service.track_records(session, missing)
        ttl = max(1, get_settings().recommendation_cache_seconds)
        try:
            async with redis.pipeline(transaction=False) as pipe:
                for pair in missing:
                    pipe.set(_cache_key(*pair), json.dumps(fresh[pair]), ex=ttl)
                await pipe.execute()
        except Exception:  # noqa: BLE001
            logger.warning("recommendations: could not cache track records")
        out.update(fresh)
    return out


# --- GET /me/recommendations ---------------------------------------------------------------------


def _age(last_closed_end: datetime, start: datetime, timeframe: Timeframe) -> int:
    """Whole bars between the bar starting at ``start`` and the last closed bar."""
    return max(0, int((last_closed_end - start) // timeframe.interval) - 1)


async def for_user(
    session: AsyncSession, redis: Redis, user: User, limit: int, now: datetime | None = None
) -> list[dict[str, Any]]:
    """Actionable now, best first: open signals of the user's active activations (at most
    ``RECOMMENDATION_MAX_AGE_BARS`` old) and open AI setups the user follows. Two queries for
    the items, one (or none: cached) for the track records."""
    settings = get_settings()
    now = now or datetime.now(UTC)
    max_age = max(0, settings.recommendation_max_age_bars)
    ends = {tf: floor_to_bucket(now, tf.interval) for tf in Timeframe}  # end of last closed bar
    recent = or_(
        *(
            and_(Signal.timeframe == tf, Signal.bar_time >= ends[tf] - tf.interval * (max_age + 1))
            for tf in Timeframe
        )
    )
    us = UserStrategy
    signals = await session.execute(
        select(
            Signal.id,
            Signal.instrument_id,
            Instrument.symbol,
            Signal.timeframe,
            Signal.strategy_key,
            Signal.side,
            Signal.bar_time,
            Signal.created_at,
            us.id,
            SignalPlan.plan,
        )
        .select_from(us)
        .join(
            Signal,
            and_(
                Signal.instrument_id == us.instrument_id,
                Signal.timeframe == us.timeframe,
                Signal.strategy_key == us.strategy_key,
                Signal.params_hash == us.params_hash,
            ),
        )
        .join(Instrument, Instrument.id == Signal.instrument_id)
        .outerjoin(SignalOutcome, SignalOutcome.signal_id == Signal.id)
        .outerjoin(
            SignalPlan,
            and_(
                SignalPlan.signal_id == Signal.id,
                SignalPlan.user_id == user.id,
                SignalPlan.user_strategy_id == us.id,
            ),
        )
        .where(
            us.user_id == user.id,
            us.is_active.is_(True),
            recent,
            prediction_service.signal_outcome() == "open",
            strategy_resolver.visible_signal(Signal.strategy_key, user),
        )
        .order_by(Signal.bar_time.desc(), Signal.id)
        .limit(CANDIDATES)
    )
    generated_at = prediction_service.ai_generated_at().label("generated_at")
    setups = await session.execute(
        select(
            AISetup.setup_id,
            AISetup.instrument_id,
            Instrument.symbol,
            AISetup.profile,
            AISetup.direction,
            AISetup.grade,
            generated_at,
            AIAlertFollow.min_grade,
            AISetupSize.lots,
            AISetupSize.risk_usd,
            AISetupSize.margin_required,
            AISetupSize.feasible,
            AISetupSize.warnings,
            AISetupSize.source,
            AISetupSize.inputs,
            AISetupSize.computed_at,
        )
        .join(
            AIAlertFollow,
            and_(
                AIAlertFollow.user_id == user.id,
                AIAlertFollow.instrument_id == AISetup.instrument_id,
                AIAlertFollow.profile == AISetup.profile,
            ),
        )
        .join(Instrument, Instrument.id == AISetup.instrument_id)
        .outerjoin(
            AISetupSize,
            and_(AISetupSize.setup_id == AISetup.setup_id, AISetupSize.user_id == user.id),
        )
        .where(
            prediction_service.ai_outcome() == "open",
            strategy_resolver.readable_ai_setups(user),
        )
        .order_by(generated_at.desc(), AISetup.setup_id)
        .limit(CANDIDATES)
    )
    graded = alerts.min_grade_active()
    candidates: list[dict[str, Any]] = []
    for sid, iid, symbol, tf, key, side, bar_time, created, us_id, plan in signals.all():
        candidates.append(
            {
                "id": f"{prediction_service.SIGNAL_PREFIX}{sid}",
                "source": "strategy",
                "instrument_id": iid,
                "symbol": symbol,
                "timeframe": tf.value,
                "strategy_key": key,
                "direction": side.value,
                "generated_at": created,
                "age_bars": _age(ends[tf], bar_time, tf),
                "user_strategy_id": us_id,
                "plan": plan,
                "plan_missing_reason": None if plan is not None else "no_plan_stored",
            }
        )
    ai_tf = Timeframe(DECISION)
    for row in setups.all():
        (setup_id, iid, symbol, profile, direction, grade, generated, min_grade, lots) = row[:9]
        if graded and not alerts.meets_grade(grade, min_grade):
            continue  # the follow's minimum grade, as for the alerts
        size = None
        if lots is not None:
            size = {
                "lots": lots,
                "risk_amount": row.risk_usd,
                "currency": ((row.inputs or {}).get("account") or {}).get("currency"),
                "margin_required": row.margin_required,
                "feasible": row.feasible,
                "warnings": row.warnings,
                "source": row.source,
                "computed_at": row.computed_at,
            }
        candidates.append(
            {
                "id": f"{prediction_service.AI_PREFIX}{setup_id}",
                "source": "ai",
                "instrument_id": iid,
                "symbol": symbol,
                "timeframe": DECISION,
                "strategy_key": profile,
                "direction": direction,
                "generated_at": generated,
                "age_bars": max(0, int((ends[ai_tf] - generated) // ai_tf.interval)),
                "user_strategy_id": None,
                "plan": size,
                "plan_missing_reason": None if size is not None else "not_sized_yet",
            }
        )
    if not candidates:
        return []
    records = await cached_track_records(
        session, redis, {(c["instrument_id"], c["timeframe"]) for c in candidates}
    )
    complete = risk_profile_complete(await session.get(RiskProfile, user.id))
    for c in candidates:
        counts = records.get((c["instrument_id"], c["timeframe"]), {})
        c["track_record"] = track_record(counts.get(f"{c['source']}:{c['strategy_key']}"))
        c["score"], c["score_reasons"] = score(c["track_record"], c["age_bars"], complete)
    candidates.sort(key=lambda c: (-c["score"], -c["generated_at"].timestamp(), c["id"]))
    return candidates[:limit]


# --- GET /recommendations/strategies -------------------------------------------------------------


async def strategies(
    session: AsyncSession,
    redis: Redis,
    user: User,
    instrument_id: uuid.UUID,
    timeframe: Timeframe,
    limit: int,
) -> list[dict[str, Any]]:
    """Every strategy the user may use (the built-in catalog, their own and public custom ones),
    ranked by the Wilson lower bound of its hit rate on this market. Fewer than
    ``RECOMMENDATION_MIN_SAMPLES`` decided predictions: last, ``insufficient_history``.
    The user's latest completed backtest here is attached for information (not ranked)."""
    minimum = get_settings().recommendation_min_samples
    candidates = [(key, s.title, "builtin") for key, s in sorted(ts.STRATEGIES.items())]
    customs = await session.execute(
        select(CustomStrategy.id, CustomStrategy.name)
        .where(
            or_(
                CustomStrategy.user_id == user.id,
                CustomStrategy.visibility == Visibility.public,
            )
        )
        .order_by(CustomStrategy.created_at, CustomStrategy.id)
    )
    candidates += [(f"custom:{cid}", name, "custom") for cid, name in customs.all()]

    pair = (instrument_id, timeframe.value)
    counts = (await cached_track_records(session, redis, {pair}))[pair]
    active = set(
        await session.scalars(
            select(UserStrategy.strategy_key).where(
                UserStrategy.user_id == user.id,
                UserStrategy.instrument_id == instrument_id,
                UserStrategy.timeframe == timeframe,
                UserStrategy.is_active.is_(True),
            )
        )
    )
    backtests = await session.execute(
        select(
            Backtest.strategy_key,
            Backtest.id,
            Backtest.metrics,
            Backtest.finished_at,
        )
        .ext(distinct_on(Backtest.strategy_key))
        .where(
            Backtest.user_id == user.id,
            Backtest.instrument_id == instrument_id,
            Backtest.timeframe == timeframe,
            Backtest.status == BacktestStatus.completed,
        )
        .order_by(Backtest.strategy_key, Backtest.finished_at.desc().nulls_last())
    )
    latest = {
        key: {
            "id": bid,
            "total_return_pct": (metrics or {}).get("total_return_pct"),
            "win_rate_pct": (metrics or {}).get("win_rate_pct"),
            "max_drawdown_pct": (metrics or {}).get("max_drawdown_pct"),
            "finished_at": finished,
        }
        for key, bid, metrics, finished in backtests.all()
    }
    entries = []
    for key, name, kind in candidates:
        record = track_record(counts.get(f"strategy:{key}"))
        entries.append(
            {
                "strategy_key": key,
                "name": name,
                "kind": kind,
                "resolved": record["resolved"],
                "decided": record["decided"],
                "hit_rate": record["hit_rate"],
                "hit_rate_lower": record["hit_rate_lower"],
                "mean_return_pct": record["mean_return_pct"],
                "insufficient_history": record["decided"] < minimum,
                "already_active": key in active,
                "backtest": latest.get(key),
            }
        )
    entries.sort(
        key=lambda e: (
            e["insufficient_history"],
            -(e["hit_rate_lower"] or 0.0) if not e["insufficient_history"] else 0.0,
            -e["decided"],
            e["strategy_key"],
        )
    )
    for rank, entry in enumerate(entries, start=1):
        entry["rank"] = rank
    return entries[:limit]


# --- the signal notification line (RECOMMENDATIONS_NOTIFY) ---------------------------------------


async def signal_track_records(
    session: AsyncSession, redis: Redis, instrument_id: uuid.UUID, timeframe: Timeframe
) -> dict[str, dict[str, Any]]:
    """strategy key -> its track record on this market, for the signal notification line."""
    pair = (instrument_id, timeframe.value)
    counts = (await cached_track_records(session, redis, {pair}))[pair]
    return {
        key.removeprefix("strategy:"): track_record(value)
        for key, value in counts.items()
        if key.startswith("strategy:")
    }
