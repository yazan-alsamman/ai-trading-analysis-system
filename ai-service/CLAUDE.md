# ai-service — handoff and working rules

Owner: Fadi (AI). Talk to Fadi in **Arabic**; code, comments and docs stay in English.
Team: Yazan = backend, Rami = mobile app, Elias = website. Repo: `yazan-alsamman/ai-trading-analysis-system`.

Full design: `docs/Trading-DSS-Architecture-v0.2.pdf` (Arabic, 24 pages) and the team doc
"AI Engine Requirements and Technical Design" (claude.ai artifact
`cdedf736-ece2-4b02-a9b2-4cb9ed88044f`, updated 2026-10-21, decisions D1–D38).
Backend contract: `../docs/ai-contract.md`, `../docs/api/ai-service.openapi.yaml`.

## What we are building

A **Hybrid Intelligent Trading Decision Support System** for XAU/USD and major FX pairs.
Advisory only: it never places, changes or closes an order.

Principle: **code computes, the model scores, the LLM explains.** Every number comes from
deterministic, tested code; ML only estimates probabilities; the LLM never produces a number.

Three services inside a **stateless** ai-service (the backend stores, schedules, delivers):

| Service | Layers | Job |
| --- | --- | --- |
| Scanner | L1–L4 | On each closed bar: data quality, multi-timeframe, SMC primitives (swings, liquidity, sweep, CHoCH/BOS, FVG, displacement, sessions), candidate setups, features |
| Scoring & Decision | L5–L8 | Self-supervised candle encoder (embeddings), HMM regime (forward filtering only), meta-model + calibration → p, EV, CI, grade; abstention rules; per-user sizing; per-currency exposure |
| AI Agent | L9–L10 | Provider-agnostic LLM with tool use and images; read-only tools; RAG over the engine's own definitions; every number verified against tool output |

Endpoints today: `/v1/evaluate`, `/v1/size`, `/v1/explain`, `/health` (contract by Yazan).
Planned (v0.2, to agree with Yazan): `/v1/agent/chat`, `/v1/risk/preview` (Monte Carlo).
The placeholder `/v1/signal` in `app/main.py` stays until replaced.

## Research

Question (locked): does ML **meta-labeling** improve the after-cost expected value of SMC/ICT
setups on XAU/USD compared with the rules alone?

- H1 rules-only EV > 0 after costs (vs random entries) · **H2 (main)** rules + ML > rules only ·
  H3 encoder embeddings add value · H4 regime adds value · H5 generalises to an unseen instrument.
- H2 metric: mean R per trade after costs, valid only if yearly total R is not below rules-only.
- Experiments E0–E10 (random, rules loosened/strict, LR, LightGBM/XGBoost, MLP, +embeddings,
  +regime, all, fixed 2R, pooled, leave-one-instrument-out).
- Accuracy is never an acceptance metric. Acceptance: detection precision ≥ 90% (manual review of
  ~50 setups), Brier skill > 0, ECE < 0.05, EV difference with weekly block bootstrap,
  Deflated Sharpe, hypotheses registered with a date before the lockbox opens.

## Data rules (do not break these)

- Source: FxPro MT5 exports (M1 since 2026-10-21, bid OHLC + spread in points, 1 point = $0.01
  on XAU/USD). The XAUUSD, EURUSD and GBPUSD history exports run past 2026-01-09: read history
  only through `app.data.raw.HistoryExport`, which stops at the first bar on or after the lockbox
  start (server date) without decoding it. Never read an export file any other way.
- Server time follows **Europe/Athens** (EU DST). Convert to UTC with Europe/Athens before any use.
- Closed bars only; higher timeframes built from closed lower bars and used only after they close.
- Split (D23): dev 2012–2017 · walk-forward 2018 → 2024-06 (expanding train, 6-month tests) ·
  secondary holdout 2024-07 → 2026-01-09 (prior exposure disclosed) ·
  **primary lockbox 2026-01-10 → export date: sealed by SHA-256, never opened, plotted, loaded or
  summarised before P9.** Any code path that could read it must refuse unless an explicit
  `--open-lockbox` flag and the frozen versions are logged.
- Purge setups whose outcome window overlaps a test window, plus a 1-day embargo.
- Costs: recorded spread + max(50%, $0.10), slippage on SL fills, and a 2× cost stress run.
- Features are scale-free (ATR units, percentiles); gold went from ~$1,600 to ~$4,500.

## Strategy v1 (formal SMC interpretation; parameters tuned on 2012–2017 only, then frozen)

Sweep → CHoCH → FVG, intraday profile (context 1h/4h, entry 15m). Swing = k bars each side
(k=3 on 1h/4h, 2 on 15m), confirmed k bars later. Liquidity = unbroken confirmed 1h/4h swings +
previous trading day high/low (day = 17:00–17:00 New York), dropped after 5 days. Sweep = trade
beyond L by ≥ 0.1×ATR(14,15m) and close back within that bar or the next; > 1.5×ATR = breakout.
CHoCH within 8 bars. First FVG ≥ 0.1×ATR in the displacement. Entry = limit at the FVG proximal
edge; SL = sweep extreme + 0.1×ATR + spread; TP = nearest opposite liquidity with R in [1.5, 4].
Lifecycle: DEVELOPING → ARMED → ACTIVE → CLOSED / EXPIRED / INVALIDATED; deterministic setup id
(direction + swept level). Labels: triple barrier (TP, SL, 48 bars), realised R kept.
Strict vs loosened rules (CHoCH or BOS, FVG as a feature) is decided in P3 after counting samples.
One TP in v1 (TP1/TP2 after v1). Custom user strategies: after v1.

Exact v1 definitions and the variants registered for P3 (same-bar reclaim, prior-trend CHoCH, strict
FVG linkage, rejection audit log): `docs/MARKET_STRUCTURE_DEFINITIONS.md`. v1 changes only by a new
recorded version.

## Engineering rules

- Python 3.12, ruff (line 100). Reuse `../libs/backtest`, `../libs/indicators`, `../libs/strategies`.
- Same code in backtest and live; identical inputs + versions → byte-identical outputs.
- Every primitive and feature: unit tests on hand-built bars + an append-future-bars
  no-look-ahead test.
- Instrument-agnostic code; per-instrument specs in config. Scope: XAU/USD → EURUSD → GBPUSD,
  USDJPY, AUDUSD, USDCAD. No other metals.
- Every experiment re-runs with one command from config + data hash.
- Training on Fadi's RTX 5060 (8 GB, Blackwell: needs PyTorch built for CUDA 12.8+); production
  inference on CPU within 512 MB (the production cap in `../docs/ai-contract.md`) / 0.5 CPU.

## Phases (a phase ends only when its gate passes on evidence)

1. **P1 Data** — importer (UTC, timeframes), quality report, Dukascopy cross-check, lockbox sealing script. Gate: clean report, feeds agree.
2. P2 SMC engine — primitives + tests + ~50-setup review. Gate: precision ≥ 90%.
3. P3 Candidates and labels — builder, triple barrier, sample count, strictness decision, E0–E1. Gate: ≥ 1,000 labelled setups.
4. P4 Meta-model — LR, GBM, MLP, calibration, SHAP, E2–E4. Gate: Brier skill > 0, ECE < 0.05.
5. P5 Deep layers — encoder, HMM, E5–E8. Gate: H3, H4 documented.
6. P6 Live scanner and risk — lifecycle, sizing, exposure, notifications. Gate: < 10 s, live = backtest.
7. P7 AI Agent — tools, knowledge base, grounded explanations, chart images. Gate: zero invented numbers.
8. P8 More instruments — EURUSD then majors, E9–E10. Gate: H5 documented.
9. P9 Freeze, open lockbox once, paper trading ≥ 3 months or 100 signals.
10. P10 Thesis, evaluation report, model card, demo, reproducibility.

**Status (2026-10-24):** design locked; phase 0 reset done (`docs/AUDIT-2026-10-21.md`): all
pre-v0.2 work removed. P1 in progress: tasks 1 (layout), 2 (lockbox sealed,
`docs/lockbox/MANIFEST-2026-10-21.json`), 3 (importer: `python -m app import`, store in
`data/processed/<SYMBOL>/{m1,5m,15m,1h,4h,D1}.parquet`, untracked) and 4 (quality report:
`python -m app quality`, `docs/data_quality/`) and 5 (Dukascopy cross-check: `python -m app
dukascopy download|compare`, all instruments pass 2012-2025) done. P1 gate passed (Fadi, 2026-10-22).
P2 in progress: tasks 1 (primitives: `app/smc/primitives.py`, parameters in
`app/config/strategy.toml`), 2 (events: `app/smc/events.py`) and 3 (detector: `python -m app smc
detect`, `docs/phase2/patterns_XAUUSD.md`) and 4 (review tool: `python -m app smc review
sample|score`) done. XAUUSD 2012-2017: 198 Sweep → CHoCH → FVG patterns (104 buy, 94 sell, 22-40 a year).
**P2 gate not passed (v1)**: 43/50 = 86% (95% 74-93%) against 90%; review by Claude, adopted by Fadi,
borderline cases counted as no (`docs/phase2/review/REVIEW.md`; state this in the thesis). Cause: thin
sessions and gold's daily reopen. V5-S built (`--rules V5-S`):
145 patterns. **P2 gate passed with V5-S** (Fadi's review, 46/50 = 92%, 95% 81-97%): V5-S is the
rule set for P3. Its rejections point at the FVG link (V3-L) and CHoCH clarity (V2-T), both P3 variants.
P3 in progress: task 1 (setup builder: `python -m app setups build --rules V5-S`,
`docs/phase3/`) done. Trade choices (Fadi, 2026-10-22): limit entry waits 8 bars; nearest liquidity
beyond 4R is rejected, not capped; spread = mean of the decision bar. XAUUSD V5-S 2012-2017: 104 armed
setups (v1: 140). Task 2 (lifecycle and triple-barrier labels: `python -m app setups label`) done:
V5-S 42 labelled setups in 2012-2017 (v1: 59), about 7 a year; 19% TP before SL, mean net R -0.14
(2x costs -0.31). The P3 gate (1,000 labelled setups) is out of reach for strict rules on gold alone.
Task 3 counts (`python -m app setups count`, counts only, 2012 to 2026-01-09, six instruments):
v1 543, V5-S 377, L1 (FVG optional, market entry) 1,634 labelled setups (gold 134 / 88 / 387). Only
L1 pooled over the six instruments passes 1,000. **Decision (Fadi, 2026-10-22): L1, pooled over the six
instruments.** The research question stays on XAUUSD (train on all six, report XAUUSD and per
instrument). Open: a cost model for the five pairs. L1 review sample drawn (`docs/phase3/review_L1/REVIEW.md`, seed 410733, 50 patterns,
five instruments x with / without FVG; AUDUSD has no development data); eye review passed (Fadi 50/50; Claude's second opinion
agrees, 5 same-bar news patterns borderline: `REVIEW_claude.md`).
Task 4 (`python -m app research baselines`, `docs/phase3/baselines.md`) done: FX costs set (gold
formula, 0.2 pip minimum and SL slippage). Development period, five instruments: E1 (L1) 378 trades,
mean net R -0.046 vs matched random E0 -0.063 (difference +0.017, 95% -0.10 to +0.13, p = 0.36):
**H1 not supported on 2012-2017**; 53% of E1 trades end at the 48-bar horizon. P3 gate (1,000
labelled, L1 pooled 1,634) passed on counts; the design also asks for E1 on walk-forward.
Horizon trials 96 / 192 bars (Fadi, 2026-10-23): no edge either (p 0.46 / 0.60); horizon stays 48.
Every performance look is logged in `docs/phase3/TRIALS.md` (10 trials; N = 10 for the Deflated Sharpe).
P4 started (2026-10-23, branch `ai/p4-meta-model`, stacked on #55). Label as the design (§9.2): y = 1 for TP
first, 0 for SL or horizon; realised R kept. Task 1 (L4 features and dataset: `python -m app features
build`, `app/features/setup_features.py`, `docs/phase4/dataset_L1.md`) done: 1,436 labelled L1 setups,
six instruments, 2012 to 2024-06, 37 scale-free features, no-look-ahead test. FX data start 2016
(AUDUSD 2018). Found: EURUSD recorded spread is zero on 54-63% of bars in 2021-2023 (other pairs
much lower then too), so costs there are understated; 4 patterns span a weekend (sweep Friday,
CHoCH Sunday evening); news timing not available yet.
Costs (Fadi, 2026-10-23): no spread floor; the cost model stays (median total cost 0.04-0.05R on FX,
0.09R on gold); feature `tp_usd_min_lot` added (Fadi: a target under $3-4 at 0.01 lot is no trade).
**Rules frozen (L1, 2026-10-23).** Task 2 (walk-forward protocol: `python -m app research
walkforward`, `app/research/walkforward.py`) done: 13 six-month test windows 2018-01 to 2024-06,
expanding train from 2012, purge + 1-day embargo by exit time, last 25% of train as the calibration
slice (Platt or isotonic by Brier), Brier skill vs the train base rate, ECE (10 bins). E1 on the
walk-forward test windows: 1,058 trades, TP 11.1%, mean net R -0.047 (95% -0.115 to +0.020).
L1-M (Fadi, 2026-10-23; trial 6, registered before the run, `docs/phase4/L1-M.md`): opposite
signal exits, same-direction signal extends (cap 192 bars). No difference from L1: walk-forward
mean net R -0.047 for both, E1 - E0 p 0.54. L1 stays.
**P4 amendment registered 2026-10-23 before any fit** (`docs/phase4/PREREG_P4.md`, approved by Fadi
as written): label y = 1{net R > 0} weighted by |net R| (replaces TP first), Platt only, EV rule
p*m1 + (1-p)*m0 > 0 with means from train, minimum 30 accepted, H2 decided on E2 alone (pooled,
XAUUSD named secondary), pooled debiased ECE on 10 equal-mass bins, E0 + meta control arm.
Task 3 (`python -m app research meta --model lr|lgbm|mlp [--label tp] [--arm context|e0]`,
`app/research/meta.py`; `python -m app features e0`) done, trials 7-10 (`docs/phase4/meta_*.md`):

| Trial | Model | Accepted | Mean net R acc. (all -0.047) | BSS |
| --- | --- | --- | --- | --- |
| 7 | **E2 LR (primary)** | 209 | -0.054 | -0.011 |
| 8 | E3 LightGBM-small | 226 | -0.144 | -0.022 |
| 9 | E4 MLP | 249 | -0.093 | -0.013 |
| 10 | E2, design label | 335 | -0.145 | -0.001 |

**H2 not supported; P4 gate not passed** (Brier skill < 0 for every model; debiased ECE 0.015-0.032
passes). E2's inner CV shrinks every coefficient to zero in 9 of 13 windows, so whole windows are
accepted or rejected. Control arms for LR (§7, not trials): context features only gain -0.037;
E0 (20 random replications) gains 5th / median / 95th -0.085 / -0.018 / +0.103; E1 with 38 features
-0.007 (about the 61st percentile of random): **the SMC pattern adds no information** beyond
session, volatility and cost context. Thesis notes: the yearly condition of H2 passes trivially for
a filter that trades less in losing years; label uniqueness median 1.0 (no AFML weights needed).
Open: LightGBM and MLP control arms (registered, not needed for H2); what P4's failed gate means
for P5 (Fadi).
Clock: GBPUSD, USDJPY, AUDUSD, USDCAD history is stamped on shifted clocks in some periods;
the importer detects and corrects them (`app/data/clock.py`, segments in `import.json`,
`docs/data_quality/README.md` §1). The rule was set on the same data: say so in the thesis.
XAUUSD and EURUSD need no correction. XAUUSD before 2011-08 is 1 h off and not corrected: never
use it (it is before the development period anyway).

Layout: `app/main.py` (service), `app/config/` (instruments + D23 splits, TOML), `app/cli.py`
(`python -m app <command>`), `app/lockbox.py`, and one package per layer: `data` (L1), `smc` (L2),
`setups` (L3), `features` (L4), `scoring` (L5–L8), `agent` (L9), `research`.

## First tasks (P1)

1. New ai-service layout (package, config, CLI), keeping `/health` and the placeholder working.
2. Lockbox sealing script: hash the 2026 export files (SHA-256), write a dated manifest, never parse contents.
3. FxPro MT5 importer → UTC → research store (Parquet), with timeframes 5m/15m/1h/4h/D1 from M1.
4. Data-quality report (gaps vs expected weekend/daily break, OHLC consistency, jumps, spread stats per year/hour).
5. Dukascopy cross-check of a sample (return correlation per year).

## Open questions

- Agent data access: backend read-only endpoints vs data passed in the request (Yazan).
- Which vision-capable LLM to start with (Fadi). Exact end date of the 2026 export (Fadi).
- FxPro production route: cTrader Open API or Windows MT5 pusher (Yazan). Free historical calendar (Yazan).
