# Risk management

Strategies only say **when** to enter (entry events on closed bars). Risk management decides
**how much** to trade and **where to get out**. The same rules run in two places:

1. **Backtests** (`trading_backtest`): every entry goes through the rules, so the results
   reflect real stops, targets and position sizes.
2. **Live signals**: every signal delivered to a user carries a **trade plan** (entry, stop,
   targets, size, money at risk, reward:risk) computed from that user's rules.

Both use the same function, `trading_backtest.plan_trade` (`RiskContext.plan` inside the
engine), so a live plan and a backtest entry on the same bar agree.

## The risk config

```json
{
  "stop":        {"type": "atr", "length": 14, "multiplier": 2.0},
  "trailing":    {"type": "atr", "length": 14, "multiplier": 3.0, "activation_r": null, "breakeven_r": 1},
  "take_profit": {"type": "r_multiple", "levels": [{"r": 1, "close_pct": 50}, {"r": 2, "close_pct": 50}]},
  "sizing":      {"mode": "risk", "risk_pct": 1.0, "max_position_pct": 100, "min_notional": 10},
  "guards":      {"max_daily_loss_pct": 3, "max_drawdown_pct": 10, "cooldown_bars": 5, "max_consecutive_losses": 3},
  "fee_bps": 10
}
```

All parts are optional. Every part is validated with Pydantic: unknown fields are errors, and
messages carry the JSON path, e.g. `stop.multiplier: Input should be greater than 0`. The JSON
Schema and the templates are at `GET /api/v1/risk/schema`.

**R** is the distance from the entry to the **initial** stop: `R = |entry − stop|`. Rules
expressed in R (`r_multiple` targets, `risk` sizing, `activation_r`, `breakeven_r`) need a stop.
The config is refused without one: `take_profit.type: r_multiple targets need a stop`.

## Order of operations inside a bar

A signal on bar `t` is computed on the closed bar and filled at the **open of bar `t + 1`**.
For each bar `i`:

1. **Gaps.** A position opened before bar `i` whose stop is already beyond the open is closed
   **at the open**. Otherwise, every target already beyond the open is filled at the open.
2. **Time exit.** `exits.max_bars_held` closes at the open.
3. **The previous bar's signal.** If flat, the account guards run first, then the trade plan
   (stop, targets, size; see below) and the fill at the open. An opposite signal closes the
   position, and with `long_short` reverses it.
4. **Stop and targets inside the bar**, from its low/high. The **stop first**: if the bar
   touches both the stop and a target, the stop is assumed to have been hit first
   (conservative). Then the targets, in order, each filled at its level.
5. **At the close: trailing stop and breakeven** are updated from this bar's data (its high or
   low, its ATR). The new stop applies **from the next bar**. There is no intrabar look-ahead:
   a bar never uses a stop computed from its own high.
6. Equity is **marked to market** at the close, and the drawdown and daily-loss guards are
   updated.

Every fill pays slippage against you and the fee on its notional, entry and each exit fill.

### The entry-bar change (`check_entry_bar`)

Until Y11, stops and targets were **not** checked on the entry bar. Since the fill is at that
bar's open, the rest of the bar happens **after** the fill, so they are now checked on the entry
bar too (step 4). The stop still comes first if both are touched, and the gap rule (step 1)
does not apply to the entry bar. This is the default, `"check_entry_bar": true`;
`"check_entry_bar": false` gives the old behaviour for comparison.

Effect, measured on the BTC/USDT 1h demo data with `ma_crossover`:

| SL / TP | `check_entry_bar` | trades | return | max DD | Sharpe | win rate | avg R |
|---|---|---|---|---|---|---|---|
| 2 % / 4 % | false | 121 | −26.19 % | −39.80 % | −1.39 | 28.1 % | −0.10 |
| 2 % / 4 % | true | 121 | −26.19 % | −39.80 % | −1.39 | 28.1 % | −0.10 |
| 0.5 % / 1 % | false | 121 | −26.27 % | −29.24 % | −4.14 | 38.0 % | −0.36 |
| 0.5 % / 1 % | true | 121 | −32.99 % | −34.09 % | −5.93 | 28.1 % | −0.47 |

With wide levels no entry bar reaches them, so nothing changes. With levels inside a typical
bar's range, the old rule hid exits that really happened (here mostly stops), which made the
results look better than they were. Y11 configs with `check_entry_bar: false` give
**bit-identical** results to the Y11 engine: a test runs 3 strategies × 5 configs through the
new engine and through the Y11 engine (kept verbatim in `libs/backtest/tests/y11_reference.py`)
and compares every trade and equity value exactly.

## Stops (`stop`)

| Rule | Long stop | Short stop |
|---|---|---|
| `{"type": "percent", "value": p}` | `entry × (1 − p/100)` | `entry × (1 + p/100)` |
| `{"type": "atr", "length": n, "multiplier": m}` | `entry − m × ATR(n)` of the **signal bar** | `entry + m × ATR(n)` |
| `{"type": "swing", "lookback": n, "buffer_pct": b}` | `min(low of the last n closed bars) × (1 − b/100)` | `max(high …) × (1 + b/100)` |
| `null` | no stop | |

- `entry` is the real fill in backtests (the next open, slippage included) and the signal bar's
  close in live plans (`entry_ref`).
- The ATR is Wilder's ATR from `trading_indicators`, known when the signal bar closes.
- The Y11 field `exits.stop_loss_pct` is an alias of the percent stop.
- If the stop cannot be computed yet (ATR or swing warm-up), the entry is skipped with
  `stop_unavailable`. If it is on the wrong side of the entry (e.g. a gap below a swing low),
  it is skipped with `stop_wrong_side`.

The exit reason is `stop_loss` while the stop is at its initial level, `trailing_stop` once a
trailing rule moved it, and `breakeven_stop` once breakeven moved it.

## Trailing stops (`trailing`)

| Rule | New stop candidate at each close (long; short mirrored) |
|---|---|
| `{"type": "percent", "value": v}` | `highest high since entry × (1 − v/100)` |
| `{"type": "atr", "length": n, "multiplier": m}` | **chandelier**: `highest high since entry − m × ATR(n)` of that bar |
| `{"breakeven_r": x}` | breakeven only (below) |

- **Only in your favour.** A candidate replaces the stop only if it is higher (long) / lower
  (short). The highest high includes the entry bar.
- **`activation_r`**: trailing starts only once the best price since entry moved at least that
  many R in your favour, i.e. `(highest high − entry) / R ≥ activation_r`. Once on, it stays on.
- **`breakeven_r`**: once the best price moved that many R, the stop moves to the price at
  which an exit covers the entry and both fees after slippage:
  `entry × (1 + fee) / ((1 − fee) × (1 − slippage))` for a long. If trailing later moves it
  higher, the exit becomes a `trailing_stop`.
- Updated **at the bar close**, effective **from the next bar** (step 5).

## Targets (`take_profit`)

| Rule | Target price (long; short mirrored) |
|---|---|
| `{"type": "percent", "value": p}` | `entry × (1 + p/100)` (alias: `exits.take_profit_pct`) |
| `{"type": "r_multiple", "value": r}` | `entry + r × R` (needs a stop) |
| `{"type": "percent" \| "r_multiple", "levels": [{"pct" \| "r": d, "close_pct": c}, …]}` | one target per level |

**Scaling out.** Each level closes `close_pct` % of the **initial** quantity. Levels are in
ascending order, at most 5, and their `close_pct` add up to at most 100. The level that
reaches 100 % closes whatever is left. If they add up to less than 100, the rest runs until
another exit (a "runner").

Every exit is a recorded **fill** (`time`, `index`, `price`, `quantity`, `reason`): partial
fills have the reason `partial_tp`, and the fill that closes the position has its own reason
(`take_profit`, `stop_loss`, …). A trade row keeps the totals: `exit_price` is the
quantity-weighted average of its fills, `gross_pnl`, `fees` and `net_pnl` are summed over all
fills, and `fills` lists them. A gap through several targets fills them all at the open.

## Position sizing (`sizing`)

Equity is the current equity at entry (cash when flat). `fee` is the fee rate. A long and a
short use the same quantity.

| Mode | Quantity |
|---|---|
| `fraction` (`value` in (0, 1], default 1) | `value × equity / (entry × (1 + fee))` |
| `fixed` (`value` quote) | `min(value, equity / (1 + fee)) / entry` |
| `risk` (`risk_pct`, needs a stop) | `risk_pct/100 × equity / (|entry − stop| + (entry + stop) × fee)`, so the loss at the stop, both fees included, ≈ `risk_pct` % of equity |
| `volatility` (`target_pct`, `length`) | `target_pct/100 × equity / ATR(length)`, so a 1-ATR move = `target_pct` % of equity |

Every mode is then capped:

- **`max_position_pct`** (default 100 = no leverage): notional + entry fee ≤
  `max_position_pct` % of equity. With a tight stop, `risk` sizing often hits this cap, and the
  money at risk is then below `risk_pct`.
- **`min_notional`** (default 10 quote): a smaller notional is not traded (`size_below_min`).

## Account guards (`guards`)

| Guard | Effect |
|---|---|
| `max_daily_loss_pct` | Once equity (realized + unrealized, marked at closes) is X % below its value at the start of the UTC day, no new entries until the next UTC day (`daily_loss`). |
| `max_drawdown_pct` | Once equity is X % below its peak (the initial capital counts), no new entries for the rest of the run (`max_drawdown`). |
| `cooldown_bars` | After an exit through a stop (`stop_loss`, `trailing_stop`, `breakeven_stop`) on bar `j`, entries on bars `≤ j + N` are skipped (`cooldown`). |
| `max_consecutive_losses` | After N losing trades in a row (net P&L ≤ 0), entries are paused for `cooldown_bars` bars (required, ≥ 1) and the count restarts (`loss_streak`). |

Guards only block **new entries**; open positions keep their exits. Guards apply to
backtests only: a live plan has no account history, so they are not part of it.

## Metrics added

| Metric | Definition |
|---|---|
| `avg_r` | mean R multiple of the trades with a stop (`r_multiple = net_pnl / risk_amount`) |
| `expectancy_r` | `Σ net_pnl / Σ risk_amount`: R earned per unit of risk taken, risk-weighted |
| `r_distribution` | trades per R bucket `[low, high)`: `<-2`, `-2..-1`, `-1..0`, `0..1`, `1..2`, `2..3`, `>=3` |
| `avg_risk_pct` | mean money at risk as % of equity at entry |
| `max_consecutive_losses` | longest run of trades with net P&L ≤ 0 |
| `exits_by_reason` | exit fills per reason (`opposite_signal`, `stop_loss`, `trailing_stop`, `breakeven_stop`, `take_profit`, `partial_tp`, `max_bars`, `end_of_data`) |
| `skipped_entries` | entries not taken, per reason (`max_drawdown`, `daily_loss`, `cooldown`, `loss_streak`, `stop_unavailable`, `stop_wrong_side`, `atr_unavailable`, `no_equity`, `size_below_min`) |

Trades also carry `initial_stop`, `risk_amount` (the loss at the initial stop, fees
included), `risk_pct`, `r_multiple` and `fills`.

## Trade plans

`plan_trade(df, signal_bar_index, side, risk_config, equity)` returns:

| Field | |
|---|---|
| `side` | `long` / `short` |
| `entry_ref` | the signal bar's close (the real fill is at the next open) |
| `stop` | initial stop price |
| `targets` | `[{price, r, close_pct}]` |
| `quantity`, `notional` | size and `quantity × entry_ref` |
| `risk_amount`, `risk_pct` | loss at the stop, fees included, and as % of `equity` |
| `rr` | reward:risk of the first target |
| `invalid_reason` | `null`, or why it should not be traded (`stop_unavailable`, `stop_wrong_side`, `atr_unavailable`, `no_equity`, `size_below_min`) |
| `equity`, `atr` (volatility sizing), `trailing` | inputs, for display |
| `lots`, `lots_feasible` | instruments with contract specs only: `quantity / contract_size` rounded **down** to the lot step, 0 and `false` below the minimum lot or without a conversion rate; `null` without specs |
| `lots_risk_amount` | price-move loss of `lots` at the stop, account currency |
| `conversion_rate` | account currency per unit of the quote currency (1 for the same currency) |
| `sizing_warnings` | what was adjusted or is missing (min/max lot, no conversion rate, USDT counted as USD) |

It reads bars up to the signal bar only. The backtest engine computes every entry with the same
code, passing the real fill as `entry`.

### Account currency and lots (B4 sizing fix)

Before B4 the size treated `account_size` as if it were in the instrument's **quote**
currency. That is right for BTC/USDT with a USDT account, but a USD/JPY plan for a 10,000 USD
account sized as if the account held 10,000 JPY, about 150× too small.

Now, on an instrument with contract specs (`contract_size` and `lot_step`, see
[instruments.md](instruments.md)), the plan converts the equity into the quote currency
before sizing (`equity / conversion_rate`). The account currency is the profile's
`quote_currency`. `risk_amount` and `risk_pct` come back in the account currency, `notional`
stays in the quote currency, and the plan adds `lots`. The conversion rate is:

1. 1 when the quote currency is the account currency;
2. `1 / entry` when the account currency is the base (USD/JPY for a USD account);
3. otherwise the latest 1m close of an active `QUOTE/ACCOUNT` market (or `1 /` that of
   `ACCOUNT/QUOTE`);
4. USD, USDT and USDC count as one dollar only when 1–3 find nothing exact, and
   `sizing_warnings` says so (the default profile currency is USDT);
5. nothing found: `lots = 0`, `lots_feasible = false` and a warning. The quantity is then the
   unconverted one, as before. A rate of 1 is never assumed silently.

Example: USD/JPY at 150.000, stop 149.500, account 10,000 USD, 1 % risk, no fees →
quantity **30,000** USD (was 200) = **0.30 lots**; `risk_amount` = 100 USD. Every old field is
kept. `fee_bps` still counts in `quantity`, so with the default 10 bps an XAU/USD plan gets
fewer lots than the fee-free hand calculation in instruments.md. `margin_rate` is not used for
the plan's size: the cap is still `max_position_pct` (the user's leverage).

### Backtests and plans in another account currency (B9)

Fadi reported that "the Sizer in libs/backtest" gave a USD/JPY size about 150× too small. A
test with the hand example above (USD account 10,000, 1 % risk, USD/JPY 150.00, stop 50 pips
away → **0.30 lots = 30,000 units**) was written first, against every path:

| Path | Before | Now |
|---|---|---|
| AI setup sizing `local_size` (B10, `tb.lots_for_risk`) | right: 0.30 lots | unchanged |
| plans and the calculator on an instrument **with** specs (B4) | right | unchanged |
| plans and the calculator on an instrument **without** specs | 200 units (150× too small): the rate was ignored | 30,000 units (no lots: no specs) |
| the backtest engine (`Sizer`, every mode) | 200 units (150× too small): the capital was taken as JPY | 30,000 units with `conversion` |
| a backtest with `"risk_profile": true` | 150× too small (the profile's USD balance as JPY) | the profile's currency is converted |

The fix:

- **libs/backtest**: `BacktestConfig.conversion` (optional): `{"type": "inverse_price"}` when the
  account currency is the instrument's base (a USD account on USD/JPY: 1 JPY = 1 / price USD
  at each fill and close), or `{"type": "fixed", "rate": r}` (account currency per quote unit,
  for the whole run). With it, `initial_capital` and every money result (equity, P&L, fees,
  `risk_amount`) are in the account currency; prices and notional stay in the quote currency.
  The size is computed on the equity converted to the quote currency, `cash` moves by the fees
  and the P&L of each fill converted at that fill, and an open position adds its P&L at the
  close. **Without it the engine runs the unchanged code path**: every USD-quoted and crypto
  backtest, and every Y11 golden test, is bit-identical.
- **Trade plans**: a conversion rate without contract specs converts the equity too (no lots).
  Live plans and the calculator pass it when the rate is not 1, so USD-quoted and USDT plans
  are unchanged.
- **Backtests with the profile**: when the profile's currency is not the instrument's quote
  currency (USD, USDT and USDC count as one), the stored config gets the `conversion`
  (`inverse_price` when the account currency is the base, otherwise the latest rate of a
  matching market, fixed for the run; none found: 422), and `config.risk_profile.conversion`
  records it. An explicit `initial_capital` stays in the quote currency, as documented.

### Worked example

ATR(14) = 1.5 on the signal bar, close = 100, account 10,000 USDT, fee 10 bps, the
`balanced`-like config above (ATR 2× stop, 1 % risk, targets 1 R / 2 R at 50 % each):

- stop = 100 − 2 × 1.5 = **97**, so R = 3;
- loss per unit at the stop, fees included = 3 + (100 + 97) × 0.001 = 3.197;
- quantity = 1 % × 10,000 / 3.197 = **31.2793**; notional = **3,127.93**, well under the
  10,000 cap;
- risk_amount = 3 × 31.2793 + 197 × 31.2793 × 0.001 = **100.00** (1 % of the account);
- targets: **103** (1 R, close 50 %) and **106** (2 R, close 50 %); rr = **1.0**;
- breakeven after +1 R: the stop moves to entry × 1.001 / (0.999 × 0.9995). For a backtest
  fill of 100.05 that is **100.30**.

```json
{"side": "long", "entry_ref": 100.0, "stop": 97.0,
 "targets": [{"price": 103.0, "r": 1.0, "close_pct": 50.0}, {"price": 106.0, "r": 2.0, "close_pct": 50.0}],
 "quantity": 31.2793243666, "notional": 3127.9324, "risk_amount": 100.0, "risk_pct": 1.0, "rr": 1.0,
 "invalid_reason": null, "equity": 10000.0, "atr": null,
 "trailing": {"type": "atr", "length": 14, "multiplier": 3.0, "activation_r": null, "breakeven_r": 1.0}}
```

### Live flow

1. The signal engine inserts a signal (one row for everyone running that setup).
2. Every user with an active matching activation gets a plan. The rules are the activation's
   `risk_override` if set, else the user's risk profile, else the `balanced` template. The size
   is the profile's `account_size` (10,000 by default). Plans are computed on the candles the
   task already loaded, which include the ATR warm-up the rules need. Profiles are loaded in one
   query per evaluation.
3. Plans are stored in `signal_plans` (unique per signal, user and activation, so re-running a
   job inserts nothing) and listed by `GET /me/signal-plans`.
4. The `user:{id}` WebSocket message gets `plan` (the first activation's) and `plans` (all of
   the user's activations on that setup). A plan with an `invalid_reason` is still stored and
   sent, flagged. Users with `notify = false` get a stored plan but no message. A failing plan
   is logged and never blocks the signal or other users.

Each plan also carries `account_size`, `quote_currency`, `risk_source` (`override`, `profile`
or `default`) and `risk_config`, the exact rules used.

## Profiles, templates, overrides

- `GET /api/v1/me/risk-profile` creates the profile on first read: `balanced`, 10,000 USDT.
  `account_size` is what the user declares; we never connect to an exchange.
- `PUT /api/v1/me/risk-profile` takes `{account_size, quote_currency, config}` or
  `{template}`. A 422 lists every error with its `loc` and `path`.
- `PATCH /api/v1/me/strategies/{id}` with `{"risk_override": {...}}` sets per-activation rules,
  and `null` clears them. It is also accepted on `POST /me/strategies`.

| Template | Stop | Targets | Sizing | Trailing | Guards |
|---|---|---|---|---|---|
| `conservative` | ATR(14) × 2 | 2 R | risk 0.5 % | – | max drawdown 10 % |
| `balanced` | ATR(14) × 2 | 1 R (50 %), 2 R (50 %) | risk 1 % | – | – |
| `aggressive` | ATR(14) × 1.5 | – | risk 2 % | ATR(14) × 3 | – |

## Endpoints

| Method | Path | Access | Notes |
|---|---|---|---|
| GET | `/risk/schema` | JWT / `strategies:read` | JSON Schema of the risk config, the normalised templates |
| GET | `/me/risk-profile` | JWT | created with defaults on first read |
| PUT | `/me/risk-profile` | JWT | `{account_size, quote_currency, leverage, config}` or `{template}`; 422 with paths. GET and PUT also return `leverage` and `ai_risk` (AI setups, below) |
| POST | `/risk/position-size` | JWT / `strategies:read` | calculator (below) |
| GET | `/me/signal-plans` | JWT | your plans with their signal, `Page`; filters `instrument_id`, `timeframe`, `strategy_key`, `since` |
| PATCH | `/me/strategies/{id}` | JWT | also `risk_override` (null clears) |

**Calculator.** Request `{instrument_id, timeframe, side: "buy"|"sell", entry?, stop?, config?,
account_size?}`. Omitted `entry`/`stop` come from the **last closed bar** (its close, and the
stop rule); omitted `config`/`account_size` come from your profile. A `stop` price replaces the
stop rule, and it also allows `risk` sizing without one. The response holds the plan, the bar
it was computed on and the rules used:

```json
{"instrument_id": "…", "timeframe": "1h", "bar_time": "2026-10-16T10:00:00Z",
 "account_size": 10000.0, "quote_currency": "USDT", "config": {"stop": {"type": "atr", …}, …},
 "plan": {"side": "long", "entry_ref": 36512.24, "stop": 35852.45195957,
          "targets": [{"price": 37172.02804043, "r": 1.0, "close_pct": 50.0},
                      {"price": 37831.81608087, "r": 2.0, "close_pct": 50.0}],
          "quantity": 0.1365835236, "notional": 4986.9704, "risk_amount": 100.0,
          "risk_pct": 1.0, "rr": 1.0, "invalid_reason": null, …}}
```

## AI setups (B10)

AI setups come from ai-service (docs/ai-contract.md). B10 adds four things: the per-user risk
values they are sized with, their size for each user, the user's "I took this trade", and two
account guards. Code: `risk_service.ai_risk_inputs`, `app/ai/sizing.py`, `app/ai/takes.py`,
`store.apply_evaluation` (close-out).

### The five fields, mapped onto the profile

There is no parallel model: the values come from the existing profile, and
`ai_risk_inputs(profile)` is the one place that maps them.

| Field (contract) | Comes from | Otherwise |
|---|---|---|
| `balance` | `account_size` | – |
| `currency` | `quote_currency` | – |
| `leverage` | `leverage` (new column, default 100, `0 < leverage <= 10000`) | – |
| `risk_per_trade_pct` | `config.sizing.risk_pct` when `sizing.mode` is `risk` | `AI_DEFAULT_RISK_PCT` (1.0), with the warning `sizing mode is not risk-based; used 1%` |
| `daily_loss_limit_pct` | `config.guards.max_daily_loss_pct` | `AI_DEFAULT_DAILY_LOSS_PCT` (3.0) |
| `max_drawdown_pct` | `config.guards.max_drawdown_pct` | `AI_DEFAULT_MAX_DRAWDOWN_PCT` (10.0) |

`GET /me/risk-profile` returns them read-only as `ai_risk`, with `sources` per field: `profile`
(a profile column), `config` (the risk config) or `default` (a setting), plus the warnings.
`PUT /me/risk-profile` takes `leverage` (optional, `> 0` and `<= 10000`).

Templates: `conservative` 0.5 % (config) / 3 % (default) / 10 % (config); `balanced` 1 %
(config) / 3 % / 10 % (defaults); `aggressive` 2 % (config) / 3 % / 10 % (defaults).

### Size

`GET /ai/setups/{setup_id}/size` (JWT or an API key with `signals:read`: AI setups are global,
so everyone who may read signals may size them) sizes an `ARMED` or `ACTIVE` setup for your
account. Other states give 409, and so does an instrument without specs.

1. **Guards** (below): if one is reached, the answer is `feasible: false`, `lots: 0` and the
   guard in `warnings`. ai-service is not called.
2. **ai-service `/v1/size`**, with the setup exactly as last returned, the instrument's B4
   specs, the account and the risk.
3. **`AI_SIZE_MODE`** decides what happens when ai-service cannot answer:
   - `auto` (default): ai-service first. When it is unavailable (timeouts, connection errors,
     5xx after the client's retries) or has no `/v1/size` yet (404), the backend sizes the
     setup itself (`source: local`, with a warning). The 404 fallback is allowed only while
     `AI_SIZE_LOCAL_FALLBACK_ON_404=true` (the default until Fadi's P6 ships `/v1/size`);
     with `false` a 404 is a 503 like an unavailable ai-service, never a silent local size.
   - `remote`: never falls back; 503 when ai-service is unavailable.
   - `local`: never calls ai-service.

   Another 4xx, or a body outside the contract, is a **contract error**: 502, no fallback,
   logged.
4. **Local formula**, the B4 lot sizing of docs/instruments.md:
   - risk amount = balance × `risk_per_trade_pct` / 100;
   - lots = risk amount / (|entry − sl| × contract size × conversion rate), rounded **down** to
     `lot_step`;
   - below `min_lot`: 0 lots, `feasible: false` and a warning; above `max_lot`: capped, with a
     warning;
   - prices off the tick are rounded first with Fadi's rule: the stop **away from** the entry,
     the target toward it (never a smaller risk);
   - margin = notional in the account currency × **max(`margin_rate`, 1 / leverage)** (Fadi):
     the broker's margin rate when it asks for more than the user's leverage; without a
     margin rate, 1 / leverage. Without a conversion rate the size is not feasible and the
     margin is null, both with a warning. USD, USDT and USDC count as one dollar when there is
     no exact market, with a warning.
5. **Stored** in `ai_setup_sizes`, one row per setup and user, with `source` (`remote`:
   ai-service `/v1/size`, or `local`; a local size **always** carries a warning saying so,
   also with `AI_SIZE_MODE=local`) and `inputs`:
   - `inputs` holds the account, the risk, a hash of the specs, a hash of the setup payload,
     the guards reached and the mode;
   - the same inputs give the stored result without a call;
   - a new balance, risk or leverage, or a setup that moved (ARMED → ACTIVE, a new payload),
     computes it again.

The answer has `lots`, `risk_amount` (account currency; the contract calls it `risk_usd`),
`margin_required`, `feasible`, `warnings`, `source`, `computed_at`, the `inputs` used with their
sources, and `taken`.

**The B4 example**: balance 2,000 USD, risk 1 % = 20 USD, XAU/USD buy at 2400.00 with the stop
at 2395.00. One lot risks 5.00 × 100 = 500 USD, so the size is 20 / 500 = **0.04** lots,
`risk_amount` 20 USD, and margin 2400 × 100 × 0.04 / 100 = 96 USD at leverage 100 (9,600 USD at
leverage 1). Both paths give this result.

`size_setup_for_users(session, setup, user_ids)` is the batch form for B9/B11, used when a
setup becomes ARMED:
- it loads the profiles in one query;
- it runs at most `AI_SIZE_CONCURRENCY` (4) ai-service calls at once;
- it returns one result or one error per user, so one broken profile does not stop the others.

### Taken trades

| Method | Path | |
|---|---|---|
| POST | `/ai/setups/{setup_id}/take` | body `{lots?, entry_price?}`; only while `ARMED` or `ACTIVE` (409 otherwise); 201 the first time, 200 with the same take afterwards |
| DELETE | `/ai/setups/{setup_id}/take` | undo, while the setup has not ended (409 after) |
| GET | `/me/ai/trades` | your takes, newest first (`Page`), with the setup's state, `realized_r` and `pnl` |

A take records:
- **`lots`:** your stored size by default.
- **`risk_amount`:** the risk of those lots at the setup's stop, in your account currency. It
  comes from the stored size, or from the specs when there is none.
- **`entry_price`:** optional.

When `apply_evaluation` records the end of the setup, in the same transaction:

| The setup becomes | The take gets |
|---|---|
| `CLOSED` | `closed_at`, `realized_r`, `pnl = realized_r × risk_amount`, `close_reason` (the transition's reason) |
| `EXPIRED`, `INVALIDATED` | `realized_r = 0`, `pnl = 0`, `close_reason` (`expired`, `invalidated` or the reason) |

A take already closed is never changed again, so a replayed response changes nothing.

### Guards (checked before every size)

The balance is declared and we never read a real account, so the rules are simple on purpose.
They use the `pnl` of your **closed takes**, and they apply even if ai-service checks the same
limits.

- **Daily loss.** Add up the `pnl` of the takes closed since 00:00 UTC today. If the loss is at
  least `daily_loss_limit_pct` of the balance: `daily_loss_limit_reached`.
- **Drawdown.** Run a total of `pnl` over the takes closed since the balance was last set
  (`risk_profiles.balance_set_at`, set by every PUT that changes `account_size`; null means all
  takes count). The drawdown is the fall from the highest point of that total (0 at the start)
  to now, as a % of the balance. At `max_drawdown_pct` or more: `max_drawdown_reached`.

Worked examples, on 2,000 USD with 1 % risk (1R = 20 USD):

- **Daily loss, 3 % limit (60 USD).**
  - A −2R take today: −40 USD (2 %). Still feasible.
  - A second −2R today: −80 USD (4 %). `daily_loss_limit_reached`, and ai-service is not
    called.
  - Takes closed yesterday do not count.
- **Drawdown, 5 % limit (100 USD).** Three takes on earlier days: +1R, −3R, −3R.
  - After the first, the total is +20 and the highest point is 20.
  - After the second, the total is −40: 60 USD (3 %) below the highest point, still feasible.
  - After the third, the total is −100: 120 USD (6 %) below it, so `max_drawdown_reached`.
  - A new balance starts the window again.

## Backtests

`POST /backtests` `config` accepts `stop`, `trailing`, `take_profit`, `sizing`, `guards` and
`check_entry_bar` next to the Y11 fields (`exits.stop_loss_pct` and `exits.take_profit_pct` are
still accepted). A 422 lists the errors with their paths
(`{"loc": ["body", "config", "stop", "multiplier"], "path": "stop.multiplier", …}`).

`"risk_profile": true` applies your profile: its rules, `fee_bps` and `account_size` (as
`initial_capital`, converted when the profile's currency is not the instrument's quote
currency: [above](#backtests-and-plans-in-another-account-currency-b9)). Fields in the request win, and a Y11 `exits.stop_loss_pct` /
`take_profit_pct` replaces the profile's stop / take profit. The profile is snapshotted into
the stored config (`config.risk_profile`: template, account size, currency, rules,
`updated_at`), so the backtest stays reproducible after the profile changes. Results include
the metrics above; trades include `initial_stop`, `risk_amount`, `r_multiple` and `fills`;
the chart markers show partial exits (`Partial TP`), trailing (`Trail`) and breakeven (`BE`)
exits.
