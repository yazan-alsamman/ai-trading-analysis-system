# Gold volatility forecast, part 1: result

_`python -m app research vol-forecast`, registered in `VOL_FORECAST.md` (with addendum 1). XAUUSD 5m, window 02:00-16:45 New York. 3,457 used days 2012-01-02 to 2026-01-09; test days 1,996 (2018-01-02 to 2026-01-09). QLIKE (lower is better); 4-week block bootstrap, 10,000 resamples, seed 20261113. No trade simulated._

## Decision

**Part 1 passes: M3, M4 beat the ATR.** M3 has the lowest mean QLIKE and goes to part 2 (a separate registration).

## Primary comparisons (model minus M1, per test day)

| Model | Mean QLIKE diff | 95% | p (one-sided) | Holm p | Years below M1 (of 8) | 2024-07 to 2026-01-09 diff | Beats the ATR |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M2 | -0.0015 | -0.0077 to +0.0058 | 0.3182 | 0.3182 | 5 | -0.0054 | no |
| M3 | -0.0235 | -0.0321 to -0.0140 | 0.0001 | 0.0003 | 7 | -0.0198 | yes |
| M4 | -0.0192 | -0.0292 to -0.0063 | 0.0030 | 0.0060 | 7 | -0.0196 | yes |

Blocks: 105. Lowest mean QLIKE over all test days: M3.

## Every model, all test days

| Model | Mean QLIKE | MSE log RV | R^2 log RV | R^2 vs M1 |
| --- | --- | --- | --- | --- |
| M0 | 0.1786 | 0.3398 | 0.305 | -0.452 |
| M1 | 0.1281 | 0.2340 | 0.522 | +0.000 |
| M2 | 0.1266 | 0.2273 | 0.535 | +0.029 |
| M3 | 0.1045 | 0.1873 | 0.617 | +0.199 |
| M4 | 0.1089 | 0.1973 | 0.597 | +0.157 |

## Per test year (mean QLIKE / R^2 of log RV)

| Year | Days | M0 | M1 | M2 | M3 | M4 |
| --- | --- | --- | --- | --- | --- | --- |
| 2018 | 249 | 0.182 / -0.64 | 0.134 / -0.14 | 0.113 / 0.04 | 0.089 / 0.24 | 0.083 / 0.23 |
| 2019 | 249 | 0.200 / 0.18 | 0.148 / 0.42 | 0.138 / 0.46 | 0.105 / 0.58 | 0.118 / 0.51 |
| 2020 | 250 | 0.194 / 0.49 | 0.142 / 0.62 | 0.169 / 0.59 | 0.179 / 0.59 | 0.199 / 0.56 |
| 2021 | 246 | 0.165 / -0.28 | 0.119 / 0.12 | 0.105 / 0.22 | 0.084 / 0.37 | 0.092 / 0.32 |
| 2022 | 250 | 0.189 / -0.15 | 0.134 / 0.20 | 0.134 / 0.20 | 0.103 / 0.37 | 0.106 / 0.36 |
| 2023 | 249 | 0.160 / -0.01 | 0.095 / 0.40 | 0.103 / 0.36 | 0.074 / 0.55 | 0.072 / 0.56 |
| 2024 | 250 | 0.167 / -0.11 | 0.125 / 0.23 | 0.124 / 0.24 | 0.085 / 0.45 | 0.080 / 0.48 |
| 2025+ | 253 | 0.171 / 0.28 | 0.127 / 0.51 | 0.126 / 0.51 | 0.117 / 0.54 | 0.120 / 0.51 |

2025+ holds 2026-01-02 to 2026-01-09 too.

## News days (TOP3 in the window) against the others

| Days | n | Median window move % (100 x sqrt RV) | QLIKE M0 | QLIKE M1 | QLIKE M2 | QLIKE M3 | QLIKE M4 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| other | 1,749 | 0.68 | 0.167 | 0.115 | 0.111 | 0.101 | 0.106 |
| TOP3 | 247 | 0.90 | 0.262 | 0.223 | 0.237 | 0.132 | 0.127 |

## Last window fits (train 2012-2024, 3,204 days)

- **M1:** const -1.492, atr +1.565
- **M2:** const -1.099, rv1 +0.104, rv5 +0.297, rv22 +0.330, on +0.144
- **M3:** const -1.205, rv1 +0.103, rv5 +0.258, rv22 +0.322, on +0.207, top3 +0.372, fed +0.273, uh1 +0.081, uh2 +0.157, early -0.014, tue +0.246, wed +0.239, thu +0.292, fri +0.310
- **M4 gain share:** atr 0.52, rv22 0.15, rv5 0.09, top3 0.08, on 0.06, uh2 0.03, rv1 0.02, tue 0.01, fri 0.01, early 0.01, wed 0.01, thu 0.01, fed 0.01, uh1 0.00

## Calibration (test days in deciles of the forecast; RV x 1e4)

**M1**

| Decile | Mean forecast | Mean realised |
| --- | --- | --- |
| 1 | 0.283 | 0.276 |
| 2 | 0.366 | 0.353 |
| 3 | 0.424 | 0.388 |
| 4 | 0.480 | 0.496 |
| 5 | 0.541 | 0.540 |
| 6 | 0.609 | 0.556 |
| 7 | 0.689 | 0.649 |
| 8 | 0.791 | 0.785 |
| 9 | 0.969 | 0.898 |
| 10 | 1.777 | 1.924 |

**M3**

| Decile | Mean forecast | Mean realised |
| --- | --- | --- |
| 1 | 0.237 | 0.232 |
| 2 | 0.326 | 0.306 |
| 3 | 0.393 | 0.384 |
| 4 | 0.457 | 0.463 |
| 5 | 0.521 | 0.545 |
| 6 | 0.589 | 0.560 |
| 7 | 0.673 | 0.691 |
| 8 | 0.791 | 0.771 |
| 9 | 0.990 | 0.978 |
| 10 | 1.777 | 1.936 |

## Product readout: the window's range by forecast decile (M3)

| Decile | Days | Range $ median (p20 to p80) | Range % median (p20 to p80) |
| --- | --- | --- | --- |
| 1 | 200 | 9.4 (7.2 to 14.2) | 0.67 (0.54 to 0.95) |
| 2 | 200 | 12.3 (8.2 to 18.6) | 0.78 (0.59 to 1.10) |
| 3 | 199 | 16.0 (11.1 to 22.9) | 0.90 (0.69 to 1.24) |
| 4 | 200 | 18.5 (12.0 to 27.5) | 0.97 (0.69 to 1.34) |
| 5 | 199 | 20.1 (14.0 to 30.5) | 1.01 (0.77 to 1.48) |
| 6 | 200 | 23.4 (16.0 to 31.0) | 1.12 (0.87 to 1.45) |
| 7 | 199 | 25.3 (17.2 to 38.2) | 1.19 (0.89 to 1.67) |
| 8 | 200 | 24.4 (16.7 to 36.2) | 1.21 (0.91 to 1.69) |
| 9 | 199 | 28.8 (20.1 to 45.7) | 1.35 (1.04 to 1.90) |
| 10 | 200 | 38.4 (23.9 to 69.7) | 1.70 (1.20 to 2.48) |

## Weekdays not used (§2), per year

| Year | Weekdays | No window bars | Failed the bar / gap rule | Used |
| --- | --- | --- | --- | --- |
| 2012 | 261 | 4 | 25 | 232 |
| 2013 | 261 | 3 | 26 | 232 |
| 2014 | 261 | 3 | 10 | 248 |
| 2015 | 261 | 4 | 9 | 248 |
| 2016 | 261 | 3 | 7 | 251 |
| 2017 | 260 | 3 | 7 | 250 |
| 2018 | 261 | 3 | 9 | 249 |
| 2019 | 261 | 3 | 9 | 249 |
| 2020 | 262 | 3 | 9 | 250 |
| 2021 | 261 | 3 | 12 | 246 |
| 2022 | 260 | 2 | 8 | 250 |
| 2023 | 260 | 3 | 8 | 249 |
| 2024 | 262 | 3 | 9 | 250 |
| 2025 | 261 | 3 | 11 | 247 |
| 2026 | 7 | 1 | 0 | 6 |

Used days also need 22 earlier used days (from 2011-09) for `rv22`.

## Notes

- `usd_high` enters M3 and M4 as two dummies (1, 2 or more).
- M4's s^2 is its in-sample residual variance, as registered; a LightGBM fits its train days closer than OLS, so its level forecast may be biased low.
- The calendar's importance labels are MT5's current ones (a small look-ahead).
