# Gold: do the breaks' bad runs persist? (commercial track)

**Registered 2026-11-08, before any outcome of these measures was computed** (Fadi: "Yes, run it").

## The question

Should the EA switch from the five break strategies to fading their breaks when breaks fail?

- **The fade's potential.** On 2026-10-21 to 2026-11-05 the breaks made −0.52 R a trade, while
  RECLAIM made +0.47.
- **The fade loses over time.** On FxPro 2016-2026, MIRROR made −0.10 R a trade and RECLAIM −0.07
  (`TRIALS.md`, 2026-11-08).
- **So a switch pays only if the bad runs can be seen early and then go on.** This test measures
  that. It trades nothing.

Code: `app/research/gold_regime.py`, run with `python -m app research gold-regime --export <GOLD M1
export>`. Report: `gold_regime_report.md`.

## 1. Trades

The trades are as `GOLD_SHADOW.md`:

- the five break strategies (LVL4H, PIVOT, PIVW, ASIA, PWHL);
- RECLAIM, the fade of the same levels: the first close back inside within 6 bars of the break,
  with the SL beyond the break's extreme + 0.1 × ATR(5m), a 1.5 R target and a cost cap of
  0.10;
- net R with slippage.

They are run on two feeds:

- **FxPro GOLD, 2016-02 to 2026-11-05.** This is the primary feed.
- **XAUUSD, 2012 to 2026-01-09.** This is the second feed.

## 2. Two detectors

Each uses only what is known when a trade enters.

- **PERF.** The mean net R of the last N break trades closed before the entry (all five
  together).
  - The regime is BAD when the mean is below −0.10.
  - N = 20, 30 or 50.
- **FALSE.** The false-break rate of the previous 20 trading days.
  - Per day: of the first breaks of PDH and PDL inside 02:00-16:00 New York, the share whose day
    closed back inside the level.
  - The regime is BAD when the rate is above its 75th percentile over all earlier days.

## 3. Measures, per detector and feed

1. The break trades' mean net R when the regime is BAD, and when it is GOOD.
2. RECLAIM's mean net R when the regime is BAD.
3. Three portfolios, each with its mean net R, sum and largest drawdown in R:
   - **ALWAYS:** the breaks every time;
   - **PAUSE:** the breaks only when GOOD;
   - **SWITCH:** the breaks when GOOD and RECLAIM when BAD.

## 4. Decision

A switch is worth building, as a shadow on the demo, only if on FxPro both of these hold for one
detector and setting:

1. **The bad runs persist.** The break trades' mean net R in BAD is below 0, with a t of −2 or
   lower.
2. **PAUSE or SWITCH beats ALWAYS.** Its sum is higher and its largest drawdown lower.

The same signs must hold on XAUUSD. Both feeds are seen data, so even a pass decides only what
the demo tests.

There are 4 detector settings (PERF 20, 30, 50; FALSE), logged in `docs/phase3/TRIALS.md`.

## 5. Outcome (2026-11-08): the bad runs do not persist, so no switch

`gold_regime_report.md`. **No detector passes.**

- **After a BAD signal, the breaks were not worse.**
  - FxPro: +0.003 to +0.023 R a trade in BAD, against +0.027 to +0.038 in GOOD. The t-values
    are +0.1 to +1.1.
  - XAUUSD: +0.019 to +0.071 in BAD. PERF 20's +0.071 had t = +3.0, so it was even better than
    in GOOD.
  - A run of losing breaks, once it can be seen, is about over.
- **RECLAIM lost in BAD:** −0.02 to −0.11 R a trade on both feeds.
- **SWITCH was below ALWAYS for every detector:** on FxPro its sum was 11 to 150 R against 189.
- **PAUSE kept less, mostly.**
  - FALSE's PAUSE came closest: FxPro sum 184 against 189 R, drawdown 93 against 129 R. XAUUSD
    sum 373 against 406, drawdown 63 against 67.
  - Its sum is below ALWAYS, so condition 2 fails. Choosing it now would be choosing after the
    look.

**What this means for the stop rules (`GOLD_V1.md`).**

- Stop rule 2 is a PERF detector. The data says stopping after a bad run costs, on average, the
  recovery that follows.
- The stop rules stay. They guard against a lasting change that the past cannot show, not a
  timing tool. That cost is known.
