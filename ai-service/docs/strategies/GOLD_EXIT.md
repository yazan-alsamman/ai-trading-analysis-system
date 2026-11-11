# Gold: a fixed target and an early lock for the five level breaks (commercial track)

**Registered 2026-11-10, before any outcome of these exits was computed.** Fadi's idea (chat,
2026-11-10): the five demo strategies' trades usually move in their direction first but not far,
so instead of a far SL with no target, use an SL and a TP of the same size that grows with the
market's movement (about $5 in quiet years, $10, then $20 in the last year and a half), move the
SL to the entry (or a quarter of the target) at half the target, then trail.

Code: `app/research/gold_exit.py`, `python -m app research gold-exit build`. XAUUSD 5m bars, 2012
to 2026-01-09 (seen data). Only the exit changes: the entries are the five strategies' own
(`gold_combo.levels`, the exam's settings, `GOLD_SHADOW.md`), the same trades in the same order.

## 1. Descriptive, measured before this registration (decides nothing)

On the five strategies' trades, how far price went in the trade's direction before the current SL
(D) was hit or the day ended:

| Reached before the SL | 2012-2021 (4,369) | 2022-2025 (4,688) | Random walk 1 / (1 + x) |
| --- | --- | --- | --- |
| +0.25 D | 78.4% | 79.6% | 80.0% |
| +0.5 D | 66.2% | 66.8% | 66.7% |
| +1 D | 46.7% | 47.9% | 50.0% |
| +2 D | 24.0% | 23.3% | 33.3% |
| +3 D | 13.0% | 10.5% | 25.0% |

Fadi's observation is right, and it is what a random walk does: four trades in five go +0.25 D
first. Far targets are hit less often than a random walk's because the day ends first.

## 2. The exits

The size S = **k x ATR(14, D1)**, the last daily bar closed at the entry. With k = 0.4 it gives
about $5 in 2017-2019, $10 in 2020-2023 and $20 in 2025 (median ATR(D1) 12-13, 24-29, 52).

- **SL** = entry ∓ S, **TP** = entry ± S.
- **Lock.** When the high (a buy) reaches entry + S/2 on a closed 5m bar, the SL moves to:
  - **BE:** entry + cost (cost = the entry bar's spread + $0.07), or
  - **Q:** entry + S/4.
- **Trail (a setting).** After the lock, the SL follows M8's trail: the last confirmed 5m swing
  ∓ 0.1 x ATR(14, 5m), when better and price is beyond it. Without it the SL stays at the lock.
- **Exit:** SL (at the open when a bar gaps through), TP, or the strategy's own end (its horizon or
  16:45 New York). A bar that reaches the SL and the TP counts as the SL. As the current engine,
  the fill bar itself is not checked.
- One trade at a time per strategy, as now.

R is the new S: gross R = move / S; cost R = cost / S; slip adds $0.10 on SL exits.

| Setting | Values |
| --- | --- |
| k | 0.3, 0.4, 0.5 |
| Lock | BE, Q |
| Trail | yes, no |

12 settings, the same for all five strategies. **Baseline:** the current exits (SL D, no TP, M8).

## 3. Choice and decision

- **Choice:** the setting with the best mean net R with slip of the five together on 2012-2021.
- **Adopt** (as a shadow exit on the demo, beside the current one) only if on the check, 2022 to
  2026-01-09, the chosen setting's mean net R with slip of the five together is **> 0 and above
  the baseline's**. Each trade risks the same share of the account in both, so the mean R
  compares them.
- Reported beside it: each strategy, years, the exit mix, and the largest drawdown in R.

## 4. Count

12 settings, logged in `docs/phase3/TRIALS.md` as exploratory looks of the commercial track.

## 5. Outcome (2026-11-10): not adopted

`gold_exit_xauusd.md`. Chosen on 2012-2021: k 0.5, lock BE, no trail, the best of the 12 but
−0.011 R a trade (50% of the years positive). On the check it makes +0.035 R a trade with slip,
**below the baseline's +0.062**, so §3 fails and the current exits stay.

| Five together, net R with slip | 2012-2021 | Check 2022 to 2026-01-09 |
| --- | --- | --- |
| Baseline (SL D, no TP, M8) | +0.034 (sum +139 R, drawdown 67 R) | +0.062 (+259 R, 64 R) |
| Chosen (SL = TP = 0.5 x ATR(D1), BE at half) | −0.011 (−42 R, 73 R) | +0.035 (+139 R, 34 R) |

- **The target cuts the gross R by more than half** (+0.137 to +0.022 on 2012-2021, +0.099 to
  +0.049 on the check), in every strategy and every setting. The breaks' edge is in the few trades
  that run far: with no target, 84-86% of the baseline's trades end at their (often trailed) SL,
  and the rest of the gain comes from the long runs a 1:1 target gives away.
- **The lock at half the target does not help either.** Every BE / Q setting is below the
  baseline on 2012-2021, and the trail after the lock changes ±0.01 R.
- **The drawdown in R is smaller** on the check (34 R against 64 R), and the sum over the
  drawdown is about the same (4.2 against 4.1). On 2012-2021 the chosen exit loses. So the fixed
  target is a smaller, not a better, version of the same trades.
