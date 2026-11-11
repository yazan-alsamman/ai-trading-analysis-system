# RECLAIM at the five's levels on the Nasdaq 100

_`python -m app research five-nas reclaim`, registered in `FIVE_NAS_RECLAIM.md` (2026-11-11). `#USNDAQ100_M1_201501040000_202611092359.csv`, trades 2016-02-01 to the export's end; commission 3.0 points a round trip, SL slip 0.5 point; the rule frozen as on gold._

| Set | Trades | Net R (SE) | With slip | Years + | Cost R |
| --- | --- | --- | --- | --- | --- |
| RECLAIM, all | 929 | +0.035 (0.039) | +0.030 | 60% | 0.067 |
| 2016-2021 | 130 | +0.158 (0.108) | +0.154 | 80% | 0.075 |
| 2022 on | 799 | +0.015 (0.042) | +0.010 | 40% | 0.065 |
| LVL4H | 234 | -0.045 (0.078) | -0.050 | 50% | 0.066 |
| PIVOT | 176 | +0.217 (0.091) | +0.213 | 100% | 0.067 |
| PIVW | 176 | +0.217 (0.091) | +0.213 | 100% | 0.067 |
| ASIA | 250 | -0.082 (0.075) | -0.087 | 33% | 0.067 |
| PWHL | 93 | -0.142 (0.122) | -0.146 | 22% | 0.067 |

Sum +28.3 R, largest drawdown 49.8 R, gross R +0.102, exits {'sl': 0.52, 'tp': 0.4, 'time': 0.08}.

E0 (the same entries, a random side, 50 runs): mean -0.083, 95th -0.035.

| Condition | Met |
| --- | --- |
| 1. 2016-2021 > 0 | yes |
| 2. 2022 on > 0 | yes |
| 3. Above E0's 95th | yes |

**Decision (§2): RECLAIM holds on the Nasdaq.**

| Year | Trades | Net R | With slip |
| --- | --- | --- | --- |
| 2017 | 1 | +0.472 | +0.472 |
| 2018 | 10 | +0.585 | +0.584 |
| 2019 | 8 | -0.018 | -0.021 |
| 2020 | 61 | +0.145 | +0.141 |
| 2021 | 50 | +0.111 | +0.107 |
| 2022 | 119 | +0.183 | +0.179 |
| 2023 | 75 | -0.061 | -0.065 |
| 2024 | 141 | +0.103 | +0.099 |
| 2025 | 198 | -0.037 | -0.041 |
| 2026 | 266 | -0.048 | -0.053 |
