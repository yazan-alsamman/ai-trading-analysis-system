# Range exhaustion: are the five's late breaks worse once the day has used its expected move? (registered before any outcome)

**Registered 2026-11-13, before any outcome below was computed.** Claude proposed it after part 1
(`VOL_FORECAST.md`: M3 forecasts the size of the 02:00-16:45 New York window's move); Fadi: "إي،
سجّل أ". The day before, gold broke every daily and weekly level down, and Fadi asked what happens
after everything is broken. The idea: a break that comes after the day has already moved more than
its forecast has less room left.

## 1. The variable (known at the entry)

For a trade entered at 5m bar i on New York day d:

- **range so far** = the highest high minus the lowest low of day d's 5m bars that open at 02:00 New
  York or later and close by the open of bar i (bar i itself is not read);
- **forecast scale** = p02(d) x sqrt(F(d)), with F(d) = M3's level forecast of the window's RV from
  part 1's walk-forward (out of sample: each year fitted on the years before it) and p02 the price
  at 02:00;
- **u = range so far / forecast scale** (scale-free; a day using more of its forecast has a higher
  u).

Trades on days without a part-1 forecast (2012-2017, days dropped by its bar / gap rule) are left
out.

## 2. Trades

The five (LVL4H, PIVOT, PIVW, ASIA, PWHL) exactly as `gold_live.five_trades`, net R with slip.
ROUND is reported, not tested.

## 3. Hypothesis and periods

**Hypothesis X:** trades in the **top tercile of u** have a lower mean net R than the other trades,
and a negative mean (so skipping them would add money).

- **Cut-off:** the 2/3 quantile of u over the five's trades of **2018-2021** on the research store.
- **Test: 2022-01-01 to 2026-01-09** (research store; out of sample for the cut-off and the forecast).
- **Readout on unseen data:** FxPro GOLD 2026-01-12 to 2026-11-05, with M3 fitted on every
  research-store day to 2026-01-09 (as `VOL_PART2.md`) and the same cut-off.

Disclosed before the run: `RISK_SPLIT.md` found that gold's trades entered while others of the five
are open in their direction (often later in a move) did **better**, which points against this
hypothesis; X is registered in the direction that could be used (skipping late breaks), and fails
if gold's late breaks are not worse.

## 4. The test and the pass rule

d = mean net R (top tercile) − mean net R (the rest), on the test period; 95% interval and a
one-sided p (H: d < 0) from a **4-week block bootstrap of trades by entry time** (10,000 resamples,
seed 20261119).

**X passes** if all of:

1. d < 0 with one-sided p < 0.05;
2. the top tercile's mean net R < 0 on the test period;
3. d < 0 on FxPro 2026-01-12 to 2026-11-05.

A pass would lead to a separate registration of the filter (skip a break when u is above the
cut-off) and its EA step (the EA needs the 02:00 forecast). A fail leaves the five as they are.

## 5. Reported with it (decide nothing)

- Mean net R, gross R, win share and stop-exit share by tercile (2018-2021 and the test period),
  overall and per strategy.
- The tercile split within entry-time blocks (02:00-08:00, 08:00-12:00, 12:00-16:00 New York): u
  rises through the day, so this shows whether the time of day drives it.
- The cut-off value, and u's deciles with mean net R.
- ROUND by tercile.

## 6. Bookkeeping

A look at the five's trades: counted in N, logged in `docs/phase3/TRIALS.md`. Code:
`app/research/exhaustion.py`, `python -m app research exhaustion --export <GOLD M1>`, committed
before the run. Report: `docs/vol/exhaustion_result.md`.

## Outcome (2026-11-13): hypothesis X does not pass; no exhaustion

`exhaustion_result.md` (code `b5acef7`). Cut-off u = 0.767. On 2022 to 2026-01-09 the top tercile
made **more**, not less: +0.090 R vs +0.054 (d +0.037, 95% −0.070 to +0.143, p 0.75); FxPro 2026
the same way (+0.092 vs +0.049); 2018-2021 equal (+0.027 vs +0.026). Breaks after the day has used
much of its forecast move do not do worse; if anything gold continues (as `RISK_SPLIT.md` hinted).
Within entry-time blocks the picture is mixed (02:00-08:00 top better; 08:00-16:00 the rest better
on fewer trades) and the u deciles show no ordering: description only. The five stay as they are.

