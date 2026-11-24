# FxPro M1 exports: summary bars (found 2026-11-11) and the reruns

## The fault

FxPro's M1 history exports for GOLD, NAS100 (`#USNDAQ100`) and XAGUSD hold lines that are not
minutes: **real volume 0 and tick volume above 5,000** (a normal minute has a few hundred). About
250 a year in 2018-2022 (54-66 in 2016-2017, none from 2023), most at 00:00 server time, the start
of the trading day, one hour before trading opens. Each carries the coming day's whole high and low.
Example, GOLD 2018-01-29 00:00: high 1352.30, low 1337.51 (the day's real extremes), tick volume
196,790 (the day's real minutes hold 375,826), real volume 0, spread 0; trading starts at 01:00.

They come from the broker's history, not from the export settings. Live prices do not have them.
The MT5 Strategy Tester reads the same history, so a tester run on GOLD in 2017-2022 sees them too.
The XAUUSD research store (the registered research and every tune / check period) does not have
them: 0-1 unusual bars a year.

Found by `GOLD_MAGNET.md` §6: on FxPro, 1h swing targets sat exactly on the later lows.

**Fix:** `gold_live.summary_bar` drops them in `gold_live.fx_lines` (every GOLD FxPro check),
`five_nas.lines` (NAS100) and `discovery.drivers.store_silver` (silver re-stored: 3,514,713
minutes, 1,236 fewer).

## The reruns (every FxPro check, same code and export `GOLD_M1_201501020000_202611052359.csv`)

Net R a trade with slip, FxPro 2016-02 to 2026-11-05, before and after the fix.

| Check | Before | After | Decision |
| --- | --- | --- | --- |
| The five together | +0.026 (7,251; drawdown 129 R) | **+0.031** (6,442; 126 R) | unchanged: they hold |
| v1 (LVL4H + PIVOT) | +0.021 | +0.017 (LVL4H +0.082, PIVOT −0.018) | unchanged |
| Shadows PIVW / ASIA / PWHL | +0.022 / +0.016 / +0.095 | +0.025 / +0.041 / +0.106 | unchanged |
| ORB (`GOLD_ORB`) | −0.055 | −0.066 | dropped |
| Value area (`GOLD_VP`) | −0.031 | −0.028 | dropped |
| Round numbers (`GOLD_ROUND`) | +0.039 | +0.022; correlation with LVL4H +0.43 | dropped (3, 4) |
| Regime (`GOLD_REGIME`) | PAUSE sums 123-184 R vs ALWAYS 189 | 165-193 R vs 201 | no detector passes |
| Hold past 16:45 (`GOLD_HOLD`) | ALL1 −0.019 vs BASE +0.021 | ALL1 +0.021 vs BASE +0.025 | not adopted (it also failed the check) |
| Tighter SL (`GOLD_SL`) | USD10 +0.033 vs BASE +0.026 | +0.037 vs +0.032 | not adopted (failed 2012-2021) |
| Loss filter (`GOLD_LOSS`) | kept +0.041 vs all +0.025 | kept +0.049 vs all +0.030 | paper shadow, unchanged |
| C1 / C3 (`GOLD_C123`) | +0.010 / +0.016 | +0.014 / +0.016 | unchanged |
| Magnet (`GOLD_MAGNET`) | M0 +0.032 | M0 −0.090 | dropped |
| Path (`gold_path.md`) | +0.043 D at 15 min | +0.051 D at 15 min | descriptive |
| TIME, USD, NIGHT, PULLBACK, RETRACE | not run (dropped before FxPro) | reports now written | dropped before FxPro |
| **Five on NAS100** (`FIVE_NAS100`) | −0.078 (5,189); E0 mean −0.049, 95th −0.025 | **−0.040** (4,831); E0 mean −0.079, 95th −0.056 | still does not pay; **the reading changes** (below) |
| RECLAIM on NAS100 | −0.012 | −0.050 | does not hold |

**What changed in a reading:** on clean NAS100 data the five's gross R is +0.074 a trade (before
+0.015) and their net −0.040 is **above** E0's 95th percentile (−0.056), not below its mean. So
on the Nasdaq the break's side is better than a coin by about the same gross margin as on gold;
the cost (0.105 R a trade) eats it. The five still do not generalise as a trade.

Not rerun: the EA-to-Python match in the tester (`GOLD_V1`) compared two runs on the same faulty
history, so it still holds as a match; `gold-live check --reference fxpro` now compares against
the clean trades.
