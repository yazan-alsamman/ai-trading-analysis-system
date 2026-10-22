# P2 detector review: XAUUSD, EURUSD, GBPUSD, USDJPY, USDCAD (L1)

Sample: 50 of 608 patterns of the development period (2012-2017), spread evenly over instrument x with / without FVG (patterns per cell: EURUSD without FVG 52, EURUSD with FVG 42, GBPUSD without FVG 27, GBPUSD with FVG 28, USDCAD without FVG 62, USDCAD with FVG 39, USDJPY without FVG 45, USDJPY with FVG 32, XAUUSD without FVG 136, XAUUSD with FVG 145),
seed 410733 (fixed before the charts were drawn). Each chart ends two bars after the
CHoCH. Times are New York.

A pattern is **valid** (`yes`) when all of these hold on the chart:

1. **Liquidity.** The dashed line is a real resting level: a clear swing high/low on its timeframe
   or the previous trading day's high/low, still untaken when it was swept.
2. **Sweep.** Price trades through it and closes back on that bar or the next; the move looks like a
   grab of the liquidity, not a breakout that happens to close back.
3. **CHoCH.** The close (blue marker) breaks the swing (dotted line) that structurally matters for
   the move into the sweep.
4. **FVG.** The shaded gap is an imbalance left by the displacement away from the sweep. **Only when a gap is shaded**: a pattern without an FVG (title "no FVG") is judged on points 1-3.

Write `yes` or `no` in **Valid**; for a `no`, say in **Notes** which point fails. The written
conditions themselves are already checked by the tests; this review asks whether the result is a
genuine trading pattern.

| # | Chart | Pattern | Sweep (NY) | Direction | Level | Valid | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | [01_XAUUSD_buy_20120731_1715.png](01_XAUUSD_buy_20120731_1715.png) | XAUUSD `buy:pd:low:201207262100:1611.74` (FVG) | 2012-07-31 13:15 | buy | pd 1611.74 |  |  |
| 2 | [02_XAUUSD_sell_20120802_0945.png](02_XAUUSD_sell_20120802_0945.png) | XAUUSD `sell:1h:high:201208011700:1605.8` (FVG) | 2012-08-02 05:45 | sell | 1h 1605.80 |  |  |
| 3 | [03_XAUUSD_sell_20130503_1015.png](03_XAUUSD_sell_20130503_1015.png) | XAUUSD `sell:4h:high:201304260100:1485.21` (FVG) | 2013-05-03 06:15 | sell | 4h 1485.21 |  |  |
| 4 | [04_XAUUSD_buy_20140509_0900.png](04_XAUUSD_buy_20140509_0900.png) | XAUUSD `buy:1h:low:201405090100:1288.3` (FVG) | 2014-05-09 05:00 | buy | 1h 1288.30 |  |  |
| 5 | [05_XAUUSD_sell_20151015_1215.png](05_XAUUSD_sell_20151015_1215.png) | XAUUSD `sell:4h:high:201510141700:1189.7` (no FVG) | 2015-10-15 08:15 | sell | 4h 1189.70 |  |  |
| 6 | [06_XAUUSD_sell_20151216_1800.png](06_XAUUSD_sell_20151216_1800.png) | XAUUSD `sell:pd:high:201512132200:1077.48` (no FVG) | 2015-12-16 13:00 | sell | pd 1077.48 |  |  |
| 7 | [07_EURUSD_sell_20160205_1330.png](07_EURUSD_sell_20160205_1330.png) | EURUSD `sell:4h:high:201602041000:1.12387` (no FVG) | 2016-02-05 08:30 | sell | 4h 1.12387 |  |  |
| 8 | [08_EURUSD_sell_20160324_1030.png](08_EURUSD_sell_20160324_1030.png) | EURUSD `sell:1h:high:201603240000:1.1186` (no FVG) | 2016-03-24 06:30 | sell | 1h 1.11860 |  |  |
| 9 | [09_EURUSD_buy_20160412_1400.png](09_EURUSD_buy_20160412_1400.png) | EURUSD `buy:4h:low:201604080500:1.13488` (FVG) | 2016-04-12 10:00 | buy | 4h 1.13488 |  |  |
| 10 | [10_EURUSD_buy_20160418_0630.png](10_EURUSD_buy_20160418_0630.png) | EURUSD `buy:1h:low:201604180200:1.12759` (no FVG) | 2016-04-18 02:30 | buy | 1h 1.12759 |  |  |
| 11 | [11_USDJPY_buy_20160427_1800.png](11_USDJPY_buy_20160427_1800.png) | USDJPY `buy:1h:low:201604271300:111.097` (no FVG) | 2016-04-27 14:00 | buy | 1h 111.097 |  |  |
| 12 | [12_EURUSD_sell_20160504_0700.png](12_EURUSD_sell_20160504_0700.png) | EURUSD `sell:1h:high:201605040100:1.15082` (no FVG) | 2016-05-04 03:00 | sell | 1h 1.15082 |  |  |
| 13 | [13_USDCAD_sell_20160509_0815.png](13_USDCAD_sell_20160509_0815.png) | USDCAD `sell:4h:high:201605060900:1.29515` (no FVG) | 2016-05-09 04:15 | sell | 4h 1.29515 |  |  |
| 14 | [14_XAUUSD_sell_20160516_1230.png](14_XAUUSD_sell_20160516_1230.png) | XAUUSD `sell:pd:high:201605082100:1287.46` (no FVG) | 2016-05-16 08:30 | sell | pd 1287.46 |  |  |
| 15 | [15_USDJPY_buy_20160607_1445.png](15_USDJPY_buy_20160607_1445.png) | USDJPY `buy:1h:low:201606070000:107.216` (FVG) | 2016-06-07 10:45 | buy | 1h 107.216 |  |  |
| 16 | [16_USDJPY_sell_20160630_1430.png](16_USDJPY_sell_20160630_1430.png) | USDJPY `sell:1h:high:201606301000:102.918` (no FVG) | 2016-06-30 10:30 | sell | 1h 102.918 |  |  |
| 17 | [17_EURUSD_buy_20160706_1415.png](17_EURUSD_buy_20160706_1415.png) | EURUSD `buy:1h:low:201607060200:1.10357` (FVG) | 2016-07-06 10:15 | buy | 1h 1.10357 |  |  |
| 18 | [18_USDCAD_sell_20160706_1430.png](18_USDCAD_sell_20160706_1430.png) | USDCAD `sell:1h:high:201607060200:1.30477` (no FVG) | 2016-07-06 10:30 | sell | 1h 1.30477 |  |  |
| 19 | [19_USDCAD_buy_20160707_1215.png](19_USDCAD_buy_20160707_1215.png) | USDCAD `buy:1h:low:201607070800:1.29161` (no FVG) | 2016-07-07 08:15 | buy | 1h 1.29161 |  |  |
| 20 | [20_USDJPY_sell_20160727_1800.png](20_USDJPY_sell_20160727_1800.png) | USDJPY `sell:1h:high:201607271400:105.88` (no FVG) | 2016-07-27 14:00 | sell | 1h 105.880 |  |  |
| 21 | [21_XAUUSD_sell_20160816_1230.png](21_XAUUSD_sell_20160816_1230.png) | XAUUSD `sell:4h:high:201608101300:1357.11` (no FVG) | 2016-08-16 08:30 | sell | 4h 1357.11 |  |  |
| 22 | [22_USDCAD_sell_20160824_0630.png](22_USDCAD_sell_20160824_0630.png) | USDCAD `sell:pd:high:201608222100:1.29461` (FVG) | 2016-08-24 02:30 | sell | pd 1.29461 |  |  |
| 23 | [23_USDJPY_buy_20160826_1415.png](23_USDJPY_buy_20160826_1415.png) | USDJPY `buy:pd:low:201608232100:100.092` (FVG) | 2016-08-26 10:15 | buy | pd 100.092 |  |  |
| 24 | [24_USDJPY_buy_20161207_1645.png](24_USDJPY_buy_20161207_1645.png) | USDJPY `buy:pd:low:201612052200:113.497` (no FVG) | 2016-12-07 11:45 | buy | pd 113.497 |  |  |
| 25 | [25_USDCAD_buy_20161212_1445.png](25_USDCAD_buy_20161212_1445.png) | USDCAD `buy:1h:low:201612120600:1.31112` (FVG) | 2016-12-12 09:45 | buy | 1h 1.31112 |  |  |
| 26 | [26_EURUSD_sell_20170119_1300.png](26_EURUSD_sell_20170119_1300.png) | EURUSD `sell:1h:high:201701190900:1.06701` (no FVG) | 2017-01-19 08:00 | sell | 1h 1.06701 |  |  |
| 27 | [27_USDJPY_sell_20170227_1330.png](27_USDJPY_sell_20170227_1330.png) | USDJPY `sell:1h:high:201702241400:112.473` (FVG) | 2017-02-27 08:30 | sell | 1h 112.473 |  |  |
| 28 | [28_USDJPY_buy_20170327_1200.png](28_USDJPY_buy_20170327_1200.png) | USDJPY `buy:1h:low:201703270700:110.115` (FVG) | 2017-03-27 08:00 | buy | 1h 110.115 |  |  |
| 29 | [29_USDCAD_sell_20170330_1015.png](29_USDCAD_sell_20170330_1015.png) | USDCAD `sell:1h:high:201703300200:1.33448` (FVG) | 2017-03-30 06:15 | sell | 1h 1.33448 |  |  |
| 30 | [30_GBPUSD_buy_20170405_0630.png](30_GBPUSD_buy_20170405_0630.png) | GBPUSD `buy:1h:low:201704041600:1.2423` (no FVG) | 2017-04-05 02:30 | buy | 1h 1.24230 |  |  |
| 31 | [31_EURUSD_buy_20170405_1800.png](31_EURUSD_buy_20170405_1800.png) | EURUSD `buy:4h:low:201704040900:1.06354` (FVG) | 2017-04-05 14:00 | buy | 4h 1.06354 |  |  |
| 32 | [32_GBPUSD_buy_20170419_0615.png](32_GBPUSD_buy_20170419_0615.png) | GBPUSD `buy:1h:low:201704190200:1.28173` (no FVG) | 2017-04-19 02:15 | buy | 1h 1.28173 |  |  |
| 33 | [33_EURUSD_sell_20170419_0730.png](33_EURUSD_sell_20170419_0730.png) | EURUSD `sell:pd:high:201704172100:1.07357` (FVG) | 2017-04-19 03:30 | sell | pd 1.07357 |  |  |
| 34 | [34_XAUUSD_buy_20170426_1730.png](34_XAUUSD_buy_20170426_1730.png) | XAUUSD `buy:4h:low:201704252100:1261.22` (FVG) | 2017-04-26 13:30 | buy | 4h 1261.22 |  |  |
| 35 | [35_GBPUSD_sell_20170509_0745.png](35_GBPUSD_sell_20170509_0745.png) | GBPUSD `sell:1h:high:201705090100:1.29555` (FVG) | 2017-05-09 03:45 | sell | 1h 1.29555 |  |  |
| 36 | [36_GBPUSD_sell_20170511_0615.png](36_GBPUSD_sell_20170511_0615.png) | GBPUSD `sell:1h:high:201705101900:1.2947` (FVG) | 2017-05-11 02:15 | sell | 1h 1.29470 |  |  |
| 37 | [37_XAUUSD_sell_20170628_1215.png](37_XAUUSD_sell_20170628_1215.png) | XAUUSD `sell:1h:high:201706280800:1254.41` (no FVG) | 2017-06-28 08:15 | sell | 1h 1254.41 |  |  |
| 38 | [38_GBPUSD_sell_20170724_1445.png](38_GBPUSD_sell_20170724_1445.png) | GBPUSD `sell:4h:high:201707190900:1.30523` (FVG) | 2017-07-24 10:45 | sell | 4h 1.30523 |  |  |
| 39 | [39_GBPUSD_buy_20170725_0945.png](39_GBPUSD_buy_20170725_0945.png) | GBPUSD `buy:1h:low:201707241600:1.3013` (FVG) | 2017-07-25 05:45 | buy | 1h 1.30130 |  |  |
| 40 | [40_USDCAD_buy_20170804_1230.png](40_USDCAD_buy_20170804_1230.png) | USDCAD `buy:1h:low:201708040700:1.25558` (no FVG) | 2017-08-04 08:30 | buy | 1h 1.25558 |  |  |
| 41 | [41_GBPUSD_sell_20170824_0730.png](41_GBPUSD_sell_20170824_0730.png) | GBPUSD `sell:1h:high:201708231900:1.28063` (no FVG) | 2017-08-24 03:30 | sell | 1h 1.28063 |  |  |
| 42 | [42_USDCAD_sell_20170825_1345.png](42_USDCAD_sell_20170825_1345.png) | USDCAD `sell:1h:high:201708242300:1.25346` (FVG) | 2017-08-25 09:45 | sell | 1h 1.25346 |  |  |
| 43 | [43_GBPUSD_buy_20170907_0630.png](43_GBPUSD_buy_20170907_0630.png) | GBPUSD `buy:1h:low:201709061900:1.30343` (FVG) | 2017-09-07 02:30 | buy | 1h 1.30343 |  |  |
| 44 | [44_EURUSD_sell_20171010_0615.png](44_EURUSD_sell_20171010_0615.png) | EURUSD `sell:4h:high:201710040900:1.17876` (FVG) | 2017-10-10 02:15 | sell | 4h 1.17876 |  |  |
| 45 | [45_GBPUSD_buy_20171016_0630.png](45_GBPUSD_buy_20171016_0630.png) | GBPUSD `buy:1h:low:201710152300:1.32729` (no FVG) | 2017-10-16 02:30 | buy | 1h 1.32729 |  |  |
| 46 | [46_GBPUSD_sell_20171018_0830.png](46_GBPUSD_sell_20171018_0830.png) | GBPUSD `sell:1h:high:201710180000:1.31976` (no FVG) | 2017-10-18 04:30 | sell | 1h 1.31976 |  |  |
| 47 | [47_USDJPY_sell_20171019_0615.png](47_USDJPY_sell_20171019_0615.png) | USDJPY `sell:1h:high:201710182200:113.092` (no FVG) | 2017-10-19 02:15 | sell | 1h 113.092 |  |  |
| 48 | [48_USDCAD_buy_20171025_1400.png](48_USDCAD_buy_20171025_1400.png) | USDCAD `buy:1h:low:201710241200:1.26385` (no FVG) | 2017-10-25 10:00 | buy | 1h 1.26385 |  |  |
| 49 | [49_USDJPY_buy_20171025_1615.png](49_USDJPY_buy_20171025_1615.png) | USDJPY `buy:1h:low:201710241900:113.539` (FVG) | 2017-10-25 12:15 | buy | 1h 113.539 |  |  |
| 50 | [50_USDCAD_sell_20171101_0700.png](50_USDCAD_sell_20171101_0700.png) | USDCAD `sell:1h:high:201711010200:1.29065` (FVG) | 2017-11-01 03:00 | sell | 1h 1.29065 |  |  |
