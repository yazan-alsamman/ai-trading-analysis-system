# Gold: the AH bot's leg exits (TP past the leg's high, SL one leg below its low)

**Registered 2026-11-09, before any outcome of these rules was computed** (Fadi approved this
text: "Approve and run").

**The idea.** The AH bot (`GOLD_AH.md`, `research_notes/ah_bot_reverse_engineering.md`) sets its
exits from the impulse leg before the pullback it buys: L the leg's low, H its high, R = H − L,
TP = L + 1.088 × R, SL = H − 2.025 × R (132 of its 156 matched signals). The wide SL alone gives a
high win rate and no edge: under a random walk, P(TP before SL) = SL / (SL + TP). Fadi's view is
that price, after its games, goes back to where it has to go, here the leg's high. **The question:
after a pullback in a 1-minute trend, does price reach just past the leg's high more often than
the random-walk rate, by more than the costs?**

Code: `app/research/gold_ah.py` (new settings). Report: `gold_ahx_xauusd.md`.

## 1. Data and costs

As `GOLD_AH.md` §1: XAUUSD research store M1, tune 2012-2021, check 2022 to 2026-01-09, FxPro
GOLD M1 for condition 3. The signal bar's spread + $0.07 per oz per leg; $0.10 slippage on SL
exits, reported beside the net; a 2x cost run.

## 2. Rules

The entries are AHB's raw signals (`GOLD_AH.md` §2: close > close[10], EMA20 > EMA50,
close > EMA50, %K(5) ≤ 0.4, the first bar of the condition, not 16:50 to 18:05 New York), with a
new exit. Written for a buy; a sell is the mirror image.

- **The leg.** Going back from the signal bar i over the confirmed M1 pivot lows (3 bars each
  side, confirmed by bar i), L is the most recent one that is still the lowest low from it to i
  and that has no other pivot low between it and H, where H is the highest high from L to i.
  No trade if none is found within the last 10 pivots, or if the entry c[i] is not between L
  and H.
- **The exits:** TP = L + 1.088 × R and SL = H − 2.025 × R, R = H − L. Exit at the SL, the TP,
  the close of the last bar before 17:00 New York, or 360 bars after the entry. A bar reaching
  both counts as the SL.
- **Overlap:** a signal is skipped while a signal of the same direction is open.
- **Result:** net R per signal, R being the planned risk (the SL distance, or as `GOLD_AH.md` §2
  with E2).

## 3. Settings (2, fixed)

| Setting | Legs |
| --- | --- |
| X1 | E1 only, 1 unit at c[i] |
| X2 | E1 + E2: 2 units more at a limit c[i] − 0.18 × (c[i] − SL), valid while E1 is open; both legs with the same TP and SL, no break-even |

## 4. Decision (per setting)

As `GOLD_AH.md` §4: net R > 0 on 2012-2021 with at least 60% of the years positive; net R with
slippage > 0 on the check; net R with slippage > 0 on FxPro GOLD 2016-02 to 2026-11-05.

**Reported beside the decision, deciding nothing:**

- **The edge test (X1, before costs):** the TP hit rate against the random-walk rate, the mean of
  SL / (SL + TP) per trade, on both periods, with its standard error.
- The leg found against the bot's on 2026-10-14 to 2026-11-05 (FxPro export): how often L, H, TP
  and SL match the bot's orders within $0.05.
- Results by year and by side; signals a day; median R in $.

## 5. Count

2 settings, logged in `docs/phase3/TRIALS.md` as exploratory looks of the commercial track.

## 6. Outcome (2026-11-09): both dropped

`gold_ahx_xauusd.md`.

| Setting | 2012-2021 net R (slip), trades | Years + | Check net R (slip) |
| --- | --- | --- | --- |
| X1 | −0.195 (−0.207), 68,597 | 0% | −0.049 (−0.056) |
| X2 | −0.173 (−0.187), 68,589 | 0% | −0.046 (−0.054) |

- **The leg finder reproduces the bot.** On the FxPro export, it finds a leg for 147 of the bot's
  156 E1 signals, and both the SL and the TP match the bot's order within $0.05 in 69% of them
  (72% within $0.50).
- **The edge test: price does not go back to the leg's high more often than chance.** On the trades
  that ended at the TP or the SL, the TP hit rate is the random-walk rate: 77.1% against 76.9% on
  2012-2021 (+0.2 points, SE 0.2), 78.3% against 77.0% on the check (+1.2, SE 0.2). Counting the
  time exits as misses (the registered line) gives −5.2 and −3.7 points; that line is biased low,
  because a trade cut by the clock has neither hit.
- **Gross R is about zero** (−0.017 and −0.002), and the costs (0.04-0.18 R) decide the sign.
  Every year from 2012 to 2025 is negative.
- The +1.2 points on the check is about 0.02 R a trade before costs, half of the 0.04-0.05 R cost.
- Implementation note: the first full run was stopped after 17 minutes: `leg_levels` negated the
  whole price series for every sell. It now slices first; the results did not change (same code
  path, checked on 2013: 82.5 s to 0.3 s).
