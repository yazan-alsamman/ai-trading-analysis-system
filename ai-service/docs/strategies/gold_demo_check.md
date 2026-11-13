# Gold demo: the account's own record

_`python -m app research gold-demo check` without `--export`: `ReportHistory-592239561.html`. No GOLD export covers these days yet, so Python's trades are not compared._

## Orders by strategy (balance 10,165.03)

| Strategy | Orders placed | Lots | D ($, median) | Risk a trade (% of the balance) |
| --- | --- | --- | --- | --- |
| LVL4H | 629 | 0.01, 0.02 | 27.10 | 0.27% |
| PIVOT | 389 | 0.02, 0.03 | 14.11 | 0.41% |
| PIVW | 294 | 0.01, 0.02 | 26.26 | 0.26% |
| ASIA | 46 | 0.01, 0.02 | 27.10 | 0.29% |
| PWHL | 411 | 0.01, 0.02 | 26.26 | 0.26% |
| ROUND | 0 | - | - | - |

## Closed trades

| Opened (server) | Strategy | Kind | Dir | Level | Fill | Slip $ | D | Lots | Exit | Exit price | Gross R | Net R | Money |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026.11.10 12:17:00 | PIVOT | S1 | -1 | 4080.22 | 4080.17 | +0.05 | 16.05 | 0.03 | ea | 4053.86 | +1.642 | +1.635 | +78.71 |
| 2026.11.10 15:30:07 | LVL4H | PDL | -1 | 4054.29 | 4047.56 | +6.73 | 28.11 | 0.01 | sl | 4022.15 | +1.143 | +0.901 | +25.33 |
| 2026.11.11 09:24:42 | ASIA | ASH | +1 | 4066.03 | 4066.09 | +0.06 | 27.10 | 0.01 | sl | 4038.93 | -1.000 | -1.005 | -27.24 |
| 2026.11.11 16:32:51 | ASIA | ASL | -1 | 4026.54 | 4025.92 | +0.62 | 25.67 | 0.01 | sl | 4007.82 | +0.729 | +0.702 | +18.02 |
| 2026.11.11 16:37:22 | LVL4H | PDL | -1 | 4013.67 | 4013.31 | +0.36 | 25.67 | 0.01 | sl | 3994.94 | +0.730 | +0.713 | +18.29 |
| 2026.11.12 09:11:53 | ASIA | ASL | -1 | 3962.43 | 3962.42 | +0.01 | 24.26 | 0.02 | sl | 3951.66 | +0.444 | +0.441 | +21.38 |
| 2026.11.12 09:32:21 | PIVOT | S1 | -1 | 3957.88 | 3957.84 | +0.04 | 13.82 | 0.03 | sl | 3951.66 | +0.450 | +0.442 | +18.32 |
| 2026.11.12 09:32:21 | PIVW | S1 | -1 | 3957.88 | 3957.84 | +0.04 | 24.26 | 0.02 | sl | 3951.66 | +0.256 | +0.252 | +12.22 |

## Open positions

None.

## The stop rules (`GOLD_V1.md`)

| Strategy | Demo trades | Mean net R | Reading |
| --- | --- | --- | --- |
| LVL4H | 2 | +0.807 | first check at 100 (98 to go) |
| PIVOT | 2 | +1.038 | first check at 100 (98 to go) |
| PIVW | 1 | +0.252 | first check at 100 (99 to go) |
| ASIA | 3 | +0.046 | first check at 100 (97 to go) |
| PWHL | 0 | - | first check at 100 (100 to go) |
| ROUND | 0 | - | first check at 100 (100 to go) |
| All | 8 | +0.510 | first check at 100 (92 to go) |

## Health (`GOLD_MONITOR.md`)

**Status: AMBER** (amber: A4 cost, last 8 (R)).

Red, process (A1): pause the EA until fixed. Red, edge (B, C, D): no move to real money on these rules; nothing is changed in reaction.

### A. Process

| Check | Value | Flag |
| --- | --- | --- |
| A1 match with Python | no export | - |
| A2 entry slippage, last 8 (R) | +0.036 | ok |
| A3 trades in the last full week | no full week yet | - |
| A4 cost, last 8 (R) | +0.039 | amber |

### B. Edge estimate (prior: half the reference mean, SD 0.10 R)

| Pool | Demo trades | Demo mean | Estimate (90%) | P(edge > 0) | Flag |
| --- | --- | --- | --- | --- | --- |
| LVL4H | 2 | +0.807 | +0.052 (-0.111 to +0.215) | 70% | ok |
| PIVOT | 2 | +1.038 | +0.002 (-0.162 to +0.165) | 51% | ok |
| PIVW | 1 | +0.252 | +0.014 (-0.149 to +0.178) | 56% | ok |
| ASIA | 3 | +0.046 | +0.021 (-0.142 to +0.184) | 58% | ok |
| PWHL | 0 | - | +0.053 (-0.112 to +0.217) | 70% | ok |
| ROUND | 0 | - | +0.066 (-0.099 to +0.231) | 75% | ok |
| ALL6 | 8 | +0.510 | +0.046 (-0.114 to +0.206) | 68% | ok |

### C. CUSUM (ALL6; good +0.042, broken −0.058)

S now 0.00, highest 0.07, red at h = 3.75 (false alarm on average every 2,030 trades; an edge 0.10 R worse found in about 579). Flag: ok.

### D. Drawdown against history (ALL6)

Current drawdown 0.0 R; worse than 0% of 10,000 historical paths of the same length (95th: 6.1 R, 99th: 7.4 R). Flag: ok.
