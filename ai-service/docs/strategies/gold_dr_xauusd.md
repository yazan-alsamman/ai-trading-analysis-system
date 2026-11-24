# Gold dealing range: XAUUSD (`GOLD_DR.md`)

_`python -m app research gold-dr build`: XAUUSD store M1 to 2026-01-10 (the lockbox is not read), 15m ranges. Net R per trade; costs and slippage as `GOLD_DR.md` §1._

## Tune period, 2012-2021

| Setting | Trades | Gross R | Cost R | Net R | Net R slip | Net R 2x | Win | TP | Time | Years + |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2R LOW M1.5 | 2 | +0.985 | 0.039 | +0.946 | +0.946 | +0.907 | 50% | 50% | 50% | 100% |
| 4R LOW M1.5 | 2 | +0.941 | 0.039 | +0.902 | +0.902 | +0.863 | 50% | 0% | 100% | 100% |
| 2R EQ M1.5 | 1 | -0.033 | 0.078 | -0.111 | -0.111 | -0.189 | 0% | 0% | 100% | 0% |
| 4R EQ M1.5 | 1 | -0.033 | 0.078 | -0.111 | -0.111 | -0.189 | 0% | 0% | 100% | 0% |
| 2R LOW M3 | 2 | +0.985 | 0.039 | +0.946 | +0.946 | +0.907 | 50% | 50% | 50% | 100% |
| 4R LOW M3 | 2 | +0.941 | 0.039 | +0.902 | +0.902 | +0.863 | 50% | 0% | 100% | 100% |
| 2R EQ M3 | 1 | -0.033 | 0.078 | -0.111 | -0.111 | -0.189 | 0% | 0% | 100% | 0% |
| 4R EQ M3 | 1 | -0.033 | 0.078 | -0.111 | -0.111 | -0.189 | 0% | 0% | 100% | 0% |

## Check, 2022 to 2026-01-09

| Setting | Trades | Gross R | Cost R | Net R | Net R slip | Net R 2x | Win | TP | Time | Years + |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2R LOW M1.5 | 0 | | | | | | | | | |
| 4R LOW M1.5 | 0 | | | | | | | | | |
| 2R EQ M1.5 | 0 | | | | | | | | | |
| 4R EQ M1.5 | 0 | | | | | | | | | |
| 2R LOW M3 | 0 | | | | | | | | | |
| 4R LOW M3 | 0 | | | | | | | | | |
| 2R EQ M3 | 0 | | | | | | | | | |
| 4R EQ M3 | 0 | | | | | | | | | |

## Decision (§3, §4)

No setting qualifies on 2012-2021 (net R > 0, ≥ 60% of years, ≥ 300 trades): **DR is dropped at condition 1.**

## Ranges (deciding nothing)

- M 1.5: 19 touches of 50%, 9 FVG orders.
- M 3: 11 touches of 50%, 10 FVG orders.

## Net R by year (no slippage)

| Year | 2R LOW M1.5 | 4R LOW M1.5 | 2R EQ M1.5 | 4R EQ M1.5 | 2R LOW M3 | 4R LOW M3 | 2R EQ M3 | 4R EQ M3 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2011 | +1.911 | +2.562 | +nan | +nan | +1.911 | +2.562 | +nan | +nan |
| 2012 | +0.946 | +0.902 | -0.111 | -0.111 | +0.946 | +0.902 | -0.111 | -0.111 |

## By side, whole period (net R with slippage)

| Setting | Buys | Sells |
| --- | --- | --- |
| 2R LOW M1.5 | +1.992 | +0.906 |
| 4R LOW M1.5 | +1.904 | +1.231 |
| 2R EQ M1.5 | +nan | -0.111 |
| 4R EQ M1.5 | +nan | -0.111 |
| 2R LOW M3 | +1.992 | +0.906 |
| 4R LOW M3 | +1.904 | +1.231 |
| 2R EQ M3 | +nan | -0.111 |
| 4R EQ M3 | +nan | -0.111 |
