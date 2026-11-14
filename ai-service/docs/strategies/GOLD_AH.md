# Gold: the "AH" bot's pullback in a 1-minute trend, cloned and varied (commercial track)

**Registered 2026-11-08, before any outcome of these rules was computed on any history** (Fadi:
"register and test").

**The idea.** A third-party gold bot (comments `AH_S0/S1_E1/E2`, FxPro real account, 2026-10-14 to
2026-11-06, +324 $ on 3,000 $) was reverse engineered from its trade report and FxPro GOLD M1 bars
(`research_notes/ah_bot_reverse_engineering.md`). Its exact trigger and SL formula were not
recovered. AHB below is the closest rule we can write; V1 to V6 are changes suggested by the bot's
own 156 trades.

**Disclosure.** The rules and every threshold here come from the bot's trades and bars between
2026-10-14 and 2026-11-05. 2026-10-14 to about 2026-10-21 lies inside the primary lockbox window
(Fadi chose on 2026-11-08 to treat that analysis as separate from the research). Nothing here reads
the research store after 2026-01-09.

Code: `app/research/gold_ah.py`.

- `python -m app research gold-ah build` runs the eight settings on XAUUSD.
- `gold-ah fxpro --export <GOLD M1 export>` runs them on FxPro's GOLD feed.

Reports: `gold_ah_xauusd.md`, `gold_ah_fxpro.md`.

## 1. Data and costs

As `GOLD_SHADOW.md` §1, on **M1** bars: XAUUSD research store 2012-01 to 2026-01-09 (tune period
2012-2021, check 2022 to 2026-01-09); FxPro GOLD M1 export for condition 3. Cost per leg, a round
trip: the signal bar's recorded spread + $0.07 per oz. Slippage: $0.10 on every stop exit (SL and
break-even), reported beside the net.

## 2. Rules: AHB (the clone)

Written for a buy; a sell is the mirror image. All on closed M1 bars; c, h, l are bid prices.

- **Condition at bar i:** c[i] > c[i−10]; EMA20 > EMA50 (on closes); c[i] > EMA50;
  %K(5) = (c − lowest low of 5) / (highest high of 5 − lowest low of 5) ≤ 0.4.
- **Signal:** the first bar where the condition holds after a bar where it did not. No signal from
  16:50 to 18:05 New York (the daily break and the reopen).
- **Distances:** SLd = 1.7 × (highest high − lowest low of the last 10 bars, i included).
  TP1 = 0.4 × SLd. Off = 0.18 × SLd.
- **Legs:** E1 is 1 unit at c[i]. E2 is 2 units, a buy limit at c[i] − Off, valid while E1 is
  open. Both have the SL at c[i] − SLd.
- **Targets:** E2's TP is c[i] + TP1. E1's TP is c[i] + TP1 while E2 is unfilled, and moves to
  c[i] + 0.7 × SLd when E2 fills. When E2 exits at its TP, E1's SL moves to c[i] (break-even).
- **Bar order (conservative):** in each bar, the E2 fill first, then the SL, then the targets. A
  leg cannot take its target in the bar it filled. A break-even move counts from the next bar.
- **Exits:** SL, TP, break-even, the close of the last bar before 17:00 New York (daily break and
  Friday close), or the close 360 bars after the entry.
- **Overlap:** a signal is skipped while a signal of the same direction is open.
- **Result per signal:** net R = net $ / planned risk, the planned risk being SLd for E1 plus
  2 × (SLd − Off) for E2 (SLd alone without E2).

## 3. Settings (each a change to AHB; fixed, no tuning)

| Setting | Change | From the bot's trades |
| --- | --- | --- |
| AHB | none | the clone |
| V1 | skip while any signal is open | one at a time +377 $ vs +224 $ |
| V2 | also c[i] − c[i−240] > 0 | 4-hour move with the trade +411 $, against −186 $ |
| V3 | also the 60-bar position (c − lowest low 60) / (range 60) ≤ 0.64 | deepest third +292 $, rest −68 $ |
| V4 | also SLd ≥ 4.7 × ATR(14, M1) | tightest third of SL −423 $ |
| V5 | TP1 = 0.8 × SLd and E1's moved TP = 1.4 × SLd | top third of TP/SL +399 $, rest −175 $ |
| V6 | E1 only (no E2, no break-even), TP1 = 0.4 × SLd | E2 fills: E1 −202 $, E2 +127 $ |
| ALL | V1 + V2 + V3 + V4 + V5 + V6 (E1 only, TP 0.8 × SLd) | |

The bot's S1 setup (−106 $) cannot be dropped: S0 and S1 are not told apart in the bars.

## 4. Decision (per setting)

As `GOLD_SHADOW.md` §4. A setting goes to the demo as a shadow strategy only if all hold:

1. Net R > 0 on 2012-2021, with at least 60% of the years positive.
2. Net R with slippage > 0 on the check, 2022 to 2026-01-09.
3. Net R with slippage > 0 on FxPro GOLD, 2016-02 to 2026-11-05.

**Reported beside the decision, deciding nothing:** results by year and by side; the 2× cost run;
signals a day; on the FxPro export of 2026-10-01 to 2026-11-05, how many of the bot's 156 E1 entries
AHB fires within 2 minutes in the same direction, and AHB's net over the bot's period.

## 5. Count

There are 8 settings. They are logged in `docs/phase3/TRIALS.md`, as exploratory looks of the
commercial track.

## 6. Outcome (2026-11-08): all eight dropped

`gold_ah_xauusd.md`.

| Setting | 2012-2021 net R (slip) | Years + | Check net R (slip) | Decision |
| --- | --- | --- | --- | --- |
| AHB | −0.180 (−0.199), 54,706 trades | 0% | −0.050 (−0.060) | dropped |
| V1 | −0.171 (−0.189) | 0% | −0.050 (−0.060) | dropped |
| V2 | −0.173 (−0.190) | 0% | −0.049 (−0.059) | dropped |
| V3 | −0.217 (−0.239) | 0% | −0.059 (−0.071) | dropped |
| V4 | −0.162 (−0.178) | 0% | −0.043 (−0.052) | dropped |
| V5 | −0.189 (−0.215) | 0% | −0.056 (−0.070) | dropped |
| V6 | −0.195 (−0.208) | 0% | −0.052 (−0.059) | dropped |
| ALL | −0.189 (−0.208), 11,162 trades | 0% | −0.030 (−0.040) | dropped |

- **There is no edge before costs.** Gross R is −0.015 to +0.017 for every setting in both
  periods. The 63-70% win rate is the 0.4 R target, not an edge.
- **Costs decide the sign.** 0.15-0.20 R a trade on 2012-2021 (smaller ranges, wider spreads in R)
  and 0.04-0.05 R on 2022 on. Every year from 2012 to 2025 is negative for AHB.
- **None of the six changes helps much.** V4 (no tight SL) and V1 (one at a time) are the least bad.
  ALL trades least and is least negative on the check, but is still negative.
- **The bot's period, FxPro GOLD 2026-10-01 to 2026-11-05** (deciding nothing): AHB fires within
  2 minutes of 84 of the bot's 160 E1 entries (52%), but gives 1,145 signals against the bot's 160.
  Every setting is negative there too after costs (AHB −0.030 R with slippage, 607 trades; ALL
  −0.124). The bot's +324 $ came from a trigger and SL that the clone does not reproduce.
- The year table's 2011 row is the December 2011 warm-up month (not in any decision).
- Condition 3 (FxPro 2016-2026) was not needed.
