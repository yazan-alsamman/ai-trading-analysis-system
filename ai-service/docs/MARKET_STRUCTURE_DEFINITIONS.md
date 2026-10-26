# Market structure definitions: Strategy v1 (as implemented)

Status: **v1, frozen as written on 2026-10-22** (code at commit `eb0be0a`: `app/smc/primitives.py`,
`app/smc/events.py`, `app/smc/detector.py`; parameters in `app/config/strategy.toml`). This file
states exactly what the code does; where the two disagree, the code is the record and this file
is wrong. Section 9 lists the variants to test in P3. **Nothing in sections 1-8 changes without a
new version** (a new name, its own parameters and a line in section 10).

Notation: the rules are written for a **buy** (sell-side liquidity, below price, swept from
above). A **sell** runs the same code on mirrored prices (`high' = -low`, `low' = -high`,
`close' = -close`), so every "below / lowest / above" swaps. Times are UTC in the data and New York
for sessions. The trading day runs 17:00-17:00 New York and is named after the day it ends.

## 1. Data the rules see

- Closed bars only, from the research store (`python -m app import`): the entry frame is **15m**;
  the context frames are **1h** and **4h**; **D1** is the trading day. Higher frames are built
  from closed M1 bars and a bar exists only once it has closed.
- Development period only for P2 and for tuning (D23: 2012-01-01 to 2018-01-01); later bars are
  filtered out while the files are read.
- **ATR**: Wilder's average true range, period 14, on the entry frame. `ATR[j]` uses bars up to
  and including `j`; it is NaN for the first 13 bars.

## 2. Swings

- Bar `i` is a **swing high** (period `k`) when `high[i]` is strictly greater than the high of each
  of the `k` bars before it and each of the `k` bars after it. Equal highs are not swings. A swing
  low is the mirror. The last `k` bars of a frame are never marked.
- A swing at `i` is **known from the close of bar `i + k`**, never earlier.
- `k = 3` on the context frames (1h, 4h), `k = 2` on the entry frame (15m).

## 3. Liquidity levels

A level is a price, a side (`high`: buy-side liquidity above price; `low`: sell-side below), a
source, the open time of the bar that made it, the time from which it is usable, and its trading
day.

| Source | Price | Usable from |
| --- | --- | --- |
| `1h`, `4h` | each confirmed swing high / low of that frame (k = 3) | the close of the confirming bar `i + 3` |
| `pd` | each trading day's high and low (D1 bar) | the close of that day (17:00 New York) |

The **level book** is stepped bar by bar on the entry frame. At each bar, in this order:
1. levels whose usable time is at or before the bar's **open** are added;
2. a level is dropped when more than **5 trading days** separate its trading day from the bar's
   (`busday_count(origin day, bar day) > 5`);
3. a level is **spent** (removed and reported as *traded through*) the first time a bar trades
   beyond it: `low < price` for a `low` level, `high > price` for a `high` level. Touching the
   price exactly does not spend it. A spent level never comes back, whatever the outcome.

## 4. Sweep, breakout, shallow

For each level traded through at bar `j` (the first bar beyond it), with `ATR = ATR[j]` (if
`ATR[j]` is NaN the level is spent and nothing is reported):

- Look at bar `j` and then up to `close_back_bars = 1` more bar. At each bar `b`, in order:
  1. update the extreme: the lowest low from `j` to `b` (and the bar where it happened);
  2. `depth = (level - extreme) / ATR`;
  3. if `depth > 1.5`: **breakout** (`too_deep`), settled at `b`;
  4. else if `close[b] > level`: **sweep** if `depth >= 0.1`, otherwise **shallow**; settled at `b`.
- If neither happened by bar `j + 1`: **breakout** (`no_close_back`), settled at `j + 1`.
- If the bars needed are not there yet, the level is **pending** and nothing is decided.

Each outcome is known at the close of its settling bar. Several levels can be traded through by
the same bar; each gets its own outcome.

## 5. CHoCH

For a sweep with extreme bar `e` and settling bar `s`:

- **Reference**: among the confirmed entry-frame swing highs (k = 2) **formed before the extreme**
  (`index < e`), the most recent one confirmed by the current bar (`index + 2 <= j`). If no swing
  high exists before `e`, the result is `no_reference`.
- Scan bars `j = s, s + 1, ..., s + 8` (`choch_window_bars = 8`):
  1. if `j > s` and `low[j] < extreme`: stop, `new_extreme`;
  2. if a reference exists and `close[j] > reference high`: **CHoCH at `j`**.
- Otherwise `window`; if bars are missing, `pending`.

v1 does **not** check the trend before the sweep: any close above that swing high counts (see
variant V2).

## 6. FVG

For a sweep (extreme bar `e`) and its CHoCH (bar `c`), scan `i = e + 2, ..., c` and take the
**first** `i` where:
- bars `i - 2, i - 1, i` are consecutive in time (`open[i] - open[i - 2] = 30 min`; bars across a
  weekend, a daily break or a hole in the data cannot form a gap), and
- `low[i] > high[i - 2]` and `(low[i] - high[i - 2]) / ATR >= 0.1`, with the sweep's ATR.

The FVG is `[high[i - 2], low[i]]` (bullish). No FVG in that range: no pattern.

## 7. Pattern

A **pattern** is a sweep (kind `sweep`), its CHoCH and its FVG. Sweeps of several levels that end
with the same direction, extreme bar, CHoCH bar and FVG bar are **one** pattern with all those
levels. The **primary level**, which names the pattern, is chosen by: source `4h`, then `pd`, then
`1h`; then the level furthest from price (lowest for a buy); then the level key. Pattern id:
`direction:source:side:origin(YYYYmmddHHMM):price`. Patterns are listed in CHoCH order.

Entry, stop, target, fill, invalidation and outcome are **not** part of the pattern; they belong
to the setup builder (P3).

## 8. Outcomes, look-ahead and tests

Outcome codes in v1 (`app/smc/events.py`):

| Stage | Codes |
| --- | --- |
| Level traded through | `sweep`, `shallow`, `breakout` + reason `too_deep` or `no_close_back`, or pending |
| After a sweep | CHoCH, `no_reference`, `new_extreme`, `window`, `pending` |
| After a CHoCH | FVG, or none |

No-look-ahead guarantees, each tested by appending future bars to a prefix and checking that
nothing already decided changes (`tests/test_smc_*.py`): ATR, swings, levels and the level book;
sweep outcomes (only those settled inside the prefix are reported); CHoCH and FVG (a result that
needs missing bars is `pending`, never early); patterns.

Development counts, XAUUSD 2012-2017 (`docs/phase2/patterns_XAUUSD.md`): 9,496 levels traded
through, 4,445 sweeps, 633 CHoCH, 198 patterns (326 before merging multi-level sweeps). Of the 198,
130 reclaim on the sweep bar and 68 on the next bar; the FVG's third bar is at most 2 bars before
the CHoCH in 82%.

## 9. Variants registered for P3 (not part of v1)

Registered on 2026-10-22, after an external specification of Sweep, CHoCH and FVG (a ChatGPT
write-up provided by Fadi on 2026-10-22) was compared with v1, and after Claude's pre-review of the
P2 charts (`docs/phase2/review/REVIEW_claude.md`). Each is a separate, named rule set; v1 stays
the reference.

### V1-S: same-bar reclaim

- **Rule**: `close_back_bars = 0`. A sweep must close back on the bar that trades beyond the level;
  a close beyond the level on that bar is a breakout (`no_close_back`).
- **Why**: the stricter, more common baseline; removes sweeps that held beyond the level for a
  full bar.
- **Expected size**: 130 of the 198 v1 patterns use a same-bar reclaim; the variant can also gain
  patterns, because a level is spent once, so the count is measured, not assumed.

### V2-T: CHoCH only against the prior trend

- **Rule** (buy; sell mirrored): at the CHoCH bar `c`, take the confirmed entry-frame swings (k = 2,
  `index + 2 <= c`) formed before the sweep extreme. The prior structure is **bearish** when the
  last two swing highs are descending (`H_last < H_prev`, lower high) **and** the last two swing
  lows are descending (`L_last < L_prev`, lower low). The close above the reference is a **CHoCH**
  only then; otherwise it is recorded as a **BOS / not CHoCH** (`REJECT_NOT_CHOCH`), and with fewer
  than two swings of each kind as `INCONCLUSIVE_STRUCTURE`.
- **Why**: v1 accepts any break of the last swing high, so a continuation break in an uptrend is
  also called a CHoCH (closer to a "market structure shift after a sweep"). This was left open in
  the design ("CHoCH or BOS", decided in P3).
- **Parameters**: the swing count (2) and the frame (entry, k = 2) are part of the variant; a
  context-frame version (1h) is a separate variant if needed.

### V3-L: strict FVG linkage

- **Rule** (buy; sell mirrored): the FVG must come from the impulse leg that broke structure. The
  leg starts at the lowest low after the last pullback: the bar of the lowest low among the bars
  after the last confirmed entry-frame swing high (k = 2, confirmed by `c`) that formed after the
  sweep extreme; if none formed, the leg starts at the sweep extreme. The FVG's first bar must be
  at or after the leg start; the rest of section 6 is unchanged. A pattern whose only FVGs lie
  before the leg is recorded as `REJECT_UNLINKED_FVG`.
- **Why**: in v1 the first gap after the extreme can sit in back-and-forth trading before the
  final push (charts #8 and #21 of the P2 review).

### V4-A: rejection audit log (engineering, no rule change)

- **What**: one record per level traded through, with every stage's outcome, so each candidate
  ends with exactly one final code and the funnel can be audited. Codes: `ACCEPTED`,
  `MERGED_INTO` (another pattern), `REJECT_SHALLOW`, `REJECT_TOO_DEEP`, `REJECT_NO_RECLAIM`,
  `REJECT_NO_REFERENCE`, `REJECT_NEW_EXTREME`, `REJECT_NO_CHOCH_IN_WINDOW`, `REJECT_NOT_CHOCH` (V2),
  `REJECT_NO_FVG`, `REJECT_UNLINKED_FVG` (V3), `INCONCLUSIVE_STRUCTURE` (V2), `PENDING`.
  `INCONCLUSIVE` and `PENDING` are never counted as failures.
- **Fields**: level (source, side, price, origin, usable from, traded through at); sweep (extreme,
  depth in ATR, ATR, settled at, reclaim bar); structure (reference swing and its confirmation
  time, CHoCH close time, prior-trend swings for V2); FVG (three bar times, bounds, size in ATR,
  linkage rule for V3); final code; rule-set name and data hash.

### V5-S: liquid sessions only, daily break as a break in the data

Registered after the P2 gate failed (section 10): six of the seven rejected patterns came from
thin hours (after the New York close, early Asia, a US holiday) or gold's daily reopen.

- **Rule**: (a) the configured daily break (XAUUSD 17:00-18:00 New York) and the weekend are a
  break in the data for every rule, as holes already are for the FVG: a swing, a sweep, a CHoCH or
  an FVG cannot use a bar inside the break, and the first bar after the reopen cannot be a swing or
  a sweep bar; (b) a sweep counts only when its first bar opens in the London or New York session,
  02:00-16:00 New York, Monday to Friday, and not on a US market holiday (`market_holidays`).
- **Session hours are a parameter of the variant**, fixed before it is run; any other window is a
  new variant.
- **Scope of (a)**: the entry frame (15m), where swings for the CHoCH, sweeps, CHoCHs and FVGs are
  found; bars whose open lies in the configured closed hours are removed from it, and the first bar
  after any gap in it (reopen, weekend, hole) can be neither an entry-frame swing nor a sweep bar.
  Context levels (1h, 4h, previous day) are unchanged.
- **Review**: a new 50-chart sample with seed **731205**, fixed on 2026-10-22 before V5-S was run
  or any of its charts drawn, same tool and criteria as the v1 review.
- **Expected effect on the P2 sample** (descriptive only): rule (b) removes five of the seven
  rejected patterns (#12, #28, #44, #45, #49); #17 (15:30 New York) and #33 (05:00 New York, holiday
  week) are inside the window.

### L1: the design's loosened version (counted, not adopted)

V5-S with the FVG optional (Sweep -> CHoCH is enough; an FVG, if any, becomes a feature) and a
market entry at the decision bar's close (no limit order, so no expiry), held 48 bars after it;
SL and TP as in the setup builder. Registered on 2026-10-22 for the P3 sample count only
(`[variants.L1]`); adopted by Fadi for P3 on 2026-10-22, pooled over the six instruments.
- **Review of L1** (requested by Fadi before P3 task 4; fixed on 2026-10-22 before any L1 chart was
  drawn): 50 patterns of the development period only (bars that closed before 2018-01-01), drawn
  with seed **410733**, spread evenly over ten cells: five instruments (XAUUSD, EURUSD, GBPUSD,
  USDJPY, USDCAD) x pattern with / without an FVG, five per cell where possible (the rest by
  largest remainder). AUDUSD has no bar before 2018 and is not covered. Same tool, same charts
  (ending two bars after the CHoCH), same criteria, with criterion 4 only when an FVG is shaded.

### L1-M: L1 with signal-based position management (registered 2026-10-23, before any run)

Requested by Fadi on 2026-10-23 after the P3 results (53% of L1 trades ended at the 48-bar
horizon). Detection, entry, SL and TP are exactly L1's; only the exit and the position count
change. A **signal** is a confirmed L1 pattern (sweep -> CHoCH) at its decision bar's close,
whether or not its own setup is armed. Per instrument, bar by bar, everything decided with
information available at that bar's close:

1. **One position per instrument.** A new trade opens only when no position is open at the close
   of the decision bar, from an armed setup (L1 entry rules), at that bar's close.
2. **Intrabar exits first.** On each bar after the entry: a gap through the SL at the open, the
   SL, then the TP (an ambiguous bar counts as SL), exactly as L1. SL or TP always beats the
   rules below.
3. **Opposite signal**: a confirmed signal in the other direction closes the position at its
   decision bar's close, in profit or in loss (`opposite`). That signal may open a new trade at
   the same close if its setup is armed. Signals in both directions on one bar close the position
   and open nothing.
4. **Same-direction signal**: no new position. The horizon becomes 48 bars after that signal's
   decision bar, capped at 192 bars after the original entry (`max_hold_bars`). An extension is
   applied at the close it becomes known, before the horizon exit of that same close, and never
   earlier. Each extension is recorded.
5. **Horizon**: otherwise the position closes at the close of its horizon bar (`timeout`), or
   of bar 192 after the entry (`max_hold`).
6. **Costs**: as L1 (round trip spread + max(50%, minimum) at the entry bar's spread; SL slippage
   on SL exits). No separate commission (the extra cost stands for it). **Swap is not modelled**
   (no swap data): the number of 17:00 New York rollovers each trade crosses is reported instead.
   Sensitivity at 0x, 1x, 2x and 3x costs.

**Outcomes kept**: exit reason (`tp`, `sl`, `opposite`, `timeout`, `max_hold`), gross and net R,
bars held, extensions, rollovers. **Primary objective: net R per trade.** Binary targets are
sensitivity analyses only, both reported: net R > 0, and net R >= +0.25R (+0.25R is about 3-6x
the median round-trip cost of 0.04-0.09R, so a trade below it barely pays its costs and risk;
fixed now, not tuned). The positive rate under any target is measured, not assumed.

**E0 for L1-M**: the matched random entries of P3 task 4 (same instrument, year, New York hour,
risk in ATR, TP rule, costs; seed 20261023, 200 replications), each managed by the same rules
with the **real** L1 signal stream of its instrument (closed by an opposite real signal, extended
by a same-direction one, same cap). Random trades do not interact with each other.

**Comparison**: L1 and L1-M, E1 and E0, on the development period (2012-2017) and on the
walk-forward period (2018 to 2024-06) separately, from the same frames (2012 to 2024-07-01). The
secondary holdout and the lockbox are not loaded. No model is trained on L1-M before this
comparison. Logged as trial 6 in `docs/phase3/TRIALS.md`.

### How the variants are decided (fixed now, before any variant is run)

1. Every variant runs on **2012-2017 only** with the same code path and data; the walk-forward,
   the secondary holdout and the lockbox are not loaded. Sample counts for the P3 gate may be
   counted on all pre-lockbox history, as the design allows; no performance is computed there.
2. For V1-S, V2-T, V3-L, V5-S and the chosen combination: the funnel (V4-A) per year, and a **new
   50-chart review** drawn with a seed fixed before drawing, same tool and criteria as P2.
3. In P3, the rules-only result of each (triple barrier, E1 vs E1s of the design) on 2012-2017.
4. A variant replaces v1 only if its review precision is at least v1's **and** it keeps enough
   setups for the P3 gate (at least 1,000 labelled setups). Otherwise v1 stays. The choice is
   recorded in section 10 and frozen before the walk-forward.

## 10. Version history

| Version | Date | Change |
| --- | --- | --- |
| v1 | 2026-10-22 | Sections 1-8 as implemented (commit `eb0be0a`). |
| v1 | 2026-10-22 | **P2 gate not passed**: detection precision 43/50 = 86% (Wilson 95% 74-93%) against 90%. Review by Claude, adopted by Fadi, borderline cases counted as no (`docs/phase2/review/REVIEW.md`, `score.json`). V5-S registered. |
| V5-S | 2026-10-22 | Built as a named rule set (`strategy("V5-S")`; v1 output unchanged, same SHA-256). XAUUSD 2012-2017: 145 patterns (all also v1 patterns); removes 5 of the 7 patterns rejected in the v1 review. Review sample drawn with seed 731205 (`docs/phase2/review_V5-S/`). |
| V5-S | 2026-10-22 | **P2 gate passed**: Fadi's review 46/50 = 92% (Wilson 95% 81-97%). Of the 4 rejections, 3 question the FVG link to the displacement (V3-L) and 1 the clarity of the CHoCH (V2-T). V5-S is the rule set carried into P3; the second condition of §9 (enough setups for the P3 gate) is checked in P3. Agreement with Claude's v1 verdicts on the 15 shared patterns: 12/15. |
| P3 count | 2026-10-22 | Labelled setups 2012-01-01 to 2026-01-09, six instruments (`docs/phase3/counts_*.md`, counts only): v1 543, V5-S 377, L1 1,634 (XAUUSD 134 / 88 / 387). Strict rules miss the P3 gate (1,000) even pooled. |
| L1 | 2026-10-22 | **Adopted for P3 by Fadi: L1, pooled over the six instruments** (1,634 labelled setups). The research question stays on XAUUSD: the model may learn from all six, results are reported for XAUUSD (and per instrument). Open before training: a cost model for the five pairs; the P2 review covered XAUUSD with the FVG required, so L1 patterns without an FVG and the FX pairs have not been reviewed by eye. |
| L1 review | 2026-10-22 | **Eye review passed** (`docs/phase3/review_L1/`, seed 410733, 50 patterns, five instruments, with and without FVG): Fadi 50/50 valid (Wilson 95% 93-100%). Claude's second opinion agrees on every chart but marks 5 as borderline: sweep and CHoCH in the same 15m bar on a scheduled release (all FVG-less); 45/50 = 90% if counted as no. Kept; `bars_sweep_to_choch` and a news-window flag go to the features, and task 4 reports E1 also without same-bar patterns. |
| P3 E0/E1 | 2026-10-22 | Development period, five instruments (`docs/phase3/baselines.md`, `python -m app research baselines`; FX costs: the gold formula with a 0.2 pip minimum and 0.2 pip SL slippage). E1 (L1 rules only) 378 trades, mean net R -0.046 (95% weekly block -0.15 to +0.06); E0 (matched random entries, 200 replications) -0.063; E1 - E0 +0.017 (-0.10 to +0.13), p = 0.36. XAUUSD alone: E1 -0.072, E0 -0.105, p = 0.33. **H1 not supported on the development period**: the rules alone are not distinguishable from random entries with the same mechanics, before or after costs. 53% of E1 trades end at the 48-bar horizon (TP 12%, SL 35%). E1s (V5-S) 86 trades, -0.20. |
| P3 horizon | 2026-10-23 | Horizon trials at Fadi's request (`docs/phase3/TRIALS.md`, trials 4-5): 96 bars E1 -0.066 vs E0 -0.069 (p 0.46); 192 bars E1 -0.100 vs E0 -0.083 (p 0.60). Longer horizons turn timeouts mostly into SL; no edge appears. Horizon stays 48. Trials on the development period so far: 5. |
