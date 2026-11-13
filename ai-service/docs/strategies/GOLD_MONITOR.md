# Monitoring the live five and ROUND (registered before it reads the demo beyond its first 8 trades)

**Registered 2026-11-13.** Claude proposed a monitor that judges the demo by all of its trades,
not one reading at a fixed count; Fadi: "Yes, register it". It changes nothing in the EA or the
strategies: it reads the account report each week (`gold-demo check`) and says green, amber or
red, with the action for red fixed here. The demo's first 8 trades (2026-11-10 to 11-12, mean net
R +0.51) were already seen when this was written; every rule below was set without regard to them.

## 1. Why

Per trade the six have a mean of about +0.04 R and a standard deviation of about 1.2 R. The old
rule (`GOLD_V1.md`: stop a strategy whose mean net R is below −0.10 at its 100th trade, then every
50) stops a sound strategy (+0.04) about 12% of the time and lets a broken one (−0.05) through
about 65% of the time, and it reads one number at one moment. The monitor below **replaces it as
the decision**; the old reading stays in the report for continuity.

## 2. The reference (what "as tested" means)

FxPro GOLD, 2016-02 to 2026-11-05 (the demo's own broker and feed; `gold_live.five_trades` with
ROUND), net R with slip a trade:

| Pool | Trades | Mean | SD |
| --- | --- | --- | --- |
| LVL4H | 1,141 | +0.082 | 1.18 |
| PIVOT | 2,116 | −0.019 | 1.36 |
| PIVW | 994 | +0.025 | 1.13 |
| ASIA | 1,695 | +0.041 | 1.17 |
| PWHL | 496 | +0.106 | 1.17 |
| ROUND | 794 | +0.132 | 1.16 |
| **ALL6** | 7,236 | **+0.042** | **1.22** |

The monitor's code recomputes these from the export and refuses to run if any mean differs from
this table by more than 0.002 R (same data, same code).

## 3. The demo's trades

The account report's closed trades with the EA's comments (`gold_demo.demo_trades`): strategy,
open time, net R (money over D x lots x contract), entry slippage, gross R. Order: by open time.
ALL6 = all six pooled.

## 4. Four layers

**A. Process checks (fast: days).** Each week:

| Check | Amber | Red |
| --- | --- | --- |
| A1 match with Python (only when `--export` covers the days) | - | under 90% of demo trades matched, or under 90% of Python's trades in the same days found in the demo |
| A2 entry slippage: mean of slip $ / D over the last 30 trades | above 0.05 R | - |
| A3 trades in the last full calendar week vs 22 expected (FxPro 2026's rate) | outside the Poisson 0.5% / 99.5% bounds | - |
| A4 cost: mean of gross R - net R over the last 30 trades | above 0.03 R (FxPro 2026: 0.008) | - |

**B. Edge estimate (Bayesian, slow).** For ALL6 and each strategy: a normal prior on the mean net R
with mean = **half** the reference mean (a haircut for decay and selection) and SD 0.10 R; the
likelihood normal with the reference SD; the posterior after the demo's trades. Reported: the
posterior mean, a 90% interval and **P(edge > 0)**. Red: ALL6 P(edge > 0) < 0.10. A strategy with
P(edge > 0) < 0.05 is marked **review** (with six strategies one can get there by chance; it is
not stopped by this alone).

**C. CUSUM on ALL6 (slow).** "Good" = +0.042, "broken" = −0.058 (0.10 R worse), SD 1.22. Each
trade x adds z = ((−0.058 − 0.042) x − ((−0.058)^2 − 0.042^2) / 2) / 1.22^2; S = max(0, S + z),
from S = 0 at the demo's first trade. **Red when S >= h.** h is the smallest multiple of 0.25 for
which the average run to a false alarm is at least 2,000 trades, simulated on 2,000 paths built
from the reference ALL6 trades resampled in whole calendar weeks (seed 20261117); the report gives
h, that run length and the average run to an alarm when the trades are 0.10 R worse.

**D. Drawdown against history (immediate).** The current drawdown of the demo's cumulative net R
(ALL6, from its peak to now) against 10,000 paths of the same number of trades drawn from the
reference in whole calendar weeks (seed 20261118): its percentile. Amber above the 95th, red above
the 99th.

Expected speed, stated before any reading: with a 0.10 R gap and SD 1.22, B and C need about
**800-900 trades** (about 9-10 months at 22 a week) to tell a broken edge from a sound one. Only A
and D can react within weeks.

## 5. Status and actions

- **Green:** nothing to do.
- **Amber:** look at the cause in that week's report; no change.
- **Red, process (A1):** pause the EA until the cause is found and fixed; the demo's clock pauses
  with it.
- **Red, edge (B, C or D):** the demo has **failed for real money**: no move to a real account on
  these rules. The EA keeps running on the demo unless Fadi decides otherwise. No rule is changed
  in reaction: any change is a new registration.
- **Review (a strategy, B):** reported each week; a decision about that strategy needs its own
  registration.

Nothing is tightened or loosened after a reading.

## 6. Bookkeeping

Code: `app/research/gold_monitor.py`, called by `python -m app research gold-demo check` (a new
"Health" section of `gold_demo_check.md`; `--export` is needed for A1 and for the reference check
of §2). Committed before it reads the demo. Tests on hand-built trades. This decides no strategy's
rules, so it is not a trial; it is logged in `docs/phase3/TRIALS.md` among the measurements.
