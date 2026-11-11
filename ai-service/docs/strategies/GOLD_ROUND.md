# Gold: breaks of round numbers (commercial track)

**Registered 2026-11-10, before any outcome of these rules was computed.** Claude's proposal,
chosen by Fadi ("بلش بالأرقام المدورة"): gold breaks real levels more often than it bounces from
them (`FINAL_REPORT.md` §9b), and round prices (4100, 4150, 4200) gather orders and stops. They
are traded with LVL4H's frozen engine, as the shadow level breaks were (`GOLD_SHADOW.md` §3).

Code: `app/research/gold_round.py`, `python -m app research gold-round build` (XAUUSD) and
`gold-round fxpro --export <GOLD M1>` (FxPro's GOLD feed).

## 1. Levels

For a step of $X, from the previous trading day's close C (days 17:00 to 17:00 New York):

- **RU** = the first multiple of X above C, **RD** = the multiple of X at or below C.
- So each day has two levels, the round numbers on either side of where the day starts.

| Setting | Values |
| --- | --- |
| Step X | $10, $25, $50, $100 |

The step is fixed in dollars, because round numbers are round in dollars. A $10 step was a 0.8%
move at $1,200 and is 0.25% at $4,000; the four steps cover that range.

## 2. The trade (LVL4H's frozen settings, `gold_exam`)

- The first touch of each level inside 02:00-16:00 New York, Monday to Friday: a stop entry with
  the break (at market if price is already through).
- D = 0.75 x ATR(14, 4h); SL = entry ∓ D; no target; M8; horizon 200 five-minute bars; exit by
  16:45 New York.
- Cost cap: (spread + $0.07) / D ≤ 0.05. One trade at a time.

## 3. Choice and decision (`GOLD_NIGHT.md` §3)

- **Choice:** the best mean net R on 2012-2021 among steps with net R > 0, at least 60% of the
  years positive and at least 300 trades. None: dropped.
- **Decision:**
  1. A step qualifies on 2012-2021 (XAUUSD).
  2. Net R with slip > 0 on the check, 2022 to 2026-01-09 (XAUUSD).
  3. Net R with slip > 0 on FxPro's GOLD feed, 2016-02 to the export's end.
  4. On FxPro, its daily net R correlates between −0.2 and +0.2 with each of the five demo
     strategies.
- A step that passes runs as a shadow on the demo.
- Reported beside it (decides nothing): trades a day, buys and sells, years.

## 4. Count

4 settings, logged in `docs/phase3/TRIALS.md` as exploratory looks of the commercial track.

## 5. Outcome (2026-11-10): conditions 1-3 met, condition 4 not met; not a shadow

`gold_round_xauusd.md`, `gold_round_fxpro.md` (export `GOLD_M1_201501020000_202611052359.csv`).

| Condition | Result |
| --- | --- |
| 1. A step qualifies on 2012-2021 | $25: +0.040 R (+0.029 with slip), 530 trades, 62% of the years: **met** |
| 2. Check 2022 to 2026-01-09 | +0.043 R with slip, 870 trades: **met** |
| 3. FxPro 2016-02 to 2026-11-05 | +0.039 R with slip, 1,365 trades, 80% of the years: **met** |
| 4. Daily correlation with the five within ±0.2 | +0.30 to +0.42: **not met** |

- **ROUND is another level break, close to the five.** Its days overlap theirs (LVL4H +0.41,
  PIVW +0.42 on FxPro), so by the registered rule it is not added.
- Added to the five on FxPro anyway (decides nothing): the mean goes from +0.026 to +0.028 R, the
  sum from +189 R to +242 R, and the largest drawdown from 129 R to 113 R.
- 2026 on FxPro: −0.009 R with slip over 144 trades.
- **The larger steps did better but had too few trades on 2012-2021.** $50: +0.144 R on 286 trades,
  check +0.167; $100: +0.281 R on 166 trades, check +0.111. They miss the 300-trade bar because
  the cost cap removes most trades before 2019, when ATR(4h) was small. They were not chosen.
- About 0.4 trades a day ($25), not one or two.

**Decision (Fadi, 2026-11-10): the registered rule is kept.** ROUND is not added to the demo.
