"""Step 9 (B9 to B11): the AI engine against the fake ai-service (tools/fake_ai_service, profile
``fake-ai``; the e2e job sets ``AI_SERVICE_URL=http://fake-ai:8001`` and
``AI_EVALUATE_ENABLED=true`` for its stack only).

A market with contract specs and 1m candles with a spread (enough for the data-quality gate:
200 bars of 15m, fresh), then ``ai.evaluate`` queued the way beat queues it, on four closed 15m
bars in a row instead of waiting for the boundaries:

1. the fake abstains: the run is recorded (``ai_evaluation_runs``, through
   ``/admin/system/status``) and no setup is created;
2. the fake's life cycle: DEVELOPING (not published), ARMED (published: the follower is
   notified over the WebSocket, a user who did not follow is not; an API key without
   ``signals:read`` cannot read it, B12), then the follower sizes and takes it (B10), and
   ACTIVE reaches the taker (B11).
"""

import math
from datetime import timedelta

from tests_e2e.conftest import (
    MINUTE,
    bars,
    fake,
    iso_z,
    need,
    new_market,
    recv_until,
    run,
    send_task,
    system_status,
    this_minute,
    wait_for,
    write_candles,
    ws_connect,
)

PROFILE = "intraday"
STEP = timedelta(minutes=15)
HISTORY = 3100  # minutes: the gate's 200 bars of 15m before the oldest evaluated bar, and more
SPREAD = 0.02
SPECS = {
    "contract_size": 1,
    "tick_size": 0.01,
    "lot_step": 0.01,
    "min_lot": 0.01,
    "max_lot": 100,
    "price_basis": "mid",
}


def close_at(k: int) -> float:
    """A smooth price around 100 (moves far below the gate's 2 % spike check)."""
    return round(100 + 0.6 * math.sin(k / 37) + 0.2 * math.sin(k / 7), 2)


class Market:
    """The run's AI market: candles up to the last closed minute, topped up before each
    evaluation so the gate's freshness check (lag <= 120 s) holds however long the step takes."""

    def __init__(self, http, world):
        self.http, self.world = http, world
        self.id, self.symbol = new_market(http, world, "AI", **SPECS)
        self.start = this_minute() - HISTORY * MINUTE
        self.end = self.start  # first minute not written yet
        self.top_up()

    def top_up(self) -> None:
        last = this_minute()  # the minute still running is not written
        n = int((last - self.end) / MINUTE)
        if n <= 0:
            return
        k0 = int((self.end - self.start) / MINUTE)
        closes = [close_at(k0 - 1)] + [close_at(k0 + i) for i in range(n)]
        candles = bars(self.end - MINUTE, closes, spread=SPREAD)[1:]
        write_candles(self.http, self.world, self.id, candles)
        self.end = last

    def evaluate(self, bar_close) -> dict:
        """Queue ``ai.evaluate`` for the bar closing at ``bar_close`` and wait for its run."""
        self.top_up()
        send_task("ai.evaluate", "e2e", self.symbol, PROFILE, iso_z(bar_close))

        def recorded():
            runs = system_status(self.http, self.world)["ai_evaluate"]["last_runs"]
            return next(
                (
                    r
                    for r in runs
                    if r["instrument"] == f"e2e:{self.symbol}"
                    and r["profile"] == PROFILE
                    and r["bar_close_ts"] == iso_z(bar_close)
                ),
                None,
            )

        return wait_for(recorded, f"the evaluation run of {iso_z(bar_close)}", timeout=90)

    def setups(self) -> list[dict]:
        res = self.http.get(
            "/admin/ai/setups", params={"instrument_id": self.id}, headers=self.world.admin.h
        )
        assert res.status_code == 200, res.text
        return res.json()


def ai_notes(http, account) -> list[dict]:
    res = http.get("/me/notifications", params={"type": "ai_setup"}, headers=account.h)
    assert res.status_code == 200, res.text
    return res.json()["items"]


def test_ai_evaluate_follow_size_take(http, world, make_account):
    need(system_status(http, world)["ai_evaluate"]["enabled"], "AI evaluate (B9)")
    trader, analyst = make_account("trader"), make_account("analyst")
    market = Market(http, world)
    world.data["ai_market"] = market.id
    res = http.put(f"/me/ai/follows/{market.id}/{PROFILE}", json={}, headers=trader.h)
    assert res.status_code == 200, res.text
    boundary = market.end.replace(minute=market.end.minute - market.end.minute % 15)

    # 1. an abstention: recorded, no setup
    fake("fake-ai", 8001, "/_fake/reset", {})
    fake("fake-ai", 8001, "/_fake/mode", {"evaluate": "abstain"})
    first = market.evaluate(boundary - 3 * STEP)
    assert first["status"] == "ok" and first["coverage"]["15m"] >= 200, first
    assert market.setups() == []
    received = fake("fake-ai", 8001, "/_fake/requests")
    assert [r["path"] for r in received] == ["/v1/evaluate"]

    # 2. the life cycle: DEVELOPING is stored but not published
    fake("fake-ai", 8001, "/_fake/reset", {})
    assert market.evaluate(boundary - 2 * STEP)["status"] == "ok"
    [setup] = market.setups()
    setup_id = setup["setup_id"]
    assert setup["state"] == "DEVELOPING"
    params = {"source": "ai", "instrument_id": market.id}
    assert http.get("/predictions", params=params, headers=trader.h).json()["total"] == 0

    # ARMED: the follower hears it live
    async def armed() -> dict:
        async with ws_connect(trader.token) as ws:
            await ws.send('{"op": "ping"}')  # the connection is registered before the run
            await recv_until(ws, lambda m: m.get("type") == "pong")
            assert market.evaluate(boundary - STEP)["status"] == "ok"
            return await recv_until(
                ws,
                lambda m: (
                    m.get("type") == "notification"
                    and m["notification"]["type"] == "ai_setup"
                    and m["notification"]["data"]["setup_id"] == setup_id
                ),
                timeout=60,
            )

    note = run(armed())["notification"]
    assert note["data"]["state"] == "ARMED" and note["data"]["instrument"]["id"] == market.id
    assert market.setups()[0]["state"] == "ARMED"
    assert ai_notes(http, analyst) == []  # did not follow
    page = http.get("/predictions", params=params, headers=trader.h).json()
    assert [(p["id"], p["outcome"]) for p in page["items"]] == [(f"ai:{setup_id}", "open")]
    res = http.get(f"/ai/setups/{setup_id}/explanation", headers=trader.h)
    assert res.status_code == 200, res.text  # the fake has no /v1/explain: "unavailable"

    # B12: a principal without signals:read sees nothing of it
    res = http.post(
        "/me/api-keys", json={"name": "e2e no signals", "scopes": ["market:read"]}, headers=trader.h
    )
    assert res.status_code == 201, res.text
    key = {"X-API-Key": res.json()["key"]}
    assert http.get(f"/ai/setups/{setup_id}/size", headers=key).status_code == 403
    assert http.get(f"/ai/setups/{setup_id}/explanation", headers=key).status_code == 403
    assert http.get("/predictions", params=params, headers=key).status_code == 403

    # B10: size and take
    res = http.get(f"/ai/setups/{setup_id}/size", headers=trader.h)
    assert res.status_code == 200, res.text
    size = res.json()
    assert size["lots"] > 0 and size["taken"] is False and size["source"], size
    res = http.post(f"/ai/setups/{setup_id}/take", json={}, headers=trader.h)
    assert res.status_code == 201, res.text
    assert http.post(f"/ai/setups/{setup_id}/take", json={}, headers=trader.h).status_code == 200
    trades = http.get("/me/ai/trades", headers=trader.h).json()
    assert [t["setup_id"] for t in trades["items"]] == [setup_id]

    # ACTIVE: the taker is told (B11)
    assert market.evaluate(boundary)["status"] == "ok"
    assert market.setups()[0]["state"] == "ACTIVE"
    notes = wait_for(
        lambda: [n for n in ai_notes(http, trader) if n["data"]["state"] == "ACTIVE"],
        "the ACTIVE alert to the taker",
    )
    assert notes[0]["data"]["setup_id"] == setup_id
    world.data["ai_setup_id"] = setup_id
