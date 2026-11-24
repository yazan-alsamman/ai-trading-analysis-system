# Gold night reversion on the XAUUSD feed (commercial track, exploratory)

_`python -m app research gold-night build`, registered in `GOLD_NIGHT.md` (2026-11-07). XAUUSD 5m bars 2012-01 to 2026-01-09; cost = the signal bar's recorded spread + $0.07 per oz; with slip adds $0.10 on stop exits. Tune 2012-2021, check 2022 to 2026-01-09. Seen data: optimistic. The lockbox was not read._

## 1. The 12 settings (by net R on 2012-2021)

| Box end | Entry | SL (x W) | Target | Tune trades | Tune net | Tune years + | Tune cost R | Check trades | Check net (SE) | Check with slip | Eligible |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 21:00 | reclaim | 0 | far | 156 | +0.011 | 62% | 0.067 | 318 | +0.020 (0.089) | -0.004 |  |
| 21:00 | reclaim | 0 | mid | 130 | +0.006 | 57% | 0.069 | 308 | -0.041 (0.067) | -0.061 |  |
| 20:00 | touch | 0.5 | far | 241 | -0.041 | 56% | 0.071 | 493 | -0.076 (0.061) | -0.100 |  |
| 21:00 | touch | 1 | far | 1,021 | -0.062 | 20% | 0.057 | 992 | -0.091 (0.026) | -0.100 |  |
| 20:00 | reclaim | 0 | far | 163 | -0.066 | 29% | 0.068 | 354 | +0.046 (0.071) | +0.027 |  |
| 20:00 | touch | 1 | far | 604 | -0.077 | 20% | 0.061 | 930 | -0.062 (0.032) | -0.077 |  |
| 21:00 | touch | 0.5 | far | 453 | -0.085 | 10% | 0.063 | 767 | -0.049 (0.045) | -0.068 |  |
| 20:00 | touch | 1 | mid | 774 | -0.090 | 30% | 0.060 | 1,239 | -0.074 (0.020) | -0.084 |  |
| 21:00 | touch | 1 | mid | 1,182 | -0.091 | 0% | 0.057 | 1,253 | -0.102 (0.018) | -0.109 |  |
| 21:00 | touch | 0.5 | mid | 514 | -0.110 | 10% | 0.063 | 920 | -0.108 (0.031) | -0.124 |  |
| 20:00 | reclaim | 0 | mid | 135 | -0.179 | 33% | 0.070 | 319 | +0.025 (0.054) | +0.011 |  |
| 20:00 | touch | 0.5 | mid | 289 | -0.233 | 33% | 0.070 | 589 | -0.093 (0.041) | -0.112 |  |

**No setting qualifies (section 2 of the registration): NIGHT is dropped.**
