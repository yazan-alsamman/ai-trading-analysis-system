# P3 trials log (rules-only performance, development period)

Every run that measured rules-only performance (E1 / E1s / E0) on 2012-2017 is listed here, so the
number of trials is known when results are corrected for multiple testing (Deflated Sharpe) and
reported in the thesis. A trial is one configuration whose performance was looked at; re-running
the same configuration (same code, seed and data) is not a new trial.

Earlier looks at performance on the development period, before this log: the XAUUSD labels of
P3 task 2 (`labels_XAUUSD_v1.md`, `labels_XAUUSD_V5-S.md`): 2 trials.

| # | Date | Configuration (all else as `strategy.toml`) | Report | E1 (L1) net R, all | E0 | E1 - E0 (95%) | p | E1 XAUUSD | Asked by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3 | 2026-10-22 | Horizon 48 bars (12 h), the registered value | `baselines.md` | -0.046 | -0.063 | +0.017 (-0.095 to +0.125) | 0.36 | -0.072 | P3 task 4 |
| 4 | 2026-10-23 | Horizon 96 bars (24 h) | `baselines_h96.md` | -0.066 | -0.069 | +0.003 (-0.123 to +0.124) | 0.46 | -0.063 | Fadi |
| 5 | 2026-10-23 | Horizon 192 bars (48 h) | `baselines_h192.md` | -0.100 | -0.083 | -0.017 (-0.154 to +0.116) | 0.60 | -0.180 | Fadi |
| 6 | 2026-10-23 | **L1-M**: L1 with signal-based position management (opposite signal exits, same-direction signal extends to 48 bars after it, cap 192; one position per instrument). Registered before the run (`MARKET_STRUCTURE_DEFINITIONS.md`, L1-M). Measured on development and walk-forward periods | `docs/phase4/L1-M.md` | -0.053 | -0.060 | +0.007 (-0.104 to +0.114) | 0.46 | -0.043 (both periods) | Fadi |

Each E1 / E0 trial also reports E1s (V5-S) and E1 without same-bar patterns; those are read from
the same run and are not counted as separate trials. Trials so far: **6**.

## Outcome mix of E1 by horizon

| Horizon | TP | SL | Horizon reached | Mean net R |
| --- | --- | --- | --- | --- |
| 48 | 12% | 35% | 53% | -0.046 |
| 96 | 19% | 49% | 31% | -0.066 |
| 192 | 27% | 62% | 11% | -0.100 |

## Reading (2026-10-23)

A longer horizon turns most of the trades that ended at the horizon into SL rather than TP:
going from 48 to 192 bars, TP rises by 15 points and SL by 27. E1 stays within the range of its
matched random entries at every horizon (p 0.36 / 0.46 / 0.60), and the TP rate is about
1.5 points above E0 at each horizon. So the horizon was not hiding an edge. **The registered
horizon (48) stays**; no parameter was changed by these trials.

## Measurements of the frozen rules (not trials)

The rules (L1, `strategy.toml`) were frozen on 2026-10-23, before P4. Measuring them on later
periods chooses nothing, so it is not a trial; any change to them after this date is a new
version and a new trial.

| Date | Measurement | Report | Result |
| --- | --- | --- | --- |
| 2026-10-23 | E1 on the 13 walk-forward test windows (2018-01 to 2024-06) | `docs/phase4/walkforward_L1.md` | 1,058 trades, TP 11.1%, mean net R -0.047 (95% weekly block -0.115 to +0.020) |
