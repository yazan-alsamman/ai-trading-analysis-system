# The path of the five's trades after entry (stage 1: a map, no rule)

**Registered 2026-11-12, before any of these measurements was computed.** Fadi wants each open
trade managed by how it moves (close it, or part of it, when its path says so), not by a rule
fixed at entry. Stage 1 measures whether the path after entry has any structure to exploit; stage
2 (a separate registration) would turn a found structure into management rules.

**Why this comes first.** If price after entry moves like a random walk, no exit rule, however
clever, changes the mean result (optional stopping): exits only trade win rate against win size.
An exit rule adds value only where the path has momentum (a trade that has gone far tends to go
further) or reversion (it tends to come back). `gold_path.md` found the path close to random after
a +0.04 D push in the first 5-15 minutes.

Code: `app/research/trade_path.py`, `python -m app research trade-path`. Report: `trade_path.md`.

## Data

The five demo strategies' trades on XAUUSD (`gold_night.day_strategies`), **2012-2021 only**: the
2022-2026-01-09 data and FxPro stay unread for stage 2's check. R = each trade's own D (its risk).
The path is the price from the bar after the entry bar (the order of prices inside the entry bar
is unknown) to the last 5m bar closing by 16:45 New York, in R from the entry, signed in the trade's
direction; the original stop (−1 R) ends it. The M8 exits are ignored here: this is the market's
path, not the trades' result.

## The measurements (each with a control)

**Control (mirror):** the same entries in the opposite direction (the same path, sign flipped),
and, for the ladder, the driftless random walk's value. A structure is a difference from both.

1. **The ladder:** for k = 0.5, 1, 1.5, ... 3.5 R: of the trades that reached +k R, the share
   that reached +(k + 0.5) R before the stop and 16:45. Random walk (no time limit):
   (k + 1) / (k + 1.5).
2. **Speed:** trades by the time they took to reach +1 R (<= 15 minutes, 15-60, 60-180, > 180):
   for each, the share reaching +2 R and +3 R, and the mean move from the +1 R moment to 16:45 (or
   the stop), in R.
3. **Give-back:** for trades whose peak reached at least +1.5 R and +2 R: at the first bar the
   price is back by 30% and by 50% of the peak, the mean move from there to 16:45 (or the stop).
   Zero under a random walk; negative means "it keeps coming back" (exit), positive "it resumes"
   (hold).
4. **Time without progress:** trades not yet at +1 R after 60 and after 120 minutes: the mean move
   from then to 16:45 (or the stop).

Each mean move is reported with its t (trading days as clusters) for all five together and per
strategy.

## What counts as a structure (for stage 2)

A measurement is a candidate for stage 2 if, on 2012-2021: |t| >= 3 against zero (moves) or
against the mirror (ladder and speed shares), a size of at least 0.05 R, and the same sign in at
least 4 of the 5 strategies. Stage 1 decides nothing else; it is logged in `TRIALS.md` as one
descriptive look.

## Outcome (2026-11-12): two candidates, both pointing the same way

`trade_path_result.md` (3,897 trades, 2012-2021). The report first overwrote this file (Windows
names are case-insensitive); it was restored from git and the report renamed.

- **Speed (candidate):** trades that reach +1 R within 15 minutes (422) go on: from +1 R the mean
  move to 16:45 (or the original stop) is **+0.67 R** (t +3.7, positive in all five strategies);
  70% reach +2 R and 47% +3 R (mirror 65% / -). Slower trades: +0.13 to +0.17 R (t 1.1-1.4).
- **The ladder (candidate):** of the trades that reached +2 R, 79.0% reached +2.5 R against the
  mirror's 72.7% (z +3.3). The other rungs are 2-3 points above the mirror (z 0.2-1.9).
- **Give-back (not a candidate):** after a peak of 1.5 R and 30% back, the mean move after is
  **+0.205 R** (t 2.5), after 50% back +0.127 (t 1.5): on average the trades resume rather than
  keep falling back, so exiting on a give-back would cut gains.
- **Time without progress (not a candidate):** not at +1 R after 60 or 120 minutes: +0.07 / +0.08
  R after (t 1.5): slow trades are not worse.
- Real final +0.211 R against the mirror's +0.107: paths that reach ±1 R tend to keep going
  (intraday trend persistence), which is what both candidates measure.
- **Reading for stage 2:** the path favours holding, not taking profit early, above all when a
  trade gets to +1 R fast. A rule to test: give fast trades more room (no trail until a larger
  profit, or a wider trail) and keep M8 for the rest; judged on 2022-2026 and FxPro.
