# Gold: do the breaks' bad runs persist? (exploratory)

_`python -m app research gold-regime`, registered in `GOLD_REGIME.md` (2026-11-08). Net R with slip; portfolios in R, in exit order. Seen data on both feeds._

## FxPro GOLD, 2016-02 to 2026-11-05 (primary)

| Detector | Break trades in BAD | Breaks in BAD (t) | Breaks in GOOD | RECLAIM in BAD (n) |
| --- | --- | --- | --- | --- |
| PERF 20 | 2,677 (42%) | +0.013 (+0.60) | +0.044 | -0.120 (1,014) |
| PERF 30 | 2,520 (39%) | +0.009 (+0.39) | +0.045 | -0.059 (937) |
| PERF 50 | 2,174 (34%) | +0.004 (+0.15) | +0.045 | -0.083 (781) |
| FALSE | 1,505 (23%) | +0.018 (+0.54) | +0.035 | -0.094 (583) |

| Detector | Portfolio | Trades | Mean | Sum | Largest drawdown |
| --- | --- | --- | --- | --- | --- |
| PERF 20 | ALWAYS | 6,442 | +0.031 | +201.0 | 126.3 |
| PERF 20 | PAUSE | 3,765 | +0.044 | +165.0 | 98.5 |
| PERF 20 | SWITCH | 4,779 | +0.009 | +43.3 | 121.6 |
| PERF 30 | ALWAYS | 6,442 | +0.031 | +201.0 | 126.3 |
| PERF 30 | PAUSE | 3,922 | +0.045 | +177.7 | 80.6 |
| PERF 30 | SWITCH | 4,859 | +0.025 | +122.8 | 99.9 |
| PERF 50 | ALWAYS | 6,442 | +0.031 | +201.0 | 126.3 |
| PERF 50 | PAUSE | 4,268 | +0.045 | +193.0 | 83.8 |
| PERF 50 | SWITCH | 5,049 | +0.025 | +128.0 | 86.4 |
| FALSE | ALWAYS | 6,442 | +0.031 | +201.0 | 126.3 |
| FALSE | PAUSE | 4,937 | +0.035 | +174.4 | 119.5 |
| FALSE | SWITCH | 5,520 | +0.022 | +119.6 | 137.5 |

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
