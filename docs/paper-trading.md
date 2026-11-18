# Paper trading (simulated orders and portfolio)

Each user has a simulated account in **virtual USD**: market, limit and stop orders, stop loss
and take profit, positions and a portfolio summary. There is **no broker and no real money**:
fills use the platform's own 1m candles. Code: `backend/app/paper/` (`service.py`, `engine.py`),
routes `backend/app/api/v1/paper.py`, task `backend/app/tasks/paper.py`, tables
`paper_accounts`, `paper_orders`, `paper_positions` (migration 0026).
Tests: `backend/tests/test_paper_trading.py`.

## Account

- Created on first use with `PAPER_INITIAL_BALANCE` (10,000 USD) and `PAPER_DEFAULT_LEVERAGE`
  (100). Leverage can be changed (1..`PAPER_MAX_LEVERAGE`) when nothing is open.
- **Reset** deletes all orders and positions and starts again with a new balance
  (100..10,000,000).
- **Summary** (the portfolio): balance, equity, unrealized and realized P/L, margin used, free
  margin, margin level %, return %, today's P/L, open positions and pending orders.

## Prices and money

- **Market order:** fills at the close of the latest 1m candle, which must be at most
  `PAPER_MAX_PRICE_AGE_MINUTES` (15) old, else 409 `market_closed`.
- **Limit / stop orders** wait. The engine fills them on closed 1m bars at the order price, or at
  the bar's open on a gap. A limit buy must be below the price, a stop buy above (and the
  opposite for sells), else 422.
- **P/L** = (exit − entry) × lots × contract size (sell: opposite sign). Only USD-quoted
  instruments (USD, USDT, USDC) can be traded, else 422 `unsupported_currency`.
- **Margin** = entry × lots × contract size × max(1 / leverage, instrument margin rate). A new
  position needs that much free margin, else the order is rejected (`insufficient_margin`).
- **Cost** = the instrument's `cost_per_unit` × units, taken at close (as in backtests).
- **Lots:** the instrument's min / step / max (default 0.01 / 0.01 / 100).
- **Limits:** `PAPER_MAX_OPEN_POSITIONS` (50), `PAPER_MAX_PENDING_ORDERS` (50).
- Not modelled: swaps, spread, stop-out / margin call.

## Engine

`paper.tick` (Celery beat, every minute) queues `paper.evaluate` at the minute + 10 s. On the
1m bars closed since the last run, per instrument:

1. pending limit / stop orders that were reached are filled (or rejected for margin);
2. open positions whose stop loss or take profit was reached are closed at that level (or the
   bar's open on a gap). If one bar reaches both, the **stop loss wins**.

Each order and position keeps `checked_until`, so a bar is never used twice and late bars are
still checked. One run at a time (Redis lock); rows are locked against a manual close.

## Notifications

Every fill, rejection and SL/TP close stores a `paper_trade` notification (inbox, WebSocket,
push; Telegram and e-mail are off by default). `data.event` is `order_filled`,
`order_rejected`, `stop_loss` or `take_profit`. The deep link is screen `paper_trade` with
`paper_event`, `position_id` and `order_id`.

## Endpoints (all under `/api/v1/me/paper`, JWT only)

| Method | Path | |
|---|---|---|
| GET | `/account` | the summary |
| PATCH | `/account` | `{leverage}` |
| POST | `/account/reset` | `{initial_balance?}` |
| POST | `/orders` | `{instrument_id, side: buy|sell, type: market|limit|stop, lots, price?, stop_loss?, take_profit?}` → 201 |
| GET | `/orders?status=pending|filled|cancelled|rejected` | |
| DELETE | `/orders/{id}` | cancel a pending order (409 `not_pending` otherwise) |
| GET | `/positions?status=open|closed` | open positions include the current price and unrealized P/L |
| PATCH | `/positions/{id}` | `{stop_loss, take_profit}` (null removes) |
| POST | `/positions/{id}/close` | close at the latest price |

A market order answers with the filled order (its `position_id` is the new position); `PAPER_TRADING_ENABLED=false`
turns every endpoint into 503.
