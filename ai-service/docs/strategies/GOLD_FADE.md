# Gold: trade against the five's trades a model expects to fail (commercial track)

**Registered 2026-11-10, before any outcome of this test was computed.** Fadi's idea (chat,
2026-11-10): keep the five demo strategies as they are, and train a model on their trades to
find the ones likely to lose, then trade **the other way** on those, as a separate strategy.

Code: `app/research/gold_fade.py`, `python -m app research gold-fade build --export <GOLD M1>`.

**What is known before:** trading the other way on every break, without a model, lost on FxPro:
MIRROR −0.10 R a trade over 2016-2026 (`TRIALS.md`, 2026-11-08). So the model has to find a
subset where the fade wins; on average it does not.

## 1. The fade trade

For each trade the five take (one at a time, M8, as the EA):

- Same bar, same entry price, **the opposite side**, D the same. SL = entry + d x D (where the
  original would be +1 D).
- **Exit (a setting):** **M8** on the fade, or **TP1**: target at 1 D (where the original's SL
  is), no trail. Both end at the original's end time (its horizon or 16:45 New York).
- Cost: the entry bar's spread + $0.07; slip $0.10 on SL exits. One fade at a time per strategy.

## 2. The model (meta-labeling, as `GOLD_AHF.md` §6)

- **Label:** y = 1 when the fade's net R > 0, weighted by |net R|; Platt calibration on the last
  25% of each training window; a fade is taken when p x m1 + (1 − p) x m0 > 0, with m1 and m0 the
  training fades' mean net R of winners and losers.
- **Features, known at the entry bar:** strategy, level kind, side, New York hour, weekday, US
  data minute, with or against the day, 1h + 4h structure, earlier trades today (categories);
  D / ATR(D1), ATR(D1) against its last 250 days, move done today / ATR(D1), the previous bar's
  range / ATR(5m), yesterday's range / ATR(D1), cost R, minute of the day (numbers)
  (`gold_loss.features`).
- **Models:** LR (C by inner time-split CV on `meta.C_GRID`) and LightGBM (`meta.LGBM_PARAMS`).
- 4 settings: 2 models x 2 exits.

## 3. Periods and decision

- **Walk-forward, 2015-2021 (XAUUSD):** each year tested by a model trained on every earlier
  year from 2012 (fades closed a day before the test year).
- **Gate 1 (walk-forward):** the accepted fades' net R with slip over 2015-2021 is > 0, above the
  95th percentile of 20 random acceptances of the same count each year, and comes from at least
  300 fades.
- **Choice:** among settings passing gate 1, the best accepted mean on the walk-forward.
- **Gate 2 (check, XAUUSD 2022 to 2026-01-09):** the chosen setting retrained on 2012-2021; its
  accepted fades' net R with slip > 0.
- **Gate 3 (FxPro GOLD 2022-01 to the export's end):** the same model on FxPro's trades; accepted
  net R with slip > 0.
- **Gate 4:** daily net R correlation with each of the five < +0.2 (a negative one is expected).
- A setting that passes all four runs as a shadow strategy. Reported beside it: the fades without
  a model, Brier skill, accepted counts, 2026 on FxPro.

## 4. Count

4 settings, logged in `docs/phase3/TRIALS.md` as exploratory looks of the commercial track.

## 5. Outcome (2026-11-10): dropped at gate 1

`gold_fade_xauusd.md`. The check and FxPro runs were not needed.

| Model / exit | Fades 2015-2021 | All fades, net R with slip | Accepted | Accepted mean | Brier skill |
| --- | --- | --- | --- | --- | --- |
| LR / M8 | 3,183 | −0.069 | 11 | −0.087 | +0.000 |
| LR / TP1 | 3,317 | −0.114 | 54 | −0.161 | −0.003 |
| LightGBM / M8 | 3,183 | −0.069 | 51 | −0.108 | −0.004 |
| LightGBM / TP1 | 3,317 | −0.114 | 60 | −0.300 | −0.005 |

- **The models find nothing.** Brier skill is 0 or below for all four: the features say no more
  about which fades win than the base rate does. With the EV rule they accept 11-60 of over 3,000
  fades, and those lose too.
- **The fade itself loses** −0.07 to −0.11 R a trade, as MIRROR did: it takes the breaks' small
  gross edge with the sign turned, and pays its own cost on top.
- The five's losing trades have nothing in common that a model can see at the entry, so no
  strategy can be built on trading against them.
