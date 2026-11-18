# Gold: the previous week's rejection as a demo shadow (PWREJ)

**Added 2026-11-16 (Fadi: "add the previous week rejection as a shadow").**

**Chosen after seeing results**, so it is not evidence of an edge:

- It is the PREV-W rejection cell of the level families (`docs/levels/SPEC.md`), picked from a
  descriptive gross ranking of every tested cell (`docs/phase3/TRIALS.md`, 2026-11-16).
- In the registered level study it did **not** beat its 200 shifted copies: 2012-2021 net
  −0.005 R, t +1.18 against the copies (`docs/levels/discovery.md`).
- Later periods:
  - 2022-2025: +0.095 R.
  - FxPro 2026: +0.475 R on 82 trades.
  - Its daily correlation with the five is +0.01.

**The demo is its test, not its proof**, as with ROUND (`GOLD_ROUND.md` §6).

## 1. Rules (the level study's, unchanged: `docs/levels/SPEC.md` §2-5)

**Levels**, for each trading day (17:00-17:00 New York):

- The previous week's high, low and close (Monday to Sunday by the trading days' dates; the close
  is the week's last trading day).
- The range's projections: high + 1 and + 2 ranges, low − 1 and − 2 ranges.

| Part | Rule |
| --- | --- |
| Rejection (signal bar's close) | The bar trades through a level from the previous close's side and closes within 0.05 x ATR(14, 5m) of it. The level nearest the close counts. From below: sell; from above: buy. |
| Window | The signal bar opens 02:00-13:00 New York on a weekday. The entry bar (the next one) is on the same New York day and closes by 13:00. |
| Entry | At market at the next bar's open |
| Target | The next level on the side the price came from |
| Stop | The midpoint between the level and the next level beyond. No neighbour on either side: no trade. |
| Cost filter | Target at least 3 x cost and stop at least 1.5 x cost from the entry; cost = spread + $0.07 |
| 5-hour rule | At the close of the entry bar + 59 (5 hours): at +1 R or more, the stop goes to +1 R and the trade runs; otherwise it closes |
| End | Everything closes at 13:00 New York |
| Books | One open PWREJ trade at a time; a signal while one is open is skipped |

## 2. In the EA (`tools/mt5/GoldLive.mq5`)

**Identity:** strategy `PWREJ`, magic `MagicBase + 6`, input `TradePWREJ`. The order comment is
`PWREJ <level>` (PWH, PWL, PWC, PWH+1, PWH+2, PWL-1, PWL-2).

**Orders:** a market order with the broker's SL at the stop and TP at the target. It does not use
M8 or the 16:45 exit. The 5-hour rule runs in `Manage`, and the 13:00 close in `Watch`.

**Size:**
- `ShadowRiskPct`, like the other shadows.
- PWREJ's stops are wide ($46-133 on the signals of October-November 2026). When that size rounds
  below the minimum lot, the minimum lot trades, unless it risks more than `PwrejMaxRiskPct`
  (1.5%) of equity; then the trade is skipped (Fadi, 2026-11-16).
- `MaxOpenRiskPct` and the account guards apply as to every strategy.

**Known differences from the Python twin:**
- The cost filter uses the spread at the order. Python uses the entry bar's mean spread.
- A sell's broker SL and TP trigger on the ask; Python uses bid bars.

## 3. Python twin and checks

- `gold_live.pwrej_trades` (the level code itself: `app/levels/events.py`, `trades.py`).
- `gold-demo check` matches it on strategy and fill bar. Its `EA_ON` entry is set to the first
  PWREJ order once it runs on the VPS; until then its Python trades are not expected.
- The live monitor (`GOLD_MONITOR.md`) stays on the five and ROUND as registered.
- PWREJ is judged by the demo's stop rule on its own trades: mean net R at or below −0.10 R at
  its 100th trade, then every 50: off.
- It becomes part of v1 only by a new registered decision after at least 150 demo trades.

## 4. Expected (from the level study, before any demo trade)

- About 0.4 signals a trading day before the cost filter; about 1-2 trades a week after it
  (8 on FxPro, 2026-10-01 to 11-13).
- Exits are often the 5-hour rule or 13:00, not the target.
