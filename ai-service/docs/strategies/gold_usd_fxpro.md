# Gold: the dollar's breaks as a gold signal, FxPro's GOLD feed (exploratory)

_`python -m app research gold-usd fxpro`: `GOLD_M1_201501020000_202611052359.csv`, trades 2016-02-01 to 2026-01-09 (EURUSD's lockbox stays sealed). Setting chosen on XAUUSD: {'levels': 'ALL', 'filt': 'LAG'}._

| Set | Trades | Net R (SE) | With slip | Years + | Cost R |
| --- | --- | --- | --- | --- | --- |
| USD | 605 | -0.006 (0.045) | -0.016 | 56% | 0.029 |

Daily net R correlation: LVL4H +0.11, PIVOT +0.06, PIVW +0.13, ASIA +0.07, PWHL +0.10.

**Conditions 3 and 4: not met** (net with slip -0.016).

| Portfolio (net R with slip) | Trades | Mean | Sum | Largest drawdown |
| --- | --- | --- | --- | --- |
| The five | 5,711 | +0.028 | +160.2 | 126.3 |
| The five and USD | 6,316 | +0.024 | +150.8 | 123.7 |

| Year | Trades | Net R | With slip |
| --- | --- | --- | --- |
| 2016 | 12 | +0.373 | +0.362 |
| 2019 | 18 | -0.093 | -0.104 |
| 2020 | 76 | +0.120 | +0.110 |
| 2021 | 79 | +0.038 | +0.027 |
| 2022 | 78 | -0.112 | -0.123 |
| 2023 | 74 | +0.135 | +0.123 |
| 2024 | 137 | -0.216 | -0.226 |
| 2025 | 125 | +0.083 | +0.078 |
| 2026 | 6 | -0.112 | -0.115 |
