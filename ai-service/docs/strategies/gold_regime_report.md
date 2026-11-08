# Gold: do the breaks' bad runs persist? (exploratory)

_`python -m app research gold-regime`, registered in `GOLD_REGIME.md` (2026-11-08). Net R with slip; portfolios in R, in exit order. Seen data on both feeds._

## FxPro GOLD, 2016-02 to 2026-11-05 (primary)

| Detector | Break trades in BAD | Breaks in BAD (t) | Breaks in GOOD | RECLAIM in BAD (n) |
| --- | --- | --- | --- | --- |
| PERF 20 | 3,026 (42%) | +0.022 (+1.05) | +0.029 | -0.109 (1,033) |
| PERF 30 | 2,731 (38%) | +0.007 (+0.31) | +0.038 | -0.021 (940) |
| PERF 50 | 2,420 (33%) | +0.023 (+1.01) | +0.027 | -0.097 (777) |
| FALSE | 1,715 (24%) | +0.003 (+0.11) | +0.033 | -0.094 (583) |

| Detector | Portfolio | Trades | Mean | Sum | Largest drawdown |
| --- | --- | --- | --- | --- | --- |
| PERF 20 | ALWAYS | 7,251 | +0.026 | +188.7 | 129.2 |
| PERF 20 | PAUSE | 4,225 | +0.029 | +123.4 | 123.1 |
| PERF 20 | SWITCH | 5,258 | +0.002 | +10.6 | 154.2 |
| PERF 30 | ALWAYS | 7,251 | +0.026 | +188.7 | 129.2 |
| PERF 30 | PAUSE | 4,520 | +0.038 | +170.1 | 101.1 |
| PERF 30 | SWITCH | 5,460 | +0.028 | +150.4 | 97.2 |
| PERF 50 | ALWAYS | 7,251 | +0.026 | +188.7 | 129.2 |
| PERF 50 | PAUSE | 4,831 | +0.027 | +132.5 | 117.1 |
| PERF 50 | SWITCH | 5,608 | +0.010 | +57.0 | 150.9 |
| FALSE | ALWAYS | 7,251 | +0.026 | +188.7 | 129.2 |
| FALSE | PAUSE | 5,536 | +0.033 | +183.7 | 93.4 |
| FALSE | SWITCH | 6,119 | +0.021 | +128.9 | 119.7 |

## XAUUSD, 2012 to 2026-01-09 (second feed)

| Detector | Break trades in BAD | Breaks in BAD (t) | Breaks in GOOD | RECLAIM in BAD (n) |
| --- | --- | --- | --- | --- |
| PERF 20 | 3,344 (41%) | +0.071 (+2.99) | +0.035 | -0.088 (1,383) |
| PERF 30 | 3,087 (38%) | +0.050 (+2.04) | +0.050 | -0.034 (1,289) |
| PERF 50 | 2,661 (32%) | +0.041 (+1.52) | +0.054 | -0.047 (1,088) |
| FALSE | 1,744 (21%) | +0.019 (+0.61) | +0.058 | -0.073 (695) |

| Detector | Portfolio | Trades | Mean | Sum | Largest drawdown |
| --- | --- | --- | --- | --- | --- |
| PERF 20 | ALWAYS | 8,189 | +0.050 | +405.8 | 67.2 |
| PERF 20 | PAUSE | 4,845 | +0.035 | +168.9 | 92.8 |
| PERF 20 | SWITCH | 6,228 | +0.008 | +47.8 | 138.6 |
| PERF 30 | ALWAYS | 8,189 | +0.050 | +405.8 | 67.2 |
| PERF 30 | PAUSE | 5,102 | +0.050 | +252.9 | 94.8 |
| PERF 30 | SWITCH | 6,391 | +0.033 | +209.2 | 85.7 |
| PERF 50 | ALWAYS | 8,189 | +0.050 | +405.8 | 67.2 |
| PERF 50 | PAUSE | 5,528 | +0.054 | +297.6 | 81.1 |
| PERF 50 | SWITCH | 6,616 | +0.037 | +246.3 | 92.7 |
| FALSE | ALWAYS | 8,189 | +0.050 | +405.8 | 67.2 |
| FALSE | PAUSE | 6,445 | +0.058 | +372.5 | 63.1 |
| FALSE | SWITCH | 7,140 | +0.045 | +321.6 | 71.1 |

## Decision (section 4)

- PERF 20: **does not pass**.
- PERF 30: **does not pass**.
- PERF 50: **does not pass**.
- FALSE: **does not pass**.
