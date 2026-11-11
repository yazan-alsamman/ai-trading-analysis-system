# Level families on gold 5m, focused version (draft registration)

**Status: APPROVED by Fadi 2026-11-11 ("Accept all defaults"): every [D#] default stands. Nothing built or run.** From Fadi's `LEVEL_FAMILIES_SPEC.md`, cut down
by his choice ("Focused version"). Items marked **[D#]** carry a default that stands unless Fadi
changes it; on his answer this file is frozen (tag `levels-spec`) before any code reads prices.

Repo rules apply: closed bars only, `HistoryExport` only, the five FX lockbox files sealed, every
look in `docs/phase3/TRIALS.md`, no change after a result without a dated addendum.

## 1. What changed from the full plan, and why

| Full plan | Focused | Why |
| --- | --- | --- |
| About 210 families (170 arbitrary) | **24 families** (13 real, 11 grids) | 170 grids with no market reason guarantee a chance winner; round numbers, the one grid with a reason, failed on six markets (`LEAD_GRID.md`) |
| Break, rejection, magnet | **Break and rejection** | the magnet was tested on 2026-11-11 with real levels: reached less often than any point at the same distance (`GOLD_MAGNET.md`) |
| 630-5,000 cells | **8 primary tests** (family type x behaviour, pooled), 48 secondary | the planted-edge check (`INJECT.md`): +0.05 R needs about 3,000 trades for t = 3; pooling by type gets there |
| Discovery 2018-2021, confirmation 2022-2024 (both seen) | **Discovery on gold 2012-2021; confirmation on the five FX pairs** (never read for level families), then the demo | gold has no unseen history; FX is clean for this question |

## 2. Families (24)

**Real (13):** levels from closed bars only; "live" as in §2.1.

| Family | Levels |
| --- | --- |
| PREV-D | previous trading day high, low, close (day 17:00-17:00 New York) |
| PREV-W | previous week high, low, close |
| SESS-A | Asian range high and low (19:00-02:00 New York), known from 02:00 |
| SESS-L | London morning high and low (02:00-07:00 New York), known from 07:00 |
| SWING-15, SWING-1H | confirmed swing highs and lows, 3 bars each side, on 15m / 1h |
| LIQ | equal highs / lows: two 1h swing points within 0.1 x ATR(14, 1h) |
| FVG-15, FVG-1H | fair value gap proximal edges, 15m / 1h, gap >= 0.1 x ATR of that frame |
| IFVG-15, IFVG-1H | an FVG a 5m bar has closed through; its edges with the role flipped |
| PIVOT | previous day's P, R1-R3, S1-S3 |
| FIB | 38.2, 50, 61.8% of the previous day's range |

**Grids (11):**

| Family | Levels | Transfers to FX |
| --- | --- | --- |
| RND-10, -25, -50, -100 | multiples of $10, 25, 50, 100 | no (gold units) |
| PCT-0.25, -0.5, -1 | 1,000 x (1 + p)^k, p = 0.25, 0.5, 1% | yes |
| ANC-D-0.5, ANC-D-1, ANC-NY-0.5, ANC-NY-1 | the day's open (18:00 New York) / the New York open (09:30) +/- k x step, step = 0.5 or 1 x the previous day's ATR(14, D1) | yes |

### 2.1 Level life **[D2]**

Grids are permanent. Day, week, session, pivot and Fib levels live for their day (or week). Swing,
LIQ and FVG levels live until a 5m bar closes beyond them by b, or 5 trading days. An FVG closed
through becomes an IFVG and lives 5 more trading days.

## 3. Events (at the close of a 5m bar; nothing after it)

ATR = ATR(14, 5m) at the signal bar. Neighbours: the nearest live levels of the same family above
and below.

- **Break** up: previous close <= L and close > L + b, b = **0.25 x ATR [D5]**. Down mirrored.
- **Rejection**: the bar trades through L from the previous close's side and closes within
  tau = **0.05 x ATR [D5]** of L. From below: sell; from above: buy. No confirmation bar.

## 4. Trade

| Item | Rule |
| --- | --- |
| Entry | market, the next bar's open (Ask for a buy: open + that bar's spread) |
| Break target / stop | the next level beyond / **the midpoint between the broken level and the one behind it [D6]** |
| Rejection target / stop | the level on the side it came from / **the midpoint between L and the next level beyond [D7]** |
| Cost filter | target distance >= 3 x round-trip cost; **stop distance >= 1.5 x cost [D8]**; else no trade |
| 5-hour rule **[D9]** | at 5 hours: if the trade is at +1 R or more, the stop goes to +1 R and it runs; otherwise it closes at market |
| End of day | everything closes at 13:00 New York; **entries 02:00-13:00 New York only [D12]** |
| Books | one open trade per family; a signal during a trade is skipped and counted |
| Same bar | a 5m bar reaching stop and target counts as the stop |

## 5. Costs

- **Raw** (the data's account): recorded spread + $0.07 commission, + $0.10 slip on stop exits.
- **Standard** (Fadi's live account): no commission; spread = **max(recorded spread, $0.35) [D10:
  measure it on your account for a week and replace 0.35]**, + $0.10 slip.
- Every result also at 2x cost.

## 6. Judging

**The main question: does the location of a family's levels matter?** For each family, 200
shifted copies (grids: a uniform shift within one step; real families: within +/- half their median
spacing; seed 20261116) run through the same rules. A family's excess = its mean net R minus the
mean of its shifted copies.

**Primary tests (8):** {real, round, percent, anchored} x {break, rejection}, each pooling its
families' trades.

- Discovery, gold 2012 to 2026-01-09 minus the lockbox, i.e. **2012-2021**: mean net R (Raw) >=
  +0.03, > 0 at 2x cost, excess over the shifted copies with a 4-week block bootstrap t >= 3,
  Holm over the 8.
- **Secondary (48 = 24 families x 2):** the same at family level, mean >= +0.05, at least 300
  trades, Benjamini-Hochberg 10%, no year above half of the total R. Reported; the primary decides.
- Also reported: Standard-account costs, trades a day, win rate, holding time, by year and session.

**Confirmation [D11]:** a primary test that passes is run once on the five FX pairs, 2016 (AUDUSD
2018) to 2026-01-09, with the families that transfer (real, percent, anchored; not round): same
sign, mean net R >= +0.03, Holm p < 0.05. FX costs as `LEAD_GRID.md`. Then a demo shadow.

**Power (stated before outcomes):** stage L0 counts the trades per family and type on 2012-2021 and
states the smallest mean R each primary test can see at t = 3, before any outcome is computed.

## 7. Stages

| Stage | Work | Gate |
| --- | --- | --- |
| L0 | families, events, trade builder with no-look-ahead tests; **counts only** + power | Fadi's go |
| L1 | discovery (8 primary + 48 secondary) | §6 |
| L2 | confirmation on FX, once | §6 |
| L3 | demo shadow | the demo's stop rules |

If no primary test passes L1, the study ends with a negative report. Count in `TRIALS.md`: 8
primary + 48 secondary cells.

## 8. Decisions with defaults (answer only where you disagree)

| # | Default |
| --- | --- |
| D1 | the 13 real families above (add order blocks or VWAP if you want them) |
| D2 | level life as §2.1 |
| D5 | b = 0.25 x ATR(5m), tau = 0.05 x ATR(5m) |
| D6 | break stop at the midpoint behind the broken level |
| D7 | rejection stop at the midpoint beyond the level |
| D8 | stop at least 1.5 x cost |
| D9 | at 5 hours: below +1 R closes |
| D10 | Standard spread 0.35 until measured |
| D11 | the pass rules of §6 |
| D12 | entries 02:00-13:00 New York |

## Addendum 1 (2026-11-11, before any outcome; L0 counts only)

Found on a one-year trial of the code (signal counts only): the rule "target = the next level of
the same family, stop = the midpoint to the one behind" needs three levels, so the range families
could not trade their own edges: SESS-A and SESS-L (two levels) gave **no signal**; PREV-D, PREV-W
(high, low, close) traded only the close; FIB only its 50%. **Fadi's decision ("Yes, add
projections"): the range families get their range's projections**: high + 1 and 2 ranges, low - 1
and 2 ranges (`families.projected`). FIB also gets 0% and 100%. SESS-A then gives about 2,700
signals a year, SESS-L about 1,800. LIQ stays as registered (about one event a year: near empty).
Also fixed: a slow loop in the level-life code (no change in what it computes).

## Addendum 2 (2026-11-11, before any outcome)

Speed only, no change in what is computed: the real families' signals are found a trading day at
a time on a bars x live-levels matrix (`events.discrete_signals`), checked identical to the first
version on every real family over 2019 (`discrete_signals_reference`, and a test); the discovery
run computes only the days of 2012-2021. One shifted copy went from 310 s to 53 s, so the 200
copies run on 2 worker processes (memory) in about 1.5 hours.
