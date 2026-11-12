# Gold: value-area re-entry and accepted breakout (commercial track)

**Registered 2026-11-12, before any outcome of these rules was computed.** From a video Fadi
summarised (two setups on the previous day's volume profile); definitions proposed by Claude and
accepted by Fadi ("موافق على التعريفات، سجّل الحالتين وجرّبهن"). `GOLD_VP.md` (2026-11-08) traded
an immediate stop-entry break of VAH / VAL and was dropped; these setups differ: a re-entry to the
POC, and a break only after it holds.

Code: `app/research/gold_vp2.py`, `python -m app research gold-vp2 build --export <GOLD M1>`.
Report: `gold_vp2_result.md`.

## 1. The profile (previous trading day, 17:00-17:00 New York)

The day's range in 100 bins; each 5m bar spreads its weight over the bins its range touches; POC =
the heaviest bin's middle; the value area grows from the POC toward the heavier side until 70%
(as `GOLD_VP.md`). Two weights, two versions of every setup:

- **TPO:** every 5m bar weighs 1 (time at price; exact from our bars).
- **TICK:** each 5m bar's tick volume (a proxy; spot gold has no real volume).

## 2. The setups (15m bars, decided at a bar's close; entry at the next real 15m open)

**RE-ENTRY (to the POC).** After a 15m close outside the value area (above VAH or below VAL) during
the trading day, **two consecutive 15m closes inside it**. Trade back toward the POC: sell if it
was above, buy if below. Target = POC. Stop = the most extreme price reached since the first close
outside, + 0.1 x ATR(14, 15m) beyond it.

**ACCEPTED BREAK (to liquidity).** **Two consecutive 15m closes outside** the value area, the bar
before them having closed at or inside that edge. Trade with the break. Stop = 0.25 x ATR(14, 15m)
back inside the broken edge. Target = the nearest of: the previous day's high and low, the previous
week's high and low, and the live (unbroken, at most 5 days old) 1h swing highs and lows (3 bars
each side), beyond the entry; **it must be at least 1.5 R away**, else no trade.

**Common:** the signal bar opens 02:00-13:00 New York; the first signal of each setup per day;
target at least 3 x cost away; exit at the target, the stop (a bar reaching both: the stop; a gap
through it fills at the open) or the close of the last 15m bar ending by 16:45 New York. Cost:
the entry bar's spread + $0.07; $0.10 slip on stop exits.

Four cells: RE-ENTRY and ACCEPTED, each with TPO and TICK.

## 3. Control: a shifted value area

The same rules with the value area (VAH, VAL, POC) moved by u x (VAH − VAL), u uniform in
[−0.5, 0.5], the same u every day, 200 copies (seed 20261118); the liquidity targets stay. The
excess = mean net R (with slip) − the copies' mean, t from a 4-week block bootstrap.

## 4. Decision (as the commercial track)

1. On 2012-2021 a cell qualifies with mean net R with slip > 0, at least 60% of years positive, at
   least 300 trades and an excess over the shifted copies > 0; the best qualifying cell is chosen.
2. Net R with slip > 0 on 2022 to 2026-01-09.
3. Net R with slip > 0 on FxPro GOLD 2016-02 to 2026-11-05 (summary bars dropped).
4. Daily net R correlation with each of the five demo strategies < +0.2.

Passing all four leads to a registered test on the five FX pairs, then a demo shadow. The excess
t is reported against the research bar (about +0.17 R by chance as the best of about 75 looks).

Count: 4 cells in `TRIALS.md`.
