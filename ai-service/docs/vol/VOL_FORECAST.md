# Forecasting gold's volatility, part 1: forecast accuracy (registered before any outcome)

**Registered 2026-11-12, before any forecast below was fitted or scored.** Fadi asked whether AI
can forecast where gold goes; the answer from the whole research record is no (direction), but
volatility clusters and scheduled news is known in advance, so its size may be forecastable.
Fadi: "إي، سجّل الجزء 1". Part 1 asks only whether a model forecasts the size of tomorrow's move
better than the ATR the five use today. **No trade is simulated here.** Whether a better forecast
helps the five (D from the forecast, or skipping days too quiet for the cost) is part 2, a
separate registration made only if part 1 passes.

This picks up layer A1 (range) of `docs/strategies/PREREG.md`, which was closed without running
(stage E). It is a new, separate look, not that registration.

## 1. Data

- XAUUSD 5m bars from the research store (`gold_lab.load`, which stops at 2026-01-09; the lockbox
  stays sealed). Days 2012-01-02 to 2026-01-09; earlier bars only as warm-up.
- The MT5 economic calendar (`data/processed/calendar.parquet`, `docs/discovery/calendar_check.md`):
  only the **scheduled time, currency and importance** of each release, all known before the day.
  Actual, forecast and surprise values are never read.
- Nothing else (no dollar index or bond: their early years are junk, `drivers.md`).

## 2. The target

A **day** is a New York weekday. Its **window** is the five's: 5m bars opening at 02:00 New York or
later and closing by 16:45 New York (177 bars).

- **RV** = the sum of the squared 5m log returns (close to close) inside the window, the first
  return taken from the close of the 01:55 bar.
- A day is used only if at least 90% of its window bars exist and no gap inside the window is
  longer than 30 minutes (holidays, short sessions and data holes drop out; the count is reported).
- The forecast target is **log RV**. A second readout, never decisive: the window's high-low range
  in dollars.

## 3. Information and timing

Every forecast is issued at **02:00 New York** of the day, from bars that closed by then and from
the calendar. Features (all computed from closed bars before 02:00):

- `rv1`, `rv5`, `rv22`: log of yesterday's window RV, and of the mean window RV over the previous 5
  and 22 used days (the HAR terms).
- `on`: log of the overnight RV, 16:45 New York of the previous used day to 02:00 New York today
  (squared 5m returns; across a weekend, from Friday 16:45).
- `atr`: log of ATR(14, 4h) at 02:00 (`gold_lab.context`, the value the five use for D).
- News, for releases scheduled inside today's window: `top3` (any of Nonfarm Payrolls, CPI m/m, the
  Fed Interest Rate Decision: `events.TOP3`), `usd_high` (number of other USD importance-3 releases,
  capped at 2), `early` (a USD importance-3 release at 08:30 New York or earlier), `fed` (the Fed
  decision on its own).
- Calendar: weekday dummies (Monday as the base).

The calendar's importance labels are MT5's current ones, not necessarily those of the time; this is
a small look-ahead and is stated in the report.

## 4. The models (all frozen here; no tuning on any test year)

| Model | log RV forecast |
| --- | --- |
| **M0** last | `rv1` |
| **M1** ATR (the incumbent, the primary baseline) | a + b x `atr`, OLS on the train years |
| **M2** HAR | OLS on `rv1`, `rv5`, `rv22`, `on` |
| **M3** HAR + news | M2's terms + `top3`, `fed`, `usd_high` (0/1/2), `early`, weekday dummies, OLS |
| **M4** LightGBM | M3's features + `atr`, squared loss on log RV; num_leaves 7, n_estimators 300, learning_rate 0.03, min_child_samples 50, subsample 0.8 (bagging every iteration), colsample 1.0, seed 20261112, no early stopping |

Each log forecast f is turned into a level forecast F = exp(f + s^2 / 2), with s^2 the variance of
the model's residuals on its train years.

## 5. Evaluation (walk-forward)

- Test years 2018, 2019, ..., 2025 (eight windows); the last also holds 2026-01-02 to 2026-01-09.
  Each model is fitted on every used day from 2012 to the end of the year before the test year
  (expanding). M0 needs no fit.
- **Loss: QLIKE** per day, L = RV / F - log(RV / F) - 1 (robust to noise in RV, Patton 2011).
  Also reported: MSE of log RV and the out-of-sample R^2 of log RV against M1.
- **Primary comparisons:** M2, M3 and M4 each against **M1**: the mean daily QLIKE difference
  (model minus M1) over all test days, its 95% interval and a one-sided p from a **4-week block
  bootstrap** (10,000 resamples, seed 20261113), **Holm over the three**.

## 6. The pass rule (part 1)

A model **beats the ATR** if, all three holding:

1. its mean QLIKE is below M1's with Holm p < 0.05;
2. it is below M1's in at least 6 of the 8 test years;
3. it is below M1's in 2024-07 to 2026-01-09 taken alone (the secondary holdout, disclosed as
   already seen by other research, so this is a consistency check, not fresh evidence).

**Part 1 passes** if at least one of M2, M3, M4 beats the ATR. If several do, the one with the
lowest mean QLIKE over all test days goes to part 2. If none does, part 2 is not registered and
the five keep the ATR.

## 7. Reported with it (decide nothing)

- Per year: QLIKE and R^2 of every model.
- News days (`top3` = 1) against the other days: mean RV, and each model's QLIKE on each group.
- The coefficients of M2 and M3 on the last train window (2012-2024), and M4's feature importance.
- A calibration table: test days in deciles of the forecast, mean forecast vs mean realised RV.
- For the product: the realised window range in dollars against the forecast, as median and
  20th / 80th percentiles per forecast decile (what an "expected range today" message would say).
- The days dropped by the rule in §2, per year.

## Addendum 1 (2026-11-12, while writing the code, before any run)

1. **`atr` is scale-free:** log(ATR(14, 4h) / the close at 02:00). As first written it was the log
   of ATR in dollars, while RV is in log returns; gold's price went from about $1,600 to $4,500, so
   a fixed a + b x log ATR would drift and handicap the baseline unfairly. The five use the dollar
   ATR for D, but their results are in R, so only the relative size matters.
2. Details the text left open: a window return is close to close against the previous 5m bar in
   the store (for the 02:00 bar, the 01:55 bar's close); `on` sums the squared 5m returns of the
   bars closing after 16:45 New York of the previous used day and by 02:00 today; `usd_high` counts
   releases, not release times (NFP, the unemployment rate and earnings at 08:30 count as three);
   the window for news is 02:00-16:45 New York inclusive; a missing-time gap is measured from 01:55
   to 16:45 (the bar opens around the window).
3. Product readout: the window's range is reported in dollars and as a % of the 02:00 price, per
   forecast decile of the model with the lowest mean QLIKE.

## 8. Bookkeeping

Code: `app/research/vol_forecast.py`, `python -m app research vol-forecast`, committed before the
run. Report: `docs/vol/vol_forecast_result.md`. Logged in `docs/phase3/TRIALS.md` as a forecast look:
it simulates no trade and so does not add to N for the Deflated Sharpe of any strategy.
