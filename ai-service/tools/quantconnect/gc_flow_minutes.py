# QuantConnect Research notebook: COMEX gold (GC) order flow, aggregated to one-minute rows.
#
# Runs inside QuantConnect's cloud; the raw ticks never leave it. For each New York calendar day
# it picks the active GC contract (the most traded over the three previous days: no look-ahead),
# reads its ticks hour by hour, signs every trade by the Lee-Ready rule (against the bid / ask in
# force just before it; at the mid, the tick rule) and writes one row per minute to the Object
# Store as a CSV per month (resumable: days already saved are skipped). Download the CSVs from
# the project's Object Store page, then compare with FxPro's XAUUSD on the laptop.
#
# Minute row (time = the minute's start, New York): contract, trades, volume, buy_vol, sell_vol,
# unsigned_vol, delta (buy - sell), big_buy / big_sell (volume of trades of BIG lots or more),
# open / high / low / close (trades), vwap, bid_close / ask_close / mid_close (last quote),
# spread_mean (mean quoted spread over the quote updates), depth_imb (mean of
# (bidsize - asksize) / (bidsize + asksize) over the quote updates).
import io
import os

import numpy as np
import pandas as pd
from AlgorithmImports import *  # noqa: F403

START, END = date(2025, 10, 1), date(2025, 12, 31)  # noqa: F405  the 3-month sample
BIG = 10  # lots: a "large" trade
KEY = "gc_flow/{:%Y%m}.csv"

qb = QuantBook()  # noqa: F405
canon = qb.add_future(
    Futures.Metals.GOLD,  # noqa: F405
    Resolution.MINUTE,  # noqa: F405
    extended_market_hours=True,
).symbol  # nearly 23 h a day, not only 08:20-13:30
added = set()


def active_contract(d: date):  # noqa: F405
    """The listed contract with the most volume over the 3 days before ``d``."""
    t0 = datetime(d.year, d.month, d.day)  # noqa: F405
    listed = sorted(
        qb.future_chain_provider.get_future_contract_list(canon, t0), key=lambda s: s.id.date
    )[:5]
    best, best_vol = None, -1.0
    for c in listed:
        if c not in added:
            qb.add_future_contract(c, Resolution.TICK, extended_market_hours=True)  # noqa: F405
            added.add(c)
        h = qb.history(c, t0 - timedelta(days=3), t0, Resolution.MINUTE)  # noqa: F405
        vol = float(h["volume"].sum()) if len(h) and "volume" in h.columns else 0.0
        if vol > best_vol:
            best, best_vol = c, vol
    return best


def sign_trades(ticks: pd.DataFrame) -> pd.DataFrame:
    """Trades with the bid / ask in force just before them and a Lee-Ready sign."""
    t = ticks.reset_index()
    t = t.sort_values("time", kind="stable")
    q = t[(t["bidprice"] > 0) | (t["askprice"] > 0)][
        ["time", "bidprice", "askprice", "bidsize", "asksize"]
    ].copy()
    q["bid"] = q["bidprice"].where(q["bidprice"] > 0).ffill()
    q["ask"] = q["askprice"].where(q["askprice"] > 0).ffill()
    tr = t[(t["quantity"] > 0) & t["lastprice"].notna()][["time", "lastprice", "quantity"]]
    tr = pd.merge_asof(
        tr, q[["time", "bid", "ask"]], on="time", direction="backward", allow_exact_matches=False
    )
    mid = (tr["bid"] + tr["ask"]) / 2
    px = tr["lastprice"]
    tick = np.sign(px.diff()).replace(0, np.nan).ffill().fillna(0)
    s = np.where(px > mid, 1, np.where(px < mid, -1, np.nan))
    tr["sign"] = np.where(np.isnan(s), tick, s)
    return tr, q


def minutes(d: date) -> pd.DataFrame:  # noqa: F405
    c = active_contract(d)
    if c is None:
        return pd.DataFrame()
    rows = []
    for hour in range(24):
        h0 = datetime(d.year, d.month, d.day, hour)  # noqa: F405
        h1 = h0 + timedelta(hours=1) - timedelta(microseconds=1)  # noqa: F405  no tick twice
        ticks = qb.history(c, h0, h1, Resolution.TICK)  # noqa: F405
        if not len(ticks):
            continue
        tr, q = sign_trades(ticks)
        if not len(tr):
            continue
        tr["m"] = tr["time"].dt.floor("min")
        tr["buy"] = np.where(tr["sign"] > 0, tr["quantity"], 0.0)
        tr["sell"] = np.where(tr["sign"] < 0, tr["quantity"], 0.0)
        tr["unsigned"] = np.where(tr["sign"] == 0, tr["quantity"], 0.0)
        tr["bigb"] = np.where(tr["quantity"] >= BIG, tr["buy"], 0.0)
        tr["bigs"] = np.where(tr["quantity"] >= BIG, tr["sell"], 0.0)
        tr["pv"] = tr["lastprice"] * tr["quantity"]
        g = tr.groupby("m")
        m = pd.DataFrame(
            {
                "trades": g.size(),
                "volume": g["quantity"].sum(),
                "buy_vol": g["buy"].sum(),
                "sell_vol": g["sell"].sum(),
                "unsigned_vol": g["unsigned"].sum(),
                "big_buy": g["bigb"].sum(),
                "big_sell": g["bigs"].sum(),
                "open": g["lastprice"].first(),
                "high": g["lastprice"].max(),
                "low": g["lastprice"].min(),
                "close": g["lastprice"].last(),
                "vwap": g["pv"].sum() / g["quantity"].sum(),
            }
        )
        m["delta"] = m["buy_vol"] - m["sell_vol"]
        q = q.dropna(subset=["bid", "ask"]).copy()
        q["m"] = q["time"].dt.floor("min")
        q["spread"] = q["ask"] - q["bid"]
        tot = q["bidsize"] + q["asksize"]
        q["imb"] = np.where(tot > 0, (q["bidsize"] - q["asksize"]) / tot, np.nan)
        gq = q.groupby("m")
        m = m.join(
            pd.DataFrame(
                {
                    "bid_close": gq["bid"].last(),
                    "ask_close": gq["ask"].last(),
                    "spread_mean": gq["spread"].mean(),
                    "depth_imb": gq["imb"].mean(),
                }
            ),
            how="outer",
        )
        rows.append(m)
    if not rows:
        return pd.DataFrame()
    out = pd.concat(rows).sort_index()
    out["mid_close"] = (out["bid_close"] + out["ask_close"]) / 2
    out["contract"] = c.value
    out.index.name = "time"
    return out


def load(key: str) -> pd.DataFrame:
    """A month already saved: the project's folder (the free plan cannot write the Object
    Store), else the Object Store when allowed."""
    if os.path.exists(key):
        return pd.read_csv(key, parse_dates=["time"])
    try:
        if qb.object_store.contains_key(key):
            return pd.read_csv(io.StringIO(qb.object_store.read(key)), parse_dates=["time"])
    except Exception:
        pass
    return pd.DataFrame()


def save(key: str, df: pd.DataFrame) -> None:
    os.makedirs(os.path.dirname(key), exist_ok=True)
    df.to_csv(key, index=False)


def run(start: date = START, end: date = END) -> None:  # noqa: F405
    print("saving under", os.path.abspath(os.path.dirname(KEY.format(start))))
    d = start
    while d <= end:
        key = KEY.format(d)
        old = load(key)
        done = set(old["time"].dt.date) if len(old) else set()
        month = [old] if len(old) else []
        while d <= end and f"{d:%Y%m}" == key[8:14]:
            if d.weekday() != 5 and d not in done:  # no Saturday session
                try:
                    m = minutes(d)
                    if len(m):
                        month.append(m.reset_index())
                    span = f"{m.index.min():%H:%M}-{m.index.max():%H:%M}" if len(m) else "-"
                    print(d, "rows", len(m), m["contract"].iloc[0] if len(m) else "-", span)
                except Exception as e:
                    print(d, "error", e)
                if month:
                    save(key, pd.concat(month))
            d += timedelta(days=1)  # noqa: F405


run()
