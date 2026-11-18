# The five demo strategies on the Nasdaq 100 (unseen instrument)

_`python -m app research five-nas build`, registered in `FIVE_NAS100.md` (2026-11-11). `#USNDAQ100_M1_201501040000_202611092359.csv`, trades 2016-02-01 to the export's end; commission 3.0 points a round trip, SL slip 0.5 point; frozen rules, nothing tuned here._

| Set | Trades | Net R (SE) | With slip | Years + | Cost R |
| --- | --- | --- | --- | --- | --- |
| The five together | 4,788 | -0.020 (0.018) | -0.030 | 36% | 0.108 |
| LVL4H | 678 | +0.024 (0.043) | +0.020 | 62% | 0.036 |
| PIVOT | 2,312 | -0.044 (0.030) | -0.060 | 55% | 0.184 |
| PIVW | 561 | +0.005 (0.045) | +0.001 | 50% | 0.036 |
| ASIA | 926 | -0.009 (0.038) | -0.013 | 25% | 0.036 |
| PWHL | 311 | -0.019 (0.059) | -0.022 | 50% | 0.036 |

Sum -142.7 R, largest drawdown 259.4 R, gross R +0.087, cost R 0.108.

E0 (the same entries, a random side, 50 runs): mean -0.076, 95th percentile -0.055.

**Decision (§3): the five does not generalise** (mean -0.030 against E0's 95th -0.055).

| Year | Trades | Net R | With slip |
| --- | --- | --- | --- |
| 2016 | 205 | -0.182 | -0.207 |
| 2017 | 230 | -0.402 | -0.438 |
| 2018 | 224 | -0.048 | -0.065 |
| 2019 | 198 | -0.169 | -0.196 |
| 2020 | 370 | -0.146 | -0.153 |
| 2021 | 323 | +0.074 | +0.065 |
| 2022 | 804 | +0.099 | +0.095 |
| 2023 | 280 | +0.072 | +0.061 |
| 2024 | 458 | +0.064 | +0.057 |
| 2025 | 783 | -0.020 | -0.024 |
| 2026 | 913 | -0.009 | -0.012 |
