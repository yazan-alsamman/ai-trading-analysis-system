# Gold: the New York opening range breakout (commercial track)

**Registered 2026-11-07, before any outcome of these rules was computed** (Fadi: "go").

**The idea.** ASIA's level break worked. So: the same engine on the range of the COMEX open and the
08:30 US data, a time when the day strategies mostly do not enter, for a lower correlation. One
fixed setting, no tuning. v1 and the shadow strategies do not change.

Code: `app/research/gold_orb.py`.

- `python -m app research gold-orb build` runs on XAUUSD.
- `gold-orb fxpro --export <GOLD M1 export>` runs on FxPro's GOLD feed.

Reports: `gold_orb_xauusd.md`, `gold_orb_fxpro.md`.

## 1. Data and costs

These are as `GOLD_SHADOW.md` §1:

- XAUUSD 2012-2021, and 2022 to 2026-01-09 as the check.
- FxPro `GOLD` from 2016-02 to 2026-11-05.
- Cost: the signal bar's recorded spread + $0.07 per oz.
- $0.10 slippage on stop exits, reported beside the net.

## 2. Rules: ORB

All times are New York, Monday to Friday.

- **The range.** The high (ORH) and low (ORL) of the 5m bars from 08:20 to 08:50: the six bars
  opening 08:20 to 08:45. At least five of them must exist.
- **The entry.** From 08:50 to 16:00, the first touch of the day of ORH (a buy) or ORL (a sell).
  It is a stop entry with the break, at the level, or at the bar's open when it gapped through.
- **Everything else is LVL4H's frozen engine and settings** (`GOLD_V1.md`, `gold_combo.levels`):
  - D = 0.75 × ATR(14, 4h), with the SL at D;
  - cost cap (spread + $0.07) / D ≤ 0.05;
  - M8, with no target;
  - exit at 16:45 or after 200 bars;
  - one trade at a time.

## 3. Decision

These are the conditions of `GOLD_NIGHT.md` §3. ORB goes to the demo as a shadow only if all of
them hold:

1. Net R > 0 on 2012-2021, with at least 60% of the years positive.
2. Net R with slippage > 0 on the check, 2022 to 2026-01-09.
3. Net R with slippage > 0 on FxPro, 2016-02 to 2026-11-05.
4. On FxPro, its daily net R correlates between −0.2 and +0.2 with each of LVL4H, PIVOT, PIVW,
   ASIA and PWHL.

**Reported beside the decision, and deciding nothing:**

- results by year and by side;
- FxPro 2026-01-12 on;
- the five day strategies with and without ORB: mean, sum and the largest drawdown.

## 4. Count

There is 1 setting. It is logged in `docs/phase3/TRIALS.md`, as an exploratory look of the
commercial track.

## 5. Outcome (2026-11-07): dropped

`gold_orb_xauusd.md`, `gold_orb_fxpro.md`. **ORB loses everywhere.** Conditions 1-4 all fail.

| Period | Trades | Net R with slippage |
| --- | --- | --- |
| XAUUSD 2012-2021 (50% of the years positive) | 726 | −0.031 |
| XAUUSD check, 2022 to 2026-01-09 | 1,112 | −0.025 |
| FxPro 2016-02 to 2026-11-05 | 1,812 | −0.055 |
| FxPro 2026-01-12 on | 226 | −0.184 |

- Its daily correlation with the five is +0.11 to +0.25 (XAUUSD) and +0.14 to +0.20 (FxPro).
- With ORB, the five's mean falls and their largest drawdown grows: 67 to 82 R on XAUUSD, 129 to
  177 R on FxPro.
- **The break of the morning range is not the break of the night range.**
  - ASIA's range is built in a quiet session and breaks when London's volume comes in.
  - The 08:20-08:50 range already holds the 08:30 data move. Its break later in the day has no
    edge.
