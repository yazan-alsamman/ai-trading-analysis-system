"""P6 task 6: ``/v1/size`` (the vendored B4 lot arithmetic, quote -> account conversion, margin)."""

import copy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.scoring import lots
from tests.test_contract import REPO, load

client = TestClient(app)
LIBS_SIZING = REPO / "libs" / "backtest" / "trading_backtest" / "sizing.py"


def test_vendored_sizing_is_unchanged() -> None:
    if not LIBS_SIZING.exists():
        pytest.skip("libs not in this checkout")
    vendored = Path(lots.__file__).read_bytes().replace(b"\r\n", b"\n")
    assert vendored == LIBS_SIZING.read_bytes().replace(b"\r\n", b"\n")


def post(body: dict) -> dict:
    res = client.post("/v1/size", json=body)
    assert res.status_code == 200, res.text
    return res.json()


def test_the_contract_hand_example() -> None:
    assert post(load("size-request")) == load("size-response")


def usdjpy(**account) -> dict:
    body = copy.deepcopy(load("size-request"))
    body["setup"] |= {
        "setup_id": "usdjpy-intraday-buy:1h:low:202410100100:149.2",
        "entry": 150.0,
        "sl": 149.5,
        "tp": 151.0,
    }
    body["instrument_spec"] |= {
        "contract_size": 100_000,
        "tick_size": 0.001,
        "quote_currency": "JPY",
    }
    body["account"] = {"balance": 10_000.0, "currency": "USD", "leverage": 100} | account
    return body


def test_usdjpy_converts_yen_to_dollars() -> None:
    # B4 example: 0.5 x 100,000 / 150 = 333.33 USD per lot; 1% of 10,000 = 100 USD -> 0.30 lots
    res = post(usdjpy())
    assert (res["lots"], res["feasible"], res["risk_usd"]) == (0.3, True, 100.0)
    assert res["margin_required"] == pytest.approx(0.3 * 100_000 / 100)  # USD notional / leverage


def test_an_unconvertible_account_currency_is_not_feasible() -> None:
    res = post(usdjpy(currency="EUR"))
    assert res["feasible"] is False and res["lots"] == 0.0
    assert any("conversion rate" in w for w in res["warnings"])


def test_margin_above_the_balance_is_not_feasible() -> None:
    body = load("size-request")
    body["account"]["leverage"] = 1
    body["risk"]["risk_per_trade_pct"] = 50.0
    body["risk"]["daily_loss_limit_pct"] = 60.0
    res = post(body)
    assert res["feasible"] is False and res["margin_required"] is None
    assert any("margin" in w for w in res["warnings"])


def test_risk_above_the_daily_limit_warns() -> None:
    body = load("size-request")
    body["risk"]["risk_per_trade_pct"] = 4.0
    res = post(body)
    assert res["feasible"] is True and res["lots"] == 0.16
    assert any("daily loss limit" in w for w in res["warnings"])


def test_a_final_setup_has_nothing_to_size() -> None:
    body = load("size-request")
    body["setup"]["state"] = "CLOSED"
    res = post(body)
    assert (res["lots"], res["feasible"]) == (0.0, False)


def test_an_unknown_instrument_is_422() -> None:
    body = load("size-request")
    body["setup"]["setup_id"] = "btcusd-intraday-x"
    assert client.post("/v1/size", json=body).status_code == 422


def test_an_evaluate_setup_names_its_instrument() -> None:
    from tests.test_main import body
    from tests.test_main import post as evaluate

    (s,) = evaluate(body()).new_setups
    assert s.payload()["instrument"] == "XAUUSD"
    res = post(load("size-request") | {"setup": s.payload() | {"state": "ACTIVE"}})
    assert res["feasible"] is True and res["lots"] > 0
