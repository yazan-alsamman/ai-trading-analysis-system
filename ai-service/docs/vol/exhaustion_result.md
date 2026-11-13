# Range exhaustion: result

_`python -m app research exhaustion`, registered in `EXHAUSTION.md`. u = the day's range from 02:00 New York to the bar before the entry / (p02 x sqrt(F)), F = M3's out-of-sample forecast. 4-week block bootstrap, 10,000 resamples, seed 20261119._

Cut-off (2/3 quantile of u, the five's 2018-2021 trades, n = 2,573): **0.767**.

## Decision

1. d < 0 with p < 0.05 (2022 to 2026-01-09): **no** (d +0.0366 R, 95% -0.0703 to +0.1427, p 0.7524, 53 blocks)
2. top tercile's mean net R < 0: **no** (+0.0903)
3. d < 0 on FxPro 2026-01-12 to 2026-11-05: **no** (+0.0428)

**Hypothesis X does not pass.** The five stay as they are.

## By tercile

| Data | Group | Trades | Mean net R with slip | Gross R | Win share | Stop exits |
| --- | --- | --- | --- | --- | --- | --- |
| 2018-2021 | top (u > cut) | 858 | +0.0271 | +0.0848 | 43.1% | 76.3% |
| 2018-2021 | rest | 1,715 | +0.0257 | +0.0872 | 43.6% | 90.3% |
| 2022 to 2026-01-09 | top (u > cut) | 1,411 | +0.0903 | +0.1244 | 46.0% | 76.4% |
| 2022 to 2026-01-09 | rest | 2,654 | +0.0537 | +0.0911 | 46.4% | 92.5% |
| FxPro 2026 | top (u > cut) | 226 | +0.0917 | +0.1025 | 45.6% | 65.5% |
| FxPro 2026 | rest | 498 | +0.0490 | +0.0602 | 51.4% | 81.3% |
| ROUND, 2018 to 2026-01-09 | top (u > cut) | 335 | +0.2206 | +0.2494 | 51.9% | 70.1% |
| ROUND, 2018 to 2026-01-09 | rest | 429 | +0.1064 | +0.1381 | 50.3% | 92.1% |

## Per strategy (2018 to 2026-01-09): mean net R, top / rest

| Strategy | Trades top / rest | Top | Rest |
| --- | --- | --- | --- |
| LVL4H | 491 / 854 | +0.1238 | +0.1000 |
| PIVOT | 663 / 917 | +0.0227 | +0.0218 |
| PIVW | 514 / 687 | +0.0298 | +0.0475 |
| ASIA | 335 / 1,595 | +0.0731 | +0.0142 |
| PWHL | 266 / 316 | +0.1317 | +0.0820 |

## Within entry-time blocks (New York; 2018 to 2026-01-09)

| Block | Trades | Share top | Top | Rest |
| --- | --- | --- | --- | --- |
| 02-08 | 3,874 | 9% | +0.1415 | -0.0058 |
| 08-12 | 2,304 | 65% | +0.0489 | +0.1874 |
| 12-16 | 460 | 86% | +0.0639 | +0.8890 |

## u deciles (the five, 2018 to 2026-01-09)

| Decile | u range | Trades | Mean net R with slip |
| --- | --- | --- | --- |
| 1 | 0.000 to 0.100 | 664 | +0.0075 |
| 2 | 0.101 to 0.222 | 664 | +0.0357 |
| 3 | 0.222 to 0.328 | 664 | +0.1530 |
| 4 | 0.328 to 0.448 | 663 | +0.0025 |
| 5 | 0.448 to 0.567 | 664 | -0.0061 |
| 6 | 0.567 to 0.694 | 664 | +0.0088 |
| 7 | 0.694 to 0.834 | 663 | +0.1046 |
| 8 | 0.834 to 1.016 | 664 | -0.0111 |
| 9 | 1.016 to 1.284 | 664 | +0.0573 |
| 10 | 1.285 to 6.509 | 664 | +0.1558 |
