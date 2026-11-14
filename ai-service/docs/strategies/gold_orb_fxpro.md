# Gold: the New York opening range breakout, FxPro's GOLD feed (exploratory)

_`python -m app research gold-orb fxpro`: `GOLD_M1_201501020000_202611052359.csv`, trades from 2016-02-01. Costs as `gold_orb_xauusd.md`._

| Set | Trades | Net R (SE) | With slip | Years + | Cost R |
| --- | --- | --- | --- | --- | --- |
| All | 1,584 | -0.058 (0.026) | -0.066 | 30% | 0.026 |
| 2026-01-12 on (used by no choice) | 226 | -0.182 (0.063) | -0.184 | 0% | 0.007 |

Daily net R correlation: LVL4H +0.19, PIVOT +0.15, PIVW +0.19, ASIA +0.17, PWHL +0.17.

| Portfolio (net R with slip) | Trades | Mean | Sum | Largest drawdown |
| --- | --- | --- | --- | --- |
| The five day strategies | 6,442 | +0.031 | +201.0 | 126.3 |
| With ORB | 8,026 | +0.012 | +96.3 | 170.9 |

| Year | Trades | Net R | With slip |
| --- | --- | --- | --- |
| 2016 | 48 | -0.054 | -0.062 |
| 2017 | 1 | -1.046 | -1.068 |
| 2019 | 45 | -0.083 | -0.094 |
| 2020 | 165 | -0.154 | -0.162 |
| 2021 | 184 | +0.011 | +0.000 |
| 2022 | 180 | -0.086 | -0.096 |
| 2023 | 169 | +0.001 | -0.010 |
| 2024 | 288 | -0.036 | -0.045 |
| 2025 | 272 | +0.022 | +0.017 |
| 2026 | 232 | -0.180 | -0.182 |

Condition 3 (net with slip > 0): **not met** (-0.066). Condition 4 (|correlation| <= 0.2): **met**.
