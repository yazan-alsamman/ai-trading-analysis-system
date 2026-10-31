# Signal system plan: strategies, management, AI

Started 2026-10-25; revised 2026-10-25 after Fadi's decision tables. The service stays a signal
detector and giver, with signals split into scalp / intraday / swing, trade management on TP and
SL, and AI layers for range, regime, exits and direction. **Signal frequency is descriptive only:
there is no minimum, zero signals on a day is valid, and nothing is loosened or chosen to produce
more signals.** Rules, bundles, models, tests and limitations: `PREREG.md` (draft until Fadi
approves it).

## How the pieces fit

```
closed bar ─► frames (5m, 15m, 1h, 4h, D1 from the request)
            ─► strategies S1-S8 + L1 ─► candidates (type, entry, SL, TP, horizon)
            ─► signal-time filters (cost, R range, window, holidays)
            ─► [A2 regime router] ─► [A1 range filter / TP] ─► [A4 direction filter]
            ─► one trade per strategy and instrument, conflicts, currency exposure
            ─► signal with status (validated / exploratory / inconclusive / unvalidated)
open trade ─► bundle rules T1-T4, L1-L5 [or A3 exit model] ─► EXIT / SL_MOVE alerts
closed     ─► net R and exit reason ─► forward paper log ─► monitoring (CUSUM, "suspended")
```

The AI layers in brackets are switched on only after they are activated (`PREREG.md` section 9).
Candidate generation is never reduced to fit an expected number of served signals.

## Stages (no outcome before stage C; nothing outcome-sensitive changes after approval)

| Stage | Work | Done when |
| --- | --- | --- |
| **A. Engine** | 1. `app/strategies/`: one interface for every strategy (signal bar, direction, `Plan`, frame, horizon, type, reject reason); parameters in `app/config/strategies.toml`. 2. `app/management/`: the rules T1-T4, L1-L5 and bundles M0-M8 as one bar-by-bar engine shared by research and live (M0 equals `labels.resolve` exactly). 3. Session VWAP with bands; the 5m frame for live requests. 4. Rollover instants (00:00 server time) and the swap-to-R conversion of every MT5 swap mode. 5. The pure decision functions of `PREREG.md` sections 8-10 (tests, Holm, classification, status). 6. Tests: hand-built bars for each strategy and rule, an append-future-bars test for each strategy and bundle, M0 == `resolve` on the L1 store, swap zero for scalp and intraday horizons, and status tests: a low-frequency strategy with enough evidence can pass, the same trades spread differently over days give the same status, weak evidence gives `inconclusive`. | tests pass |
| **B. Counts** | Rules frozen at a recorded commit. Pre-approval: `python -m app strategies count` (candidates and signal-time reasons only, 2012 to 2026-01-09; no `resolve`, management, E0 or exit time; holdout tables labelled candidate-only; lockbox untouched), then a_S and delta*_S; Fadi approves `PREREG.md`. Post-approval, before C (`python -m app research post-counts`): counts after the one-active-trade and conflict rules on the primary period; n, K, MDE, n_unval. Descriptive only (`PREREG.md` section 12): no gate, no fallback; a rule change is a new version and the counts are rerun. | `docs/strategies/counts.md`, approval filled |
| **C. Strategies** | Families A and B under M0 (`python -m app research evaluate`: E0, the tests, Holm, the classification and the sensitivities; built before approval, run only after it), trials 11-18. | `eval_<S>.md`, trials log |
| **D. Management** | Family C, trials 19-21. | `management.md` |
| **E. AI** | A1, A2, A3, A4 in that order, one addendum each before its fit (P5's encoder and HMM become A4 and A2). Trials 22-25. | `ai_<model>.md` |
| **F. Confirm and serve** | Holdout read once. Swap W2 series (if available) and the CUSUM threshold in an addendum. Contract with Yazan: `type`, `profile`, `status`, statistics, `EXIT_SUGGESTED` / `SL_MOVE_SUGGESTED` events, 5m bars. Live = backtest replay per strategy and bundle. Portfolio reports. Forward paper log and monitoring. | contract tests, replay with zero differences |

**Minimum cut if time runs short:** A, B, C, D and A1. A2-A4 are the first to go.

**Progress.** Stage A built 2026-10-26 (now on branch `ai/stage-a-engine`), tests pass, no count or
outcome computed: `STAGE_A.md` (what was built, the PREREG points from the audit, the choices
fixed in code where the text is silent). Fadi approved the family C wording and the separation
of pre-approval and post-approval counts (2026-10-26; now in `PREREG.md` sections 9, 12 and 15),
and their code and tests are in place (counting functions only, no command and no run on market
data). On 2026-10-27 Fadi decided the review points (session end and its gaps, the 1h boundary,
a_S without a swap export, complete ranges for S1 and S4, the rollover price, T4 wording; in
`PREREG.md` and `STAGE_A.md`). Stage A merged 2026-10-28 (PR #77), with the MT5 swap snapshot
(`docs/strategies/mt5/`). Rules frozen at `b9ca2a8` (tag `strategies-rules-v1`, 2026-10-29).
Pre-approval counts run 2026-10-29 on the frozen rules (`counts.md`, `counts_by_year.csv`;
candidates only, no outcome, lockbox not read). Stage C code built
2026-10-30 (`python -m app research evaluate`, `post-counts`). **PREREG approved by Fadi on
2026-10-30** (code `dc4ae2f`, seeds 20261030 / 20261031). Post-approval counts 2026-10-30
(`counts_post.md`). **Stage C done 2026-10-31** (`evaluation.md`, `eval_S1.md` to `eval_S8.md`,
trials 11-18): all eight strategies unvalidated; none goes to the holdout check. Next: Stage D.

## Expected counts (descriptive guess only)

Not a target and not a gate: the counts decide nothing.

| Profile | Type | Rough signals a trading day, six instruments |
| --- | --- | --- |
| L1 | intraday (label) | about 0.6 (measured) |
| S1 LB | intraday | 1.5-3 |
| S2 MR | intraday | 0.5-1.5 |
| S3 TF | swing | 0.3-0.6 |
| S4 ORB | scalp | 1.5-3 |
| S5 PB | scalp | 2-6 |
| S6 VR | scalp | 0.5-2 |
| S7 SQ | intraday | 0.5-1.5 |
| S8 FX | scalp | 0.5-2 |

Whether a selection or ranking layer is needed is judged from the Stage B counts after the
one-active-trade and conflict rules (and the exposure limits, once agreed). Any ranking is
registered and compared with the deterministic rule under the same constraints; no ranking model
is built before that.

## Weaknesses of the combined design, and what is done about each

| # | Weakness | Why it matters | What we do |
| --- | --- | --- | --- |
| 1 | **Many tests** (8 strategies, 9 bundles, 4 models) | the more we try, the more a lucky result looks real | four Holm families; bundle and model choice inside the walk-forward; holdout once; P9; DSR with N = 25 reported; error control is per family (`PREREG.md` section 14) |
| 2 | **Costs on scalps** | on gold 5m a 1.5 x ATR SL is about $2: costs 0.12 R, 0.16 R with SL slippage (15m 0.09 R, 1h 0.04 R, 4h 0.02 R; 2024 H1) | cost filter 0.15 R; 2x stress; about 60% of modelled cost is assumed, so delta* includes that allowance; no loosening after a failure |
| 3 | **Swap** | not in the exports; S3 and L1 cross rollovers | four labelled scenarios and a conservative decision envelope; never called historical cost |
| 4 | **News on 5m** | no historical calendar | results with and without first-Friday 08:30 bars; calendar is an open point |
| 5 | **Execution realism** | alerts are acted on later | next-bar fills with slippage; worse outcome on ambiguous bars |
| 6 | **"Trader sense" can overfit** | extra exit rules fit the past | bundles fixed now; selection only inside the walk-forward; test-window results of single bundles stay descriptive |
| 7 | **Overlap and correlation** | many signals can be one USD bet; S4 and S8 fire on all instruments at once | conflict rule, exposure limits, 4-week calendar blocks across instruments, DE 1.5 assumed for S4 and S8, portfolio reports |
| 8 | **Data** | tick-volume VWAP, zero EURUSD spreads 2021-2023, corrected clocks, FX from 2016 | stated in every report; per-instrument results; sensitivity 3 |
| 9 | **Non-stationarity** | gold rose from about $1,260 (2018) to over $2,200 (2024) | distances in ATR; per-year results; monitoring |
| 10 | **Live = backtest with this much logic** | many code paths | one strategy interface, one management engine for research and live, replay tests |
| 11 | **User trust** | an unvalidated signal looks like any other | status and statistics on every signal; "no proven edge" label |
| 12 | **Scope** | several phases of work | stages with a minimum cut |

## Better ways than "more rules"

1. **Forward paper log from day one**: the only data nobody has seen; used at P9 and for
   monitoring, never to change a rule.
2. **Monitoring**: a profile drifting below its registered mean is flagged "suspended"
   (operational); its statistical status changes only at P9.
3. **Judge the portfolio**: the descriptive validated-only portfolio report is the primary
   product-quality view.
4. **Volatility before direction**: A1 (how far price can move) is the most likely AI gain.

## Open points

1. MT5 swap export (`PREREG.md` section 6a). Fadi.
2. Official historical policy-rate series for W2, or W2 dropped (stage F addendum). Fadi.
3. Contract: `type`, `profile`, `status`, statistics, management events, 5m bars
   (`AI_BARS_5M`), evaluate every 5 minutes. Yazan.
4. Exposure limits; counts after them stay unresolved until agreed. Yazan.
5. A historical economic calendar. Yazan.
6. CUSUM threshold and forward-log storage (stage F addendum). Fadi and Yazan.
