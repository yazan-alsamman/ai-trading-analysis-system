# Gold combination: the lockbox exam (commercial track)

**Status: REGISTERED, approved by Fadi on 2026-11-05 as written, before any line of the lockbox
was read. The XAUUSD lockbox file is read once.**

| Field | Value |
| --- | --- |
| Approved by | Fadi |
| Approval date | 2026-11-05 |
| Rules frozen at | `152c53c` (the exam reader is added in its own commit before the run) |

## 1. What is tested

The gold combination of `gold_combo.md`, as replayed in `gold_combo_mt5.md`, with nothing
changed:

- **LVL4H**: prior-day levels, stop entry at the level, distance 0.75 × ATR(4h), entries 02:00 to
  16:00 New York, cost cap 0.05 R, horizon 200 five-minute bars.
- **PIVOT**: pivot levels, distance ATR(1h), entries 02:00 to 16:00 New York, horizon 48 bars.
- **Management M8**: SL to entry + cost after +1 R, then the trailing SL at the last confirmed
  5-minute swing (k = 2) − 0.1 × ATR(5m); no TP; out at 16:45 New York the same day at the latest.
- One open trade per strategy. **No AI filter** (`UseAI = false`).

Fadi chose the combination over LVL4H alone on 2026-11-05, after seeing the 2015 to 2026-01 MT5
replay. That choice is disclosed here.

## 2. Data

- **Only `XAUUSD_M1_202601120101_202610202356.csv`** of the sealed lockbox
  (`docs/lockbox/MANIFEST-2026-10-21.json`). Its SHA-256 is checked against the manifest before
  any line is decoded.
- **The other five files stay sealed.**
- Period of the exam: trades placed from 2026-01-12 to 2026-10-20 (about 9.3 months, about 280
  trades at the past rate).
- Warm-up (ATR, prior-day and pivot levels) comes from the store before 2026-01-10. No parameter is
  fitted on the lockbox.

## 3. Procedure (once)

1. `python -m app lockbox verify` on the manifest.
2. `python -m app research gold-combo exam --open-lockbox`:
   - reads the XAUUSD lockbox file;
   - builds the trades with the frozen code;
   - writes the trade file for MT5 and the Python result.
   - It logs the commit, the file hash and the time to `docs/strategies/gold_exam_log.json`, and
     refuses to run again once that log exists.
3. **MT5 Strategy Tester:**
   - GOLD, M5, "Every tick based on real ticks", from 2026-01-12 to 2026-10-21;
   - `UseAI = false`, `Part = exam`.
4. **The run counts only on real ticks.** The tester log must not say "no real ticks", "every
   tick generation used" or "real ticks begin from" a date after 2026-01-12. The server holds real
   GOLD ticks from 2026-01-02, so this should hold. If it fails, the run is repeated, never
   replaced by generated ticks.
5. `python -m app research gold-combo compare` on the exam file, written to
   `docs/strategies/gold_exam.md`.

## 4. Decision

**Measure:** the MT5 mean net R per trade of the combination over the exam period, on real ticks.
Net R = (profit + commission + swap) / the money risk of the level and SL.

| Result | Mean net R | What follows |
| --- | --- | --- |
| **Pass** | > 0 | Demo account, same rules, forward |
| **Not confirmed** | −0.10 to 0 | No real money; the demo may run as an observation only |
| **Fail** | < −0.10 | The combination is stopped |

−0.10 is about the 5th percentile of past 9-month windows (section 6): below it, the result does
not fit the backtest.

**Not part of the decision, reported only:**

- LVL4H alone and PIVOT alone.
- The AI filter's kept trades.
- Python net and net with slippage against MT5 on the same trades.
- The cost a trade on real ticks against the generated ticks of the backtest.
- The largest drawdown in R.

## 5. After a pass

- A demo account on FxPro with the same EA logic, forward, for at least 3 months or 100 trades.
- Risk per trade 0.5% to 1% of the account (fixed fractional), not a fixed lot.
- Live money only after the demo agrees with the exam.

## 6. What the past says (read before the exam)

The MT5 replay of 2016 to 2026-01 (`gold_combo_mt5.md`), split into windows of 282 days, the
length of the exam, starting every month:

| Set | Windows | Trades in a window (median) | 5th percentile | Median | Windows below 0 |
| --- | --- | --- | --- | --- | --- |
| Combination, 2016 on | 112 | 286 | −0.107 | +0.036 | 31% |
| Combination, 2020 on | 64 | 328 | −0.048 | +0.081 | 19% |
| LVL4H alone, 2016 on | 77 | 169 | +0.036 | +0.114 | 0% |

- **Even if the edge is real, the combination may fail this exam:** about one window in five
  since 2020 was negative.
- The standard deviation of one trade is about 1.35 R. So the standard error of the exam mean is
  about 0.08 R, about the size of the edge itself.
- A pass does not prove the edge; it only fails to refute it. The demo is the next check.

## 7. Disclosures

- **LVL4H was tuned on 2012 to 2021.** 2022 to 2026-01 was seen many times during development, on
  the commercial track, as Fadi decided on 2026-11-04.
- **The backtest never ran on real ticks.** Every MT5 run used ticks generated from M1 bars,
  because the FxPro server keeps real ticks only from about 2026-01. The exam is the first run on
  real ticks.
- **Opening the XAUUSD lockbox ends its use as unseen data for any later gold research.** The
  thesis (P9) must say that it was opened here, for this exam.
