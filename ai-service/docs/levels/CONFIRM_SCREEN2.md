# Screen 2: the 15 confirmations and 9 new level sets with the five's engine (registered before any outcome)

**Registered 2026-11-12, before any outcome of these rules was computed.** Fadi pointed out that
screen 1 (`CONFIRM_SCREEN.md`, none passed) used a tight stop and a fixed target, while the five
make their money with a wide stop, no target and a trailing stop (`GOLD_EXIT.md`: a fixed target
cut their gross R by more than half). Fadi: "إي، بلّش بالغربال بمحرّك الخمسة". Same screen period
and bar as screen 1; this is a second look at the same two years and is counted as such.

## The five's engine (frozen, `gold_exam` LVL4H settings)

D = 0.75 x ATR(14, 4h); trades with cost / D > 0.05 skipped; M8 management (at +1 D the stop goes
to entry + cost, then trails the last confirmed 5m swing ∓ 0.1 x ATR(5m)); no target; exit at the
last bar closing by 16:45 New York or after 200 bars; one open trade per book; cost = spread +
$0.07, $0.10 slip on stop exits (`gold_lab.simulate`, "M8").

## Part A: the 15 confirmations of screen 1 with this engine

The base events and the 15 methods exactly as `CONFIRM_SCREEN.md` §2-3 (17 families: 13 real with
projections, 4 round). Only the trade changes: entry at the next 5m open after the confirming bar,
stop = entry ∓ D, M8, no target. Confirming bars opening 02:00-16:00 New York (the five's window).
Books: family x method. Control: the same on 200 shifted copies of the families (seed 20261120).

## Part B: 9 new level sets traded exactly like the five

The five's entry too: a stop order at the level's first touch of the day, 02:00-16:00 New York
(LONDON: 07:00-16:00, when its range is known); D, cost cap, M8 as above (`gold_shadow.level_run`).

1. **PMHL:** the previous calendar month's high and low.
2. **LONDON:** today's 02:00-07:00 New York high and low.
3. **OPENS:** today's open (the first 5m bar of the trading day) and this week's open.
4. **PDC:** the previous day's close.
5. **PIV2:** the previous day's pivot P, R2 and S2.
6. **SWING:** at the day's start, the nearest unbroken (no close beyond by 0.25 x ATR 5m) 1h swing
   high above and swing low below the last close, at most 5 trading days old.
7. **HL3 / HL20:** the high and low of the previous 3 and the previous 20 trading days (two sets).
8. **R100:** the multiples of $100 around the previous day's close.
9. **NYS:** the previous day's New York session (09:30-16:00) high and low.

10 cells (HL3 and HL20 apart). Control: each day's levels moved by u x the previous day's
ATR(14, D1), |u| uniform in [0.25, 0.75] with a random sign, the same u every day, 200 copies
(seed 20261121).

## The screen bar (both parts)

XAUUSD 2024-01-01 to 2026-01-09. Per cell: mean net R with slip, the copies' mean, t of the excess
(4-week block bootstrap). **Passes:** mean net R > 0 and t >= 1.5. Reported with it: trades a day
and (part B) the daily correlation with each of the five. Passing cells go to a separate
registration for the full test (2012-2023, FxPro, the five FX pairs where they apply, Holm; the
correlation condition < +0.2). Nothing else is decided here.

Count: 25 screen cells in `TRIALS.md`. Code: `app/levels/confirm5.py`, `python -m app levels
confirm5`. Report: `confirm_screen2_result.md`.
