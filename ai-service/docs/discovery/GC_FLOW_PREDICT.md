# Does COMEX gold order flow predict the next minutes, and the five's trades? (registered before any outcome)

**Registered 2026-11-14, before any forward (predictive) relation was computed.** The sync check
(`gc_fxpro_sync.md`, 2025-10 to 2025-12) found GC and FxPro's XAUUSD one price at the minute scale
(+0.98, no lead) and GC's order-flow delta moving with FxPro's return **in the same minute**
(+0.60). It looked at nothing after the minute. Fadi: "Yes, register it". This is the first
information in the research that is not derived from FxPro's own bars.

## 1. Data

- **GC minute order flow** (`tools/quantconnect/gc_flow_minutes.py`, unchanged: the active contract
  by the three previous days' volume, extended hours, Lee-Ready signs), computed in QuantConnect's
  cloud. Only summaries leave it.
- **The five's trades on FxPro** (LVL4H, PIVOT, PIVW, ASIA, PWHL; `gold_live.five_trades`): entry
  time (UTC), direction, net R with slip. From the research store to 2026-01-09 and from the FxPro
  export (`D:/GOLD_M1_201501020000_202611052359.csv`, summary bars dropped) for 2026. Pasted into
  the notebook as a packed cell, as FxPro's minutes were.
- **FxPro spread by New York hour** (research store, 2024-2025 median) for the cost bar of §3.

## 2. Periods

- **Primary: 2024-01-01 to 2025-12-31** (GC flow to be built for 2024-01 to 2025-09; 2025-10 to
  2025-12 exists, and only its same-minute relation was looked at).
- **Confirmation: 2026-01-02 to 2026-10-30** (GC flow to be built; the five's trades from the FxPro
  export: the ten months no research has used for anything chosen).

Only minutes whose bar opens 02:00-16:00 New York, Monday to Friday (the five's window), enter
hypothesis A.

## 3. Hypothesis A: the flow leads the next five minutes

- **Signal:** d5(t) = the sum of GC's delta over minutes t-4..t, divided by the sum of GC's volume
  over the same minutes (a flow imbalance in [-1, 1]), known at the close of minute t.
- **Target:** GC's mid change from the close of minute t to the close of minute t+5, in dollars
  (GC and FxPro move together at +0.98; GC's mid avoids FxPro's bid-only close).
- **Test:** the correlation of d5(t) with the target; t from a 4-week block bootstrap of days
  (10,000 resamples, seed 20261124).
- **Economic bar:** the minutes with d5 in its top and bottom deciles (cut-offs from the primary
  period), traded in the flow's direction for five minutes: mean move in dollars minus the cost of
  a FxPro round trip (that hour's median spread + $0.07).

**A passes** if: the correlation is > 0 with t >= 3 on the primary period, > 0 on the
confirmation period, **and** the decile trade's mean net move is > 0 on both.

## 4. Hypothesis B: the flow before a break tells the five's good trades from the bad

- **Signal:** for each trade of the five, s = direction x the delta imbalance of GC over the five
  minutes that closed before the entry minute (as d5, ending at the last minute before the entry).
- **Test:** mean net R of the trades in the top tercile of s minus the bottom tercile (cut-offs
  from the primary period); one-sided p (top better) from a 4-week block bootstrap of trades by
  entry day (10,000 resamples, seed 20261125).

**B passes** if: the difference is > 0 with p < 0.05 on the primary period, **and** > 0 on the
confirmation period.

Holm over A and B on the primary period (the p of A from its bootstrap, one-sided).

## 5. What a pass would mean, and what would follow

- A pass of **A**: GC's flow carries a short lead on gold's price. Its use needs live GC data
  (about $14 a month in CME non-professional fees, more for a commercial service:
  `reports/مزودو بيانات أوامر ذهب كومكس.md`) and a separate registration of any rule.
- A pass of **B**: a filter on the five (skip breaks the flow does not back), tested in its own
  registration with the EA's own fills.
- A fail of both: the order flow, like the price, holds no edge at the minute scale for us; the
  gold intraday search stays closed.

## 6. Reported with it (decide nothing)

- A at the one-minute horizon (t+1) and at fifteen (t+15); the delta alone (one minute), the
  depth imbalance, and the large trades' delta, each with the same target.
- A by New York hour block (02-08, 08-12, 12-16).
- B per strategy, and B with the signal over 1 and 15 minutes.
- The days the GC build skipped or could not read.

## 7. Bookkeeping

Counted in N, logged in `docs/phase3/TRIALS.md`. Code (committed before the run):
`tools/quantconnect/flow_predict.py` (the notebook cell that computes A and B in the cloud and
prints the summary), `app/research/five_export.py` or equivalent (packs the five's trades and the
spread table into a cell). Report: `docs/discovery/gc_flow_predict_result.md`.
