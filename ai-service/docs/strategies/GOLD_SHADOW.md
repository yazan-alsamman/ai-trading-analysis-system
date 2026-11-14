# Gold shadow candidates: the opening candle and three level breaks (commercial track)

**Registered 2026-11-07, before any outcome of these rules was computed** (Fadi: "Opening +
alternatives"). v1 (`GOLD_V1.md`) does not change. A candidate that passes section 4 runs beside
v1 on the demo as a shadow strategy, with its own magic number, and is judged there on new data
only.

Code: `app/research/gold_shadow.py` (`python -m app research gold-shadow build`, then
`gold-shadow fxpro --export <GOLD M1 export>`). Reports: `gold_shadow_xauusd.md`,
`gold_shadow_fxpro.md`.

_Restored after the run. The first report path, `gold_shadow.md`, is this file's name on Windows,
where file names ignore case, so the run overwrote it. Sections 1-6 are the text as registered;
only the report names above changed. Section 7 was added after the run._

## 1. Data and costs

| Item | Value |
| --- | --- |
| Development feed | XAUUSD research store, 5m bars, 2012-01 to 2026-01-09 (the lockbox is not read) |
| Tune / check | 2012-2021 / 2022 to 2026-01-09 |
| Live feed | FxPro `GOLD` M1 export, 2016-02 to 2026-11-05 (`gold-live fxpro` reads it) |
| Cost | the signal bar's recorded spread + $0.07 per oz, a round trip |
| Slippage | $0.10 on every stop exit, reported beside the net |
| Session end | 16:45 New York, as v1 (SCUTA closes at 15:55) |

Every number on 2012 to 2026-01-09 is on seen data: the XAUUSD feed was used to build v1. The
check period was not used to choose any setting here.

## 2. OPEN: the opening candle (after SCUTA's "first 5-min candle vs 12 EMA", Nasdaq)

**SCUTA's rules, as their Python code does them:**

- The signal is the first 5-minute candle of the New York cash session (09:30).
- Close above EMA(12) → buy; below → sell; equal → no trade.
- Entry at the next candle's open.
- The SL starts at the other side of the signal candle (its low for a buy).
- After every closed candle, the SL moves to that candle's low (high for a sell) when that is
  better. A stop hit exits at the SL, or at the bar's open when it gapped through.
- Otherwise the exit is at the session end. One trade a day.

**For gold, a grid of 36 settings, tuned on 2012-2021:**

| Setting | Values |
| --- | --- |
| Signal candle (New York) | 08:20 (COMEX open), 08:30 (US data), 09:30 (SCUTA's) |
| Direction | EMA (close vs EMA(12, 5m) over all 5m bars), COLOR (close vs open) |
| Minimum candle range | 0, 1, 2 × ATR(14, 5m) at the bar before the signal |
| Management | BAR (SCUTA's trail), M8 (v1's: break-even at +1 R, then the swing trail) |

- **Choice.** The best mean net R on 2012-2021, among settings with at least 60% of the years
  positive and at least 300 trades.
- **SCUTA's own rules on gold** (09:30, EMA, no minimum, BAR) are reported as a reference row,
  whatever they show.

## 3. Level breaks in LVL4H's family (fixed, no tuning)

Each uses LVL4H's frozen engine and settings: a stop entry with the break at the level's first
touch of the day, 02:00-16:00 New York, D = 0.75 × ATR(14, 4h), cost cap 0.05, M8, horizon 200
bars, one trade at a time.

| Name | Levels |
| --- | --- |
| PIVW | the daily pivots R1, S1 (PIVOT's levels with LVL4H's distance and cost cap) |
| ASIA | the high and low of the Asian session, 19:00 to 02:00 New York, the same trading day |
| PWHL | the previous week's high and low (weeks of trading days, Monday to Friday) |

## 4. Decision (per candidate)

A candidate goes to the demo as a shadow strategy only if all of these hold:

1. Net R > 0 on 2012-2021, with at least 60% of the years positive. For OPEN, this is how the
   setting was chosen.
2. **Net R with slippage > 0 on the check, 2022 to 2026-01-09.**
3. Net R with slippage > 0 on FxPro `GOLD`, 2016-02 to 2026-11-05.

Otherwise it is dropped. The FxPro 2026 part (2026-01-12 to 2026-11-05) was used by none of
these choices. It is reported by itself.

## 5. Reported beside the decision (decides nothing)

- Results by year, buys against sells, and the cost and slippage as a share of R.
- The correlation of daily net R with LVL4H, and LVL4H plus the candidate together.
- **NFP days.** The first-Friday rule of the BLS: the third Friday after the week that holds the
  12th.
  - It ignores shutdowns and holiday moves.
  - Results are shown on NFP days and on other days. Nothing is filtered.
  - CPI needs a calendar source, which is still open.

## 6. Count

39 settings: 36 OPEN and 3 level breaks. They are logged in `docs/phase3/TRIALS.md`, as
exploratory looks of the commercial track.

## 7. Outcome (2026-11-07)

Net R with slippage a trade. The FxPro results run from 2016-02 to 2026-11-05; the last column is
2026-01-12 to 2026-11-05.

| Candidate | 1. 2012-2021 (years +) | 2. Check 2022-2026 | 3. FxPro | FxPro 2026 | Decision |
| --- | --- | --- | --- | --- | --- |
| OPEN (best: 09:30, COLOR, 2 × ATR, M8) | −0.127 (40%); no setting eligible | +0.063 (n 175) | −0.102 | −0.146 (n 48) | **dropped** |
| OPEN-SCUTA (reference) | −0.991 (20%) | −0.207 | −0.620 | +0.000 | reference only |
| PIVW | +0.070 (62%) | +0.039 (n 800) | +0.022 (n 1,213) | +0.102 (n 138) | **shadow** |
| ASIA | +0.011 (88%) | +0.039 (n 1,268) | +0.016 (n 1,940) | +0.134 (n 231) | **shadow** |
| PWHL | +0.081 (62%) | +0.096 (n 382) | +0.095 (n 605) | −0.074 (n 62) | **shadow** |
| LVL4H (v1, for comparison) | +0.151 (100%) | +0.102 | +0.073 | +0.007 | v1 |

**OPEN.** None of the 36 settings made money on 2012-2021: the best was −0.082 before slippage.

- **SCUTA's own rules make money before costs on gold.** Their gross is +0.27 R a trade on
  2012-2021 and +0.06 on 2022-2026.
- **But the stop is the opening candle's other side, which is small.** The median stop is $0.97
  on 2012-2021 and $2.26 on 2022-2026. The median cost is $0.33 and $0.15, or 36% and 7% of R.
- **The trail on every bar ends most trades after two bars.**
  - All the exits are stops, and only 24-28% of trades win (SCUTA's report: 57% on the Nasdaq).
  - Their code has no costs.

**The three level breaks pass. The cost was PIVOT's problem, not its levels:**

- With LVL4H's distance and cost cap, the cost falls from 0.109 to about 0.025 R a trade.
- But the edges are small: +0.016 to +0.095 R on FxPro, about one to two standard errors.
- They also overlap LVL4H. Their daily net R correlates +0.57 (PIVW), +0.39 (ASIA) and +0.38
  (PWHL) with LVL4H's on FxPro.
- With LVL4H on FxPro (LVL4H alone: +0.073 with slippage):
  - PIVW gives +0.049 and ASIA +0.040, so they lower the mean a trade but add trades.
  - PWHL gives +0.080.
- PWHL has the best history but lost in 2026: −0.074 over 62 trades, within noise.

**Before the demo, they need:**

- GoldLive strategies with their own magic numbers.
- An account-level cap on open risk, since five strategies may hold trades at the same time.
- A check against Python in the Strategy Tester, as v1 had.

## 8. In the EA (2026-11-07, Fadi: "Yes, add them")

`tools/mt5/GoldLive.mq5` trades the three shadow strategies beside v1:

| Input | Default | What it does |
| --- | --- | --- |
| `TradePIVW`, `TradeASIA`, `TradePWHL` | true | turn each shadow strategy on or off |
| `ShadowRiskPct` | 0.25 | % of equity a shadow trade; v1 keeps `RiskPct` |
| `MaxOpenRiskPct` | 2.0 | cap on the money the EA's open trades (to their current SL) and pending orders would lose. Only each strategy's largest pending order counts, since one fill deletes the rest. An order over the cap is skipped and logged (`SKIP`, "risk cap"); 0 turns it off. With the default risks (0.5% × 2 + 0.25% × 3 = 1.75%) it does not bind; it limits a raised risk |
| `MagicBase` | 20261106 | LVL4H +0, PIVOT +1, PIVW +2, ASIA +3, PWHL +4 |

- Each strategy runs as LVL4H does: one trade at a time, each level once a day, its own orders
  and M8.
- Their levels come from the terminal's bars, as v1's do.
  - PIVW trades PIVOT's R1 and S1 with its own distance, so both may be in at the same level.
  - ASIA's high and low are logged at the first bar of the window (`ASIA` event).
  - PWH and PWL are logged with the day's levels (`DAY` event).
- Python has no risk cap. So the tester check runs with `MaxOpenRiskPct = 0`.

**The tester check** has the same settings as the second v1 run:

- GOLD, M5, 2026-01-12 to 2026-10-21, "1 minute OHLC".
- `FixedLots = 1`, `MaxOpenRiskPct = 0`, and since the guards (`GOLD_V1.md`, stop rules 4)
  `DailyLossPct = 0`, `MaxDrawdownPct = 0`.

Then run `python -m app research gold-live check --reference fxpro`. The reference
(`gold-live fxpro`) now holds the shadow trades too, and the report lists matches by strategy.

### The tester check (2026-11-07)

The five strategies were run with the settings above. `gold_live_check.md` compares the run with
Python.

**The EA matches Python:**

| Item | Value |
| --- | --- |
| Trades | 694 EA, 692 Python |
| Matched on strategy and signal bar | 682 (98.6%), all in the same direction |
| Gross R per trade, correlation | 0.999 |
| Net R a trade, Python / EA | +0.096 / +0.096 |

| Strategy | Matched (Python / EA) | EA trades | EA net R a trade | EA sum |
| --- | --- | --- | --- | --- |
| ASIA | 211 (216 / 216) | 216 | +0.182 | +39.2 R |
| PIVW | 130 (131 / 131) | 131 | +0.140 | +18.3 R |
| LVL4H | 151 (153 / 155) | 155 | +0.046 | +7.2 R |
| PIVOT | 132 (133 / 133) | 133 | +0.035 | +4.7 R |
| PWHL | 58 (59 / 59) | 59 | −0.051 | −3.0 R |

- The tester's result at 1 lot was +$260,213 (PF 1.33).
- The 10 Python-only and 12 EA-only trades are the known differences of `GOLD_V1.md`: the same
  levels filled one bar apart.
- These months (2026-01-12 to 2026-10-20) were used by no choice of the shadow strategies.
  - But the strategies made most of their gain by August.
  - In Python on the same feed, September and October lost −4.5 R and −18.2 R for the five
    together.
- **The shadow strategies are ready for the demo.** The demo runs with the defaults:
  `ShadowRiskPct = 0.25`, `MaxOpenRiskPct = 2`.

### Real ticks, 2026-10-21 to 2026-11-07 (2026-11-08)

These days come after every earlier run and every choice. The run used "Every tick based on real
ticks", with `FixedLots = 1` and the guards at 0. FxPro had no real ticks for 385 of the 17,940
minutes (on 2026-11-05), and the tester generated those.

- **The EA matches Python.**
  - 39 of Python's 40 trades matched, all in the same direction, with a gross R correlation of
    1.00.
  - The EA took 44 trades. 4 of them came on 2026-11-06, which the export does not hold.
- **Every strategy lost:**

| Strategy | Trades | Winners | EA net R a trade | Sum |
| --- | --- | --- | --- | --- |
| ASIA | 16 | 3 | −0.50 | −8.1 R |
| LVL4H | 9 | 2 | −0.63 | −5.7 R |
| PIVOT | 8 | 1 | −0.71 | −5.7 R |
| PIVW | 8 | 2 | −0.58 | −4.7 R |
| PWHL | 3 | 1 | −0.37 | −1.1 R |
| All | 44 | 9 | −0.57 | −25.2 R |

At the demo's risks (0.5% v1, 0.25% shadow), these 44 trades lost 9.1% of the account. This is
the same run of losses as September and October (`GOLD_V1.md`, stop rules: rule 2 would have
stopped the EA).
