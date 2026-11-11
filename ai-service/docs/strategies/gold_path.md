# Gold: how far price goes with the five strategies' trades (descriptive)

_`python -m app research gold-path build`. The five demo strategies' own trades (one at a time, M8, as the EA), measured from the entry level. D = each trade's SL distance. Moves are before costs. Decides nothing._

## XAUUSD 2012-2021 (4,041 trades, median D $5.23)

**After the entry: share of trades ahead and the mean move.**

| Minutes | Ahead | Mean move, D (SE) | Median move, $ |
| --- | --- | --- | --- |
| 5 | 48.8% | +0.041 (0.009) | -0.03 |
| 15 | 48.9% | +0.054 (0.012) | -0.05 |
| 30 | 49.0% | +0.059 (0.015) | -0.05 |
| 60 | 48.4% | +0.053 (0.019) | -0.10 |
| 120 | 48.8% | +0.060 (0.024) | -0.10 |
| 240 | 49.2% | +0.061 (0.030) | -0.12 |

**By strategy.**

| Strategy | Trades | Ahead at 30 min | Move at 30 min, D | Move at 120 min, D | MFE, D (median) | MAE, D (median) | Minutes to MFE (median) | Gross R | Kept of MFE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ASIA | 821 | 49.1% | +0.039 | +0.014 | 1.05 | 1.14 | 265 | +0.051 | 3% |
| LVL4H | 556 | 50.4% | +0.082 | +0.093 | 1.11 | 0.93 | 145 | +0.189 | 12% |
| PIVOT | 1,966 | 48.2% | +0.068 | +0.066 | 1.15 | 1.04 | 70 | +0.167 | 10% |
| PIVW | 466 | 49.4% | +0.024 | +0.059 | 1.10 | 0.98 | 135 | +0.108 | 7% |
| PWHL | 232 | 50.9% | +0.062 | +0.093 | 1.11 | 0.92 | 130 | +0.119 | 8% |
| All | 4,041 | 49.0% | +0.059 | +0.060 | 1.11 | 1.03 | 100 | +0.137 | 9% |

**How far before the SL.**

| Reaches before the SL (−1 D) | Share | Random walk 1 / (1 + x) |
| --- | --- | --- |
| +0.25 D | 78.1% | 80.0% |
| +0.5 D | 66.2% | 66.7% |
| +1 D | 46.5% | 50.0% |
| +1.5 D | 33.4% | 40.0% |
| +2 D | 24.1% | 33.3% |
| +3 D | 13.0% | 25.0% |

**How the current exits end the trades (M8).**

| Exit | Share | Mean gross R |
| --- | --- | --- |
| sl | 84.2% | +0.047 |
| time | 15.8% | +0.619 |

Winners 51.5%, mean +1.120 R; losers mean -0.907 R. The best 10% of trades make 240% of the total gross R (+553.6 R).

## XAUUSD 2022 to 2026-01-09 (4,148 trades, median D $7.35)

**After the entry: share of trades ahead and the mean move.**

| Minutes | Ahead | Mean move, D (SE) | Median move, $ |
| --- | --- | --- | --- |
| 5 | 48.6% | +0.034 (0.006) | -0.06 |
| 15 | 50.5% | +0.048 (0.009) | +0.04 |
| 30 | 49.9% | +0.044 (0.011) | -0.00 |
| 60 | 50.8% | +0.053 (0.015) | +0.12 |
| 120 | 51.2% | +0.062 (0.019) | +0.16 |
| 240 | 51.2% | +0.061 (0.023) | +0.29 |

**By strategy.**

| Strategy | Trades | Ahead at 30 min | Move at 30 min, D | Move at 120 min, D | MFE, D (median) | MAE, D (median) | Minutes to MFE (median) | Gross R | Kept of MFE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ASIA | 1,268 | 48.5% | +0.025 | +0.046 | 1.17 | 1.05 | 290 | +0.071 | 5% |
| LVL4H | 874 | 50.0% | +0.042 | +0.092 | 1.19 | 0.97 | 178 | +0.134 | 9% |
| PIVOT | 824 | 50.0% | +0.062 | +0.056 | 1.25 | 1.08 | 90 | +0.117 | 7% |
| PIVW | 800 | 49.5% | +0.034 | +0.047 | 1.14 | 1.02 | 160 | +0.071 | 5% |
| PWHL | 382 | 54.5% | +0.088 | +0.088 | 1.08 | 0.90 | 152 | +0.128 | 9% |
| All | 4,148 | 49.9% | +0.044 | +0.062 | 1.17 | 1.02 | 165 | +0.099 | 7% |

**How far before the SL.**

| Reaches before the SL (−1 D) | Share | Random walk 1 / (1 + x) |
| --- | --- | --- |
| +0.25 D | 79.5% | 80.0% |
| +0.5 D | 66.8% | 66.7% |
| +1 D | 47.9% | 50.0% |
| +1.5 D | 33.8% | 40.0% |
| +2 D | 23.3% | 33.3% |
| +3 D | 10.5% | 25.0% |

**How the current exits end the trades (M8).**

| Exit | Share | Mean gross R |
| --- | --- | --- |
| sl | 86.4% | +0.057 |
| time | 13.6% | +0.361 |

Winners 52.6%, mean +1.012 R; losers mean -0.915 R. The best 10% of trades make 271% of the total gross R (+409.5 R).

## FxPro GOLD 2016-02 to 2025 (`GOLD_M1_201501020000_202611052359.csv`) (6,496 trades, median D $8.07)

**After the entry: share of trades ahead and the mean move.**

| Minutes | Ahead | Mean move, D (SE) | Median move, $ |
| --- | --- | --- | --- |
| 5 | 49.2% | +0.025 (0.005) | -0.03 |
| 15 | 50.4% | +0.043 (0.007) | +0.02 |
| 30 | 50.0% | +0.040 (0.009) | +0.01 |
| 60 | 49.6% | +0.042 (0.011) | -0.04 |
| 120 | 50.0% | +0.045 (0.014) | +0.00 |
| 240 | 49.7% | +0.030 (0.017) | -0.06 |

**By strategy.**

| Strategy | Trades | Ahead at 30 min | Move at 30 min, D | Move at 120 min, D | MFE, D (median) | MAE, D (median) | Minutes to MFE (median) | Gross R | Kept of MFE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ASIA | 1,701 | 48.9% | +0.021 | +0.029 | 0.96 | 0.96 | 285 | +0.039 | 3% |
| LVL4H | 1,214 | 51.5% | +0.053 | +0.081 | 0.98 | 0.84 | 160 | +0.119 | 9% |
| PIVOT | 1,969 | 48.6% | +0.034 | +0.015 | 1.03 | 0.93 | 80 | +0.089 | 6% |
| PIVW | 1,070 | 50.8% | +0.040 | +0.057 | 0.94 | 0.86 | 160 | +0.049 | 4% |
| PWHL | 542 | 54.4% | +0.090 | +0.099 | 0.97 | 0.75 | 155 | +0.152 | 12% |
| All | 6,496 | 50.0% | +0.040 | +0.045 | 0.98 | 0.89 | 140 | +0.080 | 6% |

**How far before the SL.**

| Reaches before the SL (−1 D) | Share | Random walk 1 / (1 + x) |
| --- | --- | --- |
| +0.25 D | 78.9% | 80.0% |
| +0.5 D | 65.5% | 66.7% |
| +1 D | 44.2% | 50.0% |
| +1.5 D | 29.6% | 40.0% |
| +2 D | 19.4% | 33.3% |
| +3 D | 7.8% | 25.0% |

**How the current exits end the trades (M8).**

| Exit | Share | Mean gross R |
| --- | --- | --- |
| sl | 78.9% | +0.024 |
| time | 21.1% | +0.289 |

Winners 51.9%, mean +0.962 R; losers mean -0.872 R. The best 10% of trades make 306% of the total gross R (+520.7 R).

## FxPro GOLD 2026 (756 trades, median D $27.69)

**After the entry: share of trades ahead and the mean move.**

| Minutes | Ahead | Mean move, D (SE) | Median move, $ |
| --- | --- | --- | --- |
| 5 | 47.5% | +0.032 (0.015) | -0.37 |
| 15 | 47.9% | +0.028 (0.019) | -0.78 |
| 30 | 45.6% | +0.037 (0.022) | -1.18 |
| 60 | 48.1% | +0.051 (0.025) | -0.92 |
| 120 | 51.3% | +0.103 (0.036) | +0.31 |
| 240 | 52.8% | +0.094 (0.044) | +1.47 |

**By strategy.**

| Strategy | Trades | Ahead at 30 min | Move at 30 min, D | Move at 120 min, D | MFE, D (median) | MAE, D (median) | Minutes to MFE (median) | Gross R | Kept of MFE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ASIA | 239 | 49.8% | +0.046 | +0.058 | 1.02 | 0.77 | 305 | +0.134 | 10% |
| LVL4H | 166 | 41.0% | -0.062 | +0.051 | 0.90 | 0.89 | 168 | +0.006 | 0% |
| PIVOT | 145 | 44.8% | +0.121 | +0.210 | 1.13 | 0.96 | 100 | +0.021 | 1% |
| PIVW | 143 | 44.1% | +0.063 | +0.132 | 1.01 | 0.85 | 190 | +0.116 | 8% |
| PWHL | 63 | 47.6% | +0.017 | +0.103 | 0.92 | 0.86 | 190 | -0.058 | -5% |
| All | 756 | 45.6% | +0.037 | +0.103 | 0.99 | 0.86 | 172 | +0.065 | 5% |

**How far before the SL.**

| Reaches before the SL (−1 D) | Share | Random walk 1 / (1 + x) |
| --- | --- | --- |
| +0.25 D | 77.8% | 80.0% |
| +0.5 D | 65.9% | 66.7% |
| +1 D | 43.5% | 50.0% |
| +1.5 D | 30.2% | 40.0% |
| +2 D | 21.0% | 33.3% |
| +3 D | 7.7% | 25.0% |

**How the current exits end the trades (M8).**

| Exit | Share | Mean gross R |
| --- | --- | --- |
| sl | 75.9% | +0.034 |
| time | 24.1% | +0.161 |

Winners 55.3%, mean +0.812 R; losers mean -0.860 R. The best 10% of trades make 323% of the total gross R (+48.8 R).

