# P6 plan: live scanner and risk

Started 2026-10-25 (Fadi: P6 before P5, `docs/phase4/CLOSEOUT_P4.md`). Branch
`ai/p6-live-scanner`, stacked on `ai/p4-meta-model`.

**Gate (design):** an evaluate call answers in **< 10 s** (production image, 512 MB, 0.5 CPU),
and **live = backtest**: replaying history bar by bar through `/v1/evaluate` gives exactly the
setups, states and realised R of the research pipeline (`label_all`, rules L1).

**Contract:** `../docs/ai-contract.md` (B7, `0.1.0-draft`), `../backend/app/ai/contract.py`,
examples in `../docs/api/ai-service-examples/`. v1 runs **without a model**: rules with
abstention, `probability`, `ev_r`, `grade` and `versions.model` null.

## Tasks

| # | Task | Done when |
| --- | --- | --- |
| 1 | **Contract in ai-service.** Vendor `contract.py` as `app/contract.py` (pydantic only, unchanged); tests parse every example payload. | the seven examples round-trip |
| 2 | **Request → frames.** Build the research frames from `bars`: 15m entry; 1h, 4h and D1 (17:00 New York day) from closed 15m bars with the importer's aggregation code; spread in price units → points per instrument; the lockbox guard does not apply (live data). Data-quality checks (gaps, OHLC, `bar_close_ts` rule, decision-bar spread) → `data_quality_failed` with an abstention detail. | aggregation equals the store's 1h/4h/D1 on the same 15m bars |
| 3 | **Live scanner.** Run L1 detection, the setup builder and the lifecycle on the window ending at `bar_close_ts`, with the same code as research. Map the lifecycle to contract states and transitions (`created_at`, `valid_until`, `horizon_until`, `reason`, `realized_r`); deterministic `setup_id`; every setup in the window returned with its full transition history. | unit tests on hand-built bars + append-future-bars test |
| 4 | **`/v1/evaluate`.** FastAPI endpoint, `versions` (strategy, features, service, costs), abstentions (no pattern, data quality, rules not met), byte-identical answer for the same body. Replaces `/v1/signal`. | contract tests pass; same body → same bytes |
| 5 | **Live = backtest.** Replay 2018 to 2024-06 (walk-forward period, already seen; never the holdout or the lockbox) bar by bar through the evaluate function; compare with `label_all`. | zero differences, report in `docs/phase6/` |
| 6 | **`/v1/size`.** Lots from risk %, quote → USD with the instrument's own price (all six are USD base or USD quote), lot step / min / max, margin = notional × max(margin_rate, 1 / leverage), warnings. Fixes the JPY issue of `libs/backtest` `Sizer` (AUDIT §5). | the contract's hand example (0.04 lots, 96 USD) and a USDJPY case |
| 7 | **Per-currency exposure.** Design with Yazan: the backend holds the open positions; `/v1/size` is stateless and sees one setup. | agreed in the contract |
| 8 | **Production image and performance.** Runtime dependencies (pandas, numpy, pyarrow) in the image, research extras out; `/health` versions; measure p95 latency and peak memory on the largest request at 512 MB / 0.5 CPU. | p95 < 10 s, report |

`/v1/explain` is P7.

## Progress

| # | State | Where |
| --- | --- | --- |
| 1 | done: the seven examples round-trip; a test keeps `app/contract.py` byte-equal to the backend's | `app/contract.py`, `tests/test_contract.py` |
| 2 | done: 1h/4h/D1 from the request's 15m bars equal the store's (XAUUSD, EURUSD, GBPUSD on a clock-corrected segment). The store's spread is already in price units: no conversion. Checks: entry timeframe present, bars on the 15m grid, a spread on every bar, no gap > 240 min in trading hours in the last 24 h (holidays excluded), at least 7 complete trading days (`app/config/serving.toml`). OHLC, order and the `bar_close_ts` rule are the contract's (422) | `app/live/frames.py`, `tests/test_live_frames.py` |
| 3 | done: `detect`, `build`, `resolve` unchanged; ARMED and ACTIVE at the decision close, CLOSED at the exit bar's close with net R; hand-built tests and an append-future-bars test. Only market-entry rule sets (L1) are served; no DEVELOPING in v1 | `app/live/scanner.py`, `tests/test_live_scanner.py` |
| 4 | done: `/v1/evaluate` replaces `/v1/signal`; same body → same bytes; about 0.12 s in-process for 800 bars | `app/live/evaluate.py`, `app/main.py`, `tests/test_main.py` |
| 5 | done for **XAUUSD only** (Fadi, 2026-10-25: the six-instrument replay takes about 6.5 h on this laptop; gold is the research instrument): 154,915 bars, 187 / 187 setups, **zero differences**, no bar refused, no transition rejected; in-process latency mean 182 ms, p95 216 ms (1,000 bars). The five pairs run the same code; their replay stays open (`--symbols EURUSD ...`) | `python -m app live replay --symbols XAUUSD`, `docs/phase6/replay.md` |
| 6 | done: the B4 arithmetic of `libs/backtest/trading_backtest/sizing.py` vendored unchanged (`lots_for_risk` already converts USD/JPY; `Sizer` is not used); hand example and USD/JPY 0.30 lots | `app/scoring/lots.py`, `app/scoring/size.py`, `tests/test_size.py` |
| 7 | proposal written, to agree with Yazan | `docs/phase6/EXPOSURE.md` |
| 8 | runtime dependencies set; image measurement pending (Docker) | `pyproject.toml`, `python -m app live bench` |

Choices made in tasks 2-6 (Fadi to confirm):

- **Window.** Levels live 5 trading days and are re-derived from the request, so a request needs
  7 complete trading days of 15m bars (about 650-700 bars; with the week open and holidays, 1,000
  is safe). The backend default of 500 x 15m is not enough. The 1h and 4h bars of the request are
  not used: every frame is built from the 15m bars, as the store builds them from M1.
- **Gaps.** Only the last 24 h are checked; older gaps are left to the rules, as in research (a
  bar after a gap is never a sweep or a swing). Refusing every window with an old gap would
  refuse 7 days after each feed outage.
- **Setup payload.** `setup_id` = `{instrument lower}-{profile}-{pattern id}` (direction, level
  source, side, origin, price). Prices rounded to `tick_size`; the exact research values in
  `evidence.plan`. Extra fields: `instrument`, `profile`, `created_at`, and `exit_reason`,
  `realized_r` once closed. `valid_until` = one bar after the decision (a market entry at the
  decision close); `horizon_until` = the 48th entry slot in trading hours (an estimate).
- **`versions`.** `strategy` = rule set + digest of its parameters (`L1-40194b0c93`), `features`
  = `none`, plus `costs` and `service` (the backend ignores extra fields).
- **Unknown profile or instrument** → 422 (never retried).

## Open points for the contract (to agree with Yazan)

1. **No model in v1 vs `model_unavailable`.** The backend stores nothing but versions when
   `status != ok` (contract §5.2). v1 must therefore answer `status: ok` with
   `versions.model: null`; `model_unavailable` stays for a registered model that fails to load.
2. **Bar counts.** Features need about 20 trading days of 15m (`ATR_PCT_BARS` = 1,920), 20 days of
   spread history per New York hour, and about 250 trading days for the D1 ATR percentile
   (`D1_PCT_DAYS`). Sending D1 history as 15m bars is too large (about 24,000 bars); either D1 bars
   are sent as their own timeframe, built on the 17:00 New York day, or ai-service receives them
   separately. Final counts and body size come from task 8.
3. **Spread** (contract: mean over the bar, price units) matches the research definition
   (`spread = mean of the decision bar`, Fadi 2026-10-22).
4. **Transitions:** `ACTIVE → INVALIDATED` never happens in L1 (an active trade ends by TP, SL or
   horizon: `CLOSED`); L1 enters at market, so `ARMED` and `ACTIVE` share one `at`. A new setup
   comes in `new_setups` as `ARMED` with the `ARMED → ACTIVE` transition of the same bar.
5. **`AI_BARS_15M` = 1,000** (window above); `AI_BARS_1H` / `AI_BARS_4H` can be 0 for this
   profile.
6. **A missed bar.** An open setup the backend does not echo is sent again in `new_setups` in its
   current state (`created_at` says when it was decided); an echoed setup the window no longer
   produces gets `→ INVALIDATED`, reason `not_reproduced`.
7. **Abstentions:** `no_pattern`, `rules_not_met` (detail: setup id, direction, rule), and with
   `data_quality_failed`: `missing_timeframe`, `misaligned_bars`, `missing_spread`, `gap`,
   `insufficient_history` (detail: a string or an object).
8. **Exposure** (`docs/phase6/EXPOSURE.md`): `SizeRequest.open_positions` and
   `RiskSettings.max_currency_risk_pct`, both optional.
