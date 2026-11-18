# The live gold-levels engine against the research trades

_`python -m app research gold-levels-check --from 2025-07-01 --to 2026-01-08`: 138 New York weekdays; the engine on request-sized frames (5m 3,000, 1h 500, 4h 300, D1 260 + the day in progress) at 16:55 New York, against `gold_live.five_trades` with ROUND on the full store._

| Item | Value |
| --- | --- |
| Research trades | 650 |
| Engine trades (CLOSED) | 650 |
| Matched (strategy, level, fill bar) | 650 |
| Same direction | 650 |
| Net R difference, largest / mean | 0.228029 / 0.000351 |
| Trades on a bar where two levels of the strategy were touched | 43 |
| Of them with a different R | 1 |
| Largest difference on the other trades | 0.000000 |
| Research only | 0 |
| Engine only | 0 |
| Paths at 10:00 that start the 16:55 path (no look-ahead) | 1,932 of 1,932 |

Two levels of one strategy touched on the same bar: the EA's stop orders fill in price order, so the engine takes the level nearer the bar's open (ties: the EA's level order) and the other is `strategy_busy`. The research code (`gold_lab.simulate`) sorts these with an unstable sort, so it can take the farther level's entry while labelling the trade with the nearer one. The engine follows the EA; the research code is frozen and unchanged.

