"""``POST /v1/evaluate`` (P6 task 4): one request -> new setups, transitions, abstentions.

ai-service is stateless. Every request re-derives all setups of its window with the live scanner
and compares them with ``open_setups`` (the backend's echo of every non-final setup as last
returned):

1. a setup decided on the evaluated bar is a **new setup**, sent in its first state (``ARMED``),
   with its later changes of the same bar as transitions (L1: ``ARMED -> ACTIVE``);
2. an echoed setup gets one **transition** per state change after its echoed state;
3. an echoed setup the window no longer produces is ``INVALIDATED`` (``not_reproduced``);
4. a setup decided earlier, still open and not echoed (the backend missed a bar) is sent again
   as a new setup in its current state.

A bar without a new setup gets abstentions: ``rules_not_met`` for each pattern the builder
rejected on it (``detail``: the rule), otherwise ``no_pattern``. v1 has no model
(``versions.model``, ``probability``, ``ev_r`` and ``grade`` are null), so its answer is
``status: ok``. Bars that fail the data-quality checks give ``data_quality_failed`` with one
abstention and nothing else.

Prices in a setup are rounded to the request's ``tick_size``; the exact research values are in
``evidence.plan`` (the replay of task 5 compares those). The same request always gives the same
response: nothing here reads a clock, a random source or a file other than the configuration."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from decimal import Decimal
from functools import cache
from typing import Any

import pandas as pd

from app.config import Instrument, Profile, instruments, profiles, strategy
from app.contract import (
    FINAL_STATES,
    Abstention,
    EvaluateRequest,
    EvaluateResponse,
    EvaluateStatus,
    Setup,
    SetupState,
    Transition,
    Versions,
    iso_z,
)
from app.live.frames import DataQualityError, build_frames
from app.live.scanner import LiveSetup, Step, scan

SERVICE_VERSION = "0.1.0"
FEATURES_VERSION = "none"  # v1 computes no model features


class LiveVersions(Versions):
    """The contract's versions plus the cost model and the service (the backend ignores extra
    fields of a response)."""

    costs: str
    service: str


class LiveEvaluateResponse(EvaluateResponse):
    versions: LiveVersions


class UnknownInput(ValueError):
    """An instrument or profile ai-service has no configuration for (answered with 422)."""

    def __init__(self, field: str, value: str, known: list[str]):
        super().__init__(f"unknown {field} {value!r}; known: {', '.join(known)}")
        self.field = field


def _digest(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, default=str).encode()
    return hashlib.sha256(raw).hexdigest()[:10]


@cache
def versions(profile: str, symbol: str) -> dict[str, Any]:
    """The answer's ``versions``: rule set plus a digest of its parameters and the profile,
    the cost model of the instrument, the service version."""
    prof = profiles()[profile]
    p = strategy(prof.rules)
    inst = instruments()[symbol]
    costs = {k: getattr(inst, k) for k in ("cost_extra_frac", "cost_extra_min", "sl_slippage")}
    return {
        "strategy": f"{p.rule_set}-{_digest([asdict(p), asdict(prof)])}",
        "model": None,
        "features": FEATURES_VERSION,
        "costs": f"costs-{_digest(costs)}",
        "service": SERVICE_VERSION,
    }


def config_for(req: EvaluateRequest) -> tuple[Profile, Instrument]:
    if req.profile not in profiles():
        raise UnknownInput("profile", req.profile, sorted(profiles()))
    if req.instrument not in instruments():
        raise UnknownInput("instrument", req.instrument, sorted(instruments()))
    return profiles()[req.profile], instruments()[req.instrument]


def to_tick(x: float, tick: float) -> float:
    places = max(0, -Decimal(str(tick)).as_tuple().exponent)
    return round(round(x / tick) * tick, places)


def _ts(t: pd.Timestamp) -> str:
    return iso_z(t.to_pydatetime())


def setup_id(req: EvaluateRequest, ls: LiveSetup) -> str:
    return f"{req.instrument.lower()}-{req.profile}-{ls.setup.setup_id}"


def payload(req: EvaluateRequest, ls: LiveSetup, step: Step) -> dict[str, Any]:
    """The contract setup in the state of ``step``."""
    st, pl, pt = ls.setup, ls.setup.plan, ls.setup.pattern
    tick = req.instrument_spec.tick_size
    lv = pt.primary
    out: dict[str, Any] = {
        "setup_id": setup_id(req, ls),
        "instrument": req.instrument,
        "profile": req.profile,
        "state": step.state.value,
        "direction": pt.direction,
        "entry": to_tick(pl.entry, tick),
        "sl": to_tick(pl.sl, tick),
        "tp": to_tick(pl.tp, tick),
        "r_multiple": round(pl.r_multiple, 4),
        "probability": None,
        "ev_r": None,
        "ev_r_lower": None,
        "grade": None,
        "valid_until": _ts(ls.valid_until),
        "horizon_until": _ts(ls.horizon_until),
        "created_at": _ts(ls.created_at),
        "evidence": {
            "rules": versions(req.profile, req.instrument)["strategy"],
            "level": {
                "source": lv.source,
                "side": lv.side,
                "price": lv.price,
                "origin_utc": _ts(lv.origin_utc),
            },
            "levels_taken": len(pt.levels),
            "sweep": {"extreme": pt.sweep.extreme, "depth_atr": pt.sweep.depth_atr},
            "choch_ref_price": pt.choch.ref_price,
            "fvg": None
            if pt.fvg is None
            else {"low": pt.fvg.low, "high": pt.fvg.high, "size_atr": pt.fvg.size_atr},
            "target_source": pl.target.source,
            "atr": pt.sweep.atr,
            "spread": st.spread,
            "plan": {"entry": pl.entry, "sl": pl.sl, "tp": pl.tp, "risk": pl.risk},
        },
        "features": {},
    }
    if step.state == SetupState.CLOSED:
        out["exit_reason"] = step.reason
        out["realized_r"] = step.realized_r
    return out


def _transition(sid: str, before: SetupState, step: Step) -> Transition:
    return Transition(
        setup_id=sid,
        from_=before,
        to=step.state,
        at=step.at.to_pydatetime(),
        reason=step.reason,
        realized_r=step.realized_r,
    )


def evaluate(req: EvaluateRequest) -> LiveEvaluateResponse:
    prof, inst = config_for(req)
    p = strategy(prof.rules)
    ver = LiveVersions.model_validate(versions(req.profile, req.instrument))
    try:
        live = build_frames(req, inst, p, prof)
    except DataQualityError as e:
        return LiveEvaluateResponse(
            request_id=req.request_id,
            status=EvaluateStatus.data_quality_failed,
            versions=ver,
            abstentions=[Abstention(reason=e.reason, detail=e.detail)],
        )
    found = scan(live.frames, p, inst)
    as_of = live.as_of
    by_id = {setup_id(req, ls): ls for ls in found if not ls.rejected}
    echoed = {s.setup_id: s for s in req.open_setups}

    new_setups: list[Setup] = []
    transitions: list[Transition] = []
    for sid, ls in sorted(by_id.items(), key=lambda kv: (kv[1].created_at, kv[0])):
        if sid in echoed:
            continue
        if ls.created_at == as_of:  # rule 1
            first, *rest = ls.path
            new_setups.append(Setup.model_validate(payload(req, ls, first)))
            before = first.state
            for step in rest:
                transitions.append(_transition(sid, before, step))
                before = step.state
        elif ls.state not in FINAL_STATES:  # rule 4
            new_setups.append(Setup.model_validate(payload(req, ls, ls.path[-1])))

    for sid, old in sorted(echoed.items()):
        if old.state in FINAL_STATES:
            continue
        ls = by_id.get(sid)
        if ls is None:  # rule 3
            gone = Step(SetupState.INVALIDATED, as_of, "not_reproduced")
            transitions.append(_transition(sid, old.state, gone))
            continue
        states = [s.state for s in ls.path]
        later = ls.path[states.index(old.state) + 1 :] if old.state in states else ls.path[-1:]
        before = old.state
        for step in later:  # rule 2
            if step.state != before:
                transitions.append(_transition(sid, before, step))
                before = step.state

    abstentions = []
    if not any(ls.created_at == as_of for ls in by_id.values()):
        rejected = [ls for ls in found if ls.rejected and ls.created_at == as_of]
        abstentions = [
            Abstention(
                reason="rules_not_met",
                detail={
                    "setup_id": setup_id(req, ls),
                    "direction": ls.setup.pattern.direction,
                    "rule": ls.label.reason,
                },
            )
            for ls in sorted(rejected, key=lambda ls: setup_id(req, ls))
        ] or [Abstention(reason="no_pattern")]

    transitions.sort(key=lambda t: (t.at, t.setup_id))
    return LiveEvaluateResponse(
        request_id=req.request_id,
        status=EvaluateStatus.ok,
        versions=ver,
        new_setups=new_setups,
        transitions=transitions,
        abstentions=abstentions,
    )
