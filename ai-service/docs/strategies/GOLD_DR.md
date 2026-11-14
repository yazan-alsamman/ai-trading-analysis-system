# Gold: the dealing range, a pullback to its 50% and an FVG entry (commercial track)

**Registered 2026-11-09, before any outcome of these rules was computed** (Fadi approved this
text: "Approve and run").

**The idea** (Fadi, from a video whose author says it beats ICT, SMC and classic traders). Price
always moves inside a dealing range. A move up is a range from its low L to its high H, with the
equilibrium E = 50%. While price makes new highs without touching E, the range only grows. When
the wick touches E, price is in discount; after a bounce, it comes back down to a confirmation
(an FVG), and that is the buy. The SL is below the 50%, the target is 1:4 in the video and 1:2 for
Fadi.

**Fadi's choices (2026-11-09):** 15m for everything; a wick touch counts as reaching 50%; the
entry is the return to an FVG formed by the bounce after the touch; the SL below the 50%; a
target of 2 R (4 R as in the video kept as a setting).

**Why this is not `GOLD_RETRACE.md`'s FIB50 again:** FIB50 bought the 50% itself. Here the 50% is
only the condition; the entry waits for the bounce and its FVG, and the range grows until the
touch, as the video describes.

Code: `app/research/gold_dr.py`. Reports: `gold_dr_xauusd.md`, `gold_dr_fxpro.md`.

## 1. Data and costs

As `GOLD_SHADOW.md` §1: XAUUSD research store, tune 2012-2021, check 2022 to 2026-01-09 (the
lockbox is not read); FxPro GOLD M1 export for condition 3. Cost: the signal bar's recorded
spread + $0.07 per oz, a round trip; $0.10 slippage on stop exits, reported beside the net. The
range logic runs on closed 15m bars; fills and exits are resolved on M1 bars.

## 2. Rules: DR

Written for a bullish range; a bearish one is the mirror image.

- **Swings:** 15m pivots with k = 2 (as v1), confirmed 2 bars later. ATR = ATR(14, 15m).
- **The range.** L is a confirmed swing low; H is the highest high since L; E = (H + L) / 2.
  - Before the touch, a new high only moves H (the range grows) and E with it.
  - **The touch:** the first bar whose low reaches E. The range then needs H − L ≥ M × ATR at
    that bar, otherwise it is ignored until it grows past that size.
  - After the touch, P is the lowest low since the touch (the pullback's low).
  - **A new high above H after the touch** ends the pullback: P becomes the new L, and a new range
    starts from it.
  - **A trade below L** breaks the range: the state turns bearish, with the old H as the bearish
    range's high and the lowest low since as its low.
- **The confirmation.** After the touch, the first bullish FVG: three 15m bars t − 2, t − 1, t
  with low[t] > high[t − 2], a gap ≥ 0.1 × ATR, and bar t − 1 after the touch.
- **The entry:** a buy limit at the gap's top, low[t], placed at the close of bar t and valid for
  8 15m bars. It is cancelled if price makes a new high above H or trades below P first.
- **The SL (a setting):** LOW = P − 0.1 × ATR; EQ = E − 0.1 × ATR. No trade if the SL is not
  below the entry.
- **The target (a setting):** 2 R or 4 R.
- **Every trade:** cost cap (spread + $0.07) / R ≤ 0.10; exit at the SL (a fill bar that also
  reaches the SL is a full loss), the target, the close of the last M1 bar before 17:00 New York
  (daily break), or 48 15m bars after the fill. One trade at a time. The range logic keeps
  running while a trade is open.

## 3. Grid and choice

| Setting | Values |
| --- | --- |
| Target | 2 R, 4 R |
| SL | LOW, EQ |
| Minimum range M | 1.5, 3 × ATR(14, 15m) |

- That is 8 settings.
- **Choice:** the best mean net R on 2012-2021, among settings with net R > 0, at least 60% of
  the years positive and at least 300 trades. If none qualifies, DR is dropped.

## 4. Decision

As `GOLD_PULLBACK.md` §4 (without its correlation condition):

1. A setting qualifies on 2012-2021.
2. Net R with slippage > 0 on the check, 2022 to 2026-01-09.
3. Net R with slippage > 0 on FxPro, 2016-02 to 2026-11-05.

A pass runs as a shadow on the demo.

**Reported beside the decision, deciding nothing:** results by year and by side; all 8 settings
on both periods; how often a touched range gives an FVG entry, and how often it fills.

## 5. Count

There are 8 settings. They are logged in `docs/phase3/TRIALS.md`, as exploratory looks of the
commercial track.

## 6. Outcome (2026-11-09): dropped, the rules as written are degenerate on gold

`gold_dr_xauusd.md`. **No setting has 300 trades on 2012-2021 (1 or 2 each), so DR is dropped at
condition 1.** This says nothing about the idea itself: the rules as written leave almost no
ranges to trade.

- **Why.** A range resets only when a touched pullback is followed by a new high, or when L
  breaks. In a long trend the price never comes back to 50% of the whole move, so the range keeps
  growing from the same low. Over 2011-12 to 2026-01-09 there are 19 touches of 50% in all: the
  last ones span 1,527 to 1,796 (touched 2012-12-18), then 1,796 down to 1,046, touched only on
  2019-06-24. After that the bullish range from 1,046 never came back to its 50%, so there was
  no signal from mid-2019 to 2026.
- The 15m chart a trader reads sees a local range (the last leg or two). The rules need a bound
  on how far back L may sit before they can be tested; that is a new version and a new
  registration.

## 7. DR2: the range capped by the daily ATR

**Registered 2026-11-09, before any outcome of DR2 was computed** (Fadi chose the cap by the
daily ATR over a 4h range, and approved this text: "Approve and run").

Everything is as DR (§1, §2), with one change and a new grid.

- **The cap.** Before the touch, at each closed 15m bar: if H − L > C × ATR(14, D1) (the last
  closed trading day, 17:00 to 17:00 New York), L moves up to the most recent confirmed 15m swing
  low after the current L, when there is one. E moves with it. The touch then needs the capped
  range. After the touch, the range is fixed as in DR. A bearish range is the mirror image (H
  moves down to the most recent confirmed swing high).
- **The minimum range** is fixed at M = 1.5 × ATR(14, 15m).

| Setting | Values |
| --- | --- |
| Target | 2 R, 4 R |
| SL | LOW, EQ |
| Cap C | 1, 2 × ATR(14, D1) |

- That is 8 settings, chosen and decided as DR (§3, §4).
- They are logged in `docs/phase3/TRIALS.md` as 8 more exploratory looks.

### DR2 outcome (2026-11-09): dropped

`gold_dr2_xauusd.md`. **No setting qualifies on 2012-2021, so DR2 is dropped at condition 1.**

| Setting | 2012-2021 net R (trades, years +) | Check net R with slippage |
| --- | --- | --- |
| 2R LOW C1 | −0.089 (567, 20%) | −0.044 |
| 4R LOW C1 | −0.097 (561, 20%) | −0.027 |
| 2R EQ C1 | −0.079 (185, 30%) | −0.141 |
| 4R EQ C1 | −0.152 (183, 20%) | −0.090 |
| 2R LOW C2 | −0.103 (394, 40%) | +0.083 |
| 4R LOW C2 | −0.052 (394, 50%) | +0.045 |
| 2R EQ C2 | −0.224 (137, 20%) | +0.010 |
| 4R EQ C2 | −0.240 (137, 30%) | +0.071 |

- **The cap works as meant:** 1,700 to 3,260 FVG orders over 2012-2026 (about 120 to 230 a year)
  instead of 9.
- **Gross R is about zero or below on 2012-2021** (−0.18 to +0.004) for every setting.
- **The C2 settings are positive on the check** (+0.01 to +0.08 with slippage, 170 to 347 trades),
  but none was positive on 2012-2021, where the choice is made. Picking one now would be choosing
  on the check.
- **Sells did better than buys in every setting** (whole period, with slippage: sells −0.05 to
  +0.15, buys −0.12 to −0.24). This was not registered and decides nothing.
- 29-58% of the trades end at the time limit (48 15m bars or the daily break), so the 4 R target
  is rarely reached (5-12%).
