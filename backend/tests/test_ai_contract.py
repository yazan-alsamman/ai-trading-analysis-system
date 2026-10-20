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
    "evaluate-response-model-unavailable": c.EvaluateResponse,
    "size-request": c.SizeRequest,
    "size-response": c.SizeResponse,
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
    [setup] = resp.new_setups
    assert setup.state == c.SetupState.ARMED and setup.grade == c.Grade.B
    [transition] = resp.transitions
    assert (transition.from_, transition.to) == (c.SetupState.ACTIVE, c.SetupState.CLOSED)
    assert transition.model_dump(mode="json")["from"] == "ACTIVE"  # the alias on the wire
    assert len(resp.abstentions) == 1
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
    assert not hasattr(parsed, "debug") and parsed.transitions[0].to == c.SetupState.CLOSED
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
