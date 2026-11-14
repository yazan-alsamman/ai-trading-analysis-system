# Gold v1 on FxPro's GOLD feed (Python)

_`python -m app research gold-live fxpro`: `GOLD_M1_201501020000_202611052359.csv`, the exam's code and settings (`GOLD_V1.md`), FxPro's recorded spread + $0.07 per oz. The research used another feed (XAUUSD); 2016 to 2026-01-09 was seen there, so this is a check of the feed, not a test._

_Bars from 2016.01.19 (server date; earlier GOLD history is daily or hourly bars, or has no spread), trades from 2016-02-01. 311 of 765,081 five-minute bars have no spread recorded._

| Set | Trades | Net R (SE) | Net with slip |
| --- | --- | --- | --- |
| All | 3,257 | +0.035 (0.023) | +0.017 |
| LVL4H | 1,141 | +0.091 (0.035) | +0.082 |
| PIVOT | 2,116 | +0.005 (0.030) | -0.018 |
| Exam period (2026-01-12 on) | 300 | +0.005 (0.062) | +0.001 |

| Year | Trades | Net R (SE) | Net with slip |
| --- | --- | --- | --- |
| 2016 | 196 | -0.027 (0.109) | -0.052 |
| 2017 | 199 | -0.087 (0.087) | -0.125 |
| 2018 | 200 | -0.030 (0.096) | -0.070 |
| 2019 | 227 | -0.110 (0.081) | -0.143 |
| 2020 | 319 | +0.165 (0.086) | +0.151 |
| 2021 | 319 | -0.058 (0.065) | -0.076 |
| 2022 | 336 | +0.051 (0.074) | +0.034 |
| 2023 | 343 | +0.178 (0.082) | +0.158 |
| 2024 | 429 | -0.012 (0.055) | -0.026 |
| 2025 | 378 | +0.159 (0.060) | +0.152 |
| 2026 | 311 | +0.004 (0.061) | +0.001 |
