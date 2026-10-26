# Pre-registration: signal strategies, trade management and AI layers

**Status: DRAFT, not registered.** First written 2026-10-25; revised 2026-10-25 after Fadi's
review of the decision tables (C1-C8, D1-D13, N1-N11, R1, the four final refinements). It becomes
binding when Fadi approves it as written and the approval date and commit are filled in. Until
then no outcome of any strategy, bundle or model here (R, hit rate, exit mix, MFE / MAE, equity)
may be computed, printed or plotted, on any period. Counts are allowed under section 12; they
choose nothing.

| Field | Value |
| --- | --- |
| Approved by | _(Fadi)_ |
| Approval date | _(YYYY-MM-DD, before any count or outcome is computed)_ |
| Code version frozen at approval | _(commit)_ |
| Seeds (E0, bootstrap) | _(fixed at approval)_ |

## 1. Why, and what is not a goal

P3 and P4 closed with H1 and H2 not supported (`docs/phase4/CLOSEOUT_P4.md`). The service stays a
signal detector and giver, with signals split into scalp, intraday and swing, trade management on
TP and SL, and AI layers for range, regime, exits and direction. Each strategy here is an
independent hypothesis with prior support in published work or common practice; none was added
to reach a number of signals.

**Signal frequency is descriptive only, never an acceptance criterion (Fadi, 2026-10-25).** Zero
signals on a day is a valid outcome. No strategy, rule or threshold is loosened, added or chosen
to produce more signals, and a strategy is never accepted or rejected for how often it signals.
Count statistics (section 12) describe the opportunity distribution and nothing else.

## 2. Structure: three layers, four test families, four levels of evidence

A signal is an **entry** (a strategy), then **management** (a bundle of TP and SL rules), and
optionally **AI** (a range forecast, a regime router, an exit model, a direction filter). Each
layer is tested on its own, in order:

| Family | Hypotheses | Tests | Correction |
| --- | --- | --- | --- |
| **A** primary strategies | S1-S6 under M0 (section 8) | 6 | Holm over 6 |
| **B** exploratory strategies | S7-S8 under M0 | 2 | Holm over 2 |
| **C** management | one per signal type (section 9) | 3 | Holm over 3 |
| **D** AI | one per model, its activation claim (section 9) | 4 | Holm over 4 |

Four levels, kept apart:

1. **Strategy acceptance:** families A and B, the holdout check and P9 (sections 8, 10).
2. **Management and AI activation:** families C and D (section 9).
3. **Portfolio reports, descriptive** (section 11): the validated-only portfolio is the primary
   product-quality report; the all-served portfolio is a separate descriptive report. Neither is
   statistical proof that the combined service works or is commercially suitable.
4. **Product readiness, operational** (section 13). It never raises a statistical status.

A strategy that passes its own test does not show that the combined service is robust.

L1 keeps its P3 / P4 result, its frozen rules, its 48-bar horizon and its original management
(`labels.resolve`). It is served under the `intraday` label for display only: the intraday forced
exit does not apply to it, it is not in the family C pool, and its rollover and swap exposure is
reported (section 6).

## 3. Rules common to every strategy

- Closed bars only; higher frames from closed lower bars, used only after they close. Times are
  New York wall-clock unless a rule names another zone (Europe/London for S1 and S8).
- **Entry at market at the close of the signal bar** (`entry_mode = "close"`, as L1).
- Every trade has entry, SL, TP (or none, for trailing bundles) and a horizon in bars of its entry
  frame. Labels and costs as `app.setups.labels.resolve`: ambiguous bar = SL, SL slippage,
  round-trip cost `spread + max(cost_extra_frac * spread, cost_extra_min)` with the signal bar's
  mean spread, 2x stress run, realised net R kept, plus swap (section 6).
- **Cost filter:** no signal when the round-trip cost plus the SL slippage exceeds 0.15 R.
- **One active trade per strategy per instrument** (`REJECTED`, `position_open`).
- **Conflict rule** (for served signals and the portfolio reports): a signal opposite to an active
  served trade on the same instrument from another strategy is marked `conflict` and not served,
  unless an activated A2 router decides.
- Liquid window 02:00-16:00 New York for the signal bar, no US market holiday
  (`market_holidays`); S3 holidays only.
- Indicators from `libs/indicators`; a channel a breakout is measured against uses the bars
  **before** the signal bar (`donchian` includes the current bar, so it is shifted by one). The
  session VWAP with bands for S6 is new code in ai-service (`libs` `vwap` is anchored at 00:00 UTC
  and has no bands), weighted by tick volume.
- Parameters are fixed a priori from published or common versions, **not tuned on any data**. A
  change after approval is a new version and a new trial.

## 4. Signal types

| Type | Entry frame | Holding | Forced exit | Strategies |
| --- | --- | --- | --- | --- |
| **Scalp** | 5m | up to 2 h | horizon | S4, S5, S6, S8 |
| **Intraday** | 15m, 1h | same trading day | at the close of the bar ending 16:45 New York | S1, S2, S7 (L1: label only, section 2) |
| **Swing** | 4h | days | horizon; open over weekends allowed | S3 |

No scalp or intraday trade is held over the Friday close. Scalp and intraday trades never cross a
rollover, so their swap is zero by construction.

## 5. Strategies

### Primary (family A)

**S1 LB, London breakout of the Asian range (intraday, 15m).** Asian range: high and low of the
15m bars opening 00:00-06:59 Europe/London. Filter: width 0.3-1.2 x ATR(14, D1) of the previous
closed D1 bar. Window: bars opening 07:00-10:59 London. Buy: first close above range high
+ 0.1 x ATR(14, 15m); sell: first close below range low - 0.1 x ATR(14, 15m); one signal per
instrument a day. SL: range midpoint -/+ the spread. TP 1.5 R. Horizon 32 bars.

**S2 MR, Bollinger mean reversion in a range (intraday, 1h).** ADX(14, 1h) < 20. Buy: close below
the lower band (20, 2.0) after a close inside; sell mirrored. SL 1.5 x ATR(14, 1h). TP: the middle
band at the signal bar, R in [0.75, 3] else `r_out_of_range`. Horizon 24 bars.

**S3 TF, Donchian trend breakout (swing, 4h).** Buy: close above the highest high of the 55 bars
before; sell mirrored. SL 2 x ATR(20, 4h). TP 3 R. Horizon 60 bars.

**S4 ORB, New York opening-range breakout (scalp, 5m).** Opening range: high and low of the six 5m
bars opening 08:30-08:59 New York (US data and the COMEX gold open). Filter: width 0.25-1.5 x
ATR(14, 1h) at 08:30. Window: bars opening 09:00-10:29. Buy: first close above range high
+ 0.1 x ATR(14, 5m); sell mirrored; one signal per instrument a day. SL: range midpoint -/+ the
spread. TP 1.5 R. Horizon 24 bars.

**S5 PB, trend pullback (scalp, 5m entry, 1h trend).** Trend up: the last closed 1h bar closes above
EMA(50, 1h) and EMA(50, 1h) is higher than five 1h bars before; down mirrored. Buy in an
up-trend: the 5m bar's low touches or crosses EMA(20, 5m), it closes above EMA(20, 5m) and above
its open. SL: below the lowest low of the last six 5m bars - 0.1 x ATR(14, 5m) - spread, at least
1.0 x ATR(14, 5m) from the entry. TP 1.5 R. Horizon 24 bars.

**S6 VR, VWAP reversion in a range (scalp, 5m).** Session VWAP anchored at 03:00 New York, typical
price weighted by tick volume, bands VWAP +/- 2 volume-weighted standard deviations. ADX(14, 1h)
< 20. Window: bars opening 04:00-11:59. Buy: the previous bar closed below the lower band and this
bar closes back above it; sell mirrored. SL: 1.0 x ATR(14, 5m) beyond the extreme of the last
three bars. TP: the VWAP at the signal bar, R in [0.75, 3]. Horizon 24 bars.

### Exploratory (family B)

**S7 SQ, volatility squeeze breakout (intraday, 15m).** Squeeze: Bollinger (20, 2.0) inside
Keltner (20, 1.5 x ATR 10) for at least six bars in a row. First close outside the Bollinger band
after the squeeze ends: buy above, sell below. SL 1.5 x ATR(14, 15m). TP 2 R. Horizon 32 bars.
Prior: practitioner pattern, grounded only in volatility clustering; no academic test known.

**S8 FX, fix reversal (scalp, 5m).** Fix: 15:00 London (LBMA gold PM auction) for XAUUSD, 16:00
London (WM/Reuters) for the five pairs. Move m: close at the fix minus close 30 minutes before. If
|m| >= 0.5 x ATR(14, 1h): at the close of the 5m bar ending 5 minutes after the fix, enter against
m. SL 1.5 x ATR(14, 5m). TP: half of m back, R in [0.75, 3]. Horizon 12 bars. Prior: documented
before the 2015 reforms of both fixes; probably weaker since.

### Not registered

Intraday momentum (evidence mainly on equity indices), Asian-session range fade (cost per R is
high), indicator crossovers and candlestick patterns (no evidence after costs), more SMC variants
(L1 already tested). **No count-driven fallback variants** (C2): the six relaxations drafted
earlier (wider S1 and S4 filters, ADX < 25 for S2 and S6, Donchian 20 for S3, S5 without the
slope) are not registered. A variant enters only with its own independently documented trading
hypothesis, as a separate experiment; Donchian 20 is out of scope on that basis.

## 6. Costs and swap

**Measured and assumed.** The recorded spread is the only measured cost. The extra term
`max(cost_extra_frac * spread, cost_extra_min)` and the SL slippage are assumptions (on XAUUSD in
2024 H1 about 60% of the modelled cost, at every frame). EURUSD's recorded spread is zero on most
bars of 2021-2023, so its costs there are understated.

**Swap: no historical data.** The MT5 exports have no swap. Every swap number here is an
**estimated retrospective scenario**, never a historical cost:

| Scenario | Definition |
| --- | --- |
| **W0** | no swap (lower bound of cost) |
| **W1** | the current FxPro rates (one dated snapshot, section 6a) applied to every year, with their signs. Rates reflect the snapshot's interest-rate regime and can be wrong in size and sign for years with other rates |
| **W2** | from official historical central-bank policy rates, nightly (rate of the base minus rate of the quote, minus a fixed markup) / 360 x price per side; the markup per instrument and side is set so that W2 equals W1 on the snapshot date (calibrated on the snapshot only, never on outcomes). Used only if suitable official series cover 2012-2026 for every currency; the series and source are fixed in the stage F addendum before use. **Not applicable to XAUUSD** (no official gold lease-rate series) |
| **W3** | stress: every rollover charged twice the worse side of W1, as a cost, whatever the direction. A sensitivity, not a bound |
| **Decision** | per trade, the more costly of W1 and W2 (W1 alone for XAUUSD, and wherever W2 is not available). Conservative only relative to the modelled scenarios; not a bound on the actual historical cost, and an envelope across trades rather than one consistent scenario |

Every report gives net R under W0, W1, W2 (where available), W3 and the decision scenario, labelled
"estimated retrospective swap". Only S3 and L1 can cross a rollover.

**Rollover convention (D9).** One rollover instant per trading day at 00:00 server time
(Europe/Athens), computed from UTC. That is 17:00 New York, and 18:00 New York in the weeks a year
when US and EU daylight saving differ. A trade open at the instant (entry before it, exit at or
after it) is charged one night times the day weight: `SYMBOL_SWAP_ROLLOVER3DAYS` gives the triple
day, or the per-day multipliers when the terminal exports them. Holiday nights are not added.
Unresolved and documented as assumptions: FxPro's actual rollover instant, its behaviour in the
daylight-saving mismatch weeks, whether the server clock convention changed in the past (four
pairs were exported on shifted clocks before 2022), and the day-count basis of interest modes
(360 assumed).

**Conversion to R.** For a swap value S per lot and night: R = (S converted to the profit
currency per lot) / (risk_price x contract_size); lot size and account currency cancel. By
`SYMBOL_SWAP_MODE`: `DISABLED` 0; `POINTS` R = S x point / risk_price; `CURRENCY_SYMBOL` base to
profit currency (x P); `CURRENCY_MARGIN` by `SYMBOL_CURRENCY_MARGIN` (x P if the base, as is if the
profit currency); `CURRENCY_DEPOSIT` USD to the profit currency (as is for USD-quoted symbols,
x P for USDJPY and USDCAD); `CURRENCY_PROFIT` as is; `INTEREST_CURRENT` P_t x S / 100 / 360 /
risk_price; `INTEREST_OPEN` the same at the open price; `REOPEN_CURRENT` and `REOPEN_BID`
approximated as `POINTS` (labelled). In MT5 a negative value is a charge. USD reports divide by
P for USDJPY and USDCAD.

### 6a. MT5 export needed from Fadi

For each of the six symbols, by its exact name in the account: `SYMBOL_SWAP_MODE`,
`SYMBOL_SWAP_LONG`, `SYMBOL_SWAP_SHORT`, `SYMBOL_SWAP_ROLLOVER3DAYS`, the day multipliers
`SYMBOL_SWAP_MONDAY` to `SYMBOL_SWAP_SUNDAY` if the build has them, `SYMBOL_TRADE_CALC_MODE`,
`SYMBOL_TRADE_CONTRACT_SIZE`, `SYMBOL_POINT`, `SYMBOL_DIGITS`, `SYMBOL_TRADE_TICK_SIZE`,
`SYMBOL_TRADE_TICK_VALUE`, `SYMBOL_CURRENCY_BASE`, `SYMBOL_CURRENCY_PROFIT`,
`SYMBOL_CURRENCY_MARGIN`. For the account: `ACCOUNT_CURRENCY`, `ACCOUNT_SERVER`, account type
(Standard or Raw), swap-free or not, `TimeTradeServer()` and `TimeGMT()` at the export, terminal
build. Optional, the only historical swap facts we could have: account statements with swap lines
(they inform only the dates and positions they cover).

## 7. Management: TP rules, SL rules, bundles

Rules act on entry-frame bar closes (live and research alike). A rule that fires gives an
**alert** (`EXIT_SUGGESTED` or `SL_MOVE_SUGGESTED`, with the reason); the service never touches an
order. **Execution assumption:** an exit alert fills at the next entry-frame bar's open and pays
the SL slippage (the user's reaction); a moved SL is in force from the next bar.

TP side:

| Rule | Definition |
| --- | --- |
| **T1 profit lock** | progress >= 80% of the TP distance at a close, and at least 50% of the horizon elapsed → exit |
| **T2 scale-out** | half closed at +1 R (a resting limit); the rest runs under the bundle's other rules |
| **T3 dead trade** | 50% of the horizon elapsed and the best excursion so far < 0.25 R → exit |
| **T4 momentum fade** | open profit >= 0.5 R, then a bar that engulfs the previous bar against the trade, or a close back across EMA(20) of the entry frame → exit |

SL side:

| Rule | Definition |
| --- | --- |
| **L1 break-even** | at +1 R the SL moves to entry + the round-trip cost |
| **L2 ATR trail** | from +1 R, SL = max(SL, highest high since entry - 2 x ATR(14) of the entry frame); mirrored for sells |
| **L3 structure trail** | from +1 R, SL to the last confirmed swing low (k = 2 on the entry frame) - 0.1 x ATR |
| **L4 time tightening** | from 75% of the horizon, SL to -0.5 R if price is above it |
| **L5 thesis invalidation** | breakouts (S1, S3, S4, S7): two closes in a row back inside the broken range or channel; pullback (S5): a 1h close against EMA(50, 1h); ranges (S2, S6): ADX(14, 1h) > 25 → exit. S8: none |

Bundles (fixed now; each is one policy):

| Bundle | Rules | TP |
| --- | --- | --- |
| **M0** fixed | none | registered TP |
| M1 profit lock | T1 | registered TP |
| M2 protect | L1 | registered TP |
| M3 trend runner | L1 + L2 | none (horizon cap) |
| M4 scale-out | T2 + L1 on the rest | registered TP for the rest |
| M5 active | T3 + T4 | registered TP |
| M6 thesis | L5 + L4 | registered TP |
| **M7 trader** | L5 + T3 + L1 + T1 + T4 | registered TP |
| M8 structure runner | L1 + L3 | none (horizon cap) |

Every trade record keeps the exit reason: `tp`, `profit_lock`, `scale_out_tp`, `trail`,
`breakeven`, `dead_trade`, `fade`, `invalidation`, `time_tighten`, `sl`, `timeout`,
`session_end`. **Success is net R > 0**; the app may show the reasons and a win rate, but every
decision here is on mean net R.

## 8. Strategy tests (families A and B)

**Data.** For strategy S under M0: trades i = 1..n with entry in the primary period
[2018-01-01, 2024-07-01), resolved on bars loaded only up to 2024-07-01; unresolved trades are
excluded and counted. x_i = net R (costs, SL slippage, decision swap scenario). e_i = mean net R of
the 200 E0 replications matched to trade i. d_i = x_i - e_i.

**E0** as `app/research/baselines.py`: same instrument, year and New York hour on the same entry
frame, a fair coin for the direction, the same risk in ATR units, the same TP rule in R, the same
cost filter, labels and costs; 200 replications. E0 enters the primary test only through e_i; the
Monte Carlo SE of mean(e) is reported, and the x component uses no simulation. The
replication-based p-value (share of E0 replication means at or above mean x) is reported as a
secondary comparison.

**Blocks.** Calendar 4-week blocks from Monday 2018-01-01 (28-day steps), the same for all
instruments; a trade belongs to the block of its entry time (UTC). K = number of non-empty blocks.
Bootstrap: K blocks drawn with replacement, B = 20,000; each resample gives the trade-weighted
means x* and d* (sum over drawn blocks / trades in them). Sensitivities: 1-, 2- and 8-week blocks,
reported, not decided on.

**Method condition (N1).** The block bootstrap is applied only when K >= 30. If K < 30 the
strategy is inconclusive and its hypothesis enters Holm with p = 1. This is a condition for the
method, not an acceptance criterion: no strategy is accepted or rejected because of its K, and
K >= 30 does not by itself make the inference valid (limitations in section 14).

**Two tests per component (D4, R1).** For each component c in {x, d}, one-sided tests of a positive
mean:

- **T1 (percentile, by inverting the interval):** p1_c = (1 + #{b : c*_b <= 0}) / (B + 1).
  p1_c <= a exactly when 0 lies below the a-quantile of c*, i.e. when the one-sided (1 - a)
  percentile lower bound is above 0. It is not a test that resamples under the null. It assumes
  the bootstrap distribution of c* around mean(c) approximates the sampling distribution of
  mean(c) around the true mean, and it is first-order accurate. Under skewness it differs from the
  "basic" bootstrap (#{c*_b >= 2 mean(c)}), and neither is exact. The +1 terms keep
  p1 >= 1 / (B + 1); B controls only the Monte Carlo error.
- **T2 (Wald, bootstrap standard error):** p2_c = 1 - F_(K-1)(mean(c) / sd(c*)), with F_(K-1) the
  Student t distribution with K - 1 degrees of freedom. It assumes the mean is approximately normal
  (a central limit argument under weak dependence across blocks), ignores skewness and treats the
  bootstrap SD as the standard error; the t reference allows for that SE coming from only K
  blocks.
- p_S = max(p1_x, p2_x, p1_d, p2_d).

**Why the maximum implements the rule.** The null of H1-S is the union {mean net R <= 0} or
{mean d <= 0}. The decision rejects only when all four tests reject, i.e. when p_S <= the Holm
level. If a component's null holds and its test is level a, P(p_S <= a) <= P(p1 of that component
<= a) <= a (intersection-union, Berger 1982). So p_S is a valid input to Holm to the extent that
T1 is valid, and requiring T2 as well can only shrink the rejection region. The rule is as valid
as its approximate components; no guarantee goes beyond the block-bootstrap and
normal-approximation assumptions stated here.

**Decision (D6).** Holm, one-sided alpha 0.05, within the family (A: 6, B: 2): adjusted
p_(j) = max over k <= j of min(1, (m - k + 1) p_(k)); passed if <= 0.05.

**Reported intervals (not decisions).** Two-sided 95% percentile intervals of mean x and mean d,
and Bonferroni one-sided lower bounds at level 1 - alpha/m (percentile and t forms).

**Smallest effect of interest (D1, N4).** delta*_S = max(0.05 R, a_S). a_S is the median, over the
primary-period signals of S, of the assumed part of the cost model in R:
max(cost_extra_frac * spread, cost_extra_min) + sl_slippage (counted on every trade) + the swap
term below. The recorded spread is the only measured part and is excluded. **a_S is a definitional
allowance based on assumed costs, not a measured bound on the error of the cost model.** The
0.05 R floor is an economic judgement (0.05% of equity per trade at 1% risk), not a statistical
result. delta*_S plays no part in passing; a pass whose lower bound is below delta*_S is reported as
such.

**Swap term of a_S (assumed horizon-based cost allowance).** For each signal, s_h is the estimated
swap, in R, of holding the trade from the signal bar to the end of its registered horizon. It
counts the rollover instants (section 6) inside the full horizon, under the decision scenario. A
negative s_h is a charge. The term entering a_S is max(0, -s_h): estimated charges raise the
allowance, and estimated income counts as zero, so no allowance is reduced by an assumed credit.
Nothing that depends on the exit enters it (no exit time, no realised holding period, no outcome).
It is an assumed allowance on the registered maximum horizon, not an estimate of realised swap.
Strategies whose horizon cannot cross a rollover have s_h = 0 by construction, checked by a test.

**Unvalidated classification (D2, N3; a preregistered conservative rule, not an exact bound).**
For a strategy that did not pass, U_S = max(U1, U2), where U1 = the 95th percentile of x* and
U2 = mean(x) + t_(K-1, 0.95) x sd(x*). Not passed and U_S < delta*_S: **unvalidated**. Otherwise:
**inconclusive**.

U1 assumes that the 4-week blocks are close to independent and exchangeable draws, and that the
percentile method approximates the sampling distribution of the mean (first-order accurate;
skewed R distributions add coverage error). U2 assumes that the mean is approximately normal, by a
central limit argument under weak dependence, with the bootstrap SD as its standard error. Both use
the same blocks, so both share any error of the block assumption.

Taking the larger of the two bounds makes "unvalidated" harder to reach and moves doubtful cases to
"inconclusive". It does not give a guaranteed 95% coverage: each bound is approximate, and the
maximum only inherits the better of the two approximate coverages; it does not correct the shared
block assumption. "Unvalidated" means that under both approximations a net edge of delta*_S or more
is not consistent with the data at about the one-sided 5% level. It is a classification, not a
proof that no edge exists. The bound is computed only for strategies that failed the test and is
not adjusted for multiplicity: both outcomes are "not validated" and are served marked, so a
misclassification between them has limited consequence.

**Power, stated before any evaluation.** MDE(n) = (z_(1-a) + z_0.8) x sigma x DE / sqrt(n), with n
the Stage B labelled count in the primary period, sigma = sqrt(k) for a TP of k R (the break-even
binary value, an upper bound when timeouts are frequent; for S2, S6 and S8 sigma = sqrt(mean k) of
their signals), and DE = 1.2, or 1.5 for S4 and S8 (their signals fire on all six instruments at
the same moment). **DE values are provisional assumptions, not measured facts**: L1's walk-forward
trades show 1.05-1.07 for 1- to 8-week blocks. Reported at a = alpha/m and a = alpha, next to
delta*_S and n_unval(S), the count at which a strategy with zero net edge reaches "unvalidated"
with probability 0.8. They inform the reader before the run and are not used in any decision.
Reference values (sd 1.22, DE 1.2): n_unval 5,300 for delta* 0.05 R, 1,325 for 0.10 R. Trade counts
and active years are reported as indicators only, never as sufficiency rules.

## 9. Management and AI tests (families C and D)

**Family C (management).** Three hypotheses, one per signal type t in {scalp, intraday, swing}:
H_C,t: the walk-forward selection procedure gives a higher mean net R per trade than M0 on the
same entries. The hypothesis tests the procedure "select on train, apply on test", not any single
bundle.

- **Unit:** a trade of a strategy of type t (S1-S8; L1 excluded), with the entry set fixed by M0's
  one-active-trade rule. Every bundle is evaluated on that same entry set, each entry managed on
  its own. delta_i = R_i(bundle chosen for the window of trade i) - R_i(M0).
- **Selection:** for each of the 13 test windows w, the chosen bundle is the one with the highest
  mean net R over the training trades of type t whose exit + 1 day <= the start of w and whose
  entry < the start of w (from 2012). Ties go to the lower index (M0 first). Fewer than 100
  training trades: M0. Nothing else is tuned.
- **Test:** mean delta over all test trades of type t, 4-week blocks, T1 and T2 as in section 8,
  p = max(p1, p2); Holm over the three types, one-sided alpha 0.05.

**Family D (AI).** Four hypotheses, one per model, each its activation claim:

- **D1 (A1 in use):** bundle M9 against the family C procedure, same entries, paired.
  Precondition: A1's pinball loss below its baseline (reported with an interval); if not met, A1
  is not used and D1 is not tested.
- **D2 (A2):** routed mean net R above unrouted, and above the ADX router (intersection-union;
  accepted-subset mean minus reference mean, per resample).
- **D3 (A3):** exit model against the family C procedure, same entries, paired.
- **D4 (A4):** accepted mean net R above all, and Brier skill > 0 (intersection-union).

Unit: the trade, or for A1's precondition the bar, with 4-week blocks. Each model is trained only
on its window's training data (exit-time purge, 1-day embargo, calibration slice as P4). Its
configuration is fixed in its addendum before any fit, with tuning only by inner
cross-validation inside the training data. One primary configuration per model; other
configurations are reported, not tested. Holm over the four, one-sided alpha 0.05, after all four
reports are written.

| Model | Learns | Baseline it must beat | Used for |
| --- | --- | --- | --- |
| **A1 range** | quantiles 0.2 / 0.5 / 0.8 of the max favourable and max adverse excursion over the horizon, in ATR, from every bar | the train median ratio times ATR | bundle M9: no signal when q0.5 favourable < 1 R; TP = q0.5 favourable clipped to [1, 3] R |
| **A2 regime** | HMM on 1h / 4h returns and volatility, forward filtering only (the P5 design), 2-3 states | the unrouted book and an ADX(14, 1h) 20 / 25 router | trend strategies (S1, S3, S4, S5, S7) only in trend states, range strategies (S2, S6, S8) only in range states |
| **A3 exits** | at each bar of an open trade, expected remaining net R if held under M0 versus exit now | the family C procedure | exit alerts |
| **A4 direction** | sign of the net move over the strategy horizon, in ATR, from every 5m / 15m bar (P5's encoder, H3, and LightGBM) | the rules alone; E0 with the same filter and context-only features reported | filter on rule signals |

Order: A1, A2, A3, A4, each only after the previous report is written. The LLM (P7) explains
signals with numbers from tools only; it is not a model here.

**Common rules for C and D.** A hypothesis that is not tested, or whose method condition fails,
enters Holm with p = 1. Test-window outcomes are used once, for the hypothesis. The served bundle
and model are the same procedure applied to all data before 2024-07-01; their evidence is the
walk-forward result of the procedure, not of the final choice, plus one holdout check
(improvement > 0 on holdout entries: "consistent on the holdout"; otherwise not activated). The
same outcomes are never counted again as independent evidence. Status for C and D: **activated**
or **not activated**; their intervals are reported.

**Fixed entry set (registered research approximation).** Families C and D evaluate management and
AI on the entry set that M0's one-active-trade rule produces, each entry managed independently.
This measures the effect of a bundle or model on those entries. It does not establish how the
final served portfolio performs under the actual one-active-trade, conflict and exposure
constraints, where another bundle can change which entries are admitted; that portfolio is
described only in the descriptive portfolio reports. After the walk-forward selection, the
test-window results of individual bundles and models are descriptive: they are not used for any
further selection, tuning or choice of a served configuration, and they are not counted as
independent evidence.

## 10. Periods, holdout, lockbox and statuses

| Role | Period | Use and protection |
| --- | --- | --- |
| **Primary (A, B)** | 2018-01-01 to 2024-07-01, six instruments | the strategy decision; equal to the union of the 13 walk-forward test windows; bars loaded only to 2024-07-01, unresolved trades excluded and counted; indicator warm-up from 2017 bars, no outcomes |
| Sensitivity 1 | XAUUSD alone, 2012-01-01 to 2024-07-01 | gold's longer history, including the 2013-2015 bear market; gold timestamps are weaker in 2012-2013, which matters for S1, S4 and S8 |
| Sensitivity 2 | all instruments, 2012-01-01 to 2024-07-01 | the instrument mix changes (2012-2015 gold only) |
| Sensitivity 3 | primary without EURUSD 2021-2023 | zero recorded spreads |
| **C and D** | the 13 test windows (2018-01 to 2024-06), training expanding from 2012 | `known_by`: exit + 1 day <= the window start; dense AI labels purged by label end time (bar + horizon) |
| **Holdout** | 2024-07-01 to 2026-01-10 | read once, after every report of A to D is written and committed (hash recorded); bars loaded to the lockbox start, unresolved trades excluded |
| **Lockbox** | 2026-01-10 to the export date | sealed until P9 (`HistoryExport`), read once |
| **Forward paper log** | from the day a profile is served (after the export date) | monitoring only; never used to change a rule |

Sensitivities share years with the primary period; they are reported, never decided on.

**Holdout check (single use, unchanged rule).** For a strategy that passed its family test on the
primary period, the holdout is read once. If mean net R > 0 and mean d > 0 there, the result is
reported as "consistent with improvement on the holdout"; otherwise as "not consistent on the
holdout", and the strategy is inconclusive until P9. The holdout has about 20 four-week blocks,
below the method condition: it gives no interval and no test, and it is never described as
statistically confirmed profitability. The statistical evidence is the primary-period test; the
holdout is a limited consistency check on top of it.

**P9 reassessment,** once, of every inconclusive or exploratory strategy, on the lockbox together
with the forward paper log, with the procedure and method condition of section 8.

**Statuses served with every signal:**

- **validated:** passed its family A test and consistent on the holdout. Shown as "validated
  (primary test passed; consistent on the holdout)", with its statistics (mean net R, interval, TP
  rate, exit mix, trade count, period).
- **exploratory:** passed its family B test; becomes validated only through the P9 reassessment.
- **inconclusive:** not enough evidence either way (section 8, method condition, or holdout not
  consistent).
- **unvalidated:** not passed and U_S < delta*_S.

Every status but validated is served marked "no proven edge". Separately, monitoring can set the
operational flag **suspended** (section 13); it does not change the statistical status.

## 11. Portfolio reports (descriptive)

Two portfolios under the actual one-active-trade, conflict and (once agreed) exposure rules: the
**validated-only portfolio**, the primary product-quality report, and the **all-served
portfolio**, a separate descriptive report. Each reports aggregate net R, mean net R per trade,
maximum drawdown in R, trades and trading days with exposure, exposure by instrument and currency,
correlation and overlap between strategies' signals, and results by type, instrument and year,
under every swap scenario. No hypothesis test is run on them, and they are never presented as proof
that the combined service is statistically validated or commercially suitable. If a ranking or
allocation layer is ever proposed, it is registered and compared with the deterministic rule (the
first signal wins a conflict; the exposure limit rejects) under the same constraints.

## 12. Counts (Stage B, descriptive only)

Reported per strategy, type, instrument and year, 2012-01-01 to 2026-01-09, with the summary window
2018-01 to 2026-01-09: signals; rejected candidates by reason; mean and median signals per trading
day; share of trading days with 0, 1, 2 or more signals; share of weeks with 0, fewer than 10, and
10 or more signals; counts before and after the signal-time filters, the one-active-trade and
conflict rules, and (once agreed with Yazan) the exposure limits. No count is a gate, and no count
changes a strategy, a parameter, delta* or a decision rule (section 15).

Up to 2024-07-01 the one-active-trade rule needs `resolve` inside the count; Stage B writes no R,
exit reason or exit price to disk, counts only.

**Holdout-period counts (2024-07-01 to 2026-01-09) are candidate-generation statistics only.** They
count candidates that pass the registered entry rules and the signal-time filters (cost filter, R
range, liquid window, holidays, one-per-day rules of S1, S4 and S8), with their rejection reasons.
They are counted before the one-active-trade rule, the conflict rule and any exposure constraint,
because those rules need the exit time of earlier trades. They are not served signals, not an
executable portfolio, and not performance; every holdout count table carries this label. No
outcome-dependent logic runs in holdout counting: no `resolve`, no management engine, no E0, no
label, no exit time; candidates use bars up to and including the signal bar only. Enforced by
tests: (a) the holdout counting function runs on synthetic bars with `resolve` and the management
engine replaced by functions that raise; (b) a static check that the holdout counting module
imports neither `app.setups.labels` nor `app.management`; (c) the count report has no outcome
columns. (The P3 count code, `app/setups/counts.py`, resolves through 2026-01-09; the new holdout
counting must not use it.)

## 13. Monitoring and product readiness (operational)

**Monitoring:** for each served profile, a one-sided CUSUM of forward paper net R against its
registered mean; crossing the threshold (fixed in the stage F addendum) sets the operational flag
**suspended**. The statistical status changes only at P9.

**Product readiness** is an operational checklist decided by Fadi, with no statistical test: the
pipeline runs end to end; evaluate answers in under 10 s (512 MB, 0.5 CPU); live = backtest replay
with zero differences; monitoring runs; every signal shows its type, status and statistics; and an
operational paper checkpoint (three months or 100 paper signals without a suspension). The
checkpoint is not evidence of profitability or of statistical power: 100 signals give a standard
error near 0.11 R (about +/- 0.22 R at 95%), and the absence of a CUSUM alarm only means no large
deterioration was detected. Launching with no validated strategy is Fadi's product decision.
Readiness never raises a statistical status.

## 14. Limitations

1. Error control is per family: each of A, B, C and D runs Holm at 0.05, so the chance of at least
   one false pass across all of them can approach about 0.2. The Deflated Sharpe ratio with N = 25
   (plus the pre-v0.2 exposure) is reported for every pass as a cross-family view, not as a gate,
   alongside Holm, walk-forward selection and the holdout, which all stay.
2. The families are not independent: C and D are built on the trades of A and B.
3. The block bootstrap is approximate: blocks are treated as independent and exchangeable, so
   dependence across block boundaries, over horizons longer than 4 weeks (multi-month regimes) and
   between instruments in different blocks is ignored; blocks are exchanged across years with
   different volatility, spread and rate conditions; the alpha/m tail is estimated from about 85
   blocks; R distributions are skewed; there is no BCa correction. The 4-week length is a
   provisional choice: L1 showed no long-range dependence (design effect 1.05-1.07 for 1 to 8
   weeks), which is weak evidence for breakout and trend strategies.
4. The unvalidated bound is computed after the test failed (post-selection) and is not adjusted
   for multiplicity.
5. The holdout check is weak (about 20 blocks); P9 is the stronger check.
6. Families C and D use a fixed entry set, an approximation of the served system.
7. Costs and swap are partly assumed: the extra cost term and slippage are not measured; every
   swap scenario is an estimate; the rollover instant in mismatch weeks, past server-clock
   conventions and the interest day-count basis are open.
8. DE 1.2 / 1.5 and sigma = sqrt(k) are assumptions for the power statements only.
9. Data: VWAP from tick counts, no historical news calendar (results also reported without
   first-Friday 08:30 New York bars), four pairs on corrected clocks until 2022, EURUSD zero
   spreads in 2021-2023, FX from 2016 and AUDUSD from 2018.
10. Prior exposure: the team has seen L1 and P4 results on the primary period and the
    instruments' price history; no outcome of S1-S8 has been seen.

## 15. Frozen at approval (D11)

Everything outcome-sensitive is frozen before any count or outcome: the strategy list and
parameters (S1-S8; L1 unchanged), the common rules, types, bundles M0-M8 and rules T1-T4 and L1-L5,
E0, the statistics and tests of sections 8 and 9, the block length and sensitivities, B, the
seeds, alpha, the Holm families, the delta* formula and floor, the classification and holdout
rules, the method condition, the swap scenarios and decision rule, the rollover convention, the
cost model, the periods and sensitivities, and the AI order and gates. After the counts only
mechanical constants are filled in by these fixed formulas (n, K, a_S, delta*_S, MDE, n_unval);
no strategy is dropped, added or changed after the counts.

Trials (`docs/phase3/TRIALS.md`): S1-S6 are 11-16, S7-S8 17-18, family C 19-21, A1-A4 22-25; N for
the Deflated Sharpe 25, plus the pre-v0.2 exposure.

## References (check before citing in the thesis)

- Berger (1982), intersection-union tests.
- Moskowitz, Ooi, Pedersen (2012), time-series momentum (S3).
- Zarattini, Aziz (2023), opening-range breakout on 5-minute bars (S4).
- Melvin, Prins (2015) and Evans (2018), the WM/Reuters 4 pm fix; Caminschi, Heaney (2014), the
  London PM gold fixing (S8).
