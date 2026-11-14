"""The volatility outlook's 15m form (``docs/vol/SERVING.md``, registered 2026-11-12).

    python -m app research vol-serving check    # part 1's walk-forward on 15m bars
    python -m app research vol-serving freeze   # M3 on every used 15m day -> volatility_v1.json

``freeze`` refuses unless the check passed (its report says so)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from app.research import gold_lab as gl
from app.research import vol_forecast as vf
from app.scoring import volatility as vs

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs" / "vol" / "serving_check.md"
MODEL = "vol-m3-15m-v1"
QS = {"p20": 0.2, "p50": 0.5, "p80": 0.8}
PASS = "**The 15m M3 passes: it is served.**"


def frame15() -> tuple[pd.DataFrame, pd.DataFrame]:
    fr = gl.load()
    cal = pd.read_parquet(vf.CAL)
    return vf.features(fr["15m"], fr["4h"], cal, step=vs.STEP), cal


def range_k(f: pd.DataFrame) -> dict[str, float]:
    """Percentiles of (window range / price at 02:00) / sqrt(F_M3) on the out-of-sample days."""
    lev = np.exp(f["f_M3"] + f["s2_M3"] / 2)
    k = (f["hi"] - f["lo"]) / f["p02"] / np.sqrt(lev)
    return {q: float(k.quantile(v)) for q, v in QS.items()}


def check() -> str:
    u, _ = frame15()
    f, _ = vf.walk(u)
    cmp = vf.compare(f)
    ok = bool(cmp.loc["M3", "beats"])
    k = range_k(f)
    lines = [
        "# Volatility outlook, 15m form: the check",
        "",
        "_`python -m app research vol-serving check`, registered in `SERVING.md` §2: part 1's "
        f"walk-forward on 15m bars. {len(u):,} used days, {len(f):,} test days (2018 to "
        "2026-01-09)._",
        "",
        PASS if ok else "**The 15m M3 fails: nothing is served.**",
        "",
        "| Model | Mean QLIKE diff vs M1 | 95% | Holm p | Years below M1 | 2024-07 on | Beats |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name, x in cmp.iterrows():
        lines.append(f"| {name} | {x['diff']:+.4f} | {x['lo']:+.4f} to {x['hi']:+.4f} "
                     f"| {x['holm']:.4f} | {int(x['years'])} | {x['hold']:+.4f} "
                     f"| {'yes' if x['beats'] else 'no'} |")  # fmt: skip
    lines += ["", "| Model | Mean QLIKE |", "| --- | --- |"]
    lines += [f"| {m} | {f[f'L_{m}'].mean():.4f} |" for m in vf.MODELS]
    lines += ["", "Range multipliers k (out-of-sample): "
              + ", ".join(f"{q} {v:.3f}" for q, v in k.items()), ""]  # fmt: skip
    return "\n".join(lines)


def commit() -> str:
    out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                         cwd=ROOT, check=False)  # fmt: skip
    return out.stdout.strip()


def freeze() -> dict:
    u, _ = frame15()
    f, _ = vf.walk(u)
    beta, s2 = vf.ols(u[vs.M3].to_numpy(), u["y"].to_numpy())
    return {
        "model": MODEL,
        "doc": "docs/vol/SERVING.md",
        "bars_minutes": vs.STEP,
        "fit_days": len(u),
        "fit_from": str(u.index.min().date()),
        "fit_to": str(u.index.max().date()),
        "code": commit(),
        "m3": {"coef": dict(zip(["const", *vs.M3], map(float, beta), strict=True)), "s2": s2},
        "range_k": range_k(f),
    }


def main(argv: list[str] | None = None) -> int:
    argv = argv or []
    if argv and argv[0] == "check":
        REPORT.write_text(check(), encoding="utf-8", newline="\n")
        print(f"wrote {REPORT}")
        return 0
    if argv and argv[0] == "freeze":
        if not REPORT.exists() or PASS not in REPORT.read_text(encoding="utf-8"):
            print("refused: the 15m check has not passed (serving_check.md)", file=sys.stderr)
            return 1
        vs.PARAMS.write_text(json.dumps(freeze(), indent=2) + "\n", encoding="utf-8")
        print(f"wrote {vs.PARAMS}")
        return 0
    print(__doc__, file=sys.stderr)
    return 2
