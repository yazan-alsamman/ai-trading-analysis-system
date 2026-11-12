# Volatility outlook in the service: the 15m version and what it serves (registered before the check)

**Registered 2026-11-12, before the 15m check below was run.** Part 1 (`VOL_FORECAST.md`) passed:
M3 forecasts the 02:00-16:45 New York window's RV better than the ATR. Part 2 (`VOL_PART2.md`)
found no use for it in the five's trades. Fadi: keep it as an alert for the user, with no effect on
any trade or signal ("خلينا نحتفظ فيه بدون ما يأثر على الصفقة ... تنبيه للمستخدم").

## 1. Why a 15m version

The backend sends 15m, 1h, 4h and 1d bars to `/v1/evaluate`, not 5m (`../docs/ai-contract.md`
§2). The service therefore needs M3 built from **15m** bars: the same definitions as part 1 with
a 15m bar in place of a 5m one (window = 15m bars opening 02:00 to 16:30 New York, 59 bars; the
90% and 30-minute rules unchanged; RV from squared 15m log returns).

## 2. The check (a measurement of the serving form, not a new hypothesis)

Part 1's walk-forward (`vol_forecast.walk`, test years 2018-2025, QLIKE, 4-week block bootstrap,
seed 20261113) on the 15m form. **The 15m M3 is served** only if it meets part 1's three
conditions against the 15m M1 (Holm over M2-M4, p < 0.05; better in at least 6 of 8 years;
better in 2024-07 to 2026-01-09). If it fails, nothing is served and the outlook waits for 5m bars.

## 3. What is frozen (if the check passes)

`app/config/volatility_v1.json`, written by `python -m app research vol-forecast freeze`:

- M3's coefficients and residual variance s^2, fitted on every used 15m day 2012-01-02 to
  2026-01-09.
- **Range multipliers:** on the walk-forward test days, k = window range / price at 02:00 divided
  by sqrt(F) (F = the out-of-sample level forecast); its 20th, 50th and 80th percentiles. The served
  range is price x sqrt(F) x k_q.
- The code commit and the store's row counts.

## 4. What is served (description, not advice)

An additive `volatility` object in the `/v1/evaluate` response (responses ignore unknown fields,
contract §1), computed on weekdays from 02:00 to 16:45 New York from the 15m bars closed by 02:00
and the request's calendar; otherwise null with a reason:

- `expected_move_pct` = 100 x sqrt(F); `range_usd` and `range_pct` at p20 / p50 / p80;
- `level`: F against the mean RV of the previous 22 used days: below 0.8 `quiet`, to 1.25 `normal`,
  to 1.6 `lively`, above `very_lively` (wording thresholds chosen here; they were never tested and
  decide nothing);
- `news`: the USD high-impact releases in today's window (time, title, whether TOP3);
- `model` = `vol-m3-15m-v1`.

**It changes no setup, no state, no size and no abstention.** It is information for the user.

## 5. What the backend has to send for it (a proposal for Yazan, not yet agreed)

1. **History:** 22 used days of 15m bars before 02:00 New York, not counting the data's first
   day (its first return is unknown); with the 23-hour gold day that is about **2,500 x 15m**
   (today's default `AI_BARS_15M` is 2,000; the contract maximum is 5,000).
2. **Calendar window:** the USD high-impact events of today's 02:00-16:45 New York window. Today's
   `for_evaluate` sends ±6 h, so at 02:00 it misses the 08:30 releases and the 14:00 Fed decision.
3. **Titles:** the service recognises the three TOP3 releases by title (Nonfarm Payrolls or
   Non-Farm Employment Change; headline CPI m/m; the Fed's rate decision or FOMC statement). The
   calendar source's exact titles must be checked against that list.

Until (1) and (2) hold, the object comes back with no forecast and the reason (`insufficient_history`,
`outside_window`), and nothing else in the response changes.
