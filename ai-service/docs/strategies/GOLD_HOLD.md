# Gold: let the five's winners run past 16:45 (commercial track)

**Registered 2026-11-10, before any outcome of this test was computed.** Claude's proposal after
`gold_path.md`, accepted by Fadi ("yes"): the trades still open at 16:45 New York are the
winners (+0.29 to +0.62 R gross on average), the best 10% of trades make all the gain, and far
targets are reached less often than a random walk's because the day ends first. So the 16:45 exit
may cut the very trades that pay. This is the last management test (`GOLD_EXIT.md`,
`GOLD_SL.md`, Stage D's M0-M8).

Code: `app/research/gold_hold.py`, `python -m app research gold-hold build --export <GOLD M1>`.

## 1. The exits

The five strategies' own entries and D, M8 throughout (break-even at +1 D, then the 5m swing trail).

| Setting | End of the trade |
| --- | --- |
| BASE | as now: the strategy's horizon or 16:45 New York, whichever is first |
| ALL1 | every trade: no horizon, the next trading day's 16:45 |
| WIN1 | at BASE's end, a trade whose SL is already at break-even or better goes on to the next trading day's 16:45 (no horizon); the others close as BASE |
| WIN3 | as WIN1, up to the 16:45 of the third trading day |

- A bar that gaps through the SL fills at its open (the weekend included).
- **Swap (a scenario; FxPro's real rates are not recorded):** each night held (a 17:00 New York
  rollover) costs 3% a year of the price for a buy and 1% for a sell, / 360, three nights on the
  Wednesday rollover. Reported in R on each trade's D.
- Cost and slip as before (the entry bar's spread + $0.07; $0.10 on SL exits).

## 2. Choice and decision

- **Choice:** the extended setting (ALL1, WIN1, WIN3) with the best mean net R with slip and swap of
  the five together on XAUUSD 2012-2021.
- **Adopt** (a v1 change: a shadow version first) only if it beats BASE on XAUUSD 2012-2021, on the
  check (2022 to 2026-01-09) and on FxPro's GOLD feed (2016-02 to the export's end).
- Reported beside it: each strategy, the largest drawdown in R, the share of trades held overnight,
  swap in R, and FxPro 2026.

## 3. Count

3 settings beside BASE, logged in `docs/phase3/TRIALS.md` as exploratory looks of the commercial
track.

## 4. Outcome (2026-11-10): not adopted; the management question is closed

`gold_hold_xauusd.md`. Chosen on 2012-2021: ALL1 (+0.034 against BASE's +0.026), but on the
check +0.053 against +0.062 and on FxPro −0.019 against +0.021, so §2 fails.

- **Holding every trade overnight (ALL1) is the worst on FxPro**: −0.019 R a trade and a largest
  drawdown of 440 R against 157 R. The night and the week's open are where the breaks give back.
- **Holding only the winners (WIN1, WIN3) changes almost nothing.** Only 1-2% of the trades are
  at break-even or better at their 16:45 end: M8's trail has already closed most winners by then.
  WIN1 and WIN3 are the same trades (none of them lasts past the next day), and both are 0.001 to
  0.005 R below BASE everywhere.
- **The 16:45 exit is not cutting the winners.** The trades that end "at time" are mostly trades
  still under their first SL, not trailed winners.
- BASE here fills SL exits at the open when a bar gaps through (as registered); the earlier
  reports filled them at the SL. That alone lowers BASE by about 0.008 R a trade on 2012-2021.

With `GOLD_EXIT.md`, `GOLD_SL.md` and Stage D's M0-M8, this closes the management question: no
tested exit beats the current M8 with a 16:45 close in every period.
