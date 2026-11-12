# Gold: Heikin-Ashi colour flips on 15m (commercial track)

**Registered 2026-11-12, before any outcome of these rules was computed.** Fadi's idea, from a
trader who buys on a green Heikin-Ashi (HA) candle and sells on a red one. Fadi's choices: the 15m
frame; exit when the colour changes ("الفريم 15 دقيقة، والخروج لما يتغيّر اللون").

Code: `app/research/gold_ha.py`, `python -m app research gold-ha build --export <GOLD M1>`.
Report: `gold_ha_result.md`.

## 1. Rules

- HA on closed 15m bars: HA close = (O + H + L + C) / 4; HA open = (previous HA open + previous HA
  close) / 2 (the first: (O + C) / 2). Green: HA close > HA open; red: below.
- **A flip** is a closed HA candle whose colour differs from the previous one's. Green: buy; red:
  sell. **Entry at the next real 15m bar's open** (the price one can trade).
- **Exit** at the real open of the bar after the next flip, and the opposite trade opens there
  (stop and reverse). No stop and no target (Fadi).
- **Two cells:**
  - **H24:** always in the market, except a forced exit at the last bar closing by 16:45 New York
    on Friday; after the weekend, the first flip opens again.
  - **DAY:** as H24 but every trade closes at the last bar closing by 16:45 New York each day; no
    entry from 16:45 to 18:00 New York; after the reopen, the first flip opens again.
- Cost per trade: the entry bar's spread + $0.07 commission; at 2x as well. **Swap is not charged**
  (H24 holds over the daily rollover; this favours H24 and is stated with its result).
- **R** = ATR(14, 15m) at the signal bar (no stop exists; R is the scale).

## 2. Controls and the HA-price artefact

- **E0:** the same trades with a random side (seed 20261117, 50 runs): the colour's information
  beyond the trade timing.
- **Reported, not a trial: fills at HA prices.** The same trades entered and exited at the next HA
  candle's open (what a backtest on an HA chart does) to show how much an unreal fill adds.
- **Reported, deciding nothing:** the same rules on 1h, 4h and D1 (H24).

## 3. Decision (as the commercial track's conditions)

1. On 2012-2021 the better cell has mean net R > 0, at least 60% of years positive, > 0 at 2x
   cost, and beats E0 with a 4-week block bootstrap t >= 3 (Holm over the 2 cells).
2. Net R > 0 on 2022 to 2026-01-09.
3. Net R > 0 on FxPro GOLD 2016-02 to 2026-11-05 (summary bars dropped).
4. Daily net R correlation with each of the five demo strategies < +0.2.

Count: 2 cells in `TRIALS.md` (the artefact and the other frames are logged as descriptive).
