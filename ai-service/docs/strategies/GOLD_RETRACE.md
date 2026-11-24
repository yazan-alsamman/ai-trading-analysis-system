# Gold: the 50% correction after a strong move (commercial track)

**Registered 2026-11-07, before any outcome of these rules was computed.**

**Fadi's observation.** After a very strong rise or fall, gold often corrects about half the
move. He sees it most on the 5m, 15m, 30m and 1h charts. A strong move is about $50-70 today, or
$20-30 on a quiet day.

**Two strategies, each alone and together:**

- **CORR** trades the correction itself.
- **FIB50** buys (or sells) the 50% level in the direction of the move.

The target is always the 50% level for CORR, with a "logical" trailing stop as an option. v1 and
the shadow strategies do not change.

Code: `app/research/gold_retrace.py`.

- `python -m app research gold-retrace build` tunes and checks on XAUUSD.
- `gold-retrace fxpro --export <GOLD M1 export>` runs the same on FxPro's GOLD feed.

Reports: `gold_retrace_xauusd.md`, `gold_retrace_fxpro.md`.

## 1. Data and costs

These are as `GOLD_SHADOW.md` §1:

- XAUUSD 2012-2021 to tune, 2022 to 2026-01-09 to check.
- FxPro `GOLD` from 2016-02 to 2026-11-05.
- Cost: the signal bar's recorded spread + $0.07 per oz.
- $0.10 slippage on stop exits, reported beside the net.

## 2. The strong move (a leg)

- **Bars.** Timeframe (TF) bars are built from the 5m bars, on UTC boundaries: 5m, 15m, 30m or
  1h.
- **Swings.** A swing high at bar b is the highest high of bars b − 2 to b + 2. It is confirmed
  at the close of bar b + 2. Swing lows are the mirror image.
- **A leg up**, at the confirmation bar j = b + 2:
  - H = the high of b.
  - L = the lowest low of the 24 TF bars up to b.
  - H must be the highest high from L's bar to j.
  - Leg = H − L.
  - It counts when **Leg ≥ K × ATR(14, D1)**, the last daily bar closed by j.
  - A size against the day's volatility puts a $25 move on a quiet day and a $60 move on a fast
    day on one scale.
- **A leg down** is the mirror image.
- **Times.** Signals Monday to Friday, not in the daily break (17:00-18:00 New York).

## 3. The two strategies

The 50% level is P50 = H − 0.5 × Leg after a leg up. Buys and sells are mirror images.

**CORR (with the correction).**

- At the close of bar j: sell at that close.
- The target is P50. The SL is H + 0.1 × Leg.
- It trades only when the target is at least 0.5 R away (R = the SL distance).

**FIB50 (after the correction).**

- From the next 5m bar, a buy limit at P50.
- The limit is valid until price trades above H, or 24 TF bars pass.
- The SL is at the 78.6% level, H − 0.786 × Leg. The target is H.
- If the fill bar reaches the SL too, the trade is a full loss.

**Management (a setting):**

- **FIXED.** The SL and the target as above.
- **TRAIL.** The target stays.
  - After +1 R in favour, the SL moves to entry + cost.
  - Then it trails to the last confirmed TF swing (a swing high for a sell, a swing low for a
    buy) ∓ 0.1 × ATR(14, TF), when that is better and price is beyond it.
  - So small pullbacks inside the trend do not stop the trade.

**Every trade:**

- Exit at the SL (at the bar's open when it gapped through), the target, or the close 24 TF bars
  after the entry.
- Cost cap: (spread + $0.07) / R ≤ 0.10.
- One trade at a time per strategy.

## 4. Grid and choice

| Setting | Values |
| --- | --- |
| TF | 5m, 15m, 30m, 1h |
| K | 0.5, 0.75, 1.0 × ATR(14, D1) |
| Management | FIXED, TRAIL |

- That is 24 settings per strategy, and 48 in all.
- **Choice, per strategy.** The best mean net R on 2012-2021, among settings with net R > 0, at
  least 60% of the years positive and at least 300 trades. If none qualifies, the strategy is
  dropped.
- **Together.** The chosen CORR and FIB50 run side by side, each one trade at a time. They are
  reported alone and together: mean, sum and the largest drawdown in R, on 2012-2021 and on the
  check.

## 5. Decision (per strategy)

These are the conditions of `GOLD_NIGHT.md` §3:

1. A setting qualifies on 2012-2021.
2. Net R with slippage > 0 on the check, 2022 to 2026-01-09.
3. Net R with slippage > 0 on FxPro, 2016-02 to 2026-11-05.
4. On FxPro, its daily net R correlates between −0.2 and +0.2 with each of LVL4H, PIVOT, PIVW,
   ASIA and PWHL.

A strategy that passes runs as a shadow on the demo.

**Descriptive, decides nothing.** Is the observation true? For each TF and K, the share of legs
where price reached P50 before a new extreme within 24 TF bars. The baseline is the smaller legs,
of 0.25 to 0.5 × ATR(D1).

## 6. Count

There are 48 settings. They are logged in `docs/phase3/TRIALS.md`, as exploratory looks of the
commercial track.

## 7. Outcome (2026-11-07): both dropped

`gold_retrace_xauusd.md`. **No setting qualifies on 2012-2021 for either strategy, so both are
dropped at condition 1.** The FxPro run and the correlations were not needed.

- **The observation does not hold in the data.**
  - The stronger the move, the less often price reaches its 50% level before a new extreme.
  - On 5m: 46% of the baseline legs (0.25-0.5 × ATR(D1)), 33% of legs ≥ 0.5, 24% of legs ≥ 0.75,
    20% of legs ≥ 1.0. On 1h: 73%, 50%, 44%, 38%.
  - Half of a small leg is also a shorter distance, so part of this comes from the size itself.
    Still, strong legs mostly continue rather than give back half.
  - A strong move that does correct half stands out on the chart; the ones that continue do not.
- **CORR loses in every setting.**
  - On 2012-2021: −0.06 to −0.14 R a trade, with 10-40% of the years positive.
  - On the check: −0.01 to −0.15 R.
- **FIB50 is about zero or below.**
  - Its three best settings on 2012-2021 (+0.074, +0.037, +0.006) had 109 to 288 trades and
    lost on the check (−0.18 to −0.01).
  - The 1h settings were near zero on the check (−0.03 to +0.03).
- **The trailing stop changed little,** by ±0.03 R a trade.
