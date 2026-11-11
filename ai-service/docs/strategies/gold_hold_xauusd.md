# Gold: let the five's winners run past 16:45

_`python -m app research gold-hold build`, registered in `GOLD_HOLD.md` (2026-11-10). The five's own entries and D, M8; only the end changes. Cost = the entry bar's spread + $0.07 per oz; slip $0.10 on SL exits; swap scenario 3% / 1% a year (buy / sell)._

**XAUUSD 2012-2021**

| Setting | Trades | Gross R | Cost R | Swap R | Net R with slip | Sum R | Largest drawdown R | Held overnight |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BASE | 4,041 | +0.129 | 0.081 | 0.000 | +0.026 | +106.8 | 75.7 | 0% |
| ALL1 | 3,957 | +0.145 | 0.083 | 0.002 | +0.034 | +136.5 | 78.4 | 10% |
| WIN1 | 4,038 | +0.129 | 0.082 | 0.000 | +0.025 | +100.8 | 73.9 | 1% |
| WIN3 | 4,038 | +0.129 | 0.082 | 0.000 | +0.025 | +100.8 | 73.9 | 1% |

**XAUUSD 2022 to 2026-01-09**

| Setting | Trades | Gross R | Cost R | Swap R | Net R with slip | Sum R | Largest drawdown R | Held overnight |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BASE | 4,147 | +0.098 | 0.024 | 0.000 | +0.062 | +256.1 | 66.0 | 0% |
| ALL1 | 4,048 | +0.094 | 0.024 | 0.003 | +0.053 | +216.1 | 76.2 | 11% |
| WIN1 | 4,145 | +0.098 | 0.024 | 0.000 | +0.061 | +253.6 | 66.6 | 1% |
| WIN3 | 4,145 | +0.098 | 0.024 | 0.000 | +0.061 | +253.6 | 66.6 | 1% |

**FxPro GOLD 2016-02 to the end (`GOLD_M1_201501020000_202611052359.csv`)**

| Setting | Trades | Gross R | Cost R | Swap R | Net R with slip | Sum R | Largest drawdown R | Held overnight |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BASE | 7,251 | +0.075 | 0.042 | 0.000 | +0.021 | +154.1 | 157.3 | 0% |
| ALL1 | 7,121 | +0.041 | 0.042 | 0.003 | -0.019 | -132.9 | 440.5 | 16% |
| WIN1 | 7,248 | +0.073 | 0.042 | 0.000 | +0.018 | +132.6 | 170.7 | 1% |
| WIN3 | 7,248 | +0.073 | 0.042 | 0.000 | +0.018 | +132.6 | 170.7 | 1% |

**FxPro GOLD 2026**

| Setting | Trades | Gross R | Cost R | Swap R | Net R with slip | Sum R | Largest drawdown R | Held overnight |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BASE | 756 | +0.063 | 0.008 | 0.000 | +0.052 | +39.6 | 40.9 | 0% |
| ALL1 | 738 | +0.068 | 0.008 | 0.002 | +0.054 | +39.9 | 50.3 | 21% |
| WIN1 | 756 | +0.058 | 0.008 | 0.000 | +0.047 | +35.2 | 41.5 | 2% |
| WIN3 | 756 | +0.058 | 0.008 | 0.000 | +0.047 | +35.2 | 41.5 | 2% |

Chosen on 2012-2021: **ALL1**.

The check by strategy (net R with slip and swap), BASE / chosen:

| Strategy | BASE | Chosen |
| --- | --- | --- |
| LVL4H | +0.108 | +0.105 |
| PIVOT | +0.059 | +0.042 |
| PIVW | +0.036 | +0.021 |
| ASIA | +0.038 | +0.035 |
| PWHL | +0.093 | +0.088 |

**Decision (§2): ALL1 is not adopted** (2012-2021 / check / FxPro: yes / no / no).
