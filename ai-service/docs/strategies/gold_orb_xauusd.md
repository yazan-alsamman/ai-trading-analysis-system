# Gold: the New York opening range breakout, XAUUSD feed (exploratory)

_`python -m app research gold-orb build`, registered in `GOLD_ORB.md` (2026-11-07). XAUUSD 5m bars 2012-01 to 2026-01-09; cost = the signal bar's recorded spread + $0.07 per oz; with slip adds $0.10 on stop exits. One fixed setting. Seen data: optimistic. The lockbox was not read._

| Set | Trades | Net R (SE) | With slip | Years + | Cost R |
| --- | --- | --- | --- | --- | --- |
| 2012-2021 | 726 | -0.020 (0.039) | -0.031 | 50% | 0.027 |
| 2022 to 2026-01-09 (check) | 1,112 | -0.015 (0.033) | -0.025 | 20% | 0.020 |
| Buys | 939 | -0.011 (0.036) | -0.021 | 62% | 0.022 |
| Sells | 899 | -0.023 (0.036) | -0.034 | 38% | 0.024 |

Daily net R correlation (decides nothing here): LVL4H +0.25, PIVOT +0.11, PIVW +0.23, ASIA +0.23, PWHL +0.22.

| Portfolio (net R with slip) | Trades | Mean | Sum | Largest drawdown |
| --- | --- | --- | --- | --- |
| The five day strategies | 8,189 | +0.050 | +405.8 | 67.2 |
| With ORB | 10,027 | +0.035 | +355.5 | 82.0 |

| Year | Trades | Net R | With slip |
| --- | --- | --- | --- |
| 2012 | 9 | -0.210 | -0.220 |
| 2013 | 46 | -0.187 | -0.193 |
| 2014 | 5 | +0.458 | +0.438 |
| 2016 | 36 | +0.287 | +0.280 |
| 2018 | 20 | +0.085 | +0.066 |
| 2019 | 69 | -0.120 | -0.132 |
| 2020 | 258 | -0.122 | -0.132 |
| 2021 | 283 | +0.076 | +0.064 |
| 2022 | 277 | -0.017 | -0.029 |
| 2023 | 279 | -0.011 | -0.025 |
| 2024 | 275 | -0.041 | -0.050 |
| 2025 | 275 | +0.009 | +0.004 |
| 2026 | 6 | -0.089 | -0.092 |
