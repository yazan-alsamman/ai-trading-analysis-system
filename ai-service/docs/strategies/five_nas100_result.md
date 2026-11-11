# The five demo strategies on the Nasdaq 100 (unseen instrument)

_`python -m app research five-nas build`, registered in `FIVE_NAS100.md` (2026-11-11). `#USNDAQ100_M1_201501040000_202611092359.csv`, trades 2016-02-01 to the export's end; commission 3.0 points a round trip, SL slip 0.5 point; frozen rules, nothing tuned here._

| Set | Trades | Net R (SE) | With slip | Years + | Cost R |
| --- | --- | --- | --- | --- | --- |
| The five together | 4,831 | -0.031 (0.018) | -0.040 | 36% | 0.105 |
| LVL4H | 694 | -0.006 (0.041) | -0.009 | 38% | 0.036 |
| PIVOT | 2,297 | -0.048 (0.030) | -0.064 | 36% | 0.182 |
| PIVW | 574 | -0.013 (0.044) | -0.016 | 50% | 0.035 |
| ASIA | 950 | -0.021 (0.037) | -0.025 | 25% | 0.036 |
| PWHL | 316 | -0.021 (0.057) | -0.025 | 38% | 0.035 |

Sum -193.4 R, largest drawdown 251.4 R, gross R +0.074, cost R 0.105.

E0 (the same entries, a random side, 50 runs): mean -0.079, 95th percentile -0.056.

**Decision (§3): the five does not generalise** (mean -0.040 against E0's 95th -0.056).

| Year | Trades | Net R | With slip |
| --- | --- | --- | --- |
| 2016 | 197 | -0.199 | -0.224 |
| 2017 | 223 | -0.385 | -0.421 |
| 2018 | 228 | -0.086 | -0.103 |
| 2019 | 200 | -0.139 | -0.165 |
| 2020 | 381 | -0.101 | -0.108 |
| 2021 | 339 | +0.034 | +0.026 |
| 2022 | 804 | +0.099 | +0.095 |
| 2023 | 283 | +0.061 | +0.050 |
| 2024 | 464 | +0.048 | +0.041 |
| 2025 | 794 | -0.039 | -0.044 |
| 2026 | 918 | -0.041 | -0.044 |
