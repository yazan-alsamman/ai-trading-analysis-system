# Gold: trade against the five's trades a model expects to fail

_`python -m app research gold-fade build`, registered in `GOLD_FADE.md` (2026-11-10). Fades of the five's own trades (M8 or a 1 D target); LR / LightGBM with Platt and the EV rule; net R with slip. XAUUSD walk-forward 2015-2021, check 2022 to 2026-01-09; FxPro (`GOLD_M1_201501020000_202611052359.csv`) 2022 on._

## 1. Walk-forward 2015-2021

| Model | Exit | Fades | All fades | Accepted | Accepted mean | Random 95th | BSS | Gate 1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lr | M8 | 3,183 | -0.069 | 11 | -0.087 | +0.507 | +0.000 | no |
| lr | TP1 | 3,317 | -0.114 | 54 | -0.161 | -0.064 | -0.003 | no |
| lgbm | M8 | 3,183 | -0.069 | 51 | -0.108 | +0.026 | -0.004 | no |
| lgbm | TP1 | 3,317 | -0.114 | 60 | -0.300 | -0.060 | -0.005 | no |

By year (accepted fades, mean net R with slip):

| Year | lr M8 | lr TP1 | lgbm M8 | lgbm TP1 |
| --- | --- | --- | --- | --- |
| 2015 | - | - | - | - |
| 2016 | +0.244 (7) | +0.167 (6) | - | - |
| 2017 | -0.262 (2) | -1.148 (1) | - | - |
| 2018 | -1.068 (2) | - | - | - |
| 2019 | - | -0.181 (47) | -0.108 (51) | -0.300 (60) |
| 2020 | - | - | - | - |
| 2021 | - | - | - | - |

**No setting passes gate 1: the fade is dropped.**
