# Gold v1 on FxPro's GOLD feed (Python)

_`python -m app research gold-live fxpro`: `GOLD_M1_201501020000_202611052359.csv`, the exam's code and settings (`GOLD_V1.md`), FxPro's recorded spread + $0.07 per oz. The research used another feed (XAUUSD); 2016 to 2026-01-09 was seen there, so this is a check of the feed, not a test._

_Bars from 2016.01.19 (server date; earlier GOLD history is daily or hourly bars, or has no spread), trades from 2016-02-01. 1,526 of 766,296 five-minute bars have no spread recorded._

| Set | Trades | Net R (SE) | Net with slip |
| --- | --- | --- | --- |
| All | 3,493 | +0.036 (0.020) | +0.021 |
| LVL4H | 1,379 | +0.081 (0.030) | +0.073 |
| PIVOT | 2,114 | +0.006 (0.028) | -0.013 |
| Exam period (2026-01-12 on) | 300 | +0.005 (0.062) | +0.001 |

| Year | Trades | Net R (SE) | Net with slip |
| --- | --- | --- | --- |
| 2016 | 196 | -0.028 (0.109) | -0.053 |
| 2017 | 199 | -0.081 (0.084) | -0.116 |
| 2018 | 200 | -0.106 (0.077) | -0.136 |
| 2019 | 265 | -0.018 (0.068) | -0.038 |
| 2020 | 358 | +0.099 (0.063) | +0.090 |
| 2021 | 409 | -0.023 (0.053) | -0.035 |
| 2022 | 406 | +0.065 (0.060) | +0.053 |
| 2023 | 342 | +0.187 (0.082) | +0.168 |
| 2024 | 429 | -0.013 (0.056) | -0.026 |
| 2025 | 378 | +0.159 (0.060) | +0.152 |
| 2026 | 311 | +0.004 (0.061) | +0.001 |
