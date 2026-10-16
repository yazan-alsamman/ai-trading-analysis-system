"""Step 4: a custom Builder strategy -> preview -> backtest."""

import time

RSI5 = {"type": "indicator", "name": "rsi", "params": {"length": 5}}
DEFINITION = {
    "schema_version": 1,
    "category": "mean_reversion",
    "strength": "fixed",
    "buy": {"all": [{"left": RSI5, "op": "<", "right": {"type": "constant", "value": 35}}]},
    "sell": {"any": [{"left": RSI5, "op": ">", "right": {"type": "constant", "value": 65}}]},
}


def test_custom_builder(http, world, make_account):
    trader = make_account("trader")
    res = http.post(
        "/me/custom-strategies",
        json={"name": "E2E RSI dip", "kind": "builder", "definition": DEFINITION},
        headers=trader.h,
    )
    assert res.status_code == 201, res.text
    key = f"custom:{res.json()['id']}"
    res = http.post(
        f"/strategies/{key}/preview",
        json={"instrument_id": world.instrument_id, "timeframe": "1m", "limit": 300},
        headers=trader.h,
    )
    assert res.status_code == 200, res.text
    start, end = world.data["history"]
    res = http.post(
        "/backtests",
        json={
            "instrument_id": world.instrument_id,
            "timeframe": "1m",
            "strategy_key": key,
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
        headers=trader.h,
    )
    assert res.status_code == 202, res.text
    bt_id = res.json()["id"]
    deadline = time.time() + 90
    while True:
        status = http.get(f"/backtests/{bt_id}", headers=trader.h).json()["status"]
        if status in ("completed", "failed"):
            break
        assert time.time() < deadline, "the custom backtest did not finish"
        time.sleep(1)
    assert status == "completed"
