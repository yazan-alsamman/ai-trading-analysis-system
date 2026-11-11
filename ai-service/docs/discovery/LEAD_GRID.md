# Lead test: does a round-number break continue on markets never read for it?

**Registered 2026-11-11, before any outcome on these markets was computed.** Fadi chose "untouched
markets" over a second look at gold's 2022-2026 (`INJECT.md` outcome; the reply of 2026-11-11).

## Why, and what was seen before (disclosed)

- **The lead, chosen after seeing the data:** in the negative map (`map.md`, 2018-2021) the
  largest coherent pattern was continuation after a gold M1 close across a $50 or $100 level:
  z +3.4 to +4.1 cost units at 120-240 minutes, about +0.09 to +0.12 ATR(14, 1h), t 2.2-2.6; not
  significant among 210 cells, and the map is weak at those horizons (`INJECT.md`).
- **Gold's 2022-2026 is not fresh for it:** `GOLD_ROUND.md` traded the same breaks there ($50
  check +0.167 R, $100 +0.111 R). So gold cannot confirm it; only other markets can.
- **The markets below were used before only for other rules:** the five FX pairs for L1 / S1-S8
  SMC setups (P3-P4, Stage C), NAS100 for the five level breaks and RECLAIM (`FIVE_NAS100.md`,
  which found a gross break-side edge of +0.074 R there on daily / weekly levels). No round-number
  grid, no markout after a grid break, has been computed on any of them.

## Markets, grids, periods

| Market | Data | Period | Grids (the two larger round steps, as gold's $50 / $100) | Commission (round trip, price) |
| --- | --- | --- | --- | --- |
| EURUSD, GBPUSD, AUDUSD | research store (`HistoryExport`), stops before 2026-01-10 | first stored month + 30 days to 2026-01-09 | 0.0050 and 0.0100 | 0.00007 x price |
| USDCAD | as above | as above | 0.0050 and 0.0100 | 0.00007 x price |
| USDJPY | as above | as above | 0.50 and 1.00 | 0.00007 x price |
| NAS100 | FxPro export, summary bars dropped (`five_nas.lines`) | 2016-02-01 to 2026-11-09 | 100 and 500 points | 3.0 points |

FX commission approximates FxPro Raw ($7 a 100,000 round trip); the five lockbox files stay sealed.

## Event, markout, controls (as `PREREG_2.md`, frozen code where it applies)

- **Event:** gold's F5p BREAK rule (`events.f5`): an M1 close at or across the first grid level
  above (below) the previous close; sign = the cross; a level counts once per 60 minutes.
- **Horizons:** h = 120 and 240 minutes. Markout as §4 (mid = close + spread / 2, the first bar
  closing within 5 minutes after t0 + h).
- **Units:** ATR(14, 1h) (the existence test: scale-free, without the long tails of z that
  `INJECT.md` found) and z = markout / (spread + commission) (the size reading).
- **E0:** 20 matched bars per event (same year, New York hour, ATR quintile; not within 60
  minutes of an event of the cell), seed 20261112. **Placebo:** the same grid moved by 20 random
  offsets in (0.1, 0.9) of the step, seed 20261113. 4-week blocks, B = 20,000, seed 20261114.
- 6 markets x 2 grids x 2 horizons = **24 cells**.

## Decision (fixed now)

1. A cell **shows continuation** if its ATR-unit excess over E0 and over the placebo are both > 0
   and the larger of the two one-sided p-values passes **Holm over the 24 cells at 5%**.
2. **The lead generalises** if cells show continuation in **at least 2 of the 6 markets**.
3. **Tradable elsewhere** only if such a cell also has mean z >= 2 (its excess over cost).
4. Otherwise the gold pattern is not general: it stays a gold-only observation, supported only by
   `GOLD_ROUND`'s trades.

Reported beside it, deciding nothing: gold 2018-2021 (seen) with the same code as the reference
size; counts per cell; mean z, E0 and placebo means.

**Power, from noise only:** at random gold times the standard deviation of a markout is about
1.1 ATR at 120 minutes and 1.6 at 240. A gold-sized effect (+0.10 ATR) reaches t = 2.5 with about
750 events at 120 minutes and about 1,600 at 240 minutes. Cells with fewer events can show it
only if the effect is larger there.

## Count

One trial of 24 cells in `TRIALS.md`. Code: `app/discovery/lead.py`, `python -m app discovery
lead --nas <NAS100 M1 export>`. Report: `lead_grid_result.md`.
