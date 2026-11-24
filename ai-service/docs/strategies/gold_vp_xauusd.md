# Gold: the previous day's value area (VAH, VAL), XAUUSD feed (exploratory)

_`python -m app research gold-vp build`, registered in `GOLD_VP.md` (2026-11-08). XAUUSD 5m bars 2012-01 to 2026-01-09, tick volume; cost = the signal bar's recorded spread + $0.07 per oz; with slip adds $0.10 on stop exits. One fixed setting. Seen data._

| Set | Trades | Net R (SE) | With slip | Years + | Cost R |
| --- | --- | --- | --- | --- | --- |
| 2012-2021 | 592 | +0.021 (0.048) | +0.008 | 75% | 0.027 |
| 2022 to 2026-01-09 (check) | 906 | -0.005 (0.039) | -0.017 | 60% | 0.021 |

| Set | Trades | Net R (SE) | With slip | Years + | Cost R |
| --- | --- | --- | --- | --- | --- |
| Buys | 737 | +0.028 (0.044) | +0.016 | 62% | 0.023 |
| Sells | 761 | -0.017 (0.042) | -0.028 | 46% | 0.024 |

Daily net R correlation with the five together: **+0.424**.

| Account at demo risk | Total % | Largest drawdown % |
| --- | --- | --- |
| The five | +158.5 | 31.5 |
| The five + VPVA at 0.25% | +156.0 | 30.8 |

| Year | Trades | Net R | With slip |
| --- | --- | --- | --- |
| 2012 | 14 | +0.037 | +0.028 |
| 2013 | 34 | +0.069 | +0.058 |
| 2014 | 5 | -0.812 | -0.833 |
| 2016 | 18 | +0.188 | +0.177 |
| 2018 | 15 | +0.192 | +0.172 |
| 2019 | 51 | +0.189 | +0.178 |
| 2020 | 207 | +0.001 | -0.010 |
| 2021 | 248 | -0.011 | -0.024 |
| 2022 | 239 | +0.016 | +0.003 |
| 2023 | 241 | +0.015 | -0.000 |
| 2024 | 210 | -0.055 | -0.066 |
| 2025 | 210 | -0.006 | -0.012 |
| 2026 | 6 | +0.112 | +0.109 |
