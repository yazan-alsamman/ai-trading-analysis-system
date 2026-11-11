# Gold: the magnet to an untouched level, XAUUSD and FxPro

_`python -m app research gold-magnet build`, registered in `GOLD_MAGNET.md` (2026-11-11). XAUUSD 5m 2012 to 2026-01-09, then FxPro GOLD from 2016-02; cost = spread + $0.07, slip $0.10 on SL exits. FxPro: the export's summary bars are dropped (`gold_live.fx_lines`)._

## Part A: is a level reached more often than any point at the same distance?

Hit = the move reaches the target before the SL (or 16:45). q(m) = the share of all triggers reaching the same distance m. RW = 1 / (1 + m). t from trading-day clusters.

| Period | Triggers | With a level 1.5-4 R | Mean m | Hit | q(m) | RW | Excess over q | t |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2012-2021 | 17,905 | 6,918 | 2.54 | 21.4% | 22.3% | 29.3% | -0.9% | -0.99 |
| 2022 to 2026-01-09 | 30,999 | 12,172 | 2.55 | 23.5% | 24.4% | 29.3% | -0.9% | -1.21 |
| FxPro 2016-2026 | 38,276 | 14,988 | 2.54 | 21.8% | 23.1% | 29.3% | -1.4% | -2.11 |

**Magnet (registered reading): not present.**

By family of the nearest level (trades, hit, q(m), excess, t):

| Family | 2012-2021 | 2022 to 2026-01-09 | FxPro 2016-2026 |
| --- | --- | --- | --- |
| DAY | 907: 19% vs 22%, -3.3% (t -1.4) | 1,210: 21% vs 25%, -4.0% (t -1.7) | 1,509: 19% vs 23%, -4.4% (t -2.2) |
| WEEK | 240: 18% vs 22%, -4.3% (t -0.9) | 279: 25% vs 24%, +1.4% (t +0.3) | 334: 18% vs 23%, -5.2% (t -1.4) |
| PIVOT | 664: 23% vs 23%, +0.1% (t +0.0) | 1,053: 27% vs 25%, +1.8% (t +0.7) | 1,134: 25% vs 24%, +1.5% (t +0.6) |
| ASIA | 1,681: 26% vs 22%, +3.9% (t +1.8) | 3,674: 26% vs 24%, +1.6% (t +1.0) | 4,260: 23% vs 23%, +0.4% (t +0.3) |
| SWING | 1,548: 20% vs 23%, -2.6% (t -1.4) | 2,785: 23% vs 24%, -1.5% (t -0.9) | 3,272: 22% vs 23%, -1.3% (t -0.9) |
| FVG | 771: 27% vs 23%, +3.5% (t +1.2) | 1,504: 25% vs 26%, -1.0% (t -0.5) | 1,793: 23% vs 24%, -1.1% (t -0.6) |
| ROUND | 1,107: 14% vs 21%, -6.7% (t -3.1) | 1,667: 18% vs 23%, -5.4% (t -2.6) | 2,686: 19% vs 22%, -3.5% (t -2.2) |

## Part B: the trade

| Cell | Trades a day | Tune trades | Tune net (with slip) | Tune years + | Check trades | Check net (with slip) | TP / SL / time | Eligible |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| M0 | 1.77 | 2,537 | -0.092 (-0.114) | 20% | 3,879 | -0.047 (-0.069) | 22% / 63% / 14% |  |
| BE | 2.04 | 2,875 | -0.097 (-0.122) | 20% | 4,506 | -0.035 (-0.061) | 17% / 74% / 9% |  |

FxPro 2016-02 to 2026-11-05 (net R with slip, t): M0 -0.090 (t -4.38, 5,100); BE -0.088 (t -5.38, 5,846).

**No cell qualifies on 2012-2021: dropped.**

By year (net R with slip, trades):

| Year | M0 | BE |
| --- | --- | --- |
| 2012 | -0.194 (117) | -0.181 (119) |
| 2013 | -0.133 (168) | -0.207 (175) |
| 2014 | +0.105 (51) | +0.099 (57) |
| 2015 | -0.324 (33) | -0.288 (34) |
| 2016 | +0.023 (97) | +0.031 (100) |
| 2017 | -0.051 (35) | -0.083 (35) |
| 2018 | -0.225 (90) | -0.215 (93) |
| 2019 | -0.177 (143) | -0.228 (156) |
| 2020 | -0.075 (824) | -0.092 (975) |
| 2021 | -0.134 (979) | -0.127 (1131) |
| 2022 | -0.012 (1008) | -0.049 (1172) |
| 2023 | -0.135 (912) | -0.101 (1074) |
| 2024 | -0.144 (874) | -0.088 (970) |
| 2025 | +0.003 (1053) | -0.012 (1255) |
| 2026 | -0.291 (32) | -0.229 (35) |
