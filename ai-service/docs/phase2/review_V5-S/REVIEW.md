# P2 detector review: XAUUSD (V5-S)

Sample: 50 of 145 patterns of the development period (2012-2017), spread evenly over years and
directions, seed 731205 (fixed before the charts were drawn). Each chart ends two bars after the
CHoCH. Times are New York.

A pattern is **valid** (`yes`) when all of these hold on the chart:

1. **Liquidity.** The dashed line is a real resting level: a clear swing high/low on its timeframe
   or the previous trading day's high/low, still untaken when it was swept.
2. **Sweep.** Price trades through it and closes back on that bar or the next; the move looks like a
   grab of the liquidity, not a breakout that happens to close back.
3. **CHoCH.** The close (blue marker) breaks the swing (dotted line) that structurally matters for
   the move into the sweep.
4. **FVG.** The shaded gap is an imbalance left by the displacement away from the sweep.

Write `yes` or `no` in **Valid**; for a `no`, say in **Notes** which point fails. The written
conditions themselves are already checked by the tests; this review asks whether the result is a
genuine trading pattern.

**Reviewer: Fadi (human), 2026-10-22.** Result: 46 yes, 4 no; precision 92% (Wilson 95% 81-97%);
gate passed (`score.json`).

Agreement with Claude's v1 verdicts on the 15 patterns that are in both samples: 12 of 15. Fadi
rejected two Claude had accepted (#14 = v1 #15, #22 = v1 #20, both on the FVG link) and accepted
one Claude had rejected (#33 = v1 #33, the holiday-week spike).

| # | Chart | Pattern | Sweep (NY) | Direction | Level | Valid | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | [01_buy_20120123_1400.png](01_buy_20120123_1400.png) | `buy:1h:low:201201230700:1666.57` | 2012-01-23 09:00 | buy | 1h 1666.57 | yes |  |
| 2 | [02_buy_20120215_1900.png](02_buy_20120215_1900.png) | `buy:1h:low:201202151300:1723.75` | 2012-02-15 14:00 | buy | 1h 1723.75 | yes |  |
| 3 | [03_buy_20120618_1400.png](03_buy_20120618_1400.png) | `buy:1h:low:201206180800:1616.71` | 2012-06-18 10:00 | buy | 1h 1616.71 | yes |  |
| 4 | [04_sell_20120709_0700.png](04_sell_20120709_0700.png) | `sell:1h:high:201207090100:1583.5` | 2012-07-09 03:00 | sell | 1h 1583.50 |yes  |  |
| 5 | [05_sell_20120802_0945.png](05_sell_20120802_0945.png) | `sell:1h:high:201208011700:1605.8` | 2012-08-02 05:45 | sell | 1h 1605.80 | yes |  |
| 6 | [06_buy_20120920_0700.png](06_buy_20120920_0700.png) | `buy:1h:low:201209181600:1759.98` | 2012-09-20 03:00 | buy | 1h 1759.98 | no | CHoCH is not sufficiently clear. The chart shows a strong preceding bearish move, but the required bullish structural break and its relationship to the sweep are not convincingly established. |
| 7 | [07_buy_20121010_0615.png](07_buy_20121010_0615.png) | `buy:1h:low:201210100100:1760.52` | 2012-10-10 02:15 | buy | 1h 1760.52 | yes |  |
| 8 | [08_sell_20121022_1115.png](08_sell_20121022_1115.png) | `sell:1h:high:201210220400:1726.94` | 2012-10-22 07:15 | sell | 1h 1726.94 | yes |  |
| 9 | [09_sell_20121029_0600.png](09_sell_20121029_0600.png) | `sell:1h:high:201210290000:1716.09` | 2012-10-29 02:00 | sell | 1h 1716.09 | yes |  |
| 10 | [10_sell_20130118_1345.png](10_sell_20130118_1345.png) | `sell:1h:high:201301180700:1693.48` | 2013-01-18 08:45 | sell | 1h 1693.48 | yes |  |
| 11 | [11_sell_20130305_1330.png](11_sell_20130305_1330.png) | `sell:pd:high:201303032200:1584.89` | 2013-03-05 08:30 | sell | pd 1584.89 | yes |  |
| 12 | [12_buy_20130308_1330.png](12_buy_20130308_1330.png) | `buy:4h:low:201303010600:1564.81` | 2013-03-08 08:30 | buy | 4h 1564.81 | yes |  |
| 13 | [13_sell_20130429_1115.png](13_sell_20130429_1115.png) | `sell:1h:high:201304290700:1476.96` | 2013-04-29 07:15 | sell | 1h 1476.96 | yes |  |
| 14 | [14_buy_20130816_0930.png](14_buy_20130816_0930.png) | `buy:1h:low:201308152300:1360.66` | 2013-08-16 05:30 | buy | 1h 1360.66 | no | FVG linkage is questionable. The shaded zone is very small (0.12 ATR), and the chart does not clearly establish that it was created by the displacement confirming the bullish CHoCH. |
| 15 | [15_buy_20130830_1330.png](15_buy_20130830_1330.png) | `buy:1h:low:201308300900:1392.65` | 2013-08-30 09:30 | buy | 1h 1392.65 | no | The sequence is not sufficiently clear. The chart shows a low sweep and subsequent recovery, but the relationship between the structural break and the shaded FVG is not convincingly established. |
| 16 | [16_sell_20131004_1230.png](16_sell_20131004_1230.png) | `sell:4h:high:201310021300:1323.88` | 2013-10-04 08:30 | sell | 4h 1323.88 | yes |  |
| 17 | [17_buy_20131028_0745.png](17_buy_20131028_0745.png) | `buy:1h:low:201310280100:1347.6` | 2013-10-28 03:45 | buy | 1h 1347.60 | yes |  |
| 18 | [18_buy_20140108_1915.png](18_buy_20140108_1915.png) | `buy:1h:low:201401081400:1219.16` | 2014-01-08 14:15 | buy | 1h 1219.16 | yes |  |
| 19 | [19_sell_20140114_1530.png](19_sell_20140114_1530.png) | `sell:4h:high:201401131800:1254.99` | 2014-01-14 10:30 | sell | 4h 1254.99 | yes |  |
| 20 | [20_sell_20140407_1445.png](20_sell_20140407_1445.png) | `sell:1h:high:201404071000:1301.5` | 2014-04-07 10:45 | sell | 1h 1301.50 | yes |  |
| 21 | [21_buy_20140509_0900.png](21_buy_20140509_0900.png) | `buy:1h:low:201405090100:1288.3` | 2014-05-09 05:00 | buy | 1h 1288.30 | yes |  |
| 22 | [22_buy_20140521_1800.png](22_buy_20140521_1800.png) | `buy:4h:low:201405200900:1285.83` | 2014-05-21 14:00 | buy | 4h 1285.83 | no | The FVG-to-sweep relationship is questionable. The sweep is a deep wick below the 4H level, but the chart does not clearly establish that the shaded zone is the imbalance left by the qualifying displacement away from that sweep. |
| 23 | [23_buy_20140617_1230.png](23_buy_20140617_1230.png) | `buy:pd:low:201406112100:1259.8` | 2014-06-17 08:30 | buy | pd 1259.80 | yes |  |
| 24 | [24_sell_20140618_1215.png](24_sell_20140618_1215.png) | `sell:pd:high:201406162100:1273.2` | 2014-06-18 08:15 | sell | pd 1273.20 | yes |  |
| 25 | [25_sell_20140916_1015.png](25_sell_20140916_1015.png) | `sell:pd:high:201409112100:1241.45` | 2014-09-16 06:15 | sell | pd 1241.45 | yes |  |
| 26 | [26_sell_20150121_1300.png](26_sell_20150121_1300.png) | `sell:1h:high:201501210600:1303.31` | 2015-01-21 08:00 | sell | 1h 1303.31 | yes |  |
| 27 | [27_sell_20150305_1530.png](27_sell_20150305_1530.png) | `sell:pd:high:201503032200:1209.01` | 2015-03-05 10:30 | sell | pd 1209.01 | yes |  |
| 28 | [28_sell_20150626_0830.png](28_sell_20150626_0830.png) | `sell:4h:high:201506250100:1178.05` | 2015-06-26 04:30 | sell | 4h 1178.05 | yes |  |
| 29 | [29_buy_20150807_1230.png](29_buy_20150807_1230.png) | `buy:pd:low:201508052100:1083.46` | 2015-08-07 08:30 | buy | pd 1083.46 | yes |  |
| 30 | [30_buy_20150828_1130.png](30_buy_20150828_1130.png) | `buy:1h:low:201508280100:1124.35` | 2015-08-28 07:30 | buy | 1h 1124.35 | yes |  |
| 31 | [31_buy_20151008_0615.png](31_buy_20151008_0615.png) | `buy:1h:low:201510080100:1141.56` | 2015-10-08 02:15 | buy | 1h 1141.56 | yes |  |
| 32 | [32_buy_20151013_1100.png](32_buy_20151013_1100.png) | `buy:1h:low:201510130200:1152.98` | 2015-10-13 07:00 | buy | 1h 1152.98 | yes |  |
| 33 | [33_sell_20151229_1000.png](33_sell_20151229_1000.png) | `sell:1h:high:201512290600:1074.19` | 2015-12-29 05:00 | sell | 1h 1074.19 | yes |  |
| 34 | [34_sell_20160225_1745.png](34_sell_20160225_1745.png) | `sell:1h:high:201602250700:1242.31` | 2016-02-25 12:45 | sell | 1h 1242.31 | yes |  |
| 35 | [35_sell_20160316_0700.png](35_sell_20160316_0700.png) | `sell:1h:high:201603160000:1234.93` | 2016-03-16 03:00 | sell | 1h 1234.93 | yes |  |
| 36 | [36_sell_20160427_1245.png](36_sell_20160427_1245.png) | `sell:1h:high:201604220800:1250.66` | 2016-04-27 08:45 | sell | 1h 1250.66 | yes |  |
| 37 | [37_buy_20160725_1330.png](37_buy_20160725_1330.png) | `buy:1h:low:201607250100:1313.46` | 2016-07-25 09:30 | buy | 1h 1313.46 | yes |  |
| 38 | [38_buy_20160907_1200.png](38_buy_20160907_1200.png) | `buy:1h:low:201609070800:1347.04` | 2016-09-07 08:00 | buy | 1h 1347.04 | yes |  |
| 39 | [39_sell_20160915_1230.png](39_sell_20160915_1230.png) | `sell:4h:high:201609141300:1325.85` | 2016-09-15 08:30 | sell | 4h 1325.85 | yes |  |
| 40 | [40_buy_20161214_1315.png](40_buy_20161214_1315.png) | `buy:1h:low:201612140500:1159.45` | 2016-12-14 08:15 | buy | 1h 1159.45 | yes |  |
| 41 | [41_buy_20161222_1345.png](41_buy_20161222_1345.png) | `buy:1h:low:201612220600:1128.23` | 2016-12-22 08:45 | buy | 1h 1128.23 | yes |  |
| 42 | [42_buy_20170301_1400.png](42_buy_20170301_1400.png) | `buy:1h:low:201702231200:1237.11` | 2017-03-01 09:00 | buy | 1h 1237.11 | yes |  |
| 43 | [43_sell_20170314_1200.png](43_sell_20170314_1200.png) | `sell:1h:high:201703131500:1206.44` | 2017-03-14 08:00 | sell | 1h 1206.44 | yes |  |
| 44 | [44_buy_20170509_0615.png](44_buy_20170509_0615.png) | `buy:4h:low:201705072100:1224.98` | 2017-05-09 02:15 | buy | 4h 1224.98 | yes |  |
| 45 | [45_sell_20170620_1215.png](45_sell_20170620_1215.png) | `sell:1h:high:201706200700:1247.6` | 2017-06-20 08:15 | sell | 1h 1247.60 | yes |  |
| 46 | [46_buy_20170802_1245.png](46_buy_20170802_1245.png) | `buy:1h:low:201708020400:1264.09` | 2017-08-02 08:45 | buy | 1h 1264.09 | yes |  |
| 47 | [47_buy_20170816_1300.png](47_buy_20170816_1300.png) | `buy:1h:low:201708160700:1269.21` | 2017-08-16 09:00 | buy | 1h 1269.21 | yes |  |
| 48 | [48_buy_20170929_0600.png](48_buy_20170929_0600.png) | `buy:1h:low:201709290200:1283.77` | 2017-09-29 02:00 | buy | 1h 1283.77 | yes |  |
| 49 | [49_sell_20171013_0630.png](49_sell_20171013_0630.png) | `sell:4h:high:201710120500:1297.39` | 2017-10-13 02:30 | sell | 4h 1297.39 | yes |  |
| 50 | [50_sell_20171109_2000.png](50_sell_20171109_2000.png) | `sell:1h:high:201711091100:1288.1` | 2017-11-09 15:00 | sell | 1h 1288.10 | yes |  |
