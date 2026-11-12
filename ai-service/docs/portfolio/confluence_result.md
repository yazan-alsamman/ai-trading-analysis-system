# Confluence on six markets: result

_`python -m app research confluence`, registered in `CONFLUENCE.md`. The frozen five; k = the five's trades open in the same direction at the entry. d = mean gross R (k >= 1) - mean gross R (k = 0). 4-week calendar blocks, 10,000 resamples, seed 20261116._

## Decision

Pooled D = +0.0050 R (95% -0.0315 to +0.0387), one-sided p 0.4014; d > 0 in 3 of 6 markets.

**Hypothesis C does not pass.** The gold pattern is treated as specific to the data it was found on; nothing changes.

## Per market

| Market | Period | Trades | k >= 1 | d gross (95%) | Gross R k = 0 / 1 / 2 / 3+ | Net R with slip k = 0 / k >= 1 |
| --- | --- | --- | --- | --- | --- | --- |
| NAS100 | 2016-02-02 to 2026-11-09 | 4,831 | 36.1% | -0.0250 (-0.1075 to +0.0557) | +0.083 / +0.046 / +0.066 / +0.075 | -0.0701 / +0.0132 |
| EURUSD | 2016-03-02 to 2026-01-09 | 6,542 | 48.1% | +0.0265 (-0.0342 to +0.0845) | +0.032 / +0.038 / +0.061 / +0.104 | -0.0323 / +0.0158 |
| GBPUSD | 2017-03-01 to 2026-01-08 | 4,300 | 38.5% | +0.0468 (-0.0348 to +0.1289) | +0.051 / +0.033 / +0.147 / +0.196 | -0.0416 / +0.0524 |
| USDJPY | 2016-03-01 to 2026-01-08 | 4,051 | 37.6% | +0.0644 (-0.0150 to +0.1479) | +0.099 / +0.112 / +0.162 / +0.289 | -0.0041 / +0.1193 |
| AUDUSD | 2018-03-01 to 2026-01-08 | 3,920 | 42.7% | -0.0234 (-0.1043 to +0.0558) | +0.038 / +0.037 / -0.009 / +0.003 | -0.0604 / -0.0252 |
| USDCAD | 2016-03-01 to 2026-01-08 | 3,642 | 28.7% | -0.0593 (-0.1438 to +0.0179) | +0.073 / -0.026 / +0.067 / +0.039 | -0.0550 / -0.0347 |

All six pooled by trade: 27,286 trades; net R with slip k = 0 -0.0439, k >= 1 +0.0243; gross k = 0 +0.0623, k >= 1 +0.0683.

FX costs are approximate (commission 0.00007 x the median price, no SL slip); the decision uses gross R.
