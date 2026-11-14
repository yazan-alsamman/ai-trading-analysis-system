# The path of the five's trades after entry (stage 1)

_`python -m app research trade-path`, registered in `TRADE_PATH.md`. XAUUSD 2012-2021, 3,897 trades. R = each trade's D. Mirror = the same path in the opposite direction. Moves are from the stated moment to 16:45 or the original stop; zero under a random walk._

## 1. The ladder: of the trades that reached +k R, the share that reached +(k + 0.5) R

| k | Reached k | Share on | Mirror | Random walk | z vs mirror |
| --- | --- | --- | --- | --- | --- |
| 0.5 | 2,673 | 72.3% | 69.9% | 75.0% | +1.88 |
| 1 | 1,933 | 74.9% | 72.3% | 80.0% | +1.73 |
| 1.5 | 1,447 | 76.0% | 73.2% | 83.3% | +1.64 |
| 2 | 1,099 | 79.0% | 72.7% | 85.7% | +3.30 |
| 2.5 | 868 | 77.9% | 76.8% | 87.5% | +0.53 |
| 3 | 676 | 79.7% | 78.3% | 88.9% | +0.62 |
| 3.5 | 539 | 75.5% | 74.9% | 90.0% | +0.20 |

## 2. Speed: by the minutes taken to reach +1 R

| Minutes to +1 R | Trades | Reached +2 R | +3 R | Mirror +2 R | Mean move from +1 R | t | Per strategy |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0-15 | 422 | 69.9% | 47.4% | 64.5% | +0.671 | +3.72 | ASIA +0.55 LVL4H +0.50 PIVOT +0.69 PIVW +0.69 PWHL +0.77 |
| 15-60 | 543 | 57.1% | 35.9% | 57.1% | +0.142 | +1.25 | ASIA +0.06 LVL4H +0.00 PIVOT +0.19 PIVW +0.13 PWHL +0.16 |
| 60-180 | 489 | 55.6% | 32.3% | 50.3% | +0.129 | +1.11 | ASIA +0.41 LVL4H +0.15 PIVOT +0.11 PIVW -0.31 PWHL +0.30 |
| 180-... | 479 | 46.3% | 25.7% | 47.8% | +0.167 | +1.35 | ASIA +0.12 LVL4H +0.34 PIVOT +0.16 PIVW +0.12 PWHL +0.08 |

## 3. Give-back: the move after the price is back by g of its peak

| Peak at least | Given back | Trades | Mean move after | t | Mirror | Per strategy |
| --- | --- | --- | --- | --- | --- | --- |
| 1.5 R | 30% | 1,358 | +0.205 | +2.53 | +0.137 | ASIA +0.20 LVL4H +0.12 PIVOT +0.24 PIVW +0.13 PWHL +0.20 |
| 1.5 R | 50% | 1,081 | +0.127 | +1.49 | +0.106 | ASIA +0.21 LVL4H +0.12 PIVOT +0.10 PIVW +0.12 PWHL +0.23 |
| 2 R | 30% | 987 | +0.162 | +1.71 | +0.112 | ASIA +0.05 LVL4H +0.20 PIVOT +0.22 PIVW +0.03 PWHL -0.04 |
| 2 R | 50% | 713 | +0.051 | +0.47 | +0.054 | ASIA +0.08 LVL4H +0.17 PIVOT +0.02 PIVW +0.14 PWHL -0.02 |

## 4. Time without progress: not at +1 R after s minutes

| Minutes | Trades | Mean move after | t | Mirror | Per strategy |
| --- | --- | --- | --- | --- | --- |
| 60 | 2,293 | +0.070 | +1.51 | +0.031 | ASIA +0.06 LVL4H +0.15 PIVOT +0.04 PIVW +0.05 PWHL +0.11 |
| 120 | 1,612 | +0.081 | +1.53 | +0.049 | ASIA +0.04 LVL4H +0.14 PIVOT +0.07 PIVW +0.10 PWHL +0.12 |

## Candidates for stage 2 (|t| >= 3, size >= 0.05 R, same sign in 4 of 5)

- ladder k = 2: 79.0% against the mirror's 72.7% (z +3.3)
- speed 0-15 min, move from +1 R: +0.671 R (t +3.7, same sign in 5 of 5)

Overall: mean final (to 16:45 or the original stop) +0.211 R, mirror +0.107 R; mean peak 1.67 R.
