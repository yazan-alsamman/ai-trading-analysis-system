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
- **The shadow strategies.** Since 2026-11-07 the EA can also trade PIVW, ASIA and PWHL beside v1.
  - They have their own magic numbers and a smaller risk.
  - A cap on the open risk of all the EA's trades together applies to every strategy.
  - Details in `GOLD_SHADOW.md` §8. v1's rules are unchanged.
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

### v1 on FxPro's GOLD feed (2026-11-07)

Fadi exported `GOLD` M1 with MT5's "Export Bars" (`GOLD_M1_201501020000_202611052359.csv`, to
2026-11-05).

**The export:**

- `GOLD`'s history is daily bars to 2015-09-10, hourly bars to 2016-01-08, and M1 bars from
  2016-01-08 15:16.
- The spread is 0 to 2016-01-18.
- `gold-live fxpro` reads it from 2016-01-19 and trades from 2016-02-01.

**The EA's logic is checked** (`gold_live_check.md`, `check --reference fxpro`). On the same feed,
the second tester run (M1 bars) and Python agree:

| Item | Value |
| --- | --- |
| Trades matched on strategy and signal bar | 283 of 286 Python and 288 EA, all in the same direction |
| Gross R per trade, correlation | 0.998 |
| Net R, Python / EA | +0.046 / +0.041 |

The few differences are the known live differences above:

- Five same-day levels fill one bar apart: buy stops on the ask, and the cost cap and D come from
  an earlier bar.
- D is off by more than 1% on 8 trades.
- On one day (2026-03-18) a 5-day level is $6 off.

**v1 on FxPro `GOLD`** (`gold_fxpro.md`) uses FxPro's recorded spread + $0.07 per oz. It is not a
test: 2016 to 2026-01-09 was seen on the XAUUSD feed, and the settings were tuned there.

| Set | Trades | Net R (SE) | With slippage |
| --- | --- | --- | --- |
| All, 2016-02 to 2026-11-05 | 3,493 | +0.036 (0.020) | +0.021 |
| LVL4H | 1,379 | +0.081 (0.030) | +0.073 |
| PIVOT | 2,114 | +0.006 (0.028) | −0.013 |
| Exam period, 2026-01-12 to 2026-11-05 | 300 | +0.005 (0.062) | +0.001 |

What the results show:

- **By year, the sign changes.** v1 lost in 2016–2019, 2021 and 2024. It made money in 2020, 2022,
  2023 and 2025.
- **PIVOT carries nothing on this feed.** On the XAUUSD exam it made +0.062.
- **The first bars after the exam file are new data.** From 2026-10-21 to 2026-11-05, v1 took 15
  trades: 2 won, 12 lost a full R, and the mean was −0.62 R (−9.3 R in all).
  - This is within what a 15-trade run can do.
  - It is the start of the demo's record, not a decision.

### The five strategies together on FxPro GOLD (2026-11-07)

**Method.**

- Python's trades on the FxPro feed, from 2016-02 to 2026-11-05, with slippage.
- Each trade is weighted by its demo risk: 0.5% for LVL4H and PIVOT, 0.25% for PIVW, ASIA and
  PWHL.
- Returns are added, not compounded.

| Set | Total | Largest drawdown | Peak to trough |
| --- | --- | --- | --- |
| All five | +65% | **54%** | 2016-06 to 2022-08, recovered 2024-02 |
| Without PIVOT | +79% | 26% | 2021-04 to 2022-07 |
| LVL4H only | +50% | 11% | 2021-02 to 2021-07 |
| PIVW, ASIA, PWHL | +29% | 22% | 2021-04 to 2022-10 |
| All five, from 2019 | +95% | 38% | 2021-04 to 2022-08 |
| Without PIVOT, from 2019 | +77% | 26% | 2021-04 to 2022-07 |

**PIVOT makes most of the drawdown.**

- It lost 6.8%, 12.1%, 13.5% and 9.7% of the account in 2016-2019.
- It has no cost cap, and its stop (ATR(1h)) is small against the wider spreads of those years.
- Without it, the total is higher and the drawdown less than half.

**Removing PIVOT is a v1 change.** It is Fadi's decision, recorded before the demo. It would be
done with `TradePIVOT = false`, with nothing changed in the EA.

**Decision (Fadi, 2026-11-07): keep all five on the demo.** PIVOT made money in 2026: +4.7 R,
+0.035 R a trade, over 133 trades in the tester run of `GOLD_SHADOW.md` §8. The demo's stop rule
judges each strategy by itself.

## The demo

| Item | Value |
| --- | --- |
| Account | FxPro demo, hedging, GOLD, M5 chart |
| Period | 3 months or 100 trades, whichever is later |
| Compared each month | live trades against the Python simulation of the same days; mean net R; cost a trade |
| Live money | only if the demo's trades agree with the simulation, and its mean net R is not below the exam's range |
| Strategies | LVL4H, PIVOT (v1, `RiskPct = 0.5`), PIVW, ASIA, PWHL (shadow, `ShadowRiskPct = 0.25`); `MaxOpenRiskPct = 2` |

### Stop rules (written 2026-11-07, before the demo; Fadi: "Yes, write and commit")

A trade's net R is its net money (profit + commission + swap + fee, the EA's `DEAL` rows) over
its money risk at entry (the distance D × lots × 100).

1. **Each strategy by itself.**
   - Its mean net R is checked at its 100th demo trade, and then at every 50 more.
   - If it is below −0.10 R, the strategy is turned off (`Trade<NAME> = false`) and reviewed.
2. **All strategies together.**
   - The same check runs on every demo trade together: at the 100th, then every 50.
   - Below −0.10 R, the EA stops.
3. **The review after a stop.**
   - First the execution: are the demo's trades the Python trades of the same days
     (`gold-live check` on the demo log and a fresh GOLD export)?
   - If they are not, the EA is fixed. If they are, the strategy stays off.
   - It comes back only by a new decision recorded here.
4. **Account guards, not yet in the EA (to build before live money):**
   - a daily loss of 2% of the day's opening equity closes the EA's trades and stops it to the
     next day;
   - a drawdown of 10% from the equity peak stops it until a review.
5. **Why −0.10 after 100 trades.**
   - A trade's net R spreads by about 1 R, so a mean of 100 trades spreads by about ±0.1.
   - A strategy that truly makes +0.05 falls below −0.10 by chance about 7% of the time.
   - −0.10 is also the exam's fail line.

**A stop rule is a trade-off.** It can stop a strategy at the bottom of a drawdown that would
have recovered. On Python's FxPro trades from 2026-09-01, the five together had a mean of about
−0.14 R after 165 trades, so rule 2 would have stopped them by the end of October.
