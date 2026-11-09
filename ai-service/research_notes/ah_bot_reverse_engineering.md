# "AH" gold bot: reverse engineering from trade history

Source: the bot's MT5 trade report in the repo's untracked `data/` folder (FxPro MT5, real, hedge;
2026-10-14 → 2026-11-06; deposit 3000). It is a third party's account: keep it out of git.
Parsing scripts lived in the session scratchpad (re-create if needed: read the Positions / Orders / Deals tables from the UTF-16 HTML).

## Execution structure (confirmed from Orders)
- Comment tags `AH_S{0|1}_E{1|2}`: two setups (S0 = 136 signals, S1 = 23), two legs each.
- E1: market order, opened at exactly hh:mm:00 (158/159) → triggered on an M1 bar close. Minute-of-hour is uniform (no M5/M15 alignment).
- E2: limit order placed at the same second, double size (0.04 vs 0.02), ~0.18 × SL-distance better than E1. Filled 104/162, otherwise cancelled.
- Both legs start with the same SL and TP. TP ≈ 0.4 × SL (TP1). SL is variable (median 9.5 $, range 3–40 $): structure based, not fixed.
- Size: 0.02 normally, 0.01 when SL is wide (median SL 20 $ for 0.01 vs 8.5 $ for 0.02).
- When E2 hits TP1, E1's TP is pushed out (~0.7 × SL) and its SL often moved to ~entry (break-even). If E2 never fills, E1 just takes TP1.
- 12 positions without the tag (round-number SL/TP) look manual; net ≈ +7 $.

## Results (per signal, E1+E2)
- 159 signals, +323.7 $, win rate 69.8 %, avg win +17.9 $, avg loss −34.7 $, worst −79.4 $.
- S0 +429.7 $; S1 −106.0 $.
- E2 filled: +21.9 $ over 104 signals; E2 not filled: +301.8 $ over 55. The edge comes from signals that move in favour immediately.
- Balance dipped to ~2740 (−8.7 %) by 2026-10-29 (−227.7 $ that day) and recovered only in 2026-11-02 → 11-06 (+538 $).
- By entry hour (server time): 12–17h +483 $, 00–06h −224 $.

## Lockbox decision (Fadi, 2026-11-08)
This analysis is separate from the research. It may use GOLD M1 bars for 2026-10-13 → 2026-11-07,
which overlap the primary lockbox (2026-01-10 → export date). The bars live outside `ai-service`
(`data/bot_gold_m1.csv`), are never imported into the research store, and nothing from this analysis
feeds the registered research. Disclose this exposure in the thesis.

## Entry profile (FxPro GOLD M1 export 2026-10-01 → 2026-11-05, 156 signals matched)
- Fill = decision-bar close (sell at bid, buy at bid + spread 0.32): the bot acts on the M1 close.
- Trend-pullback profile vs 1,500 random bar/direction draws:
  ret60 in trade direction +5.8 $ median (random −0.1), pos60 0.74 (0.50),
  ret5 −1.0 $ (random +0.2), pos5 0.31 (0.54), EMA9>21 in direction 77 % of the time
  (random 50 %), EMA20>50 72 %, RSI(14) 54 (50). The decision bar's own colour is random (no
  confirmation candle).
- SL is not an ATR multiple (CV 0.56–0.65 on M1–H1) and not a clean M1/M5/M15 extreme or pivot.
  TP/SL is not fixed either (0.42 median, IQR 0.32–0.51). Source still unknown.
- Candidate rule (EMA9>21 & EMA20>50 in direction, ret60 > 2 $, ret5 < 0) matches 47 % of
  entries but would fire about 250 times a day against the bot's 9: filters are missing.
  Bot trades that match it net −45 $ (74); those that do not, +270 $ (82).

## Entry vs non-entry bars (156 entries vs 35,670 eligible bar/direction pairs)
- Hard condition: close − close[10] > 0 in trade direction on the decision bar, 156/156
  (min +0.02 $). Neighbour lags are not hard: k=9 70 %, k=11 83 %, k=15 81 %. So a 10-bar momentum
  (MT5 Momentum/ROC period 10) filter is almost certainly in the rules. It is a state, not a cross
  (only 26 % flip on that bar).
- Short pullback: close < close[3..5] in about 71 % of entries; stochastic %K(5) median 0.31.
- LightGBM (5-fold CV) separates entries with average precision 0.11 (base 0.004); precision at the
  bot's own frequency is 18 %. Top features: pos10, ret10, distance to EMA50, body, ret3. The shallow
  tree only rediscovers ret10 ≥ 0 plus a pullback in an EMA20>50 trend. The exact trigger is still
  unknown: it may use inputs not in M1 bid bars (ticks, other symbols, news, a model score).
- SL: all 156 values are distinct with random cents (computed, not a level). No match with previous-day,
  day, H1/H4, M15 extremes, day open or round numbers. Best explanation is volatility: corr(log SL,
  log 10-bar M1 range) 0.73, SL about 1.7 × that range, but with CV 0.63 it is not a fixed multiple.
  TP shows the same link (corr 0.73).

## In-sample what-ifs on the bot's own 156 matched signals (descriptive only, not evidence)
All signals +224 $. S0 only +371. One trade at a time +377 (136). 4-hour move in direction > 0:
+411 (111) vs −186 (45). Deepest third of pullbacks (pos60 ≤ 0.64) +292, the rest −68.
Tightest third of SL (≤ 6.9 $) −423, widest third +516. TP/SL top third +399, rest −175.
E2 filled: E1 −202, E2 +127. Daily stop after 1 or 2 losses makes it worse (+45 / +38).

## Open question
The entry trigger. Needs GOLD M1 bars for 2026-10-13 → 2026-11-07 from the same FxPro feed (local m1.parquet ends 2026-01-09).

## Clone test (2026-11-08)
Registered and run as `docs/strategies/GOLD_AH.md` (code `app/research/gold_ah.py`, report
`docs/strategies/gold_ah_xauusd.md`). AHB plus V1-V6 and ALL: all dropped. Gross R is about 0,
net R −0.16 to −0.22 on 2012-2021 and −0.03 to −0.06 on 2022 to 2026-01-09. On the bot's own weeks
the clone matches 52% of its entries but fires about 7 times as often and is negative after costs.

## SL and TP found (2026-11-09)
In 132 of the 156 matched signals, the order's SL and TP come from one formula on the impulse leg
before the pullback, L (its low) to H (its high), R = H − L, for a buy (a sell is the mirror):

- **TP = L + 1.088 × R** (8.8% of the leg beyond its high), most common ratio 1.088 (1,103
  trade × window hits; next 1.089).
- **SL = H − 2.025 × R** (one leg plus 2.5% below its low), most common ratio 2.025 (1,426 hits).
- L is before H in 99% of them: the leg goes up, then the pullback is the entry. Median: L 12 min
  and H 5 min before the entry, R about $6 (IQR $4.1 to $9.5).
- L is the last 3-bar M1 pivot low before H in 104 of 132 (k = 2: 82, k = 4: 82). H is the
  highest high since L (it may be unconfirmed). The exact leg finder (perhaps MT5's ZigZag) is not
  pinned down.
- The 24 that do not fit: 20 S0, 4 S1 (S0 and S1 use the same formula).

So the wide stop is not a choice per trade: it is one leg length below the leg's low, while the
target is just past the leg's high. With entry in the pullback, the TP is usually closer than the
SL. Under a random walk the win rate is SL / (SL + TP), so this shape alone gives a high win rate
and no edge; an edge needs price to reach the old high more often than that.

## Leg-exit test (2026-11-09)
`docs/strategies/GOLD_AHX.md`: the bot's exits rebuilt from the leg match its orders to $0.05 in
69% of signals. On 14 years the TP is hit exactly as often as a random walk predicts (+0.2 points on
2012-2021, +1.2 on the check), gross R about 0; both settings dropped. The wide-SL / near-TP shape is
the bot's geometry, not its edge.

## Filter search (2026-11-09)
`docs/strategies/GOLD_AHF.md`: 50 features on every X1 signal (110,811 trades on 2012-2017). No
feature quintile, hour, weekday or session has gross R > 0 there. The greedy filter chosen on
2012-2017 gave +0.010 gross on 2018-2021 (p 0.128), far below the 0.15-0.17 R cost; stopped before
meta-labeling. Bigger legs lose less (less cost per R), but stay below zero before costs.
