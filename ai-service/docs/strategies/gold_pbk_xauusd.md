# Gold: PBK (pullback before the break) and RTB (re-enter a strong move), XAUUSD

_`python -m app research gold-pbk build`, registered in `GOLD_PBK.md` (2026-11-10). XAUUSD 5m bars 2012-01 to 2026-01-09; cost = the entry bar's recorded spread + $0.07 per oz; with slip adds $0.10 on stop exits. Tune 2012-2021, check 2022 to 2026-01-09. Seen data: optimistic. The lockbox was not read._

## 1. Descriptive (decides nothing)

| First touches | Count | Closed beyond within 24 bars |
| --- | --- | --- |
| All | 91,066 | 75.5% |
| With a pullback (rule 3) | 70,466 | 72.7% |
| Without | 20,600 | 85.2% |

| Strong legs (>= 0.75 x ATR(D1)) | Count | Reach 20% | Reach 30% |
| --- | --- | --- | --- |
| 5m | 3,128 | 71% | 52% |

## 2. PBK: the settings (by net R on 2012-2021)

| target | filt | Tune trades | Tune net | Tune years + | Tune cost R | Check trades | Check net (SE) | Check with slip | Eligible |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R2 | STRUCT | 96 | +0.038 | 44% | 0.067 | 203 | -0.108 (0.085) | -0.139 |  |
| LIQ | STRUCT | 95 | -0.038 | 33% | 0.067 | 205 | -0.093 (0.093) | -0.125 |  |
| R2 | NONE | 1,113 | -0.066 | 18% | 0.068 | 2,272 | -0.069 (0.025) | -0.101 |  |
| LIQ | NONE | 1,135 | -0.088 | 18% | 0.068 | 2,296 | -0.073 (0.026) | -0.106 |  |

**No setting qualifies: PBK is dropped.**

## 3. RTB: the settings (by net R on 2012-2021)

| r | target | filt | Tune trades | Tune net | Tune years + | Tune cost R | Check trades | Check net (SE) | Check with slip | Eligible |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.3 | LIQ | NONE | 321 | +0.114 | 40% | 0.054 | 341 | -0.019 (0.069) | -0.035 |  |
| 0.2 | LIQ | NONE | 630 | +0.037 | 40% | 0.058 | 410 | -0.022 (0.057) | -0.034 |  |
| 0.3 | R2 | NONE | 329 | +0.023 | 50% | 0.054 | 352 | +0.008 (0.062) | -0.005 |  |
| 0.2 | R2 | NONE | 648 | -0.001 | 60% | 0.057 | 420 | -0.021 (0.052) | -0.031 |  |
| 0.2 | R2 | STRUCT | 73 | -0.039 | 44% | 0.056 | 41 | -0.279 (0.142) | -0.291 |  |
| 0.3 | LIQ | STRUCT | 36 | -0.065 | 43% | 0.051 | 30 | -0.357 (0.205) | -0.376 |  |
| 0.2 | LIQ | STRUCT | 71 | -0.070 | 44% | 0.056 | 41 | -0.283 (0.141) | -0.295 |  |
| 0.3 | R2 | STRUCT | 36 | -0.108 | 43% | 0.051 | 31 | -0.276 (0.197) | -0.294 |  |

**No setting qualifies: RTB is dropped.**
