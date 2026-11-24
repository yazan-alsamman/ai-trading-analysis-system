# Is the cost the binding constraint? A cost-sensitivity map of every tested strategy (registered before any outcome)

**Registered 2026-11-14, before any number below was computed.** Claude, asked what had not been
researched enough: many rejected strategies were positive before costs (the five on Nasdaq +0.074 R
gross; the five on six markets +0.03 to +0.10 R gross; pooled cells such as EXTREME:M8 +0.15 R gross
on 2012-2019), so the cost, not the signal, may be what kills them. Fadi: "إي، سجّل تحليل التكلفة".

**This tests no new rule.** It re-prices trades already made by frozen code, to answer one question:
how much cheaper would trading have to be for strategies we rejected to become profitable, and is
that within reach of a real venue? It decides only whether a search for a cheaper venue is worth a
registration of its own.

## 1. Trades

All 96 cells of `POOLED_MODEL.md` §2 (the lab strategies x M0 / M8, the 24 level families x break /
rejection, the six), XAUUSD 5m, 2012 to 2026-01-09, made by the same code (`pooled.build`), each
trade with its gross R, its exit type and its risk (D) in dollars.

**The cost of a trade, in R, split in two:**

- **c_trade** = (spread at entry + $0.07 commission) / risk: what a cheaper venue changes;
- **c_slip** = $0.10 / risk on a stop exit (0 otherwise): kept as it is in every scenario (a stop
  slips on any venue).

(The trades' own net R is gross − c_trade − c_slip; the report checks that this matches the stored
net within 0.001 R on average for every cell, and lists any cell that does not.)

## 2. Scenarios (fixed here)

The trading cost multiplied by **m = 1 (FxPro Raw today), 0.75, 0.5, 0.25, 0** (0 = gross less the
stop slip only): net_m = gross − m x c_trade − c_slip.

For each cell, the **break-even multiplier** m* = (mean gross − mean c_slip) / mean c_trade, on each
period (m* > 1: profitable today; m* < 0: not even at zero cost).

No venue's prices are assumed here. Mapping m to a real venue (CME micro gold futures, another
broker, other hours) needs quoted prices and is part of any follow-up registration.

## 3. Periods

- **2012-2019** (the pooled model's selection years);
- **2022-01-01 to 2026-01-09** (later years; used by many earlier looks, so a check, not fresh);
- **FxPro GOLD 2026-01-12 to 2026-11-05**, read only for the cells that pass §4, with that feed's
  own recorded spread (the never-used ten months).

## 4. What it decides

A cell **comes alive at m** if, at that multiplier: mean net_m > 0 on 2012-2019 **and** on
2022-2026 with t >= 2 there (4-week block bootstrap of days, 10,000 resamples, seed 20261123),
**and** it is not one of the six (they are already traded).

**Cost is a lever worth pursuing** if at **m = 0.5** at least **5 cells** come alive, of which at
least 2 have daily-result correlation below +0.3 with the five on 2022-2026. Then a separate
registration looks for a venue (quotes, the real cost of a trade there, a live check) and tests
the living cells there. Otherwise the cost is not the key and nothing follows.

The Holm-adjusted count (over the 90 cells, at each m) is reported with it; the decision uses the
rule above.

## 5. Reported with it (decide nothing)

- Per cell: trades a day, mean gross, c_trade and c_slip in R, m* on both periods, net at each m.
- How many cells are positive at each m, per period and per group (lab / levels / six).
- What share of each cell's cost is the spread versus the commission, and the spread by New York
  hour (median, gold store, 2022-2026): which hours are cheapest.
- The six at each m (how much a cheaper venue would add to what is already traded).

## 6. Bookkeeping

A look at trades already measured: logged in `docs/phase3/TRIALS.md` and counted in N. Code:
`app/discovery/cost_map.py`, `python -m app discovery cost-map [--export <GOLD M1>]`, committed
before the run. Report: `docs/discovery/cost_map_result.md`.

## Outcome (2026-11-14): cost is not the key

`cost_map_result.md` (code `4555b70`; 98 cells with trades, 399,963 trades; the cost split
reproduces every stored net exactly). At half the trading cost **3 cells come alive (rule §4), all
lab copies of the five's own levels** (LVL4H M8 and M0, PIVOT M8; correlation +0.54 to +0.79 with the
five), none below +0.3: the rule needs 5 and 2. Even at **zero** trading cost only 4 cells are alive,
and the counts of positive cells (48 of 98 on 2012-2019, 46 on 2022-2026 at m = 0) are what no edge
looks like; no cell passes Holm at any m. The gross-positive strategies seen before were mostly
noise, not signals killed by costs. The six's trading cost is already small (about 0.02 R a trade,
their stops are wide): a cheaper venue would add about +0.005 to +0.01 R a trade to them. Reported:
the spread is lowest 08:00-11:00 New York (median $0.08) and highest 16:00-19:00 ($0.14-0.16).
Nothing follows.

