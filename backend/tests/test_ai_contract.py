"""B7 ai-service contract: the committed examples validate, the validation rules, the exact echo
of setups, and the size example matches the B4 sizing of the same trade."""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from trading_backtest.sizing import ContractSpec, lots_for_risk

from app.ai import contract as c

EXAMPLES = Path(__file__).resolve().parents[2] / "docs" / "api" / "ai-service-examples"
MODELS = {
    "evaluate-request": c.EvaluateRequest,
    "evaluate-response-ok": c.EvaluateResponse,
    "evaluate-response-ok-rules-only": c.EvaluateResponse,
    "evaluate-response-model-unavailable": c.EvaluateResponse,
    "size-request": c.SizeRequest,
    "size-response": c.SizeResponse,
    "size-request-fixed-cost": c.SizeRequest,
    "size-response-fixed-cost": c.SizeResponse,
    "explain-request": c.ExplainRequest,
    "explain-response": c.ExplainResponse,
}


def load(name: str) -> dict:
    return json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", sorted(MODELS))
def test_examples_validate(name: str) -> None:
    MODELS[name].model_validate(load(name))


def test_every_example_is_checked() -> None:
    assert {p.stem for p in EXAMPLES.glob("*.json")} == set(MODELS)


def test_ok_example_content() -> None:
    resp = c.EvaluateResponse.model_validate(load("evaluate-response-ok"))
    assert resp.status == c.EvaluateStatus.ok
    # 0.2.0: the current state of every setup, and the full history of each
    new, closed = resp.new_setups
    assert new.state == c.SetupState.ARMED and new.grade is None  # always null in v1
    assert closed.state == c.SetupState.CLOSED
    assert new.created_at == datetime.fromisoformat("2026-10-19T14:15:00+00:00")
    assert [(t.from_, t.to) for t in resp.transitions if t.setup_id == closed.setup_id] == [
        (c.SetupState.DEVELOPING, c.SetupState.ARMED),
        (c.SetupState.ARMED, c.SetupState.ACTIVE),
        (c.SetupState.ACTIVE, c.SetupState.CLOSED),
    ]
    transition = resp.transitions[2]
    assert transition.model_dump(mode="json")["from"] == "ACTIVE"  # the alias on the wire
    [abstention] = resp.abstentions
    assert abstention.detail == {"side": "sell", "ev_r_lower": -0.12, "threshold": 0.0}
    req = c.EvaluateRequest.model_validate(load("evaluate-request"))
    assert req.request_id == c.make_request_id("XAUUSD", "intraday", req.bar_close_ts)
    assert req.request_id == "xauusd-intraday-2026-10-19T14:15:00Z"


def test_size_example_is_the_b4_hand_example() -> None:
    req = c.SizeRequest.model_validate(load("size-request"))
    resp = c.SizeResponse.model_validate(load("size-response"))
    spec = req.instrument_spec
    risk = req.account.balance * req.risk.risk_per_trade_pct / 100
    sized = lots_for_risk(
        risk,
        req.setup.entry,
        req.setup.sl,
        ContractSpec(spec.contract_size, spec.lot_step, "USD", spec.min_lot, spec.max_lot),
        req.account.currency,
        1.0,
    )
    assert (sized.lots, resp.lots, resp.risk_usd) == (0.04, 0.04, 20.0)
    notional = resp.lots * spec.contract_size * req.setup.entry
    assert resp.margin_required == pytest.approx(notional / req.account.leverage)


def _setup(**changes) -> dict:
    base = load("evaluate-response-ok")["new_setups"][0]
    return {**base, **changes}


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"sl": 2405.0}, "buy: sl < entry < tp"),
        ({"direction": "sell"}, "sell: tp < entry < sl"),
        ({"tp": None}, "needs entry, sl and tp"),
        ({"probability": 1.2}, "less than or equal to 1"),
        ({"entry": float("inf")}, "finite"),
        ({"entry": -1}, "greater than 0"),
        ({"valid_until": "2026-10-19T15:15:00"}, "timezone"),
        ({"state": "PENDING"}, "DEVELOPING"),
    ],
)
def test_setup_rules(changes: dict, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        c.Setup.model_validate(_setup(**changes))


def test_unpriced_states_need_no_prices() -> None:
    for state in ("DEVELOPING", "CLOSED", "EXPIRED", "INVALIDATED"):
        c.Setup.model_validate({"setup_id": "s", "state": state, "direction": "sell"})


def test_setup_echo_is_exact() -> None:
    """open_setups sends a setup back exactly as received, unknown fields included."""
    raw = _setup(entry=2400, valid_until="2026-10-19T15:15:00+00:00", extra_field={"k": [1, 2]})
    setup = c.Setup.model_validate(raw)
    assert setup.payload() == raw
    assert setup.valid_until.isoformat() == "2026-10-19T15:15:00+00:00"
    req = load("evaluate-request")
    req["open_setups"] = [raw]
    sent = c.EvaluateRequest.model_validate(req).model_dump(mode="json", by_alias=True)
    assert sent["open_setups"] == [raw]
    assert sent["bar_close_ts"] == "2026-10-19T14:15:00Z"


def test_timestamps_are_utc() -> None:
    bar = c.Bar.model_validate(
        {"ts": "2026-10-19T16:00:00+02:00", "o": 1, "h": 2, "l": 1, "c": 2, "spread": None}
    )
    assert bar.ts == datetime.fromisoformat("2026-10-19T14:00:00+00:00")
    assert bar.model_dump(mode="json")["ts"] == "2026-10-19T14:00:00Z"
    with pytest.raises(ValidationError, match="timezone"):
        c.Bar.model_validate({"ts": "2026-10-19T14:00:00", "o": 1, "h": 2, "l": 1, "c": 2})
    with pytest.raises(ValidationError, match="inconsistent OHLC"):
        c.Bar.model_validate({"ts": "2026-10-19T14:00:00Z", "o": 3, "h": 2, "l": 1, "c": 2})


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda r: r.update(request_id="xauusd-intraday-x"), "request_id must be"),
        (lambda r: r.update(extra=1), "Extra inputs are not permitted"),
        (lambda r: r["bars"]["15m"].pop(), "must end with the bar closing at bar_close_ts"),
        (lambda r: r["bars"]["15m"].reverse(), "oldest first"),
        (lambda r: r.update(bar_close_ts="2026-10-19T14:00:00Z"), "request_id must be"),
        (lambda r: r["instrument_spec"].update(min_lot=200), "min_lot must be <= max_lot"),
        (lambda r: r["calendar"][0].update(impact="High"), "'high'"),
        (lambda r: r.update(bars={}), "at least one timeframe"),
    ],
)
def test_request_rules(change, message: str) -> None:
    req = load("evaluate-request")
    change(req)
    with pytest.raises(ValidationError, match=message):
        c.EvaluateRequest.model_validate(req)


def test_bars_of_a_higher_timeframe_must_be_closed() -> None:
    req = load("evaluate-request")
    req["bars"]["1h"].append({"ts": "2026-10-19T14:00:00Z", "o": 1, "h": 1, "l": 1, "c": 1})
    with pytest.raises(ValidationError, match=r"bars\[1h\]: the last bar is not closed"):
        c.EvaluateRequest.model_validate(req)


def test_responses_ignore_unknown_fields() -> None:
    resp = load("evaluate-response-ok")
    resp["debug"] = {"took_ms": 41}
    resp["versions"]["build"] = "abc"
    resp["transitions"][0]["note"] = "x"
    parsed = c.EvaluateResponse.model_validate(resp)
    assert not hasattr(parsed, "debug") and parsed.transitions[0].to == c.SetupState.ARMED
    c.SizeResponse.model_validate({**load("size-response"), "lots_raw": 0.0412})
    with pytest.raises(ValidationError):
        c.EvaluateResponse.model_validate({**resp, "status": "maybe"})


def test_contract_module_needs_only_pydantic() -> None:
    """ai-service can vendor app/ai/contract.py; the api-contract CI job imports it alone."""
    code = (
        "import sys; import app.ai.contract; "
        "bad = [m for m in ('sqlalchemy', 'fastapi', 'app.core.config') if m in sys.modules]; "
        "print(bad); sys.exit(1 if bad else 0)"
    )
    backend = Path(__file__).resolve().parents[1]
    done = subprocess.run([sys.executable, "-c", code], cwd=backend, capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr


# --- contract 0.2.0 (Fadi's answers) ------------------------------------------------------------


def test_version_is_0_2_2() -> None:
    assert c.CONTRACT_VERSION == "0.2.2"


def test_cost_per_unit_is_optional_and_sent_when_set() -> None:
    """0.2.2: ``InstrumentSpec.cost_per_unit`` (the fixed round-trip cost per unit). Without it
    the spec serialises exactly as in 0.2.1 (no key); with it, the key is there."""
    spec = load("size-request")["instrument_spec"]
    plain = c.InstrumentSpec.model_validate(spec)
    assert plain.cost_per_unit is None and "cost_per_unit" not in plain.model_dump(mode="json")
    costly = c.InstrumentSpec.model_validate({**spec, "cost_per_unit": 0.25})
    assert costly.model_dump(mode="json")["cost_per_unit"] == 0.25
    body = json.loads(json.dumps(c.SizeRequest.model_validate(load("size-request-fixed-cost"))
                                 .model_dump(mode="json", by_alias=True)))  # fmt: skip
    assert body["instrument_spec"]["cost_per_unit"] == 0.25
    with pytest.raises(ValidationError):
        c.InstrumentSpec.model_validate({**spec, "cost_per_unit": -0.25})
    assert (
        "cost_per_unit"
        not in c.EvaluateRequest.model_validate(load("evaluate-request")).model_dump(mode="json")[
            "instrument_spec"
        ]
    )


def test_size_example_with_the_fixed_cost_matches_b4() -> None:
    """XAU/USD, balance 2,000, 1 % = 20 USD, entry 2400, sl 2395, cost 0.25: (5 + 0.25) x 100 =
    525 USD per lot -> 0.03 lots, 15.75 USD at risk, margin 0.03 x 100 x 2400 / 100 = 72."""
    req = c.SizeRequest.model_validate(load("size-request-fixed-cost"))
    resp = c.SizeResponse.model_validate(load("size-response-fixed-cost"))
    spec = req.instrument_spec
    risk = req.account.balance * req.risk.risk_per_trade_pct / 100
    sized = lots_for_risk(
        risk,
        req.setup.entry,
        req.setup.sl,
        ContractSpec(spec.contract_size, spec.lot_step, "USD", spec.min_lot, spec.max_lot),
        req.account.currency,
        1.0,
        cost_per_unit=spec.cost_per_unit,
    )
    assert (sized.lots, resp.lots) == (0.03, 0.03)
    assert resp.risk_usd == pytest.approx(sized.risk_amount) == 15.75
    notional = resp.lots * spec.contract_size * req.setup.entry
    assert resp.margin_required == pytest.approx(notional / req.account.leverage)


@pytest.mark.parametrize(
    ("inside", "opens", "closes"),
    [
        # winter (EST): 17:00 New York = 22:00 UTC
        ("2026-01-14T12:00:00Z", "2026-01-13T22:00:00Z", "2026-01-14T22:00:00Z"),
        # March: DST starts on Sunday 8 March; the day opening on Saturday at 22:00 UTC closes
        # on Sunday at 21:00 UTC (23 hours)
        ("2026-03-08T10:00:00Z", "2026-03-07T22:00:00Z", "2026-03-08T21:00:00Z"),
        ("2026-03-09T12:00:00Z", "2026-03-08T21:00:00Z", "2026-03-09T21:00:00Z"),
        # November: DST ends on Sunday 1 November; that day lasts 25 hours
        ("2026-11-01T21:30:00Z", "2026-10-31T21:00:00Z", "2026-11-01T22:00:00Z"),
        ("2026-11-02T12:00:00Z", "2026-11-01T22:00:00Z", "2026-11-02T22:00:00Z"),
        # exactly at the boundary: a new day
        ("2026-10-19T21:00:00Z", "2026-10-19T21:00:00Z", "2026-10-20T21:00:00Z"),
    ],
)
def test_d1_trading_day_is_new_york_17_00(inside: str, opens: str, closes: str) -> None:
    ts = datetime.fromisoformat(inside)
    assert c.iso_z(c.d1_open(ts)) == opens
    assert c.iso_z(c.d1_close(c.d1_open(ts))) == closes
    assert c.bar_close("1d", c.d1_open(ts)) == c.d1_close(c.d1_open(ts))


def test_1d_bars_must_open_at_17_00_new_york() -> None:
    req = load("evaluate-request")
    assert [b["ts"] for b in req["bars"]["1d"]] == ["2026-10-14T21:00:00Z", "2026-10-15T21:00:00Z"]
    c.EvaluateRequest.model_validate(req)
    req["bars"]["1d"][0]["ts"] = "2026-10-14T00:00:00Z"  # a UTC day: refused
    with pytest.raises(ValidationError, match="17:00 America/New_York"):
        c.EvaluateRequest.model_validate(req)
    req = load("evaluate-request")  # the day still open at 14:15 UTC Monday: not closed
    req["bars"]["1d"].append({"ts": "2026-10-18T21:00:00Z", "o": 1, "h": 1, "l": 1, "c": 1})
    with pytest.raises(ValidationError, match=r"bars\[1d\]: the last bar is not closed"):
        c.EvaluateRequest.model_validate(req)


def test_ok_without_a_model_is_valid() -> None:
    """0.2.1 (Fadi, 25 Oct): v1 runs the rules alone, so ``ok`` comes with ``model`` null (this
    test asserted the opposite rule until 0.2.0)."""
    ok = load("evaluate-response-ok")
    ok["versions"]["model"] = None
    assert c.EvaluateResponse.model_validate(ok).versions.model is None
    rules = c.EvaluateResponse.model_validate(load("evaluate-response-ok-rules-only"))
    assert rules.status == c.EvaluateStatus.ok and rules.versions.model is None
    assert rules.versions.strategy and rules.versions.features  # always present
    for s in rules.new_setups:
        assert (s.probability, s.ev_r, s.ev_r_lower, s.grade) == (None, None, None, None)
    unavailable = c.EvaluateResponse.model_validate(load("evaluate-response-model-unavailable"))
    assert unavailable.versions.model is None


def test_abstention_detail_is_an_object() -> None:
    with pytest.raises(ValidationError, match="valid dictionary"):
        c.Abstention.model_validate({"reason": "weak_edge", "detail": "text"})
    assert c.Abstention.model_validate({"reason": "weak_edge"}).detail == {}


def test_created_at_is_optional() -> None:
    raw = _setup()
    raw.pop("created_at")
    assert c.Setup.model_validate(raw).created_at is None
    with pytest.raises(ValidationError, match="timezone"):
        c.Setup.model_validate(_setup(created_at="2026-10-19T14:15:00"))


def test_active_never_goes_to_invalidated() -> None:
    assert c.ALLOWED_TRANSITIONS[c.SetupState.ACTIVE] == {c.SetupState.CLOSED}
    assert c.SetupState.ACTIVE not in c.ALLOWED_TRANSITIONS[c.SetupState.DEVELOPING]


@pytest.mark.parametrize(
    ("direction", "levels", "expected"),
    [
        # buy: stop below, target above -> both rounded down (stop away, target toward entry)
        ("buy", (2400.004, 2395.006, 2410.009), (2400.0, 2395.0, 2410.0)),
        # sell: stop above, target below -> both rounded up
        ("sell", (2400.006, 2405.001, 2390.001), (2400.01, 2405.01, 2390.01)),
        # already on the tick: unchanged (decimal arithmetic, no float drift)
        ("buy", (2400.0, 2395.0, 2410.0), (2400.0, 2395.0, 2410.0)),
        ("sell", (1.08505, None, None), (1.09, None, None)),
    ],
)
def test_round_levels_stop_away_target_toward(direction, levels, expected) -> None:
    """Fadi (point 2): rounding never makes the risk smaller or the reward larger."""
    tick = 0.01
    assert c.round_levels(direction, *levels, tick) == expected
