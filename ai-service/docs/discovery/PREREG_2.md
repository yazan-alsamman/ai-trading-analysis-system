# Discovery round 2: pre-registration (markout map on gold)

**Status: APPROVED by Fadi 2026-11-11 ("Approved"), as written. Nothing here has been run.** No markout
(no price after any event) has been computed for any cell below. On approval this file is frozen
with a tag (`discovery-prereg-2`) and the code is frozen at the commit named there; any later change
is a dated addendum that says what it changes and whether a result had been seen.

Plan and history: `PLAN.md` (sections 4-8 are frozen here, with the changes in §12). Detectors:
`app/discovery/events.py` at commit `c105b75`. Counts: `counts.md` (counts only).

## 1. The question

At which scheduled or mechanical moments does gold's move after the moment exceed its trading
cost by a wide margin, beyond what random moments of the same hour and volatility show, and beyond
the same rule without its claimed ingredient? The answer is a map of cells (family x setting x
horizon). Only a cell that passes discovery and confirmation gets a trade designed (§9).

## 2. Data and periods

- **Gold:** the XAUUSD research store (M1 bid bars with the recorded spread; `HistoryExport` only;
  stops before 2026-01-10). It has no FxPro summary bars (`docs/data_quality/FXPRO_SUMMARY_BARS.md`).
- **Calendar:** `data/processed/calendar.parquet` (MT5 calendar, `time_utc`; `calendar_check.md`).
- **Drivers (F1 only):** Dukascopy dollar index from 2019-01-01 and bond from 2020-01-01
  (`events.DXY_FROM`, `BOND_FROM`; earlier minutes hold fake spikes).

| Period | Role |
| --- | --- |
| 2012-2017 | detector debugging only; no markout read |
| **2018-2021** | **discovery** (F1: 2020-2021 only) |
| **2022-01-01 to 2026-01-09** | **confirmation**: survivors only, read once |
| 2026-01-12 to 2026-11-05 (FxPro GOLD, clean) | consistency, exposure disclosed (§10) |
| Forward demo | the decisive evidence |

## 3. Events: 30 cells (frozen)

An event is (family, cell, M1 bar i, sign): t0 = the close of bar i; the sign is the direction
hypothesis; nothing after t0 is read. Exactly as `events.py` at `c105b75`:

| Family | Cells | Event | Sign |
| --- | --- | --- | --- |
| **F3** news (6) | TOP3+1, +5, +15; HIGH+1, +5, +15 | the bar closing d minutes after a release r; TOP3 = NFP, CPI m/m, the Fed decision; HIGH = every high-importance USD release, one per minute | the move from the close at r to the close at r + d |
| **F2** forced flow (8) | PM, WM, COMEX, MONTHEND, each with L = 30, 60 | the bar closing at 15:00 London (PM), 16:00 London (WM), 13:30 New York (COMEX), 16:00 London on the month's last weekday (MONTHEND) | against the move over the L minutes before |
| **F1** unconfirmed move (8) | UNCONF / CONF x k = 0.5, 1 x w = 15, 30 | gold moves >= k x ATR(14, 1h) over w minutes; UNCONF: neither the dollar index fell nor the bond rose with it; CONF: either moved with it by > half its usual w-minute move; 60-minute refractory | UNCONF: against gold's move; CONF: with it |
| **F5p** grids (8) | BREAK, REJECT x $25, $50, $100, $75 | BREAK: an M1 close across a grid level; REJECT: a bar through a level from the last close that closes back; a level once per 60 minutes | BREAK: the cross; REJECT: away from the level |

## 4. Markout and cost

- h = 1, 5, 15, 30, 60, 120, 240 minutes. **30 cells x 7 horizons = 210 map cells** (budget 224).
- mid(t) = close + spread / 2 of the M1 bar closing at t. m(h) = sign x (mid(t0 + h) − mid(t0)),
  using the first bar closing at or after t0 + h and within t0 + h + 5 minutes; otherwise the event
  is dropped at that horizon (weekend and daily break).
- c(t0) = the event bar's recorded spread + $0.07 (round-trip commission), in price.
  **z(h) = m(h) / c(t0)**, in cost units. Also reported: m(h) in ATR(14, 1h) units.

## 5. Controls

- **E0 (matched random moments):** for each event, 20 random M1 bars (seed 20261112) from the same
  year, the same New York hour, the same ATR(14, 1h) quintile (quintiles within the year), Monday
  to Friday, and not within 60 minutes of an event of the same cell; each takes the event's sign.
- **Placebo (the ingredient removed),** the same rule and sign definition:
  - F3: the same New York clock minute on the 5 nearest trading days with no high-importance USD
    release within 60 minutes.
  - F2 daily windows: the window moved 2 hours earlier and 2 hours later, same days (pooled).
    MONTHEND: the 16:00 London rule on the 5 trading days before the month's last one.
  - F1: the two driver series moved by +7 and −7 calendar days (pooled), re-classified.
  - F5p: each grid moved by 20 offsets drawn uniformly in (0.1, 0.9) x the step (seed 20261113).

## 6. Discovery gates (2018-2021; every gate on the same map cell)

Statistics: 4-week blocks (calendar); a block bootstrap (B = 20,000, seed 20261114) of the
difference between the events' mean z and the control's mean z, resampling blocks jointly.

1. **Size:** |mean z(h)| >= 2 cost units. (`PLAN.md` also asked for >= 1 at 2x cost; on z that is
   the same condition, so it is dropped as redundant.) Two-sided: a negative mean means the
   opposite trade; the sign is reported.
2. **Beyond chance:** t >= 3 against E0 **and** t >= 3 against the placebo, both in the sign of
   mean z.
3. **Multiplicity:** Benjamini-Hochberg at 10% over all 210 map cells, with p = the larger of the
   two two-sided normal p-values of gate 2.
4. **Stability:** no calendar year carries more than half of the summed excess over E0 (F1, with
   two years: the same sign in both).
5. **Reported for the map, not a gate:** PBO (CSCV, 16 time blocks); the Deflated Sharpe with N =
   every setting in `TRIALS.md` + 210.
6. **Stop rule:** if no cell passes 1-4, the round ends with a negative report. No second map on
   the same data, no new cells.

## 7. Confirmation (2022-01-01 to 2026-01-09, read once)

Each discovery survivor: the same sign, |mean z| >= 1.5, and Holm-adjusted p < 0.05 over the
survivors (block bootstrap against E0). Then the clean FxPro 2026 window is reported as a
consistency check (no gate; its exposure is disclosed).

## 8. The AI layer (H2'; only if a family has a confirmed cell)

As `PLAN.md` §6: one row per event of that family; label = z(h*) > 1 at the cell's horizon;
features known at t0 (move in ATR, driver confirmation, time of day, grid distance, spread and
volatility percentiles, minutes to the nearest release, release surprise); LR then LightGBM;
walk-forward on 2018-2021 (six-month windows, purge + 1-day embargo); acceptance as
`PREREG_P4.md` (Brier skill > 0, ECE < 0.05). Not run when no cell is confirmed.

## 9. From a confirmed cell to a trade

As `PLAN.md` §8: one trade per cell at its horizon h*, an SL fixed in ATR for cost per R (not
tuned on outcomes), exit by time or M8; market entry unless the curve shows an early adverse dip;
registered as an addendum, with E0, 2x cost and the MT5 real-tick replay; then a shadow on the demo.

## 10. Prior exposure (disclosed)

- **F3:** `GOLD_LOSS.md` found the five's trades at the US data minutes the best bucket (+0.263 R on
  2012-2021, +0.287 on the check). `GOLD_C123.md` C3 traded a TOP3 continuation 15 minutes after
  the release on 2012-2026 (+0.056 R on 2012-2021, +0.030 on the check): close to F3 TOP3+15.
- **F5p:** `GOLD_ROUND.md` traded breaks of round numbers on gold 2012-2026; `GOLD_MAGNET.md`
  found $50 levels reached less often than other points. The grid placebo itself was never run.
- **F1:** `GOLD_USD.md` found no EURUSD lead at 5 minutes; the dollar index and bond were never read
  against gold's later move.
- **F2:** no earlier look at these windows.
- Every period of gold has been seen by about 70 commercial-track looks; only the demo is unseen.

## 11. Power (from noise only; no event outcome read)

The standard deviation of m(h) / ATR(14, 1h) at 20,000 random M1 bars of 2012-2017 (seed 20261112):
0.10, 0.22, 0.39, 0.54, 0.77, 1.12, 1.63 at h = 1 ... 240. The median cost at the events of
2018-2021 is 0.03-0.08 ATR(1h). So the smallest |mean z| that reaches t = 3 (independent events)
is about:

| Cell size (2018-2021) | h = 5 | h = 60 | h = 240 |
| --- | --- | --- | --- |
| F1 CONF-k0.5 (5,076-6,022) | 0.3 | 0.9-1.0 | 1.9-2.1 |
| F2, F3 HIGH, F5p $25 (1,000-2,600) | 0.3-0.5 | 0.9-1.7 | 2.0-3.6 |
| F3 TOP3 (126), F1 UNCONF-k1 (221-392) | 0.8-1.4 | 2.5-4.8 | 5.4-10 |
| F2 MONTHEND (48) | 1.5 | 5.4 | 11 |

Reading: at h <= 15 the size gate (2 cost units) binds, not the t gate; at h >= 120 only large
effects can pass. TOP3, UNCONF-k1 and MONTHEND can pass only with very large effects. News minutes
are noisier than random ones, so F3's real power is lower than shown.

## 12. Changes from `PLAN.md` (for approval)

1. The size gate at 2x cost is the same condition as 2 cost units on z: dropped as redundant.
2. Every cell is two-sided; F3's drift (A) and reversal (B) are one cell read by its sign.
3. The budget is 210 map cells (30 x 7), not 224.
4. F1's discovery years are 2020-2021 only (data faults; Fadi, 2026-11-11).
5. E0 is 20 matched moments per event (the plan's "200" is read as at least 200 per cell).
6. Placebos are defined per family (§5); the daily windows use moved times, not other days.

## 13. Logging

The map is one entry in `TRIALS.md` with N = 210; confirmation one more. Reports:
`docs/discovery/map.md`, `confirm.md`. Code to build after approval: `app/discovery/markout.py`,
`map.py`, `python -m app discovery map|confirm`, with tests on hand-built bars and a no-look-ahead
test, frozen before the first run.

**Approval:** Fadi, 2026-11-11 ("Approved"), as written, including the changes in §12.
