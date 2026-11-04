# Addendum 2: prices break through support and resistance levels

**Status: REGISTERED, approved by Fadi on 2026-11-04, before any bar of the confirmation
instruments was exported or read.**

**Outcome (2026-11-04).**

- **H_L1 passed** (`levels_confirm.md`): the bounce rate was 48.0% at real levels against 49.0% at
  placebo levels, -1.0 point (95% -1.8 to -0.2), one-sided p 0.010, and all 6 instruments were
  below their placebo. The effect is about a quarter of the exploratory one.
- **H_L2 was stopped by Fadi after 2 of the 6 instruments and was not judged.** Section 5 needs
  all six, so no H_L2 result is claimed.
  - The two finished tester runs, an interim look that decides nothing:

    | Instrument | Trades | Mean net R (95%, 4-week blocks) |
    | --- | --- | --- |
    | NZDUSD | 4,582 | -0.154 (-0.185 to -0.124) |
    | XAGUSD | 7,286 | -0.124 (-0.163 to -0.089) |
    | Both | 11,868 | -0.136 (-0.162 to -0.110) |

  - Commission averaged 0.032 R a trade.
  - 34% of the trades entered at market, because price was already at or through the level.
  - The mechanism is real, but the trade loses well beyond its size after spread, commission and
    entry at market.
It adds one hypothesis (trial 27) to `PREREG.md` and changes nothing there: no rule, strategy,
bundle, period or earlier decision.

| Field | Value |
| --- | --- |
| Approved by | Fadi |
| Approval date | 2026-11-04 |
| Commit at approval | the commit that adds this file (`git log -- docs/strategies/ADDENDUM_2_LEVEL_BREAK.md`) |
| Seed (placebo levels, bootstrap) | 20261104 |

## 1. Origin (post hoc, disclosed)

This hypothesis was found in an **exploratory** analysis on 2026-11-04, after the holdout was
read. The script is `tools/research/levels_explore.py`.

- The analysis tested Fadi's chart reading that price "bounces at support and resistance, or
  breaks and retests".
- The design was written down before any outcome was computed: the levels, the placebo levels,
  the distance, the horizon and the outcome definitions.
- It ran on the six research instruments, with touches from 2018-01-01 and bars to the holdout
  start (2024-07-01). Every bar of that period had been seen before. **That result is therefore
  the origin of the hypothesis, not evidence for it.**

What it showed, with costs left out:

| | Real levels | Placebo levels | Real - placebo (95%, 4-week blocks) |
| --- | --- | --- | --- |
| Touches | 26,030 | 23,630 | |
| Bounce before break (distance D both ways) | 46.1% | 50.0% | **-3.9 points (-4.7 to -3.2)** |
| Continuation after a break (2D beyond before back to the level) | 50.5% | 49.5% | +1.0 point (-0.5 to +2.5) |

- **Every instrument** was below its placebo, by -2.0 to -5.4 points.
- On gold, **every year** from 2018 to 2024 was below its placebo.
- The effect is the opposite of the "bounce" reading: **at a real level, price is more likely to
  go a distance D through the level than D back.**
- After a break there is no extra follow-through: "break and retest" behaves like chance.
- A published mechanism fits this pattern: stop-loss orders cluster just beyond obvious levels
  and round numbers, so reaching a level triggers them and pushes price on (Osler 2000 and 2003;
  check before citing).

Other exploratory looks were made on the same days, on data already seen, and decided nothing:

- the Stage C trades re-costed with the MT5 costs;
- the gold strategies under M8;
- cost terciles;
- S3 by direction;
- the scalp directional diagnostic;
- fixed small SL/TP variants.

They are listed in `docs/phase3/TRIALS.md`. Counting them, the Deflated Sharpe of this trial uses
**N = 60** (26 registered trials plus about 34 exploratory configurations, rounded up).

## 2. Hypotheses

- **H_L1 (mechanism):** at the levels of section 3, the first touch of the day is followed by a
  bounce (D back) **less often** than at placebo levels, and so by a break (D through) more often.
- **H_L2 (trade):** a trade entered **with the break**, at the level when it is touched, has a
  mean net R per trade above zero under the measured costs.

## 3. Rules (fixed now, as in the exploratory script)

### Levels

New York trading days run from 17:00 to 17:00. The levels are:

- **PDH and PDL:** the previous day's high and low.
- **5DH and 5DL:** the high and low of the previous five days.
- **Round numbers:**

  | Instruments | Step |
  | --- | --- |
  | NZDUSD, USDCHF, EURGBP | 0.0050 |
  | EURJPY, GBPJPY | 0.50 |
  | XAGUSD | 0.25 |

### Placebo levels (for H_L1 only)

- PDH, PDL, 5DH and 5DL each move by a random 0.3-1.0 x ATR(14, D1) of the previous day, with a
  random sign.
- Round numbers move by half a step.

### Touch

- A touch is the first 5m bar of the day, opening 02:00-15:59 New York on a weekday, whose range
  crosses the level from the previous bar's close.
- For each PDH, PDL, 5DH and 5DL level, only the first touch of the day counts.
- For round numbers, only the first touch of each round level in a day counts.

### Distance and outcome

- **D** = ATR(14) of the last 1h bar closed before the touch bar opens.
- **Outcome (H_L1)**, decided by which price comes first within 48 bars (4 h):
  - a **bounce** is D back to the side price came from;
  - a **break** is D through the level;
  - the touch bar counts for the break side only;
  - a bar that reaches both is ambiguous and left out;
  - if neither is reached within the 48 bars, the touch is left out too.

### The trade (H_L2)

- A **stop order at the level**, in the direction of approach: a buy stop for a level approached
  from below, a sell stop for one approached from above. It fills at the first touch.
- **SL** = level ∓ D; **TP** = level ± D.
- **Exit at market** after 48 bars if neither is hit.
- Every real-level touch is a trade, and trades may overlap (hedging account).
- **Net R** = the MT5 Strategy Tester result on real ticks (spread, commission, stop fills on
  real ticks, swap), divided by the money risk of the level and SL.

## 4. Confirmation data (never read by anyone in this project)

- **Instruments:** NZDUSD, USDCHF, EURJPY, GBPJPY, EURGBP and XAGUSD (silver; `XAGUSD` or the
  account's own name for it). None of them has been exported, imported, charted or analysed
  here.
- **Source:** the same FxPro account, M1 bars through the MT5 export, and real ticks in the
  Strategy Tester.
- **Period:** touches from 2018-01-01 to 2026-01-10. Bars stop at the lockbox start (2026-01-10),
  and the lockbox stays sealed.
- **One reading.** The data are imported and read once, after this addendum is approved and
  committed. Nothing is tuned on them.
- The instruments' specs (point, digits, contract size, currencies, session hours) come from the
  account. `tools/mt5/ExportHistory.mq5` writes them to `history_meta.json`, and they are held
  in the confirmation command. They are **not** added to `app/config`, which stays as frozen at
  `b9ca2a8`. No cost field is used, because net R comes from the tester. (Clarified 2026-11-04,
  before any bar was exported; no rule, level, distance or decision changed.)

## 5. Decision rules

### H_L1 (mechanism)

Pooled over the six instruments:

- the real-minus-placebo bounce rate is below zero, with a one-sided p < 0.05 (4-week block
  bootstrap from 2018-01-01, B = 20,000, percentile);
- **and** it is below zero on at least 4 of the 6 instruments.

### H_L2 (trade)

The `PREREG.md` section 8 procedure on x = net R alone:

- T1 (percentile) and T2 (t with K - 1 df), p = max(p1, p2) < 0.05 one-sided;
- method condition K >= 30;
- the Deflated Sharpe is reported with N = 60.

### Results

| H_L1 | H_L2 | Result |
| --- | --- | --- |
| passed | passed | **confirmed out of sample**: the rule enters the forward paper log as strategy L-BRK with status `exploratory`. It becomes `validated` only through P9 (lockbox together with the paper log) |
| passed | not passed | **mechanism confirmed, no net edge**: reported, nothing served as a strategy |
| not passed | any | **not confirmed** |

Reported and not decided on:

- per instrument and level type;
- gold-like and FX subsets;
- continuation after a break;
- the trade at twice the measured cost;
- per year.

## 6. Power, stated before the data are read

### H_L1

- About 670 touches per instrument a year, so about 32,000 real touches over eight years on six
  instruments.
- The standard error of the rate difference is about 0.005 (design effect 1.2).
- At the exploratory effect (-3.9 points) the test passes almost surely. At a third of it (-1.3
  points) the chance is about 80%.

### H_L2

- The exploratory gross was +0.04 to +0.11 D a trade on the research instruments. Costs were
  0.05-0.14 D at recorded spreads; the MT5 check found FX spreads near a third of the recorded
  ones.
- With about 30,000 trades, the standard error of mean net R is about 0.008.
- A true +0.02 R is found about 80% of the time.
- A result near zero is the likeliest failure: the mechanism is real, but costs and stop slippage
  eat it.

## 7. Steps after approval

1. Fadi runs `tools/mt5/ExportHistory.mq5`. It writes M1 bars of the six instruments, to
   2026-01-09 23:59 server time, and their specs, to `<MT5 Common>/Files/history/`.
2. The data are imported with the same parser, clock checks and quality report as the research
   instruments, using the specs of section 4.
3. A registered command runs H_L1 once and writes `docs/strategies/levels_confirm.md`. It uses
   the same code as `levels_explore.py`, with the instrument list and steps of section 3.
4. An MT5 EA places the section 3 stop orders, one Strategy Tester run per instrument, and the
   comparison writes the H_L2 result into the same report.
5. The result goes into `TRIALS.md` as trial 27.
