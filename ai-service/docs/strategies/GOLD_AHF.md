# Gold: filters on the AH bot's leg exits (X1), then meta-labeling

**Registered 2026-11-09, before any outcome of these rules was computed** (Fadi approved this
text: "موافق، شغّل").

**The idea.** X1 (`GOLD_AHX.md`: AHB's entries with the bot's leg exits) trades about 27 times a
day and has gross R about 0 on 14 years. Fadi's view: the bot loses a little on average because it
takes every signal; some of its signals carry an edge and others give it back. **Question 1: is
there a small set of fixed conditions, chosen on 2012-2017, under which X1's gross R is above 0 on
2018-2021?** Only if it is, **question 2: does a meta-model on the filtered trades raise the net R
further?** Meta-labeling is used to grow an edge that the filter showed, not to create one (Fadi,
2026-11-09).

Code: `app/research/gold_ahf.py`, `python -m app research gold-ahf features|screen|meta|check`.
Reports: `gold_ahf_screen.md`, `gold_ahf_meta.md`, `gold_ahf_check.md`.

## 1. Data, periods and costs

As `GOLD_AHX.md` §1: the XAUUSD research store, M1, read only through `gold_ah.load_store` (stops
before the lockbox).

| Period | Dates | Use |
| --- | --- | --- |
| D, discovery | 2012-01-01 to 2017-12-31 | descriptive tables; the filter is chosen here |
| V, validation | 2018-01-01 to 2021-12-31 | the filter's gate; the meta-model's walk-forward |
| C, check | 2022-01-01 to 2026-01-09 | read once, at the end, if stages 2 and 3 pass |
| F, FxPro GOLD | 2016-02 to 2026-11-05 (its 2022 on reported alone) | condition 3, as `GOLD_AH.md` §4 |

Costs: the signal bar's spread + $0.07 per oz; $0.10 slippage on SL exits, reported beside the net;
a 2x cost run.

## 2. The trades

X1's entries and exits, unchanged (`GOLD_AHX.md` §2: AHB's raw signal, the leg L-H before the
pullback, TP = L + 1.088 R, SL = H − 2.025 R, exit at the 17:00 New York break or after 360 bars).

**One change, for the filter to apply cleanly: every signal is a trade** (no skip while a signal
of the same direction is open). With the skip, removing one signal changes which later signals
trade. The result per trade is the same as in X1. X1 with the skip is reported beside every result,
deciding nothing. Standard errors and p-values come from a **weekly block bootstrap** (2,000 draws,
seed 20261109), because trades overlap.

## 3. The features (50, fixed here)

Computed at the close of the signal bar i from bars up to i only. "Signed" means multiplied by the
trade direction d, so a high value always means "in favour of the trade". ATR_m = ATR(14, M1);
ATR_D = ATR(14, D1) on the 17:00 New York day, from completed days only. "Day" is the trading day
(17:00 to 17:00 New York); "previous day" values come from completed days.

| # | Family | Feature | Definition |
| --- | --- | --- | --- |
| 1 | Time | `hour` | New York hour of bar i (category) |
| 2 | Time | `weekday` | New York weekday of the trading day (category) |
| 3 | Time | `session` | Asia 18:00-02:00, London 02:00-08:00, overlap 08:00-12:00, NY afternoon 12:00-16:50 (category) |
| 4 | Time | `mins_left` | minutes until 17:00 New York |
| 5 | Time | `news_window` | 1 if 08:25-09:05 or 09:55-10:35 New York, else 0 |
| 6 | Volatility | `vol_m1_1d` | ATR_m / mean true range of the last 1,440 bars |
| 7 | Volatility | `vol_1d_20d` | mean TR of the last 1,440 bars / mean TR of the last 28,800 |
| 8 | Volatility | `atr_d_bp` | ATR_D / c × 10,000 |
| 9 | Volatility | `atr_d_pct` | percentile of ATR_D among the previous 250 days |
| 10 | Volatility | `day_used` | (day high − day low so far) / ATR_D |
| 11 | Volatility | `rng10_atr` | range of the last 10 bars / ATR_m |
| 12 | Trend (signed) | `ret10` | (c − c[i−10]) / ATR_m |
| 13 | Trend (signed) | `ret60` | (c − c[i−60]) / ATR_D |
| 14 | Trend (signed) | `ret240` | (c − c[i−240]) / ATR_D |
| 15 | Trend (signed) | `ret1440` | (c − c[i−1440]) / ATR_D |
| 16 | Trend (signed) | `ret_5d` | (c − close of 5 completed days ago) / ATR_D |
| 17 | Trend (signed) | `ema_gap` | (EMA20 − EMA50) / ATR_m |
| 18 | Trend (signed) | `dist_ema50` | (c − EMA50) / ATR_m |
| 19 | Trend (signed) | `htf_ema` | (EMA1200 − EMA3000 on M1 closes, about H1 EMA20/50) / ATR_D |
| 20 | Trend (signed) | `er60` | signed efficiency ratio: (c − c[i−60]) / Σ\|Δc\| over 60 bars |
| 21 | Trend (signed) | `pos_day` | position of c in the day's range so far (1 − pos for a sell) |
| 22 | Trend (signed) | `pos_5d` | position of c in the last 5 completed days' range + today |
| 23 | Trend (signed) | `prev_day_dir` | sign of the previous day's close − open |
| 24 | Pullback | `k5` | %K(5) (1 − %K for a sell) |
| 25 | Pullback | `pos60` | position in the 60-bar range (1 − pos for a sell) |
| 26 | Pullback | `pull_depth` | (H − c) / (H − L) of the leg, mirrored for a sell |
| 27 | Pullback | `pull_bars` | bars from the leg's extreme H to i |
| 28 | Pullback | `ret3` | signed (c − c[i−3]) / ATR_m |
| 29 | Pullback | `sig_body` | signed (c − o) / (h − l) of bar i (0 for a flat bar) |
| 30 | Pullback | `sig_range` | (h − l) of bar i / ATR_m |
| 31 | Leg | `leg_atr` | R / ATR_m |
| 32 | Leg | `leg_d` | R / ATR_D |
| 33 | Leg | `leg_bars` | bars from L to H |
| 34 | Leg | `leg_speed` | R / leg_bars / ATR_m |
| 35 | Leg | `rw_p` | random-walk win rate SL / (SL + TP) of this trade |
| 36 | Leg | `sl_atr` | SL distance / ATR_m |
| 37 | Leg | `leg_try` | which pivot (1-10) the leg finder used |
| 38 | Levels | `room_tp` | distance in the trade's direction to the nearest of PDH, PDL, 5-day high and low, P, R1, S1 (the v1 levels), in TP distances, capped at 5 |
| 39 | Levels | `room_sl` | the same against the trade's direction, in SL distances, capped at 5 |
| 40 | Levels | `pd_pos` | signed position of c in the previous day's range ((c − PDL) / (PDH − PDL), 1 − that for a sell), may be < 0 or > 1 |
| 41 | Levels | `round_dist` | distance to the nearest multiple of $10 / ATR_m |
| 42 | Levels | `gap_open` | signed (day open − previous day close) / ATR_D |
| 43 | Activity | `tv_ratio` | tick volume of bar i / mean of the last 60 |
| 44 | Activity | `tv_1d` | mean tick volume of the last 10 bars / mean of the last 1,440 |
| 45 | Activity | `spread_rel` | spread of bar i / median spread of the last 1,440 bars |
| 46 | Activity | `sig_same_60` | raw signals in the same direction in the last 60 bars |
| 47 | Activity | `sig_opp_60` | raw signals in the opposite direction in the last 60 bars |
| 48 | Cost | `cost_r` | (spread + $0.07) / SL distance |
| 49 | Recent | `last20_all` | mean gross R of the last 20 trades (all directions) closed before bar i |
| 50 | Recent | `last20_same` | the same for trades in the same direction |

A feature that cannot be computed (warm-up, a flat range) is missing; the filter never keeps a
missing value, the models use their own handling (LR: median of the train window plus a missing
flag; LightGBM: native).

## 4. Stage 1: descriptive tables (D only; decide nothing)

For every feature, on D: quintiles at D's own edges (categories by level), with trades, gross R
(SE), TP rate minus the random-walk rate (the edge before costs), net R. Beside it the Spearman
correlation of the feature with gross R on D. **V is not read in stage 1.**

## 5. Stage 2: the gross filter (chosen on D by a fixed procedure, judged on V)

**Candidate conditions per feature,** from D's quintile edges q20, q40, q60, q80:
x ≤ q20, x ≤ q40, x ≤ q60, x ≥ q40, x ≥ q60, x ≥ q80 (6 per numeric feature). For a category: keep
the levels whose D gross R is above 0 with at least 1% of D trades (1 per categorical feature).

**Greedy selection on D, score = t of the gross R** (mean / week-clustered SE, the ratio
estimator over weeks):

1. Pick the condition with the highest t that keeps at least 20% of D's trades.
2. Add a second and then a third condition (on the trades already kept) only if it raises t and
   the set keeps at least 10% of D's trades.
3. At most 3 conditions; at most one per feature.

**The selection-bias control (D):** the whole greedy procedure (the categorical keep sets
included) is rerun 50 times with the gross R circularly shifted in time by a random 10-90% of
the trades (seed 20261109), so features and outcomes lose their link while the outcomes' serial
structure stays. The 95th percentile of those 50 best t values is the bar.

**Gate of stage 2 (all must hold):**

1. On D, the chosen filter's t is above the 95th percentile of the shuffled selections.
2. On V, the filtered trades' gross R > 0, one-sided weekly block bootstrap p < 0.05.
3. On V, gross R > 0 in at least 3 of the 4 years.

If the gate fails, the study stops: stage 3 does not run, C is not read (Fadi's condition above).
Reported beside, deciding nothing: net R, net R with slippage and the 2x cost run on D and V; trades
a day; X1 with the skip.

## 6. Stage 3: meta-labeling on the filtered trades (only if stage 2 passes)

- **Trades:** those that pass the frozen filter.
- **Label:** y = 1 if net R > 0, weight |net R| (as `docs/phase4/PREREG_P4.md`).
- **Features:** all 50.
- **Walk-forward:** 8 six-month test windows, 2018-01 to 2021-12. Train expanding from 2012-01,
  keeping only trades that exit before the window starts, plus a 1-day embargo. The model is fit
  (weighted) on the first 75% of the train window by time; Platt calibration on the last 25%,
  **unweighted**, so p estimates P(net R > 0) and the EV rule below is an expectation.
- **Models (fixed):** LR, L2, C from `meta.C_GRID` by 3 time-ordered inner folds (log loss);
  LightGBM with `meta.LGBM_PARAMS`, 200 rounds.
- **Accept** a trade if p × m1 + (1 − p) × m0 > 0, m1 and m0 the mean net R of the train window's
  winners and losers.
- **Control:** 20 random acceptances at each window's acceptance rate (seeds 1-20).

**Gate of stage 3, per model, on V's walk-forward (all must hold):**

1. Accepted trades' net R > 0, with at least 30 accepted per window on average.
2. Accepted net R above the filtered set's net R (the meta-model adds something).
3. Accepted net R above the 95th percentile of the 20 random controls.
4. Brier skill > 0 against the train base rate.

If both models pass, LR is the one carried forward (the simpler one); if only one passes, that one.
If none passes, the filter alone is carried forward, if its own net R with slippage on V is > 0;
otherwise the study stops.

## 7. Stage 4: the check (once)

The carried-forward rule (filter, or filter + the model trained on 2012-2021 with its calibration
slice) runs once on C and on F's 2022-02 to 2026-11-05. **Decision for the demo as a shadow
strategy:** net R with slippage > 0 on C and > 0 on F 2022 on. Reported beside: gross, net by year,
by side, trades a day, the 2x cost run, the bot's weeks (2026-10-14 to 2026-11-05) on F.

**Each stage runs once.** The command keeps its state in `gold_ahf_state.json` and refuses a
second run of a stage, stage 3 without a passed stage 2, and stage 4 without a carried rule or
without the FxPro export.

## 8. Count

One exploratory look of the commercial track in `docs/phase3/TRIALS.md` (stages 1-4 together).
The 300 candidate conditions and the 50 shuffled selections are disclosed with it.

## 9. Outcome (2026-11-09): stage 2 not passed; the study stops

`gold_ahf_screen.md` (code at `0b3f60a` plus this study's uncommitted files). Stage 3 and stage 4
did not run; C was not read.

| Set | Trades | Gross R | Cost R | Net R (slip) |
| --- | --- | --- | --- | --- |
| D, all | 110,811 (72 a day) | −0.028 | 0.282 | −0.310 (−0.328) |
| D, filter | 12,013 | +0.004 | 0.315 | −0.311 (−0.331) |
| V, all | 73,875 | −0.004 | 0.151 | −0.156 (−0.172) |
| V, filter | 8,315 | +0.010 (95% −0.007 to +0.028, p 0.128) | 0.169 | −0.159 (−0.175) |

- **The filter chosen on D:** `gap_open` ≤ −0.041 (the day opened against the trade),
  `ema_gap` ≤ 1.11 (a weak M1 trend), `news_window` = 0.
- **Gate:** 1 met (D t 0.51 against a shuffled 95th percentile of −0.51), 2 not met (p 0.128),
  3 met (V gross positive in 4 of 4 years, +0.002 to +0.027).
- **No quintile of any of the 47 numeric features, and no hour, weekday or session, has gross R
  above 0 on D.** The best cells are about −0.006 to −0.010.
- The clearest monotone link is the leg's size (`leg_atr`, `sl_atr`, `leg_d`, `rng10_atr`; ρ −0.11
  to −0.28 with gross R): bigger legs lose less before costs (Q5 −0.010 to −0.017 against Q1 −0.045)
  and carry less cost per R. `rw_p` and `pull_depth` (ρ ∓0.35) mostly restate the TP / SL shape.
- **The costs are the problem, not the filter.** Even the filter's +0.010 gross on V is a
  fifteenth of the 0.15-0.17 R cost; no feature moves gross R by more than about 0.04 R between its
  quintiles.
- Gate 1's null keeps the outcomes' negative mean (the shifted runs' best t has median −1.38), so
  "met" says the features rank trades a little better than chance, not that an edge exists.
- Report note: discrete features (`news_window`, `prev_day_dir`, `leg_try`, `sig_opp_60`) show
  empty quintiles in the stage-1 table because their quintile edges tie; their candidate conditions
  were still built from those edges.
- The first run printed nothing (a cp1252 console could not print "−") after writing the report
  and the state; the console is now set to UTF-8. Nothing was rerun.

## 10. Disclosure

The base rules come from the bot's trades (`GOLD_AH.md`, disclosure). X1 has already been read on
D, V and C (gross about 0 everywhere, `gold_ahx_xauusd.md`); this study reads the same trades split
by features. The stage-2 control is there because the filter is searched on D.

## 11. Amendment 1 (2026-11-09, after the stage-2 outcome): stage 3 on every X1 trade

**Written after stage 2 was read and did not pass** (§9). Fadi chose to run the meta-model anyway
("وافقت. خلينا على كل الصفقات والموديل يتعلم"): if no fixed filter makes gross R positive, can a
model trained on all 50 features find the trades whose net R is positive?

- **Base:** every X1 trade, no filter. The stage-2 filter is not used: its +0.010 gross on V was
  not distinguishable from 0 and it dropped 90% of the trades; the model can learn its conditions
  if they are real.
- **Everything else as written:** §6 (label, features, walk-forward, models, EV rule, random
  controls) and its gate, unchanged; the carry rule of §6 applies with "the filter alone" read as
  "every trade" (V net R with slippage −0.172, so it cannot be carried); §7 (the check, once) only if
  a model passes.
- **Disclosure:** stage 3 now runs on a base whose gross R is about 0 (−0.004 on V), against the
  original condition. The study counts as one exploratory look with stage 2; this amendment is
  disclosed beside it in `docs/phase3/TRIALS.md`.

Command: `python -m app research gold-ahf meta --amendment 1` (refuses unless stage 2 ran and did
not pass; runs once).

### Outcome of Amendment 1 (2026-11-09): neither model passes; the study stops

`gold_ahf_meta.md`. Walk-forward 2018-2021, 73,875 base trades (gross −0.004, net −0.156, slip
−0.172).

| Model | Accepted | Net R acc. (slip) | Gain vs base | Random 95th | BSS | Gate |
| --- | --- | --- | --- | --- | --- | --- |
| LR | 8,320 (11%) | −0.067 (−0.079) | +0.089 | −0.117 | +0.145 | not met (net < 0) |
| LightGBM | 2,550 (3%) | −0.056 (−0.064) | +0.099 | −0.153 | +0.156 | not met (net < 0) |

- Both models meet conditions 2-4 (they beat the base and the random controls, Brier skill
  +0.15) and fail condition 1: the accepted trades still lose after costs. Nothing is carried
  forward; C and F were not read.
- **The models learned the cost, not an edge.** The accepted trades' gross R, weighted over the
  windows, is about +0.003 (LR) and −0.001 (LightGBM): the same as the base. The gain of +0.09 to
  +0.10 R is the cost per R falling from about 0.15 to about 0.06, by picking trades with large
  legs and low spread. The high Brier skill has the same source: a trade whose cost is a large
  share of its SL almost never ends with net R > 0, and `cost_r` is a feature.
- LightGBM accepts nothing in 2021; LR's best window (2021-07) is +0.002 on 228 trades.
- With stage 1 (no cell with gross R > 0 on 2012-2017), this closes the AH line: the bot's
  geometry has no edge before costs on 14 years, no fixed filter and no model on 50 features finds
  one, and a model can only lower the cost share.
