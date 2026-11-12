# Forecasting gold's volatility, part 2: does the forecast help the five? (registered before any outcome)

**Registered 2026-11-12, before any trade of the variant below was simulated.** Part 1
(`VOL_FORECAST.md`, outcome 2026-11-12) found that M3 (HAR + scheduled USD news + weekday)
forecasts the RV of the 02:00-16:45 New York window better than the ATR the five use (QLIKE 0.105
vs 0.128). Fadi: "Yes, register part 2". This asks one question: **does sizing the five's stop by
that forecast make them more money per day?**

## 1. The idea

The five set their stop distance D from a lagging ATR (LVL4H, PIVW, ASIA, PWHL: 0.75 x ATR(14, 4h);
PIVOT: ATR(14, 1h)). The ATR does not know that today has CPI at 08:30, or that it is a Monday. M3
does. On a day M3 expects to be livelier than the ATR implies, D widens (fewer stop-outs on noise);
on a quieter day it narrows (closer stop, and trades the cost cap allowed less often).

## 2. The variant (one, no free parameter)

For each New York day d with part 1's out-of-sample forecasts:

- ratio(d) = exp((f_M3(d) - f_M1(d)) / 2), clipped to [0.67, 1.5]: M3's forecast window volatility
  over the ATR model's (f = log RV forecasts from part 1's walk-forward fits, so every ratio comes
  from a model fitted on earlier years only). The clip is fixed here, before any trade is read.
- **VOL:** every bar of day d uses D x ratio(d) wherever the five use D: the stop, the +1 D step to
  breakeven + cost in M8, and LVL4H's cost cap (cost / D > 0.05 skipped). Everything else is the
  frozen v1 / shadow code (`gold_live.five_trades`): levels, window 02:00-16:00, M8 trail, 16:45
  exit, horizon, one trade per book, cost = spread + $0.07, $0.10 slip on stop exits.
- **BASE:** the same code with ratio = 1 (the five as they trade now).
- Days without a part-1 forecast (dropped by its bar / gap rule) use ratio = 1 in both.

The unit is R of the trade's own D: risk per trade is a fixed share of equity, so a day's sum of
net R is that day's account return in risk units, comparable between BASE and VOL.

## 3. Data and periods

- **Research store (XAUUSD), 2018-01-02 to 2026-01-09:** the days with part 1's walk-forward
  forecasts. Two segments are reported: **2018-2021** (inside the years the five's settings were
  chosen on) and **2022 to 2026-01-09** (their check period).
- **FxPro GOLD export, 2026-01-12 to 2026-11-05** (`D:/GOLD_M1_201501020000_202611052359.csv`,
  read by `gold_live.fx_lines`, summary bars dropped): **unseen by the volatility model.** M3 and M1
  are fitted once on every used research-store day 2012-01-02 to 2026-01-09; the features are built
  from FxPro's bars and the same calendar. Reported, see §5.

## 4. The test

Per day: S(d) = the sum of net R with slip of the five's trades placed that day, for BASE and VOL
(0 on a day with no trade). Difference x(d) = S_VOL(d) - S_BASE(d), over every day where either has a
trade. Mean of x, its 95% interval and a one-sided p from a **4-week block bootstrap** (10,000
resamples, seed 20261114) on the research store 2018-01-02 to 2026-01-09.

## 5. The pass rule

**VOL passes** if all of:

1. mean x > 0 with one-sided p < 0.05 on 2018-01-02 to 2026-01-09;
2. mean x > 0 in both segments (2018-2021 and 2022 to 2026-01-09);
3. mean net R per trade of VOL >= that of BASE (the gain is not just more trades).

If VOL passes, it goes to the EA **only if** FxPro 2026-01-12 to 2026-11-05 also shows mean x >= 0
(about ten months: too short to prove anything, but a negative reading on unseen data stops the
change). The EA change would then need the forecast at 02:00 New York (the calendar from MT5's
own calendar functions) and its own tester match, a separate step.

If VOL fails, the five keep the ATR, and the forecast is used for the product's "expected range
today" message only.

## 6. Reported with it (decide nothing)

- Per strategy (LVL4H, PIVOT, PIVW, ASIA, PWHL) and for ROUND (the $50 shadow, not in the test):
  trades, mean net R with slip, the day difference, BASE and VOL.
- Per year: x and both sides' totals.
- The ratio's distribution (deciles), and on TOP3 news days against the other days.
- **The five's BASE results by M3 forecast quintile** (trades, mean net R, win share), and by
  ratio quintile: do the five do better on days forecast to be lively? This is description only;
  any filter it suggests needs its own registration.

## 7. Bookkeeping

One look at the five's trades: logged in `docs/phase3/TRIALS.md` and counted in N. Code:
`app/research/vol_part2.py`, `python -m app research vol-part2 --export <GOLD M1>`, committed before
the run. Report: `docs/vol/vol_part2_result.md`.
