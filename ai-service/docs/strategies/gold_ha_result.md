# Gold: Heikin-Ashi colour flips on 15m, XAUUSD and FxPro

_`python -m app research gold-ha build`, registered in `GOLD_HA.md` (2026-11-12). Entry and exit at the real next open; R = ATR(14, 15m); cost = spread + $0.07; no swap charged._

| Cell | Period | Trades | A day | Gross R | Cost R | Net R | At 2x | Years + | Bars held | t vs E0 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| H24 | 2012-2021 | 59,780 | 19.3 | -0.012 | 0.279 | -0.291 | -0.569 | 0% | 3.9 | -2.29 |
| H24 | 2022 to 2026-01-09 | 23,465 | 18.7 | -0.003 | 0.077 | -0.080 | -0.157 | 0% | 4.0 | -0.41 |
| DAY | 2012-2021 | 59,210 | 19.1 | -0.009 | 0.278 | -0.286 | -0.564 | 0% | 3.8 | -1.63 |
| DAY | 2022 to 2026-01-09 | 23,259 | 18.6 | -0.001 | 0.077 | -0.077 | -0.154 | 20% | 3.9 | -0.07 |

Condition 1 (2012-2021): H24 not met, DAY not met; the better cell by net R: DAY.

**DAY:** check -0.077 R (23,259 trades); FxPro -0.203 (63,169, gross -0.007); daily correlation with the five LVL4H +0.15, PIVOT +0.22, PIVW +0.13, ASIA +0.17, PWHL +0.09. Conditions 1-4: no/no/no/no. **dropped.**

## Reported, not a trial: fills at HA prices (the artefact)

The same trades of each cell, entered and exited at HA prices instead of real ones:

| Cell | Period | Net R at real prices | Net R at HA prices |
| --- | --- | --- | --- |
| H24 | 2012-2021 | -0.291 | +0.429 |
| H24 | 2022 to 2026-01-09 | -0.080 | +0.668 |
| DAY | 2012-2021 | -0.286 | +0.431 |
| DAY | 2022 to 2026-01-09 | -0.077 | +0.667 |

## Reported, deciding nothing: other frames (H24, real fills)

| Frame | Period | Trades | A day | Gross R | Cost R | Net R | t vs E0 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1h | 2012-2021 | 14,632 | 4.71 | +0.028 | 0.125 | -0.097 | +2.43 |
| 1h | 2022 to 2026-01-09 | 5,788 | 4.62 | -0.020 | 0.035 | -0.055 | -0.81 |
| 4h | 2012-2021 | 3,527 | 1.14 | +0.066 | 0.060 | +0.006 | +2.63 |
| 4h | 2022 to 2026-01-09 | 1,392 | 1.11 | +0.128 | 0.017 | +0.111 | +3.43 |
| D1 | 2012-2021 | 492 | 0.16 | +0.020 | 0.021 | -0.001 | +0.20 |
| D1 | 2022 to 2026-01-09 | 199 | 0.16 | +0.144 | 0.006 | +0.138 | +1.30 |

By year, net R (15m):

| Cell | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| H24 | -0.238 | -0.311 | -0.219 | -0.449 | -0.430 | -0.290 | -0.406 | -0.271 | -0.263 | -0.149 | -0.114 | -0.090 | -0.100 | -0.106 | -0.025 | -0.006 |
| DAY | -0.233 | -0.305 | -0.218 | -0.444 | -0.424 | -0.286 | -0.404 | -0.265 | -0.257 | -0.147 | -0.108 | -0.086 | -0.095 | -0.103 | -0.026 | +0.007 |
