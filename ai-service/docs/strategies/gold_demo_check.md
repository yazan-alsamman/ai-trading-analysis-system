# Gold demo: the account's own record

_`python -m app research gold-demo check` without `--export`: `ReportHistory-592239561.xlsx`. No GOLD export covers these days yet, so Python's trades are not compared._

## Orders by strategy (balance 10,078.67)

| Strategy | Orders placed | Lots | D ($, median) | Risk a trade (% of the balance) |
| --- | --- | --- | --- | --- |
| LVL4H | 190 | 0.01 | 28.11 | 0.28% |
| PIVOT | 91 | 0.02, 0.03 | 15.33 | 0.45% |
| PIVW | 0 | - | - | - |
| ASIA | 0 | - | - | - |
| PWHL | 0 | - | - | - |

## Closed trades

| Opened (server) | Strategy | Kind | Dir | Level | Fill | Slip $ | D | Lots | Exit | Exit price | Gross R | Net R | Money |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026.11.10 12:17:00 | PIVOT | S1 | -1 | 4080.22 | 4080.17 | +0.05 | 16.05 | 0.03 | ea | 4053.86 | +1.642 | +1.635 | +78.71 |

## Open positions

| Time | Strategy | Type | Volume | Price | S / L | Profit |
| --- | --- | --- | --- | --- | --- | --- |
| 2026.11.10 15:30:07 | LVL4H PDL | sell | 0.01 | 4047.56 | 4046.40 | 22.58 |

## The stop rules (`GOLD_V1.md`)

| Strategy | Demo trades | Mean net R | Reading |
| --- | --- | --- | --- |
| LVL4H | 0 | - | first check at 100 (100 to go) |
| PIVOT | 1 | +1.635 | first check at 100 (99 to go) |
| PIVW | 0 | - | first check at 100 (100 to go) |
| ASIA | 0 | - | first check at 100 (100 to go) |
| PWHL | 0 | - | first check at 100 (100 to go) |
| All | 1 | +1.635 | first check at 100 (99 to go) |
