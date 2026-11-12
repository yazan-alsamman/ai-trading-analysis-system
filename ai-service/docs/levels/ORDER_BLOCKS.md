# Order blocks as a level family (registered before any outcome)

**Registered 2026-11-12, before any order-block outcome was computed.** Fadi's request ("سجّل
اختبار الأوردر بلوك وجرّبه") after the level-family study (`SPEC.md`) ended negative. Order blocks
were not one of its 24 families; FVG and IFVG were, and matched their shifted copies.

Same machinery, rules and costs as `SPEC.md` (§3-6 with addenda 1-2): events on 5m bars, target
the next level of the same family, stop at the midpoint behind, the 5-hour and 13:00 rules,
entries 02:00-13:00 New York, Raw and Standard costs, 200 shifted copies. Only the family is new.

## 1. The family (an exact reading of the SMC / ICT definition)

On a source frame (15m: family **OB-15**; 1h: **OB-1H**), a **bullish order block** is bar j when:

1. bar j closes below its open (the last down candle);
2. a displacement follows: for some m = 2 or 3, bar j+m closes at least 1.0 x ATR(14, frame) of
   bar j above the high of bar j;
3. that close breaks structure: it is above the last swing high (3 bars each side) confirmed by
   bar j;
4. the displacement leaves a fair value gap: for some q in j+2 .. j+m, low[q] > high[q-2].

The block is known at the close of bar j+m (the first m that meets 2-4). **Its levels:** the
proximal edge (high of bar j) and the distal edge (low of bar j). Bearish blocks mirror it (an up
candle, a displacement down below the last swing low, a downward gap; proximal = low, distal =
high). **Life:** both edges live until a 5m bar closes beyond the distal edge by b (the block is
invalid) or 5 trading days.

Behaviours on these levels, as `SPEC.md` §3: **rejection** (the classic order-block trade: price
returns to an edge and closes on it, trade away from it) and **break**.

## 2. Judging (fixed now)

- Discovery: XAUUSD 2012-2021.
- **Primary (2):** order blocks x {break, rejection}, OB-15 and OB-1H pooled. Gates: mean net R
  (Raw) >= +0.03, > 0 at 2x cost, excess over the 200 shifted copies with a 4-week block bootstrap
  t >= 3, Holm over the 2 at 5% (one-sided).
- **Secondary (4):** each family x behaviour: mean >= +0.05, >= 300 trades, t >= 3, BH 10%, no year
  above half of the total R. Reported.
- Reported with it: orders a day and the smallest effect each primary test can see (as `SPEC.md`
  L0), Standard costs, by year.
- A primary pass goes once to the five FX pairs (2016 / AUDUSD 2018 to 2026-01-09), then the demo.
  No pass: the order-block test ends negative.

Count: 2 primary + 4 secondary cells in `TRIALS.md`. Code: `app/levels/ob.py`,
`python -m app levels ob`. Report: `ob_result.md`.
