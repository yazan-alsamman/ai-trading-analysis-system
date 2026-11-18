# Gold: the pullback inside a strong move, traded with the move (commercial track)

**Registered 2026-11-07, before any outcome of these rules was computed** (Fadi).

**The idea.** After a strong move, a shallow pullback of at least 15%, then an entry with the
move when the pullback ends.

**Why this follows from `GOLD_RETRACE.md`:**

- Strong legs mostly do not reach their 50% level.
- FIB50 waited for that level, so it filled only on the deep pullbacks, where the move often
  ends.

**Fadi's choices:**

- A pullback of 15% to 50%.
- Two signals for the end of the pullback.
- Three targets, all with the trailing stop.

v1 and the shadow strategies do not change.

Code: `app/research/gold_pullback.py`.

- `python -m app research gold-pullback build` tunes and checks on XAUUSD.
- `gold-pullback fxpro --export <GOLD M1 export>` runs the same on FxPro's GOLD feed.

Reports: `gold_pullback_xauusd.md`, `gold_pullback_fxpro.md`.

## 1. Data, costs, legs

- Data and costs are as `GOLD_SHADOW.md` §1.
- Legs, TF bars, swings and signal times are as `GOLD_RETRACE.md` §2.
  - A leg runs from the lowest low of 24 TF bars to a confirmed swing high H, with size ≥ K ×
    ATR(14, D1).
  - It is confirmed at bar j.
  - A leg down is the mirror image.

## 2. Rules: PBC (pullback continuation)

These are written for a leg up; a leg down is the mirror image. Depth = (H − the lowest low since
H) / leg.

- **The pullback.** After H, price must not trade above H before the entry.
  - If the depth passes 50%, the leg is dropped.
  - The entry needs a depth of at least 15%.
  - Everything happens within 24 TF bars of j.
- **The end of the pullback (a setting):**
  - **SWING.** The first swing low p after H, confirmed at p + 2, with a depth of 15% to 50%.
    - A buy stop goes at the highest high of bars p to p + 2.
    - It is valid from the next 5m bar while price stays above the low of p and the leg's
      24-bar limit runs.
    - The fill is at the stop, or at the bar's open when it gapped above.
    - If the fill bar reaches the SL too, the trade is a full loss.
  - **BAR.** The first TF bar t with a depth of at least 15% that closes above the previous TF
    bar's high. The entry is at that close.
- **The SL.** The pullback's low (SWING: the low of p; BAR: the lowest low since H) − 0.1 ×
  ATR(14, TF).
- **The target (a setting); the trailing stop is on in every case:**
  - **HIGH.** The leg's end H.
  - **ABCD.** The pullback's low + the leg's size (the measured move).
  - **NONE.** No target: only the trailing stop and the time limit.
  - HIGH and ABCD need the target at least 0.5 R away.
- **The trailing stop** is as GOLD_RETRACE's TRAIL.
  - After +1 R in favour, the SL moves to entry + cost.
  - Then it trails to the last confirmed TF swing low − 0.1 × ATR(14, TF), when that is better
    and price is above it.
- **Every trade:**
  - Exit at the SL (at the bar's open when it gapped through), the target, or the close 48 TF
    bars after the entry.
  - Cost cap: (spread + $0.07) / R ≤ 0.10.
  - One trade at a time.

## 3. Grid and choice

| Setting | Values |
| --- | --- |
| TF | 5m, 15m, 30m, 1h |
| K | 0.5, 0.75 × ATR(14, D1) |
| End of the pullback | SWING, BAR |
| Target | HIGH, ABCD, NONE |

- That is 48 settings.
- **Choice:** the best mean net R on 2012-2021, among settings with net R > 0, at least 60% of
  the years positive and at least 300 trades. If none qualifies, PBC is dropped.

## 4. Decision

These are the conditions of `GOLD_NIGHT.md` §3:

1. A setting qualifies on 2012-2021.
2. Net R with slippage > 0 on the check, 2022 to 2026-01-09.
3. Net R with slippage > 0 on FxPro, 2016-02 to 2026-11-05.
4. On FxPro, the daily net R correlates between −0.2 and +0.2 with each of LVL4H, PIVOT, PIVW,
   ASIA and PWHL.

A pass runs as a shadow on the demo.

**Reported beside the decision, and deciding nothing:**

- results by year and by side;
- SWING against BAR, and the three targets, on the chosen TF and K;
- the five day strategies with and without PBC.

## 5. Count

There are 48 settings. They are logged in `docs/phase3/TRIALS.md`, as exploratory looks of the
commercial track.

## 6. Outcome (2026-11-07): dropped

`gold_pullback_xauusd.md`.

- **Three settings qualified on 2012-2021.** The choice was 30m, K 0.75, SWING, ABCD.
  - On 2012-2021: +0.048 R a trade (+0.031 with slippage), 511 trades, 60% of the years positive.
  - **On the check: −0.005 R (−0.021 with slippage), 458 trades.**
- **Condition 2 fails, so PBC is dropped.** The FxPro run was not needed.

**What it showed, deciding nothing:**

- **Its correlation with the day strategies is near zero:** +0.02 to +0.07 a day with LVL4H,
  PIVOT, PIVW, ASIA and PWHL. A pullback entry trades other days than the level breaks.
- **Year by year it swings:** −0.43 R in 2018, +0.25 in 2020, −0.13 in 2023 and 2024, +0.23 in
  2025.
- **The settings ranked the same way:**
  - SWING (a stop above the bars that confirm the pullback's low) did better than BAR.
  - No target, or the measured move, did better than the old high.
  - The two best settings on the check (5m, K 0.75, SWING, NONE or ABCD: +0.03 with slippage)
    had too few trades on 2012-2021 (252 and 258). Picking one of them now would be choosing on
    the check.
