# Confirmed breaks and rejections: a screen of 15 methods (registered before any outcome)

**Registered 2026-11-12, before any outcome of these rules was computed.** Fadi: not every touch
is a break or a rejection; require a confirmation. Claude proposed 15 confirmation methods from
common price-action practice; Fadi: "جرّب الـ 15 كلهن بالغربال". This is a **screen**: a cheap,
loose filter on the last two years; it decides only which methods go to a full registered test.

## 1. Data, levels, period

- XAUUSD 5m, **2024-01-01 to 2026-01-09** (the research store; the lockbox stays sealed). These two
  years become "used" for these methods: a later full test decides on **2012-2023 and the five FX
  pairs**, never on them.
- Levels: the 13 real families of `SPEC.md` (with the range projections of its addendum 1) and the
  four round-number grids ($10, 25, 50, 100). 17 families.

## 2. Base events (5m, at a bar's close)

- **Break** of a live level L: previous close <= L, close > L + 0.25 x ATR(14, 5m) (down
  mirrored); the farthest broken level counts. Trade with the break.
- **Rejection** of L: the bar trades through L from the previous close's side and closes back on
  that side (resistance: previous close < L, high >= L, close < L); the level nearest the close
  counts. Trade away from L.
- **Target:** the next level of the same family beyond L in the trade's direction.

## 3. The 15 methods

Break (entry at the next 5m open after the confirming bar; stop = the confirming bar's far extreme
∓ 0.1 x ATR unless stated):

- **B1 hold:** the bar after the break also closes beyond L (confirming bar = that one).
- **B2 retest:** within 24 bars after the break, price comes back to within 0.1 x ATR of L without
  a close beyond L by b on the other side; then a close at least 0.25 x ATR beyond L in the break's
  direction. Stop: the retest's extreme ∓ 0.1 x ATR.
- **B3 strong candle:** the break bar's body >= 1 x ATR and it closes in the outer 25% of its range.
- **B4 activity:** the break bar's tick volume >= 1.5 x the mean of the previous 20 bars.
- **B5 squeeze:** in the 12 bars before the break every close is within 1 x ATR of L and their
  range is <= 2 x ATR.
- **B6 second attempt:** earlier the same trading day the level was touched and not closed beyond
  (at least once).
- **B7 with the 1h trend:** EMA(20) vs EMA(50) on the last closed 1h bar agrees with the break.
- **B8 opening hour:** the break bar opens 03:00-04:00 or 09:30-10:30 New York.

Rejection (entry at the next 5m open; stop = beyond the rejection bar's wick ∓ 0.1 x ATR unless
stated):

- **R1 double:** a second rejection of the same level 2-48 bars after a first one, price having
  moved at least 0.5 x ATR away in between. Stop: beyond the farther of the two wicks.
- **R2 pin bar:** the wick through L >= 2 x the body and >= 60% of the bar's range.
- **R3 engulfing:** the rejection bar's body engulfs the previous bar's body, against it.
- **R4 fakeout:** a break of L, then within 1-3 bars a close back on the original side; trade
  against the break. Stop: beyond the fakeout's extreme.
- **R5 divergence:** at a resistance rejection the bar's high is the highest of the last 48 bars
  but RSI(14, 5m) is below its highest of bars i-48..i-3 (support mirrored).
- **R6 exhaustion:** the 12 bars before the rejection moved >= 3 x ATR toward L.
- **R7 with the 1h trend:** the trade's direction agrees with EMA(20) vs EMA(50) on 1h.

Common: signal bars opening 02:00-13:00 New York; target >= 3 x cost; exit at the target, the stop
(a bar reaching both: the stop) or the last bar closing by 16:45 New York; cost = the entry bar's
spread + $0.07, $0.10 slip on stop exits; one open trade per family and method.

## 4. Control and the screen bar

The same rules on 200 shifted copies of every family (grids: by u x step; real families: by
(u - 0.5) x their median spacing; seed 20261119). For each method (17 families pooled): mean net R,
the copies' mean, t of the excess (4-week block bootstrap).

**A method passes the screen** if its mean net R > 0 and its excess over the shifted copies has
t >= 1.5. Passing methods go to a separate registration for the full test (2012-2023, the five FX
pairs, Holm over the methods tested). Nothing else is decided here.

Count: 15 screen cells in `TRIALS.md`. Code: `app/levels/confirm.py`, `python -m app levels
confirm`. Report: `confirm_screen_result.md`.
