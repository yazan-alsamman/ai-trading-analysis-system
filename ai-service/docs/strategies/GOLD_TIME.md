# Gold: three time-of-day strategies (commercial track)

**Registered 2026-11-10, before any outcome of these rules was computed.** Claude's proposals,
chosen by Fadi ("روح A B C وجربهم كلهم وجربهم بأكتر من طريقة"): daily intraday strategies that
enter at fixed times, not at levels, so they differ from the five demo strategies by
construction. About one trade a day each.

Code: `app/research/gold_time.py`, `python -m app research gold-time build` (XAUUSD) and
`gold-time fxpro --export <GOLD M1>` (FxPro's GOLD feed).

**Changed condition 4 (Fadi, 2026-11-10, before this run):** a strategy's daily net R must
correlate **below +0.2** with each of the five; a negative correlation is accepted (it lowers the
portfolio's drawdown). It was "between −0.2 and +0.2" (`GOLD_NIGHT.md` §3).

## 1. Common rules

- 5m bars, New York time. A trading day runs 17:00 to 17:00 New York. "At HH:MM" means the close
  of the 5m bar that ends at HH:MM.
- Entry at market at that close. **D = 0.75 x ATR(14, 4h)**, SL = entry ∓ D, no target.
- **Management (a setting):** **M8** (`GOLD_V1.md`) or **TIME** (the SL only, exit at the end time).
- Cost cap (spread + $0.07) / D ≤ 0.05 at the entry bar; cost = that spread + $0.07; with slip
  adds $0.10 on SL exits. One trade at a time per strategy. Entries Monday to Friday trading days.

## 2. A: intraday momentum (after Gao, Han, Li and Zhou, 2018)

- **Signal:** the sign of gold's move over a morning window; the trade goes the same way.
  - **S1:** from the trading day's first bar open (18:00) to 10:00.
  - **S2:** from 16:00 of the previous trading day to 10:00 (the overnight and the first half
    hour of New York, as the paper).
- **Entry time:** 10:00, 14:30 or 15:30. **Exit:** 16:45 New York.
- Settings: 2 signals x 3 entries x 2 managements = **12**.

## 3. B: London to New York

- **Signal:** the sign of gold's move from 02:00 to 08:00.
- **Mode:** **CONT** trades with it, **REV** against it.
- **Entry:** 08:30. **Exit:** 12:00 or 16:45.
- Settings: 2 modes x 2 exits x 2 managements = **8**.

## 4. C: the night

- **Direction:** **LONG** or **SHORT**, fixed.
- **Entry:** 18:30 or 20:00. **Exit:** 02:00 (before London).
- Settings: 2 directions x 2 entries x 2 managements = **8**.

## 5. Choice and decision (per strategy A, B, C)

- **Choice:** the best mean net R on 2012-2021 among settings with net R > 0, at least 60% of the
  years positive and at least 300 trades. None: dropped.
- **Decision:**
  1. A setting qualifies on 2012-2021 (XAUUSD).
  2. Net R with slip > 0 on the check, 2022 to 2026-01-09 (XAUUSD).
  3. Net R with slip > 0 on FxPro's GOLD feed, 2016-02 to the export's end.
  4. On FxPro, its daily net R correlation with each of the five demo strategies **< +0.2**.
- A strategy that passes runs as a shadow on the demo. Reported beside it: trades a day, buys and
  sells, years, and the five's portfolio with and without it.

## 6. Count

28 settings, logged in `docs/phase3/TRIALS.md` as exploratory looks of the commercial track.

## 7. Outcome (2026-11-10): all three dropped

`gold_time_xauusd.md`. The FxPro run was not needed.

| Strategy | Chosen on 2012-2021 | 2012-2021, net with slip | Check, net with slip | Decision |
| --- | --- | --- | --- | --- |
| A, intraday momentum | S1 / 15:30 / TIME | +0.009 (595 trades, 75% of years) | −0.011 (998) | dropped at condition 2 |
| B, London to New York | CONT / 16:45 / TIME | +0.043 (624, 62%) | −0.007 (1,020) | dropped at condition 2 |
| C, the night | none qualifies | best LONG / 18:30 / M8 −0.003 | | dropped at condition 1 |

- **A.** Gold has no intraday momentum here: every setting is within about ±0.07 R of 0, and the
  sign flips between the two periods. The 10:00 entries made +0.04 to +0.07 R on the check after
  −0.02 to −0.06 on 2012-2021. Its daily correlation with the five is about +0.07: it is
  different from them, but it has no edge.
- **B.** London's direction does not carry into New York reliably: CONT made money on 2012-2021,
  REV on the check, both within one standard error of 0. CONT also correlates +0.27 to +0.41 with
  the five (a London move is often a level break).
- **C.** No direction of the night pays: long about 0, short −0.06 to −0.08 R a trade (gold rose
  over the period, so short loses its drift).
- About 0.4 trades a day each: the cost cap removes most entries before 2019 and the entries that
  fall on a holiday or a short session.
