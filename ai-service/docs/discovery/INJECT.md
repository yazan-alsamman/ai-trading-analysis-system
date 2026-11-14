# Tool check: can our tests find an edge we plant? (registered before the run)

**Registered 2026-11-11, before any injected run.** Fadi did not accept "nothing beats the five"
and asked whether the tools themselves could be blind. This check plants an edge of known size in
real gold prices and asks whether the same code finds it, at the size the power statement
(`PREREG_2.md` §11) says it should, and not where nothing was planted. It is a check of the tools,
not a market trial: it says nothing about real edges, and it is not added to the trial count.

Code: `app/discovery/inject.py`, `python -m app discovery inject`. Report: `inject_result.md`.

## Part A: the markout map (`map.py`, `markout.py`, frozen at `discovery-map-code`)

- Data: XAUUSD M1, 2018-2021, as the map.
- **Planting:** for every event of one cell, from the bar after t0 the price (open, high, low, close)
  moves by sign x delta x c(t0), linearly over 15 bars, then stays moved (a permanent step, as
  news would be). delta in cost units: **1, 2, 3, 5**. Events and placebos are those of the
  original prices (so the planted cell's events are exactly the ones planted); markouts, E0 and
  every gate run on the planted prices with the frozen code, all 210 cells.
- Cells planted, one per run: F2 PM-30 (about 1,030 events), F3 HIGH+5 (about 1,380), F5p
  BREAK-25 (about 2,580), F3 TOP3+5 (126). 16 runs.
- **Expected if the tools work** (from §11's noise and the gates):
  1. delta = 1: never passes (below the 2-unit size gate).
  2. delta = 3 and 5 in the three large cells: passes all four gates at h = 15, 30 and 60 at
     least (t well above 3).
  3. delta = 2: borderline (the size gate sits at 2): pass or fail both acceptable.
  4. TOP3+5 (126 events): passes at delta = 5 at h = 15 at most; at longer horizons its noise is
     too large. Failing elsewhere is expected, not a defect.
  5. The measured lift (mean z planted − mean z unplanted, same cell and h >= 15) is within 2
     standard errors of delta.
  6. False alarms: across the 16 runs, at most 1 unplanted cell passes all four gates.
- **The tools fail the check** if 2 or 5 fails in any large cell, or 6 fails.

## Part B: the trade simulator (`gold_lab.simulate`, the code behind every strategy test)

- Data: XAUUSD 5m, 2012-2021. Signals: one random liquid bar a trading day between 02:00 and
  16:00 New York (seed 20261115), a random side, SL = 1 x ATR(14, 1h), no target, exit after 12
  bars (60 minutes) or 16:45; cost = spread + $0.07; M0.
- **Planting:** after each entry the price moves by side x delta x risk, linearly over 3 bars, then
  stays moved. delta in R: **0, 0.03, 0.05, 0.10, 0.20**.
- **Expected if the simulator works:**
  1. Lift in mean gross R over delta = 0 within 2 standard errors of delta (a little below is
     allowed: an SL hit before the drift completes takes part of it).
  2. Cost R per trade equals (spread + $0.07) / risk computed independently, to 1e-9.
  3. With about 2,500 trades (SE about 0.01 R) a planted 0.05 R gives t >= 3 on gross R.
- **The simulator fails the check** if 1 or 2 fails.

## Count

Not a trial (planted data). Logged in `TRIALS.md` under measurements, with the outcome.

## Outcome (2026-11-11): the computations are right; the map is weaker than registered at long horizons

`inject_result.md`. By the letter of the criteria above, **Part B passes and Part A fails**
(criteria 2 and 6). What the failures are:

**Part B, the simulator: passes.** Planted 0.03, 0.05, 0.10, 0.20 R came back as +0.029, +0.049,
+0.097, +0.198 (within 0.2 SE); cost R exact for every trade; a planted 0.05 R gives t = 3.7 on
2,578 trades. The strategy tests measure what is there.

**Part A, the map.**
- Every planted lift is measured exactly (+1.00, +2.00, +3.00, +5.00 at h >= 15); 1x cost is never
  flagged (criterion 1 holds); 2x is borderline and 3x and 5x pass at 15 minutes in every large cell
  (BREAK-25 at 15-120 minutes).
- **Criterion 2 fails at 60 minutes** (PM-30 at 3x and 5x, HIGH+5 at 3x; PM-30 at 30 minutes at 3x).
  Planting did not move E0 or the placebo; the cause is noise. The standard error of mean z at
  60 minutes is about 1.3-1.5 cost units for these cells, about 3.5x what `PREREG_2.md` §11 implied:
  z divides each markout by its own bar's cost, which is sometimes very small (a tight recorded
  spread), so z has long tails that the §11 calculation (median cost) missed. **§11 overstated the
  map's power at h >= 30-60.**
- **Criterion 6 "fails" by overlap, not by false alarms:** the cells that also passed share the
  planted events: every BREAK-50, -75 and -100 event is also a BREAK-25 event (same bar and sign),
  and 77% of PM-60's are PM-30's. Cells with no shared events: 0 false alarms in 16 runs. The
  registration missed the overlap.
- **A defect found:** E0 for COMEX (13:30 New York every day) has a draw for only 15-18% of events
  (every bar of that hour lies within 60 minutes of a daily event); PM and WM 85-90%. Their E0
  tests rest on few, unusual days. It does not change the map (their |mean z| is below 1.3).

**What this means for the negative map (`map.md`).**
- At 1-30 minutes the verdict stands: an effect of 2-3 cost units in a large cell would have
  been found.
- **At 60-240 minutes it is weaker than written:** an effect of 2-4 cost units there could pass
  unseen. The largest long-horizon readings of the real map (continuation after a $50 / $100 break,
  z +3.4 to +4.1 at 120-240 minutes, t 2.3-2.6) are the size a real effect of that order would
  show; they are equally what chance gives among 210 cells. The map cannot tell which.
