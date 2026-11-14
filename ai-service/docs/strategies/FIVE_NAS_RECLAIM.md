# RECLAIM, the fade at the five's levels, on the Nasdaq 100

**Registered 2026-11-11, before any outcome of this rule on the Nasdaq was computed.** Fadi's idea
(chat, 2026-11-11): after the five's breaks failed on the Nasdaq (`FIVE_NAS100.md`: −0.078 R, below
a random side), try the strongest bounce rule we have at the same levels.

**Disclosed:** the rule was chosen *after* seeing that the breaks lose on this instrument (and
that they lost in 2016-2021 and won a little in 2022-2024). The Nasdaq is no longer unseen for a
fade at these levels. So the decision needs both halves, not the whole.

Code: `app/research/five_nas.py`, `python -m app research five-nas reclaim --export <M1 export>`.

## 1. The rule: RECLAIM, frozen as on gold (`gold_regime.reclaim`, `TRIALS.md` 2026-11-08)

- The five's level sets (LVL4H's day and 5-day levels, the pivots R1 / S1, the Asian range, the
  previous week), each level's first break of the day inside 02:00-16:00 New York.
- The first M5 close back inside the level within 6 bars: a trade **against** the break, at that
  close. SL beyond the break's extreme + 0.1 x ATR(14, 5m). **TP 1.5 R.** Exit at 16:45 New York.
  Cost cap (spread + commission) / R ≤ 0.10. One trade at a time per level set.
- On gold (FxPro 2016-2026) it made −0.07 R a trade; MIRROR (the plain opposite trade) −0.10.

The Nasdaq's costs as `FIVE_NAS100.md`: commission 3.0 points a round trip, SL slip 0.5 point.

## 2. Decision

RECLAIM on the Nasdaq **holds** only if all three are met:

1. Mean net R with slip > 0 on **2016-02 to 2021**.
2. Mean net R with slip > 0 on **2022 to 2026-11-09**.
3. Over the whole period, above the 95th percentile of E0: the same entries, SL distance and
   target with the side drawn by a fair coin (50 runs, seed 20261112).

Reported beside it: each level set, years, the drawdown in R. A rule that holds is a candidate for
its own forward demo; nothing changes on the gold demo.

## 3. Count

One run (5 level sets, one setting), logged in `docs/phase3/TRIALS.md`.

**Correction (2026-11-11, after the first run):** PIVW's levels are PIVOT's (R1, S1); PIVW differs
only in D, which RECLAIM does not use, so the first run counted the same 176 trades twice
(`five_nas_reclaim_result_first_run.md`: PIVOT and PIVW both +0.213 on 176). The level sets are
four, not five: PIVW is dropped from RECLAIM, the rule is otherwise unchanged, and the decision is
read on the rerun (`five_nas_reclaim_result.md`).

## 4. Outcome (2026-11-11): does not hold

`five_nas_reclaim_result.md` (the rerun without the duplicate).

| Set | Trades | Net R with slip | Years + |
| --- | --- | --- | --- |
| RECLAIM, all | 753 | −0.012 | 60% |
| 2016-2021 | 108 | +0.108 | 80% |
| 2022 to 2026-11-09 | 645 | **−0.033** | 40% |

Condition 2 fails. E0 (random side): mean −0.088, 95th −0.020; RECLAIM is above E0's 95th, so
its side carries some information, but not enough to pay its cost (0.067 R) after 2021.

- By level set: **PIVOT's levels +0.213 R on 176 trades, positive in every year**; LVL4H −0.050,
  ASIA −0.087, PWHL −0.146. The PIVOT subset is a finding *after* the fact on this data: it is not
  a result, only a candidate for its own registered test on another unseen index (US500 or US30).
- 2025-2026, the bulk of the trades (464), lost −0.04 to −0.05 R a trade.
- The first run's "holds" came only from counting PIVOT's trades twice.
- Note for gold: `gold_regime.reclaim` built RECLAIM from the same five level sets, so the gold
  figure in `TRIALS.md` (2026-11-08) may count PIVOT's trades twice as well; it was exploratory and
  decided nothing.

**Decision (Fadi, 2026-11-11): stop here.** The PIVOT-level subset is not taken to another index;
it stays an unconfirmed observation.
