# Gold v1 live EA against Python

_`tools/mt5/GoldLive.mq5` in the Strategy Tester over the exam period against v1 in Python on FxPro's GOLD feed (`gold-live fxpro`) (`GOLD_V1.md`). Matched on strategy and signal bar._

| Item | Value |
| --- | --- |
| Python trades | 692 |
| EA trades | 694 |
| Matched | 682 |
| Same direction | 682 |
| Largest level difference | 6.06 |
| D, EA / Python (median) | 1.0000 |
| D off by more than 1% | 11 |
| Gross R, matched: Python / EA | +0.110 / +0.106 |
| Net R, all: Python / EA | +0.096 / +0.096 |

| Strategy | Python | EA | Matched | Gross R matched, Python / EA |
| --- | --- | --- | --- | --- |
| ASIA | 216 | 216 | 211 | +0.201 / +0.199 |
| LVL4H | 153 | 155 | 151 | +0.072 / +0.069 |
| PIVOT | 133 | 133 | 132 | +0.043 / +0.034 |
| PIVW | 131 | 131 | 130 | +0.143 / +0.139 |
| PWHL | 59 | 59 | 58 | -0.044 / -0.045 |

## Python only (10)

| Strategy | Signal bar (server) | EA's reason |
| --- | --- | --- |
| ASIA | 2026.01.14 14:55:00 | - |
| ASIA | 2026.01.16 13:45:00 | - |
| ASIA | 2026.02.04 09:50:00 | - |
| ASIA | 2026.07.21 09:10:00 | - |
| ASIA | 2026.08.17 17:15:00 | - |
| LVL4H | 2026.09.30 09:50:00 | - |
| LVL4H | 2026.10.20 10:00:00 | - |
| PIVOT | 2026.06.11 22:20:00 | - |
| PIVW | 2026.06.11 22:20:00 | - |
| PWHL | 2026.07.17 19:20:00 | - |

## EA only (12)

| Strategy | Signal bar (server) | Kind | Fill |
| --- | --- | --- | --- |
| ASIA | 2026.01.14 09:25:00 | ASH | stop |
| ASIA | 2026.01.16 13:40:00 | ASH | stop |
| ASIA | 2026.02.04 09:30:00 | ASH | stop |
| ASIA | 2026.07.21 09:05:00 | ASH | stop |
| ASIA | 2026.08.17 16:55:00 | ASH | stop |
| LVL4H | 2026.05.26 13:50:00 | PDL | stop |
| LVL4H | 2026.07.14 15:30:00 | PDH | stop |
| LVL4H | 2026.09.30 09:15:00 | PDH | stop |
| LVL4H | 2026.10.20 09:55:00 | PDL | stop |
| PIVOT | 2026.06.11 22:15:00 | R1 | stop |
| PIVW | 2026.06.11 22:15:00 | R1 | stop |
| PWHL | 2026.07.17 19:15:00 | PWL | stop |
