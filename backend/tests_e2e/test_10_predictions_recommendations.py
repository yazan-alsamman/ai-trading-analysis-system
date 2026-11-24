"""Step 10 (Y16, Y17): strategy signals become predictions with outcomes, and recommendations.

A market with 1m candles shaped so that RSI(1) crosses up 30 on four chosen bars (A, B, D and
the last closed one, C), followed by what each case needs over the horizon
(``PREDICTION_HORIZON_BARS``, 10): A rises (tp_hit), B misses a bar (a data gap: expired, left
out of the stats), D falls (sl_hit), C has no horizon yet (open). The trader runs the built-in
``rsi_reversal``; the analyst a **private** custom strategy with the same trigger.

The engine's ``signals.evaluate`` is queued for those four bars the way the beat tick queues it
(instead of waiting for live bars), then ``predictions.resolve_signals`` once.
"""

import math
from datetime import datetime

from tests_e2e.conftest import (
    MINUTE,
    bars,
    new_market,
    send_task,
    this_minute,
    wait_for,
    write_candles,
)

RSI1 = {"length": 1, "oversold": 30.0, "overbought": 70.0}
CLOSE = {"type": "price", "field": "close"}
UP_DAY = {  # the same trigger as RSI(1) crossing 30: the close turns up after a dip
    "schema_version": 1,
    "category": "mean_reversion",
    "strength": "fixed",
    "buy": {"all": [{"left": CLOSE, "op": "crosses_above", "right": {**CLOSE, "shift": 1}}]},
    "sell": {"all": [{"left": CLOSE, "op": "crosses_below", "right": {**CLOSE, "shift": 1}}]},
}
HISTORY = 400
HORIZON = 10
# minutes before the current one: (bar, what follows it over the horizon)
CASES = {"A": (90, "up"), "B": (60, "gap"), "D": (30, "down"), "C": (1, None)}


def shaped_closes() -> list[float | None]:
    """Closes of the HISTORY minutes before the current one (index HISTORY - m is the bar m
    minutes ago): a gentle wave, a dip and an up-close on each case's bar, then its horizon."""
    closes: list[float | None] = [round(10 + 0.3 * math.sin(k / 9), 4) for k in range(HISTORY)]
    for ago, after in CASES.values():
        x = HISTORY - ago
        closes[x - 1] = round(closes[x - 2] - 0.5, 4)  # the dip: RSI(1) 0
        closes[x] = round(closes[x - 1] + 0.2, 4)  # up again: RSI(1) 100, crosses 30
        for i in range(1, HORIZON + 1):
            if after == "up":
                closes[x + i] = round(closes[x] + 0.1 * i, 4)
            elif after == "down":
                closes[x + i] = round(closes[x] - 0.1 * i, 4)
            elif after == "gap":
                closes[x + i] = None if i == 1 else round(closes[x] + 0.1 * i, 4)
    return closes


def predictions(http, account, **params) -> list[dict]:
    res = http.get("/predictions", params={"limit": 200, **params}, headers=account.h)
    assert res.status_code == 200, res.text
    return res.json()["items"]


def test_signals_predictions_recommendations(http, world, make_account):
    trader, analyst = make_account("trader"), make_account("analyst")
    iid, _ = new_market(http, world, "P")
    now = this_minute()
    start = now - HISTORY * MINUTE
    write_candles(http, world, iid, bars(start, shaped_closes()))
    bar_of = {name: now - ago * MINUTE for name, (ago, _) in CASES.items()}

    # 1. activations: the trader's built-in strategy, the analyst's private custom one
    res = http.post(
        "/me/strategies",
        json={"strategy_key": "rsi_reversal", "instrument_id": iid, "timeframe": "1m",
              "params": RSI1, "notify": False},
        headers=trader.h,
    )  # fmt: skip
    assert res.status_code == 201, res.text
    res = http.post(
        "/me/custom-strategies",
        json={"name": "E2E private up-close", "kind": "builder", "definition": UP_DAY},
        headers=analyst.h,
    )
    assert res.status_code == 201, res.text
    custom = f"custom:{res.json()['id']}"
    res = http.post(
        "/me/strategies",
        json={"strategy_key": custom, "instrument_id": iid, "timeframe": "1m", "notify": False},
        headers=analyst.h,
    )
    assert res.status_code == 201, res.text
    for name in ("C", "A", "B", "D"):  # C first: it must still be fresh for the recommendations
        send_task("signals.evaluate", iid, "1m", bar_of[name].isoformat())

    def signals_of(account, count):
        items = predictions(http, account, source="strategy", instrument_id=iid)
        return items if len(items) == count else None

    mine = wait_for(lambda: signals_of(trader, 4), "the trader's four signals")
    theirs = wait_for(lambda: signals_of(analyst, 8), "the analyst's eight signals")
    by_bar = {}
    for item in theirs:
        detail = http.get(f"/predictions/{item['id']}", headers=analyst.h).json()
        bar = datetime.fromisoformat(detail["signal"]["bar_time"].replace("Z", "+00:00"))
        by_bar[(item["strategy_key"], bar)] = item["id"]
    ids = {
        (key, name): by_bar[(key, bar_of[name])]
        for key in ("rsi_reversal", custom)
        for name in CASES
    }
    assert {i["strategy_key"] for i in mine} == {"rsi_reversal"}  # B12: not the private one
    assert all(i["direction"] == "buy" and i["outcome"] == "open" for i in theirs)

    # 2. recommendations: only your own active strategies, fresh signals, with your plan
    def strategy_items(account):
        res = http.get("/me/recommendations", params={"limit": 50}, headers=account.h)
        assert res.status_code == 200, res.text
        return res.json()

    def here(items):  # this market only: other suites' live signals are recommendations too
        return [r for r in items if r["source"] == "strategy" and r["instrument_id"] == iid]

    recos = strategy_items(trader)
    signal_recos = here(recos)
    assert [r["id"] for r in signal_recos] == [ids[("rsi_reversal", "C")]], recos
    [reco] = signal_recos
    assert reco["plan"] is not None and reco["age_bars"] <= 3, reco
    assert reco["track_record"] is not None and 0 <= reco["score"] <= 1
    if world.data.get("ai_setup_id"):  # step 9: the followed, taken setup (ACTIVE)
        ai = [r for r in recos if r["source"] == "ai"]
        assert [r["id"] for r in ai] == [f"ai:{world.data['ai_setup_id']}"], recos
    theirs_reco = here(strategy_items(analyst))
    assert [r["id"] for r in theirs_reco] == [ids[(custom, "C")]]

    def fits(account) -> list[dict]:
        res = http.get(
            "/recommendations/strategies",
            params={"instrument_id": iid, "timeframe": "1m", "limit": 20},
            headers=account.h,
        )
        assert res.status_code == 200, res.text
        return res.json()

    for account, active in ((trader, "rsi_reversal"), (analyst, custom)):
        entries = fits(account)
        assert [e["rank"] for e in entries] == list(range(1, len(entries) + 1))
        order = sorted(
            entries,
            key=lambda e: (
                e["insufficient_history"],
                -(e["hit_rate_lower"] or 0.0) if not e["insufficient_history"] else 0.0,
                -e["decided"],
                e["strategy_key"],
            ),
        )
        assert entries == order
        assert {e["strategy_key"] for e in entries if e["already_active"]} == {active}
    assert custom not in {e["strategy_key"] for e in fits(trader)}  # B12
    assert custom in {e["strategy_key"] for e in fits(analyst)}

    # 3. resolution over the horizon (A up, B gap, D down; C still open)
    send_task("predictions.resolve_signals")
    wait_for(
        lambda: all(
            i["outcome"] != "open"
            for i in predictions(http, trader, instrument_id=iid)
            if i["id"] != ids[("rsi_reversal", "C")]
        ),
        "the resolver",
        timeout=90,
    )
    outcomes = {i["id"]: i for i in predictions(http, analyst, instrument_id=iid)}
    for key in ("rsi_reversal", custom):
        got = {name: outcomes[ids[(key, name)]]["outcome"] for name in CASES}
        assert got == {"A": "tp_hit", "B": "expired", "D": "sl_hit", "C": "open"}, (key, got)
        assert outcomes[ids[(key, "B")]]["note"].startswith("gap"), outcomes[ids[(key, "B")]]
    detail = http.get(f"/predictions/{ids[('rsi_reversal', 'A')]}", headers=trader.h).json()
    outcome = detail["signal"]["outcome"]
    assert outcome["correct"] is True and outcome["horizon_bars"] == HORIZON, detail
    resolver = http.get("/admin/predictions/resolver", headers=world.admin.h).json()
    assert resolver["last_status"] == "ok" and resolver["last_run_at"], resolver

    # stats: hit rate over tp_hit + sl_hit; the gap is excluded, not counted as expired
    def stats(account) -> dict:
        res = http.get(
            "/predictions/stats",
            params={"source": "strategy", "instrument_id": iid},
            headers=account.h,
        )
        assert res.status_code == 200, res.text
        return res.json()

    for account, n in ((trader, 1), (analyst, 2)):
        s = stats(account)
        got = (s["tp_hit_count"], s["sl_hit_count"], s["expired_count"], s["excluded_count"])
        assert got == (n, n, 0, n), s
        assert (s["hit_rate"], s["open"], s["total"]) == (0.5, n, 3 * n), s
        assert s["brier_score"] is None and s["calibration"] == []  # v1: no probabilities
    assert {b["strategy_key"] for b in stats(trader)["by_strategy"]} == {"rsi_reversal"}

    # B12: the private strategy's rows never reach another user
    for name in CASES:
        assert http.get(f"/predictions/{ids[(custom, name)]}", headers=trader.h).status_code == 404
    keys = {i["strategy_key"] for i in predictions(http, trader, instrument_id=iid)}
    assert keys == {"rsi_reversal"}
