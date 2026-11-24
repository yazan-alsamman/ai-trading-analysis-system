# P2 detector review: Claude's pre-review (XAUUSD, 2026-10-22)

**This is not the gate.** The P2 gate is Fadi's review in `REVIEW.md`. This file is a second
opinion, written first at Fadi's request, from the same 50 charts and the same four criteria. It
was done by looking at the chart images, so prices are read off the axes (about ±0.1). Reading it
before reviewing can anchor the judgement, so it is worth forming an opinion on each chart first.

Verdicts: **yes** (all four criteria hold), **borderline** (the rules are met and the shape is
there, but the pattern has little significance: a thin market, tiny moves, or a structure point
that is noise), **no** (a criterion clearly fails). No chart got a plain **no**.

## Summary

| Verdict | Count | Charts |
| --- | --- | --- |
| yes | 43 | all others |
| borderline | 7 | 12, 17, 28, 33, 44, 45, 49 |
| no | 0 | none |

Precision if borderline counts as yes: 50/50. If borderline counts as no: 43/50 = 86% (Wilson 95%
interval 74-93%), below the 90% gate. So **the gate depends on how the borderline cases are
judged**, and they share one cause (below).

## What the borderline cases have in common

1. **Thin sessions.** Six of the seven are in low-liquidity hours: after the New York close or in
   early Asia (#12 19:00, #28 21:30, #45 18:15, #49 20:30 New York), a US holiday (#44 Memorial Day
   2017, 00:15) or the holiday weeks (#33 2015-12-29). The sweep, the CHoCH and the FVG are there,
   but the whole move is $1-3 and the swing the CHoCH breaks is noise rather than structure.
   **Suggestion for P3:** the session of the sweep as a feature (planned in L4) and, if the
   development data support it, a session filter (London and New York only) decided on 2012-2017
   and then frozen.
2. **Gold's daily reopen.** In #45 the CHoCH reference is the low of the 18:00 New York bar, the
   first bar after the 17:00-18:00 daily break (1225.28), and the sweep bar right after it spans
   $3.5. Bars around the reopen are often spikes on thin liquidity (the data-quality report also
   counts 939 bars inside the configured break). **Suggestion:** treat the daily break as a break
   in the data, as the FVG rule already does for holes, and test on 2012-2017 whether the first
   bars after the reopen should be allowed to form swings. (Corrected after checking the data:
   the first version of this file read the reference as 17:30 from the chart.)
3. **A one-bar spike.** #33 is a single 15-minute spike of about $4 and straight back in a holiday
   week; it is a valid sweep by the rules but hard to call a liquidity grab.

## Weaker "yes" cases (worth a look)

- **Tiny FVG at the threshold:** #6 (0.11 ATR), #13 (0.10). The 0.1 ATR minimum lets through gaps
  that are barely visible; a minimum of about 0.2 ATR would drop them (to decide on 2012-2017).
- **FVG left by chop, not the displacement:** #8, #21. The CHoCH comes from one late bar and the gap
  sits in the back-and-forth before it.
- **News spikes:** #10 (ECB, 2013-02-07), #20 (FOMC minutes, 2014-05-21), #41 (US election day),
  #46 (jobs report, 2017-11-03). Valid patterns; the news-window filter of the design (±30 min of a
  high-impact release) would decide whether to trade them.
- **Thin holiday market:** #25 (2014-12-30). Same cause as point 1, but the structure is clearer.

## Limits of this review

- **Level origin not on the chart** for 4h and previous-day levels whose extreme is older than the
  40 bars shown (#3, #6, #10, #14, #17, #23, #26, #29, #30, #31, #36, #38, #41, #43, #45, #46,
  #48). Criterion 1 could only be checked from the label, not seen. **Suggestion for the tool:**
  mark the level's origin time in the label, or widen the window to include it.
- Each chart ends two bars after the CHoCH, as designed; the outcome was not considered.

## Per chart

| # | Verdict | Notes |
| --- | --- | --- |
| 1 | yes | Equal lows ~1666.6 swept at 09:00, close back; CHoCH breaks the 08:00 high 1676.6; FVG in the rally. |
| 2 | yes | Low 1705.7 swept deep (1.27 ATR) and closed back; retest holds above the extreme; strong displacement. |
| 3 | yes | 4h level (origin off chart), three levels taken; CHoCH above 1717; small FVG. |
| 4 | yes | High 1680.6 from the overnight session swept at 09:15; clean break of the 07:45 low; clear FVG. |
| 5 | yes | High 1676.8 swept at 03:00, closed back on the next bar; CHoCH below 1673.3. |
| 6 | yes | 4h high swept after a rally; closed back next bar; CHoCH far below (1560.8). FVG tiny (0.11 ATR). |
| 7 | yes | Previous-day low swept at 06:30, closed back next bar; textbook displacement and FVG. |
| 8 | yes | Equal highs 1726.9 swept; but the drop is choppy and the FVG sits in the chop (weak displacement). |
| 9 | yes | High 1693.5 swept at 08:45 with a long wick; CHoCH below 1688.4; small FVG. |
| 10 | yes | 4h low swept by a news spike (ECB) and recovered next bar; strong reversal; FVG clear. |
| 11 | yes | Low 1587.9 swept at 10:00, closed back next bar; very strong displacement. |
| 12 | borderline | High 1582.1 taken by cents at 19:00 New York; whole move about $1.5 in a thin evening market; CHoCH swing is noise. |
| 13 | yes | Double low 1386.2 swept at 21:00, strong move up; FVG at the 0.10 minimum. |
| 14 | yes | 1h high (origin off chart) swept at 01:30; clean CHoCH and FVG. |
| 15 | yes | Low 1360.7 swept deep at 05:30 with a long wick; CHoCH above 1364.8; small FVG. |
| 16 | yes | Previous-day high swept at the London open (depth 0.10 ATR); clear displacement down. |
| 17 | borderline | 4h high taken by 0.11 ATR at 15:30 in a slow afternoon grind; CHoCH swing 1252.4 is minor. |
| 18 | yes | Next day, same zone: highs swept at 10:30 (four levels) and a sharp drop; textbook. |
| 19 | yes | Low 1291.0 swept at the London open; small range but clear structure. |
| 20 | yes | 4h low swept by the FOMC-minutes spike at 14:00 and closed back; CHoCH above 1290.8. |
| 21 | yes | High 1326.0 swept, closed back next bar; CHoCH from one late bar; FVG in the chop before it. |
| 22 | yes | High 1338.7 swept at 08:15; clean break of the 06:45 low. |
| 23 | yes | 4h low swept on the second bar (wick 1291.6) and recovered; CHoCH above 1294.6. |
| 24 | yes | Low 1202.4 swept at 06:00; retest holds; CHoCH at the end of the window. |
| 25 | yes | High 1189.6 swept at 03:15 in the holiday week; structure fine but small. |
| 26 | yes | 4h low swept at 07:30, closed back; CHoCH above 1223.6. |
| 27 | yes | Previous-day high swept at 10:30 after a rally; clear displacement and FVG. |
| 28 | borderline | High 1184.8 taken at 21:30 (after the New York close), closed back next bar; tiny move, thin market. |
| 29 | yes | 4h high swept at 04:30 after a stop run down at 03:00; clean CHoCH and a large FVG. |
| 30 | yes | 1h low (origin off chart) swept at 07:30 and closed back; CHoCH above 1128.2. |
| 31 | yes | 4h low swept with a long wick at 06:45; CHoCH above 1106.4. |
| 32 | yes | Low 1153.0 swept, closed back next bar; CHoCH above 1155.8. |
| 33 | borderline | One 15-minute spike of about $4 above the high and straight back, holiday week; the CHoCH reference is a long wick. |
| 34 | yes | Swing high 1129.0 swept at 01:00 New York; clean break of 1126.5. |
| 35 | yes | Low 1253.1 swept by 0.11 ATR at 01:00; clear move up. |
| 36 | yes | Rally into the 1h high, swept at 08:45 and rejected; clean CHoCH. |
| 37 | yes | Low swept by 0.13 ATR at 07:30; steady move up to the CHoCH. |
| 38 | yes | Low swept at 09:30, closed back next bar; large FVG (2.2 ATR) in the displacement. |
| 39 | yes | High 1327.8 swept at 08:45; strong drop through 1322.2. |
| 40 | yes | Low 1262.5 swept at 07:45 (wick), strong displacement up. |
| 41 | yes | US election day: high swept at 10:30 with a long wick, sharp drop. |
| 42 | yes | Equal lows 1210.4 swept at 09:30, closed back next bar; clean CHoCH. |
| 43 | yes | Low swept by 0.14 ATR at 09:00 after a sharp drop; recovery breaks 1243.2. |
| 44 | borderline | Memorial Day, 00:15 New York: low swept by cents, whole move about $1.5; thin holiday market. |
| 45 | borderline | 4h high swept at 18:15, right after gold's daily reopen; the CHoCH reference is the 18:00 reopen bar's low (1225.28). |
| 46 | yes | Jobs-report spike sweeps the high at 08:30 and fails; strong drop. |
| 47 | yes | High 1288.1 swept at 15:00; gradual drop through 1285.6; small FVG. |
| 48 | yes | 4h low swept at the London open on Monday after the weekend gap; CHoCH above 1274.9. |
| 49 | borderline | Low 1260.5 taken at 20:30 New York, closed back next bar; range about $1.5, evening session. |
| 50 | yes | High 1264.9 swept at 07:15; clean break of 1262.6. |

## Appendix: the seven borderline cases checked against the data (2026-10-22)

Every rule holds exactly for all seven: the sweep extreme is beyond the level and a close comes
back on the same or the next bar; the CHoCH reference swing (k = 2) was confirmed by the time of
the sweep; the CHoCH close is beyond it with no new extreme in between; the FVG is three
consecutive bars with a real gap, between the extreme and the CHoCH. So *borderline* is about the
significance of the pattern (thin sessions), not about the rules. Times New York.

| # | Level | Sweep bar (extreme, close) | Settled | CHoCH reference | CHoCH close | FVG (bars, gap) |
| --- | --- | --- | --- | --- | --- | --- |
| 12 sell | 1h 1582.14 | 03-11 19:00 (1582.40, 1581.91) | same bar | 16:45, 1580.95 | 20:30, 1580.90 | 19:45-20:15, 1581.52-1581.88 |
| 17 sell | 4h 1254.82 | 01-13 15:30 (1254.99, 1254.88) | 15:45, 1254.80 | 15:15, 1252.36 | 18:00, 1251.66 | 15:45-16:15, 1253.57-1254.43 |
| 28 sell | 1h 1184.80 | 04-30 21:30 (1185.13, 1184.86) | 21:45, 1183.32 | 20:30, 1182.86 | 22:00, 1182.81 | 21:30-22:00, 1183.72-1184.53 |
| 33 sell | 1h 1074.19 | 12-29 05:00 (1075.17, 1075.00) | 05:15, 1070.69 | 04:45, 1069.23 | 06:45, 1069.21 | 05:00-05:30, 1070.72-1070.94 |
| 44 buy | 1h 1265.68 | 05-29 00:15 (1265.32, 1265.60) | 00:30, 1265.87 | 05-28 23:30, 1266.75 | 02:30, 1267.13 | 01:45-02:15, 1266.06-1266.21 |
| 45 sell | 4h 1228.76 | 07-05 18:15 (1229.09, 1228.73) | same bar | 18:00, 1225.28 | 20:00, 1225.15 | 19:30-20:00, 1226.56-1227.10 |
| 49 buy | 1h 1260.46 | 12-18 20:30 (1260.11, 1260.31) | 20:45, 1260.50 | 20:00, 1261.30 | 21:45, 1261.41 | 21:15-21:45, 1260.61-1260.69 |

Entries are not part of this review: the detector (P2) finds patterns; the entry (a limit at the
FVG's near edge), the fill and the outcome are the setup builder's (P3), and the charts stop two
bars after the CHoCH on purpose.
