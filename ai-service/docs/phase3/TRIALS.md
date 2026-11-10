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
plus trial 26 (Addendum 1). Trial 27 (Addendum 2, approved 2026-11-04) uses N = 60, which also counts the
exploratory looks of 2026-11-03/04 (below).

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
**Holdout (read once, 2026-10-31, `docs/strategies/holdout.md`):** trial 19 consistent, M8 against
M0 +0.010 R on 8,057 holdout scalp entries: **activated**. Trials 20-21 were not activated, so
they had no holdout check. Trials 22-25 (family D) were not run: Stage E was closed by Fadi on
2026-10-31.

## Post-hoc trial (Addendum 1)

| # | Date | Hypothesis | Origin | Primary period (not evidence) | Judged by |
| --- | --- | --- | --- | --- | --- |
| 26 | 2026-10-31 | S1 managed by M8: mean net R > 0 and above M0 (holdout: **not consistent**, net -0.077, M8 - M0 +0.002, gross -0.012, n 903) | best of 72 strategy-bundle combinations in an exploratory analysis after Stages C and D | net R +0.005 (gross +0.054) | the single holdout reading (consistency only) and the forward paper log (section 8 procedure at K = 30); `docs/strategies/ADDENDUM_1_S1_M8.md` |
| 27 | 2026-11-04 | Level break: at prior-day, five-day and round-number levels, price goes D through more often than D back (H_L1), and a stop entry with the break has mean net R > 0 (H_L2) | exploratory level test on the research instruments, 2018 to 2024-06 (`tools/research/levels_explore.py`) | bounce 46.1% at real levels against 50.0% at placebo levels, -3.9 points (-4.7 to -3.2); every instrument and every gold year below placebo | one reading of six instruments never read here (NZDUSD, USDCHF, EURJPY, GBPJPY, EURGBP, XAGUSD), 2018 to 2026-01-10; `docs/strategies/ADDENDUM_2_LEVEL_BREAK.md`. **H_L1 passed (2026-11-04, `docs/strategies/levels_confirm.md`)**: bounce 48.0% against 49.0% at placebo, -1.0 point (-1.8 to -0.2), one-sided p 0.010, 6 of 6 instruments below placebo; a quarter of the exploratory effect. **H_L2 stopped by Fadi after 2 of 6 instruments, not judged**: interim net R NZDUSD -0.154, XAGUSD -0.124 (11,868 trades, both well below zero); correction 2026-11-05: both runs used ticks generated from M1 bars, not real ticks (the FxPro server keeps real ticks only from about 2026-01) |

## Exploratory looks after the holdout (not trials; decided nothing)

On data already seen (the primary period, 2018 to 2024-06), after the holdout reading. They count
toward N for the Deflated Sharpe of trial 27 (**N = 60**).

| Date | Look | What it showed |
| --- | --- | --- |
| 2026-11-03 | Stage C gold trades re-costed with the MT5 costs, per strategy (8) and under M8 (8) | gold -0.049 R a trade at real cost; best S4 + M8 +0.013 (SE 0.066) |
| 2026-11-03 | Gold M8 trades by cost tercile (S1, S4, S7) and S3 by direction | no pattern; S3 long followed gold's rise |
| 2026-11-04 | Scalp diagnostic: signed move after S4, S5, S6, S8 at 5-120 min, excursions, move size against random bars | no positive directional information; a small move against the signal in the first 30 min; S6 reversed |
| 2026-11-04 | Gold scalp signals with fixed SL/TP ($2/$4, $2/$5, $5/$10, $6/$12, $5/$12) against coin-flip entries | the same as coin flips; net -0.093 to +0.009 R |
| 2026-11-04 | Level test (origin of trial 27) | see trial 27 |
| 2026-11-07 | Gold commercial track, shadow candidates (`docs/strategies/GOLD_SHADOW.md`, registered before the run): 36 opening-candle settings (OPEN, after SCUTA's 09:30 candle vs EMA 12) and 3 level breaks with LVL4H's settings (PIVW, ASIA, PWHL); seen data 2012 to 2026-01-09 plus FxPro GOLD to 2026-11-05 | OPEN dropped (no setting positive on 2012-2021; SCUTA's own rules −0.99 R with slip, the stop too small for gold's costs); PIVW, ASIA, PWHL pass (FxPro +0.022 / +0.016 / +0.095 with slip), daily correlation with LVL4H +0.38 to +0.57 |
| 2026-11-07 | Gold commercial track, night reversion inside the Asian box (`docs/strategies/GOLD_NIGHT.md`, registered before the run): 12 settings (box to 20:00 / 21:00, touch with SL 0.5 / 1 x W or reclaim, target the middle or the other edge), XAUUSD 2012 to 2026-01-09 | dropped: no setting positive with >= 300 trades on 2012-2021; touch fades lose in every setting (check -0.05 to -0.12 R), reclaim about zero |
| 2026-11-07 | Gold commercial track, the 50% correction after a strong move (`docs/strategies/GOLD_RETRACE.md`, registered before the run): CORR (trade the correction to the 50% level) and FIB50 (a limit at the 50% level with the move), 24 settings each (TF 5m / 15m / 30m / 1h, leg >= 0.5 / 0.75 / 1.0 x ATR(D1), fixed or trailing SL), XAUUSD 2012 to 2026-01-09 | both dropped: no setting positive with >= 300 trades and 60% of years on 2012-2021; strong legs reach their 50% level less often than small ones (5m: 20% at >= 1 x ATR(D1) against 46%) |
| 2026-11-07 | Gold commercial track, pullback continuation (`docs/strategies/GOLD_PULLBACK.md`, registered before the run): after a strong leg, a 15-50% pullback, then an entry with the move (SWING stop or BAR close), target the old high, the measured move or none, always trailing; 48 settings, XAUUSD 2012 to 2026-01-09 | dropped: chosen 30m / 0.75 / SWING / ABCD +0.048 R on 2012-2021, -0.021 with slip on the check; daily correlation with the day strategies +0.02 to +0.07 |
| 2026-11-07 | Gold commercial track, the New York opening range breakout (`docs/strategies/GOLD_ORB.md`, registered before the run): the 08:20-08:50 range broken from 08:50 to 16:00 with LVL4H's engine, one fixed setting, XAUUSD 2012 to 2026-01-09 and FxPro GOLD to 2026-11-05 | dropped: -0.031 / -0.025 R with slip on XAUUSD 2012-2021 / check, -0.055 on FxPro, -0.184 in 2026; daily correlation with the five +0.11 to +0.25 |
| 2026-11-08 | Gold commercial track, fading the five's breaks on FxPro GOLD at their levels (exploratory, not registered, decides nothing; Fadi asked for 2026-10-21 to 2026-11-05): MIRROR (the opposite trade at the level, SL D, TP 1 R) and RECLAIM (a close back inside within 6 bars, SL beyond the break, TP 1.5 R) | Oct 21-Nov 5: breaks -0.52 R a trade, MIRROR +0.49, RECLAIM +0.47; 2026: breaks +0.06, MIRROR -0.09, RECLAIM -0.04; 2016-2026: breaks +0.03, MIRROR -0.10 (-750 R), RECLAIM -0.07 |
| 2026-11-08 | Gold commercial track, do the breaks' bad runs persist (`docs/strategies/GOLD_REGIME.md`, registered before the run): PERF (mean of the last 20 / 30 / 50 break trades < -0.10) and FALSE (20-day false-break rate above its 75th percentile), FxPro GOLD 2016-2026 and XAUUSD 2012-2026 | no: breaks after BAD +0.003 to +0.023 R on FxPro (t +0.1 to +1.1), RECLAIM in BAD negative, SWITCH below ALWAYS for every detector; no switch |
| 2026-11-08 | Gold commercial track, daily trend swing (`docs/strategies/GOLD_SWING.md`, registered before the run): N-day close breakout, 2 x ATR(20, D1) SL, M-day channel exit, 20/10 and 55/20, with and without shorts, swap scenario 3% a year on longs, XAUUSD 2012 to 2026-01-09 | dropped: no setting with 60% of the years positive (40-50%); all positive (long only 20/10: +0.168 R on 2012-2021, 38 trades; +0.520 on the check, 20 trades), mostly gold's rise |
| 2026-11-08 | Gold commercial track, the previous day's value area (`docs/strategies/GOLD_VP.md`, registered before the run): VAH / VAL from 5m tick volume (100 bins, 70%), broken with LVL4H's engine, one fixed setting | dropped: +0.008 R with slip on 2012-2021, -0.017 on the check, -0.031 on FxPro, -0.089 in 2026; daily correlation with the five +0.41 |
| 2026-11-08 | Gold commercial track, the "AH" bot clone (`docs/strategies/GOLD_AH.md`, registered before the run): M1 trend pullback (close > close[10], EMA20 > EMA50, %K(5) ≤ 0.4), SL 1.7 × 10-bar range, TP 0.4 SL, E1 + double E2 limit, break-even; AHB and V1-V6, ALL (8 settings), XAUUSD 2012 to 2026-01-09 | all dropped: gross R about 0 everywhere, net R −0.16 to −0.22 on 2012-2021 (0% of years positive), −0.03 to −0.06 on the check |
| 2026-11-09 | Gold commercial track, the dealing range (`docs/strategies/GOLD_DR.md`, registered before the run): 15m range grows until a wick touches 50%, then a limit at the bounce's first FVG, SL LOW / EQ, 2 R / 4 R, minimum range 1.5 / 3 x ATR (8 settings), XAUUSD 2012 to 2026-01-09 | dropped: degenerate as written, 19 touches of 50% in 14 years, 1-2 trades a setting on 2012-2021, none after 2012; needs a bound on the range's low |
| 2026-11-09 | Gold commercial track, DR2: the dealing range capped by the daily ATR (`docs/strategies/GOLD_DR.md` §7, registered before the run): DR with L moved up to the latest 15m swing low when H - L > C x ATR(14, D1), M 1.5, SL LOW / EQ, 2 R / 4 R, C 1 / 2 (8 settings), XAUUSD 2012 to 2026-01-09 | dropped: every setting negative on 2012-2021 (-0.05 to -0.24 R, 20-50% of years positive); C2 positive on the check (+0.01 to +0.08 with slippage), not chosen |
| 2026-11-09 | Gold commercial track, the AH bot's leg exits (`docs/strategies/GOLD_AHX.md`, registered before the run): AHB entries, TP = L + 1.088 R and SL = H - 2.025 R on the leg before the pullback (L = last 3-bar M1 pivot low), X1 E1 only and X2 with E2 (2 settings), XAUUSD 2012 to 2026-01-09 | dropped: net R -0.19 / -0.17 on 2012-2021 (0% of years positive), -0.05 on the check; TP hit rate equals the random-walk rate (+0.2 points, SE 0.2; check +1.2) |
| 2026-11-09 | Gold commercial track, filters on X1 then meta-labeling (`docs/strategies/GOLD_AHF.md`, registered before the run): every X1 signal a trade, 50 features, a greedy filter of up to 3 conditions from 300 candidates chosen on 2012-2017 (gross R, with 50 shuffled reruns as the bar), gated on 2018-2021 before any meta-model | stopped at stage 2: no feature quintile, hour, weekday or session with gross R > 0 on 2012-2017; chosen filter (gap_open, ema_gap, news_window) +0.004 gross on D, +0.010 on V (p 0.128, gate needs 0.05), net −0.16 on V against 0.15-0.17 R cost; meta-labeling not run, check not read. **Amendment 1** (after the stage-2 reading, Fadi): stage 3 on every X1 trade, no filter: LR net −0.067 R on 8,320 accepted, LightGBM −0.056 on 2,550 (gain +0.09 to +0.10 over the base, above random, BSS +0.15), both fail net > 0; the accepted trades' gross is about 0, the gain is a lower cost per R; check not read |
| 2026-11-09 | Gold commercial track, X1 with large legs and low cost (`app/research/gold_ahl.py`, `docs/strategies/gold_ahl_explore.md`; exploratory, not registered, decides nothing; Fadi asked after GOLD_AHF): top 20% of leg_d on 2012-2017 and the cheaper half of those (11,082 trades), signed move at 5-360 min and a 5 x 4 grid of fixed TP / SL from the entry; bars before 2018 only, so 2018 on stays unread | no drift: +0.021 leg R at 360 min at most (t 0.8) against a cost of 0.086 leg R; every grid cell gross within ±0.026 R (|t| < 2 except the near-TP cells, negative), net −0.04 to −0.36; X1 exits gross −0.013, net −0.063 |
| 2026-11-10 | Gold commercial track, Fadi's pullback before the break and re-entry of a strong move (`docs/strategies/GOLD_PBK.md`, registered before the run): PBK (first touch of a 5m swing level or PDH / PDL, a 0.5-1.5 x ATR(5m) pullback, entry on the first up close, SL >= 1 x ATR, target 2 R or the next live level, 1h + 4h structure filter or none; 4 settings) and RTB (a limit at 20% / 30% of a 5m leg >= 0.75 x ATR(D1), SL at 50%; 8 settings), M8 with the target, XAUUSD 2012 to 2026-01-09 | both dropped: no setting with net > 0 and 60% of the years on 2012-2021 (PBK best +0.038 R on 96 trades, check -0.139; RTB best +0.114 on 321 trades, 40% of years, check -0.035); a pullback after the touch lowers the break rate (72.7% against 85.2% without); gross R without the cost cap about 0 for every setting (-0.008 to +0.043) |
| 2026-11-10 | Gold commercial track, PBK-M1 (`GOLD_PBK.md` §10, Addendum 1, registered before the run; Fadi): PBK's 5m first touch and pullback without a trend filter, entry on the first M1 up close, fixed SL and TP of $10 (1,000 points), 16:45 exit, one setting, XAUUSD 2012 to 2026-01-09 | dropped: net -0.040 R on 4,111 trades on 2012-2021 (10% of years positive), -0.018 with slip on the check; gross about 0 (-0.002 / +0.004); TP before SL is a coin flip (23.3% / 22.6%, check 35.4% / 34.7%) |

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
