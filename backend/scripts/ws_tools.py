"""Manual / load testing tools for /ws/market (run from the host, e.g. against Nginx on :80).

    python scripts/ws_tools.py watch --base http://localhost --timeframes 1m 1h --count 5
    python scripts/ws_tools.py load  --base http://localhost --clients 200 --seconds 60
    python scripts/ws_tools.py abort --base http://localhost

Log in with --email/--password (default: the env vars WS_EMAIL / WS_PASSWORD).
"""

import argparse
import asyncio
import json
import os
import statistics
import time
from collections import defaultdict

import httpx
import websockets


def _login(base: str, email: str, password: str) -> str:
    res = httpx.post(f"{base}/api/v1/auth/login", json={"email": email, "password": password})
    res.raise_for_status()
    return res.json()["access_token"]


def _instrument_id(base: str, token: str, source: str, symbol: str) -> str:
    res = httpx.get(
        f"{base}/api/v1/market/instruments",
        params={"source": source, "q": symbol},
        headers={"Authorization": f"Bearer {token}"},
    )
    res.raise_for_status()
    return next(i["id"] for i in res.json()["items"] if i["symbol"] == symbol)


def _ws_url(base: str, token: str) -> str:
    return base.replace("http", "ws", 1) + f"/ws/market?token={token}"


def _sub(instrument_id: str, timeframe: str) -> str:
    body = {"op": "subscribe", "topic": "candles", "instrument_id": instrument_id}
    return json.dumps(body | {"timeframe": timeframe})


async def watch(args, token: str, instrument_id: str) -> None:
    """Print the first --count messages of each timeframe (snapshot + live candles)."""
    seen: dict[str, int] = defaultdict(int)
    async with websockets.connect(_ws_url(args.base, token)) as ws:
        for tf in args.timeframes:
            await ws.send(_sub(instrument_id, tf))
        deadline = time.monotonic() + args.timeout
        while any(seen[tf] < args.count for tf in args.timeframes):
            raw = await asyncio.wait_for(ws.recv(), timeout=max(0.1, deadline - time.monotonic()))
            msg = json.loads(raw)
            tf = msg.get("timeframe") or (msg.get("topic") or "").rsplit(":", 1)[-1]
            if msg["type"] in ("subscribed", "snapshot", "candle") and seen[tf] < args.count:
                seen[tf] += 1
                print(f"[{tf} #{seen[tf]}] {raw}")


async def _load_client(url: str, sub: str, seconds: float, result: dict) -> None:
    try:
        async with websockets.connect(url, open_timeout=30) as ws:
            await ws.send(sub)
            result["connected"] = True
            deadline = time.monotonic() + seconds
            while (left := deadline - time.monotonic()) > 0:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=left)
                except TimeoutError:
                    break
                received_ms = time.time() * 1000
                msg = json.loads(raw)
                if msg["type"] == "candle":
                    result["candles"] += 1
                    result["latency_ms"].append(received_ms - msg["sent_at"])
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"{type(exc).__name__}: {exc}"


async def load(args, token: str, instrument_id: str) -> None:
    url, sub = _ws_url(args.base, token), _sub(instrument_id, "1m")
    results = [
        {"connected": False, "candles": 0, "latency_ms": [], "error": None}
        for _ in range(args.clients)
    ]
    started = time.monotonic()
    await asyncio.gather(*(_load_client(url, sub, args.seconds, r) for r in results))
    ok = [r for r in results if r["connected"] and r["error"] is None]
    counts = [r["candles"] for r in ok]
    latencies = sorted(lat for r in ok for lat in r["latency_ms"])
    errors = defaultdict(int)
    for r in results:
        if r["error"]:
            errors[r["error"]] += 1

    def pct(p: float) -> float:
        return latencies[min(len(latencies) - 1, int(p * len(latencies)))] if latencies else 0.0

    print(
        json.dumps(
            {
                "clients": args.clients,
                "connections_ok": len(ok),
                "errors": dict(errors),
                "duration_s": round(time.monotonic() - started, 1),
                "msgs_per_client": {
                    "min": min(counts, default=0),
                    "avg": round(statistics.fmean(counts), 1) if counts else 0,
                    "max": max(counts, default=0),
                },
                "latency_ms": {
                    "samples": len(latencies),
                    "p50": round(pct(0.50), 1),
                    "p95": round(pct(0.95), 1),
                    "max": round(latencies[-1], 1) if latencies else 0,
                },
            },
            indent=2,
        )
    )


async def abort(args, token: str, instrument_id: str) -> None:
    """Subscribe, then drop the TCP connection without a close frame."""
    ws = await websockets.connect(_ws_url(args.base, token))
    await ws.send(_sub(instrument_id, "1m"))
    print("received:", await ws.recv())
    ws.transport.abort()  # RST, no WebSocket close handshake
    print("connection aborted without a close frame")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["watch", "load", "abort"])
    parser.add_argument("--base", default="http://localhost")
    parser.add_argument("--email", default=os.environ.get("WS_EMAIL"))
    parser.add_argument("--password", default=os.environ.get("WS_PASSWORD"))
    parser.add_argument("--source", default="binance")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--timeframes", nargs="+", default=["1m", "1h"])
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--clients", type=int, default=200)
    parser.add_argument("--seconds", type=float, default=60)
    args = parser.parse_args()

    token = _login(args.base, args.email, args.password)
    instrument_id = _instrument_id(args.base, token, args.source, args.symbol)
    print(f"instrument {args.source}:{args.symbol} = {instrument_id}")
    command = {"watch": watch, "load": load, "abort": abort}[args.command]
    asyncio.run(command(args, token, instrument_id))


if __name__ == "__main__":
    main()
