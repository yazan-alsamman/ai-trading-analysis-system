# Confluence: are the five's breaks better when others of the five are already open in their direction? (registered before any outcome on the data below)

**Registered 2026-11-12.** Fadi: "Yes, register it".

## 1. Where the idea comes from (disclosed)

Found **after** the run of `RISK_SPLIT.md`, on gold. For each of the five's trades, k = the number
of the five's trades open in the same direction at its entry (`risk_split.open_same`, known at the
entry). Mean net R with slip by k:

| Data | k = 0 | 1 | 2 | 3+ |
| --- | --- | --- | --- | --- |
| XAUUSD store 2012 to 2026-01-09 | +0.009 | +0.048 | +0.136 | +0.135 |
| FxPro GOLD 2016-02 to 2026-11-05 | −0.021 | +0.060 | +0.118 | +0.108 |

About 53% of trades have k = 0. Both gold feeds are therefore **used** for this idea and cannot
test it. A plausible reason, written before the test: several of the five breaking the same way on
one morning marks a trend day; a lone break is more often noise.

## 2. The question

**Hypothesis C:** on markets where the k split was never computed, the five's trades with k >= 1
have a higher mean R than those with k = 0.

## 3. Markets (never read for this split)

| Market | Data | Period | Used before for |
| --- | --- | --- | --- |
| NAS100 | FxPro `#USNDAQ100` M1 export (`data/raw/#USNDAQ100_M1_201501040000_202611092359.csv`), summary bars dropped (`five_nas.lines`) | 2016-02-01 to 2026-11-09 | the five's overall result and RECLAIM (`FIVE_NAS100.md`), the round lead |
| EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD | research store (`HistoryExport`, stops before 2026-01-10; lockbox sealed) | 2016-02-01 (AUDUSD: its first stored month + 30 days) to 2026-01-09 | SMC setups (P3-P4, Stage C), the round lead; **the five never ran on them** |

Silver is left out: it moves with gold and would not be an independent market.

## 4. Trades

The frozen five, exactly as `gold_live.five_trades` (levels, 02:00-16:00 New York window, D = 0.75 x
ATR(4h) / ATR(1h), M8, 16:45 exit, one trade per book), on each market's bars. k as
`risk_split.open_same` over the five (order LVL4H, PIVOT, PIVW, ASIA, PWHL; exit bar >= entry bar).

Costs: NAS100 as `FIVE_NAS100.md` (3.0 points commission, 0.5 point SL slip); FX: commission
0.00007 x the pair's median price over the period, no SL slip; LVL4H's cost cap (0.05) uses these.
**The test uses gross R** (before costs), so the cost model cannot decide it; net R with slip is
reported.

## 5. The test and the pass rule

Per market: d_m = mean gross R (k >= 1) − mean gross R (k = 0). **Pooled: D = the mean of d_m over
the six markets** (equal weights). Interval and one-sided p from a **4-week block bootstrap on
calendar time** (the same blocks drawn for all markets, so their correlation is kept; 10,000
resamples, seed 20261116).

**Hypothesis C passes** if both:

1. D > 0 with one-sided p < 0.05;
2. d_m > 0 in at least 4 of the 6 markets.

## 6. What a pass would and would not mean

A pass says the confluence pattern is general, not a gold accident. It changes nothing in the EA
by itself: any use (skip k = 0 trades, or size by k) needs its own registration, a check on the
**demo's trades from 2026-11-13 on** (the only gold data still unseen for this split), and an EA
step (the EA sizes pending orders before it knows k at the fill).

If C fails, the gold pattern is treated as specific to the data it was found on, and nothing
changes.

## 7. Reported with it (decide nothing)

- Per market: trades, share with k >= 1, mean gross and net R by k (0, 1, 2, 3+), d_m with its own
  bootstrap interval.
- Per market and pooled: the net R of the k = 0 trades alone and of the k >= 1 trades alone (what
  skipping the lone breaks would have given).
- No other variant (other k cut-offs, other weights) is run.

## 8. Bookkeeping

Counted in N, logged in `docs/phase3/TRIALS.md`. Code: `app/research/confluence.py`,
`python -m app research confluence`, committed before the run. Report:
`docs/portfolio/confluence_result.md`.
