# Gold: the dollar's breaks as a gold signal (commercial track)

**Registered 2026-11-10, before any outcome of these rules was computed.** Claude's proposal,
chosen by Fadi ("وبعدها بالرقم 2 تبع الدولار"): when EURUSD (the dollar, inverted) breaks one of its
own day levels, trade gold the same way at once, on the chance that gold follows the dollar a
little later.

Code: `app/research/gold_usd.py`, `python -m app research gold-usd build` (XAUUSD) and
`gold-usd fxpro --export <GOLD M1>` (FxPro's GOLD feed).

## 1. Data and the lockbox

- EURUSD 5m bars from the research store, 2016-01-10 to 2026-01-09 (`gold_lab.load("EURUSD")`).
  **The EURUSD lockbox file (2026-01-10 on) stays sealed for P9**, so no trade is taken after
  2026-01-09, on either gold feed.
- Gold: XAUUSD (research feed) and FxPro's GOLD export, aligned with EURUSD on the bar's UTC open.
- Tune 2016-2021 (EURUSD starts in 2016), check 2022 to 2026-01-09.

## 2. Signal and trade

1. **EURUSD break.** EURUSD's day levels, as LVL4H's: PDH, PDL (setting **PD**), or PDH, PDL, 5DH,
   5DL (setting **ALL**). The first touch of each level of the day inside 02:00-16:00 New York,
   Monday to Friday, crossing it from below (up) or above (down) (`gold_combo.levels`, no cost
   cap: EURUSD is not traded).
2. **Gold trade.** At the close of gold's 5m bar with the same open time: up on EURUSD (a weaker
   dollar) buys gold at market at that close; down sells.
3. **Not yet moved (a setting).** **NONE**: always. **LAG**: only when gold has not already moved
   that way by a quarter of D over the last 12 bars (d x (close − close 12 bars before) < 0.25 D).
4. **Exits: LVL4H's frozen ones.** D = 0.75 x ATR(14, 4h) of gold; SL = entry ∓ D; no target; M8;
   horizon 200 bars; exit by 16:45 New York. Cost cap (spread + $0.07) / D ≤ 0.05. One trade at a
   time.

| Setting | Values |
| --- | --- |
| Levels | PD, ALL |
| Filter | NONE, LAG |

## 3. Choice and decision (`GOLD_NIGHT.md` §3, with the tune years above)

- **Choice:** the best mean net R on 2016-2021 among settings with net R > 0, at least 60% of the
  years positive and at least 300 trades. None: dropped.
- **Decision:** 1. a setting qualifies; 2. net R with slip > 0 on the check; 3. net R with slip > 0
  on FxPro's GOLD feed, 2016-02 to 2026-01-09; 4. on FxPro, daily net R correlation with each of
  the five demo strategies within ±0.2. A setting that passes runs as a shadow on the demo (live
  it would need EURUSD in the EA).
- **Descriptive (decides nothing):** the correlation of EURUSD's 5m return with gold's 5m return
  in the same bar and in the next one, 2016 to 2026-01-09. A lead shows as a next-bar correlation
  above zero.

## 4. Count

4 settings, logged in `docs/phase3/TRIALS.md` as exploratory looks of the commercial track.

## 5. Outcome (2026-11-10): dropped at condition 2

`gold_usd_xauusd.md`. The FxPro run was not needed.

- **EURUSD does not lead gold at 5 minutes.** Their 5m returns move together in the same bar
  (+0.347 over 703,250 bars), but EURUSD's bar says nothing about gold's next one (−0.001).
- Chosen on 2016-2021: ALL / LAG, +0.064 R (+0.052 with slip) on 302 trades, 4 of the 5 years with
  trades positive (2016 had 10 trades at +1.5 R).
- **Check, 2022 to 2026-01-09: −0.029 R with slip on 507 trades** (2 of 5 years positive), so
  condition 2 fails. Every setting is at or below 0 on the check (−0.013 to −0.029).
- Without the LAG filter the signal is about 0 on both periods.
