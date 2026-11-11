# Gold: what the five strategies' losing trades share (commercial track)

**Registered 2026-11-10, before any outcome of this study was computed.** Fadi's idea (chat,
2026-11-10): take every losing trade of the five demo strategies and look for what they have in
common, to remove them with a filter or to find a new strategy in them.

Code: `app/research/gold_loss.py`, `python -m app research gold-loss build --export <GOLD M1>`.

## 1. Trades and features

The five's own trades (one at a time, M8, as the EA). Each feature is known at the entry bar:

| # | Feature | Buckets |
| --- | --- | --- |
| 1 | strategy | the five |
| 2 | level kind | PDH, PDL, 5DH, 5DL, R1, S1, ASH, ASL, PWH, PWL |
| 3 | side | buy, sell |
| 4 | New York time | 02-05, 05-08, 08-10, 10-12, 12-16 |
| 5 | weekday | Monday to Friday |
| 6 | US data minute | the entry bar opens 08:25-08:35 or 09:55-10:05 New York, or not |
| 7 | fill | stop (at the level) or market (price already through) |
| 8 | D against the day | D / ATR(14, D1), quintiles (2012-2021 edges) |
| 9 | volatility regime | ATR(14, D1) against its last 250 days, quintiles |
| 10 | move done today | abs(close − day open) / ATR(14, D1) at entry, quintiles |
| 11 | with the day | the trade's side agrees with the day's move so far, or not |
| 12 | 1h + 4h structure | both with the trade, both against, or mixed (`gold_pbk.structure`) |
| 13 | the bar before the entry | its range / ATR(14, 5m), quintiles (the entry bar's own range is not known at the fill) |
| 14 | yesterday's range | the previous day's range / ATR(14, D1), quintiles |
| 15 | earlier trades today | trades of the five already open or closed today: 0, 1, 2+ |
| 16 | cost | cost R, quintiles |

## 2. The screen (2012-2021 only)

- For each bucket with at least 5% of the trades: the trades' mean net R with slip, its share of
  losers, and the t of its mean against the others' (Welch).
- **The filter:** remove the bucket that raises the mean net R of the rest the most; then, once
  more, a second bucket. Up to two buckets, chosen on 2012-2021.
- **The bar (50 shuffles):** the same two-step search on 2012-2021 with the net R shuffled across
  the trades. The real gain must beat the 95th percentile of the shuffled gains.

## 3. Decision

The filter is adopted (as a shadow version, beside v1) only if all hold:

1. Its gain on 2012-2021 beats the shuffled 95th percentile.
2. On the check (XAUUSD 2022 to 2026-01-09) the filtered mean net R with slip is above the
   unfiltered one.
3. The same on FxPro's GOLD feed, 2016-02 to the export's end.
4. It keeps at least 60% of the trades.

**A strategy from the losers (decides nothing here):** a bucket whose mean net R is below −0.10 on
2012-2021 *and* on the check is listed as a candidate for its own registered test (trading it
the other way). Nothing is traded from it in this study.

## 4. Count

One filter search (16 features), logged in `docs/phase3/TRIALS.md` as an exploratory look of the
commercial track.

**Correction (2026-11-10, after a first run):** the first run's search checked only the size of
the removed bucket, so it removed "fill = stop" (99.5% of the trades) and kept 19. The search now
skips any removal that would keep under 60% of the trades (condition 4, applied inside the
search, and to the shuffles alike). Nothing else changed; the first run is not used.

## 5. Outcome (2026-11-10): the four conditions are met, but the filter looks like noise

`gold_loss_xauusd.md`. Removed: **yesterday's range / ATR(14, D1) in (0.904, 1.151]** (its 4th
quintile on 2012-2021) and **cost R in (0.055, 0.146]** (4th quintile).

| Net R with slip | All | Kept | Removed |
| --- | --- | --- | --- |
| XAUUSD 2012-2021 | +0.034 (4,041) | +0.113 (2,610) | −0.109 (1,431) |
| XAUUSD check | +0.062 (4,148) | +0.069 (3,131) | +0.042 (1,017) |
| FxPro 2016-02 to 2026-11-05 | +0.025 (7,252) | +0.041 (4,855) | −0.008 (2,397) |
| FxPro 2026 | +0.054 (756) | +0.004 (605) | +0.253 (151) |

- Conditions 1-4 hold: the gain on 2012-2021 (+0.079) beats the shuffled 95th percentile
  (+0.064), the kept trades beat all on the check and on FxPro, and 65% are kept.
- **But the reading is weak:**
  - The gain on the check is +0.007 R a trade; on FxPro +0.016.
  - The removed buckets are not ends of a trend. Yesterday's range by quintile on 2012-2021:
    +0.19, −0.06, +0.20, −0.14, −0.02; on the check +0.02, +0.14, +0.05, +0.04, +0.05. Cost R:
    +0.08, +0.02, +0.11, −0.08, +0.04. A middle quintile that is bad in one period and fine in the
    next is what noise looks like.
  - In 2026 the removed trades did best (+0.253 on 151).
  - The search was corrected once after its first run (above).
- No bucket is below −0.10 on both periods, so the losers give no strategy of their own.

**What follows:** by §3 the filter would run as a shadow version. It needs no EA change: the
demo's own trades can be split by the two features in Python, so it is tracked on paper beside
v1, and v1 is not changed.
