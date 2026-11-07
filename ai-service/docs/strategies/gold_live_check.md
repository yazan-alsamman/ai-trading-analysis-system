# Gold v1 live EA against Python

_`tools/mt5/GoldLive.mq5` in the Strategy Tester over the exam period against v1 in Python on FxPro's GOLD feed (`gold-live fxpro`) (`GOLD_V1.md`). Matched on strategy and signal bar._

| Item | Value |
| --- | --- |
| Python trades | 286 |
| EA trades | 288 |
| Matched | 283 |
| Same direction | 283 |
| Largest level difference | 6.06 |
| D, EA / Python (median) | 1.0000 |
| D off by more than 1% | 8 |
| Gross R, matched: Python / EA | +0.058 / +0.053 |
| Net R, all: Python / EA | +0.046 / +0.041 |

## Python only (3)

| Strategy | Signal bar (server) | EA's reason |
| --- | --- | --- |
| LVL4H | 2026.09.30 09:50:00 | - |
| LVL4H | 2026.10.20 10:00:00 | - |
| PIVOT | 2026.06.11 22:20:00 | - |

## EA only (5)

| Strategy | Signal bar (server) | Kind | Fill |
| --- | --- | --- | --- |
| LVL4H | 2026.05.26 13:50:00 | PDL | stop |
| LVL4H | 2026.07.14 15:30:00 | PDH | stop |
| LVL4H | 2026.09.30 09:15:00 | PDH | stop |
| LVL4H | 2026.10.20 09:55:00 | PDL | stop |
| PIVOT | 2026.06.11 22:15:00 | R1 | stop |
