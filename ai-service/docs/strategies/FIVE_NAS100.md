# The five demo strategies on the Nasdaq 100 (an unseen instrument)

**Registered 2026-11-11, before any outcome on this instrument was computed.** Fadi's idea (chat,
2026-11-11): run the five gold strategies, exactly as frozen, on FxPro's `#USNDAQ100`. No Nasdaq
data has been read by this project before, so this is the first test of the five on data that
shaped none of their choices (the role of H5 in the research plan).

Code: `app/research/five_nas.py`, `python -m app research five-nas build --export <M1 export>`.

(This file was overwritten by the run's report on 2026-11-11, because Windows does not tell
`five_nas100.md` from `FIVE_NAS100.md`; the registration below is restored word for word, the
report now goes to `five_nas100_result.md`, and nothing in the rules changed.)

## 1. Data and costs

- FxPro's `#USNDAQ100_M1_201501040000_202611092359.csv` (Fadi's export, 2026-11-11). M1 bars with
  a spread from 2015-10; the run reads from **2016-01-04** and trades from **2016-02-01** (as gold's
  FxPro run, so the 5-day levels and the ATRs have filled). Only the file's first and last lines
  and its bars-per-day counts were looked at.
- Server time with Europe/Athens, through the same parser and clock check as gold
  (`gold_exam.frames_from_lines`); the index keeps gold's session (week open 18:00 New York, daily
  break 17:00-18:00), as its specification shows.
- **Costs**, from the symbol's specification (Fadi's screenshot): contract size 1, a point (0.01)
  worth $0.01 a lot, so 1 index point = $1 a lot. Commission $1.5 a lot each deal, **3.0 index
  points a round trip** (gold's $0.07 an ounce is replaced). Spread: the bar's recorded spread.
  **SL slippage 0.5 point** (gold's $0.10 is about 0.0025% of the price; 0.0025% of 20,000).
  Swap is not counted: every trade closes the same day.

## 2. The strategies: unchanged

LVL4H, PIVOT, PIVW, ASIA and PWHL with their frozen rules (`GOLD_V1.md`, `GOLD_SHADOW.md`): the
same levels, D (0.75 x ATR(14, 4h); PIVOT ATR(14, 1h)), the cost cap 0.05 (not PIVOT), the 02:00-16:00
New York window, M8, the 16:45 exit, one trade at a time each. Nothing is tuned on this instrument.

## 3. Decision

- **H5-like reading:** the five together, mean net R with slip a trade, 2016-02 to 2026-11-09.
  - **Generalises** if it is > 0 and above the 95th percentile of **E0**: the same entries with
    the side drawn by a fair coin (50 runs, seed 20261111), so only the break's direction is
    tested, with every cost and exit the same.
  - **Does not generalise** if it is ≤ 0 or within E0's range.
- Reported beside it: each strategy, years, the drawdown in R, the cost in R.
- This changes nothing on the gold demo. A positive result would make the Nasdaq a candidate for its
  own forward demo, registered separately.

## 4. Count

One run (5 strategies, one setting), logged in `docs/phase3/TRIALS.md`.

## 5. Outcome (2026-11-11): does not generalise

`five_nas100_result.md`. 5,189 trades, 2016-02 to 2026-11-09.

| Set | Trades | Net R with slip | Years + |
| --- | --- | --- | --- |
| The five together | 5,189 | **−0.078** (SE 0.017) | 27% |
| LVL4H | 883 | −0.140 | 22% |
| PIVOT | 2,022 | −0.111 | 27% |
| PIVW | 703 | −0.034 | 44% |
| ASIA | 1,184 | −0.019 | 33% |
| PWHL | 397 | −0.026 | 33% |

- **E0** (the same entries, a random side): mean −0.049, 95th percentile −0.025. The five are
  **below E0's mean**: on the Nasdaq the break's side does worse than a coin.
- Gross R +0.015 a trade against a cost of 0.085 R (PIVOT 0.165, with no cost cap).
- By year: −0.10 to −0.47 R in 2016-2021, +0.04 to +0.05 in 2022-2024, −0.04 in 2025 and 2026.
  Sum −404 R, largest drawdown 427 R.
- **Reading:** the level-break edge seen on gold does not carry to a second, unseen market. This
  is the one test of the five on untouched data, and it weighs against reading their gold results
  as a general effect; their gold results may be specific to gold or a product of the search
  (about 60 looks on gold). The gold demo is unchanged.
