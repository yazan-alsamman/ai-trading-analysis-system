"""Step 3: backtests through the API, completion over the WebSocket, compare."""

from tests_e2e.conftest import recv_until, run, ws_connect


def test_backtests_and_compare(http, world, make_account):
    trader = make_account("trader")
    start, end = world.data["history"]
    ids: list[str] = []

    async def go() -> None:
        async with ws_connect(trader.token) as ws:
            for key, params in (("ma_crossover", {"fast": 3, "slow": 8}), ("rsi_reversal", {})):
                res = http.post(
                    "/backtests",
                    json={
                        "instrument_id": world.instrument_id,
                        "timeframe": "1m",
                        "strategy_key": key,
                        "params": params,
                        "start": start.isoformat(),
                        "end": end.isoformat(),
                    },
                    headers=trader.h,
                )
                assert res.status_code == 202, res.text
                ids.append(res.json()["id"])
            done: set[str] = set()
            while done != set(ids):
                msg = await recv_until(
                    ws,
                    lambda m: m.get("type") in ("backtest_completed", "backtest_failed"),
                    timeout=90,
                )
                assert msg["type"] == "backtest_completed", msg
                done.add(msg["backtest_id"])

    run(go())
    bt = http.get(f"/backtests/{ids[0]}", headers=trader.h).json()
    assert bt["status"] == "completed" and bt["metrics"]["trades"] >= 1
    res = http.post("/backtests/compare", json={"ids": ids}, headers=trader.h)
    assert res.status_code == 200, res.text
    assert len(res.json()["items"]) == 2
