# Gold: what the five strategies' losing trades share (XAUUSD and FxPro)

_`python -m app research gold-loss build`, registered in `GOLD_LOSS.md` (2026-11-10). The five's own trades (M8), net R with slip. Buckets and the filter chosen on XAUUSD 2012-2021; 50 shuffles; read on the check and on FxPro (`GOLD_M1_201501020000_202611052359.csv`)._

Trades: 4,041 on 2012-2021 (losers 59%, mean +0.034), 4,148 on the check (mean +0.062).

## 1. The buckets, worst first (2012-2021)

| Feature | Bucket | Share | Mean net R | Losers | t against the rest | Check mean | Check trades |
| --- | --- | --- | --- | --- | --- | --- | --- |
| yday_range | q4 | 20% | -0.137 | 62% | -4.3 | +0.044 | 934 |
| cost_q | q4 | 20% | -0.083 | 63% | -2.7 | +0.013 | 97 |
| weekday | 2 | 20% | -0.080 | 63% | -2.5 | -0.061 | 896 |
| prev_bar | q2 | 20% | -0.074 | 61% | -2.6 | +0.036 | 887 |
| moved | q4 | 20% | -0.069 | 62% | -2.5 | -0.036 | 730 |
| yday_range | q2 | 20% | -0.060 | 65% | -2.1 | +0.140 | 814 |
| vol_regime | q4 | 19% | -0.060 | 58% | -2.2 | +0.130 | 1,411 |
| with_day | against | 11% | -0.048 | 54% | -1.6 | +0.022 | 532 |
| d_atr | q2 | 20% | -0.039 | 62% | -1.7 | -0.021 | 345 |
| vol_regime | q2 | 19% | -0.033 | 61% | -1.4 | +0.081 | 324 |
| yday_range | q5 | 20% | -0.020 | 58% | -1.3 | +0.053 | 1,002 |
| d_atr | q4 | 20% | -0.017 | 60% | -1.2 | +0.018 | 1,234 |
| hour | 02-05 | 42% | -0.015 | 56% | -1.9 | +0.031 | 1,905 |
| kind | R1 | 31% | -0.015 | 62% | -1.4 | +0.054 | 888 |
| earlier | 0 | 50% | -0.014 | 60% | -2.1 | +0.033 | 1,030 |
| kind | ASL | 10% | -0.006 | 58% | -0.6 | +0.030 | 591 |
| hour | 10-12 | 12% | -0.005 | 58% | -0.7 | +0.154 | 507 |
| strategy | PIVOT | 49% | -0.003 | 64% | -1.6 | +0.065 | 824 |
| weekday | 3 | 21% | +0.011 | 58% | -0.6 | +0.022 | 878 |
| side | buy | 49% | +0.011 | 58% | -1.0 | +0.113 | 2,141 |
| strategy | ASIA | 20% | +0.011 | 55% | -0.6 | +0.039 | 1,268 |
| news | no | 93% | +0.016 | 59% | -2.1 | +0.042 | 3,803 |
| moved | q1 | 20% | +0.022 | 56% | -0.3 | +0.083 | 1,104 |
| cost_q | q2 | 20% | +0.024 | 58% | -0.2 | +0.015 | 1,477 |
| kind | ASH | 10% | +0.029 | 51% | -0.1 | +0.046 | 677 |

The best buckets, for comparison:

| Feature | Bucket | Share | Mean net R | Losers | t | Check mean |
| --- | --- | --- | --- | --- | --- | --- |
| news | yes | 7% | +0.263 | 58% | +2.1 | +0.287 |
| yday_range | q3 | 20% | +0.198 | 55% | +3.2 | +0.045 |
| yday_range | q1 | 20% | +0.192 | 54% | +3.3 | +0.024 |
| kind | PDL | 6% | +0.171 | 55% | +1.3 | +0.040 |
| d_atr | q5 | 20% | +0.151 | 47% | +2.9 | +0.102 |
| strategy | LVL4H | 14% | +0.150 | 51% | +2.1 | +0.101 |
| hour | 08-10 | 23% | +0.138 | 60% | +2.3 | +0.083 |
| weekday | 0 | 18% | +0.130 | 54% | +2.0 | +0.104 |

## 2. The filter

Removed: yday_range = q4, cost_q = q4.

| Period | All trades | Kept | Removed |
| --- | --- | --- | --- |
| XAUUSD 2012-2021 | +0.034 (4,041) | +0.113 (2,610) | -0.109 (1,431) |
| XAUUSD check | +0.062 (4,148) | +0.069 (3,131) | +0.042 (1,017) |
| FxPro 2016-02 on | +0.025 (7,252) | +0.041 (4,855) | -0.008 (2,397) |
| FxPro 2026 | +0.054 (756) | +0.004 (605) | +0.253 (151) |

Gain on 2012-2021: +0.079 R a trade; shuffled 95th percentile +0.064.

| Condition | Met |
| --- | --- |
| 1. Gain above the shuffled 95th percentile | yes |
| 2. Check: kept above all | yes |
| 3. FxPro: kept above all | yes |
| 4. At least 60% of the trades kept | yes |

**Decision (§3): adopt as a shadow version.**

## 3. Buckets below −0.10 R on 2012-2021 and on the check (candidates, decide nothing)

None.
