# Gold combination in the MT5 Strategy Tester (commercial track, exploratory)

_`tools/mt5/GoldCombo.mq5`, "Every tick based on real ticks" (where the broker has no real ticks, MT5 generates them from M1 bars: the tester log says which); parts merged. Statuses: {'closed': 3362, 'expired': 858}. Net R = (profit + commission + fee + swap) / the money risk of the level and SL. Python = the simulation of `gold_combo.md` on the same trades._

| Set | Trades | MT5 net R | Python net R | Python net with slip |
| --- | --- | --- | --- | --- |
| All replayed | 3,362 | +0.057 | +0.067 | +0.048 |
| AI filter kept | 1,991 | +0.078 | +0.086 | +0.067 |
| LVL4H | 1,376 | +0.125 | +0.128 | +0.116 |
| PIVOT | 1,986 | +0.010 | +0.025 | -0.000 |

| Year | Trades | MT5 net R | Python net R |
| --- | --- | --- | --- |
| 2015 | 9 | -0.047 | -0.207 |
| 2016 | 197 | +0.009 | +0.005 |
| 2017 | 198 | -0.059 | -0.045 |
| 2018 | 211 | +0.002 | +0.011 |
| 2019 | 244 | -0.008 | -0.057 |
| 2020 | 397 | +0.147 | +0.165 |
| 2021 | 423 | -0.000 | +0.047 |
| 2022 | 444 | +0.062 | +0.100 |
| 2023 | 452 | +0.137 | +0.150 |
| 2024 | 401 | -0.024 | -0.033 |
| 2025 | 375 | +0.179 | +0.170 |
| 2026 | 11 | -0.019 | -0.006 |

## Runs (2026-11-05)

- Parts merged: `gold_combo_replay.csv` (2024-01-01 to 2026-01-10) and `_2024-2022`,
  `_2022-2020`, `_2020-2018`, `_2017-2015`, `_2014-2012`; all with UseAI = false, M5, 1 lot.
  `_2026_2024` (an M1 rerun to 2026-01-01) is left out.
- **Tick source: every part ran on ticks MT5 generated from M1 bars.** Each log says "real ticks
  begin from 2026.01.02, every tick generation used": the terminal holds real GOLD ticks only from
  2026-01. So this checks the broker's order rules, contract size, commission and the EA's
  logic, not fills inside the minute. MT5 and Python read the same M1 bars.
- **The tester has no M1 history before late 2015** (the server's 2012-2015 files hold daily bars
  only): 2012-2014 replayed nothing and 2015 has 9 trades. Those years exist only in Python.

## LVL4H alone in MT5

| Year | Trades | MT5 net R | Python net R |
| --- | --- | --- | --- |
| 2016 | 19 | +0.738 | +0.717 |
| 2018 | 14 | +0.030 | +0.014 |
| 2019 | 52 | +0.246 | +0.231 |
| 2020 | 194 | +0.161 | +0.169 |
| 2021 | 233 | +0.080 | +0.100 |
| 2022 | 230 | +0.057 | +0.084 |
| 2023 | 238 | +0.169 | +0.157 |
| 2024 | 196 | +0.021 | +0.006 |
| 2025 | 194 | +0.204 | +0.198 |
| 2026 (to 01-09) | 6 | -0.273 | -0.262 |

- Tuning years (2016-2021): 512 trades, +0.151 (SE 0.061).
- Check years (2022-2026): 864 trades, +0.110 (SE 0.041); Python with slippage +0.098.
- 172.6 R in total; the largest drawdown was 14.9 R.
- Per-trade correlation, MT5 against Python, all strategies: 0.974.
