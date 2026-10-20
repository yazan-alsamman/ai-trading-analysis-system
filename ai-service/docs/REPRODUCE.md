# Reproducing the AI research results

Every committed report under `docs/` can be rebuilt from the two MT5 exports. The research store
(`data/processed/`) and the setup CSVs are not tracked by git; these commands recreate them. Run
everything from `ai-service/`, in this order.

## Environment

```bash
python -m venv .venv            # Python 3.12, as in CI
. .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e ".[dev]"         # pandas, pyarrow, matplotlib, scikit-learn, pytest, ruff
pytest -q                       # the real-data tests skip until the research store exists
```

## Inputs

The FxPro MT5 M5 exports, kept outside git in the repository's `data/raw/`:

- `XAUUSD_M5_mt5.csv`
- `EURUSD_M5_mt5.csv`

Both are in broker server time (`Europe/Athens`); the importer converts to UTC.

## Phase 1: research store and data-quality reports

```bash
python -m app.data.importer     # data/processed/<SYMBOL>/{5m,15m,1h,4h}.parquet
                                # docs/data_quality/<SYMBOL>_M5.{md,json}
```

Re-running on the same input rewrites byte-identical outputs.

## Phase 2: rule attempts (multiple-testing record)

Each command writes `docs/phase2/variant_<name>.{md,json}` (the baseline writes
`docs/phase2/rules_only.*`). Attempts 1–5 also counted the walk-forward period; 6 and 7 load
2012–2017 only.

| # | Variant | Command |
| --- | --- | --- |
| 1 | baseline | `python -m app.smc.report` |
| 2 | A | `python -m app.smc.report --variant A --set extend_sweep=true` |
| 3 | AB | `python -m app.smc.report --variant AB --set extend_sweep=true --set session_levels=true` |
| 4 | AB5 | `python -m app.smc.report --variant AB5 --rules FROZEN_V1` |
| 5 | AB5F | `python -m app.smc.report --variant AB5F --rules FROZEN_V2` |
| 6 | AB5F3 | `python -m app.smc.report --variant AB5F3 --rules FROZEN_V3 --dev-only` |
| 7 | AB5F3S | `python -m app.smc.report --variant AB5F3S --rules FROZEN_V4 --dev-only` |

Gate 2a, the automated check of the written conditions on the current rules (`FROZEN_V4`):

```bash
python -m app.smc.conditions    # docs/phase2/conditions.{md,json}
```

Review charts for the current rules. The archived v1–v3 sheets are in `docs/phase2/review_v*/`;
their charts can be regenerated from the commit named in PROJECT_CONTEXT.md:

```bash
python -m app.smc.review --seed 2027   # docs/phase2/review/*.png and REVIEW.md
```

## Phase 3: dataset, walk-forward and robustness

```bash
python -m app.ml.dataset        # data/processed/XAUUSD/phase3_dataset.parquet, docs/phase3/dataset.md
python -m app.ml.walkforward    # docs/phase3/walkforward.{md,json} and the predictions parquet
python -m app.ml.robustness     # docs/phase3/robustness.{md,json} (about 3 minutes)
```

The walk-forward evaluation was run once, under protocol v1 in the spec. Re-running it reproduces
the same numbers: the models and the bootstrap use fixed seeds. It is not a new attempt.

## Not scripted in the repository

- **The random-entry base rates** (experiments log, 2026-10-19) came from a one-off script that was
  not committed. The method is in the log entry.
- **The lockbox (2024-07 onward)** is never loaded by any command here.
