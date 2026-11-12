# Order blocks as a level family (gold 2012-2021)

_`python -m app levels ob`, registered in `ORDER_BLOCKS.md` (2026-11-12) before the run. Net R a trade, Raw costs unless stated; 200 shifted copies; 4-week block bootstrap._

Blocks: OB-15 12,416, OB-1H 3,263 (2011-2026).

Power (orders before the one-trade-per-book rule, no outcome):

| Behaviour | Orders (before the book rule) | A day | Mean m | Smallest R at t = 3 |
| --- | --- | --- | --- | --- |
| break | 8,144 | 3.15 | 3.50 | 0.062 |
| rejection | 2,524 | 0.98 | 4.86 | 0.132 |

**Primary tests passed: 0 of 2.**

| Behaviour | Trades | A day | Mean net R | At 2x | Standard | Shifted copies | t | Win | Holm | Passed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| break | 6,051 | 2.34 | -0.288 | -0.560 | -0.317 | -0.289 | +0.03 | 39% |  |  |
| rejection | 1,983 | 0.77 | -0.308 | -0.623 | -0.384 | -0.294 | -0.35 | 38% |  |  |

| Family | Behaviour | Trades | Mean net R | At 2x | Standard | Shifted | t | Stable | BH | Passed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OB-15 | break | 4,841 | -0.297 | -0.585 | -0.330 | -0.306 | +0.42 |  |  |  |
| OB-15 | rejection | 1,564 | -0.319 | -0.647 | -0.403 | -0.301 | -0.39 |  |  |  |
| OB-1H | break | 1,210 | -0.252 | -0.456 | -0.267 | -0.223 | -0.88 |  |  |  |
| OB-1H | rejection | 419 | -0.268 | -0.534 | -0.313 | -0.270 | +0.02 |  |  |  |

By year (mean net R):

| Behaviour | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| break | -0.313 | -0.183 | -0.361 | -0.396 | -0.408 | -0.489 | -0.323 | -0.311 | -0.131 | -0.214 |
| rejection | -0.408 | -0.205 | -0.130 | -0.565 | -0.280 | -0.266 | -0.363 | -0.354 | -0.366 | -0.209 |
