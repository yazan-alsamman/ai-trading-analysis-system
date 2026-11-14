# Final report: rule-based signals, trade management and AI, 2026-10-21 to 2026-10-31

Written 2026-11-03 for the team and the thesis. It summarises the registered research from the
first rule set (L1) to the single holdout reading. Every number here is copied from a committed
report (section 10 lists the files), except the per-strategy gross figures of section 6.3, which
come from an uncommitted exploratory script and are labelled so. Nothing in this report is a new
result, and nothing here was computed on the lockbox (2026-01-10 onward), which stays sealed
until P9.

## 1. The answer first

| Question | Answer | Evidence |
| --- | --- | --- |
| H1: do the SMC rules (L1) beat matched random entries after costs? | **No.** | P3, P4 walk-forward: E1 -0.047 R a trade; p 0.36 on the development period |
| H2: does a meta-model on top of L1 improve net R? | **No.** Every model had negative Brier skill. | P4, trials 7-10 |
| Do any of eight published intraday, scalp or swing strategies have a net edge (families A and B)? | **No.** All eight are **unvalidated**. | Stage C, trials 11-18 |
| Does trade management beat a fixed TP and SL (family C)? | **For scalps, yes, slightly:** M8 adds +0.015 R a trade (holdout +0.010). The trades stay negative after it. Intraday and swing: not shown. | Stage D, trials 19-21; holdout |
| Do AI layers (range, regime, exits, direction) help (family D)? | **Not tested.** Stage E was closed, because no strategy had a net edge for a model to build on. | `PREREG.md`, the Stage E row |
| The best post-hoc combination, S1 + M8? | **Not consistent on the holdout**: -0.077 R a trade net, -0.012 R before costs. | Addendum 1, trial 26 |

In one sentence: **no entry rule tested here has an edge after costs on six instruments from 2018
to 2026-01. One management rule (M8, for scalps) reduces the loss slightly and consistently.**
The service can serve these signals only as "no proven edge".

These are negative results, but not empty ones. The design was fixed before any outcome was
seen. For most strategies it had the power to find edges of about 0.05-0.09 R a trade, which is the
size that would matter after costs. So the null is informative: an edge larger than that is unlikely for
these rules.

## 2. Setting

- **Instruments:** XAUUSD, EURUSD, GBPUSD, USDJPY, USDCAD and AUDUSD.
  - FX from 2016; AUDUSD from 2018; gold from 2012.
  - Data: MT5 bars from the FxPro account, through `HistoryExport` only.
- **Frames:** 5m, 15m, 1h, 4h and D1, all built from closed bars.
- **Costs:** the recorded spread is the only measured cost.
  - Assumed on top: an extra term and SL slippage. On gold in 2024 H1 these make up about 60% of
    the modelled cost.
  - Every result is also reported at twice the costs.
- **Swap:** there is no historical swap data. Swap uses one dated FxPro snapshot (2026-10-28, Raw
  account, not swap-free), applied as estimated scenarios (W0, W1, W3 and the decision scenario).
  Only swing trades and L1 can cross a rollover.
- **Unit:** R, the profit or loss divided by the initial risk (entry to SL). "Net R" includes costs,
  SL slippage and swap.
- **The service is advisory only.** It gives signals and management alerts, and never places an
  order.

### Periods

| Role | Period | Use |
| --- | --- | --- |
| Development (P3) | 2012 to 2017 | L1 rules, E1 against E0 |
| Primary (walk-forward test windows) | 2018-01-01 to 2024-07-01 | every decision in P4, Stage C and Stage D |
| Holdout | 2024-07-01 to 2026-01-10 | read once, on 2026-10-31; consistency checks only |
| Lockbox | 2026-01-10 to the export date | sealed until P9; never read |
| Forward paper log | from the day signals are served | the only data nobody has seen |

## 3. How the research was protected against fooling itself

1. **Pre-registration.**
   - The rules, parameters, statistics, seeds, periods and decision rules were written down
     before any outcome was computed.
   - The rules were frozen at commit `b9ca2a8` (tag `strategies-rules-v1`, 2026-10-29).
   - The plan was approved on 2026-10-30, before any R was computed (`PREREG.md`).
   - Guards in the code refuse to run an evaluation if the rule files changed since the freeze.
2. **Matched random entries (E0).** Each trade is compared with 200 random trades with the same:
   - instrument, year and New York hour;
   - entry frame;
   - risk in ATR units and TP rule;
   - cost filter and costs.

   The direction is a fair coin. This separates "the rule picks good moments" (d = x - e) from
   "the market drifted" or "the costs are low".
3. **Tests that respect dependence.**
   - Calendar 4-week blocks, with a block bootstrap (B = 20,000).
   - Two tests per component (percentile and t), on both x (net R) and d (net R against E0).
     The p-value is the largest of the four.
   - Method condition: at least 30 blocks.
4. **Multiple testing.**
   - Holm within each family: A (6 strategies), B (2), C (3 types) and D (4 models).
   - The Deflated Sharpe ratio is reported with N = 26 trials.
   - Every trial that looked at performance is logged in `docs/phase3/TRIALS.md`.
5. **Walk-forward.** Model and bundle choices are made only on training data known before each
   six-month test window, with a 1-day embargo.
6. **Read-once holdout, sealed lockbox.**
   - The holdout was read once, after every Stage C and D report was committed (hash recorded).
   - The lockbox is kept for P9.
7. **No loosening after a failure.** No rule was changed, relaxed or added because of a count or a
   result. Signal frequency was never a target.

## 4. Path of the research

| Phase | Dates | What was asked | Result |
| --- | --- | --- | --- |
| P2 | before P3 | detect SMC patterns (liquidity sweep, change of character, fair value gap) | patterns built and reviewed (V5-S); data-quality reports per instrument |
| P3 | 2026-10-22 to 23 | H1: L1 (sweep, then CHoCH, market entry, 48-bar horizon) against E0 | **H1 not supported**: E1 -0.046 against E0 -0.063 (p 0.36). Horizons 96 and 192, and L1-M management, did not change that (trials 3-6) |
| P4 | 2026-10-23 to 25 | H2: meta-model (logistic regression, LightGBM, MLP) to filter L1 trades | **H2 not supported**: the primary model's accepted trades -0.054 against -0.047 for all. Brier skill was negative for every model (trials 7-10). L1 on the walk-forward windows: 1,058 trades, -0.047 R (95% -0.115 to +0.020) |
| P6 | from 2026-10-25 | live scanner, lifecycle, exposure | taken before P5, because it does not need a model (`docs/phase6/`) |
| Strategy plan A | 2026-10-25 to 28 | one engine for 8 strategies and 9 management bundles, live = backtest | merged (PR #77), with the MT5 swap snapshot |
| B | 2026-10-29 to 30 | counts, frozen rules, approval | rules frozen 2026-10-29; PREREG approved 2026-10-30 |
| C | 2026-10-31 | families A and B: eight strategies under fixed TP and SL (M0) | **all unvalidated** |
| D | 2026-10-31 | family C: walk-forward choice of management bundle against M0 | **scalp passed (M8)**; intraday and swing not activated |
| Addendum 1 | 2026-10-31 | S1 + M8, chosen post hoc, registered before the holdout | trial 26 |
| E | 2026-10-31 | family D: AI layers | **closed without running** (decision by Fadi) |
| Holdout | 2026-10-31 | the single reading | scalp M8 consistent, so activated; S1 + M8 not consistent |

## 5. The strategies (frozen at `b9ca2a8`)

Every parameter was taken from published or common versions, **not tuned on any data**.

| Strategy | Type, frame | Idea | Prior |
| --- | --- | --- | --- |
| S1 LB | intraday, 15m | London breakout of the Asian range | common practice |
| S2 MR | intraday, 1h | Bollinger mean reversion when ADX < 20 | common practice |
| S3 TF | swing, 4h | 55-bar Donchian trend breakout | time-series momentum (Moskowitz, Ooi, Pedersen 2012) |
| S4 ORB | scalp, 5m | New York opening-range breakout (08:30-08:59) | Zarattini, Aziz (2023) |
| S5 PB | scalp, 5m | pullback to EMA(20) in a 1h trend | common practice |
| S6 VR | scalp, 5m | reversion to the session VWAP bands in a range | common practice |
| S7 SQ (B) | intraday, 15m | Bollinger-in-Keltner squeeze breakout | practitioner pattern |
| S8 FX (B) | scalp, 5m | reversal after the London gold and FX fixes | Melvin, Prins (2015); Evans (2018); Caminschi, Heaney (2014) |

Management bundles: M0 (fixed TP and SL) up to M8 (break-even at +1 R, then a trail to the last
swing low, with no fixed TP). The rules T1-T4 and L1-L5 are listed in `PREREG.md`, section 7.

## 6. Results

### 6.1 Stage C: strategies under M0 (primary period 2018-01 to 2024-06)

x is the mean net R a trade. d is x minus its matched E0. A strategy passes only if both x and d
are reliably above zero.

| Trial | Strategy | n | Mean x | Mean d | At 2x costs | Holm p | Result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | S1 | 3,735 | -0.014 | **+0.038** | -0.060 | 1.000 | unvalidated |
| 12 | S2 | 3,421 | -0.082 | -0.027 | -0.129 | 1.000 | unvalidated |
| 13 | S3 | 1,271 | -0.128 | -0.031 | -0.151 | 1.000 | unvalidated |
| 14 | S4 | 4,458 | -0.055 | +0.003 | -0.120 | 1.000 | unvalidated |
| 15 | S5 | 38,970 | -0.087 | -0.017 | -0.158 | 1.000 | unvalidated |
| 16 | S6 | 5,845 | -0.099 | -0.036 | -0.161 | 1.000 | unvalidated |
| 17 | S7 | 2,906 | -0.067 | -0.004 | -0.132 | 1.000 | unvalidated |
| 18 | S8 | 1,264 | -0.045 | +0.013 | -0.103 | 1.000 | unvalidated |

- **Every strategy loses after costs**, and every one loses more at twice the costs.
- **"Unvalidated" is stronger than "inconclusive".** It means the upper bound U_S of the edge is
  below the smallest edge worth having (delta*, 0.05 R). For six strategies that bound is below zero.
  For S1 it is +0.019, and for S8 +0.007.
- **S1 is the only strategy that times the market better than chance.**
  - d = +0.038 R, with 95% interval +0.001 to +0.075.
  - Its random twins lose -0.051 R, and S1 loses only -0.014 R.
  - The timing edge is smaller than the costs, so S1 still loses money.
  - S1's d stays between +0.030 and +0.040 across the sensitivities (gold from 2012, all
    instruments from 2012, without EURUSD 2021-2023, without first-Friday news bars). Its p_S stays
    at 0.74-0.78 with blocks of 1, 2 and 8 weeks.
- **Power** (`counts_post.md`, the smallest edge found 80% of the time, without and with the
  Holm level). S5: 0.019-0.024 R. S1, S2, S4 and S6: 0.047-0.089 R. S7: 0.078-0.088 R. S8 and S3
  have fewer trades or more variance: 0.113-0.127 R and 0.145-0.189 R.

### 6.2 Stage D: management against M0 (same entries, walk-forward)

Within each six-month window, the bundle that did best on earlier trades (known by the window
start) manages the window's trades. That result is compared with M0 on the same entries.

| Trial | Type | Test trades | Mean delta (95%) | Holm p | Result | Bundle chosen in the last windows |
| --- | --- | --- | --- | --- | --- | --- |
| 19 | scalp | 50,537 | **+0.015** (+0.005 to +0.026) | 0.007 | **passed** | M8 (10 of 13 windows) |
| 20 | intraday | 10,062 | +0.012 (-0.005 to +0.029) | 0.123 | not activated | M8 |
| 21 | swing | 1,271 | +0.063 (-0.015 to +0.142) | 0.123 | not activated | M7 |

- Scalp management helps, but **it does not turn the scalps profitable**. On the same entries, M0
  makes -0.085 R a trade and M8 makes -0.069.
- M8 moves the SL to break-even at +1 R, then trails it to the last swing low, with no fixed TP.
  The report does not split the gain by exit reason.
- Swing has the largest point estimate, but only about 100 trades a window, so the interval
  includes zero.

### 6.3 Exploratory, after Stages C and D (not evidence)

This analysis was asked for after the results. It is reported so that it is not hidden, and it
decides nothing. The scripts were not committed. Addendum 1 records the S1 + M8 figures; the
per-strategy gross figures below are from the same scripts.

- **Before costs** (gross R), only S1 (+0.033), S4 (+0.011) and S8 (+0.012) are above zero under
  M0. The other five lose even with no costs.
- **All 72 strategy-bundle pairs.** Every strategy S1-S8 was paired with every bundle M0-M8, on
  M0's entries.
  - S1 + M8 had the best gross mean, +0.054 R.
  - It was the only pair with a positive net mean: +0.005 R, n = 3,735.
  - The best of 72 tries is expected to be about +0.05 R above zero even when nothing works. So
    this was registered as a new hypothesis (Addendum 1, trial 26), with its own power statement,
    before the holdout was read.

**Costs decide the outcome.** For these rules, the modelled costs (about 0.05-0.07 R a trade on
average) are larger than any timing edge found.

### 6.4 The holdout (2024-07-01 to 2026-01-10, read once on 2026-10-31)

The holdout has about 20 four-week blocks. That is below the method condition, so it gives a
consistency check, not a test.

| Check | Holdout result | Decision |
| --- | --- | --- |
| Families A and B | no strategy passed Stage C | no check; every status stays unvalidated |
| Family C, scalp (M8 against M0) | n 8,057, 21 blocks, mean delta **+0.010** | **consistent: M8 activated for scalps** |
| Addendum 1, S1 + M8 | n 903; net **-0.077** (M0 -0.079; delta +0.002); gross -0.012; at 2x costs -0.142 | **not consistent** |

- S1 + M8 by instrument on the holdout:
  - only XAUUSD is above zero (+0.013, n 191);
  - AUDUSD is the worst (-0.280, n 143).
- By month, S1 + M8 is above zero in 5 of 19 months.
- The power statement made before the reading said a true edge of +0.005 R would show a positive
  holdout mean only 54% of the time. So the holdout alone does not rule out a tiny edge, but it
  gives no support for one.

## 7. What it means

1. **The market is hard to beat with these rules at retail costs.**
   - Twelve entry configurations were tested: L1 at three horizons, L1-M, and S1-S8.
   - All of them use published or common parameters, on six liquid instruments over 6.5 years.
   - None has a net edge. The one with real timing skill (S1) gives it back in costs.
2. **Machine learning did not rescue a rule without an edge** (P4). With about 630 positive
   examples and 38 features, the models had no stable signal. In 9 of 13 windows the primary
   model's regularisation shrank every coefficient to zero.
3. **Management is the one layer that helped**, for scalps only:
   - +0.015 R on the primary period and +0.010 R on the holdout;
   - small, consistent, and not enough to make the trades profitable.
4. **The method worked as intended.**
   - The best-looking post-hoc combination (S1 + M8, +0.005 R) did not survive data it had not
     seen.
   - Without the pre-registration and the holdout, it could have been served as a "strategy that
     works".
5. **What would be needed for a profitable signal**, from these numbers:
   - a timing edge above about 0.07 R before costs on 5m and 15m entries; or
   - much lower costs, for example institutional spreads; or
   - longer holding periods, where costs per R are smaller.

   S3 (4h, swing) has the lowest costs per R, and it still had no timing edge.

## 8. What the service serves now

- **All eight strategies:** status `unvalidated`, shown as **"no proven edge"**, with their
  primary-period statistics.
- **L1:** served under the intraday label for display; it keeps its P3 / P4 result (H1 not
  supported) and no proven edge.
- **Management:** M8 alerts for scalp trades (break-even at +1 R, then a structure trail),
  activated by Stage D and the holdout. Intraday and swing use M0 (fixed TP and SL).
- **AI layers:** none. Stage E was not run. `probability`, `ev_r` and `grade` stay null.
- **S1 + M8:** will run in the forward paper log from the day signals are served (Addendum 1,
  section 6). It is judged once, at 30
  four-week blocks (about 2.3 years).
  - At that look the test can only find an edge of about 0.1 R or more.
  - The most likely outcome, stated in advance, is "inconclusive".

## 9. Limitations

1. **Costs are partly assumed.** About 60% of the modelled cost on gold is an assumption.
   EURUSD's recorded spread is zero on most bars of 2021-2023, which favours the rules. The null
   results hold either way, and every strategy is worse at twice the costs.
   - **Checked afterwards in the MT5 Strategy Tester** (`mt5_cost_check.md`, 2026-11-03,
     descriptive). 2,776 Stage C trades of 2024 H1 were replayed with FxPro's contract specs and
     commission.
   - Correction (2026-11-05): the replay was not on real ticks. The tester log says "no real
     ticks, every tick generation used", because the FxPro server keeps real ticks only from
     about 2026-01. So the spread is the M1 bar's spread, not the spread at the fill.
   - Overall the real cost was 0.082 R a trade against 0.074 R modelled, and the mean net R
     -0.109 against -0.102.
   - The model overstates the cost on gold and the four other pairs (0.050 R real against
     0.084 R modelled).
   - It understates the cost on EURUSD (0.140 R against 0.055 R). There, 52% of the 2024 trades
     have a recorded spread of zero, and the commission alone is 0.11 R on stops of about 7 pips.
   - The tester fills stops at their level, so slippage is not checked. No conclusion changes.
2. **Swap is a scenario,** not history: one snapshot of rates applied to every year. Only S3 and
   L1 are affected.
3. **Error control is per family.** Across the four families, the chance of at least one false
   pass can approach about 0.2. The one pass (scalp management) has a Holm p of 0.007, and it was
   consistent on the holdout.
4. **The block bootstrap is approximate.** Blocks are treated as independent; dependence over
   multi-month regimes and across instruments is ignored.
5. **The holdout is weak** (about 20 blocks). P9 (the lockbox plus the paper log) is the stronger
   check.
6. **Families C and D use a fixed entry set**, which approximates the served system. The overlaps
   and entry-set differences are reported in `management.md`.
7. **Data.**
   - VWAP is weighted by tick volume.
   - There is no historical news calendar; results are also reported without first-Friday bars.
   - Four pairs were on corrected clocks until 2022.
8. **Prior exposure.**
   - The team had seen L1 and P4 results on the primary period before the strategy plan.
   - No outcome of S1-S8 was seen before approval.
   - The exploratory 72-pair analysis came after Stage D and is disclosed as trial 26.
9. **Scope.** Six instruments, retail costs, one broker's data. The results say nothing about
   other markets, other cost levels, or discretionary trading.

## 9b. After the registered plan (2026-11-03 and 04)

- **MT5 cost check** (`mt5_cost_check.md`): see limitation 1.
- **Exploratory looks on data already seen** (`TRIALS.md`; none of them decides anything):
  - Gold, re-costed with the MT5 costs: -0.049 R a trade over 2018 to 2024-06.
  - The scalp signals carry no positive directional information at 5 to 120 minutes, and drift
    slightly against the signal in the first 30 minutes.
  - Fixed small SL and TP variants did the same as coin-flip entries.
  - Fadi's support and resistance reading: real levels were broken more often than placebo levels,
    not bounced from (-3.9 points).
- **Addendum 2 (trial 27, registered before the data were read)** tested the level effect on six
  instruments never used before: NZDUSD, USDCHF, EURJPY, GBPJPY, EURGBP and XAGUSD.
  - **The mechanism was confirmed out of sample:** -1.0 point (-1.8 to -0.2), p 0.010, and all six
    instruments below placebo. It is the only effect in this research that held on new data. It is
    about a quarter of its exploratory size.
  - **The trade test was stopped after two instruments and is not judged.** Both lost clearly:
    -0.154 and -0.124 R a trade. Both runs turned out to use ticks generated from M1 bars,
    because the FxPro server keeps real ticks only from about 2026-01 (correction, 2026-11-05).
  - So the level effect is real but much smaller than the cost of trading it at this distance.
- **The XAUUSD lockbox file was opened on 2026-11-05**, once, for the exam of the commercial gold
  combination (`GOLD_LOCKBOX_EXAM.md`, outside the registered plan).
  - The other five lockbox files stay sealed.
  - The XAUUSD lockbox is no longer unseen data for any later gold research.
  - The result passed: +0.052 R a trade on real ticks (SE 0.071), as recorded in `gold_exam.md`.

## 10. Sources

| Topic | File |
| --- | --- |
| Registered plan, rules, tests, statuses | `docs/strategies/PREREG.md` |
| Engine and choices fixed in code | `docs/strategies/STAGE_A.md` |
| Stage plan and progress | `docs/strategies/PLAN.md` |
| Pre-approval counts | `docs/strategies/counts.md`, `counts_by_year.csv` |
| Post-approval counts and power | `docs/strategies/counts_post.md` |
| Stage C summary and per strategy | `docs/strategies/evaluation.md`, `eval_S1.md` to `eval_S8.md` |
| Stage D | `docs/strategies/management.md` |
| Addendum 1 (S1 + M8) and the exploratory analysis | `docs/strategies/ADDENDUM_1_S1_M8.md` |
| Holdout | `docs/strategies/holdout.md` |
| Every trial (1-26) | `docs/phase3/TRIALS.md` |
| H1 (P3) | `docs/phase3/baselines.md`, `baselines_h96.md`, `baselines_h192.md`, `docs/phase4/L1-M.md` |
| H2 (P4) | `docs/phase4/PREREG_P4.md`, `CLOSEOUT_P4.md`, `meta_*.md`, `walkforward_L1.md` |
| Data quality | `docs/data_quality/` |

## 11. What remains

| Item | Owner | Status |
| --- | --- | --- |
| Stage F: contract fields (`type`, `profile`, `status`, statistics, `EXIT_SUGGESTED` / `SL_MOVE_SUGGESTED`, 5m bars) and serving | Fadi and Yazan | open |
| Live = backtest replay per strategy and bundle | Fadi | open |
| Forward paper log, monitoring (CUSUM threshold in an addendum) | Fadi and Yazan | open |
| W2 swap series (historical policy rates) or dropping W2 | Fadi | open |
| P9: the lockbox together with the paper log, read once | later | sealed |
