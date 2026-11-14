# Gold: the magnet to an untouched level (commercial track)

**Registered 2026-11-11, before any outcome of these rules was computed.** Fadi's idea: when price
starts to move with some strength toward an important level that is still far away (far enough
after costs), enter toward it; the target is the level itself, whatever happens there (break or
rebound). The analysis is on 5m; the side follows the 1h trend. Fadi accepted the design below and
asked for a measurement first, and for the trade with and without a move to break-even at +1 R.

Code: `app/research/gold_magnet.py`, `python -m app research gold-magnet build --export <GOLD M1>`.
Report: `gold_magnet_result.md` (not `gold_magnet.md`: Windows would overwrite this file).

Known overlap, disclosed: gold after an entry is close to a random walk (`gold_path.md`); strong
legs reach their 50% retrace less often (`GOLD_RETRACE`); round numbers were tested as break
levels (`GOLD_ROUND`). This test asks a different question: is the **way to** a level easier than
the way to any point at the same distance?

## 1. Levels (all, each with its own life)

A level is a target only while it is **alive** at the trigger bar (untouched through the trigger
bar's own high and low). Trading day = 18:00 to 17:00 New York (the D1 bar).

| Family | Levels | Alive while |
| --- | --- | --- |
| DAY | previous day high, low, close; 5-day high, low | untouched since the trading day began |
| WEEK | previous week high, low | untouched since the trading day began |
| PIVOT | classic daily pivot P, R1, S1 (from the previous day) | untouched since the trading day began |
| ASIA | high and low of 19:00-02:00 New York | untouched since 02:00 New York |
| SWING | confirmed 1h swing highs and lows (3 bars each side), known at the close of the third bar after | untouched since confirmation, at most 5 days after the swing bar |
| FVG | near edge of a 1h fair value gap of at least 0.1 x ATR(14, 1h) (bullish: the low of bar j above the high of bar j-2; the near edge for price above it is the low of bar j; bearish mirrored), known at the close of bar j | untouched since bar j closed, at most 5 days |
| ROUND | multiples of $50 | untouched since the trading day began |

The target is the **nearest** alive level in the trade's direction; its family is kept.

## 2. The trigger (5m bars, at the bar's close)

- Entry window: bars opening 02:00 to 13:55 New York, Monday to Friday. No entry from 15 minutes
  before to 15 minutes after a high-importance USD release (`calendar.parquet`).
- **1h trend:** EMA(20) above EMA(50) on the last closed 1h bar for a buy, below for a sell.
- **Strong move** in that direction: the bar's body (close - open, signed) at least 0.6 x
  ATR(14, 5m), or the close minus the close three bars earlier at least 1.0 x ATR(14, 5m).
- **SL** = the move's origin: the lowest low of the last three bars (this one included) minus
  0.1 x ATR(14, 5m) for a buy; mirrored for a sell. R = entry - SL.
- **Target** T = the nearest alive level minus 0.05 x ATR(14, 5m) for a buy (just before it);
  mirrored for a sell. m = (T - entry) / R.
- **Distance gate:** 1.5 <= m <= 4, and cost (the bar's spread + $0.07) / R <= 0.10.
- Exit: T, SL, or 16:45 New York. A bar that reaches both counts as the SL.

## 3. Part A: the measurement (the magnet itself; descriptive)

- **Triggers:** every bar that passes the trend, strength, window, release and cost rules of §2,
  with or without a level (overlapping triggers allowed). For each, MFE = the largest favourable
  move, in R, before the SL is hit or 16:45 (a bar that reaches the SL adds nothing).
- **Control curve** q(m) = the share of all triggers with MFE >= m: how often an arbitrary point
  at distance m is reached after the same kind of move.
- **Level triggers:** those with a target in 1.5-4 R. Hit = MFE >= m. Excess = hit - q(m), and
  hit - 1/(1 + m) (the drift-free random walk, which ignores the 16:45 cut) for reference.
- Reported for 2012-2021, 2022 to 2026-01-09 and FxPro 2016-02 to 2026-11-05, in total and by
  family, with t of the mean excess from day sums (trading days as clusters).
- **Reading (registered):** the magnet is present if the mean excess over q(m) is > 0 with t >= 2
  on 2012-2021 and > 0 on the check period. Limitation, stated: the control triggers include
  moments with no level ahead (new highs), so the two sets differ in context, not only in the
  level.

## 4. Part B: the trade (two cells)

- **M0:** T, SL or 16:45, nothing else.
- **BE:** as M0, and once a bar's favourable extreme reaches +1 R (the bar not hitting the SL),
  the SL moves to entry + the round-trip cost from the next bar (Fadi, 2026-11-11).
- One open trade at a time. Cost = the entry bar's spread + $0.07; slip $0.10 on SL exits
  (break-even exits included).
- **Choice and decision** (as `GOLD_C123` §3): the cell with the best mean net R with slip on
  2012-2021 among cells with net > 0, at least 60% of the years positive and at least 300 trades.
  Conditions: 1. a cell qualifies; 2. net R with slip > 0 on 2022 to 2026-01-09; 3. net R with
  slip > 0 on FxPro 2016-02 to 2026-11-05; 4. daily net R correlation with each of the five < +0.2.
  Its t on the check and FxPro is reported against the research bar (about +0.17 R by chance as
  the best of about 66 looks).
- Part B is decided by its conditions whatever Part A shows; both are reported.

## 5. Count

Part A (1 look) and 2 trade cells, logged in `docs/phase3/TRIALS.md` (about 69 looks on gold).

## 6. Outcome (2026-11-11): no magnet; the trade loses; dropped

`gold_magnet_result.md`.

- **Part A: not present.** A level 1.5-4 R away is reached slightly *less* often than any point at
  the same distance after the same kind of move: excess -0.9% on 2012-2021 (t -0.99, 6,918 level
  triggers), -0.9% on the check (t -1.21), -1.4% on FxPro (t -2.11). By family nothing holds in
  every period; ROUND levels are reached less often (-3.5% to -6.7%, t -2.2 to -3.1), DAY levels
  less often too. ASIA was +3.9% (t 1.8) on 2012-2021 but +1.6% and +0.4% after.
- **Part B: dropped at condition 1.** M0 -0.114 R with slip on 2012-2021 (2,537 trades, 20% of
  years positive), -0.069 on the check, -0.090 on FxPro; BE -0.122 / -0.061 / -0.088. The move to
  break-even does not help: it turns targets into break-even stops (TP 22% to 17%).
- **Correction, before any reading was taken from it.** The first run read the FxPro export as is
  and showed FxPro excess +3.1% (t 4.5; SWING +11.9%, t 9.2) and M0 +0.032. The SWING targets sat
  exactly at the later lows, which led to a data fault: **the FxPro GOLD export holds summary bars**
  (real volume 0, tick volume above 5,000; about 250 a year in 2017-2022, most at 00:00 server
  time), each carrying the coming day's whole high and low (2018-01-29 00:00: high 1352.30, low
  1337.51, the day's real extremes). Levels built from them (1h swings, the Asia range) were the
  day's future extremes. FxPro was rerun without them (now in `gold_live.fx_lines`); the numbers above are the
  clean run. The XAUUSD research store does not have them (0-1 unusual bars a year).
- **Effect on the five's FxPro check** (descriptive, same code, with and without the summary bars):
  all five +0.026 R with slip (7,251 trades) raw, +0.031 (6,442) clean; LVL4H +0.073 / +0.082,
  PIVOT -0.013 / -0.019, PIVW +0.022 / +0.025, ASIA +0.016 / +0.041, PWHL +0.095 / +0.106. The
  five's verdict does not change; about 800 raw-only trades came from the fake bars. Every other
  FxPro check, NAS100 and silver were rerun without them the same day; no decision changed, one
  reading did (the five on NAS100): `docs/data_quality/FXPRO_SUMMARY_BARS.md`.
