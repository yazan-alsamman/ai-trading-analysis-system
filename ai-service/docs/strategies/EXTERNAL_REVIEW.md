# Review of five public trading projects, compared with this research

Written 2026-11-03 at Fadi's request. Each repository was cloned at its latest commit on that date.
Its code, tests and published results were read, and none of its code was run. The comparison
is with the registered research summarised in `FINAL_REPORT.md`.

## 1. Summary

| Repository | What it is | How it is evaluated | Published result | Strength of the evidence |
| --- | --- | --- | --- | --- |
| [KVignesh122/MT5-SMC-trading-bot](https://github.com/KVignesh122/MT5-SMC-trading-bot) | one MQL5 Expert Advisor (558 lines): order blocks, FVG, BOS | none | "60% to 300%+ returns yearly", with no report | none; the README carries a broker referral link and promotes a paid product |
| [carreypro/ict-trading-model](https://github.com/carreypro/ict-trading-model) | a Codex skill that validates an ICT setup step by step | unit tests of the detectors | none | no trading result |
| [MobiusQuant/OpenMobius-skill](https://github.com/MobiusQuant/OpenMobius-skill) | a retrieval knowledge base (2,008 cards) for trading questions, with charts | fixed retrieval benchmark, 180 cases | Recall@5 about 0.95 | retrieval quality, not trading |
| [GifariKemal/xaubot-ai](https://github.com/GifariKemal/xaubot-ai) | XAUUSD 15m bot: XGBoost, HMM regime, SMC, MT5 | backtest 2025-01 to 2026-02 | 654 trades, win rate 63.9%, profit factor 2.64, Sharpe 4.83 | very weak (section 5) |
| [0xagarg/xau-ai-trading-bot](https://github.com/0xagarg/xau-ai-trading-bot) | **an exact copy of xaubot-ai** | | | `diff -r` finds no difference; the last commit has the same message and date |

**No project shows a better result than ours on evidence.** They did not measure the way this
research did, so they found nothing to disappoint them. Their real advantages are elsewhere:
they run in the market, they explain each signal, and they ship a product.

## 2. MT5-SMC-trading-bot

**What it does.**
- Entries:
  - in an order block at the 61.8% retracement;
  - on a touch of an FVG;
  - on a BOS with displacement.
- Filters: the session (skips Asia) and ADX for the trend.
- SL 1.5 x ATR and TP 2.5 x ATR.
- "Equity bagging": closes everything at +8% or -4% of equity.

**Problems.**
- No backtest is published; the return claim has no support.
- The FVG scan starts at the bar still forming (`i = 0`), so a signal can appear and disappear.
- Filled FVGs are never removed, so the EA keeps entering them.
- Position size is a fixed lot per $1,000 of balance, not set from the risk.

**What to take.**
- It runs inside MT5, so it can be tested in the Strategy Tester on "Every Tick" with the broker's
  real spread.
  - For us: replay a sample of our trades in the Strategy Tester. This checks our cost model,
    whose extra term and slippage are about 60% assumed.
- Equity bagging, as a daily loss limit on the whole portfolio.

## 3. ict-trading-model

**What it does.** An FVG, an order block or an opposing candle alone is never a signal. The whole
sequence must hold, in order:

1. higher-timeframe bias;
2. a liquidity objective;
3. premium or discount location;
4. a liquidity sweep;
5. displacement with a strict FVG;
6. an MSS or BOS confirmed by a close;
7. a retracement into an OB, FVG, breaker or OTE;
8. an invalidation level and a target;
9. reward to risk of at least 1:2.

Each analysis returns one status: `confirmed`, `developing`, `invalidated` or `no-trade`. Evidence
is kept in four groups: observed, derived, interpretive and missing.

**Problems.** There is no performance measurement. The scanner states that its reward to risk is
gross of fees, spread and slippage.

**Better than ours.**
- **Each signal is explained.** Ours carries a number and a status, with no account of why it
  fired.
- **A `developing` state** tells the user that a setup is forming. We have nothing like it.
- **Our L1 is a thinner definition:** a sweep then a CHoCH. It has no higher-timeframe bias, no
  premium/discount location and no liquidity target, and its TP is a fixed R, not a liquidity
  level.

**What to take.**
- Contract fields, for display only, with no rule change:
  - `evidence`: the steps that held;
  - `invalidation`: the level where the idea is wrong;
  - a `developing` state.
- The full sequence (higher-timeframe bias, location, liquidity target) as a **new registered
  hypothesis**, judged on the forward paper log or the lockbox, because the holdout has been read.
  - Expectation: P3 and P4 found that SMC context adds no information beyond session and
    volatility, so it is likely to be inconclusive.

## 4. OpenMobius-skill

**What it does.**
- A knowledge base across trading schools (ICT, SMC, ChanLun and others), with each item tied to
  its source, plus chart rendering.
- It **fails closed**: when no native analyser exists for the school asked for, it stops, and
  does not relabel SMC output as another school.

**How it is evaluated.**
- A fixed benchmark of 180 queries, measuring Recall@1/5, MRR and scope purity.
- Its README says this is a regression benchmark, not a measure of generalisation.

**Result.** Retrieval only (Recall@5 about 0.95); no trading figure.

**Better than ours.**
- Explanations tied to sources.
- Charts with the levels drawn on them.
- A measured benchmark for the language-model layer.

**What to take.**
- Any language-model layer we add (an explanation of a signal, or the backend's Gemini chart
  analysis) gets:
  - a fixed benchmark like this one;
  - fail-closed routing.
- A chart for each signal, with the entry, SL, TP and invalidation drawn on it.

## 5. xaubot-ai (and its copy)

**What it does.**
- XAUUSD on 15m:
  - XGBoost with 37 features, a 3-state HMM regime model, SMC detection and 14 entry filters;
  - Kelly position sizing;
  - loss limits of 5% a day and 10% in total.
- Product: a news filter, Telegram notifications, a Next.js dashboard and Docker.
- The model is retrained every day.
- **It trades on a live or demo account and analyses its own trades.**

**Why its numbers are not evidence.**

1. **The training data covers the test period.**
   - The model is retrained daily on the latest 15,000-20,000 15m bars (about 7-10 months), with
     `train_ratio=1.0` for the final fit.
   - The backtest runs from 2025-01 to 2026-02, so the model saw the second half of that period
     during training.
2. **No costs.** Profit is `pips * pip_value * lot_size`, with no spread, commission or slippage.
   In our Stage C, costs alone took S1 from +0.033 R before costs to -0.014 R after them.
3. **About 39 variants on the same period** (`01_smc_only` to `39_h1_hmm`).
   - A `--tune` mode searches thresholds on the same data.
   - There is no multiple-testing correction, so the published figure is the best of about 39.
4. **The label** is the direction of the next bar (`lookahead=1`), the noisiest label possible.
5. **No hard SL in the backtest** ("smart exit logic (no hard SL)").
6. **The walk-forward check is short:** 50-bar test windows (12.5 hours) and a 50-bar gap between
   training and test.

**Its own live record.** `ANALYSIS-FEB10-TRADES.md` reviews one live trading day (2026-02-10):

| | Backtest | Live day |
| --- | --- | --- |
| Trades | 654 | 42 |
| Win rate | 63.9% | 42.9% |
| Average win / average loss | about 1.5 (implied by the profit factor and win rate) | 0.64 ($5.04 / $7.85) |
| Net | +$4,189.52 | -$97.78 |

- This is the gap a read-once holdout guards against.
- After that day the sell filter was changed and judged on the same trades ("41.2% to 57.9%"):
  the same mistake again.

**Done right.**
- Swing points are confirmed `swing_length` bars late, so swing detection uses no future bars.
- There is a gap between the training and test sets.

**Better than ours.**
- **Market data from live trading.** We have no paper trade yet. Live trading showed problems a
  backtest would not show: a loss seven times the average, and losing night hours.
- **Daily monitoring reports**, by hour and by direction.
- **Operational risk limits:** a daily loss limit, a maximum number of open positions, and a
  cooldown between trades.
- **A complete product.** Part of this exists in the backend, but ai-service itself has nothing
  running live.

**What to take.**
- **Start the forward paper log as soon as possible.** It is the only source of data nobody has
  seen.
- A daily or weekly monitoring report by hour, instrument and direction. It is descriptive and
  never changes a rule.
- Portfolio risk limits in R: a daily loss limit and a maximum number of open trades. These are
  part of the exposure limits, an open point with Yazan.

## 6. Where this research is stronger

| Area | This research | The projects reviewed |
| --- | --- | --- |
| Costs | measured spread, assumed extra cost and slippage, swap scenarios, a 2x stress run | none (xaubot), or gross only (ict-trading-model) |
| Baseline | 200 matched random entries for each trade (E0) | none |
| Data | 6 instruments, 2018-01 to 2024-06 primary, 2012 for gold | gold, about 13 months (xaubot) |
| Rules fixed before results | pre-registration; rules frozen at `b9ca2a8` | tuned on the test period |
| Multiple testing | Holm per family; Deflated Sharpe with N = 26; every trial logged | about 39 variants, no correction |
| Out of sample | 13 six-month walk-forward windows; holdout read once; lockbox sealed | training covers the backtest period |
| Unknowns | "no proven edge" served with every signal | profitability claimed |

## 7. Recommendations, by priority

1. **Serve the signals and start the forward paper log,** with a periodic descriptive monitoring
   report (from xaubot-ai).
2. **Check the cost model in the MT5 Strategy Tester** on "Every Tick", on a sample of trades
   (from MT5-SMC-trading-bot).
3. **Explain each signal in the contract** (from ict-trading-model and OpenMobius-skill):
   - the evidence that held and the invalidation level;
   - a `developing` state;
   - a chart with the levels drawn.
4. **Portfolio risk limits in R,** agreed with Yazan.
5. **Optional:** register the full ICT sequence as a new hypothesis, judged on the forward paper
   log. The expected result is inconclusive.
