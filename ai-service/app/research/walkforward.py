"""Walk-forward protocol (P4 task 2): folds, purge and embargo, calibration, scoring metrics.

    python -m app research walkforward          # folds and E1 (rules only) on the test windows

Writes ``docs/phase4/walkforward_<rules>.md``. Models (E2-E4) plug into ``predict`` in task 3.

**Folds** (D23): test windows of ``walk_forward_test_months`` (6) months from the start of the
walk-forward period (2018-01-01) to its end (2024-07-01): 13 windows. A setup is in a test window
when its decision time is. The training set of a window is every earlier setup (from 2012,
expanding) whose outcome is known at least ``embargo_days`` (1) before the window starts: its exit
time plus the embargo is not after the window start. That one rule is both the purge (no training
outcome overlaps the test window) and the embargo (a full day between them).

**Calibration** (design §9.3): the last ``CAL_SHARE`` of a training set (by decision time) is held
out as the calibration slice, purged the same way from the part the model is fitted on. Platt and
isotonic calibration are compared on that slice by a time-ordered two-fold (fit on one half, score
the other, both ways); the one with the lower Brier score is refitted on the whole slice.

**Metrics** on the pooled test predictions (and per window): Brier score; Brier skill against the
training base rate of each window (climatology, known before the window); ECE over ``ECE_BINS``
equal-width bins. Expected value and the H2 comparison come with the models (task 3)."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from app.config import splits
from app.data.importer import DEFAULT_OUT as STORE
from app.research.baselines import block_ci, week_of

OUT_DIR = Path(__file__).resolve().parents[2] / "docs" / "phase4"
CAL_SHARE = 0.25
ECE_BINS = 10
SEED = 20261023


@dataclass(frozen=True)
class Fold:
    start: pd.Timestamp
    end: pd.Timestamp
    train: np.ndarray  # row positions in the dataset
    test: np.ndarray


def known_by(df: pd.DataFrame, t: pd.Timestamp, embargo_days: int) -> np.ndarray:
    """Rows whose outcome is known at least ``embargo_days`` before ``t``."""
    return (df["exit_utc"] + pd.Timedelta(days=embargo_days) <= t).to_numpy()


def folds(df: pd.DataFrame) -> list[Fold]:
    s = splits()
    start = pd.Timestamp(s.walk_forward[0], tz="UTC")
    stop = pd.Timestamp(s.walk_forward[1], tz="UTC")
    t = df["decision_utc"]
    out = []
    while start < stop:
        end = min(start + pd.DateOffset(months=s.walk_forward_test_months), stop)
        train = np.flatnonzero(known_by(df, start, s.embargo_days) & (t < start).to_numpy())
        test = np.flatnonzero(((t >= start) & (t < end)).to_numpy())
        out.append(Fold(start, end, train, test))
        start = end
    return out


def split_calibration(df: pd.DataFrame, train: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Fit and calibration rows of a training set: the latest ``CAL_SHARE`` (by decision time)
    calibrates; the fit rows are purged and embargoed from its first decision."""
    order = train[np.argsort(df["decision_utc"].to_numpy()[train], kind="stable")]
    n_cal = max(1, int(round(len(order) * CAL_SHARE)))
    cal = order[-n_cal:]
    first = df["decision_utc"].iloc[cal[0]]
    rest = order[:-n_cal]
    fit = rest[known_by(df.iloc[rest], first, splits().embargo_days)]
    return fit, cal


class Platt:
    def fit(self, p: np.ndarray, y: np.ndarray) -> Platt:
        self.lr = LogisticRegression(C=1e6).fit(_logit(p)[:, None], y)
        return self

    def predict(self, p: np.ndarray) -> np.ndarray:
        return self.lr.predict_proba(_logit(p)[:, None])[:, 1]


class Isotonic:
    def fit(self, p: np.ndarray, y: np.ndarray) -> Isotonic:
        self.iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip").fit(p, y)
        return self

    def predict(self, p: np.ndarray) -> np.ndarray:
        return self.iso.predict(p)


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def brier(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def ece(p: np.ndarray, y: np.ndarray, bins: int = ECE_BINS) -> float:
    """Expected calibration error: bin-weighted |mean p - hit rate| over equal-width bins."""
    idx = np.minimum((p * bins).astype(int), bins - 1)
    total = 0.0
    for b in range(bins):
        m = idx == b
        if m.any():
            total += m.mean() * abs(p[m].mean() - y[m].mean())
    return float(total)


def choose_calibrator(p: np.ndarray, y: np.ndarray) -> Platt | Isotonic:
    """Platt or isotonic, by Brier on a time-ordered two-fold of the calibration slice."""
    half = len(p) // 2
    scores = {}
    for kind in (Platt, Isotonic):
        s = []
        for a, b in ((slice(0, half), slice(half, None)), (slice(half, None), slice(0, half))):
            if len(np.unique(y[a])) < 2:
                s.append(np.inf)
                continue
            s.append(brier(kind().fit(p[a], y[a]).predict(p[b]), y[b]))
        scores[kind] = np.mean(s)
    best = min(scores, key=scores.get)
    if len(np.unique(y)) < 2:
        best = Isotonic
    return best().fit(p, y)


def predict(
    df: pd.DataFrame, features: list[str], make_model: Callable[[], object]
) -> pd.DataFrame:
    """Out-of-sample calibrated probabilities for every test row of every fold."""
    rows = []
    y = df["y"].to_numpy(int)
    x = df[features].to_numpy(float)
    for k, f in enumerate(folds(df)):
        if len(f.test) == 0:
            continue
        fit, cal = split_calibration(df, f.train)
        model = make_model()
        model.fit(x[fit], y[fit])
        cal_p = model.predict_proba(x[cal])[:, 1]
        calibrator = choose_calibrator(cal_p, y[cal])
        raw = model.predict_proba(x[f.test])[:, 1]
        rows.append(
            pd.DataFrame(
                {
                    "row": f.test,
                    "fold": k,
                    "p_raw": raw,
                    "p": calibrator.predict(raw),
                    "base_rate": y[f.train].mean(),
                    "calibrator": type(calibrator).__name__,
                }
            )
        )
    return pd.concat(rows, ignore_index=True)


def scores(pred: pd.DataFrame, y: np.ndarray) -> dict:
    yy = y[pred["row"].to_numpy()]
    p = pred["p"].to_numpy()
    ref = brier(pred["base_rate"].to_numpy(), yy)
    b = brier(p, yy)
    return {"brier": b, "brier_ref": ref, "bss": 1 - b / ref, "ece": ece(p, yy), "n": len(p)}


def render(df: pd.DataFrame, fs: list[Fold], rules: str) -> str:
    rng = np.random.default_rng(SEED)
    lines = [
        f"# P4: walk-forward folds and E1 on the test windows ({rules})",
        "",
        "_Generated by `python -m app research walkforward`; protocol in"
        " `app/research/walkforward.py`. Rules frozen (L1, 2026-10-23) before this run._",
        "",
        "| Window | Train (fit / calibration) | Test | Train base rate | E1 TP | E1 mean net R |"
        " E1 total R |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    y = df["y"].to_numpy(int)
    for f in fs:
        fit, cal = split_calibration(df, f.train)
        te = df.iloc[f.test]
        lines.append(
            f"| {f.start:%Y-%m} | {len(f.train)} ({len(fit)} / {len(cal)}) | {len(f.test)} |"
            f" {y[f.train].mean():.1%} | {te['y'].mean():.1%} | {te['net_r'].mean():+.3f} |"
            f" {te['net_r'].sum():+.1f} |"
        )
    test = df.iloc[np.concatenate([f.test for f in fs])]
    lo, hi = block_ci(test["net_r"].to_numpy(float), week_of(test["decision_utc"]), rng)
    lines += [
        "",
        f"E1 on all test windows (2018-01 to 2024-06): **{len(test)} trades**, TP"
        f" {test['y'].mean():.1%}, mean net R **{test['net_r'].mean():+.3f}** (95% weekly block"
        f" {lo:+.3f} to {hi:+.3f}), at 2x costs {test['net_r_2x'].mean():+.3f}, total"
        f" {test['net_r'].sum():+.1f} R.",
        "",
        "| Instrument | Trades | TP | Mean net R |",
        "| --- | --- | --- | --- |",
        *[
            f"| {s} | {len(g)} | {g['y'].mean():.1%} | {g['net_r'].mean():+.3f} |"
            for s, g in test.groupby("symbol")
        ],
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research walkforward")
    ap.add_argument("--rules", default="L1")
    ap.add_argument("--store", type=Path, default=STORE)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args(argv)
    path = args.store / f"p4_dataset_{args.rules}.parquet"
    if not path.exists():
        print(f"{path} missing: run python -m app features build", file=sys.stderr)
        return 1
    df = pd.read_parquet(path).sort_values("decision_utc").reset_index(drop=True)
    fs = folds(df)
    args.out.mkdir(parents=True, exist_ok=True)
    report = render(df, fs, args.rules)
    (args.out / f"walkforward_{args.rules}.md").write_text(report, encoding="utf-8", newline="\n")
    print(report)
    return 0
