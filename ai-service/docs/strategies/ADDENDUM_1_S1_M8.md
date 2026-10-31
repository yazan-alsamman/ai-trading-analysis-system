# Addendum 1: S1 managed by M8, judged on the holdout

**Status: REGISTERED, approved by Fadi on 2026-10-31, before the holdout is read.** Written
2026-10-31. It adds
one hypothesis to `PREREG.md` and changes nothing there: no rule, parameter, bundle, statistic,
period or earlier decision.

| Field | Value |
| --- | --- |
| Approved by | Fadi |
| Approval date | 2026-10-31 |
| Commit at approval | the commit that adds this file (`git log -- docs/strategies/ADDENDUM_1_S1_M8.md`); code unchanged since `7bf8142` |

## 1. Origin (post-hoc, disclosed)

This hypothesis was chosen **after** the primary-period results of Stages C and D. On
2026-10-31 an exploratory analysis was run that is not part of the registered plan. It took every
strategy S1-S8 under every bundle M0-M8 (72 combinations) on M0's fixed entry set, test windows
2018-01 to 2024-06. Results before costs and swap:

- S1 + M8 had the highest gross mean R, +0.054.
- It was the only combination whose mean net R under the registered costs and the decision swap
  scenario was above zero: +0.005 R a trade, n = 3,735.

Being the best of 72 on the same data is expected even without any edge: under that null the
maximum would be about +0.05 R above zero. The primary period is therefore **no evidence** for
this hypothesis. It counts as a new trial (trial 26). N for the Deflated Sharpe becomes 26.

Supporting facts, also from the primary period and also not evidence:

- S1 beat its matched random entries in Stage C (d +0.038, 95% +0.001 to +0.075). Before costs the
  margin was +0.040.
- The registered family C procedure chose M8 in most windows for scalp and intraday trades.

## 2. Hypothesis

**H_A1:** on the holdout, S1 under bundle M8 has a mean net R per trade above zero, and above S1
under M0 on the same entries.

- **Rules:** S1 and M8 exactly as frozen at `b9ca2a8` (`strategies.toml`, `app/strategies`,
  `app/management`), with no change of any parameter.
- **Entries:** M0's one-active-trade entry set of S1 on each of the six instruments, as in Stage D.
  Each entry is managed by M8 and by M0 on its own.
- **Net R:** registered costs, SL slippage, and the decision swap scenario (W1 by its own exit
  time).
- **Period:** the holdout, entries from 2024-07-01, with bars loaded to the lockbox start
  (2026-01-10). Unresolved trades are excluded and counted. The lockbox is not read.
- **Reported as well, and not decided on:**
  - S1 under M8's own one-active-trade book;
  - per instrument and per month;
  - before costs;
  - at twice the costs;
  - W0 and W3.

## 3. Decision rule (fixed now)

The holdout has about 20 four-week blocks, below the method condition of 30 (`PREREG.md` section
8). So, as in section 10, **no test and no interval decide anything**. The rule is:

- **"Consistent on the holdout"**: mean net R of S1 + M8 > 0 **and** mean (M8 - M0) > 0 on the
  same entries.
- **"Not consistent on the holdout"**: otherwise.

A consistent result is **not** a validation. S1's statistical status stays **unvalidated**
(Stage C) whatever the holdout shows. Whatever the holdout shows, S1 + M8 also runs in the
forward paper log (section 6). That test is the only route to "validated".

## 4. Power, stated before the holdout is read

S1 gives about 575 trades a year, so the holdout has about 880. The standard deviation of net R
under M8 is 1.29, and the design effect is 1.2. The standard error of the holdout mean is
therefore about **0.052 R**. The chance that the holdout mean is above zero:

| True mean net R | Chance the holdout mean is above zero |
| --- | --- |
| +0.005 (the primary-period value) | about 54% |
| +0.030 | about 72% |
| +0.050 | about 83% |

At the edge the primary period suggests, **the holdout cannot tell S1 + M8 from no edge**: either
answer is close to a coin flip. A "consistent" result would be weak, and so would a "not
consistent" one. Even if real, +0.005 R a trade is economically negligible: 0.5 R per 100 trades,
before any change in costs.

## 5. When the holdout is read

The holdout is read **once** (`PREREG.md` section 10). This hypothesis does not get its own
reading. It is evaluated at the single holdout reading, together with the registered holdout
checks: family C scalp, which passed in Stage D. That reading happens after every report of
families A to D is written and committed. If Fadi decides to close Stage E (the AI models)
without running it, the reading happens after that decision is recorded.

## 6. Forward paper log (the registered final test)

From the day the service serves signals, which is after the export date, S1 + M8 runs in the
forward paper log on the six instruments. The paper log is data nobody has seen, so it is the
only clean evidence for this hypothesis. Everything in this section is fixed now, before any
paper trade exists.

- **Trades:** the served trades, meaning S1's signals under M8's own one-active-trade rule, with
  the registered costs, SL slippage, the decision swap scenario and next-bar fills. The engine is
  the same research and live engine (live = backtest).
- **One look:** the test runs once, on the first date when the paper log holds K >= 30 non-empty
  four-week blocks (about 2.3 years). No interim result decides anything. Monitoring
  (`PREREG.md` section 13) may flag "suspended" in the meantime, which is operational only.
  If 30 blocks are not reached within 4 years, the result is inconclusive.
- **Test:** the section 8 procedure for a family of one: x = net R, and d = x minus its matched
  E0 drawn on the paper-log period. Two tests per component, p = max(p1_x, p2_x, p1_d, p2_d),
  one-sided alpha 0.05, B = 20,000, seeds 20261030 (E0) and 20261031 (bootstrap). delta* = 0.05 R.
- **Result:**
  - **validated (forward paper log)** if passed;
  - **unvalidated** if not passed and U < delta*;
  - **inconclusive** otherwise.

  The Deflated Sharpe is reported with N = 26.

**Power, stated now.** With about 575 trades a year and the same standard deviation and design
effect as in section 4:

| Paper log length | Trades | Smallest edge found 80% of the time | Chance to pass if the true edge is +0.005 R | ... if +0.030 R |
| --- | --- | --- | --- | --- |
| 2.3 years (K = 30, the registered look) | about 1,320 | 0.106 R | about 6% | about 17% |
| 5 years | about 2,900 | 0.072 R | about 7% | about 27% |
| 10 years | about 5,750 | 0.051 R | about 8% | about 43% |

To find an edge of +0.03 R with 80% power would take about 29 years of paper trading. **An edge
of the size the primary period suggests (+0.005 R) cannot be confirmed by any test this project
can run.** At the registered look, the paper log can only confirm S1 + M8 if its true edge is
about 0.1 R or more, about twenty times the primary-period value. The most likely outcome is
therefore "inconclusive". This is said now so that no later result is read as more than it is.
