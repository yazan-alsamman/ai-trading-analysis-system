# AI Side — Project Context (living record)

This is a short, version-controlled memory for the AI work. Update it whenever a decision is made or an
experiment finishes. The detailed evidence is in [REPOSITORY_AUDIT.md](REPOSITORY_AUDIT.md). The shared copy
of the audit is the doc "AI Trading Engine — Repository Audit"
(https://claude.ai/artifact/XJCecjPXZeAYx7JSSK3Q8L).

_Last updated: 2026-10-19 (Phase 1 history import added). Full-platform audit of `main` @ `5b91175`. The remote `main` has since moved to
`593cfbf`, which has not been audited._

## Purpose and scope

The AI side analyses gold (XAU/USD) first, then forex.

- **Signals:** it finds candidate setups and estimates a calibrated P(TP before SL within a horizon). It
  recommends BUY / SELL / NO TRADE only through a documented, deterministic decision and risk layer.
- **Phasing:** signals come first, then Paper Trading. Live execution is a separately authorised future phase.
  The web docs say AI 19, "Automated Trading", is cancelled.
- **Timeframe:** Scalping is the stated initial priority. The exact timeframe and horizon are still open (see
  below).

## Current state (facts)

- **ai-service is a placeholder.** `POST /v1/signal` always returns `hold`, and nothing calls it.
  `ai_service_url` in the backend config is never read. No manifest contains an ML or LLM dependency.
- **There is no real market data in the system.** No collector or adapter exists. Candles come only from
  random-walk seed CLIs or manual admin backfill.
  - Local, untracked MT5 exports exist in `data/raw/`, exported by Fadi from the team's FxPro MT5 account:
    - `XAUUSD_M5_mt5.csv`: M5 from 2012-04-23 to 2026-01-09, with tick volume and spread (in points;
      1 point = $0.01).
    - `EURUSD_M5_mt5.csv`: M5 from 2000-05-30 to 2026-02-13, no spread column, and its first data row is
      malformed.
  - Timestamps are broker server time. **Corrected 2026-10-19 by the history importer:** the server clock
    follows **EU** daylight saving (`Europe/Athens`: UTC+2 in winter, UTC+3 from the last Sunday of March
    to the last Sunday of October), not "New York time + 7h". The two agree except in the US/EU mismatch
    weeks (second Sunday of March → last Sunday of March, last Sunday of October → first Sunday of
    November), when server time is New York + 6h: the daily break moves to 23:00–00:00 server time, the
    weekly open to Monday 00:00, and the 08:30 New York jobs report sits at 14:30 server time. Outside
    those weeks the weekly open is Monday 01:00 and the daily break about 23:55–01:00 server time
    (17:00–18:00 New York). The importer converts to UTC; see the experiments log.
  - The UTC research store is built with `python -m app.data.importer` (in `ai-service/`): Parquet in
    `ai-service/data/processed/<SYMBOL>/{5m,15m,1h,4h}.parquet` (untracked) and the report in
    `ai-service/docs/data_quality/`.
  - XAUUSD median bar spread by year: about 40 points in 2012–2015, 5 in 2021–2022, 14–15 in 2024–2025.
    The MT5 bar spread is the minimum spread within the bar, so it understates real costs; treat it as a
    lower bound.
- **The live rule-signal engine runs, with gaps.**
  - It has no data-quality gate: it evaluates bars whose 1m data is incomplete, never retries a bar with
    missing data, and does not catch up after downtime.
  - Signals have no lifecycle (no status, expiry or outcome).
- **FX and gold semantics are missing.**
  - Instruments carry no pip, tick or contract size, and no sessions.
  - Sizing treats the account balance as quote currency, so USD/JPY plans come out about 150× too small.
  - Costs are crypto bps, and annualisation assumes markets trade 24/7.
- **The reusable deterministic libraries pass their tests** (re-run 2026-10-19):
  - `libs/indicators`: 21 indicators with TA-Lib parity; 221 passed, 1 skipped.
  - `libs/strategies`: 6 rule strategies plus Builder and Composite; 187 passed.
  - `libs/backtest`: engine, `plan_trade`, and `run_backtest` for any signal source; 131 passed.
- **The news ingestion API for the AI side is ready.** `/api/v1/ingest/news` and `/ingest/news/sentiment` use
  an API key with the `news:write` scope.
- **The web client expects contracts nothing serves yet.** It expects `Opportunity` and `PredictionRecord`
  (`web/src/domain/`). In production everything except auth is simulated (`VITE_DATA_SOURCE=demo`).
- **Platform security issues that affect AI outputs:**
  - Signals from private custom strategies are visible to all users.
  - Production runs on plain HTTP.
  - WebSocket sessions are never re-authorised.
- **The production budget for ai-service is tight:** 256 MB and 0.5 CPU on a shared 2 vCPU / 8 GB VPS.
  Training happens offline.

## Key file map

| What | Where |
| --- | --- |
| Candle storage, reads and upserts | `backend/app/services/market_service.py`, `backend/app/models/candle.py` |
| Live signal engine (the pattern to copy for AI inference) | `backend/app/services/signal_engine.py`, `backend/app/tasks/signals.py` |
| Closed-bar selection and the `no_data` path (the data-quality gap) | `signal_engine.py:53-61, 358-364`, `tasks/signals.py:26, 215` |
| Trade plans, sizing and risk templates | `libs/backtest/trading_backtest/risk.py` (`plan_trade`), `libs/backtest/trading_backtest/config.py` (`Sizer`), `backend/app/services/risk_service.py` |
| Instrument model (no contract specs yet) | `backend/app/models/instrument.py`, `backend/app/services/seed_service.py` |
| Backtest engine and metrics | `libs/backtest/trading_backtest/{engine,metrics,api}.py` |
| AI client contract (web) | `web/src/domain/opportunity.ts`, `web/src/domain/predictions.ts`, `web/docs/API_INTEGRATION.md` |
| News ingestion for the AI side | `docs/news-ingestion.md`, `backend/app/news/service.py` |
| Deployment rules and limits | `docs/deployment.md`, `infra/deploy/docker-compose.prod.yml` |

## Confirmed decisions

_Record each one as: date, decision, rationale, alternatives considered._

- **2026-10-19: the analytical core must contain a trained ML or neural-network model.**
  - Rationale: this is a project requirement ("it had to have AI"). An LLM used only for explanations does
    not satisfy it.
  - Consequence: a purely deterministic rule engine (requirements Q&A option A) is not enough on its own.
    The direction is now option B (predictive) or C (rules propose candidates, a model scores them).
  - Alternatives considered: LLM-only "AI" (rejected as too thin for the requirement).
  - Model family (gradient boosting vs. a neural network, etc.) is not fixed; it will be chosen by comparing
    candidates under the same walk-forward evaluation.
- **2026-10-19: the engine is a hybrid (option C), built in stages.**
  - Rule strategies (built-in ICT/SMC and, later, user-defined ones) generate candidate setups with entry, SL
    and TP. A trained model estimates each candidate's probability of success (meta-labelling). A setup is
    signalled only if its expected value after costs clears a threshold; otherwise the answer is NO TRADE.
  - Staging: the traceable rule engine with backtest statistics comes first; the model layer is added next
    and kept only if out-of-sample results beat the raw rules after costs.
  - Rationale: the only option that meets the ML requirement while keeping traceable, explainable,
    strategy-based setups and the user-defined-strategy goal.
  - Alternatives considered: A (rules only; fails the ML requirement), B (pure prediction; weak
    explainability, poor fit for user-defined strategies).
  - Open consequence: a user-defined strategy has no trained model until it has enough historical
    candidates; until then it reports rule compliance plus backtest statistics only.
- **2026-10-19: two user-selectable trading profiles, Scalping and Intraday.**
  - Scalping: entry on 1m–5m, horizon of minutes. Intraday: context on 1h/4h, entry on 15m, horizon of hours.
    Swing (Daily/4h) is out of scope for v1.
  - Proposed (not yet confirmed): each profile is a configuration of context and entry timeframes, horizon,
    minimum R:R and cost model, with its own labels, model and evaluation; both run on closed 1m bars
    aggregated upward, so no tick data is needed for v1.
  - Risk: gold spreads (about $0.2–0.5, wider around news) are large relative to scalping targets, so the
    Scalping profile may show no edge after costs.
  - **Confirmed: Intraday is built and evaluated first.** The full pipeline (data → rules → model →
    evaluation) is completed on Intraday; Scalping is then added as a second profile on the same
    infrastructure.
  - Proposed default (not yet confirmed): a profile that shows no out-of-sample edge after costs stays
    available, with its real statistics and a clear warning, rather than being disabled.
- **2026-10-19: market data — $0 budget, FxPro account available, Yazan builds the data adapters.**
  - Data budget is $0: only free sources.
  - The team has a **real (live-money) FxPro MT5 account**. It is the candidate live feed and source of
    history. Only the investor (read-only) password may be used by any service; the master password must
    never be stored in code, config or on the server, and the system never places orders.
  - Data adapters (F01) are a backend task owned by Yazan. The AI side owns the data contract it needs
    (fields, bid/ask, UTC timestamps, closed-bar guarantee, gap flags, quality report).
  - Proposed (not yet confirmed): Dukascopy for multi-year 1m bid/ask history; FxPro for live and recent
    history; a reconciliation step that measures and documents the price and spread difference between them.
  - Risk (still open; Yazan's call): the MetaTrader5 Python package needs a running Windows terminal, while production is a Linux VPS
    with a tight memory budget. Alternatives are FxPro's cTrader Open API (cross-platform) or a Windows
    machine that pushes closed bars to a backend ingest endpoint.

- **2026-10-19: v1 ships one precisely defined ICT/SMC strategy, plus simple baselines.**
  - The SMC strategy is the candidate generator for the model. Existing rule strategies in
    `libs/strategies` serve as baselines, to measure whether SMC adds anything.
  - Alternatives considered: several SMC strategies (each would be weakly defined and validated); classical
    technical strategies only (strays from the project vision).
  - Constraint: **no one on the team trades ICT/SMC.** Rules must be derived from public sources and written
    as formal, parameterised, closed-bar definitions in a strategy spec. Detection is checked by a manual
    chart review of a sample, and parameters are fixed before any test-set evaluation.
  - **Setup pattern (confirmed): liquidity-sweep reversal, Sweep → CHoCH → FVG.**
    1. Price trades through a significant high or low (a 1h/4h swing, or the previous day's high or low)
       and closes back inside.
    2. A CHoCH forms on 15m in the opposite direction.
    3. Entry is at the first FVG created by that displacement.
    4. SL goes beyond the sweep extreme.
  - **TP and success (confirmed):**
    - TP is at the nearest significant opposite liquidity (swing high or low).
    - The setup is rejected if R:R is below 1.5, and the TP is capped at 4R (initial values, fixed before
      test-set evaluation).
    - Label: TP is hit before SL within the horizon. A trade with neither is closed at the horizon's end. If
      a single bar touches both, it counts as SL hit. R is a model feature and part of the EV calculation.
  - Deferred to after v1 (confirmed): multiple TPs with partial closes.
  - Proposed (not yet confirmed): a fixed 2R target run as an ablation against the liquidity-based TP.
  - **Entry (confirmed):** a limit order at the proximal edge of the FVG. Entry at the FVG midpoint
    (consequent encroachment) runs as an ablation.
  - **Signal lifecycle (confirmed):**
    `DEVELOPING → ARMED → ACTIVE → CLOSED (TP / SL / TIMEOUT)`; `DEVELOPING → DISCARDED`;
    `ARMED → EXPIRED / INVALIDATED`.

    | State | Meaning |
    | --- | --- |
    | DEVELOPING | A sweep happened; waiting for the CHoCH. Shown to users as a "watch", clearly marked "not a signal". |
    | ARMED | All rules met and the model's EV clears the threshold. This is the official signal. |
    | ACTIVE | Price returned to the entry level (the limit order would have filled). |
    | CLOSED | TP, SL or timeout, with the outcome recorded. |
    | EXPIRED | Price did not reach the entry within 8 bars of 15m (2 hours). |
    | INVALIDATED | Price reached the SL or TP level before the entry filled. |

    - The maximum holding horizon is 48 bars of 15m (12 hours); the trade is closed at the end of it.
    - Duplicates: each setup has an ID derived from its direction and the swept liquidity. No new setup in the
      same direction is issued while one built on the same liquidity is ARMED or ACTIVE.
    - Unfilled setups (EXPIRED / INVALIDATED) are kept and labelled as unfilled, never counted as wins or
      losses.
- **2026-10-19: confidence and abstention.**
  - Users see three values:
    1. A calibrated probability of TP before SL, checked out of sample with a reliability diagram, Brier
       score and ECE.
    2. EV in R after costs: `p × R − (1 − p) × 1 − costs`. EV is what decides a signal.
    3. An A/B/C grade derived from EV with fixed bands, for quick reading only.
  - A setup becomes ARMED only if all of these hold; otherwise the answer is NO TRADE with the reason:
    1. Every strategy rule is met.
    2. The lower bound of the EV confidence interval is above 0.
    3. The current spread is within its normal range.
    4. No high-impact economic event is within ±30 minutes.
  - The news filter is in v1. It needs a free economic calendar, both live and **historical** (so the same
    filter is applied in backtests); the source is an open question for Yazan.
  - Before the model exists (rules-only stage), users see the strategy's historical statistics (win rate,
    mean R, trade count, confidence interval), labelled as strategy history, not an estimate for the setup.
  - The session (Asia / London / New York) is a model feature, not a hard filter, to keep the sample large.
  - Alternatives considered: trend continuation via Order Block (the least well-defined SMC concept); an
    Asian-range sweep (the most objective, but at most one candidate a day, roughly 700–1,300 in total).

- **2026-10-19: deadline and acceptance framework.**
  - Deadline: **no fixed date**; the final submission may be about a year away. There is no weekly plan:
    work proceeds by phases and milestones, implemented with Claude Code. The full vision stays in scope,
    built in stages (Intraday first; Scalping, user-defined strategies, scenarios and sentiment later).
  - Acceptance criteria are judged on five separate levels (exact thresholds to be set later):
    1. Engineering correctness: unit tests per SMC primitive, an automated no-look-ahead test, and a manual
       chart review of about 50 detected setups.
    2. Model quality, out of sample: Brier skill score above 0 against the base rate, and ECE below a set
       threshold.
    3. Trading value: EV after costs of model-filtered signals beats the raw rules, with bootstrap
       confidence intervals. Profitability is not a success criterion.
    4. Operations: a signal within seconds of bar close; abstain on bad data; a live paper-trading period
       compared with the backtest.
    5. Explanations: zero fabricated numbers, checked automatically against engine output.
  - **The "70%" requirement, clarified by Fadi:** it is not a win rate.
    - The target is **above 90%** for pattern and zone detection accuracy and for statistical confidence.
    - A win rate of 40–50% is acceptable, because profit comes from R:R (average win larger than the
      loss).
    - The system as a whole must be profitable after costs.
  - Proposed operationalisation (not yet confirmed):
    1. Detection precision of at least 90% on a manually reviewed sample, judged against the written
       definitions.
    2. Statistical claims at a 95% confidence level.
    3. Profitability means the bootstrap 95% CI of out-of-sample EV after costs lies above 0. This is a
       hypothesis to test, not something that can be guaranteed.
  - Reference point: random entries at 1.5R win about 32% after spread (see the experiment log), so a 40–45%
    win rate is a meaningful edge to demonstrate.
- **2026-10-19: risk management and position sizing are in scope (new requirement).** Users enter their
  account details, and the engine sizes positions in lots from the account balance and risk. Sizing is
  deterministic (it extends `plan_trade` / `Sizer`), never decided by the model.
  - **Risk engine (confirmed):**
    - No fixed preset percentages. Each user sets their own risk appetite: risk per trade and loss limits,
      high or low.
    - For every signal, the engine computes from that user's account and settings: lot size, contract
      size, entry, SL and TP.
  - **Advisory only (confirmed):** the system never opens, modifies or closes trades. Limits produce warnings
    and pause new signals for that user; they are not enforced on the broker account.
  - Proposed (not yet confirmed):
    - No hard cap on the user's risk. Above a threshold (for example 5% per trade) the engine shows an
      explicit warning, including the drawdown after a typical losing streak.
    - "Suits the account" means feasibility, judged from balance, leverage, minimum lot (0.01 = 1 oz of
      gold), lot step and required margin. If the minimum lot risks more than the user's chosen amount, or
      the margin is insufficient, the engine warns and shows no size.
    - Account currency is USD only in v1, with the design ready for others.
- **2026-10-19: LLM integration.**
  - The LLM sits behind a provider-agnostic interface.
  - Development uses a free tier. A small monthly paid budget is possible for the final demo.
  - Explanations are in **Arabic and English from the start**.
  - Guardrails: the LLM sees only the engine's structured output. Every number in an explanation is
    verified automatically, and if verification fails a fixed text template is shown instead.
  - Proposed staging (not yet confirmed): signal explanations and grounded Q&A in v1; "what if" scenarios
    and natural-language strategy parsing later.
- **2026-10-19: model features and model comparison.**
  - **v1 features:**
    1. Setup geometry: R, SL distance in ATR, FVG size, sweep depth, CHoCH displacement.
    2. Market context: 1h/4h trend, volatility regime, distance to the previous day's high and low,
       session, day of week.
    3. Cost: current spread against its normal level.
    4. News timing: time to the next high-impact event and since the last one.
  - **Ablation:** cross-asset features (USD strength via EURUSD, daily US yields from FRED).
  - **Later, only if shown useful:** sentiment.
  - Rule: every feature uses only data available before the decision time, enforced by the no-look-ahead
    test.
  - **Models compared on the same features and the same evaluation:** base rate and raw rules, logistic
    regression, gradient boosting (LightGBM or XGBoost), and a small MLP (which satisfies the ML-or-NN
    requirement through a fair comparison).
  - Raw-candle neural networks (LSTM, Transformer) are deferred until after v1: a few thousand samples is
    too few.
  - Training runs on a local CPU; Colab is the fallback.
- **2026-10-19: validation protocol.**
  - **Time split:**

    | Period | Dates | Use |
    | --- | --- | --- |
    | Development | 2012–2017 | Tune SMC detector parameters, then freeze them |
    | Walk-forward | 2018 → 2024-06 | Train and evaluate the model: expanding training window, 6-month test windows |
    | Lockbox | 2024-07 → 2026-01 | **Opened exactly once**, after everything is frozen. These are the reported results |
    | Paper trading | Live, after the freeze | Confirm live performance matches the backtest |

  - **Leakage control:** purge any setup whose outcome window (8-bar entry window + 48-bar horizon, about
    14 hours) overlaps the test period, plus a 1-day embargo.
  - **Costs:**
    - Recorded spread plus the larger of +50% or $0.10, because MT5 records the in-bar minimum.
    - Slippage on SL fills.
    - A sensitivity run at 2× costs, reported even if it removes the edge.
  - **Regime changes:** features are scale-free (ATR units, percentages), and results are reported per year.
  - **Paper trading:** at least 3 months or 100 signals, whichever is later. A rules-only version may start
    early, in parallel with model work.
- **2026-10-19: service boundary — ai-service is stateless and owns all analytical logic (option A).**
  - **Backend (Yazan):** ingests data, schedules, stores, and sends notifications. On each bar close it
    sends ai-service a candle window plus the currently open setups, and persists what comes back.
  - **ai-service (Fadi):** returns new setups, lifecycle transitions for open setups, model probabilities and
    EV, and the computed position size.
  - The same code runs in backtests and live, so historical and live behaviour match. The backend contains
    no trading logic.
  - Yazan is available to co-write an explicit API contract (inputs, outputs, errors).
  - Alternatives considered: a fully independent ai-service with its own DB and scheduler (duplicated
    infrastructure, two sources of truth, memory pressure); everything inside the backend (strategy logic
    split across two owners, harder to keep backtests and live identical).

- **2026-10-19: backend handoff doc for Yazan.** The doc "Backend Changes for the AI Engine"
  (https://claude.ai/code/artifact/dc7486a5-4da8-4f08-95ca-4780e5b09357) covers:
  - the FxPro feed with UTC conversion and spread, and the data-quality gate;
  - instrument specs and the economic calendar;
  - a draft ai-service API (`/v1/evaluate`, `/v1/size`, `/v1/explain`);
  - the tables `ai_setups`, `ai_setup_events` and `ai_model_versions`;
  - scheduling, catch-up and user risk settings;
  - security fixes;
  - a task list B1–B12.

  Multi-year training data stays as files in ai-service, not in the database.
- **2026-10-19: failure handling (confirmed, as in the backend doc).**
  - Data-quality gate before every evaluation. A stale feed makes the system "degraded": no new signals,
    open setups frozen.
  - Missed bars are replayed in order after downtime. Setups that expired meanwhile are stored as EXPIRED
    and never sent as late alerts.
  - **Model outage: no ARMED signals.** DEVELOPING setups still show, with "model unavailable".
  - LLM failure: the fixed template is shown instead.
  - Every signal stores the strategy, model and feature versions, the feature values and the data window
    ID, so it can be reproduced exactly.
  - Live monitoring tracks rolling metrics over the last 50 closed signals. It alerts the developer when
    calibration drifts and never retrains automatically.
- **2026-10-19: user-defined strategies (later phase; design confirmed now).**
  - The pipeline is: text → LLM translation → Builder JSON → validator → clarifying questions → user
    confirmation → mandatory backtest → activation.
  - The existing JSON Builder (`libs/strategies/trading_strategies/builder.py`) is extended with SMC parts
    (swing, sweep, CHoCH, BOS, FVG), sessions, and entry/SL/TP/R:R rules. The SMC detectors are built
    once, as composable parts, and shared with the built-in strategy.
  - **The LLM only translates** into the schema. It never analyses markets or executes strategies.
    Anything outside the available parts is refused with an explanation.
  - Ambiguity becomes a question to the user with a suggested default; nothing is guessed silently.
  - Signals from a custom strategy show rule compliance plus historical statistics. A strategy gets its
    own model only once it has enough historical candidates (for example 300 or more).
  - Custom strategies and their signals are private to their owner (requires P0-04).
  - Editing is through text and questions; a visual rule editor comes later. Users do not edit raw JSON.
- **2026-10-19: "what if" scenarios.**
  - The LLM only translates the question into a structured request: price level, direction and profile.
    It asks when the question is ambiguous.
  - The engine analyses the present state at that level: the liquidity there (1h/4h swings, previous
    day's high and low), the higher-timeframe trend, and upcoming events.
  - The answer is a **conditional plan, not a signal**:
    - what is observed now;
    - the conditions needed for a setup;
    - approximate SL, TP and R:R;
    - what invalidates the idea.
  - **No probability or EV** for hypothetical setups, because the features do not exist yet.
  - If there is no meaningful level at that price, the engine says so plainly.
  - Every statement is labelled as an observed fact, a rule-based interpretation, a statistical estimate or
    an unconfirmed hypothesis.
  - **"Watch it for me" is in scope:** the user subscribes to a scenario and is alerted only if a real setup
    reaches ARMED there.

- **2026-10-19: academic deliverables and the spec.**
  - The eight deliverables are confirmed:
    1. AI chapter;
    2. evaluation report;
    3. model card;
    4. paper-trading log;
    5. detector review;
    6. explanation audit;
    7. live demo;
    8. reproducibility.
  - The report is written in **Arabic and English**.
  - The requirements Q&A is complete. The full spec is in [AI_ENGINE_SPEC.md](AI_ENGINE_SPEC.md), which is
    a copy of the shared doc "AI Engine Requirements and Technical Design"
    (https://claude.ai/code/artifact/cdedf736-ece2-4b02-a9b2-4cb9ed88044f).
  - Open: whether the university requires a report template, a literature review or a length.

## Earlier proposed plan (superseded by AI_ENGINE_SPEC.md)

_Kept for history. The confirmed phases and gates are in [AI_ENGINE_SPEC.md](AI_ENGINE_SPEC.md)._

The roadmap had seven phases, each gated by evidence; see REPOSITORY_AUDIT.md §11–12.

| Phase | Name | Backlog items |
| --- | --- | --- |
| 0 | Decisions and security | P0-04, P0-05, P0-06 |
| 1 | Trustworthy data | P0-01, P0-02, P0-03, P1-02 |
| 2 | Reliable rule signals with lifecycle and outcomes | P1-03, P1-05 and others |
| 3 | Evaluation and research | walk-forward harness, baselines, ICT/SMC primitives |
| 4 | ML in the loop | — |
| 5 | Paper Trading (can follow phase 2) | — |
| 6 | Assistant and natural-language strategies | — |

**Recommended first task:** a provider-agnostic historical candle importer with a data-quality report,
used to load XAU/USD 1m history (§14).

**Proposed AI design:**

1. **Outcome:** triple-barrier labels using `trading_backtest` semantics: entry at the next open, ATR stop,
   R-multiple target, stop-first on ambiguous bars, an N-bar horizon, and per-instrument spread costs.
2. **Models:** baselines first (base rate, raw rule strategies, logistic regression). Then gradient boosting,
   possibly as meta-labelling of rule candidates. Calibrate on a chronological hold-out.
3. **Validation:** walk-forward with purge and embargo; Brier score, log loss, ECE and a reliability diagram;
   trading metrics after costs through `tb.run_backtest`; ablations.
4. **Decision:** trade only if EV in R after costs is above a threshold and the lower probability bound is
   above break-even. Otherwise NO TRADE. SL, TP and size always come from `plan_trade`, never from the model.
5. **Serving:**
   - ai-service is stateless and stores no data.
   - A backend Celery task loads the closed-bar candles after each bar close, calls `AI_SERVICE_URL`, and
     stores the result in new `predictions` and `model_versions` tables.
   - A resolver task records the outcomes.
6. **Sentiment / LLM:** later, and only if ablations show value. FinBERT is scored offline and pushed through
   the ingest API. An LLM may explain structured evidence, but it never produces numbers.

## Known risks

- No data yet. Every result on the random-walk seed data is meaningless.
- The live engine has no data-quality gate, catch-up or signal lifecycle.
- Sizing is wrong for non-USD-quoted pairs, and there is no contract specification.
- Annualisation assumes 24/7 markets (Sharpe is inflated by about 1.19× for FX and gold), and the cost model
  is crypto bps with no spread.
- Real-time aggregates include the forming bar, so feature pipelines must cut at the last closed bar.
- News timestamps need point-in-time handling (`fetched_at`, not `published_at`).
- The Feature 12 spec is not in the repo, and the symbol and universe lists differ between backend and web.
- The production compute budget is tight.

## Open questions

Answered on 2026-10-19 (see Confirmed decisions):
- Timeframe and horizon: Intraday first, with entry on 15m and a 48-bar horizon.
- Data source: FxPro, with the price on bid plus the spread.
- Adapters: a backend task.
- Training compute: a local CPU.
- Signal semantics: the lifecycle.

Still open:

1. Can you add the **Feature 12 specification** and the **F-task list** (F01…F19, AI 13/18/19) to the repo?
2. **Instrument universe beyond gold:** which FX pairs come later? Is crypto still in scope anywhere?
3. **FxPro connection for production:** cTrader Open API or a Windows MT5 pusher (Yazan).
4. **Historical economic calendar:** which free source (Yazan).
5. **University requirements:** is there a required report template, literature review or length?
6. **FVG timing (Fadi), after gate 2b failed on v3:** keep the displacement reading (the gap
   belongs to the move that broke structure, up to 6 bars before the CHoCH), or require the
   strict order (the gap forms on or after the CHoCH bar), which is a new rule set (attempt 7)?

## Experiments log

### Phase 2 rule-variant attempts (multiple-testing record)

Every variant tried on the development period is listed here, including the ones that are not
kept. This is the count of attempts for the final report. The walk-forward period is counted, not
scored.

| # | Date | Variant | Change | Closed trades before lockbox | Dev trades | Dev win rate | Dev mean net R (95% CI) | Report |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2026-10-19 | baseline | Spec's initial rules | 149 | 71 | 21.1% | −0.065 (−0.35 to +0.22) | [rules_only](phase2/rules_only.md) |
| 2 | 2026-10-19 | A | A new extreme extends the sweep while depth ≤ 1.5 ATR, instead of discarding | 178 | 87 | 21.8% | −0.084 (−0.34 to +0.17) | [variant_A](phase2/variant_A.md) |
| 3 | 2026-10-19 | AB | A, plus Asian (20:00–00:00 NY) and London (02:00–05:00 NY) session highs and lows as levels | 297 | 143 | 26.6% | −0.045 (−0.26 to +0.18) | [variant_AB](phase2/variant_AB.md) |
| 5 | 2026-10-19 | AB5F | AB5, plus: the FVG's third bar must be the CHoCH bar or one of the 6 entry bars before it (counted in bars). Sweep, CHoCH, entry, SL and TP unchanged | 843 | 384 | 27.3% | **−0.257 (−0.40 to −0.11)** | [variant_AB5F](phase2/variant_AB5F.md) |
| 4 | 2026-10-19 | AB5 | AB with 5m entry bars (same 1h/4h and session levels). Bar windows scaled to the same clock time: CHoCH and entry windows 24 bars (2 h), horizon 144 bars (12 h); swing k and ATR period stay in entry bars | 807 | 364 | 25.8% | **−0.337 (−0.49 to −0.18)** | [variant_AB5](phase2/variant_AB5.md) |
| 6 | 2026-10-19 | AB5F3 | AB5F, plus one combined change: FVG ≥ 0.25 ATR, sweep first-bar penetration ≥ 0.25 ATR, CHoCH reference swing k = 3 on 5m. Run on 2012–2017 only | not counted (2012–2017 only loaded) | 201 | 29.4% | **−0.208 (−0.40 to −0.02)** | [variant_AB5F3](phase2/variant_AB5F3.md) |

**Status after attempt 4:**
- 5m entries bring the sample close to target, with 807 closed trades before the lockbox.
- On 5m, however, the rules **lose money with statistical confidence** on the development period: the
  whole CI is below zero.
  - Gross R is already about −0.07.
  - Costs weigh much more, because 5m stops are tighter.
  - The win rate is 25.8% against a 31.2% break-even.
- On 15m (AB) the rules sit near zero after costs, with only 297 trades.
- Further changes wait for Fadi's decision. Variant attempts are capped to keep the multiple-testing
  count honest.

**Decision, 2026-10-19 (Fadi): AB5 is frozen as the v1 rule set.**
- It is `FROZEN_V1` in `app/smc/params.py`. No more rule variants will be tried.
- The Phase 3 question becomes: can a model select a subset of these setups that is profitable after
  costs, when the rules alone lose? Either answer is a reportable result.
- **Phase 2 gate, manual detector review: pending.**
  - Run `python -m app.smc.review`. It writes 50 charts of planned setups, stratified by year over
    2012–2017 (seed 2026), and a checklist at
    [phase2/review/REVIEW.md](phase2/review/REVIEW.md).
  - Fadi marks each chart. The gate passes at 45 of 50 correct or more.
  - Claude spot-checked charts #01, #10, #25 and #37: the rule elements and the plan were drawn where
    the rules put them. This is not the review itself.

**Decision, 2026-10-19 (Fadi), after reviewing v1 charts 1–5: the FVG definition is amended, and v2
replaces v1.**
- **The v1 review:** Fadi marked #2, #3 and #5 ❌ and #1, #4 ⚠️, all about FVG timing or visibility.
  - A data check showed all five matched the written v1 rules.
  - #2's gap formed 19 bars (95 min) before the CHoCH, far from the displacement that broke structure.
  - The partial sheet is kept in
    [phase2/review_v1/REVIEW_v1_partial.md](phase2/review_v1/REVIEW_v1_partial.md). Its charts can be
    regenerated from commit `ed12bc5`; the files in `review/` are now v2's.
- **The amended rule (spec, Strategy rule 5):**
  - The gap's third bar is the CHoCH bar or one of the 6 entry bars before it, counted in bars.
  - It stays inside the move from the sweep extreme.
  - A small gap is valid if it meets the minimum size. Nothing else changes.
- **Frozen v2 = `FROZEN_V2`** (attempt 5, AB5F). FROZEN_V1 is kept unchanged for the record.
- **Result on 2012–2017:**
  - 843 closed trades before the lockbox.
  - Development mean net R −0.26 (95% CI −0.40 to −0.11): still a loss after costs, about break-even
    before them.
- **The review restarts from chart 1** on v2 (same seed). The charts now outline thin FVGs and print
  the gap size and its distance from the CHoCH.

**Decision, 2026-10-19 (Fadi): the Phase 2 gate is split in two.**
- **Why:** the v2 review of charts 1–25 reached 19 of 25. Five of the six non-✅ marks gave reasons
  that contradicted the numbers printed on the chart, for example a sell CHoCH "closing above" when
  it closed below. No implementation error was found. That sheet is archived in
  [phase2/review_v2/REVIEW_v2_partial.md](phase2/review_v2/REVIEW_v2_partial.md). The reviewer's
  only definitional point was #12 (minimum sweep depth).
- **Gate 2a, implementation matches the written definition (automated):**
  - `python -m app.smc.conditions` re-derives the five conditions from the raw bars for every planned
    setup, without the engine's decision code. It writes [phase2/conditions.md](phase2/conditions.md).
  - **Result: 649 of 649 setups pass** in 2012–2017.
  - One apparent failure was a bug in the checker itself (it used the ATR of the wrong bar), now fixed.
  - Tests in `tests/test_smc_conditions.py` show that tampered setups fail the matching condition.
- **Gate 2b, pattern validity (human, Fadi in person):**
  - One question per chart: would an SMC trader recognise this as a genuine sweep → CHoCH → FVG?
  - A ❌ must name what is visible on the chart.
  - Definition feedback goes in its own column and is decided once, after the review.
  - The gate passes at 45 of 50 ✅ or more, on a new sheet at
    [phase2/review/REVIEW.md](phase2/review/REVIEW.md). The sample is unchanged (seed 2026).

**Decision, 2026-10-19 (Fadi): v3 replaces v2 after gate 2b failed (attempt 6).**
- **Why:** gate 2b on v2 reached 14 of 20 ✅ with 6 not ✅. The gate allows at most 5 of 50, so it
  had already failed. The sheet is archived in
  [phase2/review_v2/REVIEW_v2_gate2b_partial.md](phase2/review_v2/REVIEW_v2_gate2b_partial.md).
  Its definition feedback had three themes: weak or small FVGs (#1, #5, #6, #9, #13, #15), shallow
  sweeps (#7, #9, #16, #18) and a CHoCH that breaks a minor swing (#12, #16, #20).
- **One combined change, `FROZEN_V3`** (spec, Strategy rule 5, "Frozen v3"):
  - FVG at least 0.25 ATR (was 0.1).
  - Sweep: the first bar trades through the level by at least 0.25 ATR (was 0.1). The 1.5 ATR
    maximum and the extension rule are unchanged.
  - CHoCH reference: a 5m swing with k = 3 (was 2).
- **Result on 2012–2017 only** (the walk-forward period was not loaded for this attempt):
  - 201 closed trades, win rate 29.4% against a 32.3% break-even before costs.
  - Gross R about 0.00; mean net R −0.21 (95% CI −0.40 to −0.02). Still a loss after costs.
  - 349 setups reached a full trade plan. v2 had 649.
- **Gate 2a: 349 of 349 pass** ([phase2/conditions.md](phase2/conditions.md)). The checker now
  takes its thresholds from the parameters instead of printing 0.1 and 1.5.
- **Gate 2b restarts on a new sample, seed 2027** (50 charts, 8–9 per year):
  [phase2/review/REVIEW.md](phase2/review/REVIEW.md).
  - The chart panel now prints the current minimums (0.25 ATR for the sweep and the FVG, k = 3);
    before this fix it printed the v1 FVG minimum of 0.1 ATR.
  - 10 of the 50 sweeps were also in an earlier sheet (v1 or v2). They are kept, to avoid biasing
    the random sample, but the reviewer has seen them before.
- **Attempt count:** this is the sixth variant tried on the development period.

**Result, 2026-10-19: gate 2b failed on v3 at chart 6** (0 ✅, 2 ⚠️, 4 ❌; charts 7–50 not
reviewed). Sheet: [phase2/review/REVIEW.md](phase2/review/REVIEW.md).
- **One reason throughout:** the FVG forms on the CHoCH bar (#1, #3, ⚠️) or 1–4 bars before it
  (#2, #4, #5, #6, ❌). The reviewer expects the strict order Sweep → CHoCH → FVG.
- **Data check:** the offsets on the charts are right (0, 1, 0, 1, 3, 4 bars), and all six meet
  the written rule (v2 amendment: third bar on the CHoCH bar or up to 6 bars before it).
- **Consequence:** this is a conflict with the definition, not a sampling or implementation issue.
  No v3 setup has its FVG after the CHoCH. Of 349 planned setups, 107 have it on the CHoCH bar and
  242 before it. Under the strict-order reading, no sample from v2 or v3 can pass the gate.
- **Open decision (Fadi):** which FVG timing is the definition? See Open questions.

### 2026-10-19 — Phase 2, first rules-only run (Sweep → CHoCH → FVG, initial parameters)

- **Code:** `app/smc/` (primitives, bar-by-bar engine with the full lifecycle, report). Run it with
  `python -m app.smc.report`; the output is in [phase2/rules_only.md](phase2/rules_only.md).
- **Data:** XAUUSD 15m/1h/4h in UTC, cut at 2024-07-01. The lockbox is not loaded.
  - Performance is computed on the development period (2012–2017) only.
  - The walk-forward period is counted, not scored.
- **Parameters:** the spec's initial values; costs are spread + max(50%, $0.10), plus $0.10 SL slippage.
- **Tests:** 47 pass. These include prefix-equality no-look-ahead tests on a random walk and on real data.
- **Results:**

  | Measure | Value |
  | --- | --- |
  | Setups detected, 2012 to 2024-06 | about 5,400 |
  | Setups reaching a trade plan | about 360 |
  | Closed trades | 149 |
  | Development-period trades | 71 |
  | Development win rate | 21.1% (95% CI 13–32%) |
  | Break-even win rate before costs | 32.5% |
  | Mean net R | −0.07 (95% CI −0.35 to +0.22) |

- **Where setups die (all periods):**

  | Reason | Count |
  | --- | --- |
  | New extreme before the CHoCH | 3,238 |
  | No CHoCH within 8 bars | 1,387 |
  | No qualifying FVG | 420 |

- **Takeaways:**
  1. **The sample-size check fails.** 149 trades before the lockbox is far below the ~1,000 the spec
     requires before model work. Per the spec, the rules must be revisited, on development data only.
  2. With 71 development trades, the rules show no evidence of an edge. Their confidence interval is
     wide and includes both a loss and a gain.
  3. The main bottleneck is the rule that discards a setup when price makes a new extreme after the
     sweep. Most sweeps keep running for a bar or two.
- **Next:** decide which rule changes to try on 2012–2017. Log every variant tried, so the number of
  attempts is reported (multiple-testing control). Then run the manual detector review on the final
  rules.

### 2026-10-19 — Phase 1 history import and data-quality report (XAUUSD, EURUSD)

- **Command:** `cd ai-service && python -m app.data.importer --raw-dir <path to data/raw>` (about 30 s for
  both files). Re-running gives byte-identical Parquet and reports. Reports:
  [data_quality/XAUUSD_M5.md](data_quality/XAUUSD_M5.md), [data_quality/EURUSD_M5.md](data_quality/EURUSD_M5.md),
  with JSON next to each.
- **Input:** `XAUUSD_M5_mt5.csv`, SHA-256 `291252dbc621bebf9d292dfdf0bd4407efb9a64e5e55d01c6df9a7fa31d44dc3`.
- **Method:**
  - Server time → UTC with the `Europe/Athens` clock; spread × $0.01 per point.
  - Bars that are malformed, OHLC-inconsistent, off the 5-minute grid or duplicated are dropped and listed
    with their line number.
  - The export's final bar is dropped when it may still have been forming.
  - 15m/1h/4h bars come from closed 5m bars only. 4h bars start at 17:00 New York, the trading-day start.
    Each bar carries `n_bars` and `n_expected` (5m slots inside trading hours).
  - Gaps are counted only inside trading hours (Sunday 18:00 to Friday 17:00 New York, minus 17:00–18:00
    daily). They are classed as mid-session, session edge (next to the break or weekend) or holiday.
- **XAUUSD results:**

  | Item | Value |
  | --- | --- |
  | Range (UTC) | 2012-04-22 22:05 → 2026-01-09 15:55; the 16:00 bar dropped as possibly forming |
  | Bars | 5m 963,014; 15m 322,800; 1h 80,770; 4h 21,158 |
  | Rows rejected | 0 (no malformed rows, OHLC inconsistencies or duplicate timestamps) |
  | Coverage of expected 5m slots | 96.6–98.5% per full year |
  | Mid-session gaps | 77 (392 bars; the largest is 39 bars, 2021-09-24 11:25 NY) |
  | Session-edge / holiday gaps | 4,938 (7,127 bars) / 394 (17,587 bars); mostly the 16:55 NY bar before the break and late Sunday opens |
  | Partial higher-timeframe bars | 15m 5,258; 1h 5,285; 4h 5,292 |
  | Jump flags (≥ 30× the trailing median, reported, not removed) | 203 close-to-close, 23 range; many at 08:30 NY releases or Sunday opens |
  | Flat bars (O = H = L = C) | 146 |
  | 5m content hash | `2e8a9d50fab97e62c4cfe282ef4bb7ee9eee8dfa685bdb98ae114823e8fc7162` |

- **Timezone evidence (XAUUSD):**
  - With the EU-DST clock, 113 bars fall inside expected closed hours, all in 2012–2014 mismatch weeks,
    when the broker kept a fixed server-time session. If the clock were New York + 7h, 1,029 bars would.
  - On first Fridays in mismatch weeks, the widest bar between 07:00 and 10:00 NY is at 08:30 NY on 9 of
    10 days with this clock. Under New York + 7h it would be at 07:30 on 8 of 10.
  - Over all first Fridays, the widest bar is at 08:30 NY on 112 days.
- **XAUUSD spread** (median / P95 per year, in $):

  | Year | Median | P95 |
  | --- | --- | --- |
  | 2012–2015 | 0.32–0.41 | 0.52–0.60 |
  | 2016–2019 | 0.19–0.29 | 0.24–0.39 |
  | 2020 | 0.11 | 0.43 |
  | 2021–2023 | 0.05–0.07 | 0.12–0.16 |
  | 2024–2025 | 0.14–0.15 | 0.18–0.33 |

  Zero-spread bars cluster in 2021 (6,408) and 2022 (10,021). This is the in-bar minimum, so the cost
  margin in the validation protocol applies.
- **EURUSD:**
  - 1,858,961 bars kept (2000-05-30 → 2026-02-13). Two rows were rejected: line 2 (the malformed first
    row) and line 85,256 (2001-09-11, all prices −0.0001).
  - **Not clean.** 121,070 bars lie on Sundays 10:00–18:00 NY, before the normal weekly open, in every
    year.
  - 8,031 mid-session gaps.
  - The jobs-report check does not peak at 08:30 NY, so the clock of this export is **not verified**.
  - Review it before using EURUSD, even as an ablation.
- **Takeaways:**
  - XAUUSD passes the Phase 1 quality gate on history.
  - The spec's timezone rule ("New York time + 7 h") must be corrected to the EU-DST server clock. Live
    adapters must use the same clock, or better, take UTC from the broker API.
  - The base-rate experiment below used server time with no UTC conversion, so its numbers are
    unaffected.

### 2026-10-19 — random-entry base rates on XAUUSD (sanity baseline)

- **Data:** FxPro MT5 M5 export aggregated to 15m, 2012-04-23 to 2026-01-09 (322,801 bars; server time,
  not converted to UTC, which does not matter here).
- **Setup:** entry at the next bar's open, long and short, every 7th bar (n = 92,210); SL = 1 × ATR(14); TP
  = R × ATR; 48-bar horizon; stop-first on ambiguous bars. "With spread" pays the bar's maximum recorded
  spread on entry. No strategy and no model; this is what pure chance gives.

| R | Win, no spread | Win, with spread | Loss, with spread |
| --- | --- | --- | --- |
| 1.0 | 49.2% | 40.5% | 59.2% |
| 1.5 | 39.2% | 32.2% | 66.8% |
| 2.0 | 32.2% | 26.4% | 71.7% |
| 3.0 | 23.1% | 18.8% | 77.3% |

- **Takeaways:**
  - With TP at 1.5R or more, always predicting "loss" scores about 67–77% accuracy. A "70% accuracy" target
    is met by a useless model, so it must not be the acceptance metric.
  - Spread is material at 15m with a 1 × ATR stop: it removes 7–9 points of win rate.
  - Break-even win rate at 1.5R is 40% before costs, so a 70% win rate at 1.5R or more would be
    extraordinary.
