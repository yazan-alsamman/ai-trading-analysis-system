# The economic calendar: checks (stage D1)

_`python -m app discovery calendar`: 154,224 releases, 2010-01-01 to 2026-12-10, USD 50,821, EUR 43,937, JPY 17,522, GBP 15,582, AUD 8,843, CAD 8,584, CNY 4,650, CHF 4,285. Importance 3 (high): 13,539. No market data read._

## 1. New York times of the main US releases (from `time_utc`)

| Event | Releases | Expected | At the expected time | Other times |
| --- | --- | --- | --- | --- |
| Nonfarm Payrolls | 203 | 08:30 | 99.5% | 07:30 (1) |
| CPI m/m | 202 | 08:30 | 100.0% | - |
| Core CPI m/m | 202 | 08:30 | 100.0% | - |
| GDP q/q | 199 | 08:30 | 100.0% | - |
| Retail Sales m/m | 203 | 08:30 | 99.5% | 07:30 (1) |
| Core PCE Price Index m/m | 201 | 08:30 | 93.0% | 10:00 (12), 07:30 (2) |
| Initial Jobless Claims | 875 | 08:30 | 99.8% | 08:31 (1), 09:30 (1) |
| ISM Manufacturing PMI | 204 | 10:00 | 100.0% | - |
| Fed Interest Rate Decision | 137 | 14:00 | 80.3% | 14:15 (17), 12:30 (8), 10:00 (1), 17:00 (1) |

## 2. NFP dates: the calendar against the BLS rule

Calendar 203, rule 203, both 185.

| Calendar only | Rule only |
| --- | --- |
| 20100108 | 20131004 |
| 20131022 | 20131101 |
| 20131108 | 20140103 |
| 20140110 | 20140704 |
| 20140703 | 20150102 |
| 20150109 | 20150703 |
| 20150702 | 20160101 |
| 20160108 | 20200103 |
| 20200110 | 20200703 |
| 20200702 | 20210101 |
| 20210108 | 20250103 |
| 20250110 | 20250704 |
| 20250703 | 20251003 |
| 20251120 | 20251107 |
| 20251216 | 20251205 |
| 20260109 | 20260102 |
| 20260211 | 20260206 |
| 20260702 | 20260703 |

The rule ignores holiday moves and shutdowns (`gold_shadow.nfp_days`); the calendar holds the actual dates (for example the 2013 shutdown: 2013-10-22 and 2013-11-08), so F3 uses the calendar.
