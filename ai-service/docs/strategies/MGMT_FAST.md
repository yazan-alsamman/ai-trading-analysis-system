# Managing the five's trades by their path (stage 2, registered before any outcome)

**Registered 2026-11-12, before any outcome of these rules was computed.** Fadi's choice ("Yes,
register it") after stage 1 (`TRADE_PATH.md`): on 2012-2021, trades that reached +1 R within 15
minutes went on +0.67 R from there (t 3.7, all five strategies), and a give-back of 30% from a
1.5 R peak was followed by +0.21 R on average. Both say the current management (M8) stops trades out
too early. The entries do not change; only how open trades are managed.

Code: `app/research/mgmt_fast.py`, `python -m app research mgmt-fast --export <GOLD M1>`.
Report: `mgmt_fast_result.md`.

## 1. The cells (the five's frozen entries, one open trade per strategy, exit by 16:45 New York or
the horizon, as now)

- **BASE = M8** (now): at +1 R the stop goes to entry + cost, then trails the last confirmed 5m
  swing ∓ 0.1 x ATR(14, 5m). Must reproduce `gold_lab.simulate(..., "M8")` exactly.
- A trade is **fast** if it reaches +1 R on one of the two 5m bars after its entry bar (stage 1's
  "under 15 minutes").
- **F1:** fast trades keep the original stop until +2 R, then go to entry + cost and trail as M8;
  other trades as M8.
- **F2:** fast trades go to entry + cost at +1 R and trail the last confirmed **15m** swing ∓ 0.1 x
  ATR(14, 15m); other trades as M8.
- **F3:** fast trades keep the original stop until +2 R, then entry + cost and the 15m trail; other
  trades as M8.
- **A1:** every trade as M8 but with the 15m trail (more room for all, from the give-back reading).

Swings: the last swing low (high) confirmed by the bar (2 bars each side), as `gold_lab`; the 15m
swing is known at the 5m bar after its 15m bar closes. Cost and slip as now ($0.10 on stop exits).

## 2. Decision

1. **Choice on 2012-2021:** the cell with the best mean net R with slip, the five pooled; it must
   beat BASE there, in at least 60% of the years, with a block-bootstrap t >= 2 for the difference.
2. **Check 2022 to 2026-01-09:** chosen − BASE > 0.
3. **FxPro GOLD 2016-02 to 2026-11-05** (summary bars dropped): chosen − BASE > 0.

Passing all three: a new EA version with that management is proposed to Fadi for the demo (v1's
management changes only by his registered decision). Also reported: the sum and largest drawdown in
R, the share of trades that are fast, and each strategy.

Count: 4 cells in `TRIALS.md`.
