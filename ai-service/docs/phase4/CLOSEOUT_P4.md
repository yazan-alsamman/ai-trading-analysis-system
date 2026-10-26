# P4 close-out: meta-model (gate not passed, documented)

Closed 2026-10-25 by Fadi. Branch `ai/p4-meta-model`. A phase ends only when its gate passes on
evidence (`CLAUDE.md`); P4's gate did not pass, so P4 is closed as **documented, not passed**, the
way P2 v1 was. The result is the evidence the thesis reports for H2.

## Gate

| Gate (design) | Result | Source |
| --- | --- | --- |
| Brier skill > 0 | **fail**: -0.011 (E2), -0.022 (E3), -0.013 (E4), -0.001 (E2, design label) | `meta_*.md` |
| ECE < 0.05 | pass: debiased ECE +0.015 to +0.032, pooled, 10 equal-mass bins | `meta_*.md` |

Read as registered in `PREREG_P4.md` §6 (registered 2026-10-23, before any fit).

## H2: rules + ML > rules only

**Not supported.** Decided on E2 alone (trial 7): 209 of 1,058 walk-forward test trades accepted,
mean net R -0.054 against -0.047 for all trades, difference -0.007 (one-sided 95% lower bound
-0.122), deflated Sharpe ratio 0.013 with N = 10. The secondary families (trials 8-9) and the
design label (trial 10) accept trades that are worse than all trades (-0.093 to -0.145).

| Trial | Model | Accepted | Mean net R acc. | Difference (lower 95%) | BSS |
| --- | --- | --- | --- | --- | --- |
| 7 | **E2 elastic-net LR (primary)** | 209 | -0.054 | -0.007 (-0.122) | -0.011 |
| 8 | E3 LightGBM-small | 226 | -0.144 | -0.097 (-0.205) | -0.022 |
| 9 | E4 MLP (16) | 249 | -0.093 | -0.046 (-0.150) | -0.013 |
| 10 | E2, design label (TP first) | 335 | -0.145 | -0.098 (-0.184) | -0.001 |

## Control arms (`PREREG_P4.md` §7, LR)

| Run | Gain (accepted - all) |
| --- | --- |
| meta(E1), 38 features (trial 7) | -0.007 |
| meta(E1), 29 context features | -0.037 |
| meta(E0), 20 matched random replications: 5th / median / 95th percentile | -0.085 / -0.018 / +0.103 |

The SMC pattern adds no information beyond session, volatility and cost context: meta(E1) sits
at about the 61st percentile of the random-entry gains (`meta_lr_e0.md`).

## What the evidence says, together with P3

1. H1 not supported (P3): the L1 rules alone do not beat matched random entries, on the
   development period (p 0.36) or on the walk-forward period (`L1-M.md`, p 0.55). Horizons 96 and
   192 bars and signal-based management (L1-M) do not change that (trials 4-6).
2. H2 not supported (P4): no model family, label or feature set registered finds a filter that
   improves mean net R after costs; Brier skill is negative for every model.
3. In 9 of 13 windows E2's inner CV shrinks every coefficient to zero: the data offer no stable
   signal at this sample size (about 630 positives, 38 features).

## Notes for the thesis

- The yearly condition of H2 (accepted total R not below all trades' in 4 of 7 years) passes
  trivially for a filter that trades less in losing years (5 of 7 for trials 8-10). Report it
  with that caveat.
- Label uniqueness median 1.0: AFML uniqueness weights are not needed for this setup density.
- Prior exposure before P4: trials 1-6 and the removed pre-v0.2 Phase 3 run
  (`docs/AUDIT-2026-10-21.md` §2).
- Costs on EURUSD 2021-2023 are understated (recorded spread zero on 54-63% of bars,
  `dataset_L1.md`), which favours the rules; the null result holds regardless.

## Left open (registered, not needed for H2)

- §7 control arms for E3 and E4 (`--model lgbm|mlp --arm context|e0`).
- SHAP figures for E3 beyond the table in `meta_lgbm.md`.

## Consequence for the next phases (Fadi, 2026-10-25)

- **P6 before P5.** P6 (live scanner, lifecycle, sizing, exposure; gate < 10 s, live = backtest)
  does not depend on a model: the contract's `model_unavailable` path covers it, and it unblocks
  the backend's evaluate job (B9). P5 (encoder, HMM; gate "H3, H4 documented") follows.
- v1 ships rules with abstention and no probability: `versions.model` null, `grade` null,
  `probability` and `ev_r` null, until a model passes a gate. The lockbox stays sealed.
