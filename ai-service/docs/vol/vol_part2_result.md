# Gold volatility forecast, part 2: result

_`python -m app research vol-part2`, registered in `VOL_PART2.md`. VOL = the five's D x ratio(d), ratio = exp((f_M3 - f_M1) / 2) clipped to (0.67, 1.5); BASE = the five as they trade. Per New York day: the sum of the five's net R with slip. 4-week block bootstrap, 10,000 resamples, seed 20261114._

## Decision

1. mean x > 0 with p < 0.05: **no** (-0.0032 R a day, 95% -0.0452 to +0.0393, p 0.5532, 105 blocks)
2. mean x > 0 in both segments: **no** (2018-2021 -0.0160, 2022 to 2026-01-09 +0.0080)
3. mean net R a trade VOL >= BASE: **no** (+0.0473 vs +0.0482)

**VOL does not pass.** The five keep the ATR; the forecast serves the product's "expected range today" only. (FxPro 2026, reported: mean x -0.0187 R a day.)

## Both sides

| Data | Days | Trades BASE / VOL | Net R a trade BASE / VOL | Total R BASE / VOL | Mean x (R a day) |
| --- | --- | --- | --- | --- | --- |
| Store 2018 to 2026-01-09 | 1,938 | 6,787 / 6,777 | +0.0482 / +0.0473 | +326.9 / +320.6 | -0.0032 |
| 2018-2021 | 908 | 2,639 / 2,615 | +0.0254 / +0.0201 | +67.1 / +52.6 | -0.0160 |
| 2022 to 2026-01-09 | 1,030 | 4,148 / 4,162 | +0.0626 / +0.0644 | +259.8 / +268.0 | +0.0080 |
| FxPro 2026-01-12 to 2026-11-05 | 208 | 731 / 731 | +0.0558 / +0.0505 | +40.8 / +36.9 | -0.0187 |

## Per strategy (store 2018 to 2026-01-09; ROUND not in the test)

| Strategy | Trades BASE / VOL | Net R a trade BASE / VOL | Total R BASE / VOL |
| --- | --- | --- | --- |
| LVL4H | 1,372 / 1,369 | +0.1098 / +0.0982 | +150.6 / +134.4 |
| PIVOT | 1,615 / 1,615 | +0.0205 / +0.0197 | +33.2 / +31.7 |
| PIVW | 1,223 / 1,231 | +0.0410 / +0.0515 | +50.2 / +63.4 |
| ASIA | 1,990 / 1,973 | +0.0175 / +0.0250 | +34.9 / +49.3 |
| PWHL | 587 / 589 | +0.0988 / +0.0707 | +58.0 / +41.7 |
| ROUND | 784 / 782 | +0.1521 / +0.1433 | +119.2 / +112.0 |

## Per year (store)

| Year | Days | Total R BASE | Total R VOL | Mean x |
| --- | --- | --- | --- | --- |
| 2018 | 193 | -6.5 | -11.9 | -0.0281 |
| 2019 | 205 | -1.2 | -3.3 | -0.0103 |
| 2020 | 253 | +89.2 | +95.7 | +0.0258 |
| 2021 | 257 | -14.4 | -27.9 | -0.0527 |
| 2022 | 257 | +48.2 | +26.3 | -0.0855 |
| 2023 | 257 | +74.7 | +103.6 | +0.1125 |
| 2024 | 258 | +42.4 | +62.4 | +0.0773 |
| 2025 | 252 | +94.6 | +80.9 | -0.0544 |
| 2026 | 6 | -0.1 | -5.1 | -0.8204 |

## The ratio (store test days)

Deciles 10% ... 90%: 0.83, 0.88, 0.92, 0.95, 0.99, 1.02, 1.05, 1.10, 1.19; clipped low 0.3%, high 0.5%.

Mean ratio on TOP3 news days 1.24, other days 0.97.

## The five's BASE trades by the day's forecast (description only)

| M3 forecast (low to high) quintile | Trades | Mean net R with slip (SE) | Win share |
| --- | --- | --- | --- |
| 1 | 1,328 | +0.0129 (0.0356) | 42.3% |
| 2 | 1,327 | +0.1034 (0.0370) | 47.1% |
| 3 | 1,328 | +0.0219 (0.0328) | 44.8% |
| 4 | 1,327 | +0.0770 (0.0348) | 46.1% |
| 5 | 1,328 | +0.0388 (0.0340) | 45.4% |

| Ratio M3 / ATR (low to high) quintile | Trades | Mean net R with slip (SE) | Win share |
| --- | --- | --- | --- |
| 1 | 1,328 | +0.0865 (0.0339) | 48.9% |
| 2 | 1,327 | +0.0158 (0.0316) | 47.2% |
| 3 | 1,328 | -0.0370 (0.0319) | 42.5% |
| 4 | 1,327 | +0.1692 (0.0371) | 47.7% |
| 5 | 1,328 | +0.0195 (0.0389) | 39.4% |

Any filter these suggest needs its own registration.
