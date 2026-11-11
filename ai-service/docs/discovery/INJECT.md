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
