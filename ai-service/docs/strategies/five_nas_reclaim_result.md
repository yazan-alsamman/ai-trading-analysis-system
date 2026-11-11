# RECLAIM at the five's levels on the Nasdaq 100

_`python -m app research five-nas reclaim`, registered in `FIVE_NAS_RECLAIM.md` (2026-11-11). `#USNDAQ100_M1_201501040000_202611092359.csv`, trades 2016-02-01 to the export's end; commission 3.0 points a round trip, SL slip 0.5 point; the rule frozen as on gold._

| Set | Trades | Net R (SE) | With slip | Years + | Cost R |
| --- | --- | --- | --- | --- | --- |
| RECLAIM, all | 753 | -0.008 (0.044) | -0.012 | 60% | 0.067 |
| 2016-2021 | 108 | +0.112 (0.118) | +0.108 | 80% | 0.076 |
| 2022 on | 645 | -0.028 (0.047) | -0.033 | 40% | 0.065 |
| LVL4H | 234 | -0.045 (0.078) | -0.050 | 50% | 0.066 |
| PIVOT | 176 | +0.217 (0.091) | +0.213 | 100% | 0.067 |
| PIVW | 0 | - | - | - | - |
| ASIA | 250 | -0.082 (0.075) | -0.087 | 33% | 0.067 |
| PWHL | 93 | -0.142 (0.122) | -0.146 | 22% | 0.067 |

Sum -9.3 R, largest drawdown 45.2 R, gross R +0.059, exits {'sl': 0.54, 'tp': 0.39, 'time': 0.08}.

E0 (the same entries, a random side, 50 runs): mean -0.088, 95th -0.020.

| Condition | Met |
| --- | --- |
| 1. 2016-2021 > 0 | yes |
| 2. 2022 on > 0 | no |
| 3. Above E0's 95th | yes |

**Decision (§2): RECLAIM does not hold on the Nasdaq.**

| Year | Trades | Net R | With slip |
| --- | --- | --- | --- |
| 2017 | 1 | +0.472 | +0.472 |
| 2018 | 10 | +0.585 | +0.584 |
| 2019 | 7 | -0.221 | -0.224 |
| 2020 | 49 | +0.087 | +0.083 |
| 2021 | 41 | +0.074 | +0.070 |
| 2022 | 101 | +0.110 | +0.106 |
| 2023 | 53 | -0.154 | -0.159 |
| 2024 | 114 | +0.074 | +0.069 |
| 2025 | 162 | -0.075 | -0.080 |
| 2026 | 215 | -0.080 | -0.085 |
