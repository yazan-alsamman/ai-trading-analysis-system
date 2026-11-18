# Gold: the daily trend swing (commercial track)

**Registered 2026-11-08, before any outcome of these rules was computed** (Fadi: "let's try the
swing on the daily frame").

**The idea.** A classic channel breakout on daily bars. Trades are held for days to weeks and
follow gold's long trends. The aim is an edge of its own and a low correlation with the five day
strategies, which close every day by 16:45 New York. v1 and the shadow strategies do not change.

Code: `app/research/gold_swing.py`.

- `python -m app research gold-swing build` runs on XAUUSD.
- `gold-swing fxpro --export <GOLD M1 export>` runs on FxPro's GOLD feed.

Reports: `gold_swing_xauusd.md`, `gold_swing_fxpro.md`.

## 1. Data and costs

- **Bars.** The research D1 bars, one per trading day, 17:00 to 17:00 New York.
  - XAUUSD 2012-2021 to tune, 2022 to 2026-01-09 to check.
  - FxPro `GOLD` from 2016-02 to 2026-11-05.
- **Cost:** the entry day's mean recorded spread + $0.07 per oz, and $0.10 slippage on stop exits.
- **Swap: an estimated scenario.** There is no swap history.
  - Longs pay 3% a year of the price per calendar night held. Shorts pay nothing.
  - Results are given with and without it, and the decision uses the net with swap.

## 2. Rules: SWING

- **Entry.** A daily close above the highest high of the N days before → buy at the next day's
  open. A close below the lowest low of the N days before → sell (when shorts are on).
- **Risk.** The initial SL is 2 × ATR(20, D1) from the entry, with ATR as of the signal day.
  R = that distance.
- **Exit:**
  - the SL intraday (at the SL, or at the open when it gapped through);
  - or a daily close below the lowest low of the M days before (above the highest high for a
    short) → exit at the next day's open.
- **One trade at a time.** An exit and a new entry the same day are both taken, the exit first.

**Settings (4):**

| N / M | Sides |
| --- | --- |
| 20 / 10, 55 / 20 | long and short; long only |

**Choice.** The best mean net R (with swap) on 2012-2021, among settings with net R > 0, at least
60% of the years positive and at least 40 trades. If none qualifies, SWING is dropped.

## 3. Decision

SWING goes to the demo as a shadow only if all of these hold:

1. A setting qualifies on 2012-2021.
2. Net R with swap > 0 on the check, 2022 to 2026-01-09.
3. Net R with swap > 0 on FxPro, 2016-02 to 2026-11-05.
4. **On FxPro, its daily marked-to-market R correlates between −0.2 and +0.2 with the five day
   strategies' daily net R together.**

**Reported beside the decision, and deciding nothing:**

- by year;
- long against short;
- days held;
- the five at demo risk, with and without SWING at 0.5%: the total and the largest drawdown in
  account %.

## 4. Count

There are 4 settings. They are logged in `docs/phase3/TRIALS.md`.

## 5. Outcome (2026-11-08): dropped by the registered rule

`gold_swing_xauusd.md`. **No setting qualifies, so the FxPro run was not done.**

- No setting had 60% of the years positive on 2012-2021. All had 40-50%.
- Two had fewer than 40 trades.

**What it showed, deciding nothing:**

- **Every setting made money, with and without the swap**, on both 2012-2021 and the check.
  - Long only, 20/10: +0.168 R a trade on 2012-2021 (38 trades) and +0.520 on the check (20).
  - Long only, 55/20: +0.166 (20 trades) and +1.40 (8).
- **These are few trades,** 3 to 8 a year, and **mostly gold's long rise.**
  - From 2012 to 2026 gold went from about $1,600 to over $4,000, and the long-only settings did
    best.
  - With so few trades a year, a demo would need years to judge it.
- **The rule was set before the run, and SWING fails it.** It was written for strategies with
  hundreds of trades. Relaxing it now would be choosing after the look. A low-frequency version
  needs a new registration with its own test, and no data is left that is unseen and long enough
  to judge it.
