# Gold: the daily trend swing, XAUUSD feed (exploratory)

_`python -m app research gold-swing build`, registered in `GOLD_SWING.md` (2026-11-08). XAUUSD D1 bars 2012 to 2026-01-09; cost = the entry day's mean spread + $0.07 per oz, $0.10 on stop exits; swap scenario: longs 3% a year. Seen data: optimistic._

| N / M | Shorts | Tune trades | Tune net (swap) | Without swap | Tune years + | Check trades | Check net (swap) | Without swap | Eligible |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20 / 10 | no | 38 | +0.168 | +0.279 | 50% | 20 | +0.520 | +0.620 |  |
| 55 / 20 | no | 20 | +0.166 | +0.349 | 50% | 8 | +1.403 | +1.655 |  |
| 55 / 20 | yes | 41 | +0.083 | +0.172 | 50% | 13 | +0.616 | +0.772 |  |
| 20 / 10 | yes | 77 | +0.013 | +0.066 | 40% | 33 | +0.100 | +0.161 |  |

**No setting qualifies: SWING is dropped.**
