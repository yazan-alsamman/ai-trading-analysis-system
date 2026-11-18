# Gold: three continuation candidates from the building-block research (commercial track)

**Registered 2026-11-11, before any outcome of these rules was computed.** From the research report
`reports/تراكيب استراتيجيات تداول جديدة.md` (candidates 1-3); Fadi chose them ("Candidates 1, 2, 3").
The literature points to continuation, not reversion, on gold: one-day trend at moderate strength,
abnormal days, and news days.

Code: `app/research/gold_c123.py`, `python -m app research gold-c123 build --export <GOLD M1>`.

## 1. Common rules

- 5m bars; XAUUSD 2012 to 2026-01-09 (seen data), then FxPro's GOLD feed 2016-02 to 2026-11-05.
- Entry at market at the close of the stated bar. SL = entry ∓ 1.0 x ATR(14, 1h) unless stated.
  No target; exit at the stated time or 16:45 New York. No trailing.
- Cost: the entry bar's spread + $0.07; slip $0.10 on SL exits. A trade is skipped when cost / risk
  > 0.10. Trading days Monday to Friday. One open trade per cell.
- **Cost gate:** no entry from 15 minutes before to 15 minutes after a high-importance USD release
  (the MT5 calendar, `calendar.parquet`), except candidate 3.

## 2. The candidates (two cells each)

**C1, moderate-trend checkpoints.** At 08:00 London and at 09:30 New York (two legs), TS = the log
return since the same checkpoint on the previous trading day, divided by the standard deviation of
that return over the previous 60 trading days. Enter in the sign of TS when **BAND**: 0.5 ≤ |TS| ≤
2.0, or **OPEN**: |TS| ≥ 0.5. The London leg exits at 12:00 London, the New York leg at 16:45 New
York.

**C2, abnormal day into the settle.** At 12:30 New York, z = the log return from the trading day's
first bar (18:00 New York the evening before) to 12:30, divided by its standard deviation over the
previous 60 trading days. If |z| ≥ 1.5, enter in its direction. **A**: exit at 13:35 New York.
**B**: exit at 16:45 New York.

**C3, delayed post-release continuation.** For each release on the list, 15 minutes after it,
move = close at release + 15 minutes − close at release − 1 minute; noise = the mean |move| over
the same clock window on the previous 20 trading days. If |move| ≥ 1.0 x noise, enter in its
direction. SL beyond the opposite extreme of the post-release range (the low since the release for
a buy) − 0.1 x ATR(14, 5m). Exit at 16:45 New York (the Fed decision: at 16:45 or 3 hours,
whichever is first). **TOP3**: NFP, CPI m/m, the Fed decision. **TOP5**: also Core PCE m/m and
GDP q/q (every estimate). Disclosed: C3 uses the news family of discovery round 2 (F3) on gold; its
markout map must count this look.

## 3. Choice and decision (per candidate)

- **Choice:** the cell with the best mean net R with slip on 2012-2021 among cells with net > 0,
  at least 60% of the years positive and at least 300 trades (C3: at least 100, its events are
  few). None: dropped.
- **Conditions:** 1. a cell qualifies; 2. net R with slip > 0 on the check, 2022 to 2026-01-09;
  3. net R with slip > 0 on FxPro, 2016-02 to 2026-11-05; 4. daily net R correlation with each of
  the five demo strategies < +0.2.
- **The extra bar from the research (reported, and needed before any money):** after about 60 looks
  on gold, the best of many backtests shows about +0.17 R a trade by chance (deflated Sharpe
  multiplier 2.35 at N = 60). So a candidate that passes conditions 1-4 goes next to a registered
  test on markets never touched (not to the demo), and its t-statistic is reported here.

## 4. Count

6 cells, logged in `docs/phase3/TRIALS.md` (N for the deflated Sharpe grows to about 66 looks).

## 5. Outcome (2026-11-11): C1 and C3 pass conditions 1-4 with edges too small to confirm; C2 dropped

`gold_c123_result.md`.

| Candidate | Chosen cell | 2012-2021 (with slip) | Check 2022 to 2026-01-09 | FxPro 2016-2026 | Trades a day |
| --- | --- | --- | --- | --- | --- |
| C1 | OPEN | +0.039 (1,013 trades, 70% of years) | +0.016 (t +0.37, 1,074) | +0.010 (t +0.35, 1,987) | 0.58 |
| C2 | none: 176-177 trades, under 300 | A +0.027, B +0.041 | B +0.075 (150) | | 0.09 |
| C3 | TOP3 | +0.056 (179, 60%) | +0.030 (t +0.22, 99) | +0.016 (t +0.19, 229) | 0.08 |

- Condition 4: C1's daily correlation with LVL4H is +0.1994, just under +0.2 (the others +0.11 to
  +0.19); C3's +0.03 to +0.12.
- **By the research's own bar they are noise-sized.** Their t-statistics on the check and on FxPro
  are 0.2-0.4. After about 66 looks on gold, the best of many backtests shows about +0.17 R by
  chance; these are +0.01 to +0.03 R. Confirming +0.02 R at t = 3 would take about 20,000 unseen
  trades, more than any holdout we have.
- **Recommendation (Claude), for Fadi to decide:** the registered next step (a test on untouched
  markets) is not worth its data for C1 and C3 as they stand; record them as passed but
  unconfirmable, like ROUND.
- C2-B (abnormal day held to 16:45) made +0.075 on the check, but on 150 trades and with 50% of
  the years positive on 2012-2021; it is not chosen.
