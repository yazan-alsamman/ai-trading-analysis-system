# The five as a portfolio: splitting risk across trades open in the same direction (registered before any outcome)

**Registered 2026-11-12, before any outcome below was computed.** Claude listed AI-supported
decisions that do not need a forecast of direction; Fadi chose the first: "إي، سجّل الأولى". The
five (LVL4H, PIVOT, PIVW, ASIA, PWHL) often break nearby levels in the same direction on the same
morning, so two or three open trades can be one bet taken several times. This test asks whether
sizing a trade down when others of the five are already open in its direction gives **more return
per unit of risk** (a higher daily Sharpe) and **a smaller drawdown at the same return**.

The trades, entries, exits and costs do not change: only each trade's size.

## 1. Trades and units

- The five's trades as the EA trades them (`gold_live.five_trades`: frozen v1 + shadows, M8,
  16:45 exit, cost = spread + $0.07, $0.10 slip on stop exits), each with its entry bar i, exit
  bar j, direction and net R with slip.
- ROUND (the $50 shadow) is not in the test; its result under each rule is reported.
- A trade's **weight** w is its risk as a multiple of the normal risk (BASE: w = 1). A day's
  result is the sum of w x net R with slip of the trades placed that day (0 with no trade); this is
  the day's account return in units of the normal risk.

## 2. The rules (no free parameter is chosen on the test period)

At a trade's entry bar i, let k = the number of the five's trades open **in the same direction**
(entered at an earlier bar, or at the same bar earlier in the order LVL4H, PIVOT, PIVW, ASIA, PWHL;
exit bar j >= i). Opposite-direction open trades are ignored.

- **BASE:** w = 1 (the EA today; its cap of 3.5% open risk at 0.5% a trade is 7 trades and is
  not modelled).
- **SPLIT:** w = 1 / (1 + k). The extreme view: same-direction trades are one bet.
- **LEARNED:** w = 1 / (1 + k x rho), with rho the correlation of net R with slip between a new
  trade and each same-direction trade open at its entry, **estimated on the research store
  2012-2021** (every such pair pooled; clipped to [0, 1]). The equal-risk weight for k + 1 bets
  with pairwise correlation rho. rho is written in the report; it is not tuned.

## 3. Data and periods

- **Research store (XAUUSD):** rho from 2012-01-01 to 2021-12-31. **The test: 2022-01-01 to
  2026-01-09** (out of sample for rho; the five's own check period). 2012-2021 is reported.
- **FxPro GOLD export, 2016-02-01 to 2026-11-05** (`D:/GOLD_M1_201501020000_202611052359.csv`,
  summary bars dropped), rho from the store: a second feed, holding about ten months never used by
  any research.

## 4. Measures

- **Daily Sharpe** = mean / standard deviation of the day results over every weekday with at least
  one trade of the five under BASE (the same days for every rule).
- **Max drawdown at equal return:** each rule's day results scaled by c = (BASE mean) / (rule
  mean), so all have BASE's mean; the largest peak-to-trough fall of the cumulative sum, in R.
  (Only meaningful when the rule's mean is positive; otherwise reported as not defined.)
- Also: mean R a day, total R, the share of trades with k >= 1, mean weight.

## 5. The test and the pass rule

For SPLIT and LEARNED: the Sharpe difference (rule minus BASE) on the store 2022 to 2026-01-09,
its 95% interval and a one-sided p from a **4-week block bootstrap of days** (10,000 resamples, seed
20261115; each resample recomputes both Sharpes on the same days), **Holm over the two**.

A rule **passes** if all of:

1. Sharpe difference > 0 with Holm p < 0.05 (store 2022 to 2026-01-09);
2. its max drawdown at equal return is smaller than BASE's on the store 2022 to 2026-01-09 **and**
   on FxPro 2016-02 to 2026-11-05;
3. its Sharpe difference on FxPro 2016-02 to 2026-11-05 is > 0.

If both pass, the one with the higher Sharpe on the store 2022 to 2026-01-09 is chosen. If none
passes, the EA keeps equal risk.

**Power, stated before the run:** a sizing rule changes only part of the days (those with
overlapping same-direction trades), so the expected Sharpe change is small and the test may be
unable to see it; a non-pass then means "not shown", and equal risk stays.

## 6. Reported with it (decide nothing)

- rho, the number of pairs it rests on, and rho separately for pairs from the same level family
  (for example PDH with the weekly high) and from different ones.
- How often k = 0, 1, 2, 3+; the mean net R with slip of trades by k under BASE (do later
  same-direction trades do worse?).
- Per year (store): BASE and each rule's total R, Sharpe and max drawdown at equal return.
- ROUND's result, and the six together, under each rule.
- The largest drawdowns of BASE (dates, depth) and what each rule does in them.

## 7. If a rule passes (a later, separate step)

The EA sizes its stop orders when it places them, before it knows which other trades will be open
at the fill. Using a rule live needs the EA to re-size (delete and re-place) its pending orders
whenever one of the five opens or closes, and a tester match with this Python. That is its own
registration.

## 8. Bookkeeping

A look at the five's trades: logged in `docs/phase3/TRIALS.md` and counted in N. Code:
`app/research/risk_split.py`, `python -m app research risk-split --export <GOLD M1>`, committed before
the run. Report: `docs/portfolio/risk_split_result.md`.
