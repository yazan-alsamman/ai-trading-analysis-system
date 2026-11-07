# Gold: the New York opening range breakout, FxPro's GOLD feed (exploratory)

_`python -m app research gold-orb fxpro`: `GOLD_M1_201501020000_202611052359.csv`, trades from 2016-02-01. Costs as `gold_orb_xauusd.md`._

| Set | Trades | Net R (SE) | With slip | Years + | Cost R |
| --- | --- | --- | --- | --- | --- |
| All | 1,812 | -0.048 (0.023) | -0.055 | 36% | 0.026 |
| 2026-01-12 on (used by no choice) | 226 | -0.182 (0.063) | -0.184 | 0% | 0.007 |

Daily net R correlation: LVL4H +0.20, PIVOT +0.16, PIVW +0.20, ASIA +0.14, PWHL +0.19.

| Portfolio (net R with slip) | Trades | Mean | Sum | Largest drawdown |
| --- | --- | --- | --- | --- |
| The five day strategies | 7,251 | +0.026 | +188.7 | 129.2 |
| With ORB | 9,063 | +0.010 | +88.9 | 177.0 |

| Year | Trades | Net R | With slip |
| --- | --- | --- | --- |
| 2016 | 48 | -0.054 | -0.062 |
| 2017 | 1 | -1.046 | -1.068 |
| 2018 | 3 | +0.220 | +0.209 |
| 2019 | 92 | +0.025 | +0.018 |
| 2020 | 209 | -0.141 | -0.146 |
| 2021 | 257 | -0.018 | -0.025 |
| 2022 | 241 | -0.028 | -0.035 |
| 2023 | 169 | +0.001 | -0.010 |
| 2024 | 288 | -0.036 | -0.045 |
| 2025 | 272 | +0.022 | +0.017 |
| 2026 | 232 | -0.180 | -0.182 |

Condition 3 (net with slip > 0): **not met** (-0.055). Condition 4 (|correlation| <= 0.2): **not met**.
