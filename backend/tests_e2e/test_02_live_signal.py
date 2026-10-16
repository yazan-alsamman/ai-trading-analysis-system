"""Step 2 (and 6): a market with 1m candles, a strategy with notify and a price alert. On the next
closed bar the beat-scheduled engine sends the signal with a trade plan, an inbox notification and
the price alert over the WebSocket.

The candles are written through the admin candles API (the same path as ``simulate-live``) with
known closes ending in a dip, so RSI(1) crosses up and the alert fires on that bar every time.
"""

import math
from datetime import UTC, datetime, timedelta

from tests_e2e.conftest import RUN, recv_until, run, ws_connect

RSI1 = {"length": 1, "oversold": 30.0, "overbought": 70.0}


def _candle(ts: datetime, prev: float, close: float) -> dict:
    return {
        "ts": ts.isoformat(),
        "open": prev,
        "high": round(max(prev, close) + 0.1, 4),
        "low": round(min(prev, close) - 0.1, 4),
        "close": close,
        "volume": 1.0,
    }


def test_live_signal_and_price_alert(http, world, make_account):
    admin, trader = world.admin, make_account("trader")
    res = http.post(
        "/admin/instruments",
        json={
            "symbol": f"E2E{RUN}/USDT",
            "source": "e2e",
            "market": "crypto",
            "price_precision": 2,
            "quantity_precision": 4,
        },
        headers=admin.h,
    )
    assert res.status_code == 201, res.text
    world.instrument_id = iid = res.json()["id"]
    now = datetime.now(UTC)
    minute = now.replace(second=0, microsecond=0)
    if now.second >= 45:  # too close to the boundary: target the next bar
        minute += timedelta(minutes=1)
    # 400 minutes of history (the backtests use it), then a dip: RSI(1) crosses 30 upward on the
    # target bar, which the engine evaluates ~10 s after it closes
    closes = [round(10 + 2 * math.sin(i / 9), 4) for i in range(400)] + [10.0, 9.0, 8.0, 9.0]
    start = minute - timedelta(minutes=len(closes) - 1)
    candles, prev = [], closes[0]
    for i, close in enumerate(closes):
        candles.append(_candle(start + timedelta(minutes=i), prev, close))
        prev = close
    res = http.post(f"/admin/instruments/{iid}/candles", json={"candles": candles}, headers=admin.h)
    assert res.status_code == 200 and res.json()["written"] == len(candles), res.text
    world.data["history"] = (start, minute - timedelta(minutes=5))
    res = http.post(
        "/me/strategies",
        json={
            "strategy_key": "rsi_reversal",
            "instrument_id": iid,
            "timeframe": "1m",
            "params": RSI1,
            "notify": True,
        },
        headers=trader.h,
    )
    assert res.status_code == 201, res.text
    res = http.post(
        "/me/price-alerts",
        json={"instrument_id": iid, "condition": "above", "value": 8.5, "note": "e2e"},
        headers=trader.h,
    )
    assert res.status_code == 201, res.text
    world.data["alert_id"] = res.json()["id"]

    async def wait() -> dict:
        got: dict = {}
        wanted = {"signal_topic", "user_signal", "notification", "price_alert"}
        async with ws_connect(trader.token) as ws:
            await ws.send(f'{{"op":"subscribe","topic":"signals","instrument_id":"{iid}"}}')
            while not wanted <= set(got):
                msg = await recv_until(
                    ws,
                    lambda m: m.get("type") in ("signal", "notification", "price_alert"),
                    timeout=140,
                )
                if msg["type"] == "signal":
                    key = "user_signal" if msg["topic"].startswith("user:") else "signal_topic"
                    got[key] = msg
                elif msg["type"] == "notification" and msg["notification"]["type"] == "signal":
                    got["notification"] = msg
                elif msg["type"] == "price_alert":
                    got["price_alert"] = msg
        return got

    got = run(wait())
    signal = got["user_signal"]["signal"]
    assert (signal["side"], signal["strategy_key"], signal["timeframe"]) == (
        "buy",
        "rsi_reversal",
        "1m",
    )
    assert signal["bar_time"].startswith(minute.isoformat()[:16])
    assert "plan" in got["user_signal"] and got["user_signal"]["plans"]
    assert got["notification"]["notification"]["title"]
    world.data["price_alert"] = got["price_alert"]
    inbox = http.get("/me/notifications", params={"type": "signal"}, headers=trader.h).json()
    assert inbox["total"] >= 1


def test_price_alert_fired(http, world, make_account):
    """Step 6: the alert fired on the simulated bar, once, and is now off."""
    trader = make_account("trader")
    msg = world.data["price_alert"]
    assert msg["alert_id"] == world.data["alert_id"] and msg["price"] >= 8.5
    alerts = http.get("/me/price-alerts", headers=trader.h).json()["items"]
    [alert] = [a for a in alerts if a["id"] == world.data["alert_id"]]
    assert (alert["is_active"], alert["trigger_count"]) == (False, 1)
    history = http.get("/me/price-alerts/history", headers=trader.h).json()
    assert history["items"][0]["alert_id"] == world.data["alert_id"]
