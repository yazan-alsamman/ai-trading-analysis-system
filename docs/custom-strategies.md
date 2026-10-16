# Custom strategies (Builder + Composite)

Users can build their own strategies without writing code, in two ways:

- **Builder**: rules made of indicator conditions combined with AND/OR, stored as a JSON
  document.
- **Composite**: 2–5 strategies (global or custom) that vote, combined into one.

A custom strategy has the key **`custom:<uuid>`** and works everywhere a global key such as
`ma_crossover` does: chart preview, backtests, `/me/strategies` activations and the live signal
engine. The editors (web: Elias, mobile: Batoul) are generated from
`GET /api/v1/custom-strategies/schema`.

Definitions are data, never code. The server validates them with Pydantic (unknown keys are
rejected), checks indicator names and parameters against the indicator catalog, and evaluates
the rules with vectorised numpy. It never evaluates or parses user strings as expressions.

## Endpoints (`/api/v1`)

| Method | Path | Access | Notes |
|---|---|---|---|
| GET | `/custom-strategies/schema` | JWT or API key `strategies:read` | JSON Schema of both definitions + the operand catalog (below) |
| POST | `/custom-strategies/validate` | JWT | `{kind, definition, id?}` → **always 200** `{valid, errors[], history, definition, definition_hash}`; rate-limit cost 2 |
| GET | `/me/custom-strategies` | JWT | Your strategies, `Page` (`limit`, `offset`, `kind`), no definitions |
| POST | `/me/custom-strategies` | JWT | `{name, description?, kind, definition, visibility?}` → 201; 422 invalid; 409 name taken; 400 over your limit; 403 `public` as a trader |
| GET | `/me/custom-strategies/{id}` | JWT | Full: `key`, `definition`, `valid` + `errors` (whether it can still run), `history`, `usage` |
| PUT | `/me/custom-strategies/{id}` | JWT | `{version, definition, name?, description?}`: replace the definition; 409 with `current_version` if `version` is stale |
| PATCH | `/me/custom-strategies/{id}` | JWT | `name`, `description`, `visibility` |
| DELETE | `/me/custom-strategies/{id}` | JWT | 204; 409 if one of your composites uses it |
| POST | `/me/custom-strategies/{id}/clone` | JWT | Private copy named `"<name> (copy)"` → 201 |
| GET | `/custom-strategies/public` | JWT or API key `strategies:read` | Everyone's public strategies, newest first, `search` (name), `kind`; author display name and role, no user ids |
| POST | `/custom-strategies/public/{id}/clone` | JWT | Copy a public strategy into your list (private, `cloned_from` set, your limit applies) → 201 |

Accessing someone else's private strategy, by id or by key, always gives **404**, never 403,
so it does not reveal that the strategy exists. `GET /strategies` (the catalog) still lists only
the global strategies.

**Limits per user:** trader 5, analyst / expert / admin 50 (settings
`CUSTOM_STRATEGY_LIMIT_<ROLE>`). Names are 1–60 characters and unique per user (case-insensitive).
Descriptions are at most 500 characters. Only analysts, experts and admins can make a strategy
public.

## Builder

```json
{
  "schema_version": 1,
  "buy":  { "all": [ <condition or group>, ... ] },
  "sell": { "any": [ ... ] },
  "strength": "fixed",
  "category": "trend"
}
```

- `buy` and/or `sell`: at least one. Each is a **group**.
- `strength`: `fixed` (always 1.0, the default) or `rule_ratio` (below).
- `category`: `trend`, `mean_reversion`, `breakout` or `momentum` (required).

### Operands

| Operand | Example | Notes |
|---|---|---|
| Indicator | `{"type": "indicator", "name": "rsi", "params": {"length": 14}, "output": "rsi"}` | Any indicator of `GET /indicators`. Omitted params take their defaults. `output` is required when the indicator has several outputs (e.g. `bollinger`: `upper`, `middle`, `lower`) |
| Price | `{"type": "price", "field": "close"}` | `open`, `high`, `low`, `close`, `volume`, `hl2`, `hlc3`, `ohlc4` |
| Constant | `{"type": "constant", "value": 30}` | A finite number |

All three take an optional **`"shift": n`** (0–100): the value `n` bars ago (never a future
bar). Indicator and price operands also take an optional **`"multiplier": x`** (0 < x ≤ 1000,
default 1), which uses x times the value, e.g. `1.5` × the volume SMA. There is no other
arithmetic.

### Conditions

| Op | Shape | True when |
|---|---|---|
| `>` `<` `>=` `<=` | `{"left", "op", "right"}` | the comparison holds on this bar |
| `crosses_above` | `{"left", "op", "right"}` | `left ≤ right` on the previous bar and `left > right` now |
| `crosses_below` | `{"left", "op", "right"}` | `left ≥ right` on the previous bar and `left < right` now |
| `between` | `{"op", "value", "lower", "upper"}` | `lower ≤ value ≤ upper` (inclusive) |
| `rising` / `falling` | `{"op", "value", "bars": n}` | strictly rising (falling) over `n` bars (1–50): `v[t] > v[t-1] > … > v[t-n]` |

**Groups** are `{"all": [...]}` (AND) and `{"any": [...]}` (OR). They contain conditions and
other groups, nested at most **3 levels** (`buy`/`sell` itself is level 1), with at most
**50 conditions** in the whole definition.

### Semantics

- **Closed bars, no look-ahead.** Bar `t` uses bars `≤ t` only; a signal is actionable at the
  open of bar `t + 1`, like the global strategies.
- **Edge-triggered.** A side fires on the bar where its rule tree becomes **true after being
  false** on the previous bar. A tree that stays true does not fire again until it has been
  false for at least one bar. So "RSI < 30" gives one buy when RSI drops below 30, not one buy
  on every bar while it stays below. The bar before the data counts as false.
- **Conflicts.** If buy and sell fire on the same bar, **no signal is emitted** on that bar.
  There is no "conflict" signal.
- **NaN.** A condition that reads a missing value (warm-up, a data gap, a shift beyond the
  data) is **false**. In an `any` group, the other branches can still make it true.
- **Strength.** `fixed` = 1.0. `rule_ratio` = the fraction of the top-level group's children
  that are true on the signal bar (useful with `any`: 3 of 4 rules true → 0.75).
- **Reason** is `builder_buy` / `builder_sell`.
- **Details** give the operand values of every top-level child on the signal bar, in the same
  order as the definition, so the UI can explain the signal:

```json
{
  "rules": "all", "true": 3, "total": 3,
  "conditions": [
    {"op": "<", "true": true, "left": 31.2, "right": 35.0},
    {"op": "crosses_above", "true": true, "left": 101.2, "right": 100.9,
     "left_prev": 100.7, "right_prev": 100.8},
    {"op": "between", "true": true, "value": 55.1, "lower": 40.0, "upper": 70.0},
    {"op": "rising", "true": true, "value": 12.3, "value_start": 11.8, "bars": 3},
    {"group": "any", "true": true}
  ]
}
```

- **History** (bars of warm-up before the first reliable signal) = the largest indicator
  warm-up (lookback + convergence) + the largest `shift` + the largest look-back of an op
  (`bars` of rising/falling, 1 for crosses) + 1 bar for the edge trigger + 1. It is returned by
  `/validate` and `GET /me/custom-strategies/{id}`.
- Each distinct indicator (name + params) is computed once, however many conditions read it.

### Example: the `ma_crossover` replica

This definition produces exactly the same signal bars as the global `ma_crossover` with its
defaults (EMA 9 / EMA 21, no ADX filter):

```json
{
  "schema_version": 1,
  "category": "trend",
  "buy":  {"all": [{"left":  {"type": "indicator", "name": "ema", "params": {"length": 9}},
                    "op": "crosses_above",
                    "right": {"type": "indicator", "name": "ema", "params": {"length": 21}}}]},
  "sell": {"all": [{"left":  {"type": "indicator", "name": "ema", "params": {"length": 9}},
                    "op": "crosses_below",
                    "right": {"type": "indicator", "name": "ema", "params": {"length": 21}}}]}
}
```

`rsi_reversal` can be replicated with `shift`: buy = all of `RSI[1] < 30` and `RSI >= 30`; sell
= all of `RSI[1] > 70` and `RSI <= 70`.

### Example: RSI + Bollinger + volume

Buy when RSI(14) < 35 **and** the close is below the lower Bollinger band **and** volume is
above 1.5 × its 20-bar average. Sell when RSI(14) > 65.

```json
{
  "schema_version": 1,
  "category": "mean_reversion",
  "strength": "fixed",
  "buy": {"all": [
    {"left": {"type": "indicator", "name": "rsi", "params": {"length": 14}},
     "op": "<", "right": {"type": "constant", "value": 35}},
    {"left": {"type": "price", "field": "close"}, "op": "<",
     "right": {"type": "indicator", "name": "bollinger", "params": {"length": 20, "std": 2},
               "output": "lower"}},
    {"left": {"type": "price", "field": "volume"}, "op": ">",
     "right": {"type": "indicator", "name": "volume_sma", "params": {"length": 20},
               "multiplier": 1.5}}
  ]},
  "sell": {"any": [
    {"left": {"type": "indicator", "name": "rsi", "params": {"length": 14}},
     "op": ">", "right": {"type": "constant", "value": 65}}
  ]}
}
```

The server stores definitions **normalised**: params resolved with their defaults, single
outputs, `shift` and `multiplier` written out explicitly, constants as floats. Two definitions
that mean the same thing get the same hash.

## Composite

```json
{
  "schema_version": 1,
  "members": [
    {"ref": "rsi_reversal", "params": {"oversold": 25}, "weight": 1.0},
    {"ref": "bollinger_reversion", "weight": 1.0},
    {"ref": "custom:4f6c…", "weight": 2.0}
  ],
  "mode": "weighted",
  "window": 3,
  "threshold": 0.5
}
```

- **members**: 2–5. `ref` is a global key (with optional `params`, validated like everywhere
  else) or `custom:<uuid>` (one of your strategies or a public one; **no params**). `weight` is
  in (0, 100], default 1.
- **Votes.** A member *votes buy* on bar `t` if it emitted a buy within the last `window` bars
  (`t − window + 1 … t`, 1–20, default 1) **and no sell since**; the same for sell.
- **mode**:
  - `all`: every member votes the same side.
  - `any`: at least one member votes a side and none votes the other side (conflict → nothing).
  - `majority`: more than half of the members vote the same side.
  - `weighted`: the weight of the members voting a side ÷ the total weight is ≥ `threshold`
    (0 < threshold ≤ 1, default 0.5). If both sides reach it, nothing.
- The output is **edge-triggered** too: it fires when the agreement starts, not on every bar it
  lasts.
- **strength** = the agreement ratio (voting weight ÷ total weight for `weighted`, voters ÷
  members otherwise). **reason** = `composite_buy` / `composite_sell`. **details** list every
  member's vote:

```json
{"mode": "weighted", "window": 3, "agreement": 0.75,
 "members": [{"ref": "rsi_reversal", "weight": 1.0, "vote": "buy"},
             {"ref": "bollinger_reversion", "weight": 1.0, "vote": null},
             {"ref": "custom:4f6c…", "weight": 2.0, "vote": "buy"}]}
```

- **history** = the longest member history + `window`.
- **Nesting.** Composites may contain composites, at most 3 levels deep. **Cycles** (A → B → A,
  or a composite containing itself) are rejected with the cycle in the message. When editing, send
  the strategy's `id` to `/validate` so cycles through it are found.
- Custom members are resolved with the **composite owner's** access (their own strategies and
  public ones). A **public** composite may only contain public custom strategies.

## Validation errors

`POST /custom-strategies/validate` never answers 422 for a bad definition. It lists every
problem with its JSON path:

```json
{
  "valid": false,
  "errors": [
    {"path": "buy.all[2].right.params.length", "loc": ["buy", "all", 2, "right", "params", "length"],
     "message": "length must be between 1 and 1000, got 0"},
    {"path": "sell.any[0].left.output", "loc": ["sell", "any", 0, "left", "output"],
     "message": "required: macd has several outputs (macd, signal, histogram)"}
  ],
  "history": null, "definition": null, "definition_hash": null
}
```

`POST` / `PUT /me/custom-strategies` answer **422** with the same problems in FastAPI's format,
the path included:

```json
{"detail": [{"loc": ["body", "definition", "buy", "all", 2, "right", "params", "length"],
             "msg": "length must be between 1 and 1000, got 0", "type": "value_error",
             "path": "buy.all[2].right.params.length"}]}
```

Structural errors (unknown keys, wrong types, missing fields, unknown ops) are reported first.
Indicator, parameter, output, depth and count errors are reported once the structure is valid.
Paths use `.` for keys and `[i]` for list items, matching the JSON you sent.

## The editor schema (`GET /custom-strategies/schema`)

```json
{
  "schema_version": 1,
  "json_schema": {"builder": {…JSON Schema…}, "composite": {…}},
  "catalog": {
    "kinds": ["builder", "composite"],
    "builder": {
      "operand_types": ["indicator", "price", "constant"],
      "indicators": [{"name": "rsi", "title": "Relative Strength Index", "category": "momentum",
                      "params": [{"name": "length", "type": "int", "default": 14, "min": 1, "max": 1000, "title": "Length"}],
                      "outputs": ["rsi"], "output_required": false, "levels": [30.0, 70.0]}, …],
      "price_fields": ["open", "high", "low", "close", "volume", "hl2", "hlc3", "ohlc4"],
      "ops": [{"op": ">", "title": "is greater than", "operands": ["left", "right"]}, …,
              {"op": "between", "title": "is between (inclusive)", "operands": ["value", "lower", "upper"]},
              {"op": "rising", "title": "is rising (strictly, over N bars)", "operands": ["value"], "bars": {"min": 1, "max": 50}}, …],
      "groups": ["all", "any"], "strengths": ["fixed", "rule_ratio"],
      "categories": ["trend", "mean_reversion", "breakout", "momentum"]
    },
    "composite": {"modes": ["all", "any", "majority", "weighted"],
                  "strategies": [{"key": "ma_crossover", "title": "…", "params": […]}, …],
                  "custom_ref": "custom:<uuid>"},
    "limits": {"max_depth": 3, "max_conditions": 50, "shift": {"min": 0, "max": 100},
               "multiplier": {"min_exclusive": 0, "max": 1000.0, "default": 1},
               "bars": {"min": 1, "max": 50}, "members": {"min": 2, "max": 5},
               "window": {"min": 1, "max": 20}, "threshold": {"min_exclusive": 0, "max": 1},
               "max_nesting": 3}
  }
}
```

Suggested editor flow: build the form from `catalog`, run `/validate` while the user edits
(debounced; it costs 2 rate-limit units), show `errors[].path` next to the field it points to,
then `POST` / `PUT`.

## Preview, backtest, activate

Use the key `custom:<uuid>` (returned as `key`) with **empty `params`**. Sending params for a
custom strategy is 422.

```bash
# chart preview: signals, markers and the indicator lines the rules read
curl -X POST "$API/strategies/custom:$ID/preview" -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"instrument_id": "'$BTC'", "timeframe": "1h", "limit": 500}'

# backtest
curl -X POST "$API/backtests" -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"instrument_id": "'$BTC'", "timeframe": "1h", "strategy_key": "custom:'$ID'",
       "start": "2026-03-01T00:00:00Z", "end": "2026-10-01T00:00:00Z"}'

# live signals
curl -X POST "$API/me/strategies" -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"strategy_key": "custom:'$ID'", "instrument_id": "'$BTC'", "timeframe": "1h"}'
```

- **Preview** works with JWT or an API key with `strategies:read`. The response has
  `params_hash`, the strategy's definition hash.
- **Backtests** store a **snapshot** of the definition in `config.strategy`, together with the
  definitions of every custom member a composite reaches. This keeps results reproducible: a
  backtest reads the same, and a queued one still runs, after the strategy is edited or deleted.

```json
"config": {"initial_capital": 10000.0, "…": "…",
           "strategy": {"key": "custom:…", "name": "RSI + BB + volume", "version": 3,
                        "definition_hash": "…", "kind": "builder",
                        "definition": {…}, "members": {}}}
```

- **Activations** (`/me/strategies`) of a custom strategy have `params = {}` and
  `params_hash` = its definition hash. The live engine runs global and custom setups of a market
  in the same per-instrument + timeframe task, with candles loaded once. Users running the same
  public strategy share one setup: one evaluation and one stored signal, sent to each user's
  `user:<id>` topic. Signals carry `strategy_key: "custom:<uuid>"` (filter
  `GET /signals?strategy_key=custom:…`).

## Edits, visibility and deletion

- **Editing a definition** (`PUT`, `version` = the one you edited) bumps `version` and changes
  `definition_hash`. Active setups **follow the new version from the next bar**: their
  `params_hash` is updated at once, and signals already stored keep the old hash. Signals stay
  idempotent per (market, timeframe, key, hash, bar). Changing only the name or description does
  not bump the version.
- A composite's hash also covers its custom members' definitions. **Editing a member re-hashes
  every composite that contains it** (transitively, for all users) and their activations. The
  composite's own `version` does not change.
- **Making a strategy private** deactivates other users' activations of it, and of their
  composites that can no longer run without it. It is refused (409) while one of your **public**
  composites contains it. Your own activations keep running.
- **Deleting** deactivates every activation of it (`is_active = false`, for all users) and of
  other users' composites that contained it. **Signals and backtests are kept.** It is refused
  with **409** and the composites' names while one of **your** composites uses it, e.g.
  `Used by your composite(s): Combo A, Combo B; remove it from them first`.
- A stored composite that can no longer run (a member deleted or made private by its author)
  shows `valid: false` with the reason in `errors`. Preview, backtest and activation then answer
  422, and the live engine skips it and logs the error.
- **Cloning** copies the definition. Custom members of a composite are referenced, not copied.
  Your own clone is named `"<name> (copy)"` (then `(copy 2)`, …). A public clone keeps its name
  when it is free.

## Library

The same code is in [`libs/strategies`](../libs/strategies/README.md) (pure Python, no
database):

```python
import trading_strategies as ts

ts.BuilderStrategy(definition).generate(df)                     # like a global strategy
ts.CompositeStrategy(definition, resolver=lambda ref: ("builder", defs[ref])).generate(df)
ts.validate("builder", definition)                              # .valid, .errors, .history
snap = ts.snapshot("composite", definition, resolver)          # reproducible, JSON-able
ts.from_snapshot(snap).generate(df); ts.snapshot_hash(snap)
```
