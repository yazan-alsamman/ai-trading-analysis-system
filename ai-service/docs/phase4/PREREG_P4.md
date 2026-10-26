# P4 pre-registration amendment: label, acceptance rule, small-sample setup, controls

**Status: REGISTERED 2026-10-23** (approved by Fadi as written, before any model was fitted;
nothing below had run at registration). Branch `ai/p4-meta-model`. Section 5's open point (pooled
headline, XAUUSD as the named secondary) and N = 10 in section 8 were approved with it.

Background and sources: `reports/تحسين الميتا ليبلينج قبل التدريب.md` and
`research_notes/`. Applies to P4 task 3 (E2 LR, E3 LightGBM, E4 MLP) on rules **L1** (frozen
2026-10-23), pooled over the six instruments, walk-forward 2018-01 to 2024-06 (13 windows,
`app/research/walkforward.py`). The secondary holdout and the lockbox are not loaded.

## 0. What has been seen before this amendment (disclosure)

- Development period and walk-forward test windows: E1 (L1 rules only) and matched E0 results,
  exit-reason mix and mean net R by exit reason (`docs/phase3/baselines*.md`,
  `docs/phase4/walkforward_L1.md`, `docs/phase4/L1-M.md`); trials 1-6 in `docs/phase3/TRIALS.md`.
- The share of E1 trades with net R > 0: 45.5% (2012-2017), 42.5% (walk-forward), reported in
  `L1-M.md` as a sensitivity target. So the base rate of the new label is known.
- **No model has been fitted** on any label; no feature has been related to any outcome.
- Trigger for the change: 53% of E1 trades end at the 48-bar horizon with mean net R about
  +0.2R (dev) / +0.35R (walk-forward), and the design label (§9.2) counts them as 0 with SL.
  Prior reason, independent of these numbers: the H2 metric is mean net R per trade after costs,
  and a label should rank trades by the sign of that quantity.

## 1. Label

- **Primary: `y = 1{net R > 0}`**, net R after costs as in `labels.resolve` (round trip spread +
  extra cost, SL slippage), all exit reasons kept (TP, SL, horizon).
- **Sample weight `w = |net R|`**, normalised to mean 1 within each fit set. The fitted score is
  therefore an R-weighted score, not a probability; the calibrator (section 3) is fitted
  **unweighted**, so the reported `p` estimates P(net R > 0).
- Replaces the design label (y = 1 for TP first) for E2-E4. The design label is run once, with
  E2 (LR) only, same everything else, and reported beside the primary result as a disclosure
  (trial 10). It is not used to choose anything.

## 2. Models (fixed now; families ranked before any fit)

All families use the 38 features of `app/features/setup_features.py` (`FEATURES`), unchanged. No
feature is added, dropped or selected by hand; elastic net does the shrinkage inside each window.
Feature-set changes (news timing, round numbers, volatility ratio) are not part of this
amendment.

**No class weights, no SMOTE / over- or under-sampling, no `is_unbalance` / `scale_pos_weight`,
no focal loss.** The only weights are the |net R| weights of section 1.

| Rank | Experiment | Model (seeds fixed at 20261023) |
| --- | --- | --- |
| **Primary** | **E2** | Elastic-net logistic regression (`saga`, `l1_ratio` 0.5). Missing values: median of the fit rows; features standardised on the fit rows. `C` from 10 values log-spaced 1e-3 to 1e1, chosen by weighted log loss on a purged, time-ordered inner split of the fit rows (3 expanding folds, purge + 1-day embargo as the outer protocol). |
| Secondary | E3 | LightGBM, fixed parameters, no tuning: `num_leaves` 6, `max_depth` 3, `min_data_in_leaf` 40, `extra_trees` true, `lambda_l2` 10, `path_smooth` 5, `max_bin` 63, `learning_rate` 0.05, 200 rounds, `feature_fraction` 0.8, `bagging_fraction` 0.8 (freq 1), no monotone constraints. NaN handled natively. |
| Secondary | E4 | MLP (scikit-learn), one hidden layer of 16, ReLU, `alpha` 1e-2, Adam, 300 iterations, no early stopping; same imputation and scaling as E2; mean of 5 seeds (20261023 + 0..4). |

**H2 is decided on E2 alone.** E3 and E4 are reported in full but cannot replace E2 as the
headline result, whichever scores best on the test windows.

## 3. Calibration (replaces the Platt-or-isotonic choice in `walkforward.py`)

- **Platt scaling only**, for every family, fitted unweighted on the calibration slice (the last
  25% of each training set by decision time, purged and embargoed from the fit rows, as now).
- Isotonic is not used (about 95-340 calibration rows per window). Beta calibration and
  Venn-Abers are not run.

## 4. Acceptance rule (EV) and minimum trades

For each window, from that window's **training rows only** (fit + calibration):
`m1` = mean net R of rows with y = 1, `m0` = mean net R of rows with y = 0, pooled over
instruments.

A test setup is **accepted** when `p * m1 + (1 - p) * m0 > 0`. No other threshold, threshold
sweep, learned threshold or sizing curve is run.

**Minimum: 30 accepted trades** pooled over the 13 windows. Below 30, H2 is reported as
**"insufficient"** (neither supported nor rejected) for that family.

## 5. H2 test and reporting

- **Metric**: mean net R per accepted trade (costs included) against mean net R of all E1 trades
  in the same 13 windows (1,058 trades).
- **Test**: paired difference (accepted mean - all mean), weekly block bootstrap (all instruments
  of a week resampled together, 10,000 resamples, seed 20261023), **one-sided 95%**. H2 supported
  for E2 only if the lower bound is above 0, at least 30 trades are accepted, and the design's
  condition holds: yearly total R of the accepted trades is not below E1's in a majority of the
  years 2018-2024 (7 years; at least 4). Reported for every family.
- Also reported: accepted share, precision (share of accepted with net R > 0), mean net R at 2x
  costs, sign test of the 13 window differences, per instrument (XAUUSD first), per year.
- **Scope of the headline**: pooled over the six instruments; XAUUSD reported as the named
  secondary (about 190 test trades, likely below 30 accepted).
- **Deflated Sharpe** on the accepted-trade series (per-trade Sharpe), N = all strategy trials in
  `TRIALS.md` up to and including this amendment (section 8).

## 6. Calibration reading (P4 gate)

All on the **pooled** out-of-sample predictions of the 13 windows:

- **Brier skill** against each window's training base rate (climatology), as now. Gate: > 0.
- **ECE**: 10 **equal-mass** bins (replaces equal-width), absolute deviation weighted by bin
  size. **Debiased ECE** = ECE minus the mean ECE of 1,000 simulated label sets drawn as
  Bernoulli(p) on the same predictions (the ECE a perfectly calibrated model would show by noise
  alone). Gate: **point estimate of the debiased ECE < 0.05**; its weekly block bootstrap 95%
  interval is reported beside it.
- Calibration intercept and slope (logistic recalibration of y on logit p), reliability diagram.
- Per-window Brier and ECE are diagnostics only (8-40 positives a window); they do not gate.

## 7. Controls and diagnostics (not used to choose anything)

**E0 + meta (control arm).** Does the model find something in the SMC pattern, or only learn
session, volatility and cost timing? The matched random entries of P3 task 4, drawn on the
walk-forward period (same instrument, year, New York hour, risk in ATR, TP rule, costs; seed
20261023), labelled the same way (section 1). The 9 pattern features do not exist for a random
entry (`depth_atr`, `levels_taken`, `src_4h`, `src_pd`, `has_fvg`, `fvg_size_atr`,
`bars_sweep_to_choch`, `displacement_atr`, `choch_margin_atr`); the other 29 (context) are
computed at the random bar with the same code.

- `meta(E0)`: each family trained and tested on the E0 trades with the 29 context features, same
  folds, calibration and EV rule; **20 E0 replications**, each a separate run; reported as the
  distribution of (accepted mean - all mean).
- `meta(E1, context)`: each family on E1 with the same 29 features.
- Reading: the SMC pattern adds value only if `meta(E1)` (38 features) beats `meta(E1, context)`
  and its gain over E1 lies above the 95th percentile of the `meta(E0)` gains. Reported for every
  family, not a gate.

**Uniqueness** (AFML ch. 4): median label uniqueness per instrument and across instruments. If
the median is above 0.9, no uniqueness weights are used (the default here); if below, this is
reported and the weights still are not added in this amendment.

**Model reading**: LR coefficients (standardised), SHAP for E3, importance stability across the
13 windows. Diagnostics only.

## 8. Trials (`docs/phase3/TRIALS.md`)

| # | Configuration |
| --- | --- |
| 7 | E2 elastic-net LR, label net R > 0 weighted, Platt, EV rule (primary) |
| 8 | E3 LightGBM-small, same |
| 9 | E4 MLP, same |
| 10 | E2 with the design label (TP first), disclosure |

The E0 + meta and context-only runs are controls, listed in `TRIALS.md` under their own heading
and not counted in N. N for the Deflated Sharpe after this amendment: **10**. Any change after
these results (label, features, threshold, family, calibrator) is a new numbered trial.

## 9. Code changes this implies (before any run)

- `walkforward.py`: `y` from net R; sample weights passed to `fit`; `Platt` only; equal-mass and
  debiased ECE, calibration intercept and slope; `ECE_BINS` stays 10.
- New `app/research/meta.py` (`python -m app research meta --model lr|lgbm|mlp [--label tp]
  [--arm e0|context]`): models, inner CV for E2, EV rule, H2 test, report
  `docs/phase4/meta_<model>.md`.
- E0 trades and their 29 context features on the walk-forward period
  (`app/research/baselines.py` + `app/features/setup_features.py`).
- `lightgbm` and `scikit-learn` added to the `research` extra in `pyproject.toml`.
- Unit tests for the EV rule, debiased ECE, weights and the context-feature path for random
  entries, plus the no-look-ahead test, before the first run.
