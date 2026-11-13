"""Step 12 (B13, contract 0.3.0): the ``gold_levels`` profile and the daily volatility, against
the fake ai-service in its ``gold_levels`` mode.

A market of its own (as step 9), then ``ai.evaluate`` queued the way beat queues it on five
closed 5m bars in a row:

1. three setups without a target come ARMED (``exit_type: trailing``, ``tp`` null): a
   follower hears them over the WebSocket with the exit label in place of the target; the
   trader takes all three, a second follower takes none;
2. the pdh setup goes ACTIVE, then its stop moves twice (``sl_moved``): the taker is told the
   new stop over the WebSocket, the follower who did not take it hears nothing; the pdl setup
   EXPIRES and the round one is INVALIDATED (``strategy_busy``), with no alert;
3. it CLOSES on its trailing stop: ``exit_reason``, the stop history, Y16 (``tp_hit`` by
   ``realized_r``, ``risk_reward`` null);
4. the volatility block of the answers: the first ``ok`` of the day is stored once and read
   back from ``/ai/volatility/today`` and ``/ai/volatility``.
"""

from datetime import timedelta

from tests_e2e.conftest import fake, need, recv_until, run, system_status, wait_for, ws_connect
from tests_e2e.test_09_ai_evaluate import Market, ai_notes

PROFILE = "gold_levels"
STEP = timedelta(minutes=5)


class GoldMarket(Market):
    profile = PROFILE
    suffix = "GL"


def is_alert(m: dict, setup_id: str) -> bool:
    return (
        m.get("type") == "notification"
        and m["notification"]["type"] == "ai_setup"
        and m["notification"]["data"]["setup_id"] == setup_id
    )


def test_gold_levels_lifecycle_and_volatility(http, world, make_account):
    need(system_status(http, world)["ai_evaluate"]["enabled"], "AI evaluate (B9)")
    trader, follower = make_account("trader"), make_account("analyst")  # one account a role
    market = GoldMarket(http, world)
    for account in (trader, follower):
        res = http.put(f"/me/ai/follows/{market.id}/{PROFILE}", json={}, headers=account.h)
        assert res.status_code == 200, res.text
    boundary = market.end.replace(minute=market.end.minute - market.end.minute % 5)
    closes = [boundary - (4 - k) * STEP for k in range(5)]
    fake("fake-ai", 8001, "/_fake/reset", {})
    fake("fake-ai", 8001, "/_fake/mode", {"evaluate": "gold_levels", "volatility": "ok"})

    # 1. ARMED without a target: the follower hears it, with the exit label
    async def armed() -> dict:
        async with ws_connect(trader.token) as ws:
            await ws.send('{"op": "ping"}')
            await recv_until(ws, lambda m: m.get("type") == "pong")
            first = market.evaluate(closes[0])
            assert first["status"] == "ok" and first["coverage"]["5m"] >= 200, first
            return await recv_until(
                ws,
                lambda m: (
                    m.get("type") == "notification"
                    and m["notification"]["type"] == "ai_setup"
                    and "-lvl4h-pdh-" in m["notification"]["data"]["setup_id"]
                ),
                timeout=60,
            )

    note = run(armed())["notification"]
    data = note["data"]
    setup_id = data["setup_id"]
    assert data["state"] == "ARMED" and data["profile"] == PROFILE
    assert data["tp"] is None and data["r_multiple"] is None and data["exit_type"] == "trailing"
    assert data["exit_label"]["en"] == "Exit: trailing stop, or 16:45 New York"
    setups = {s["setup_id"]: s for s in market.setups()}
    assert len(setups) == 3 and {s["state"] for s in setups.values()} == {"ARMED"}
    assert all(s["exit_type"] == "trailing" and s["tp"] is None for s in setups.values())
    assert setups[setup_id]["exit_label"]["ar"] == "الخروج: ستوب متحرك، أو الساعة 16:45 نيويورك"
    for sid in setups:  # the trader takes all three; the follower takes none
        res = http.post(f"/ai/setups/{sid}/take", json={}, headers=trader.h)
        assert res.status_code == 201, res.text

    # 2. ACTIVE, then a stop move reaches the taker live
    assert market.evaluate(closes[1])["status"] == "ok"
    assert {s["setup_id"]: s for s in market.setups()}[setup_id]["state"] == "ACTIVE"

    async def moved() -> dict:
        async with ws_connect(trader.token) as ws:
            await ws.send('{"op": "ping"}')
            await recv_until(ws, lambda m: m.get("type") == "pong")
            assert market.evaluate(closes[2])["status"] == "ok"
            return await recv_until(
                ws,
                lambda m: (
                    is_alert(m, setup_id) and m["notification"]["data"].get("event") == "sl_moved"
                ),
                timeout=60,
            )

    move = run(moved())["notification"]["data"]
    detail = http.get(f"/admin/ai/setups/{setup_id}", headers=world.admin.h).json()
    assert [m["sl"] for m in detail["sl_history"]] == [move["new_sl"]]
    assert detail["sl"] == move["new_sl"] and detail["state"] == "ACTIVE"
    others = [s["setup_id"] for s in market.setups() if s["setup_id"] != setup_id]
    ends = []
    for sid in others:  # the state and its reason, as stored (the last event)
        events = http.get(f"/admin/ai/setups/{sid}", headers=world.admin.h).json()["events"]
        ends.append((events[-1]["to_state"], events[-1]["reason"]))
    assert sorted(ends) == [
        ("EXPIRED", "level_not_touched"),
        ("INVALIDATED", "strategy_busy"),
    ]

    # 3. the second move, then CLOSED on the trailing stop
    assert market.evaluate(closes[3])["status"] == "ok"
    assert market.evaluate(closes[4])["status"] == "ok"
    detail = http.get(f"/admin/ai/setups/{setup_id}", headers=world.admin.h).json()
    assert detail["state"] == "CLOSED" and detail["exit_reason"] == "trailing_stop"
    assert len(detail["sl_history"]) == 2 and detail["realized_r"] > 0
    assert detail["sl"] == detail["sl_history"][-1]["sl"]
    notes = wait_for(
        lambda: [n for n in ai_notes(http, trader) if n["data"]["state"] == "CLOSED"],
        "the CLOSED alert to the taker",
    )
    assert notes[0]["data"]["setup_id"] == setup_id
    mine = ai_notes(http, trader)
    assert len([n for n in mine if n["data"].get("event") == "sl_moved"]) == 2
    assert not [n for n in mine if n["data"]["state"] in ("EXPIRED", "INVALIDATED")]
    theirs = ai_notes(http, follower)
    assert {n["data"]["state"] for n in theirs} == {"ARMED"}  # followed, took nothing
    assert not [n for n in theirs if n["data"].get("event") == "sl_moved"]
    prediction = http.get(f"/predictions/ai:{setup_id}", headers=trader.h)
    assert prediction.status_code == 200, prediction.text
    prediction = prediction.json()
    assert prediction["outcome"] == "tp_hit" and prediction["risk_reward"] is None
    assert prediction["ai"]["exit_type"] == "trailing"
    assert len(prediction["ai"]["sl_history"]) == 2

    # 4. the day's volatility: stored once, from the first ok answer
    res = http.get("/ai/volatility", params={"instrument_id": market.id}, headers=trader.h)
    assert res.status_code == 200, res.text
    [day] = res.json()["items"]
    assert day["status"] == "ok" and day["level"] == "normal"
    assert day["level_label"] == {"ar": "عادي", "en": "Normal"}
    assert day["range_usd"]["p50"] is not None
    today = http.get("/ai/volatility/today", params={"instrument_id": market.id}, headers=trader.h)
    assert today.status_code == 200, today.text
    today = today.json()
    if today["day"] == day["day"]:  # the bars' New York day is today's (not across 17:00)
        assert today["status"] == "ok" and today["level_label"]["en"] == "Normal"
    else:
        assert today["status"] == "pending" and today["reason"], today
    status = system_status(http, world)["ai_evaluate"]
    assert status["volatility"]["last_received"]["status"] == "ok"
