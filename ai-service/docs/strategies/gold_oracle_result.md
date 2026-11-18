# The five's hindsight ceiling (a thought experiment)

_`python -m app research gold-oracle`: every trade of the five and ROUND, XAUUSD store, closed at the best price it reached before its real exit. **No rule can do this: it needs the future.** It shows how much of the move the real management keeps. Net R after the trading cost; the real results include the stop slip._

### 2012 to 2026-01-09

| Strategy | Trades | Real winners | **Real** net R | **A** every trade at its best | **B** real winners at their best | MFE median (R) | Real / A |
| --- | --- | --- | --- | --- | --- | --- | --- |
| LVL4H | 1,430 | 49% | +0.121 | +1.062 | +0.465 | 0.96 | 11% |
| PIVOT | 2,790 | 37% | +0.020 | +1.088 | +0.394 | 0.93 | 2% |
| PIVW | 1,266 | 46% | +0.050 | +0.976 | +0.373 | 0.91 | 5% |
| ASIA | 2,089 | 47% | +0.028 | +1.002 | +0.359 | 0.89 | 3% |
| PWHL | 614 | 48% | +0.090 | +1.022 | +0.443 | 0.92 | 9% |
| ROUND | 811 | 50% | +0.155 | +1.080 | +0.501 | 0.98 | 14% |
| **The five** | 8,189 | 44% | +0.050 | +1.040 | +0.398 | 0.92 | 5% |
| **All six** | 9,000 | 44% | +0.059 | +1.043 | +0.407 | 0.92 | 6% |

### 2022 to 2026-01-09

| Strategy | Trades | Real winners | **Real** net R | **A** every trade at its best | **B** real winners at their best | MFE median (R) | Real / A |
| --- | --- | --- | --- | --- | --- | --- | --- |
| LVL4H | 874 | 49% | +0.102 | +1.026 | +0.429 | 0.98 | 10% |
| PIVOT | 824 | 39% | +0.065 | +1.114 | +0.429 | 0.97 | 6% |
| PIVW | 800 | 46% | +0.039 | +0.964 | +0.353 | 0.90 | 4% |
| ASIA | 1,268 | 48% | +0.039 | +1.011 | +0.375 | 0.93 | 4% |
| PWHL | 382 | 49% | +0.096 | +1.013 | +0.428 | 0.89 | 9% |
| ROUND | 525 | 51% | +0.167 | +1.062 | +0.505 | 0.99 | 16% |
| **The five** | 4,148 | 46% | +0.063 | +1.026 | +0.398 | 0.94 | 6% |
| **All six** | 4,673 | 47% | +0.074 | +1.030 | +0.410 | 0.95 | 7% |

## How far the trades went (the five, 2012 to 2026-01-09)

| Best open profit reached | >= 0.5R | >= 1.0R | >= 1.5R | >= 2.0R | >= 3.0R | >= 5.0R |
| --- | --- | --- | --- | --- | --- | --- |
| Share of trades | 66% | 47% | 27% | 16% | 7% | 2% |

## Reading

The ceiling (+1.04 R a trade) is not a sign of an edge waiting to be caught. With a stop at −1 R and
the price a random walk, the chance of reaching +x R before the stop is 1 / (1 + x): 67% for 0.5 R
and 50% for 1 R. The five reach them 66% and 47% of the time, as a coin would. Fewer reach 2 R (16%
against 33%) because M8 moves the stop to break-even at +1 R and the trades end by 16:45. A random
entry would show about the same ceiling; the gap between it and the real result is the price of
not knowing the future, not a management fault (`GOLD_EXIT`, `MGMT_FAST`: no exit rule beat M8).

