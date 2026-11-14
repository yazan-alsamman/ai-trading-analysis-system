# Contract proposal for Yazan: the `gold_levels` profile and trailing exits (P7 F1)

**Status: proposal (2026-11-13), not agreed.** ai-service has the engine ready
(`app/live/gold_levels.py`, checked against the research trades in `gold_levels_check.md`), but
it is not served until this is agreed: the current contract would reject its setups (`tp` is
required in `ARMED` / `ACTIVE`). Everything below is **additive**: the `intraday` profile (L1) and
its setups do not change.

## Why

The research found an edge only in the gold level breaks (LVL4H, PIVOT, PIVW, ASIA, PWHL and the
ROUND shadow), the strategies running on the demo EA. They have no fixed target: a stop at a
distance D, moved to break-even plus cost at +1 D, then trailed under the last 5m swing, and an exit
at 16:45 New York at the latest. To serve them, and later other strategies with other exits, the
contract needs an exit type instead of a required target.

## 1. `Setup`: an exit type (general, for every later strategy)

| Field | Change |
| --- | --- |
| `exit_type` | **new**, optional: `target` (default when absent: today's behaviour), `trailing`, `time` |
| `tp` | required in `ARMED` / `ACTIVE` **only when** `exit_type` is `target`; null for `trailing` / `time` |
| `r_multiple` | null when `tp` is null |
| `sl` | for `trailing`, the stop **as of now** (it moves while `ACTIVE`) |
| `exit_reason` (when `CLOSED`) | adds `stop`, `trailing_stop`, `time` to today's `tp` / `sl` / `timeout` |

The side rule stays: buy `sl < entry` (and `< tp` when there is one), sell the mirror.

## 2. Transitions: the stop moves

A trailing stop's move is a transition that keeps the state:

```json
{"setup_id": "xauusd-gold_levels-lvl4h-pdh-20261113", "from": "ACTIVE", "to": "ACTIVE",
 "at": "2026-11-13T15:40:00Z", "reason": "sl_moved", "sl": 4092.15}
```

`sl` is a **new optional field** on a transition, present only with `reason: "sl_moved"`. The backend
updates the stored setup's `sl` and may notify the user ("the stop moved to ...").

## 3. The `gold_levels` profile

| Item | Value |
| --- | --- |
| `profile` | `gold_levels` (instrument `XAUUSD` only) |
| Schedule | every **5m** bar close (the strategies touch and trail on 5m) |
| `bars` | **`5m` × 3,000** (about 10 trading days), `1h` × 500, `4h` × 300, `1d` × 260; the smallest timeframe (`5m`) ends at `bar_close_ts` as today's rule |
| `calendar` | the USD high-impact events of today's 02:00-16:45 New York window (as `ai-service/docs/vol/SERVING.md` §5 asks for the volatility outlook) |
| Setups a day | one per strategy and level: about 14 (`ARMED` from 02:00 New York) |
| `setup_id` | `xauusd-gold_levels-<strategy>-<level>-<yyyymmdd>`, deterministic |

Lifecycle: `ARMED` (02:00, the stop order waits at the level) → `ACTIVE` (the touch; the fill) →
`sl_moved` transitions → `CLOSED` (`stop`, `trailing_stop` or `time`, with `realized_r` after
costs). `EXPIRED` at 16:00 New York when the level was never touched. `INVALIDATED` at the touch when
the trade is not taken (`cost_cap`, or `strategy_busy`: the strategy is already in a trade).
`DEVELOPING` is not used.

## 4. `evidence`: one shape for every strategy

```json
{"strategy": "LVL4H", "version": "gold-v1", "entry_type": "stop", "exit_type": "trailing",
 "window_ny": "02:00-16:00", "exit_by_ny": "16:45", "d": 19.65, "d_rule": "0.75 x ATR(14, 4h)",
 "facts": [
   {"key": "level_kind", "value": "PDH", "label_ar": "قمة اليوم السابق", "label_en": "previous day's high"},
   {"key": "level_price", "value": 4349.03, "label_ar": "سعر المستوى", "label_en": "level price"}],
 "volatility": {"status": "ok", "expected_move_pct": 0.95, "...": "..."}}
```

`evidence` stays free-form for the backend (stored and echoed as it is); the shape is ai-service's
promise to itself, so `/v1/explain` needs nothing more than the setup.

## 5. Sizing

`/v1/size` works unchanged: the risk is `|entry − sl|` (+ `cost_per_unit`), with the stop at
entry. A `trailing` setup has no `tp`, so the size response has no reward figure.

## What the backend would do

1. Accept `exit_type` and nullable `tp` (migration: a nullable column + the new enum values).
2. Store `sl` updates from `sl_moved` transitions.
3. Schedule `gold_levels` every 5m for XAUUSD with the bar counts above, and widen the calendar
   window for it.
4. Show `trailing` setups without a target ("exit: trailing stop, by 16:45 New York").
