# RECLAIM at the five's levels on the Nasdaq 100

_`python -m app research five-nas reclaim`, registered in `FIVE_NAS_RECLAIM.md` (2026-11-11). `#USNDAQ100_M1_201501040000_202611092359.csv`, trades 2016-02-01 to the export's end; commission 3.0 points a round trip, SL slip 0.5 point; the rule frozen as on gold._

| Set | Trades | Net R (SE) | With slip | Years + | Cost R |
| --- | --- | --- | --- | --- | --- |
| RECLAIM, all | 759 | -0.046 (0.043) | -0.050 | 40% | 0.067 |
| 2016-2021 | 115 | -0.153 (0.106) | -0.157 | 40% | 0.076 |
| 2022 on | 644 | -0.026 (0.047) | -0.031 | 40% | 0.065 |
| LVL4H | 243 | -0.121 (0.075) | -0.126 | 50% | 0.066 |
| PIVOT | 177 | +0.142 (0.090) | +0.138 | 67% | 0.068 |
| PIVW | 0 | - | - | - | - |
| ASIA | 250 | -0.082 (0.075) | -0.087 | 33% | 0.067 |
| PWHL | 89 | -0.109 (0.123) | -0.114 | 22% | 0.066 |

Sum -37.9 R, largest drawdown 52.4 R, gross R +0.021, exits {'sl': 0.55, 'tp': 0.36, 'time': 0.09}.

E0 (the same entries, a random side, 50 runs): mean -0.104, 95th -0.050.

| Condition | Met |
| --- | --- |
| 1. 2016-2021 > 0 | no |
| 2. 2022 on > 0 | no |
| 3. Above E0's 95th | no |

**Decision (§2): RECLAIM does not hold on the Nasdaq.**

| Year | Trades | Net R | With slip |
| --- | --- | --- | --- |
| 2017 | 1 | +0.472 | +0.472 |
| 2018 | 8 | +0.672 | +0.669 |
| 2019 | 7 | -0.159 | -0.161 |
| 2020 | 44 | -0.139 | -0.143 |
| 2021 | 55 | -0.294 | -0.300 |
| 2022 | 100 | +0.122 | +0.118 |
| 2023 | 53 | -0.154 | -0.159 |
| 2024 | 114 | +0.074 | +0.069 |
| 2025 | 162 | -0.075 | -0.080 |
| 2026 | 215 | -0.080 | -0.085 |
