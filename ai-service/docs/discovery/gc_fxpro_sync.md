# COMEX gold (GC) order flow against FxPro XAUUSD: the sync check (descriptive)

_2026-11-14. GC minute order flow built in QuantConnect's cloud (`tools/quantconnect/gc_flow_minutes.py`:
the active contract by the 3 previous days' volume, ticks signed by Lee-Ready, extended hours),
compared there with FxPro's XAUUSD M1 from the research store (`tools/quantconnect/compare_in_cloud.py`;
FxPro's minutes pasted as a packed cell, since uploaded files arrive empty in the notebook). Only
the summary below left the cloud. 2025-10-01 to 2025-12-31; no prediction was looked at._

| Item | Value |
| --- | --- |
| Minutes with both prices | 87,192 (GC 88,112; full 23-hour days, 1,380 minutes, Fridays to 16:59, Sundays from 18:00) |
| One-minute return correlation, same minute | **+0.981** |
| At lags −5..−1 and +1..+5 minutes | −0.006 to +0.002 (no lead at the minute scale either way) |
| GC delta (buy − sell volume, standardised) with FxPro's return, same minute | **+0.602** (with GC's own return +0.604) |
| Gap GC − FxPro (mid), Dec 2025 contract (Z25) | median $12.61, SD 8.06 (converges toward expiry) |
| Gap, Feb 2026 contract (G26) | median $30.06, SD 5.47 |
| Daily median gap | −3.28 to +35.18; largest SD within a day $2.70 |
| GC activity | median 75 trades and 108 lots a minute; every trade signed (Lee-Ready, tick rule at the mid) |

Reading: GC and FxPro's gold are one price at the minute scale (+0.98), and the gap is a slow carry
that jumps at the roll (about +$17 from Z25 to G26), stable within a day. The order flow measured on
GC moves with FxPro's price in the same minute (+0.60, about 36% of its variance), as the order-flow
literature finds for the market's own price. Whether it predicts the **next** minutes is the open
question; it needs its own registration and more than three months.
