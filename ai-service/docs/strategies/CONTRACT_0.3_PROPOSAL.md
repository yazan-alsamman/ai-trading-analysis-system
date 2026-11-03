# Contract 0.3.0 proposal: the signal strategies, management alerts and statuses

**Status: DRAFT, written by Fadi for Yazan on 2026-11-03. Nothing is built yet.** It extends
`docs/ai-contract.md` (0.2.2) for Stage F of `docs/strategies/PLAN.md`.

- Every change only adds fields or values, except one: `tp` may be null under bundle M8 (section
  4), which needs Yazan's agreement.
- The questions for Yazan are listed in section 9 (Y1-Y9).
- Nothing here changes a registered rule. The strategies, bundles, costs and statuses are frozen
  at `b9ca2a8` (`PREREG.md`).

## 1. What changes

| Area | 0.2.2 (now) | 0.3.0 (proposed) |
| --- | --- | --- |
| Profiles | `intraday` only (L1, 15m) | `scalp`, `intraday` and `swing` (the signal types of `PREREG.md` section 4) |
| Strategies served | L1 | S1-S8 and L1, each tagged on its setup |
| Instruments | XAU/USD | the six research instruments |
| Bars | 15m, 1h, 4h, 1d | adds 5m (`AI_BARS_5M`) for the scalp profile |
| Schedule | every 15m | scalp every 5m, intraday every 15m, swing every 4h (section 2) |
| Setup | prices, state, null scores | adds `strategy`, `status`, `management`, `cost_r`, `sl_initial` and a structured `evidence` (section 3) |
| Management | none: a trade ends at TP, SL or the horizon | `management_events` (`SL_MOVE_SUGGESTED`, `EXIT_SUGGESTED`) for scalps under M8 (section 5) |
| Strategy facts | none | `GET /v1/strategies`: the catalogue, with each strategy's statistics and status (section 6) |
| Forward paper log | none | the stored setups are the paper log: rules on keeping and exporting them (section 7) |

## 2. Profiles, bars and schedule

A **profile is a signal type**. Every evaluate call is (instrument, profile, `bar_close_ts`),
as in 0.2.2. The **decision timeframe** is the smallest timeframe sent, and its last bar closes
at `bar_close_ts`.

| Profile | Strategies | Decision timeframe | Schedule | Bars (proposal) |
| --- | --- | --- | --- | --- |
| `scalp` | S4 ORB, S5 PB, S6 VR, S8 FX | 5m | each 5m boundary + `AI_EVALUATE_DELAY_SECONDS` | 5m x 1,000, 1h x 300 |
| `intraday` | S1 LB (15m), S2 MR (1h), S7 SQ (15m), L1 (15m) | 15m | each 15m boundary + delay (as now) | 15m x 2,000, 1h x 500, 1d x 260 (as now) |
| `swing` | S3 TF | 4h | each 4h boundary + delay | 4h x 300, 1d x 60 |

- S2 decides on 1h bars. An intraday call at a 15m boundary that is not an hour boundary simply
  finds no new 1h bar, so S2 proposes nothing then.
- The bar counts cover each indicator's warm-up:
  - VWAP from 03:00 New York;
  - EMA(50, 1h) and its slope;
  - ADX(14, 1h);
  - ATR(14, D1);
  - Donchian 55 on 4h.

  They are confirmed by the live = backtest replay (section 8) before anything is switched on.
- **Load.** Six instruments: 288 scalp calls a day per instrument, 96 intraday and 6 swing,
  about 2,340 calls a day in all. Measured P6 latency: p95 377 ms at 1,000 bars (512 MB, 0.5 CPU).
  The 5m path is measured again before it is switched on.

## 3. Setup: new fields

`Setup` already keeps unknown fields both ways (0.2.2, section 1), so the backend stores these
fields without a code change. Showing them needs the fields below.

| Field | Type | Meaning |
| --- | --- | --- |
| `strategy` | `S1`-`S8`, `L1` | the strategy that proposed the setup |
| `type` | `scalp`, `intraday`, `swing` | equals the profile; repeated so that a stored setup reads on its own |
| `status` | `validated`, `exploratory`, `inconclusive`, `unvalidated` | the strategy's **statistical status** (`PREREG.md` section 10). Today every strategy is `unvalidated` |
| `operational` | `active`, `suspended` | the monitoring flag (`PREREG.md` section 13). `suspended`: monitoring found the strategy drifting below its registered mean. It never changes `status` |
| `management` | `{bundle, rules, tp_rule}` | `bundle` `M0` or `M8`. `rules`: for M8, `["L1 break-even at +1 R", "L3 structure trail from +1 R"]`. `tp_rule`: `fixed` or `none (horizon cap)` |
| `sl_initial` | price | the SL at entry. `sl` is the SL in force now, moved by `SL_MOVE_SUGGESTED` |
| `cost_r` | number | the modelled round trip plus SL slippage at the decision bar, in R (the registered cost model, the one the 0.15 R cost filter uses) |
| `evidence` | object | structured, below. The 0.2.2 free-form keys stay |

**`evidence`** explains the signal, in the spirit of the ICT model's step list
(`EXTERNAL_REVIEW.md`, section 3):

```json
{
  "steps": [
    {"name": "asian_range", "met": true, "detail": {"high": 2034.10, "low": 2027.40, "bars": 28}},
    {"name": "range_width", "met": true, "detail": {"atr_d1_multiple": 0.62, "allowed": [0.3, 1.2]}},
    {"name": "breakout_close", "met": true, "detail": {"close": 2035.20, "threshold": 2034.85}}
  ],
  "invalidation": {"price": 2030.75, "rule": "SL: the range midpoint minus the spread"},
  "plan": {"entry": 2035.2, "sl": 2030.75, "tp": 2041.875, "risk": 4.45, "r_multiple": 1.5}
}
```

Every number in `evidence` is the research value. `explain` (P7) may only cite numbers found here.

## 4. `tp` null under M8 (needs Yazan's agreement)

Bundle M8 (activated for scalps by Stage D and the holdout) has **no fixed TP**. The trade ends at
the trailed SL or the horizon.

0.2.2 requires `tp` in `ARMED` and `ACTIVE`. Proposal:

- `tp` may be null when `management.tp_rule` is `none`.
- `horizon_until` is then required.
- Price checks keep `sl < entry` for buys and `entry < sl` for sells.
- The alert text reads "no fixed target; managed by break-even and a structure trail" (Arabic:
  "بدون هدف ثابت؛ إدارة بنقطة التعادل وتتبّع البنية").

The alternative is to send the strategy's registered TP as a reference target. It is not
proposed, because M8 never exits there, and showing it would mislead the user.

## 5. Management events

While a setup is `ACTIVE`, ai-service may emit alerts. **They never change the state, and the
service never touches an order.**

`EvaluateResponse.management_events`: `[{setup_id, kind, at, reason, new_sl, realized_r_if_exit}]`

| Kind | When (M8) | Fields |
| --- | --- | --- |
| `SL_MOVE_SUGGESTED` | +1 R reached: SL to entry + the round-trip cost (rule L1); later, each new confirmed swing low or high (rule L3) | `new_sl`, `reason`: `breakeven` or `structure_trail` |
| `EXIT_SUGGESTED` | reserved for bundles with exit rules (T1, T3, T4, L5). M8 has none, so v0.3 sends none | `reason` |

- Like transitions, the response carries the **full event history** of each open setup.
- The backend dedupes on `(setup_id, kind, at)` and notifies the setup's takers (B11), in the
  same way as a state change.
- When the trade ends, the `ACTIVE → CLOSED` transition gives the reason as before:
  `sl`, `breakeven`, `trail`, `timeout`, `session_end` or `session_end_gap`.
- **Execution assumption** (research and live alike): a moved SL is in force from the next bar.
  The user acts on the alert.

## 6. `GET /v1/strategies`: the catalogue

This endpoint holds the facts that are the same for every setup of a strategy. The backend
caches them, for example once a day and on a version change.

```json
{
  "version": "strategies-rules-v1 (b9ca2a8)",
  "strategies": [
    {
      "strategy": "S1", "type": "intraday", "family": "A", "frame": "15m",
      "name": {"en": "London breakout", "ar": "اختراق جلسة لندن"},
      "status": "unvalidated", "operational": "active",
      "management": {"bundle": "M0"},
      "stats": {
        "period": "2018-01-01/2024-07-01", "trades": 3735, "mean_net_r": -0.014,
        "ci95": [-0.052, 0.025], "vs_random_r": 0.038, "tp_rate": 0.312,
        "exit_mix": {"tp": 0.31, "sl": 0.48, "timeout": 0.21}, "at_2x_costs": -0.060
      },
      "source": "docs/strategies/eval_S1.md"
    }
  ]
}
```

**Display rule.** Every status other than `validated` is shown with the label **"No proven edge"**
(Arabic: **"لا توجد أفضلية مثبتة"**), together with `stats`. A validated strategy shows "validated
(primary test passed; consistent on the holdout)". Today none is validated.

## 7. The forward paper log

The paper log is the only clean test left (`ADDENDUM_1_S1_M8.md`, section 6; P9). **The backend's
`ai_setups` and `ai_setup_events` already hold it**, provided these rules hold:

1. Every setup ai-service returns is stored, **whether or not anyone follows it**.
2. Rows are never deleted or edited by hand. Corrections are new events.
3. `realized_r` on `ACTIVE → CLOSED` is ai-service's net R:
   - registered costs and SL slippage;
   - the decision swap scenario;
   - next-bar fills.

   It is computed by the research engine.
4. **Export:** an admin endpoint or job that writes every setup and event of a period as CSV or
   Parquet, for Fadi's monitoring report and for P9.
5. **Backup:** the database backup covers these tables. They are part of the research record.

## 8. Order of work

| Step | Who | Done when |
| --- | --- | --- |
| 1. Agree on this proposal (section 9) | Fadi and Yazan | the answers are written into 0.3.0 |
| 2. Contract models and examples (`contract.py`, OpenAPI, example payloads) | Yazan, vendored by Fadi | the `api-contract` CI job passes |
| 3. ai-service: S1-S8 and M0/M8 behind `/v1/evaluate`; `/v1/strategies` | Fadi | unit tests; same body gives the same bytes |
| 4. Live = backtest replay: every strategy and bundle on 2018 to 2024-06 (never the holdout or lockbox) | Fadi | zero differences, report in `docs/phase6/` |
| 5. Backend: profiles, 5m schedule, six instruments, `management_events`, display rule, paper-log export | Yazan | e2e with the fake ai-service |
| 6. Monitoring addendum (CUSUM threshold, report) and portfolio risk limits in R | Fadi and Yazan | registered before step 7 |
| 7. Switch on | Yazan | first runs `ok` on the server; the paper log starts |

## 9. Questions for Yazan

| # | Question | Fadi's proposal |
| --- | --- | --- |
| Y1 | Does the feed give 1m bars **with spreads** for all six instruments (EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD as well as gold)? | needed. A decision bar without a spread is a local abstention, as now |
| Y2 | Can beat run a 5m schedule for 6 instruments (about 1,730 scalp calls a day)? | yes, with the same one-run-per-key lock |
| Y3 | `tp` null under M8 (section 4) | accept |
| Y4 | `management_events`: a new table, or rows in `ai_setup_events` with a `kind`? | your choice; dedupe on `(setup_id, kind, at)` |
| Y5 | Paper log: export endpoint, retention and backup (section 7) | an admin CSV export; keep everything |
| Y6 | Display: the "No proven edge" label and `stats` on every signal and alert (section 6) | on every signal; `stats` on the signal page |
| Y7 | `cost_per_unit` (0.2.2, `/v1/size` only): also send it with `/v1/evaluate`, so that `cost_r` can include the commission | yes. The MT5 check found commission is 0.02-0.11 R a trade (`mt5_cost_check.md`) |
| Y8 | Exposure limits (`docs/phase6/EXPOSURE.md`) and a daily loss limit in R across the portfolio | agree them before step 7 |
| Y9 | Followers: one follow per instrument and profile (as now), or per strategy too? | per instrument and profile in v0.3; per strategy later |

## Changelog row (when agreed)

| Version | Date | Change |
| --- | --- | --- |
| 0.3.0 | (agreed date) | Profiles `scalp` and `swing`; `AI_BARS_5M`; Setup `strategy`, `type`, `status`, `operational`, `management`, `sl_initial`, `cost_r` and structured `evidence`; `tp` null under a no-TP bundle; `management_events`; `GET /v1/strategies`; paper-log rules |
