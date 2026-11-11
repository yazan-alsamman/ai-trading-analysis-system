# Discovery plan: markout map first (second registered round)

**Status: PLAN, corrected 2026-11-11 from the proposal "DISCOVERY PLAN MARKOUT" (Fadi). Nothing
here is registered, approved or run.** The next step is `PREREG_2.md` (sections 4-8 frozen, with
seeds and a power statement), approved by Fadi before any outcome is computed.

Branch: `ai/freeze-rules-v1`. Read with `ai-service/CLAUDE.md`, `docs/strategies/FINAL_REPORT.md`,
`docs/strategies/GOLD_V1.md`, `docs/phase3/TRIALS.md`.

Every existing rule stays: closed bars only, `HistoryExport` only, the five non-gold lockbox files
sealed until P9, every look logged in `TRIALS.md`, no rule changed after a count or a result. The
frozen strategies (L1, S1-S8) and the demo's five gold strategies do not change.

## 0. What was corrected in the proposal, and why

| # | The proposal said | Corrected |
| --- | --- | --- |
| 1 | Q1: the five pending-order break strategies were tried "outside this repo"; how were they measured? | They are in this repo (commercial track): `GOLD_V1.md` (LVL4H, PIVOT), `GOLD_SHADOW.md` (PIVW, ASIA, PWHL), the lockbox exam `GOLD_LOCKBOX_EXAM.md` (+0.052 R a trade on real ticks, SE 0.071), FxPro's GOLD feed `gold_fxpro.md`, and the live demo since 2026-11-10 |
| 2 | The lockbox (2026-01-10 on) is sealed for P9 | **The XAUUSD lockbox file was opened once on 2026-11-05 for the exam**, and FxPro's GOLD feed to 2026-11-05 has been read by about 30 commercial-track looks. Gold has no unseen history; only the forward demo is. The five other lockbox files stay sealed |
| 3 | Deflated Sharpe with N = 26 + this round | `TRIALS.md` holds the 27 registered trials **and 32 dated commercial-track entries, many with 4-48 settings each**. N counts every setting (section 8) |
| 4 | F4 (session hand-over) is new | Tested 2026-11-10 (`GOLD_TIME.md`: intraday momentum, London to New York, the night): every setting within about ±0.08 R of 0. **F4 is dropped** |
| 5 | F5 (level touches and breaks) as a full family | Breaks were tested many times (the five, `GOLD_ROUND.md`, `GOLD_PBK.md`, Addendum 2 with placebo levels). **F5 keeps only the placebo test of grids** (round numbers and the "time zones" grid against randomly shifted grids), which was never run |
| 6 | F1 (the dollar) as new | `GOLD_USD.md` found no lead of EURUSD over gold at 5 minutes (next-bar correlation −0.001). F1 keeps only the different claim: **a gold move the dollar does not confirm reverts** |
| 7 | Limit fills simulated on FxPro ticks for the whole period | **FxPro's server keeps real ticks only from about 2026-01** (`FINAL_REPORT.md` §9b). Earlier limit fills need Dukascopy ticks (`app/data/dukascopy.py`), or the markouts stay on M1 bars (enough for h ≥ 1 minute) |
| 8 | News needs a calendar "none today" | `tools/mt5/ExportCalendar.mq5` (new) exports MT5's calendar with history (time, importance, actual, forecast); BLS (NFP, CPI) and the Fed (FOMC) dates check it. `gold_shadow.nfp_days` is a rule, not a calendar |
| 9 | (not known to the proposal) | **A lead and a prior exposure for F3:** in `GOLD_LOSS.md` the five's trades entered at the US data minutes (08:25-08:35, 09:55-10:05 New York) were the best bucket in both periods: +0.263 R on 2012-2021 and +0.287 on the check (7% of the trades). F3 is the most promising family, and this look must be disclosed in PREREG_2 |

## 1. What the first round and the commercial track tell us

| Fact | Number | Implication |
| --- | --- | --- |
| No registered entry rule has a net edge (L1, S1-S8) | all `unvalidated` | do not design a thirteenth full strategy |
| The five gold breaks on FxPro, 2016-2026 | +0.026 R a trade with slip, largest drawdown about 134 R | the best found is about one standard error from 0 |
| Gold after the five's entries (`gold_path.md`) | half the trades ahead at any horizon; +0.04 D in the first 5-15 minutes, flat after | a small, fast push; the rest is noise |
| No exit beats M8 with the 16:45 close | `GOLD_EXIT`, `GOLD_SL`, `GOLD_HOLD`, Stage D | management is closed |
| Models on the five's trades | Brier skill ≤ 0 (`GOLD_FADE.md`) | no entry feature tells winners from losers |
| Real cost, MT5 tester 2024 H1 | gold 0.039 R, EURUSD 0.140 R | gold is the cheapest per R; EURUSD scalps are dead on commission |

**Lesson:** the binding constraint is the ratio of predictable move to cost. The markout map
measures that ratio directly.

## 2. Execution fact (kept from the proposal)

On MT5 a Buy Limit fills at the Ask when the Ask reaches the order price, a Sell Limit at the
Bid. A limit order does not earn the spread; it only removes entry slippage, and it fills more
often when the move continues against it (adverse selection). Limit-entry tests need ticks.

## 3. The method

1. Define **events**: a timestamp, an instrument, a signed direction hypothesis. No SL, no TP.
2. **Markout** m(h) = s x (mid(t0 + h) − mid(t0)), h = 1, 5, 15, 30, 60, 120, 240 minutes; mid =
   bid + spread / 2 from M1 bars.
3. **Cost units** z(h) = m(h) / c(t0), c(t0) = the spread at t0 + the round-trip commission
   ($0.07 an ounce on gold), in price units. Also at 2x cost, and m(h) in ATR(14, 1h) units.
4. Compare with **E0** (200 matched random timestamps: same instrument, year, New York hour,
   volatility bucket) and the family's **placebo** (the claimed ingredient removed).
5. Only a cell above a pre-set multiple of cost gets a trade designed (section 9).

## 4. Event families (the only ones in this round)

| # | Family | Event and hypothesis | Placebo | Data |
| --- | --- | --- | --- | --- |
| **F3** | After scheduled US releases | t0 = the release minute (NFP, CPI, FOMC; then the other high-importance USD releases), events at +1, +5, +15 minutes signed by the first move. A: drift; B: reversal | the same New York minutes on days without a release | M1 bars + `ExportCalendar.mq5`, checked against BLS / Fed dates |
| **F2** | Forced-flow windows | LBMA PM auction (15:00 London), WM/Reuters 16:00 London, COMEX settlement (13:30 New York), month-end. Signed by the move into the window; hypothesis: it reverts after | the same minutes on other days | M1 bars |
| **F1** | Unconfirmed move | gold moves ≥ k x ATR in w minutes while the dollar proxy (EURUSD, USDJPY, GBPUSD, USDCAD) moves the other way or not at all; hypothesis: it reverts. Mirror: a confirmed move continues | a shuffled dollar series | M1 bars of the five instruments (to 2026-01-09: their lockbox is sealed) |
| **F5p** | Grid placebo | rejections and breaks at round numbers ($25, $50, $100) and at an evenly spaced $75 grid (the "time zones" indicator) | the same grids shifted by a random offset | M1 bars |
| F6 | Conditioning only | spread, tick rate, realised volatility bucket, as features for the model (section 6), never a signal | | M1 bars; ticks only for 2026 |

Instrument: **gold first** (the cheapest per R). The other five only as F1 drivers in this round.

**Trial budget (fixed before running):** at most 4 families x 8 parameter cells x 7 horizons on
gold = 224 cells. Each cell is a logged trial. No cell is added after results without a dated
addendum.

## 5. Periods and exposure (stated plainly in PREREG_2)

| Period | Exposure so far | Role |
| --- | --- | --- |
| 2012-2017 (XAUUSD) | L1 development, commercial-track tuning | detector debugging only, no markout read |
| 2018-2021 (XAUUSD) | L1, S1-S8, commercial-track tuning | **discovery**: the map |
| 2022 to 2026-01-09 (XAUUSD) | S1-S8, holdout, commercial-track checks | **confirmation**: only cells that pass discovery, read once |
| 2026-01-10 to 2026-11-05 (XAUUSD lockbox, FxPro GOLD) | the exam, about 30 commercial-track looks | second consistency check, exposure disclosed |
| Forward (the demo and its paper log) | unseen | the decisive evidence |

## 6. The AI layer: a toxicity meta-label on events

- Unit: one event of any family; expected 10^4-10^5 on gold.
- Label: z(h*) at the family's registered horizon above +1 cost unit, or not.
- Features, all known at t0 and scale-free: family, move size in ATR, dollar confirmation, time
  of day, distance to the nearest grid level, spread and volatility percentiles, minutes from the
  nearest release, surprise (actual − forecast, scaled) for F3.
- Models: LR, then LightGBM; an encoder only if both show Brier skill > 0. Walk-forward on the
  discovery period (six-month windows, purge + 1-day embargo), acceptance as `PREREG_P4.md`
  (Brier skill > 0, ECE < 0.05).
- Question (H2'): does conditioning on predicted toxicity raise a family's after-cost markout above
  its unconditional value and above E0?

## 7. Decision rules (to fix in PREREG_2)

1. **Discovery size gate:** mean z(h) ≥ 2 cost units at 1x cost and ≥ 1 at 2x, and the E0- and
   placebo-adjusted difference has a 4-week block bootstrap t ≥ 3 (B = 20,000).
2. **Multiplicity:** Benjamini-Hochberg at 10% over all cells of the map, then Holm over the
   survivors on confirmation.
3. **Confirmation:** same sign, z(h) ≥ 1.5 cost units, Holm-adjusted p < 0.05.
4. **Stability:** no single year carries more than half of the effect.
5. **PBO** for the whole map; Deflated Sharpe with N = every setting in `TRIALS.md` + this round.
6. **Stop rule:** if no cell passes discovery, the round ends with a negative report. No second
   map on the same data.

## 8. From a surviving cell to a signal

1. One trade per cell from its markout curve: horizon h*, SL a registered multiple of ATR chosen
   for cost per R (not tuned on outcomes), exit by time or M8.
2. Market entry if the curve moves at once; a limit entry (Dukascopy ticks before 2026, FxPro
   ticks after) only if the curve shows an early adverse dip, with fill rate and adverse
   selection reported.
3. Registered as an addendum; E0, 2x costs, swap scenarios; the MT5 real-tick replay on 2026.
4. A shadow strategy on the demo, judged by the demo's stop rules (`GOLD_V1.md`).

## 9. Data and tooling

| Need | Source | Status |
| --- | --- | --- |
| News calendar with history | `tools/mt5/ExportCalendar.mq5` → `<Common>/Files/calendar_history.csv`; BLS and federalreserve.gov dates as the check | script written 2026-11-11, not run. The calendar's times are server time: convert with Europe/Athens, as every bar |
| Spread and cost | the stores' recorded spread + $0.07 commission | exists |
| Dollar proxy | EURUSD, USDJPY, GBPUSD, USDCAD in the store (about 92% of the DXY weight) | exists, to 2026-01-09 |
| Ticks | Dukascopy before 2026; FxPro real ticks from 2026-01 | Dukascopy downloader exists (bars); a tick path is new work |
| Yield proxy | none in the account (Q3) | F1 runs on the dollar alone unless one is found |

New code behind the existing guards: `app/discovery/events.py` (detectors, pure functions on
closed bars, no-look-ahead tests), `markout.py` (curves, cost units, E0, placebos), `map.py` (cells
and multiplicity); `python -m app discovery {count,map,confirm}`. Reports in `docs/discovery/`.

## 10. Stages

| Stage | Work | Gate |
| --- | --- | --- |
| D0 | This plan; the calendar exported and checked against BLS / Fed | Fadi's go (2026-11-11: "كمّل بـ D1–D2") |
| D1 | Calendar importer, cost unit, dollar proxy, quality report | NFP and FOMC times match the official dates |
| D2 | Event detectors + tests; **counts only** per family, cell and year | enough events per cell; no outcome |
| D3 | `PREREG_2.md` frozen (tag) | approved |
| D4 | The map on 2018-2021 | rules 1-2, or the round ends |
| D5 | Confirmation (2022 to 2026-01-09), then the model | rules 3-5 |
| D6 | Trade design, addendum, replay, 2026 consistency | section 8 |
| D7 | Shadow on the demo, paper log | the demo's stop rules |

## 11. Honest expectations

- **Most likely: most cells fail the size gate.** The breaks' push is about 0.04 D against a cost
  of about 0.02-0.08 R, far from 2 cost units. A negative map is still a thesis chapter: it says
  where and by how much.
- F3 has the one lead from this data (the data-minute trades), so it is the family to run first.
- Published effects decay (McLean and Pontiff, 2016); the gold fix became an electronic auction in
  2015, so older studies of the fix may not hold.
- Every historical period of gold has been seen; only the forward demo is clean.
- The service stays advisory. Nothing here is financial advice.

## 12. Open questions for Fadi

- **Q2.** How far back does the MT5 calendar go on this terminal? (Run `ExportCalendar.mq5`.)
  **Answered 2026-11-11:** 154,224 releases, 2010-01-01 to 2026-12-10, 8 currencies, 13,539 of
  high importance (`calendar_check.md`). MT5 gives the times at the server's offset at export,
  so `time_utc` is the true UTC: NFP, CPI, GDP at 08:30 New York in 99.5-100% of releases, ISM
  at 10:00 in 100%, the Fed decision at 14:00 (14:15 and 12:30 in 2010-2012, as it was). The NFP
  dates differ from the BLS rule on 18 days, all holiday moves and the 2013 and 2025 shutdowns,
  where the calendar holds the real dates. **F3 uses the calendar** (`app/discovery/calendar.py`,
  `data/processed/calendar.parquet`).
- **Q3.** Is a US yield instrument available on FxPro (for example a bond or yield CFD)?
  **Answered 2026-11-11 from Dukascopy's public datafeed** (probed one day a year, nothing else
  read): `USTBONDTRUSD`, a US Treasury bond CFD (its price moves against long yields), M1 from
  2018 (thin in early 2018: 34 bars with volume on 2018-03-07, 721 on 2019-03-06), and
  `DOLLARIDXUSD`, the dollar index, M1 from 2018. So F1 can use the real dollar index and a
  bond price beside the four-pair proxy, from the start of the discovery period; the first
  usable day of each is fixed in D1 from coverage alone. Equity indices (US500, NAS100) are not a
  yield proxy (their link to yields flips sign by regime); `USA500IDXUSD` is on the same feed if a
  risk-sentiment feature is wanted for the model later.
  **On FxPro (seen 2026-11-11):** bond ETF CFDs under ETFs > Bonds, of which `TLT.O` (iShares 20+
  Year Treasury) is the useful one. It trades in US stock hours only (09:30-16:00 New York), so
  the research uses Dukascopy's near-24-hour bond series; `TLT.O` matters if an F1 cell survives,
  because a live EA can read it from the broker and cannot read Dukascopy.
- **Q4.** May silver be used as a feature only? (`CLAUDE.md`: no other metals as instruments.)
  **Answered (Fadi, 2026-11-11): yes, as a feature only**, never as a traded instrument. The Addendum
  2 data (`data/confirm/XAGUSD`) was read once for the level effect. **Export received 2026-11-11:**
  `XAGUSD_M1_201001040000_202601092359.csv` (FxPro, to 2026-01-09, so nothing past the lockbox
  start). Like GOLD's export it holds daily bars to 2015-09-10, hourly bars to 2016-01-08, M1
  bars from 2016-01-08 14:38 and spreads from 2016-01-18: **silver features start 2016-01-19**,
  which covers the discovery period (2018-2021). Only its header and its first and last lines have
  been read.
- **Q5.** Accept the gates of section 7 (2 cost units, t ≥ 3) and the 224-cell budget?
  **Answered (Fadi, 2026-11-11): accepted as written.**

## 13. References (verify each before citing)

As in the proposal: McLean and Pontiff (2016); Harvey, Liu and Zhu (2016); Bailey, Borwein,
Lopez de Prado and Zhu (2017); Osler (2003); Caminschi and Heaney (2014); Smales and Yang (2015);
Gao, Han, Li and Zhou (2018); Batten et al. (2018); Hauptfleisch, Putnins and Lucey; Easley, Lopez
de Prado and O'Hara (2012); MetaTrader 5 help, "Basic Principles".

## 14. Progress

- **D1 (2026-11-11).** Calendar imported and checked (`calendar_check.md`). Silver stored from the
  FxPro export, 2016-01-19 to 2026-01-09 (3,515,949 minutes; `drivers.md`). The dollar index and
  the bond series downloaded from Dukascopy and stored (`python -m app discovery drivers download`,
  then `store`): the dollar index from 2018-01-02, the bond from 2018-01-04 (thin in 2018). Cost unit c(t0) = the event bar's
  recorded spread + $0.07: median $0.49 (2012) falling to $0.12 (2021-2022) and $0.22 (2025).
- **D2 (2026-11-11), counts only.** Detectors `app/discovery/events.py` with hand-built and
  no-look-ahead tests (`tests/test_discovery_events.py`). `counts.md`: F2 about 1,030 events per
  window cell in 2018-2021 (month-end 48), F3 HIGH about 1,380 and TOP3 126 per delay, F5p 665 to
  2,582 per grid cell. F1 (from 2018, the drivers' start): CONF cells 2,182 to 9,266 events in
  2018-2021, UNCONF 299 to 3,070 (UNCONF-k1-w15 is thin; 2018 is thin in every F1 cell, from the
  bond data). 145,845 events in all. No price after an event has been read. Next: `PREREG_2.md`.
- **Data faults found, D1 corrected (2026-11-11, before any outcome).** (a) Dukascopy's dollar index
  has about 1,525 fake one-minute spikes in 2018 (89.41 to 86.99 and back within a minute), 1-10 a
  year after; the bond about 3,700 a year in 2018-2019 (68 to 232 within a minute), 2-48 in
  2020-2024, and in 2025-2026 its large bars fall at 08:30 New York releases (real moves). **Decision
  (Fadi): F1 reads the dollar index from 2019-01-01 and the bond from 2020-01-01** (`events.DXY_FROM`,
  `BOND_FROM`), so F1's discovery years are 2020-2021 only; recounted (`counts.md`): CONF 1,379
  to 6,022 events in 2020-2021, UNCONF 221 to 2,153 (UNCONF-k1 thin). (b) FxPro's M1 exports (GOLD, NAS100,
  XAGUSD) hold summary bars in 2017-2022 (real volume 0, tick volume above 5,000, mostly at 00:00
  server time) that carry the day's whole high and low (`GOLD_MAGNET.md` §6); silver was re-stored
  without them. The XAUUSD research store does not have them. (c) The calendar's repeated rows are
  real (euro-area and German releases at the same minute; the 2013 shutdown's double releases).
