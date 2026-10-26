# Instruments: contract specs, sessions, candle fields

An instrument is a symbol on a data source (`binance:BTC/USDT`, `fxpro:XAU/USD`). Since
migration 0013 it can also carry its **contract specs**: what one lot is, how the volume moves,
which price the candles use and when the market trades. The AI engine runs on
`fxpro:XAU/USD` 1m bars; the specs are the base for sizing in lots and for the data-quality
gate (B5).

## Spec fields

All are nullable: `null` means unknown. `GET /api/v1/market/instruments` and
`GET /api/v1/market/instruments/{id}` return them.

| Field | Type | Meaning |
|---|---|---|
| `contract_size` | double > 0 | units of the base per 1.0 lot (XAU/USD: 100 oz; FX: 100,000) |
| `tick_size` | double > 0 | minimum price increment (XAU/USD 0.01) |
| `lot_step` | double > 0 | volume step, in lots (0.01) |
| `min_lot`, `max_lot` | double > 0, `min_lot <= max_lot` | volume limits, in lots |
| `quote_currency` | varchar(16) | currency of the P&L per price unit; set to `quote_asset` when an instrument is created, `null` on older rows means `quote_asset` |
| `margin_rate` | double in (0, 1] | margin as a fraction of the notional at 1:1 (0.01 = 1:100); `null` = the user's leverage (`max_position_pct`). Stored, not used for sizing yet |
| `cost_per_unit` | double ≥ 0 | fixed trading cost per unit of quantity, price units, per round trip (spread and every cost). Backtests and sizing use it instead of `fee_bps` / `slippage_bps` ([risk-management.md](risk-management.md#fixed-cost-per-unit-per-instrument)). `fxpro:XAU/USD`: 0.25 per oz (Fadi; migration 0021 and `seed-instruments`, only while null); others `null` |
| `price_basis` | `bid` \| `mid` \| `last` | the price the candles are built from (FxPro bars are bid; Binance trades are last) |
| `session_calendar` | jsonb | when the market trades (below) |
| `spec_source` | varchar(32) | where the values came from: `typical`, `fxpro_ctrader`, `manual` |
| `spec_updated_at` | timestamptz | when they were last set |

The database enforces the checks (`ck_instruments_*`): positive values, `min_lot <= max_lot`,
`margin_rate` in (0, 1], `cost_per_unit` ≥ 0, `price_basis` in the list. The API validates the same rules and answers
422 first. On a PATCH, `min_lot`/`max_lot` are checked against the stored values too.

### Where the values come from (`spec_source`)

| `spec_source` | Set by |
|---|---|
| `typical` | migration 0013 and `seed-instruments`: usual broker values, written **only into fields that are null**, so a re-run never overwrites anything |
| `fxpro_ctrader` | the cTrader Open API adapter (a later prompt), with the broker's real values |
| `manual` | an admin. `POST /api/v1/admin/instruments` with any spec, or `PATCH /api/v1/admin/instruments/{id}` that **changes** a spec field (sending the same value changes nothing), sets `spec_source = manual` and `spec_updated_at = now` |

The typical values must be replaced with the broker's own before real money depends on them.
`margin_rate` has no typical value.

| Instrument | contract | tick | lot step | min / max lot | price basis | calendar |
|---|---|---|---|---|---|---|
| `fxpro:XAU/USD` | 100 | 0.01 | 0.01 | 0.01 / 100 | bid | FxPro (below) |
| `twelvedata:EUR/USD`, `GBP/USD` | 100,000 | 0.00001 | 0.01 | 0.01 / 100 | bid | – |
| `twelvedata:USD/JPY` | 100,000 | 0.001 | 0.01 | 0.01 / 100 | bid | – |
| `binance:*` (crypto) | 1 | 10^-price precision | 10^-quantity precision | one step / – | last | – |
| `twelvedata:XAU/USD` | – | – | – | – | – | – (left untouched) |

`fxpro:XAU/USD` (commodity, XAU/USD, price precision 2) is created by migration 0013 and by
`seed-instruments`. It never gets demo candles: `seed-demo-candles` and `simulate-live` refuse
it, because its candles only come from the real feed.

## Session calendar

Stored on the instrument as JSON and validated by `app.schemas.sessions.SessionCalendar`.
Every time is a **wall-clock time in `tz`**, an IANA zone, so DST is handled by the zone and
never by a fixed offset.

```json
{"tz": "America/New_York",
 "week_open": {"day": "sun", "time": "18:00"},
 "week_close": {"day": "fri", "time": "16:55"},
 "daily_breaks": [{"start": "16:55", "end": "18:00"}],
 "holidays": [{"name": "Thanksgiving", "date": "2026-11-26"},
              {"name": "Early close", "start": "2026-12-24T13:00", "end": "2026-12-24T18:00"}]}
```

- `day`: `mon` … `sun`; times `HH:MM` (00:00–23:59). Opens are inclusive and closes exclusive:
  with a 16:55 close, 16:54:59 is open and 16:55 is closed.
- `week_open`/`week_close`: both or neither. Without them the market trades all week (crypto).
- `daily_breaks`: closed every day from `start` to `end`. `end < start` crosses midnight.
- `holidays`: a whole local `date`, or a local `start`/`end` (no offset).

### FxPro XAU/USD

FxPro's MT5 server time is New York time + 7 h (UTC+2 in winter, UTC+3 under US DST). Fadi
verified that the week opens **Monday 01:00 server time** and that there is a daily break
**23:55–01:00 server time**. In New York time that is: open Sunday 18:00, break 16:55–18:00,
close Friday 16:55 (the calendar above, without the example holidays).

| | New York | winter (EST, UTC-5) | summer (EDT, UTC-4) |
|---|---|---|---|
| week opens | Sun 18:00 | **Sun 23:00 UTC** | **Sun 22:00 UTC** |
| daily break | 16:55–18:00 | 21:55–23:00 UTC | **20:55–22:00 UTC** |
| week closes | Fri 16:55 | Fri 21:55 UTC | Fri 20:55 UTC |

On the 2026 transition weekends the change happens between the Friday close and the Sunday
open. Friday 6 March closes 21:55 UTC (EST) and Sunday 8 March opens 22:00 UTC (EDT). Friday
30 October closes 20:55 UTC (EDT) and Sunday 1 November opens 23:00 UTC (EST). A full trading
week has 7,135 − 4 × 65 = **6,875** one-minute bars.

### `app/services/sessions.py`

Pure functions (no database), for B5's data-quality gate ([data-quality.md](data-quality.md))
to tell real gaps from weekends and breaks:

| Function | Returns |
|---|---|
| `is_open(calendar, ts_utc)` | whether the market trades at `ts_utc` (must be timezone-aware) |
| `next_open(calendar, ts_utc)` | `ts_utc` if open, else the UTC instant it next opens |
| `expected_bar_starts(calendar, start_utc, end_utc, timeframe="1m")` | iterator of the UTC bar starts that should exist in `[start, end)`; buckets are epoch-aligned like `time_bucket` (1d = 00:00 UTC), and a bar should exist if the market is open at any moment inside it |

`calendar` is a `SessionCalendar` or its JSON (as stored). Closed stretches are skipped in one
jump to the end of the closure, so a weekend costs a few steps, not 3,000 minutes.

## Candle fields (1m only)

`candles_1m` has three more nullable columns:

| Column | Meaning |
|---|---|
| `spread` | in price units (XAU/USD: 1 point = 0.01), `>= 0` |
| `source` | where the bar came from: `fxpro_ctrader`, `binance`, `seed`, … (lower-cased) |
| `received_at` | when the backend first received the bar; defaults to the insert time |

`CandleIn` (admin ingest and the collectors) accepts all three, optional. On a re-sent bar
`spread` and `source` are only overwritten by a value (a null keeps the stored one), and
`received_at` keeps the **earliest** arrival, so the lag metric stays honest. The demo
generators write `source = "seed"`.

The 1m read endpoint and the WebSocket candle payloads include `spread` only when the candle
has one. Higher timeframes never have it.

`GET /api/v1/market/instruments/{id}/candles` takes `closed_only=true` to leave out the bar that
is still forming (the newest bucket of every aggregate, and the running 1m bar). The answer
then also carries `last_closed_bar` (unix seconds). The default (`false`) is unchanged, because
charts want the forming bar. The rule and the data-quality gate built on it are in
[data-quality.md](data-quality.md).

**Why the check is not in the database:** TimescaleDB 2.17 refuses `ALTER TABLE ... ADD
CONSTRAINT` on any hypertable with compression enabled, even `NOT VALID` ("operation not
supported on hypertables that have compression enabled"). The alternative is to decompress
every chunk, turn compression off, add the check and compress again, which rewrites the
production table. So `spread >= 0` is enforced by `CandleIn` (`ge=0`), the only write path.
Adding the nullable columns is a catalog change only: compressed chunks stay compressed and are
not rewritten (tested in `tests/test_migration_0013.py`).

**Why the continuous aggregates are unchanged:** `candles_5m` … `candles_1d` are a hierarchical
chain (`5m ← 1m`, `15m ← 5m`, `1h ← 15m`, …). A new aggregate column means dropping and
recreating the whole chain and re-materializing all history, a long and risky operation on
production data that runs at backend start. Spread is only needed per bar for evaluation
windows, which later prompts aggregate from 1m themselves.

## Position size in lots

`trading_backtest.sizing` (pure, tested in `libs/backtest/tests/test_sizing.py`):

```
value_per_price_unit = contract_size × conversion_rate        (account currency, 1 lot, 1.0 move)
risk_per_lot         = |entry − stop| × value_per_price_unit
lots                 = risk_amount / risk_per_lot  → rounded DOWN to lot_step → capped at max_lot
                       below min_lot → 0, feasible = false, with a warning
```

- `value_per_price_unit(contract_size, quote_currency, account_currency, conversion_rate)`
- `lots_for_risk(risk_amount, entry, stop, spec, account_currency, conversion_rate)` →
  `LotSize(lots, feasible, warnings, raw_lots, risk_per_lot, risk_amount, …)`. This is the
  price-move risk only; spread and commission are not included.

`conversion_rate` = account currency per unit of the quote currency: 1 for the same currency,
`1 / entry` for USD/xxx with a USD account, otherwise the latest close of a matching market
(the backend looks it up). Without one the size is not feasible: 1 is never assumed. The full
rule, including USDT, is in [risk-management.md](risk-management.md#account-currency-and-lots-b4-sizing-fix).

**XAU/USD.** Balance 2,000 USD, risk 1 % = 20 USD, entry 2400.00, stop 2395.00 (a 5.00 move).
A 1.00 move on 1 lot (100 oz) is worth 100 USD, so 1 lot risks 5 × 100 = 500 USD and
lots = 20 / 500 = **0.04**.

**USD/JPY.** Entry 150.000, stop 149.500, risk 100 USD, contract 100,000, USD account. 1 JPY =
1/150 USD, so 1 lot loses 0.5 × 100,000 / 150 = 333.33 USD and lots = 100 / 333.33 = 0.3000 →
**0.30** after rounding down. Before B4 the plan sized this as if the account were in JPY:
about 150× too small.

**EUR/USD.** Entry 1.08500, stop 1.08300 (20 pips), risk 100 USD: 0.002 × 100,000 = 200 USD per
lot → **0.50**.

**Minimum lot.** Balance 100 USD, risk 1 % = 1 USD on the XAU/USD trade above: 0.01 lot
already risks 5 USD, so `lots = 0`, `feasible = false`, with the warning "the minimum 0.01
lots would risk 5.00 USD, more than the 1.00 USD allowed".

The position-size calculator (`POST /api/v1/risk/position-size`) and the plans of live signals
use this for every instrument with specs. They add `lots`, `lots_feasible`,
`lots_risk_amount`, `conversion_rate` and `sizing_warnings` next to the existing `quantity`.
Their `quantity` still includes the risk config's `fee_bps` (see
[risk-management.md](risk-management.md)). AI setups will be sized by ai-service (`/v1/size`),
not here.
