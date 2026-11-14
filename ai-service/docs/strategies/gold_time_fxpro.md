# Gold: time-of-day strategies, FxPro's GOLD feed (exploratory)

_`python -m app research gold-time fxpro`: `GOLD_M1_201501020000_202611052359.csv`, trades from 2016-02-01. Settings chosen on XAUUSD 2012-2021._

| Set | Trades | Net R (SE) | With slip | Years + | Cost R |
| --- | --- | --- | --- | --- | --- |
| A (S1 / 15:30 / TIME) | 1,454 | -0.007 (0.008) | -0.007 | 44% | 0.027 |
| A, 2026-01-12 on | 207 | +0.034 (0.024) | +0.034 | 100% | 0.008 |
| B (CONT / 16:45 / TIME) | 1,358 | -0.006 (0.036) | -0.011 | 44% | 0.027 |
| B, 2026-01-12 on | 213 | +0.018 (0.080) | +0.017 | 100% | 0.008 |

**A**: net with slip -0.007; daily correlation LVL4H +0.07, PIVOT +0.03, PIVW +0.12, ASIA +0.08, PWHL +0.06; conditions 3 and 4: **not met**.

| Year | Trades | Net R | With slip |
| --- | --- | --- | --- |
| 2016 | 33 | -0.085 | -0.086 |
| 2019 | 44 | +0.011 | +0.011 |
| 2020 | 138 | +0.019 | +0.018 |
| 2021 | 188 | +0.007 | +0.007 |
| 2022 | 185 | -0.051 | -0.051 |
| 2023 | 162 | -0.036 | -0.036 |
| 2024 | 243 | -0.001 | -0.001 |
| 2025 | 248 | -0.013 | -0.013 |
| 2026 | 213 | +0.036 | +0.036 |

**B**: net with slip -0.011; daily correlation LVL4H +0.34, PIVOT +0.16, PIVW +0.32, ASIA +0.34, PWHL +0.28; conditions 3 and 4: **not met**.

| Year | Trades | Net R | With slip |
| --- | --- | --- | --- |
| 2016 | 28 | +0.229 | +0.226 |
| 2019 | 31 | -0.155 | -0.162 |
| 2020 | 138 | -0.103 | -0.108 |
| 2021 | 134 | -0.118 | -0.124 |
| 2022 | 155 | +0.029 | +0.023 |
| 2023 | 142 | +0.058 | +0.050 |
| 2024 | 253 | -0.047 | -0.053 |
| 2025 | 258 | +0.076 | +0.073 |
| 2026 | 219 | -0.003 | -0.005 |

| Portfolio (net R with slip) | Trades | Mean | Sum | Largest drawdown |
| --- | --- | --- | --- | --- |
| The five | 6,442 | +0.031 | +201.0 | 126.3 |
| The five and A | 7,896 | +0.024 | +191.3 | 125.5 |
| The five and B | 7,800 | +0.024 | +185.8 | 157.2 |
