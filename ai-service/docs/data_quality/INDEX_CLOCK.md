# The index CFD exports were read on a wrong clock (found 2026-11-18)

## What happened

The FxPro M1 exports of the index CFDs (`#USNDAQ100`, and in the personal lab `#US30`,
`#USSPX500`, `#Germany40`, `#UK100`, `#Japan225`) were read with `gold_exam.frames_from_lines`.
That reader runs the importer's clock check (`app/data/clock.py`). The check finds a week's
offset from its weekly open and the US 08:30 release spikes, with the open set for gold and FX.
The index CFDs open at other times, so the check moved whole weeks of them by whole hours.

**How it was found.** A lab model that used the indices' last half-hour as features for other
markets scored +0.94 R a trade with t 40: a leak. The half-hour returns of each index, lined up
against US500 and gold, peaked at the wrong lag:

| Export, as read before | Lag of the best match (against US500) |
| --- | --- |
| GER40 | 3 h, all years |
| UK100 | 2 h, all years |
| US30, NAS100 | 0 in most weeks, 1 h in a part of most years (2018, 2021, 2025 the most) |
| US500 | 13 segments moved (against its own raw reading: 0.95 correlation, not 1) |
| JP225 | 0 |

Read straight from the export (server time Europe/Athens to UTC, no check), every index lines up
with US500 and gold at lag 0 (correlations +0.60 to +0.95).

The gold exports are not affected: on FxPro `GOLD` the check finds one segment with offset 0, and
the demo matches Python trade for trade. The research store (XAUUSD and the FX pairs) is the
importer's own, checked against Dukascopy.

## The fix

`gold_exam.index_frames_from_lines`: the export's lines, server time to UTC, aggregated, nothing
moved (test: `tests/test_five_nas.py`). `five_nas.py` and `confluence.py` now use it.

## Project results rerun (2026-11-18): no decision changes

| Report | Before | After | Decision |
| --- | --- | --- | --- |
| `five_nas100_result.md` (`FIVE_NAS100.md`) | 4,831 trades, −0.040 R with slip, E0 95th −0.056; gross +0.074 | 4,788, **−0.030**, E0 95th −0.055; gross +0.087 | does not generalise (unchanged) |
| `five_nas_reclaim_result.md` (`FIVE_NAS_RECLAIM.md`) | 759, −0.050; 2016-2021 −0.157, 2022 on −0.031 | 737, **−0.032**; 2016-2021 −0.239, 2022 on +0.001 | does not hold (unchanged: 2016-2021 still below 0; conditions 2 and 3 now met) |
| `confluence_result.md` (`CONFLUENCE.md`) | D +0.0050 R, p 0.40, 3 of 6 | D **+0.0068**, p 0.36, 3 of 6 | does not pass (unchanged) |

## Personal lab results that used the same reader

Not part of the project; rerun on the server clock the same day, no verdict changed: the five on
US500, US30, GER40, UK100, JP225 (US30 and GER40 pass, the other three fail, as before); HKS
(the same to the fourth decimal). The frozen DIRML run's 2019-2021 figures shrink when the indices
are read correctly (gross +0.176 to +0.073 R); its 2022-2025 figures hardly move. The
lab's Nasdaq pre-market and momentum tests and the trend look read the export themselves on the
server clock and are not affected.
