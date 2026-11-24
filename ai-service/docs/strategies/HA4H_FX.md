# Heikin-Ashi flips on 4h, on the five FX pairs (registered before any outcome)

**Registered 2026-11-12, before any outcome on these markets.** Fadi's choice ("Yes, register it")
after `GOLD_HA.md`: on gold, 4h flips had a gross edge over a random side in both periods (+0.066 R,
t 2.6; +0.128 R, t 3.4), reported as a lead because the 4h frame was not the registered cell and
gold has no unseen history. The five FX pairs have never been read for this rule.

Code: `app/research/ha_fx.py`, `python -m app research ha-fx [--export <GOLD M1>]`. Report:
`ha4h_fx_result.md`.

## Rules (as `GOLD_HA.md` H24, on 4h)

- 4h bars of the research store (New York-aligned, as every frame here): EURUSD, GBPUSD, USDJPY
  and USDCAD from the first stored month + 30 days, AUDUSD likewise (from 2018); to 2026-01-09
  (the lockbox stays sealed).
- A Heikin-Ashi colour flip at a closed 4h bar: green buys, red sells, at the next real 4h open;
  the next flip exits at the real open after it and reverses. Flat over the weekend: forced exit at
  the last 4h bar closing by 16:45 New York on Friday; the first flip after the reopen opens again.
- R = ATR(14, 4h) at the signal bar. Cost: the entry bar's recorded spread + commission 0.00007 x
  price (FxPro Raw, as `LEAD_GRID.md`). Note: EURUSD's recorded spread is zero on many bars in
  2021-2023, which understates its cost.
- **Swap, as scenarios** (no swap history exists): each 17:00 New York rollover held costs S pips
  (three on Wednesdays), S = 0, 0.5 and 1 pip (a pip: 0.0001; USDJPY 0.01).
  **The decision uses S = 0.5 pip.**
- E0: the same trades with a random side (seed 20261117, 50 runs).

## Decision (fixed now)

- **Primary:** the five pairs' trades pooled: mean net R (S = 0.5) > 0, > 0 at 2x cost, and the
  excess over E0 with a 4-week block bootstrap t >= 3.
- **The rule generalises** if the primary passes and at least 3 of the 5 pairs have mean net R
  (S = 0.5) > 0.
- Reported, deciding nothing: each pair; S = 0 and 1 pip; gold on FxPro 2016-02 to 2026-11-05
  (4h, same rules, swap scenarios in dollars: $0.10 / 0.20 an ounce a night).
- If it generalises: next, a registered portfolio test with the many-markets project (parked) and a
  demo shadow. If not: the 4h gold reading stays a lead only.

Count: 1 primary cell (+ 5 pairs reported) in `TRIALS.md`.

## Outcome (2026-11-12): does not generalise

`ha4h_fx_result.md`. **Pooled, 0.5 pip: −0.077 R a trade (16,620 trades), t −1.39 against a random
side; 0 of 5 pairs positive.** Gross R on the five pairs is −0.040 to +0.052 (pooled −0.003): the
colour carries no direction there; USDJPY is the only one above zero (+0.052, t +1.6 at 0.5 pip).
Gold on FxPro (reported, seen): gross +0.050, net +0.008 without swap and −0.003 at $0.10 a night.
The 4h gold reading in `GOLD_HA.md` stays a lead that other markets do not support.
