# P3 trials log (rules-only performance, development period)

Every run that measured rules-only performance (E1 / E1s / E0) on 2012-2017 is listed here, so the
number of trials is known when results are corrected for multiple testing (Deflated Sharpe) and
reported in the thesis. A trial is one configuration whose performance was looked at; re-running
the same configuration (same code, seed and data) is not a new trial.

Earlier looks at performance on the development period, before this log: the XAUUSD labels of
P3 task 2 (`labels_XAUUSD_v1.md`, `labels_XAUUSD_V5-S.md`): 2 trials.

| # | Date | Configuration (all else as `strategy.toml`) | Report | E1 (L1) net R, all | E0 | E1 - E0 (95%) | p | E1 XAUUSD | Asked by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3 | 2026-10-22 | Horizon 48 bars (12 h), the registered value | `baselines.md` | -0.046 | -0.063 | +0.017 (-0.095 to +0.125) | 0.36 | -0.072 | P3 task 4 |
| 4 | 2026-10-23 | Horizon 96 bars (24 h) | `baselines_h96.md` | -0.066 | -0.069 | +0.003 (-0.123 to +0.124) | 0.46 | -0.063 | Fadi |
| 5 | 2026-10-23 | Horizon 192 bars (48 h) | `baselines_h192.md` | -0.100 | -0.083 | -0.017 (-0.154 to +0.116) | 0.60 | -0.180 | Fadi |
| 6 | 2026-10-23 | **L1-M**: L1 with signal-based position management (opposite signal exits, same-direction signal extends to 48 bars after it, cap 192; one position per instrument). Registered before the run (`MARKET_STRUCTURE_DEFINITIONS.md`, L1-M). Measured on development and walk-forward periods | `docs/phase4/L1-M.md` | -0.053 | -0.060 | +0.007 (-0.104 to +0.114) | 0.46 | -0.043 (both periods) | Fadi |

Each E1 / E0 trial also reports E1s (V5-S) and E1 without same-bar patterns; those are read from
the same run and are not counted as separate trials. Trials so far: **18** run (7-10 below, P4;
11-21 and 26, the signal strategies); N for the Deflated Sharpe: **26**: the 25 registered for
the strategy plan (`docs/strategies/PREREG.md`, section 15; trials 22-25 are family D, not run)
plus trial 26 (Addendum 1).

## P4 meta-model trials (walk-forward test windows, 2018-01 to 2024-06)

Registered 2026-10-23 in `docs/phase4/PREREG_P4.md` before any model was fitted. Label
`y = 1{net R > 0}` weighted by |net R|, Platt, EV acceptance rule, minimum 30 accepted trades;
H2 decided on trial 7 alone. Baseline: E1 on the same windows, 1,058 trades, mean net R -0.047.

| # | Date | Configuration | Report | Accepted | Mean net R accepted | Accepted - E1 (one-sided 95% lower) | BSS | Debiased ECE | Status | Asked by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 7 | 2026-10-23 | **E2** elastic-net LR (primary) | `docs/phase4/meta_lr.md` | 209 (19.8%) | -0.054 | -0.007 (-0.122) | -0.011 | +0.032 | **H2 not supported**; P4 gate fail (BSS < 0) | Fadi |
| 8 | 2026-10-23 | E3 LightGBM-small, fixed parameters | `docs/phase4/meta_lgbm.md` | 226 (21.4%) | -0.144 | -0.097 (-0.205) | -0.022 | +0.029 | not supported (secondary); P4 gate fail (BSS < 0) | Fadi |
| 9 | 2026-10-23 | E4 MLP (16), mean of 5 seeds | `docs/phase4/meta_mlp.md` | 249 (23.5%) | -0.093 | -0.046 (-0.150) | -0.013 | +0.027 | not supported (secondary); P4 gate fail (BSS < 0) | Fadi |
| 10 | 2026-10-23 | E2 with the design label (TP first), disclosure | `docs/phase4/meta_lr_tp.md` | 335 (31.7%) | -0.145 | -0.098 (-0.184) | -0.001 | +0.015 | not supported (disclosure); P4 gate fail (BSS < 0) | Fadi |

Controls (not counted in N, not used to choose anything; `PREREG_P4.md` §7): E0 + meta (20
replications, 29 context features) and E1 + meta with context features only, for each family.

## Signal strategy trials (primary period 2018-01 to 2024-06, families A and B)

Registered in `docs/strategies/PREREG.md` (approved 2026-10-30, rules frozen at `b9ca2a8`); run by
`python -m app research evaluate` on code `57cc935`, seeds 20261030 / 20261031, M0, net R with the
decision swap scenario. d = x minus the mean of 200 matched E0 entries. Holm within family A (6) and
B (2). Summary: `docs/strategies/evaluation.md`.

| # | Date | Strategy | Report | n | Mean x | Mean d | p_S | Holm p | U_S | delta* | Result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 2026-10-31 | S1 LB, London breakout (A, intraday, 15m) | `docs/strategies/eval_S1.md` | 3,735 | -0.014 | +0.038 | 0.760 | 1.000 | +0.019 | 0.050 | unvalidated |
| 12 | 2026-10-31 | S2 MR, Bollinger reversion (A, intraday, 1h) | `docs/strategies/eval_S2.md` | 3,421 | -0.082 | -0.027 | 1.000 | 1.000 | -0.049 | 0.050 | unvalidated |
| 13 | 2026-10-31 | S3 TF, Donchian breakout (A, swing, 4h) | `docs/strategies/eval_S3.md` | 1,271 | -0.128 | -0.031 | 0.990 | 1.000 | -0.035 | 0.073 | unvalidated |
| 14 | 2026-10-31 | S4 ORB, New York opening range (A, scalp, 5m) | `docs/strategies/eval_S4.md` | 4,458 | -0.055 | +0.003 | 0.992 | 1.000 | -0.017 | 0.050 | unvalidated |
| 15 | 2026-10-31 | S5 PB, trend pullback (A, scalp, 5m) | `docs/strategies/eval_S5.md` | 38,970 | -0.087 | -0.017 | 1.000 | 1.000 | -0.075 | 0.050 | unvalidated |
| 16 | 2026-10-31 | S6 VR, VWAP reversion (A, scalp, 5m) | `docs/strategies/eval_S6.md` | 5,845 | -0.099 | -0.036 | 1.000 | 1.000 | -0.071 | 0.050 | unvalidated |
| 17 | 2026-10-31 | S7 SQ, squeeze breakout (B, intraday, 15m) | `docs/strategies/eval_S7.md` | 2,906 | -0.067 | -0.004 | 0.994 | 1.000 | -0.023 | 0.050 | unvalidated |
| 18 | 2026-10-31 | S8 FX, fix reversal (B, scalp, 5m) | `docs/strategies/eval_S8.md` | 1,264 | -0.045 | +0.013 | 0.929 | 1.000 | +0.007 | 0.050 | unvalidated |

No strategy passed, so none goes to the holdout check; all eight are served as "unvalidated" ("no
proven edge"). S1 beats its matched random entries (d +0.038, 95% +0.001 to +0.075) but not its
costs (x -0.014). Every strategy is below zero at twice the costs.

## Management trials, family C (test windows 2018-01 to 2024-06)

Registered in `docs/strategies/PREREG.md` section 9; run by `python -m app research management`
on code `7bf8142`. The walk-forward bundle selection (M0-M8) against M0, on M0's fixed entry
set. Holm over the three types. Report: `docs/strategies/management.md`.

| # | Date | Type | Test trades | Mean delta (95%) | p | Holm p | Result | Bundle served |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 19 | 2026-10-31 | scalp | 50,537 | +0.015 (+0.005 to +0.026) | 0.002 | 0.007 | passed, waits for the holdout check | M8 |
| 20 | 2026-10-31 | intraday | 10,062 | +0.012 (-0.005 to +0.029) | 0.094 | 0.123 | not activated | M8 |
| 21 | 2026-10-31 | swing | 1,271 | +0.063 (-0.015 to +0.142) | 0.061 | 0.123 | not activated | M7 |

Scalp management improves net R but leaves it negative (M0 -0.085, M8 -0.069 on the same entries).

## Post-hoc trial (Addendum 1)

| # | Date | Hypothesis | Origin | Primary period (not evidence) | Judged by |
| --- | --- | --- | --- | --- | --- |
| 26 | 2026-10-31 | S1 managed by M8: mean net R > 0 and above M0 | best of 72 strategy-bundle combinations in an exploratory analysis after Stages C and D | net R +0.005 (gross +0.054) | the single holdout reading (consistency only) and the forward paper log (section 8 procedure at K = 30); `docs/strategies/ADDENDUM_1_S1_M8.md` |

## Outcome mix of E1 by horizon

| Horizon | TP | SL | Horizon reached | Mean net R |
| --- | --- | --- | --- | --- |
| 48 | 12% | 35% | 53% | -0.046 |
| 96 | 19% | 49% | 31% | -0.066 |
| 192 | 27% | 62% | 11% | -0.100 |

## Reading (2026-10-23)

A longer horizon turns most of the trades that ended at the horizon into SL rather than TP:
going from 48 to 192 bars, TP rises by 15 points and SL by 27. E1 stays within the range of its
matched random entries at every horizon (p 0.36 / 0.46 / 0.60), and the TP rate is about
1.5 points above E0 at each horizon. So the horizon was not hiding an edge. **The registered
horizon (48) stays**; no parameter was changed by these trials.

## Measurements of the frozen rules (not trials)

The rules (L1, `strategy.toml`) were frozen on 2026-10-23, before P4. Measuring them on later
periods chooses nothing, so it is not a trial; any change to them after this date is a new
version and a new trial.

| Date | Measurement | Report | Result |
| --- | --- | --- | --- |
| 2026-10-23 | E1 on the 13 walk-forward test windows (2018-01 to 2024-06) | `docs/phase4/walkforward_L1.md` | 1,058 trades, TP 11.1%, mean net R -0.047 (95% weekly block -0.115 to +0.020) |
