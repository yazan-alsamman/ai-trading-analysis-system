# Gold lockbox exam: result

_Registration: `GOLD_LOCKBOX_EXAM.md`. Read once: `gold_exam_log.json`. MT5 net R = (profit + commission + fee + swap) / the money risk of the level and SL._

## Tick source

- The last tester run of `gold_exam_trades.csv` (Part = ``), replay `gold_combo_replay.csv`:
- `GOLD : real ticks begin from 2026.01.02 00:00:00`
- **Real ticks for the whole exam**

## Decision (section 4)

| Trades closed | MT5 mean net R (SE) | Pass above | Fail below | Result |
| --- | --- | --- | --- | --- |
| 274 | +0.052 (0.071) | +0.00 | -0.10 | **Pass** |

Statuses: {'closed': 274, 'expired': 15}.

## Reported only

| Set | Trades | MT5 net R | Python net R | Python net with slip |
| --- | --- | --- | --- | --- |
| Combination | 274 | +0.052 | +0.055 | +0.052 |
| LVL4H | 146 | +0.044 | +0.066 | +0.063 |
| PIVOT | 128 | +0.062 | +0.043 | +0.039 |

- Total +14.3 R; the largest drawdown -15.8 R.
- Cost a trade in MT5 (Python gross - MT5 net): 0.013 R; the Python cost model: 0.010 R.
