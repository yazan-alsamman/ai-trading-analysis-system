# Gold: breaks of round numbers, FxPro's GOLD feed (exploratory)

_`python -m app research gold-round fxpro`: `GOLD_M1_201501020000_202611052359.csv`, trades from 2016-02-01. Step chosen on XAUUSD 2012-2021: $25._

| Set | Trades | Net R (SE) | With slip | Years + | Cost R |
| --- | --- | --- | --- | --- | --- |
| ROUND, all | 1,365 | +0.046 (0.030) | +0.039 | 80% | 0.025 |
| ROUND, 2026-01-12 on | 144 | -0.006 (0.089) | -0.009 | 0% | 0.008 |

Daily net R correlation: LVL4H +0.41, PIVOT +0.30, PIVW +0.42, ASIA +0.36, PWHL +0.31.

**Conditions 3 and 4: not met** (net with slip +0.039).

| Portfolio (net R with slip) | Trades | Mean | Sum | Largest drawdown |
| --- | --- | --- | --- | --- |
| The five | 7,251 | +0.026 | +188.7 | 129.2 |
| The five and ROUND | 8,616 | +0.028 | +241.8 | 113.0 |

| Year | Trades | Net R | With slip |
| --- | --- | --- | --- |
| 2016 | 18 | -0.024 | -0.033 |
| 2018 | 1 | +0.820 | +0.802 |
| 2019 | 59 | -0.057 | -0.065 |
| 2020 | 165 | +0.075 | +0.069 |
| 2021 | 190 | +0.023 | +0.016 |
| 2022 | 186 | +0.096 | +0.088 |
| 2023 | 116 | +0.212 | +0.201 |
| 2024 | 241 | +0.019 | +0.009 |
| 2025 | 241 | +0.009 | +0.003 |
| 2026 | 148 | +0.001 | -0.002 |
