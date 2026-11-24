# Gold: the previous day's value area, VAH and VAL (commercial track)

**Registered 2026-11-08, before any outcome of these rules was computed** (Fadi: "make a strategy
on the volume profile, especially VAH and VAL, and test it").

**The idea.** The previous day's value area holds 70% of its volume. Its edges, VAH and VAL, are
levels many traders watch. They are traded with LVL4H's engine, as PIVW, ASIA and PWHL were
(`GOLD_SHADOW.md`). One fixed setting, no tuning. v1 and the shadow strategies do not change.

Code: `app/research/gold_vp.py`.

- `python -m app research gold-vp build` runs on XAUUSD.
- `gold-vp fxpro --export <GOLD M1 export>` runs on FxPro's GOLD feed.

Reports: `gold_vp_xauusd.md`, `gold_vp_fxpro.md`.

## 1. The volume profile

There is no real volume on spot gold, so the profile uses each 5m bar's **tick volume** (the count
of price changes). It is a common proxy and close to real volume on the hour and the day, but it
is an approximation.

- **The bins.** For each trading day (17:00 to 17:00 New York), the day's range from low to high
  is cut into 100 equal bins.
- **The volume.** Each 5m bar spreads its tick volume evenly over the bins its range touches.
- **POC** is the bin with the most volume.
- **The value area** grows from the POC one bin at a time. At each step it takes the side, above
  or below, with more volume, until it holds at least 70% of the day's volume.
- **VAH** is the top of the value area and **VAL** is its bottom.
- Today's levels are the previous trading day's VAH and VAL.

## 2. Rules: VPVA

- LVL4H's frozen engine and settings, at VAH and VAL.
- The first touch of the day of each level, 02:00 to 16:00 New York, is a stop entry with the
  break.
- D = 0.75 × ATR(14, 4h), with the cost cap at 0.05.
- M8 management, with no target.
- Exit at 16:45 or after 200 bars. One trade at a time.

## 3. Data, costs, decision

Data and costs are as `GOLD_SHADOW.md` §1. **The decision is §4 there.** VPVA runs as a shadow on
the demo only if all of these hold:

1. Net R > 0 on 2012-2021, with at least 60% of the years positive.
2. Net R with slippage > 0 on the check, 2022 to 2026-01-09.
3. Net R with slippage > 0 on FxPro, 2016-02 to 2026-11-05.

**Reported beside the decision, and deciding nothing:**

- results by year and by side;
- FxPro 2026-01-12 on;
- the daily correlation with the five;
- the five at demo risk with and without VPVA at 0.25%: the total and the largest drawdown.

## 4. Count

There is 1 setting. It is logged in `docs/phase3/TRIALS.md`.

## 5. Outcome (2026-11-08): dropped

`gold_vp_xauusd.md`, `gold_vp_fxpro.md`.

| Condition | Result |
| --- | --- |
| 1. 2012-2021 | +0.021 R a trade (+0.008 with slippage), 592 trades, 75% of the years positive: met |
| 2. Check, 2022 to 2026-01-09 | −0.017 with slippage, 906 trades: **not met** |
| 3. FxPro, 2016-02 to 2026-11-05 | −0.031 with slippage, 1,451 trades: **not met** |

- In 2026 it made −0.089, over 163 trades.
- **The value area's edges break like the other levels, without their edge.**
  - Its daily correlation with the five is +0.41 to +0.42.
  - On FxPro it lowers their total (+65% to +54%) and deepens their drawdown (54% to 62%).
- Buys did better than sells on both feeds (FxPro +0.014 against −0.077), as with gold's rise in
  every strategy here.
