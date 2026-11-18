# The five as a portfolio: risk split, result

_`python -m app research risk-split`, registered in `RISK_SPLIT.md`. Same trades as the EA; only the weight changes. Day result = sum of w x net R with slip. Sharpe per day over days with a trade of the five. 4-week block bootstrap, 10,000 resamples, seed 20261115._

rho (store 2012-2021, 2,636 pairs): +0.6624, used 0.6624.

## Decision

**No rule passes. The EA keeps equal risk.**

| Rule | Sharpe diff (store 2022 to 2026-01-09) | 95% | p | Holm p | DD at equal return smaller (store / FxPro) | FxPro Sharpe higher | Passes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SPLIT | -0.0170 | -0.0326 to -0.0007 | 0.9790 | 1.0000 | no / no | no | no |
| LEARNED | -0.0130 | -0.0252 to -0.0001 | 0.9756 | 1.0000 | no / no | no | no |

## Each rule

| Data | Rule | Days | Mean R a day | Total R | Daily Sharpe | Max DD at equal return (R) |
| --- | --- | --- | --- | --- | --- | --- |
| Store 2022 to 2026-01-09 (test) | BASE | 1,030 | +0.2522 | +259.8 | 0.0629 | 57.5 |
| Store 2022 to 2026-01-09 (test) | SPLIT | 1,030 | +0.1077 | +111.0 | 0.0459 | 91.6 |
| Store 2022 to 2026-01-09 (test) | LEARNED | 1,030 | +0.1289 | +132.7 | 0.0499 | 81.6 |
| Store 2012-2021 (rho fitted here) | BASE | 2,005 | +0.0728 | +146.0 | 0.0260 | 66.1 |
| Store 2012-2021 (rho fitted here) | SPLIT | 2,005 | +0.0265 | +53.1 | 0.0134 | 184.8 |
| Store 2012-2021 (rho fitted here) | LEARNED | 2,005 | +0.0328 | +65.7 | 0.0157 | 145.8 |
| FxPro 2016-02 to 2026-11-05 | BASE | 2,391 | +0.0841 | +201.0 | 0.0279 | 125.3 |
| FxPro 2016-02 to 2026-11-05 | SPLIT | 2,391 | +0.0115 | +27.6 | 0.0060 | 1011.1 |
| FxPro 2016-02 to 2026-11-05 | LEARNED | 2,391 | +0.0222 | +53.2 | 0.0108 | 517.3 |
| FxPro 2026-01-12 on (never used) | BASE | 208 | +0.1962 | +40.8 | 0.0678 | 39.9 |
| FxPro 2026-01-12 on (never used) | SPLIT | 208 | +0.1236 | +25.7 | 0.0687 | 44.9 |
| FxPro 2026-01-12 on (never used) | LEARNED | 208 | +0.1350 | +28.1 | 0.0687 | 44.0 |

## Same-direction overlap (BASE trades of the five)

| Data | k | Trades | Share | Mean net R with slip |
| --- | --- | --- | --- | --- |
| Store 2012 to 2026-01-09 | 0 | 4,335 | 52.9% | +0.0087 |
| Store 2012 to 2026-01-09 | 1 | 1,773 | 21.7% | +0.0484 |
| Store 2012 to 2026-01-09 | 2 | 1,229 | 15.0% | +0.1360 |
| Store 2012 to 2026-01-09 | 3+ | 852 | 10.4% | +0.1351 |
| FxPro | 0 | 3,387 | 52.6% | -0.0207 |
| FxPro | 1 | 1,431 | 22.2% | +0.0598 |
| FxPro | 2 | 966 | 15.0% | +0.1183 |
| FxPro | 3+ | 658 | 10.2% | +0.1083 |

## rho per strategy pair (store 2012-2021; new trade x open trade)

| New | Open | Pairs | rho |
| --- | --- | --- | --- |
| ASIA | LVL4H | 151 | +0.889 |
| ASIA | PIVOT | 74 | +0.365 |
| ASIA | PIVW | 81 | +0.912 |
| ASIA | PWHL | 26 | +0.847 |
| LVL4H | ASIA | 203 | +0.775 |
| LVL4H | PIVOT | 78 | +0.554 |
| LVL4H | PIVW | 100 | +0.700 |
| LVL4H | PWHL | 24 | +0.520 |
| PIVOT | ASIA | 240 | +0.663 |
| PIVOT | LVL4H | 246 | +0.610 |
| PIVOT | PWHL | 34 | +0.667 |
| PIVW | ASIA | 226 | +0.767 |
| PIVW | LVL4H | 235 | +0.806 |
| PIVW | PIVOT | 466 | +0.734 |
| PIVW | PWHL | 33 | +0.803 |
| PWHL | ASIA | 115 | +0.566 |
| PWHL | LVL4H | 141 | +0.640 |
| PWHL | PIVOT | 76 | +0.269 |
| PWHL | PIVW | 86 | +0.400 |

(The registration asked for rho by level family; it is given per strategy pair, which is what the trades carry.)

## Per year (store; BASE / SPLIT / LEARNED)

| Year | Total R | Sharpe | Max DD at equal return |
| --- | --- | --- | --- |
| 2012 | -1.1 / -11.7 / -10.5 | -0.003 / -0.032 / -0.028 | nan / nan / nan |
| 2013 | +24.4 / +21.7 / +21.9 | 0.068 / 0.064 / 0.064 | 21.2 / 21.8 / 22.0 |
| 2014 | +17.1 / +11.9 / +12.6 | 0.058 / 0.042 / 0.044 | 40.3 / 58.0 / 54.7 |
| 2015 | +38.9 / +38.9 / +38.9 | 0.104 / 0.104 / 0.104 | 11.9 / 11.9 / 11.9 |
| 2016 | +16.8 / +3.8 / +5.4 | 0.031 / 0.010 / 0.013 | 23.3 / 100.1 / 71.7 |
| 2017 | -17.2 / -17.2 / -17.2 | -0.067 / -0.067 / -0.067 | nan / nan / nan |
| 2018 | -6.5 / -6.4 / -6.2 | -0.021 / -0.022 / -0.021 | nan / nan / nan |
| 2019 | -1.2 / -19.3 / -16.6 | -0.003 / -0.058 / -0.047 | nan / nan / nan |
| 2020 | +89.2 / +43.2 / +49.7 | 0.077 / 0.066 / 0.069 | 49.0 / 60.8 / 58.4 |
| 2021 | -14.4 / -11.9 / -12.2 | -0.014 / -0.020 / -0.018 | nan / nan / nan |
| 2022 | +48.2 / +30.0 / +33.4 | 0.047 / 0.049 / 0.049 | 47.6 / 50.9 / 49.2 |
| 2023 | +74.7 / +21.6 / +28.8 | 0.059 / 0.030 / 0.036 | 57.5 / 135.0 / 108.0 |
| 2024 | +42.4 / +2.6 / +7.7 | 0.045 / 0.005 / 0.013 | 29.4 / 521.6 / 172.2 |
| 2025 | +94.6 / +58.3 / +64.2 | 0.111 / 0.115 / 0.115 | 31.9 / 29.2 / 29.5 |
| 2026 | -0.1 / -1.6 / -1.3 | -0.007 / -0.132 / -0.101 | nan / nan / nan |

## The six with ROUND (reported, not tested)

| Data | Rule | Days | Mean R a day | Total R | Daily Sharpe | Max DD at equal return (R) |
| --- | --- | --- | --- | --- | --- | --- |
| Store 2022 to 2026-01-09 | BASE | 1,031 | +0.3370 | +347.5 | 0.0755 | 65.3 |
| Store 2022 to 2026-01-09 | SPLIT | 1,031 | +0.1288 | +132.7 | 0.0521 | 112.3 |
| Store 2022 to 2026-01-09 | LEARNED | 1,031 | +0.1572 | +162.0 | 0.0573 | 99.1 |
| FxPro 2016-02 to 2026-11-05 | BASE | 2,397 | +0.1276 | +305.9 | 0.0378 | 120.9 |
| FxPro 2016-02 to 2026-11-05 | SPLIT | 2,397 | +0.0271 | +65.0 | 0.0136 | 613.3 |
| FxPro 2016-02 to 2026-11-05 | LEARNED | 2,397 | +0.0409 | +98.1 | 0.0188 | 399.7 |

## The deepest BASE drawdowns (FxPro) and each rule in them

| Peak day | Trough day | BASE fall (R) | SPLIT change | LEARNED change |
| --- | --- | --- | --- | --- |
| 20160621 | 20201027 | -125.3 | -916.5 | -475.7 |
| 20260908 | 20261105 | -39.9 | -204.0 | -113.5 |
| 20251114 | 20260121 | -33.9 | -159.8 | -89.9 |

Rule changes are scaled to BASE's mean (equal return).
