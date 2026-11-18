# RECLAIM at the five's levels on the Nasdaq 100

_`python -m app research five-nas reclaim`, registered in `FIVE_NAS_RECLAIM.md` (2026-11-11). `#USNDAQ100_M1_201501040000_202611092359.csv`, trades 2016-02-01 to the export's end; commission 3.0 points a round trip, SL slip 0.5 point; the rule frozen as on gold._

| Set | Trades | Net R (SE) | With slip | Years + | Cost R |
| --- | --- | --- | --- | --- | --- |
| RECLAIM, all | 737 | -0.027 (0.044) | -0.032 | 50% | 0.067 |
| 2016-2021 | 101 | -0.234 (0.111) | -0.239 | 60% | 0.075 |
| 2022 on | 636 | +0.005 (0.047) | +0.001 | 40% | 0.065 |
| LVL4H | 237 | -0.120 (0.076) | -0.125 | 50% | 0.066 |
| PIVOT | 173 | +0.143 (0.091) | +0.139 | 67% | 0.068 |
| PIVW | 0 | - | - | - | - |
| ASIA | 240 | -0.036 (0.077) | -0.041 | 44% | 0.067 |
| PWHL | 87 | -0.090 (0.125) | -0.094 | 22% | 0.066 |

Sum -23.5 R, largest drawdown 46.6 R, gross R +0.039, exits {'sl': 0.54, 'tp': 0.37, 'time': 0.08}.

E0 (the same entries, a random side, 50 runs): mean -0.098, 95th -0.045.

| Condition | Met |
| --- | --- |
| 1. 2016-2021 > 0 | no |
| 2. 2022 on > 0 | yes |
| 3. Above E0's 95th | yes |

**Decision (§2): RECLAIM does not hold on the Nasdaq.**

| Year | Trades | Net R | With slip |
| --- | --- | --- | --- |
| 2017 | 1 | +0.472 | +0.472 |
| 2018 | 6 | +0.413 | +0.410 |
| 2019 | 6 | +0.150 | +0.148 |
| 2020 | 42 | -0.274 | -0.279 |
| 2021 | 46 | -0.347 | -0.352 |
| 2022 | 99 | +0.134 | +0.130 |
| 2023 | 53 | -0.154 | -0.159 |
| 2024 | 113 | +0.084 | +0.080 |
| 2025 | 161 | -0.031 | -0.035 |
| 2026 | 210 | -0.029 | -0.034 |
