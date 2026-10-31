# Stage A: the engine (strategies, management, swap, decision functions)

Started and built 2026-10-26 on branch `ai/strategies-engine` (stacked on `ai/p6-live-scanner`);
moved uncommitted on 2026-10-27 to `ai/stage-a-engine`, from `main` after P6 was merged.
**No count and no outcome of any strategy S1-S8 was computed on market data.** Every test runs on
hand-built bars or on a synthetic random-walk market (`tests/strategy_data.py`). The one exception
is the M0 == `resolve` test, which replays L1 setups whose results are already known (P3) and
prints nothing.

## What was built

| Plan item | Code | Tests |
| --- | --- | --- |
| 1. One strategy interface, parameters in config | `app/strategies/base.py` (`Candidate`, `Trigger`, `Thesis`, common filters), `app/strategies/rules.py` (S1-S8), `app/config/strategies.toml` | `tests/test_strategies_rules.py`: hand-built bars per strategy, filters, append-future-bars per strategy on two instruments |
| 2. Management engine, bundles M0-M8 | `app/management/engine.py` (one bar-by-bar loop for every bundle), `app/management/book.py` (one active trade; family C fixed entry set with one exit, reason and net R column per bundle; overlap and entry-set diagnostics) | `tests/test_management_engine.py`: each rule on hand-built bars, sell = mirror of buy, M0 == `resolve` on 400 random plans and on every armed L1 setup of the development period (XAUUSD, EURUSD), append-future-bars per bundle; `tests/test_management_counts.py`: each bundle's columns from its own management, unresolved outcomes left missing, overlaps |
| 3. Session VWAP with bands; 5m frame for live requests | `app/strategies/vwap.py`; `app/live/frames.py` (`frames_for`, 5m entry frame) | VWAP by hand; 5m request builds 5m, 15m, 1h, 4h, D1; L1 frames unchanged |
| 4. Rollover instants, swap to R | `app/strategies/swap.py` (every `SYMBOL_SWAP_MODE`, W1, W3, decision, horizon end for a_S; signal-time, so it lives outside `app/management`) | `tests/test_strategies_swap.py`: triple day, 18:00 New York in the mismatch week, conversions, **no scalp or intraday horizon crosses a rollover** |
| 5. Decision functions of sections 8-10 | `app/research/decide.py` (blocks, bootstrap, T1 / T2, Holm, classification, status, delta*, MDE, n_unval, family C training set, selection and test trades, holdout check) | `tests/test_research_decide.py`: a low-frequency strategy can pass; the same trades on other days of their blocks give the same result; weak evidence is inconclusive; clear absence is unvalidated; K < 30 is inconclusive; n_unval reproduces 5,300 / 1,325; family C: a missing bundle column is an error, a training trade needs every bundle resolved and known by the window start, outcomes not known by then do not change the selection, test trades never depend on bundles not chosen |
| Research frames with 5m | `app/strategies/frames.py` (refuses an end past the lockbox start) | - |
| Stage B count command (built ahead, not run on market data) | `app/strategies/cli.py`: `python -m app strategies count` writes `docs/strategies/counts.md` and `counts_by_year.csv`; refuses while "Rules frozen at commit" is empty or a rule file (`RULE_PATHS`) differs from it (changed, uncommitted or untracked); `--swaps` takes the section 6a export (S3's a_S only) | `tests/test_strategies_cli.py`: report and yearly table on a synthetic store, no outcome columns, import graph without labels, management or E0, runs with them replaced by raising functions, the swap export fills S3's a_S, lockbox end refused, refused on the real (unfrozen) PREREG, the guard on a throwaway git repository |
| Stage B counting functions (built ahead, not run) | `app/strategies/counts.py` (pre-approval candidate counts, a_S, delta*_S), `app/management/counts.py` (post-approval counts after the one-active-trade and conflict rules; n, K, MDE, n_unval); `app/setups/costs.py` holds `round_trip`, so the strategies no longer import `app.setups.labels` (L1 behaviour unchanged) | `tests/test_strategies_counts.py`: the import graph loads no labels, management or E0; runs with them replaced by raising functions; no outcome columns or timestamps; lockbox refused before reading; holdout rows labelled; a_S unchanged when prices after the signal bar change. `tests/test_management_counts.py`: nothing printed or written, no exit detail or R in the tables, bars after 2024-07-01 refused, refused before approval, served-signal rules, power statements |

`libs/indicators` (`trading-indicators`) is now a dependency of ai-service: in the `research` and
`dev` extras of `pyproject.toml` (with a `tool.uv.sources` path), installed in the local venv
(`uv pip install -e ../libs/indicators`) and in CI (`.github/workflows/ci.yml`). It is not in the
base dependencies, so the production image still builds. Full suite: 413 tests pass (2026-10-31,
after the review decisions, on `ai/stage-a-engine` with `main`'s tests).

## Audit points (2026-10-26)

**Decided by Fadi (2026-10-26), wording now in `PREREG.md`:**

3. **Family C.** Each bundle's outcome on an entry is its own (exit time, exit reason, net R).
   "Exit + 1 day" applies to training membership only: a training trade needs its exit under every
   bundle + 1 day at or before the window start, or it is left out of that window's training. Test
   trades are the fixed M0 entry set in the window, excluded (and counted) only when the M0 or the
   chosen bundle's outcome is unresolved; unchosen bundles never include or exclude a test trade.
   The fixed-entry approximation, overlaps and entry-set differences are descriptive diagnostics,
   not portfolio results (section 9). Code: `decide.training`, `select_bundle`, `window_trades`;
   `book.fixed_entry_table`, `overlaps`, `entry_set_difference`.
4. **Approval timing.** Rules frozen at a recorded commit before any count; pre-approval
   candidate counts only (no `resolve`, management, E0 or exit time); approval after them and
   before any outcome or any count that uses an exit; post-approval counts write and print no
   exit detail or R; a rule change is a new version with the counts rerun (header, sections 12 and
   15). Code: `app/strategies/counts.py`, `app/management/counts.py`.

**Decided by Fadi (2026-10-27), after the Stage A review; wording now in `PREREG.md`:**

1. **Scalp forced exit (section 4).** Horizon or the session end, whichever comes first, for
   scalps as for intraday trades (`[types.scalp] session_end`), so that no scalp crosses the 17:00
   rollover. **Missing bars:** when the next bar in the data closes after 16:45, the trade exits at
   its open with the SL slippage, marked `session_end_gap` and counted; no price is invented and
   swap runs to that actual exit time (resting TP and T2 fill at their levels if that open reaches
   them). The normal session-end exit is at a close and pays no slippage, as the timeout. Code:
   `engine.manage` step 3; tests: `test_bars_missing_before_the_session_end_exit_at_the_next_open`.
2. **The 1h boundary (S2, section 4).** The rule is written as the code applies it, unchanged:
   exit at the close of the last bar that can close by 16:45 (5m and 15m: the bar ending 16:45; 1h:
   the bar ending 16:00), `no_time_left` when the next bar would close after 16:45 (1h: the bar
   opening 15:00). A session end on 4h or D1 is a configuration error (`SignalSpec`). Tests: the
   boundaries on 5m, 15m and 1h in winter, summer and both daylight-saving mismatch weeks.
3. **a_S without a swap export (section 8).** s_h = 0 by construction for scalp and intraday
   strategies, so their a_S and delta*_S need no MT5 export; S3's waits for it
   (`counts.assumed_r`).
4. **Complete ranges (S1, S4, section 5).** Every bar of the range window must be present (S1: 28,
   S4: 6), else the day's first breakout is rejected as `incomplete_range`.
5. **The rollover price (section 6).** In trade results P is the close of the last entry-frame bar
   closed by the rollover instant (`swap.close_before`); in a_S the entry price (no price after the
   signal bar). W3 stays at the open price.
6. **T4 wording (section 7).** "A close beyond EMA(20) against the trade, at a later close after
   arming", whatever side the earlier closes were on (the code's reading, unchanged).

Every other choice below was kept as it is.

## Choices fixed in code where the PREREG text is silent (review; part of the frozen version)

Strategies (`rules.py`, `base.py`):

- One signal a day (S1, S4): the day's first breakout in either direction is the only trigger,
  whatever the filters then decide; no later breakout that day is a trigger.
- A range needs every bar of its window (S1: 28, S4: 6), else `incomplete_range`; a day without
  any range bar has no range and no trigger.
- A failed regime, width or move-size filter is a rejection reason of the trigger (`regime`,
  `range_width`, `move_too_small`), so the counts show it.
- Rejection order: `holiday`, `outside_liquid_window`, the strategy's own reason
  (`incomplete_range` before `range_width`),
  `non_positive_risk`, `r_out_of_range`, `cost_filter`, `no_time_left`.
- Liquid window: the signal bar opens in [02:00, 16:00) New York, Monday to Friday; holidays by
  the New York date of its open.
- S2: "after a close inside" means the previous close within [lower, upper].
- S3: every close beyond the channel is a trigger; the one-active-trade rule limits entries.
- S5: the six bars for the SL include the signal bar; the SL is the further of the structure SL
  and 1.0 x ATR.
- S6: the previous bar must belong to the same VWAP session (from 03:00 New York).
- S7: after a run of at least six squeeze bars ends, the first close outside the band, from the
  bar where the squeeze ends; a new squeeze bar before that resets it.
- S8: m from the close of the 5m bar ending at the fix and the close of the bar ending 30 minutes
  earlier; both bars and the signal bar must be present; R from the entry to the TP.
- L5 of a breakout counts closes strictly back inside the level broken at the signal (range edge,
  channel, band), held fixed.

Management (`engine.py`):

- "+1 R" (L1, L2, L3) is the best excursion so far, from highs, at a close.
- T4 arms at a close with open profit >= 0.5 R and fires at a later close: a body that engulfs
  the previous body against the trade, or a close beyond EMA(20) against the trade (whatever side
  the earlier closes were on).
- Exit alerts fill at the next open minus the SL slippage; if several fire at one close, the
  reason is the first of `invalidation`, `dead_trade`, `profit_lock`, `fade`.
- T2 fills at +1 R even when the bar opens beyond it (a limit; as the TP in `resolve`).
- T1, T3, L4 fractions use the registered horizon, not one shortened by the session end.
- L2 uses the highest high of the bars after the signal bar; L3 the ATR at the current close.
- Exit time for swap: the bar's open for an exit at the open, its close otherwise.
- Session end: exits at a close (`timeout`, `session_end`) pay no slippage; a `session_end_gap`
  exit at an open pays it.

Swap (`swap.py`): the instant that ends server day D is charged when D is Monday to Friday (MT5
day numbers, Sunday = 0); W3 charges twice the worse side of W1 at the open price; the price for
conversions is the close of the last entry-frame bar closed by the rollover in trade results and
the entry price in a_S; the a_S horizon ends at the
close of bar idx + horizon (the bar grid past the data), capped by the session end.

Decision (`decide.py`): sd(c*) with ddof 1; a passed family B strategy that is not consistent on
the holdout is inconclusive (section 10); a passed strategy gets a status only after its holdout
check.

Counts (`app/strategies/counts.py`, `app/management/counts.py`): a trading day is a New York
weekday that is not a US market holiday and has an entry-frame bar, plus any other date with a
candidate (S3 can signal on a Sunday evening); weeks run Monday to Sunday, shares 0 / 1-9 / 10 or
more; the post-approval counts take armed candidates with entry from the primary start (earlier
bars are warm-up only); in the served-signal rules the first signal wins a conflict, ties by
strategy name, a candidate after an unresolved served trade of its strategy is undecided (as the
one-active book) and one opposite to an unresolved trade of another strategy is a conflict (that
trade is open to the data end); DE 1.5 for S4 and S8, 1.2 otherwise, as constants of the module.

## Left for later stages

- **Stage C code, built 2026-10-30 before approval, not run** (`app/research/strategy_eval.py`,
  `python -m app research evaluate`; `app/research/post_counts.py`, `python -m app research
  post-counts`). Both refuse to run until the approval date and the seeds are in `PREREG.md`, and
  while any file of `EVAL_PATHS` differs from the frozen commit. `EVAL_PATHS` is `RULE_PATHS` plus
  `app/management`, `app/setups/labels.py` and `app/smc/primitives.py`: the count command's
  `RULE_PATHS` (frozen) leave out the management engine and the label code it reads, which are
  rules too (section 15). delta*_S is read from `counts.md`, which must name the frozen commit.
  Tests on synthetic markets only (`tests/test_strategy_eval.py`). Choices fixed in this code where
  section 8 is silent (part of what Fadi approves):
  - Trades: entries from 2018-01-01 under M0's one-active-trade rule, warm-up bars from 2017, the
    same set as the post-approval counts (tested); sensitivities 1 and 2 use a second book with
    entries from 2012.
  - x and E0 both use the decision swap scenario (W1 by the trade's own exit time, at the price of
    each rollover). The 2x stress keeps the W1 swap.
  - E0 matches on the New York year and hour of the signal bar's open. Its risk is the trade's risk
    over the strategy's entry-frame ATR, times the ATR of the random bar. Its TP is the trade's own
    R multiple (for S2, S6 and S8, whose TP is a price level, the R the level gave). A drawn bar must
    be a weekday that is not a US holiday, with time left before the session end (scalp and
    intraday), and with a bar after it. A draw that fails the cost filter or is unresolved is
    redrawn, up to 50 times.
  - Trades without any E0 draw are left out of the test and counted. Unresolved trades are left out
    and counted.
  - One bootstrap seed for every strategy and sensitivity. The Bonferroni bounds use the same
    draws. The first-Friday filter drops trades open at 08:30 New York on a month's first Friday.
  - A passed strategy is reported as "passed", waiting for the holdout check. The holdout is not
    read by this command.
- **Incident, 2026-10-30.** After the approval fields were filled in (not yet committed), a test
  meant to check that `post-counts` refuses an unapproved preregistration patched the guard of
  `evaluate` only, so `post-counts` ran on the real store twice and wrote `counts_post.md` and
  `counts_post_by_year.csv`. These are the post-approval counts the approval allows (no R, exit
  reason, exit price or exit time). The two files were deleted unread and the test fixed (it now
  patches both commands); the counts are rerun with the command after the approval commit.
- **Stage C restart, 2026-10-31.** The first run of `evaluate` (started 2026-10-30) printed nothing
  and spent 84% of its time rebuilding the rollover instants for every E0 draw (about 1 ms each,
  about 14 million draws). It was stopped before writing anything. `Rollovers` now computes them
  once per entry frame: about 10 times faster, the same floats (tests compare both paths exactly),
  with a progress line per E0 replication. Recorded in `PREREG.md` (code changes after approval).
  The second run showed 7 minutes per replication (about 24 hours in all): the E0 loop rebuilt the
  New York year and hour arrays of all 74,174 trades for every trade. They are now computed once;
  the same values. That run was stopped too, before writing anything.
- **Stage D code, built 2026-10-31 after Stage C, not run** (`app/research/management_eval.py`,
  `python -m app research management`; tests on synthetic data, `tests/test_management_eval.py`).
  Same guard as Stage C. It uses the frozen family C functions (`book.fixed_entry_table`,
  `overlaps`, `entry_set_difference`; `decide.training`, `select_bundle`, `window_trades`,
  `paired_test`, `holm`). Choices fixed here where section 9 is silent: the entry set is M0's
  one-active book on bars from 2012 (all candidates after the indicator warm-up); net R of every
  bundle includes the decision swap (W1 by its own exit time); the 13 windows and the 1-day embargo
  come from `research.toml`; the 95% interval of the mean delta is the percentile interval of the
  same bootstrap (reported); the bundle the procedure would serve is the selection at 2024-07-01;
  trial numbers 19 scalp, 20 intraday, 21 swing; the diagnostics (overlaps, entries added and
  dropped) cover all years.
- **Holdout reading code, built 2026-10-31 after Stage E was closed, not run**
  (`app/research/holdout.py`, `python -m app research holdout`; `tests/test_holdout.py`). It runs
  once: it is refused when `holdout.md` exists, while `evaluation.md` or `management.md` is not
  committed unchanged, before the Stage E decision is in `PREREG.md`, and under the Stage C guard.
  It computes only the registered checks: family C scalp (the bundle selected at 2024-07-01
  against M0 on the holdout scalp entries) and Addendum 1 (S1 + M8), with Addendum 1's reported
  details. Bars go to the lockbox start; the lockbox is not read.
- Stage B: the rules are frozen at `b9ca2a8` (`main` after PR #77, tag `strategies-rules-v1`,
  recorded in `PREREG.md` on 2026-10-29). The pre-approval counts ran on the real store the same
  day (`docs/strategies/counts.md`, `counts_by_year.csv`).
- Production image: `ai-service/Dockerfile` builds from `ai-service/` and cannot see
  `libs/indicators`; serving the strategies needs a build-context change (Yazan), Stage F.
- Live serving: contract fields, 5m bars (`AI_BARS_5M`), history long enough for S3 (55 + 20 4h
  bars, about 13 trading days) and S5 (EMA(50, 1h)): Stage F.
- `SwapSpec` values: received 2026-10-28 (`docs/strategies/mt5/`, PREREG section 6a). The
  export showed FxPro's GOLD in `CURRENCY_SYMBOL` mode with base currency USD; the conversion
  multiplied every `CURRENCY_SYMBOL` swap by the price, which would have made gold's swap about
  4,000 times too large. Fixed: as is when the base is the profit currency, x P otherwise
  (`swap.per_night_r`; tests with the real values).
