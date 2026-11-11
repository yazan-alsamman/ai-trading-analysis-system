# Gold: breaks of round numbers, XAUUSD feed (exploratory)

_`python -m app research gold-round build`, registered in `GOLD_ROUND.md` (2026-11-10). XAUUSD 5m bars 2012-01 to 2026-01-09; LVL4H's frozen engine; cost = the signal bar's spread + $0.07 per oz; with slip adds $0.10 on stop exits. Tune 2012-2021, check 2022 to 2026-01-09. Seen data: optimistic. The lockbox was not read._

## 1. The four steps (by net R on 2012-2021)

| Step | Trades a day | Tune trades | Tune net | Tune years + | Tune cost R | Check trades | Check net (SE) | Check with slip | Eligible |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| $100 | 0.12 | 166 | +0.281 | 86% | 0.025 | 270 | +0.119 (0.073) | +0.111 |  |
| $50 | 0.22 | 286 | +0.144 | 75% | 0.024 | 525 | +0.176 (0.051) | +0.167 |  |
| $25 | 0.39 | 530 | +0.040 | 62% | 0.025 | 870 | +0.053 (0.040) | +0.043 | yes |
| $10 | 0.48 | 714 | -0.035 | 38% | 0.027 | 1,033 | +0.037 (0.038) | +0.026 |  |

Chosen: $25.

| Set | Trades | Net R (SE) | With slip | Years + | Cost R |
| --- | --- | --- | --- | --- | --- |
| 2012-2021 | 530 | +0.040 (0.053) | +0.029 | 62% | 0.025 |
| Check | 870 | +0.053 (0.040) | +0.043 | 100% | 0.020 |
| Buys | 696 | +0.099 (0.043) | +0.089 | 67% | 0.022 |
| Sells | 704 | -0.002 (0.047) | -0.012 | 46% | 0.022 |

Daily net R correlation with the five, 2012 to 2026-01-09 (decides nothing here): LVL4H +0.47, PIVOT +0.24, PIVW +0.48, ASIA +0.40, PWHL +0.26.

| Year | Trades | Net R | With slip |
| --- | --- | --- | --- |
| 2012 | 16 | +0.221 | +0.210 |
| 2013 | 30 | -0.123 | -0.133 |
| 2014 | 4 | +0.157 | +0.143 |
| 2016 | 18 | +0.217 | +0.206 |
| 2018 | 8 | -0.361 | -0.374 |
| 2019 | 51 | +0.055 | +0.044 |
| 2020 | 201 | +0.090 | +0.080 |
| 2021 | 202 | -0.005 | -0.018 |
| 2022 | 208 | +0.097 | +0.085 |
| 2023 | 191 | +0.095 | +0.081 |
| 2024 | 226 | +0.023 | +0.013 |
| 2025 | 241 | +0.008 | +0.002 |
| 2026 | 4 | +0.258 | +0.256 |
