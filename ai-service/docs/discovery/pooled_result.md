# A model over all the tested strategies' trades: result

_`python -m app discovery pooled run`, registered in `POOLED_MODEL.md`. XAUUSD 5m; 59 cells; walk-forward yearly, purge + 1-day embargo. Intervals by 4-week blocks of days (10,000 resamples)._

## Validation (2020-2021)

| Model | tau | Trades | A day | Mean net R |
| --- | --- | --- | --- | --- |
| ridge | 0.00 | 8,800 | 17.02 | +0.0094 |
| ridge | 0.02 | 5,506 | 10.65 | +0.0035 |
| ridge | 0.05 | 2,369 | 4.58 | +0.0044 |
| ridge | 0.10 | 569 | 1.10 | +0.0171 |
| ridge | 0.15 | 88 | 0.17 | +0.0817 |
| lgbm | 0.00 | 9,600 | 18.57 | -0.0188 |
| lgbm | 0.02 | 6,098 | 11.79 | -0.0143 |
| lgbm | 0.05 | 2,977 | 5.76 | -0.0144 |
| lgbm | 0.10 | 948 | 1.83 | -0.0361 |
| lgbm | 0.15 | 313 | 0.61 | -0.0444 |

All candidates 2020-2021: 51,170, mean net R -0.1077.

Chosen: **ridge, tau 0.10**.

## Decision (test 2022-01-01 to 2026-01-09)

1. Edge: mean net R per selected trade -0.0313 (95% -0.1312 to +0.0722), p 0.7258, 53 blocks: **no**
2. Above the 95th percentile of 200 random selections (+0.0039; their median -0.0638): **no**
3. Useful: correlation with the five's days +0.454; daily Sharpe five 0.0627, five + selection 0.0458: **no**
4. FxPro 2026-01-12 to 2026-11-05: 329 selected of 29,773, mean net R +0.0134: **yes**

**It does not pass.** The search for an edge in gold's intraday trades ends here.

## Test detail

Selected 881 of 103,217 candidates on 1,038 days (0.85 a day); all candidates' mean net R -0.0955; largest drawdown of the selection 65.7 R.

| Year | Candidates | Selected | Mean net R selected | Mean net R all |
| --- | --- | --- | --- | --- |
| 2022 | 25,844 | 298 | -0.1436 | -0.1057 |
| 2023 | 24,083 | 231 | +0.1409 | -0.1063 |
| 2024 | 24,463 | 164 | -0.2842 | -0.1134 |
| 2025 | 28,060 | 186 | +0.1683 | -0.0615 |
| 2026 | 767 | 2 | -1.0147 | -0.0942 |

| Group | Selected | Mean net R |
| --- | --- | --- |
| lab | 469 | -0.0312 |
| levels | 66 | +0.0042 |
| six | 346 | -0.0381 |

## LightGBM gain by feature (fit on 2012-2024)

cost_r 0.48, cell_code 0.15, logF 0.04, atr4h_d 0.04, pool_recent5 0.04, vratio 0.04, atr1h_4h 0.03, u 0.03, minute 0.03, cell_recent 0.03, fired_today 0.02, opp_levels 0.01, same_lab 0.01, dir 0.01, weekday 0.01, same_levels 0.01, opp_lab 0.01, group_code 0.00, open_same 0.00, open_opp 0.00, same_six 0.00, opp_six 0.00

