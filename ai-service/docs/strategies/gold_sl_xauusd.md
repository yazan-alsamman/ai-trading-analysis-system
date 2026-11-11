# Gold: a tighter SL with a larger lot for the five level breaks

_`python -m app research gold-sl build`, registered in `GOLD_SL.md` (2026-11-10). The five strategies' own entries; only the SL distance changes, M8 on it; R = the new distance. Cost = the entry bar's spread + $0.07 per oz; slip $0.10 on SL exits._

## 1. The five together

**XAUUSD 2012-2021**

| Setting | Trades | Gross R | Cost R | Net R with slip | Sum R | Largest drawdown R | SL exits |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BASE | 4,041 | +0.137 | 0.081 | +0.034 | +139.0 | 66.6 | 84% |
| H50 | 4,159 | +0.216 | 0.160 | +0.008 | +34.2 | 231.4 | 97% |
| H67 | 4,131 | +0.162 | 0.121 | +0.006 | +25.7 | 179.1 | 95% |
| USD10 | 3,884 | +0.048 | 0.029 | +0.015 | +58.1 | 63.5 | 45% |
| USD15 | 3,772 | +0.030 | 0.019 | +0.009 | +34.1 | 45.8 | 27% |

**XAUUSD 2022 to 2026-01-09**

| Setting | Trades | Gross R | Cost R | Net R with slip | Sum R | Largest drawdown R | SL exits |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BASE | 4,148 | +0.099 | 0.024 | +0.062 | +258.6 | 63.7 | 86% |
| H50 | 4,329 | +0.170 | 0.047 | +0.094 | +408.4 | 88.7 | 98% |
| H67 | 4,298 | +0.140 | 0.036 | +0.084 | +359.6 | 77.1 | 95% |
| USD10 | 4,022 | +0.096 | 0.018 | +0.071 | +285.1 | 45.5 | 71% |
| USD15 | 3,882 | +0.061 | 0.012 | +0.046 | +178.2 | 33.3 | 50% |

Chosen on 2012-2021: **USD10**.

By strategy, the check (net R with slip):

| Strategy | BASE | H50 | H67 | USD10 | USD15 |
| --- | --- | --- | --- | --- | --- |
| LVL4H | +0.101 | +0.142 | +0.129 | +0.099 | +0.057 |
| PIVOT | +0.065 | +0.089 | +0.083 | +0.053 | +0.025 |
| PIVW | +0.039 | +0.080 | +0.059 | +0.042 | +0.043 |
| ASIA | +0.039 | +0.046 | +0.040 | +0.080 | +0.066 |
| PWHL | +0.096 | +0.199 | +0.188 | +0.076 | +0.012 |

## 2. FxPro's GOLD feed

**FxPro GOLD 2016-02 to the end (`GOLD_M1_201501020000_202611052359.csv`)**

| Setting | Trades | Gross R | Cost R | Net R with slip | Sum R | Largest drawdown R | SL exits |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BASE | 7,251 | +0.079 | 0.042 | +0.026 | +185.2 | 134.4 | 79% |
| H50 | 7,616 | +0.143 | 0.083 | +0.032 | +245.0 | 223.7 | 96% |
| H67 | 7,530 | +0.104 | 0.063 | +0.022 | +165.1 | 207.6 | 93% |
| USD10 | 7,213 | +0.067 | 0.027 | +0.033 | +238.4 | 78.5 | 66% |
| USD15 | 6,989 | +0.037 | 0.018 | +0.016 | +108.5 | 68.7 | 49% |

**FxPro GOLD 2026**

| Setting | Trades | Gross R | Cost R | Net R with slip | Sum R | Largest drawdown R | SL exits |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BASE | 756 | +0.065 | 0.008 | +0.054 | +40.7 | 40.3 | 76% |
| H50 | 781 | +0.011 | 0.016 | -0.012 | -9.7 | 48.2 | 97% |
| H67 | 776 | -0.013 | 0.012 | -0.031 | -24.0 | 58.4 | 93% |
| USD10 | 784 | +0.022 | 0.022 | -0.009 | -7.1 | 57.8 | 98% |
| USD15 | 781 | -0.033 | 0.014 | -0.054 | -41.9 | 48.0 | 96% |

**Could a $10,000 account take a 0.25% trade (0.01 lots at least)?** FxPro 2026:

| Setting | Median D' ($) | Trades with lots >= 0.01 |
| --- | --- | --- |
| BASE | 27.82 | 29% |
| H50 | 13.91 | 89% |
| H67 | 18.55 | 80% |
| USD10 | 10.00 | 100% |
| USD15 | 15.00 | 100% |

**Decision (§2): USD10 is not adopted** (beats BASE on 2012-2021 / check / FxPro: no / yes / yes).
