# Volatility outlook, 15m form: the check

_`python -m app research vol-serving check`, registered in `SERVING.md` §2: part 1's walk-forward on 15m bars. 3,462 used days, 1,996 test days (2018 to 2026-01-09)._

**The 15m M3 passes: it is served.**

| Model | Mean QLIKE diff vs M1 | 95% | Holm p | Years below M1 | 2024-07 on | Beats |
| --- | --- | --- | --- | --- | --- | --- |
| M2 | +0.0029 | -0.0040 to +0.0107 | 0.7722 | 2 | +0.0053 | no |
| M3 | -0.0222 | -0.0326 to -0.0101 | 0.0021 | 6 | -0.0132 | yes |
| M4 | -0.0207 | -0.0325 to -0.0066 | 0.0056 | 6 | -0.0180 | yes |

| Model | Mean QLIKE |
| --- | --- |
| M0 | 0.2563 |
| M1 | 0.1701 |
| M2 | 0.1730 |
| M3 | 0.1480 |
| M4 | 0.1494 |

Range multipliers k (out-of-sample): p20 1.062, p50 1.415, p80 1.970
