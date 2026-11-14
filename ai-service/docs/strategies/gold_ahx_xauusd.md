# Gold AH leg exits: XAUUSD (`GOLD_AHX.md`)

_`python -m app research gold-ah build-x`: XAUUSD store M1, 2012-01-01 to 2026-01-10 (the lockbox is not read). Net R per signal; costs as `GOLD_AHX.md` §1._

## Tune period, 2012-2021

| Setting | Trades | A day | Gross R | Cost R | Net R | Net R slip | Net R 2x | Win |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| X1 | 68,597 | 26.7 | -0.017 | 0.178 | -0.195 | -0.207 | -0.398 | 62% |
| X2 | 68,589 | 26.7 | -0.018 | 0.155 | -0.173 | -0.187 | -0.356 | 65% |

## Check, 2022 to 2026-01-09

| Setting | Trades | A day | Gross R | Cost R | Net R | Net R slip | Net R 2x | Win |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| X1 | 29,965 | 28.9 | -0.002 | 0.047 | -0.049 | -0.056 | -0.110 | 74% |
| X2 | 29,960 | 28.9 | -0.005 | 0.041 | -0.046 | -0.054 | -0.102 | 75% |

## Decision (§4)

| Setting | 1. 2012-2021 | 2. Check | 3. FxPro |
| --- | --- | --- | --- |
| X1 | not met (0% of years +) | not met | not needed |
| X2 | not met (0% of years +) | not met | not needed |

## The edge test (X1, before costs; deciding nothing)

| Period | Trades | TP hit | Random-walk rate | Difference | Median R |
| --- | --- | --- | --- | --- | --- |
| 2012-2021 | 68,597 | 71.8% | 77.0% | -5.2% (SE 0.2%) | $2.90 |
| Check | 29,965 | 73.6% | 77.2% | -3.7% (SE 0.3%) | $5.05 |

Resolved trades only (TP or SL; the time and daily-break exits left out):

| Period | Trades | TP hit | Random-walk rate | Difference | Median R |
| --- | --- | --- | --- | --- | --- |
| 2012-2021 | 63,905 | 77.1% | 76.9% | +0.2% (SE 0.2%) | $2.80 |
| Check | 28,170 | 78.3% | 77.0% | +1.2% (SE 0.2%) | $4.92 |

## Net R by year (no slippage)

| Year | X1 | X2 |
| --- | --- | --- |
| 2011 | -0.196 | -0.171 |
| 2012 | -0.212 | -0.186 |
| 2013 | -0.180 | -0.158 |
| 2014 | -0.305 | -0.268 |
| 2015 | -0.286 | -0.251 |
| 2016 | -0.204 | -0.184 |
| 2017 | -0.266 | -0.237 |
| 2018 | -0.182 | -0.159 |
| 2019 | -0.199 | -0.180 |
| 2020 | -0.076 | -0.069 |
| 2021 | -0.060 | -0.055 |
| 2022 | -0.050 | -0.047 |
| 2023 | -0.059 | -0.055 |
| 2024 | -0.062 | -0.057 |
| 2025 | -0.028 | -0.025 |
| 2026 | +0.006 | -0.012 |

## By side, whole period (net R with slippage)

| Setting | Buys | Sells |
| --- | --- | --- |
| X1 | -0.166 | -0.157 |
| X2 | -0.151 | -0.143 |
