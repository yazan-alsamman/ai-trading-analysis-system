# Managing the five's trades by their path (stage 2), XAUUSD and FxPro

_`python -m app research mgmt-fast`, registered in `MGMT_FAST.md` (2026-11-12) before the run. Net R with slip; t of the difference from BASE (4-week block bootstrap)._

## XAUUSD

| Cell | Period | Trades | Fast | Mean net R | Minus BASE | t | Years better | Sum R | Largest drawdown R |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BASE | 2012-2021 | 4,041 | 11% | +0.036 | +0.000 | +nan | nan% | +146.0 | 66.6 |
| F1 | 2012-2021 | 4,041 | 11% | +0.040 | +0.004 | +0.64 | 50% | +160.3 | 66.7 |
| F2 | 2012-2021 | 4,041 | 11% | +0.041 | +0.005 | +0.97 | 80% | +166.7 | 66.5 |
| F3 | 2012-2021 | 4,040 | 11% | +0.043 | +0.006 | +0.90 | 50% | +172.0 | 65.6 |
| A1 | 2012-2021 | 4,034 | 11% | +0.052 | +0.016 | +1.58 | 80% | +210.8 | 73.2 |
| BASE | 2022 to 2026-01-09 | 4,148 | 7% | +0.063 | +0.000 | +nan | nan% | +259.8 | 63.1 |
| F1 | 2022 to 2026-01-09 | 4,148 | 7% | +0.060 | -0.002 | -0.40 | 20% | +250.5 | 67.6 |
| F2 | 2022 to 2026-01-09 | 4,147 | 7% | +0.059 | -0.003 | -0.87 | 20% | +245.5 | 65.5 |
| F3 | 2022 to 2026-01-09 | 4,147 | 7% | +0.059 | -0.003 | -0.51 | 40% | +246.3 | 68.0 |
| A1 | 2022 to 2026-01-09 | 4,133 | 7% | +0.058 | -0.005 | -0.41 | 40% | +238.1 | 81.9 |

## FxPro GOLD 2016-02 to 2026-11-05

| Cell | Period | Trades | Fast | Mean net R | Minus BASE | t | Years better | Sum R | Largest drawdown R |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BASE | all | 6,442 | 7% | +0.030 | +0.000 | +nan | nan% | +194.3 | 133.1 |
| F1 | all | 6,440 | 7% | +0.029 | -0.001 | -0.25 | 36% | +186.5 | 133.2 |
| F2 | all | 6,441 | 7% | +0.026 | -0.005 | -1.50 | 18% | +164.5 | 147.9 |
| F3 | all | 6,438 | 7% | +0.026 | -0.005 | -0.86 | 45% | +164.6 | 144.9 |
| A1 | all | 6,427 | 7% | +0.029 | -0.001 | -0.14 | 45% | +185.3 | 142.0 |

**No cell beats BASE on 2012-2021 by the registered bar (condition 1): M8 stays.**
