# Gold: buy the pullback before the break, and re-enter a strong move (commercial track)

**Registered 2026-11-10, before any outcome of these rules was computed.** Fadi's idea (chat,
2026-11-10): gold breaks a level more often than it bounces from it, so trade the small pullback
after the first touch in the break's direction; and after a strong move, re-enter with it on a
20-30% retracement. The rules below are Claude's proposals that Fadi accepted ("موافق على أغلب
اقتراحاتك"), with his changes: 20% and 30% instead of 50% for part B.

Code: `app/research/gold_pbk.py`, `python -m app research gold-pbk build`. XAUUSD 5m bars, 2012 to
2026-01-09 (all seen before by the commercial track: optimistic). The real test is the demo,
forward.

## 1. Bars, levels and trend

- **5m bars**, New York time. Entries 02:00 to 16:00, Monday to Friday. Every trade is closed by
  16:45 New York the same day (`cx.deadline`).
- **Levels (liquidity).**
  - A 5m swing high: a high above the 3 bars on each side, known 3 bars after it. Swing lows are
    the mirror image.
  - The previous trading day's high and low (PDH, PDL; days run 17:00 to 17:00 New York).
  - A swing level lives 288 bars (24 h) from its bar. A level is **broken** at the first 5m close
    beyond it, and is not used after that.
- **Trend (1h and 4h, market structure).** On each frame, swings with 2 bars on each side, known
  2 bars later. Up: the last swing high is above the one before it and the last swing low above
  the one before it. Down: the mirror image. A buy needs both 1h and 4h up; a sell both down.
  The frames are those closed at the 5m bar's close.

## 2. Part A: PBK, the pullback before the break

For a high (buys; a low is the mirror image, sells):

1. **Away first.** After the level's bar, price must have traded at least 1 x ATR(14, 5m) below
   the level, and the touch must come at least 6 bars after the level's bar.
2. **Touch.** The first 5m bar whose high reaches the level − 0.1 x ATR(14, 5m) without closing
   above it. Only the first touch of each level counts.
3. **Pullback.** Within 12 bars after the touch, the low drops at least 0.5 x ATR below the
   highest high since the touch. If price closes above the level first, there is no trade (the
   break came without a pullback). If the low goes more than 1.5 x ATR below the level first,
   there is no trade (a real bounce).
4. **Entry.** The first bar after the pullback that closes up (close > open), still within the 12
   bars and with no close above the level: buy at its close (market).
5. **SL.** The lowest low since the touch − 0.1 x ATR, at least 1 x ATR below the entry.
6. **Target (a setting).**
   - **R2:** entry + 2 R.
   - **LIQ:** the nearest live level above the touched one that is at least 1 R from the entry;
     with none, no target (the management and the 16:45 exit end the trade).

## 3. Part B: RTB, re-entering a strong move

1. **A strong move.** A leg up on 5m bars: from the lowest low of the 24 bars before a confirmed
   5m swing high (2 bars on each side) to that high, of at least 0.75 x ATR(14, D1). It is known
   2 bars after the high. A leg down is the mirror image. (`gold_retrace.legs`, TF 5m.)
2. **Entry.** From the next bar, a buy limit at H − r x Leg, r = 0.20 or 0.30 (a setting). If the
   bar opens below the limit, the fill is at the open. The limit lapses when price trades above H
   or after 24 bars.
3. **SL.** At the 50% level, H − 0.5 x Leg. If the fill bar reaches the SL too, it is a full loss.
4. **Target (a setting).** R2, or LIQ: the nearest live level above H at least 1 R away (none: no
   target).
5. The trend filter applies as in part A, as a setting.

## 4. Every trade

- **Management: M8 with the target.** After +1 R in favour, the SL moves to entry + cost; then it
  trails to the last confirmed 5m swing (2 bars a side) ∓ 0.1 x ATR(14, 5m) when better and price
  is beyond it (`gold_retrace.simulate`, TRAIL, frame 5m).
- **Exit:** the SL (at the open when the bar gaps through it), the target, or 16:45 New York.
- **Cost:** the entry bar's recorded spread + $0.07 per oz; with slip adds $0.10 on SL exits. A
  trade is skipped when cost / risk > 0.10.
- One trade at a time per strategy and setting.

## 5. Settings and choice

| Strategy | Settings |
| --- | --- |
| PBK | target R2 / LIQ x trend STRUCT / NONE (4) |
| RTB | r 0.20 / 0.30 x target R2 / LIQ x trend STRUCT / NONE (8) |

**Choice, per strategy:** the best mean net R on 2012-2021 among settings with net R > 0, at least
60% of the years positive and at least 300 trades. None: the strategy is dropped. The NONE trend
settings are there to show what the filter adds; they can be chosen like the others.

## 6. Decision (per strategy; `GOLD_NIGHT.md` §3)

1. A setting qualifies on 2012-2021.
2. Net R with slippage > 0 on the check, 2022 to 2026-01-09.
3. Net R with slippage > 0 on FxPro's GOLD feed from 2016-02 (needs a fresh full GOLD M1 export;
   the 2015-2026 export is no longer on this laptop).
4. On FxPro, its daily net R correlates between −0.2 and +0.2 with each of the five demo
   strategies.

A strategy that passes runs as a shadow on the demo.

**Descriptive, decides nothing.**

- Part A: of the first touches (rule 1-2), the share that close beyond the level within 24 bars;
  and of those with a pullback (rule 3), the same share.
- Part B: the share of strong legs that reach 20% and 30% before a new extreme within 24 bars.

## 7. Not yet registered: the doubled add-on

Fadi asked for a second trade at twice the lot when price moves 15% against the first. Its exact
reading is open (15% of which distance; same direction or the opposite one). It is registered as
an addendum to this file once Fadi answers, before it is run.

## 8. Count

12 settings, logged in `docs/phase3/TRIALS.md` as exploratory looks of the commercial track.

## 9. Outcome (2026-11-10): both dropped

`gold_pbk_xauusd.md`. **No setting of either strategy qualifies on 2012-2021 (§5), so both are
dropped at condition 1.** The FxPro run and the correlations were not needed.

- **The observation, first touches.** 75.5% of the first touches of a level close beyond it
  within 24 bars (91,066 touches). With a pullback (rule 3) the share falls to 72.7%; without one
  it is 85.2%. A pullback after the touch makes the break less likely, not more.
- **PBK.**
  - Best on 2012-2021: R2 / STRUCT, +0.038 R on 96 trades, 44% of the years positive; check
    −0.139 R with slip on 203 trades. Without the trend filter: −0.07 to −0.09 R, 18% of the
    years positive.
  - The cost cap (cost / risk ≤ 0.10) keeps 4,223 of 19,282 entries: 1-3% a year before 2020,
    when the SL (about 1 x ATR(5m)) was small against the spread. The median cost is 0.24 R.
- **RTB.**
  - 71% of the strong legs reach 20% before a new extreme, 52% reach 30%.
  - Best on 2012-2021: 0.30 / LIQ / NONE, +0.114 R on 321 trades but 40% of the years positive;
    check −0.035 R with slip. With the 1h + 4h filter every setting loses (few trades).

**Exploratory after the decision (decides nothing): gross R without the cost cap.** Every entry,
before costs:

| Setting | 2012-2021 trades, gross (SE) | 2022 to 2026-01-09 trades, gross (SE) |
| --- | --- | --- |
| PBK R2 NONE | 10,720, +0.008 (0.011) | 4,104, −0.007 (0.018) |
| PBK LIQ NONE | 10,865, −0.005 (0.012) | 4,155, −0.008 (0.020) |
| PBK R2 STRUCT | 972, +0.043 (0.038) | 344, −0.024 (0.065) |
| RTB 0.30 R2 NONE | 842, +0.018 (0.039) | 363, +0.026 (0.062) |
| RTB 0.20 R2 NONE | 1,044, +0.034 (0.033) | 430, −0.005 (0.051) |

The gross is about 0 in every case: the entries carry no direction before costs, so the cost
alone decides the sign. The doubled add-on (§7) was not registered or run; it reshapes the
outcomes of a trade but cannot add direction to entries with a gross of about 0.

## 10. Addendum 1: PBK-M1, fixed $10 SL and TP, entry on M1 (registered 2026-11-10, before the run)

Fadi, after §9: no trend filter; the levels, the touch and the pullback stay on 5m bars; the entry
is on M1; the SL and the TP are fixed in price, "1000 pips" each. On this feed 1 point = $0.01,
so 1,000 points = **$10.00** (if Fadi meant $0.10 pips, i.e. $100, this is rerun with that).

- **5m, as §2 rules 1-3.** The first touch, then the pullback (0.5 x ATR(5m) below the highest
  high since the touch, counted from the touch bar's close). Let p be the 5m bar that completes
  it; the break (a 5m close above the level) and the bounce (1.5 x ATR below the level) still
  cancel, up to and including p.
- **M1 entry.** From the first M1 bar after p closes, until the end of the 12th 5m bar after the
  touch: the first M1 bar that closes up (close > open) is the entry, at its close. An M1 close
  above the level first, or an M1 low more than 1.5 x ATR(5m) below the level first, cancels. The
  5m bar holding the entry must be in the entry window (§1).
- **Exit, on M1 bars.** SL = entry − $10, TP = entry + $10 (sells mirror). The SL fills at the
  bar's open when the bar gaps through it, the TP likewise at the open when it gaps beyond it. A
  bar that reaches both counts as the SL. Otherwise the trade closes at 16:45 New York. No M8.
- **Cost:** the entry M1 bar's recorded spread + $0.07 per oz; with slip adds $0.10 on SL exits.
  No cost cap (the SL is fixed). One trade at a time.
- **One setting, no choice.** It passes when, on 2012-2021, net R > 0 with at least 60% of the
  years positive and at least 300 trades; and net R with slip > 0 on the check, 2022 to
  2026-01-09. Then the FxPro and correlation conditions of §6 follow. Reported beside it,
  descriptive: the share of trades reaching the TP, the SL and the time exit.

### Outcome of Addendum 1 (2026-11-10): dropped

`gold_pbk_m1_xauusd.md`. On 2012-2021: 4,111 trades, net −0.040 R (SE 0.011), 10% of the years
positive. Check: 2,534 trades, −0.018 R with slip. **Condition 1 fails: PBK-M1 is dropped.**

- Gross R is about 0: −0.002 (SE 0.011) on 2012-2021, +0.004 (0.017) on the check.
- +$10 before −$10 is a coin flip: TP 23.3% against SL 22.6% (54% end at 16:45) on 2012-2021,
  35.4% against 34.7% on the check.
- The cost is now small (0.037 R, then 0.019 R), so the loss is the cost of trades with no
  direction.
