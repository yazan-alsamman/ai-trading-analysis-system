"""Turn a load-test run into one Markdown table (run.sh calls it):

    python infra/loadtest/summarize.py infra/loadtest/out

Reads ``summary.json`` (k6) and ``stats.csv`` (docker stats samples) and prints latency
percentiles, errors and 429s per endpoint, WebSocket fan-out delay and the memory / CPU peak of
each container next to its production limit.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

PROD_MEM_MIB = {
    "backend": 384,
    "worker": 384,
    "worker-backtest": 512,
    "beat": 192,
    "telegram-bot": 128,
    "redis": 192,
    "db": 768,
    "nginx": 64,
    "ai-service": 256,
}
PROD_CPUS = {
    "backend": 1.0,
    "worker": 0.75,
    "worker-backtest": 1.0,
    "beat": 0.25,
    "telegram-bot": 0.25,
    "redis": 0.5,
    "db": 1.0,
    "nginx": 0.25,
    "ai-service": 0.5,
}
UNITS = {"B": 1 / 2**20, "KiB": 1 / 1024, "MiB": 1, "GiB": 1024}
ENDPOINTS = ["candles", "indicators", "signals", "news", "posts"]


def mib(text: str) -> float:
    m = re.match(r"([\d.]+)\s*([KMG]?i?B)", text.strip())
    return float(m.group(1)) * UNITS[m.group(2)] if m else 0.0


def service(container: str) -> str:
    # aitradinganalysissystem-worker-backtest-1 -> worker-backtest
    return re.sub(r"^[^-]+-(.*)-\d+$", r"\1", container)


def main(out: Path) -> int:
    metrics = json.loads((out / "summary.json").read_text())["metrics"]

    def val(name: str, stat: str) -> float:
        return metrics.get(name, {}).get("values", {}).get(stat, 0)

    print("| endpoint | requests | p50 ms | p95 ms | p99 ms | max ms | errors | 429 |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    for ep in ENDPOINTS:
        lat = f"lat_{ep}"
        print(
            f"| {ep} | {val(lat, 'count'):.0f} | {val(lat, 'med'):.0f} | {val(lat, 'p(95)'):.0f}"
            f" | {val(lat, 'p(99)'):.0f} | {val(lat, 'max'):.0f}"
            f" | {val(f'err_{ep}', 'count'):.0f} | {val(f'r429_{ep}', 'count'):.0f} |"
        )
    print(
        f"\nhttp_reqs {val('http_reqs', 'count'):.0f} ({val('http_reqs', 'rate'):.1f}/s), "
        f"failed {val('http_req_failed', 'rate') * 100:.2f}%"
    )
    print(
        f"WebSocket: {val('ws_connected', 'count'):.0f} connected, "
        f"{val('ws_candle_messages', 'count'):.0f} candle messages, "
        f"{val('ws_errors', 'count'):.0f} errors; fan-out delay "
        f"p50 {val('ws_fanout_delay', 'med'):.0f} ms, p95 {val('ws_fanout_delay', 'p(95)'):.0f}"
        f" ms, p99 {val('ws_fanout_delay', 'p(99)'):.0f} ms, max "
        f"{val('ws_fanout_delay', 'max'):.0f} ms"
    )

    peaks: dict[str, tuple[float, float]] = {}
    with (out / "stats.csv").open() as fh:
        for name, mem, cpu in csv.reader(fh):
            svc = service(name)
            m, c = mib(mem.split("/")[0]), float(cpu.rstrip("%") or 0)
            pm, pc = peaks.get(svc, (0.0, 0.0))
            peaks[svc] = (max(pm, m), max(pc, c))
    print("\n| service | peak memory MiB | prod limit MiB | % of limit | peak CPU % | prod cpus |")
    print("|---|---:|---:|---:|---:|---:|")
    for svc, (m, c) in sorted(peaks.items()):
        limit = PROD_MEM_MIB.get(svc)
        share = f"{m / limit * 100:.0f}%" if limit else "-"
        print(
            f"| {svc} | {m:.0f} | {limit or '-'} | {share} | {c:.0f} | {PROD_CPUS.get(svc, '-')} |"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1] if len(sys.argv) > 1 else "infra/loadtest/out")))
