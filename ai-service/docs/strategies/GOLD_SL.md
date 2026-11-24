# Gold: a tighter SL with a larger lot for the five level breaks (commercial track)

**Registered 2026-11-10, before any outcome of these rules was computed.** Fadi's idea (chat,
2026-11-10): the SL is always far ($15-28 now), so set it nearer, around $10, and raise the lot so
each trade still risks the same share of the account. On a small account this also lets every
strategy trade (a 0.25% trade on $10,000 needs D ≤ $25 for 0.01 lots).

The risk a trade stays the same, so the question is only whether a nearer SL, with the same
entries and M8, makes more R a trade. LVL4H's distance was tuned among 0.75, 1.0 and 1.5 x
ATR(4h) (`gold_combo.py`); nothing nearer than 0.75 was tried.

Code: `app/research/gold_sl.py`, `python -m app research gold-sl build [--export <GOLD M1>]`.

## 1. The test

- **Entries:** the five strategies' own (`gold_exit.signals`), unchanged, the same trades in the
  same order. The cost cap keeps its original test (on the current D), so the entry set is the same
  in every setting.
- **SL distance D' (a setting):**

| Setting | D' |
| --- | --- |
| BASE | the current D: 0.75 x ATR(14, 4h) (PIVOT: ATR(14, 1h)) |
| H50 | 0.5 x the current D |
| H67 | 2/3 x the current D |
| USD10 | $10 |
| USD15 | $15 |

- **Management:** M8 on D' (break-even at +1 D', then the swing trail), no target, the strategies'
  own end times.
- **R** is D': gross R = move / D', cost R = (spread + $0.07) / D', slip $0.10 on SL exits.

## 2. Choice and decision

- **Choice:** the setting other than BASE with the best mean net R with slip of the five together
  on XAUUSD 2012-2021.
- **Adopt** (a v1 change, so as a shadow version first, as `GOLD_V1.md` requires) only if its mean
  net R with slip of the five together is **above BASE's on 2012-2021, on the check (2022 to
  2026-01-09) and on FxPro's GOLD feed (2016-02 to the export's end)**.
- Reported beside it: each strategy, the largest drawdown in R, and on FxPro 2026 the share of
  trades a $10,000 account could take at 0.25% (0.01 lots at least).

## 3. Count

4 settings beside BASE, logged in `docs/phase3/TRIALS.md` as exploratory looks of the commercial
track.

## 4. Outcome (2026-11-10): not adopted

`gold_sl_xauusd.md`. Chosen on 2012-2021: USD10, +0.015 R a trade with slip, **below BASE's
+0.034**, so §2 fails at its first period.

| Five together, net R with slip | BASE | USD10 | H50 |
| --- | --- | --- | --- |
| XAUUSD 2012-2021 | +0.034 | +0.015 | +0.008 |
| XAUUSD 2022 to 2026-01-09 | +0.062 | +0.071 | +0.094 |
| FxPro 2016-02 to 2026-11-05 | +0.026 | +0.033 | +0.032 |
| FxPro 2026 | +0.054 | −0.009 | −0.012 |

- **No nearer SL wins everywhere.** Halving D helps in 2022-2025 and loses in 2012-2021 (its cost
  doubles to 0.16 R) and in 2026. A fixed $10 is a wide SL in the quiet years (D was about $5) and
  a narrow one now (D about $28): in 2026 it is about 0.36 D, 98% of the trades end at the SL, and
  it loses.
- **USD10 has the smallest drawdowns** in R (FxPro 79 R against 134 R), and on 2026 every trade
  could be taken at 0.25% on $10,000 (BASE: 29%). It would let the shadows trade, but in the
  current market it loses.
- The current distance (0.75 x ATR(4h)) stays.
