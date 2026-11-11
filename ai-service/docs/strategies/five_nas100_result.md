# The five demo strategies on the Nasdaq 100 (unseen instrument)

_`python -m app research five-nas build`, registered in `FIVE_NAS100.md` (2026-11-11). `#USNDAQ100_M1_201501040000_202611092359.csv`, trades 2016-02-01 to the export's end; commission 3.0 points a round trip, SL slip 0.5 point; frozen rules, nothing tuned here._

| Set | Trades | Net R (SE) | With slip | Years + | Cost R |
| --- | --- | --- | --- | --- | --- |
| The five together | 5,189 | -0.071 (0.017) | -0.078 | 27% | 0.085 |
| LVL4H | 883 | -0.137 (0.035) | -0.140 | 22% | 0.035 |
| PIVOT | 2,022 | -0.097 (0.030) | -0.111 | 27% | 0.165 |
| PIVW | 703 | -0.031 (0.041) | -0.034 | 44% | 0.035 |
| ASIA | 1,184 | -0.015 (0.032) | -0.019 | 33% | 0.035 |
| PWHL | 397 | -0.023 (0.051) | -0.026 | 33% | 0.034 |

Sum -404.3 R, largest drawdown 426.5 R, gross R +0.015, cost R 0.085.

E0 (the same entries, a random side, 50 runs): mean -0.049, 95th percentile -0.025.

**Decision (§3): the five does not generalise** (mean -0.078 against E0's 95th -0.025).

| Year | Trades | Net R | With slip |
| --- | --- | --- | --- |
| 2016 | 197 | -0.199 | -0.224 |
| 2017 | 211 | -0.432 | -0.466 |
| 2018 | 287 | -0.248 | -0.256 |
| 2019 | 159 | -0.158 | -0.174 |
| 2020 | 503 | -0.220 | -0.225 |
| 2021 | 422 | -0.098 | -0.103 |
| 2022 | 951 | +0.043 | +0.039 |
| 2023 | 283 | +0.061 | +0.050 |
| 2024 | 464 | +0.048 | +0.041 |
| 2025 | 794 | -0.039 | -0.044 |
| 2026 | 918 | -0.040 | -0.043 |
