# Gold v1: frozen for the demo (commercial track)

**Frozen by Fadi on 2026-11-05, after the lockbox exam passed (`GOLD_LOCKBOX_EXAM.md`).** v1 does
not change. Any improvement runs beside it as a separate shadow version on the demo, is compared
with v1 on new data only, and replaces v1 only if it beats it there.

## Rules

The rules are those of the exam (`gold_combo.py`, `gold_exam.py`). All times are New York.

| | LVL4H | PIVOT |
| --- | --- | --- |
| Levels, from the previous trading days (17:00 to 17:00 New York) | PDH, PDL, 5-day high, 5-day low | R1 = 2P − L, S1 = 2P − H, P = (H + L + C) / 3 |
| Distance D | 0.75 × ATR(14, 4h) | ATR(14, 1h) |
| Entries | 02:00 to 16:00, Monday to Friday | 02:00 to 16:00, Monday to Friday |
| Cost cap | (spread + $0.07) / D ≤ 0.05 | none |
| Horizon | 200 five-minute bars | 48 bars |

- **Entry.** Each level trades once a day, at its first touch inside the window.
  - It is a stop order at the level, in the direction of approach, valid for one 5-minute bar.
  - If price is already through the level, the entry is at market.
  - SL = entry ∓ D; no TP.
- **One open trade per strategy.** When one level fills, the strategy's other orders are
  cancelled.
- **M8 management, on each closed 5-minute bar:**
  - After +1 D in favour, the SL moves to entry + cost, where cost = the entry bar's mean spread
    + $0.07.
  - Then the SL trails to the last confirmed 5-minute swing (2 bars on each side) ∓ 0.1 ×
    ATR(14, 5m), when that is better and price is beyond it.
- **Exit:**
  - by the SL;
  - at 16:45 New York the same day;
  - or after the horizon, whichever comes first.
- **No AI filter.**
- **Size: 0.5% to 1% of the account a trade (fixed fractional).** 0.5% to start.

## The live EA: `tools/mt5/GoldLive.mq5`

- It computes the signals itself from the terminal's bars, places the orders and runs M8.
- It logs every signal, fill, SL move and exit to `<Common>/Files/gold_live_log.csv`.
- It needs a hedging account: LVL4H and PIVOT may hold opposite trades.
- `SignalsOnly = true` logs the signals and places nothing (advisory).
- It is checked against Python in the Strategy Tester (`python -m app research gold-live check`)
  before the demo starts.

**Known live differences from the backtest**, where the backtest used information from the touch
bar itself:

- **The cost cap.** It uses the last closed bar's mean spread, not the touch bar's.
- **The distance D.** It uses the last 4h or 1h bar closed when the bar opens. The backtest used
  the bar closed at the touch bar's close. They differ only when the touch bar is the last
  5-minute bar of a 4h (or 1h) bar.
- **Buy stops.** They fill on the ask; the backtest's touch is on the bid.

### First tester run (2026-11-05): the exam period on real ticks, RiskPct 0.5

`gold_live_check.md` compares the run with Python.

**Results:**

- 287 EA trades against 289 Python trades; 229 match on strategy and signal bar, all in the same
  direction.
- **On the 229 matched trades, the EA and the exam replay agree:** +0.029 against +0.031 R, with a
  per-trade correlation of 0.988. So the orders, M8 and the exits work as the backtest.
- **The rest differ because the bars differ, not the rules.**
  - In the tester the bars are built from real ticks. Python used the broker's exported M1 bars.
  - The two disagree on a day's high or low by a few cents on most days, and by dollars on some.
  - So a level sits a little elsewhere, and a few touches happen at another bar or not at all.
  - The 46 exam trades the EA did not take made +0.156 R. The 58 the EA took instead lost
    −0.094 R.
- Overall the EA made +0.004 R a trade (the tester's net profit was −$226 on $100,000) against
  +0.052 for the exam replay.
- The difference between the two sets of about 50 trades is within noise: the SE of each set is
  about 0.19 R. Still, it shows how thin the edge is. Moving the levels by cents moved the result
  from +0.05 to 0 R.

### Second tester run (2026-11-05): the same period in "1 minute OHLC" mode, FixedLots 1

**Results:**

- 288 EA trades against 289 in Python; 228 match.
- On the matched trades, gross R is +0.067 for the EA and +0.068 for Python.
- Overall the EA made +0.041 R a trade (net profit +$59,675 at 1 lot, PF 1.20).

**The levels still differ by cents on almost every day, so the bars were not the cause. The
feed is:**

- The research data is the `XAUUSD` M1 export, `XAUUSD_M1_201001110105_…`. Its M1 history goes
  back to 2010.
- The demo account trades `GOLD`. Its server has M1 bars only from late 2015.
- So these are two symbols with two price feeds. Their highs and lows differ by a few cents most
  days.
- On the `GOLD` feed, v1 made +0.004 R a trade on real ticks and +0.041 R on M1 bars, against
  +0.052 R for Python's trades replayed.

**Next:**

- The demo should trade the feed the live account will trade.
- The signal logic is checked against Python run on that same feed: export `GOLD` M1, build the
  Python trades from it, and compare them with the EA run.

## The demo

## The demo

| Item | Value |
| --- | --- |
| Account | FxPro demo, hedging, GOLD, M5 chart |
| Period | 3 months or 100 trades, whichever is later |
| Compared each month | live trades against the Python simulation of the same days; mean net R; cost a trade |
| Live money | only if the demo's trades agree with the simulation, and its mean net R is not below the exam's range |
