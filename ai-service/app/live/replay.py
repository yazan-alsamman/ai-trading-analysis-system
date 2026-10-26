"""Live = backtest (P6 task 5): replay history bar by bar through ``evaluate`` and compare with
the research pipeline.

    python -m app live replay                       # six instruments, 2018 to 2024-06
    python -m app live replay --symbols XAUUSD --workers 8
    python -m app live bench --url http://localhost:8001   # latency of a running service (task 8)

Writes ``docs/phase6/replay.md``. Only the walk-forward period is replayed (already seen in P3
and P4); nothing at or after its end is loaded, so the secondary holdout and the lockbox stay
closed. The report compares states, times, prices and realised R one by one and summarises no
performance: it is not a trial (``docs/phase3/TRIALS.md``).

**Research side:** ``label_all`` on the store frames from 2012 to the end of the period, as P4
used them. **Live side:** for every 15m bar of the period, a request carrying the last
``--bars`` 15m bars of the store (the backend's feed in this test) and the open setups of a
simulated backend, which applies each answer as ``backend/app/ai/store.py`` does (new setups,
forward state moves, transitions checked against the allowed table) and echoes the non-final
setups on the next bar. The period is cut into six-month chunks run in parallel; each chunk
starts 20 days early, runs 3 days past its end so its last setups finish, and records only the
setups decided inside it. Finished chunks are kept in ``data/processed/p6_replay/`` (keyed by the
strategy and service versions), so an interrupted run resumes.

A setup matches when the id, direction, decision time, entry, SL, TP and risk (relative
1e-9), final state (research ``CLOSED`` = ``CLOSED``, ``PENDING`` = still ``ACTIVE``), exit
reason, exit time and net realised R (absolute 1e-6) all agree."""

from __future__ import annotations

import argparse
import json
import pickle
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import profiles, splits, strategy
from app.contract import (
    FINAL_STATES,
    Bar,
    EvaluateRequest,
    EvaluateStatus,
    InstrumentSpec,
    Setup,
    SetupState,
    iso_z,
    make_request_id,
)
from app.data.importer import DEFAULT_OUT as STORE
from app.live.evaluate import evaluate, versions
from app.setups.counts import history_frames
from app.setups.labels import label_all

OUT = Path(__file__).resolve().parents[2] / "docs" / "phase6" / "replay.md"
CACHE = STORE / "p6_replay"  # finished chunks (untracked)
SYMBOLS = ("XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD")
PROFILE = "intraday"
BARS = 1000
LEAD = pd.Timedelta(days=20)
TAIL = pd.Timedelta(days=3)
M15 = pd.Timedelta(minutes=15)
ALLOWED = {
    SetupState.DEVELOPING: {SetupState.ARMED, SetupState.EXPIRED, SetupState.INVALIDATED},
    SetupState.ARMED: {SetupState.ACTIVE, SetupState.EXPIRED, SetupState.INVALIDATED},
    SetupState.ACTIVE: {SetupState.CLOSED, SetupState.INVALIDATED},
}  # docs/ai-contract.md section 5
ORDER = list(SetupState)


def period() -> tuple[pd.Timestamp, pd.Timestamp]:
    start, end = splits().walk_forward
    return pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC")


def chunks() -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    start, end = period()
    edges = list(pd.date_range(start, end, freq="6MS", tz="UTC"))
    if edges[-1] < end:
        edges.append(end)
    return list(zip(edges, edges[1:], strict=False))


def spec_for(symbol: str) -> InstrumentSpec:
    """The B4 specs the backend would send (only ``tick_size`` changes the answer)."""
    from app.config import instruments

    inst = instruments()[symbol]
    return InstrumentSpec(
        contract_size=inst.contract_size,
        tick_size=inst.point,
        lot_step=0.01,
        min_lot=0.01,
        max_lot=100,
        price_basis="bid",
        quote_currency=inst.quote_currency,
    )


@dataclass
class Backend:
    """What ``backend/app/ai/store.py`` keeps: every setup's payload and state."""

    setups: dict[str, dict] = field(default_factory=dict)
    rejected: list[str] = field(default_factory=list)

    def apply(self, resp) -> None:
        for s in resp.new_setups:
            sid, state = s.setup_id, SetupState(s.state)
            p = s.payload()
            known = self.setups.get(sid)
            if known is None:
                self.setups[sid] = {"payload": p, "state": state, "events": [(None, state)]}
            elif known["state"] not in FINAL_STATES and ORDER.index(state) > ORDER.index(
                known["state"]
            ):
                known.update(payload=p, state=state)
                known["events"].append((None, state))
        for t in sorted(resp.transitions, key=lambda t: t.at):
            known = self.setups.get(t.setup_id)
            ok = (
                known is not None
                and known["state"] not in FINAL_STATES
                and known["state"] == t.from_
                and t.to in ALLOWED.get(t.from_, set())
            )
            if not ok:
                self.rejected.append(f"{t.setup_id} {t.from_}->{t.to} at {iso_z(t.at)}")
                continue
            known["state"] = t.to
            known["events"].append((t, t.to))

    def open_setups(self) -> list[Setup]:
        return [
            Setup.model_validate(v["payload"] | {"state": v["state"].value})
            for v in self.setups.values()
            if v["state"] not in FINAL_STATES
        ]


def chunk_path(symbol: str, lo: pd.Timestamp, n_bars: int) -> Path:
    """Where a finished chunk is kept, so an interrupted replay resumes. The name carries the
    strategy and service versions: a change of rules or code starts the chunk again."""
    v = versions(PROFILE, symbol)
    tag = f"{v['strategy']}_{v['service']}_{n_bars}"
    return CACHE / f"{symbol}_{lo:%Y%m}_{tag}.pkl"


def run_chunk(args: tuple[str, pd.Timestamp, pd.Timestamp, int]) -> dict:
    symbol, lo, hi, n_bars = args
    cached = chunk_path(symbol, lo, n_bars)
    if cached.exists():
        return pickle.loads(cached.read_bytes())
    _, end = period()
    stop = min(hi + TAIL, end)
    path = STORE / symbol / "15m.parquet"
    m15 = pd.read_parquet(
        path, filters=[("ts_utc", ">=", lo - LEAD), ("close_utc", "<=", stop)]
    ).reset_index(drop=True)
    bars = [
        Bar(ts=r.ts_utc.to_pydatetime(), o=r.open, h=r.high, l=r.low, c=r.close, spread=r.spread)
        for r in m15[["ts_utc", "open", "high", "low", "close"]]
        .assign(spread=m15["spread_mean"])
        .itertuples()
    ]
    spec = spec_for(symbol)
    backend = Backend()
    refused: dict[str, int] = {}
    latency = []
    evaluated = 0
    closes = m15["close_utc"]
    for i in np.flatnonzero((closes > lo).to_numpy() & (closes <= stop).to_numpy()):
        close = closes.iloc[i].to_pydatetime()
        req = EvaluateRequest.model_construct(
            request_id=make_request_id(symbol, PROFILE, close),
            instrument=symbol,
            profile=PROFILE,
            bar_close_ts=close,
            bars={"15m": bars[max(0, i - n_bars + 1) : i + 1]},
            open_setups=backend.open_setups(),
            calendar=[],
            instrument_spec=spec,
        )
        t0 = time.perf_counter()
        resp = evaluate(req)
        latency.append(time.perf_counter() - t0)
        evaluated += 1
        if resp.status != EvaluateStatus.ok:
            reason = resp.abstentions[0].reason
            refused[reason] = refused.get(reason, 0) + 1
            continue
        backend.apply(resp)
    rows = []
    for sid, v in backend.setups.items():
        p = v["payload"]
        created = pd.Timestamp(p["created_at"])
        if not lo <= created < hi:
            continue
        closed = [t for t, s in v["events"] if s == SetupState.CLOSED and t is not None]
        t = closed[0] if closed else None
        plan = p["evidence"]["plan"]
        rows.append(
            {
                "setup_id": sid.split("-", 2)[2],
                "direction": p["direction"],
                "created_at": created,
                "state": v["state"].value,
                "reason": t.reason if t else None,
                "exit_at": pd.Timestamp(t.at) if t else None,
                "net_r": t.realized_r if t else None,
                **{k: plan[k] for k in ("entry", "sl", "tp", "risk")},
            }
        )
    out = {
        "symbol": symbol,
        "chunk": (lo, hi),
        "evaluated": evaluated,
        "refused": refused,
        "rejected_transitions": backend.rejected,
        "latency": latency,
        "setups": rows,
        "bars": n_bars,
    }
    cached.parent.mkdir(parents=True, exist_ok=True)
    tmp = cached.with_suffix(".tmp")
    tmp.write_bytes(pickle.dumps(out))
    tmp.replace(cached)
    return out


def research(symbol: str) -> pd.DataFrame:
    start, end = period()
    p = strategy(profiles()[PROFILE].rules)
    df = label_all(history_frames(symbol, p, end=end), symbol, p)
    df = df[df["state"] != "REJECTED"].copy()
    df["created_at"] = df["decision_utc"] + M15
    df = df[(df["created_at"] >= start) & (df["created_at"] < end)]
    df["exit_at"] = df["exit_utc"] + M15
    return df.reset_index(drop=True)


def compare(ref: pd.DataFrame, live: pd.DataFrame) -> list[str]:
    diffs = []
    r = ref.set_index("setup_id")
    v = live.set_index("setup_id") if len(live) else live
    for sid in sorted(set(r.index) - set(v.index)):
        diffs.append(f"missing live: {sid} ({r.loc[sid, 'created_at']})")
    for sid in sorted(set(v.index) - set(r.index)):
        diffs.append(f"extra live: {sid} ({v.loc[sid, 'created_at']})")
    for sid in sorted(set(r.index) & set(v.index)):
        a, b = r.loc[sid], v.loc[sid]
        want_state = "ACTIVE" if a["state"] == "PENDING" else a["state"]
        checks = [
            ("direction", a["direction"] == b["direction"]),
            ("created_at", a["created_at"] == b["created_at"]),
            ("state", want_state == b["state"]),
        ]
        checks += [(k, np.isclose(a[k], b[k], rtol=1e-9, atol=0)) for k in ("entry", "sl", "risk")]
        checks.append(("tp", np.isclose(a["tp"], b["tp"], rtol=1e-9, atol=0)))
        if a["state"] == "CLOSED":
            checks += [
                ("reason", a["reason"] == b["reason"]),
                ("exit_at", a["exit_at"] == b["exit_at"]),
                ("net_r", b["net_r"] is not None and abs(a["net_r"] - b["net_r"]) <= 1e-6),
            ]
        bad = [k for k, ok in checks if not ok]
        if bad:
            diffs.append(f"{sid}: {', '.join(bad)}")
    return diffs


def render(results: dict[str, dict], n_bars: int, seconds: float) -> str:
    start, end = period()
    lines = [
        "# P6: live = backtest (replay)",
        "",
        "_Generated by `python -m app live replay`; code in `app/live/replay.py`. Equality only:"
        " no performance is summarised (not a trial)._",
        "",
        f"Period: {start:%Y-%m-%d} → {end:%Y-%m-%d} (walk-forward; nothing later is loaded)."
        f" Each request carries the last {n_bars} 15m bars; profile `{PROFILE}`"
        f" ({profiles()[PROFILE].rules}). Run time {seconds / 60:.0f} min.",
        "",
        "| Instrument | Bars evaluated | Refused (data quality) | Research setups | Live setups"
        " | Differences | Rejected transitions | Latency mean / p95 / max (ms) |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    total = 0
    for sym, r in results.items():
        lat = np.array(r["latency"]) * 1000
        refused = ", ".join(f"{k} {v}" for k, v in sorted(r["refused"].items())) or "0"
        total += len(r["diffs"]) + len(r["rejected_transitions"])
        lines.append(
            f"| {sym} | {r['evaluated']:,} | {refused} | {r['n_ref']} | {r['n_live']} |"
            f" {len(r['diffs'])} | {len(r['rejected_transitions'])} |"
            f" {lat.mean():.0f} / {np.percentile(lat, 95):.0f} / {lat.max():.0f} |"
        )
    lines += [
        "",
        f"**Result: {'zero differences' if total == 0 else f'{total} differences'}.**",
        "",
    ]
    for sym, r in results.items():
        if r["diffs"] or r["rejected_transitions"]:
            lines += [f"## {sym}", ""]
            lines += [f"- {d}" for d in r["diffs"][:40]]
            lines += [f"- rejected transition: {d}" for d in r["rejected_transitions"][:20]]
            lines.append("")
    lines += [
        "Latency is in-process (`evaluate` alone, this machine, one worker per core); the"
        " production measurement at 512 MB / 0.5 CPU is task 8.",
        "",
    ]
    return "\n".join(lines)


def bench(url: str, symbol: str, sizes: list[int], n: int) -> list[str]:
    """Latency of ``POST /v1/evaluate`` on a running service, with requests of ``sizes`` 15m
    bars from the store (the last bars of the walk-forward period)."""
    import httpx

    _, end = period()
    m15 = pd.read_parquet(STORE / symbol / "15m.parquet", filters=[("close_utc", "<=", end)])
    m15 = m15.tail(max(sizes) + n).reset_index(drop=True)
    head = "| 15m bars | Body (KB) | Calls | p50 (ms) | p95 (ms) | max (ms) |"
    lines = [head, "| --- " * 6 + "|"]
    with httpx.Client(base_url=url, timeout=30) as client:
        for size in sizes:
            times, kb = [], 0.0
            for k in range(n):
                part = m15.iloc[len(m15) - n - size + k + 1 : len(m15) - n + k + 1]
                close = part["close_utc"].iloc[-1].to_pydatetime()
                body = {
                    "request_id": make_request_id(symbol, PROFILE, close),
                    "instrument": symbol,
                    "profile": PROFILE,
                    "bar_close_ts": iso_z(close),
                    "bars": {
                        "15m": [
                            {
                                "ts": iso_z(r.ts_utc.to_pydatetime()),
                                "o": r.open,
                                "h": r.high,
                                "l": r.low,
                                "c": r.close,
                                "spread": r.spread_mean,
                            }
                            for r in part.itertuples()
                        ]
                    },
                    "instrument_spec": spec_for(symbol).model_dump(mode="json"),
                }
                raw = json.dumps(body).encode()
                kb = len(raw) / 1024
                t0 = time.perf_counter()
                headers = {"content-type": "application/json"}
                res = client.post("/v1/evaluate", content=raw, headers=headers)
                times.append((time.perf_counter() - t0) * 1000)
                res.raise_for_status()
            t = np.array(times)
            lines.append(
                f"| {size} | {kb:.0f} | {n} | {np.percentile(t, 50):.0f} |"
                f" {np.percentile(t, 95):.0f} | {t.max():.0f} |"
            )
    return lines


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m app live")
    sub = ap.add_subparsers(dest="command", required=True)
    bp = sub.add_parser("bench", help="latency of a running service")
    bp.add_argument("--url", default="http://localhost:8001")
    bp.add_argument("--symbol", default="XAUUSD")
    bp.add_argument("--sizes", nargs="+", type=int, default=[1000, 5000])
    bp.add_argument("--n", type=int, default=40)
    rp = sub.add_parser("replay", help="live = backtest over the walk-forward period")
    rp.add_argument("--symbols", nargs="+", default=list(SYMBOLS))
    rp.add_argument("--bars", type=int, default=BARS)
    rp.add_argument("--workers", type=int, default=10)
    rp.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    if args.command == "bench":
        for line in bench(args.url, args.symbol, args.sizes, args.n):
            print(line)
        return 0

    t0 = time.perf_counter()
    jobs = [(s, lo, hi, args.bars) for s in args.symbols for lo, hi in chunks()]
    with ProcessPoolExecutor(args.workers) as pool:
        parts = list(pool.map(run_chunk, jobs))
    refs = {s: research(s) for s in args.symbols}  # one at a time: each loads 2012 onwards
    results = {}
    for s in args.symbols:
        mine = [p for p in parts if p["symbol"] == s]
        live = pd.DataFrame([row for p in mine for row in p["setups"]])
        refused: dict[str, int] = {}
        for p in mine:
            for k, v in p["refused"].items():
                refused[k] = refused.get(k, 0) + v
        results[s] = {
            "evaluated": sum(p["evaluated"] for p in mine),
            "refused": refused,
            "rejected_transitions": [x for p in mine for x in p["rejected_transitions"]],
            "latency": [x for p in mine for x in p["latency"]],
            "n_ref": len(refs[s]),
            "n_live": len(live),
            "diffs": compare(refs[s], live),
        }
        print(
            f"{s}: {results[s]['n_live']} live / {results[s]['n_ref']} research setups,"
            f" {len(results[s]['diffs'])} differences",
            file=sys.stderr,
        )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        render(results, args.bars, time.perf_counter() - t0), encoding="utf-8", newline="\n"
    )
    bad = sum(len(r["diffs"]) + len(r["rejected_transitions"]) for r in results.values())
    return 0 if bad == 0 else 1
