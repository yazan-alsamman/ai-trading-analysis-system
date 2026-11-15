# Gold demo against Python

_`python -m app research gold-demo check`: `ReportHistory-592239561.xlsx` against the five strategies in Python on `GOLD_M1_202609100100_202611132359.csv` (FxPro GOLD). Trades placed 2026-11-10 02:00 to 2026-11-13 00:00 (server time). Matched on strategy and the 5-minute bar of the fill._

Turned on in the EA later than the start (server time; Python's earlier trades are not expected): PIVW 2026.11.10 20:40, ASIA 2026.11.10 20:40, PWHL 2026.11.10 20:40, ROUND 2026.11.12 14:10.

| Item | Value |
| --- | --- |
| Python trades | 9 |
| Demo trades | 9 |
| Matched | 9 |
| Same direction | 9 |
| Largest level difference ($) | 0.00 |
| D, demo / Python (median) | 1.0000 |
| Gross R, matched: Python / demo | +0.524 / +0.550 |
| Net R, all: Python / demo | +0.514 / +0.514 |
| Entry slippage, stop fills ($, mean / worst) | +0.89 / +6.73 |

| Strategy | Python | Demo | Matched | Gross R matched, Python / demo | Net R, Python / demo |
| --- | --- | --- | --- | --- | --- |
| LVL4H | 2 | 2 | 2 | +0.942 / +0.937 | +0.934 / +0.807 |
| PIVOT | 2 | 2 | 2 | +1.054 / +1.046 | +1.039 / +1.038 |
| PIVW | 1 | 1 | 1 | +0.260 / +0.256 | +0.251 / +0.252 |
| ASIA | 3 | 3 | 3 | +0.062 / +0.058 | +0.054 / +0.046 |
| PWHL | 1 | 1 | 1 | +0.277 / +0.553 | +0.269 / +0.546 |
| ROUND | 0 | 0 | 0 | - / - | - / - |

## The stop rules (`GOLD_V1.md`): demo trades, mean net R

| Strategy | Demo trades | Mean net R | Reading |
| --- | --- | --- | --- |
| LVL4H | 2 | +0.807 | first check at 100 (98 to go) |
| PIVOT | 2 | +1.038 | first check at 100 (98 to go) |
| PIVW | 1 | +0.252 | first check at 100 (99 to go) |
| ASIA | 3 | +0.046 | first check at 100 (97 to go) |
| PWHL | 1 | +0.546 | first check at 100 (99 to go) |
| ROUND | 0 | - | first check at 100 (100 to go) |
| All | 9 | +0.514 | first check at 100 (91 to go) |

## Python only (0)

| Strategy | Signal bar (server) | Dir | Level |
| --- | --- | --- | --- |

## Demo only (0)

| Strategy | Signal bar (server) | Kind | Dir | Fill | Net R |
| --- | --- | --- | --- | --- | --- |

## Every demo trade

| Opened (server) | Strategy | Kind | Dir | Level | Fill | D | Lots | Exit | Gross R | Net R | Money |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026.11.10 12:17:00 | PIVOT | S1 | -1 | 4080.22 | 4080.17 | 16.05 | 0.03 | ea | +1.642 | +1.635 | +78.71 |
| 2026.11.10 15:30:07 | LVL4H | PDL | -1 | 4054.29 | 4047.56 | 28.11 | 0.01 | sl | +1.143 | +0.901 | +25.33 |
| 2026.11.11 09:24:42 | ASIA | ASH | +1 | 4066.03 | 4066.09 | 27.10 | 0.01 | sl | -1.000 | -1.005 | -27.24 |
| 2026.11.11 16:32:51 | ASIA | ASL | -1 | 4026.54 | 4025.92 | 25.67 | 0.01 | sl | +0.729 | +0.702 | +18.02 |
| 2026.11.11 16:37:22 | LVL4H | PDL | -1 | 4013.67 | 4013.31 | 25.67 | 0.01 | sl | +0.730 | +0.713 | +18.29 |
| 2026.11.12 09:11:53 | ASIA | ASL | -1 | 3962.43 | 3962.42 | 24.26 | 0.02 | sl | +0.444 | +0.441 | +21.38 |
| 2026.11.12 09:32:21 | PIVOT | S1 | -1 | 3957.88 | 3957.84 | 13.82 | 0.03 | sl | +0.450 | +0.442 | +18.32 |
| 2026.11.12 09:32:21 | PIVW | S1 | -1 | 3957.88 | 3957.84 | 24.26 | 0.02 | sl | +0.256 | +0.252 | +12.22 |
| 2026.11.12 16:47:44 | PWHL | PWL | -1 | 3881.57 | 3881.48 | 27.51 | 0.01 | ea | +0.553 | +0.546 | +15.03 |

## Health (`GOLD_MONITOR.md`)

**Status: AMBER** (amber: A4 cost, last 9 (R)).

Red, process (A1): pause the EA until fixed. Red, edge (B, C, D): no move to real money on these rules; nothing is changed in reaction.

### A. Process

| Check | Value | Flag |
| --- | --- | --- |
| A1 match with Python | demo 100%, Python 100% | ok |
| A2 entry slippage, last 9 (R) | +0.032 | ok |
| A3 trades in the last full week | no full week yet | - |
| A4 cost, last 9 (R) | +0.036 | amber |

### B. Edge estimate (prior: half the reference mean, SD 0.10 R)

| Pool | Demo trades | Demo mean | Estimate (90%) | P(edge > 0) | Flag |
| --- | --- | --- | --- | --- | --- |
| LVL4H | 2 | +0.807 | +0.052 (-0.111 to +0.215) | 70% | ok |
| PIVOT | 2 | +1.038 | +0.002 (-0.162 to +0.165) | 51% | ok |
| PIVW | 1 | +0.252 | +0.014 (-0.149 to +0.178) | 56% | ok |
| ASIA | 3 | +0.046 | +0.021 (-0.142 to +0.184) | 58% | ok |
| PWHL | 1 | +0.546 | +0.057 (-0.107 to +0.220) | 71% | ok |
| ROUND | 0 | - | +0.066 (-0.099 to +0.231) | 75% | ok |
| ALL6 | 9 | +0.514 | +0.049 (-0.111 to +0.209) | 69% | ok |

### C. CUSUM (ALL6; good +0.042, broken −0.058)

S now 0.00, highest 0.07, red at h = 3.75 (false alarm on average every 2,030 trades; an edge 0.10 R worse found in about 579). Flag: ok.

### D. Drawdown against history (ALL6)

Current drawdown 0.0 R; worse than 0% of 10,000 historical paths of the same length (95th: 6.7 R, 99th: 8.5 R). Flag: ok.
