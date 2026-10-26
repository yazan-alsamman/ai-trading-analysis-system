# P6 task 7: per-currency exposure (proposal, to agree with Yazan)

Status: **proposal**, not in the contract. `/v1/size` today sees one setup and one account; it
cannot see what the user already holds, so it cannot limit exposure. ai-service stays stateless:
the backend owns the open positions (B10) and sends them.

## Why

Six instruments share one currency: every trade is long or short USD. Three buys of EUR/USD,
GBP/USD and AUD/USD at 1% each are about 3% of the balance on one bet (USD falls). A per-trade
limit does not see that.

## Measure

Risk at the stop, split by currency leg, in the account currency:

- a trade on `BASE/QUOTE` that risks `R` (its `risk_usd`) puts `+R` on the currency it is long
  and `+R` on the one it is short, each with its sign: buy EUR/USD = long EUR `R`, short USD `R`;
  buy XAU/USD = long XAU `R`, short USD `R`; buy USD/JPY = long USD `R`, short JPY `R`;
- per currency, `exposure = |sum of signed R|` over the open positions plus the new setup;
- the limit: `exposure <= max_currency_risk_pct` of the balance, for every currency.

Risk at the stop rather than notional: it is what the user loses if all of them stop out, and it
needs no other price (the contract has none). Correlation between currencies is not modelled.

## Contract change (B7 v0.2)

| Where | Field | |
| --- | --- | --- |
| `SizeRequest` | `open_positions: [{instrument, direction, risk_usd}]` | optional, default `[]`: the user's open positions (or open advised setups), with the risk the backend stored from `/v1/size` |
| `RiskSettings` | `max_currency_risk_pct` | optional; null = no exposure limit |
| `SizeResponse` | `exposure: {currency: pct}` | after the new trade |

Behaviour: when a currency would go above the limit, `lots` is reduced to the largest lot step
that keeps every currency within it (never increased), with a warning naming the currency; if no
lot fits, `feasible: false`. The daily loss and drawdown limits stay with the backend (B10): they
need the account history.

## Open

1. Does the backend size from the user's actual positions (broker) or from the advised setups the
   user marked as taken? v1 has no broker link: the second.
2. Default `max_currency_risk_pct` (proposal: 2 x `risk_per_trade_pct`).
