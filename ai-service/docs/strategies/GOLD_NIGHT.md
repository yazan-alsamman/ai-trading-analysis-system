# Gold night reversion inside the Asian range (commercial track)

**Registered 2026-11-07, before any outcome of these rules was computed** (Fadi: the Asian range
reversion, "a period we do not trade at all"). v1 and the shadow strategies do not change. The
aim is a strategy with an edge of its own and almost no correlation with the day strategies
(LVL4H, PIVOT, PIVW, ASIA, PWHL), which all trade breaks between 02:00 and 16:45 New York.

Code: `app/research/gold_night.py`.

- `python -m app research gold-night build` tunes and checks on XAUUSD.
- `gold-night fxpro --export <GOLD M1 export>` runs the same on FxPro's GOLD feed.

Reports: `gold_night_xauusd.md`, `gold_night_fxpro.md`.

## 1. Data and costs

These are as `GOLD_SHADOW.md` §1:

- XAUUSD 2012-2021 to tune, 2022 to 2026-01-09 to check.
- FxPro `GOLD` from 2016-02 to 2026-11-05.
- Cost: the signal bar's recorded spread + $0.07 per oz. Night spreads are wider, and the cost
  uses the recorded spread of that bar.
- $0.10 slippage on stop exits, reported beside the net.

## 2. Rules: NIGHT

All times are New York. The night of a trading day runs from 19:00 to 02:00. Its 5m bars belong
to the next day's D1 bar, which opens at 17:00.

- **The box.** The high (H) and low (L) of the night's bars from 19:00 to B.
  - The box needs at least 80% of its bars.
  - W = H − L, and M = (H + L) / 2.
- **The window.** Entries from B to 01:55. Every trade closes at the latest at the close of the
  01:55 bar (02:00), before London and before the day strategies' window.
- **Entry, two kinds** (a setting):
  - **touch.** The first bar of the night that reaches an edge from inside it.
    - At the upper edge: a sell at H, or at the bar's open when it opened above H.
    - The SL is H + s × W, and the target is M or L (a setting).
    - Buys are the mirror image at L.
    - Conservative fill: if the touch bar itself reaches the SL, the trade is a full loss, and a
      target on the touch bar is not counted.
  - **reclaim.** The first bar of the night that trades beyond an edge and closes back inside.
    - The entry is at its close.
    - The SL is beyond that bar's extreme by 0.1 × ATR(14, 5m).
    - The target is M or the other edge.
- **Rules for every trade:**
  - Each edge trades at most once a night, and one trade is open at a time.
  - A trade needs a target beyond the entry.
  - Cost cap: (spread + $0.07) / risk ≤ 0.10, else no trade.
  - A fixed SL and target, with no trail. Exit at the SL, the target, or 02:00.

**Grid (12 settings), tuned on 2012-2021:**

| Setting | Values |
| --- | --- |
| B, the box end | 20:00, 21:00 |
| Entry | touch (s = 0.5 or 1.0 × W), reclaim |
| Target | M (the middle), the other edge |

That is 2 × (2 + 1) × 2 = 12 settings.

**Choice:** the best mean net R on 2012-2021, among settings with at least 60% of the years
positive and at least 300 trades. If none qualifies, NIGHT is dropped.

## 3. Decision

NIGHT goes to the demo as a shadow strategy only if all of these hold:

1. A setting qualifies on 2012-2021 (§2).
2. Net R with slippage > 0 on the check, 2022 to 2026-01-09.
3. Net R with slippage > 0 on FxPro `GOLD`, 2016-02 to 2026-11-05.
4. On FxPro, the correlation of its net R per trading day with each of LVL4H, PIVOT, PIVW, ASIA
   and PWHL is between −0.2 and +0.2. Days without a trade count as 0.

Reported beside the decision, and deciding nothing:

- results by year, and buys against sells;
- the cost as a share of R;
- FxPro 2026-01-12 on, which no choice used;
- the six strategies together against the five: mean net R and the largest drawdown in R.

## 4. Count

There are 12 settings. They are logged in `docs/phase3/TRIALS.md`, as exploratory looks of the
commercial track.

## 5. Outcome (2026-11-07): dropped

`gold_night_xauusd.md`. **No setting qualifies on 2012-2021, so NIGHT is dropped at condition 1.**
The FxPro run and the correlations were not needed.

- **Fading a touch of the box edge loses, in every setting.**
  - On 2012-2021: −0.04 to −0.23 R a trade.
  - On the check: −0.05 to −0.12 R. The 1 × W versions lost −0.07 to −0.10 there with standard
    errors of 0.02-0.03, so this is not noise.
- **The reclaim entry is about zero.**
  - It is the only setting family with some positive results: +0.011 on 2012-2021, but with 156
    trades (fewer than 300). The others were 130-163.
  - The cost cap of 0.10 R leaves few trades: night spreads are wide against the stops.
- **The box's edges at night break more often than they turn.** That agrees with the level test
  (trial 27: at real levels, price goes through more often than it bounces) and with ASIA's
  break working by day.
