"""P6 task 4: ``/v1/evaluate`` and ``/health`` against the contract, on hand-built gold bars."""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import contract as c
from app.config import instruments
from app.data.sessions import is_open
from app.main import app
from tests.test_contract import load
from tests.test_smc_detector import PATTERN

client = TestClient(app)
XAU = instruments()["XAUUSD"]
SPEC = {
    "contract_size": 100,
    "tick_size": 0.01,
    "lot_step": 0.01,
    "min_lot": 0.01,
    "max_lot": 100,
    "price_basis": "bid",
}
FLAT = (101.0, 102.0, 100.0, 101.0)
SPIKE = (101.0, 113.0, 100.0, 101.0)  # each day at 03:00 New York: the target liquidity
UP = (104.0, 104.5, 103.5, 104.0)
TP_HIT = (104.0, 113.5, 103.8, 113.2)
PATTERN_START = pd.Timestamp("2024-01-18 06:00", tz="America/New_York")  # Thursday


def history() -> pd.DataFrame:
    """Gold trading hours from Sunday 2024-01-07 18:00 New York: flat bars, a daily spike to 113,
    then the detector test's sweep of the previous day's low 100 and CHoCH (close 104.0)."""
    grid = pd.date_range("2024-01-07 23:00", "2024-01-19 20:00", freq="15min", tz="UTC")
    grid = grid[is_open(grid, XAU)]
    ny = grid.tz_convert("America/New_York")
    rows = [SPIKE if (t.hour, t.minute) == (3, 0) else FLAT for t in ny]
    df = pd.DataFrame(rows, columns=["o", "h", "l", "c"])
    df.insert(0, "ts", grid)
    i = int(grid.searchsorted(PATTERN_START))
    df.loc[i : i + len(PATTERN) - 1, ["o", "h", "l", "c"]] = PATTERN
    return df, i + len(PATTERN) - 1  # the decision bar


def body(n_after: int = 0, after=UP, open_setups=(), last=None) -> dict:
    df, d = history()
    end = d + n_after if last is None else last
    df = df.iloc[: end + 1].copy()
    if n_after and last is None:
        df.loc[d + 1 :, ["o", "h", "l", "c"]] = after
    close = df["ts"].iloc[-1] + pd.Timedelta(minutes=15)
    return {
        "request_id": c.make_request_id("XAUUSD", "intraday", close.to_pydatetime()),
        "instrument": "XAUUSD",
        "profile": "intraday",
        "bar_close_ts": c.iso_z(close.to_pydatetime()),
        "bars": {
            "15m": [
                {"ts": c.iso_z(r.ts.to_pydatetime()), "o": r.o, "h": r.h, "l": r.l, "c": r.c}
                | {"spread": 0.3}
                for r in df.itertuples()
            ]
        },
        "open_setups": list(open_setups),
        "instrument_spec": SPEC,
    }


def post(b: dict) -> c.EvaluateResponse:
    res = client.post("/v1/evaluate", json=b)
    assert res.status_code == 200, res.text
    return c.EvaluateResponse.model_validate(res.json())


def test_health() -> None:
    res = client.get("/health").json()
    assert res["status"] == "ok" and res["versions"]["model"] is None
    assert res["versions"]["strategy"].startswith("L1-")
    c.Health.model_validate(res)


def test_signal_placeholder_is_gone() -> None:
    assert client.post("/v1/signal", json={"symbol": "XAUUSD"}).status_code == 404


def test_a_new_setup_is_armed_then_active() -> None:
    resp = post(body())
    assert resp.status == c.EvaluateStatus.ok and resp.versions.model is None
    (s,) = resp.new_setups
    assert (s.state, s.direction, s.entry, s.tp) == (c.SetupState.ARMED, "buy", 104.0, 113.0)
    assert s.sl == round(s.sl, 2) and s.sl < s.entry
    assert s.probability is None and s.grade is None and s.ev_r is None
    assert s.setup_id.startswith("xauusd-intraday-buy:pd:low:")
    (t,) = resp.transitions
    bar_close = c.EvaluateRequest.model_validate(body()).bar_close_ts
    assert (t.setup_id, t.from_, t.to, t.at) == (
        s.setup_id,
        c.SetupState.ARMED,
        c.SetupState.ACTIVE,
        bar_close,
    )
    assert s.payload()["created_at"] == c.iso_z(t.at)
    assert resp.abstentions == []


def echo(resp: c.EvaluateResponse, state: c.SetupState) -> dict:
    """The backend's echo: the setup as returned, its state moved by the transitions."""
    return resp.new_setups[0].payload() | {"state": state.value}


def test_the_horizon_closes_an_echoed_setup() -> None:
    first = post(body())
    n = 48  # strategy.toml horizon_bars
    (t,) = post(body(n_after=n, open_setups=[echo(first, c.SetupState.ACTIVE)])).transitions
    assert (t.from_, t.to, t.reason) == (c.SetupState.ACTIVE, c.SetupState.CLOSED, "timeout")
    assert t.at == c.EvaluateRequest.model_validate(body(n_after=n)).bar_close_ts


def test_tp_hit_gives_the_net_realized_r() -> None:
    first = post(body())
    b = body(n_after=2, after=TP_HIT, open_setups=[echo(first, c.SetupState.ACTIVE)])
    (t,) = post(b).transitions
    plan = first.new_setups[0].payload()["evidence"]["plan"]
    cost = 0.3 + max(0.15, 0.10)
    assert (t.to, t.reason) == (c.SetupState.CLOSED, "tp")
    assert t.realized_r == pytest.approx((113.0 - 104.0 - cost) / plan["risk"], abs=1e-6)
    assert t.at == c.EvaluateRequest.model_validate(body(n_after=1)).bar_close_ts


def test_an_unchanged_echo_gives_nothing() -> None:
    first = post(body())
    resp = post(body(n_after=2, open_setups=[echo(first, c.SetupState.ACTIVE)]))
    assert resp.new_setups == [] and resp.transitions == []
    assert [a.reason for a in resp.abstentions] == ["no_pattern"]


def test_a_missed_bar_resends_the_open_setup() -> None:
    first = post(body())
    (s,) = post(body(n_after=2)).new_setups
    assert s.state == c.SetupState.ACTIVE and s.setup_id == first.new_setups[0].setup_id


def test_an_echo_the_window_does_not_produce_is_invalidated() -> None:
    ghost = post(body()).new_setups[0].payload() | {"setup_id": "xauusd-intraday-ghost"}
    resp = post(body(n_after=1, open_setups=[ghost | {"state": "ACTIVE"}]))
    (t,) = [t for t in resp.transitions if t.setup_id == "xauusd-intraday-ghost"]
    assert (t.to, t.reason) == (c.SetupState.INVALIDATED, "not_reproduced")


def test_same_body_same_bytes() -> None:
    b = body()
    assert (
        client.post("/v1/evaluate", json=b).content == client.post("/v1/evaluate", json=b).content
    )


def test_data_quality_failure() -> None:
    b = body()
    b["bars"]["15m"][-5]["spread"] = None
    resp = post(b)
    assert resp.status == c.EvaluateStatus.data_quality_failed
    assert [a.reason for a in resp.abstentions] == ["missing_spread"]
    assert resp.new_setups == [] and resp.transitions == []


def test_too_little_history() -> None:
    b = body()
    b["bars"]["15m"] = b["bars"]["15m"][-300:]
    assert post(b).abstentions[0].reason == "insufficient_history"


def test_unknown_profile_is_422() -> None:
    b = body()
    b["profile"] = "swing"
    b["request_id"] = b["request_id"].replace("intraday", "swing")
    res = client.post("/v1/evaluate", json=b)
    assert res.status_code == 422
    c.ErrorResponse.model_validate(res.json())


def test_the_contract_example_is_refused_without_enough_history() -> None:
    resp = post(load("evaluate-request"))
    assert resp.status == c.EvaluateStatus.data_quality_failed
