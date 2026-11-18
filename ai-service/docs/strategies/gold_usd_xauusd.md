# Gold: the dollar's breaks as a gold signal, XAUUSD feed (exploratory)

_`python -m app research gold-usd build`, registered in `GOLD_USD.md` (2026-11-10). EURUSD and XAUUSD 5m bars, 2016-01 to 2026-01-09; LVL4H's frozen exits; cost = gold's signal bar spread + $0.07 per oz; with slip adds $0.10 on stop exits. Tune 2016-2021, check 2022 to 2026-01-09. No lockbox file was read._

## 1. Does EURUSD lead gold? (descriptive)

Correlation of 5m log returns over 703,250 common bars: same bar +0.347, EURUSD then gold's next bar -0.001.

## 2. The four settings (by net R on 2016-2021)

| Levels | Filter | Tune trades | Tune net | Tune years + | Tune cost R | Check trades | Check net (SE) | Check with slip | Eligible |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ALL | LAG | 302 | +0.064 | 80% | 0.026 | 507 | -0.019 (0.049) | -0.029 | yes |
| PD | LAG | 279 | +0.036 | 80% | 0.027 | 451 | -0.017 (0.052) | -0.028 |  |
| ALL | NONE | 540 | +0.002 | 20% | 0.026 | 948 | -0.007 (0.037) | -0.018 |  |
| PD | NONE | 500 | -0.011 | 40% | 0.026 | 872 | -0.002 (0.039) | -0.013 |  |

Chosen: {'levels': 'ALL', 'filt': 'LAG'}.

| Set | Trades | Net R (SE) | With slip | Years + | Cost R |
| --- | --- | --- | --- | --- | --- |
| 2016-2021 | 302 | +0.064 (0.072) | +0.052 | 80% | 0.026 |
| Check | 507 | -0.019 (0.049) | -0.029 | 40% | 0.021 |
| Buys | 389 | +0.062 (0.057) | +0.051 | 70% | 0.023 |
| Sells | 420 | -0.034 (0.058) | -0.045 | 40% | 0.023 |

Daily net R correlation with the five (decides nothing here): LVL4H +0.17, PIVOT +0.03, PIVW +0.16, ASIA +0.10, PWHL +0.08.

| Year | Trades | Net R | With slip |
| --- | --- | --- | --- |
| 2016 | 10 | +1.510 | +1.498 |
| 2018 | 6 | +0.244 | +0.229 |
| 2019 | 26 | -0.360 | -0.372 |
| 2020 | 135 | +0.035 | +0.024 |
| 2021 | 125 | +0.060 | +0.047 |
| 2022 | 126 | -0.108 | -0.121 |
| 2023 | 119 | +0.171 | +0.157 |
| 2024 | 131 | -0.200 | -0.210 |
| 2025 | 125 | +0.086 | +0.081 |
| 2026 | 6 | -0.110 | -0.114 |
