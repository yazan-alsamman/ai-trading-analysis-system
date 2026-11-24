# Gold: breaks of round numbers, FxPro's GOLD feed (exploratory)

_`python -m app research gold-round fxpro`: `GOLD_M1_201501020000_202611052359.csv`, trades from 2016-02-01. Step chosen on XAUUSD 2012-2021: $25._

| Set | Trades | Net R (SE) | With slip | Years + | Cost R |
| --- | --- | --- | --- | --- | --- |
| ROUND, all | 1,164 | +0.031 (0.034) | +0.022 | 56% | 0.025 |
| ROUND, 2026-01-12 on | 144 | -0.008 (0.089) | -0.011 | 0% | 0.008 |

Daily net R correlation: LVL4H +0.43, PIVOT +0.30, PIVW +0.44, ASIA +0.40, PWHL +0.25.

**Conditions 3 and 4: not met** (net with slip +0.022).

| Portfolio (net R with slip) | Trades | Mean | Sum | Largest drawdown |
| --- | --- | --- | --- | --- |
| The five | 6,442 | +0.031 | +201.0 | 126.3 |
| The five and ROUND | 7,606 | +0.030 | +227.2 | 133.5 |

| Year | Trades | Net R | With slip |
| --- | --- | --- | --- |
| 2016 | 18 | -0.024 | -0.033 |
| 2019 | 27 | -0.154 | -0.164 |
| 2020 | 128 | +0.101 | +0.093 |
| 2021 | 118 | -0.070 | -0.081 |
| 2022 | 127 | +0.035 | +0.025 |
| 2023 | 116 | +0.212 | +0.201 |
| 2024 | 241 | +0.019 | +0.009 |
| 2025 | 241 | +0.009 | +0.003 |
| 2026 | 148 | -0.001 | -0.004 |
