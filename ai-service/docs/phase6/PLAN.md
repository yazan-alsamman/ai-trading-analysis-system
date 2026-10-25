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
   horizon: `CLOSED`); L1 enters at market, so `ARMED` and `ACTIVE` share one `at`.
