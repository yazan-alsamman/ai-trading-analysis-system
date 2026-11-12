"""Gold's volatility outlook for the user (``docs/vol/SERVING.md``): information only.

M3 of ``docs/vol/VOL_FORECAST.md`` (HAR + scheduled USD news + weekday) in its 15m form,
forecasting the realised variance of today's 02:00-16:45 New York window at 02:00 from the bars
closed by then and the day's calendar. **It changes no setup, state, size or abstention.**

The day and news definitions here are the ones the research used (``app.research.vol_forecast``
imports them), so the served number is the tested one. Nothing reads a clock, a random source or
a file other than the frozen parameters."""

from __future__ import annotations

import json
import re
from functools import cache
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel

NY = "America/New_York"
W_FROM, W_END = 2 * 60, 16 * 60 + 45  # window: bar opens >= 02:00, closes <= 16:45 New York
MIN_SHARE, MAX_GAP = 0.9, 30  # share of window bars, longest missing time (minutes)
EARLY = 8 * 60 + 30
TOP3 = ("Nonfarm Payrolls", "CPI m/m", "Fed Interest Rate Decision")
FED = "Fed Interest Rate Decision"
HAR = ["rv1", "rv5", "rv22", "on"]
NEWS = ["top3", "fed", "uh1", "uh2", "early"]
WEEK = ["tue", "wed", "thu", "fri"]
M3 = HAR + NEWS + WEEK
STEP = 15  # the service's bars (``SERVING.md`` §1)
HISTORY_DAYS = 22
PARAMS = Path(__file__).resolve().parents[1] / "config" / "volatility_v1.json"
LEVELS = ((0.8, "quiet"), (1.25, "normal"), (1.6, "lively"))  # above: very_lively (wording only)


# --- days and news (shared with the research) ------------------------------------------------


def at_ny(days: pd.DatetimeIndex | pd.Series, minutes: int) -> pd.DatetimeIndex:
    """The UTC instant of ``minutes`` after New York midnight on each (naive) date."""
    d = pd.DatetimeIndex(days) + pd.Timedelta(minutes=minutes)
    return d.tz_localize(NY).tz_convert("UTC")


def days(m: pd.DataFrame, step: int = 5) -> tuple[pd.DataFrame, np.ndarray]:
    """One row per New York weekday with window bars (RV, bars, missing time, range, the price
    at 02:00, the bars closing by 02:00 and by 16:45) and the running sum of squared returns.
    ``step``: the bar length in minutes (5 in parts 1-2; 15 for the service, ``SERVING.md``)."""
    ny = m["ts_utc"].dt.tz_convert(NY)
    omin = (ny.dt.hour * 60 + ny.dt.minute).to_numpy()
    c = m["close"].to_numpy(float)
    r2 = np.r_[0.0, np.diff(np.log(c))] ** 2
    win = (omin >= W_FROM) & (omin + step <= W_END) & (ny.dt.day_of_week < 5).to_numpy()
    w = pd.DataFrame({"day": ny.dt.tz_localize(None).dt.normalize().to_numpy()[win],
                      "omin": omin[win], "r2": r2[win], "high": m["high"].to_numpy()[win],
                      "low": m["low"].to_numpy()[win]})  # fmt: skip
    prev = w.groupby("day")["omin"].shift(1).fillna(W_FROM - step).to_numpy()
    w["miss"] = w["omin"].to_numpy() - prev - step
    g = w.groupby("day")
    d = pd.DataFrame({"rv": g["r2"].sum(), "n": g["omin"].size(), "hi": g["high"].max(),
                      "lo": g["low"].min(), "miss": g["miss"].max(),
                      "last": g["omin"].max()})  # fmt: skip
    d["miss"] = np.maximum(d["miss"], W_END - step - d["last"])
    d["used"] = (d["n"] >= MIN_SHARE * ((W_END - W_FROM) // step)) & (d["miss"] <= MAX_GAP)
    # the price at 02:00: the last bar closing by then
    cu = m["close_utc"].to_numpy()
    k02 = np.searchsorted(cu, at_ny(d.index, W_FROM).to_numpy(), "right") - 1
    d["p02"] = np.where(k02 >= 0, c[np.maximum(k02, 0)], np.nan)
    d["k02"] = k02
    d["k1645"] = np.searchsorted(cu, at_ny(d.index, W_END).to_numpy(), "right") - 1
    return d.drop(columns=["last"]), np.cumsum(r2)


def news(cal: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
    """Scheduled USD importance-3 releases inside each day's window (02:00-16:45 inclusive)."""
    u = cal[(cal["currency"] == "USD") & (cal["importance"] == 3)]
    t = u["ts_utc"].dt.tz_convert(NY)
    mins = (t.dt.hour * 60 + t.dt.minute).to_numpy()
    e = pd.DataFrame({"day": t.dt.tz_localize(None).dt.normalize().to_numpy(), "min": mins,
                      "event": u["event"].to_numpy()})  # fmt: skip
    e = e[(e["min"] >= W_FROM) & (e["min"] <= W_END)]
    e["top3"] = e["event"].isin(TOP3)
    e["fed"] = e["event"] == FED
    e["other"] = ~e["top3"]
    e["early"] = e["min"] <= EARLY
    g = e.groupby("day")[["top3", "fed", "other", "early"]].sum().reindex(index, fill_value=0)
    out = pd.DataFrame(index=index)
    out["top3"] = g["top3"] > 0
    out["fed"] = g["fed"] > 0
    out["uh1"] = g["other"] == 1
    out["uh2"] = g["other"] >= 2
    out["early"] = g["early"] > 0
    return out.astype(float)


# --- the calendar the backend sends ------------------------------------------------------------

_TITLES = (
    (re.compile(r"non-?farm (payrolls|employment change)", re.I), "Nonfarm Payrolls"),
    (re.compile(r"^(cpi|consumer price index) ?(m/m|\(?mom\)?)$", re.I), "CPI m/m"),
    (
        re.compile(
            r"^(fed(eral)? (interest|funds) rate( decision)?|fomc (statement|rate decision)"
            r"|federal funds rate)$",
            re.I,
        ),
        FED,
    ),  # fmt: skip
)


def canonical(title: str) -> str:
    """The research calendar's name of a TOP3 release (``SERVING.md`` §5.3); other titles as
    they are."""
    t = " ".join(title.split())
    for rx, name in _TITLES:
        if rx.search(t):
            return name
    return t


def calendar_frame(events: list) -> pd.DataFrame:
    """The request's ``CalendarEvent`` list in the research calendar's columns (high = 3)."""
    return pd.DataFrame({
        "ts_utc": pd.to_datetime([e.ts for e in events], utc=True),
        "currency": [e.currency for e in events],
        "importance": [3 if e.impact == "high" else 0 for e in events],
        "event": [canonical(e.title) for e in events],
        "title": [e.title for e in events],
    })  # fmt: skip


# --- the outlook -------------------------------------------------------------------------------


class Range(BaseModel):
    p20: float
    p50: float
    p80: float


class NewsItem(BaseModel):
    ts: str
    title: str
    top3: bool


class VolatilityOutlook(BaseModel):
    """Today's expected size of gold's move, 02:00-16:45 New York. Information, not advice."""

    status: Literal["ok", "outside_window", "insufficient_history", "not_supported"]
    model: str | None = None
    day: str | None = None
    window: str = "02:00-16:45 America/New_York"
    expected_move_pct: float | None = None
    range_pct: Range | None = None
    range_usd: Range | None = None
    level: Literal["quiet", "normal", "lively", "very_lively"] | None = None
    news: list[NewsItem] = []


@cache
def params(path: Path = PARAMS) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def row(m: pd.DataFrame, cal: pd.DataFrame, day: pd.Timestamp, step: int = STEP) -> dict | None:
    """M3's features for ``day`` (naive New York date) from bars closed by 02:00 and ``cal``;
    None without 22 used days after the data's first day."""
    t02 = at_ny(pd.DatetimeIndex([day]), W_FROM)[0]
    mm = m[m["close_utc"] <= t02].reset_index(drop=True)
    if mm.empty:
        return None
    d, cum = days(mm, step)
    first = mm["ts_utc"].dt.tz_convert(NY).dt.tz_localize(None).dt.normalize().iloc[0]
    used = d[d["used"] & (d.index < day) & (d.index > first)]
    if len(used) < HISTORY_DAYS:
        return None
    rv = used["rv"].to_numpy()
    on = cum[len(mm) - 1] - cum[int(used["k1645"].iloc[-1])]
    x = {"rv1": np.log(rv[-1]), "rv5": np.log(rv[-5:].mean()), "rv22": np.log(rv[-22:].mean()),
         "on": np.log(max(on, 1e-12))}  # fmt: skip
    x.update(news(cal, pd.DatetimeIndex([day])).iloc[0].to_dict())
    for i, name in enumerate(WEEK, start=1):
        x[name] = float(day.day_of_week == i)
    x["p02"] = float(mm["close"].iloc[-1])
    x["mean22"] = float(rv[-22:].mean())
    return x


def outlook(m: pd.DataFrame, cal: pd.DataFrame, as_of: pd.Timestamp,
            p: dict | None = None) -> VolatilityOutlook:  # fmt: skip
    """The outlook at ``as_of`` (UTC) from 15m bars ``m`` (``ts_utc``, ``close_utc``, ``open``,
    ``high``, ``low``, ``close``) and the request's calendar in research columns."""
    p = p or params()
    ny = as_of.tz_convert(NY)
    mins = ny.hour * 60 + ny.minute
    if ny.day_of_week >= 5 or mins < W_FROM or mins > W_END:
        return VolatilityOutlook(status="outside_window")
    day = pd.Timestamp(ny.date())
    x = row(m, cal, day)
    if x is None:
        return VolatilityOutlook(status="insufficient_history")
    beta = p["m3"]["coef"]
    f = beta["const"] + sum(beta[k] * x[k] for k in M3)
    var = float(np.exp(f + p["m3"]["s2"] / 2))
    vol = np.sqrt(var)
    k = p["range_k"]
    ratio = var / x["mean22"]
    level = next((name for lim, name in LEVELS if ratio < lim), "very_lively")
    u = cal[(cal["currency"] == "USD") & (cal["importance"] == 3)]
    t = u["ts_utc"].dt.tz_convert(NY)
    mins_e = t.dt.hour * 60 + t.dt.minute
    on_day = (t.dt.tz_localize(None).dt.normalize() == day) & (mins_e >= W_FROM) & (mins_e <= W_END)
    items = [NewsItem(ts=ts.strftime("%Y-%m-%dT%H:%M:%SZ"), title=str(title), top3=ev in TOP3)
             for ts, title, ev in zip(u["ts_utc"][on_day], u.get("title", u["event"])[on_day],
                                      u["event"][on_day], strict=True)]  # fmt: skip
    return VolatilityOutlook(
        status="ok",
        model=p["model"],
        day=day.strftime("%Y-%m-%d"),
        expected_move_pct=round(100 * vol, 3),
        range_pct=Range(**{q: round(100 * vol * k[q], 3) for q in ("p20", "p50", "p80")}),
        range_usd=Range(**{q: round(x["p02"] * vol * k[q], 2) for q in ("p20", "p50", "p80")}),
        level=level,
        news=sorted(items, key=lambda n: (n.ts, n.title)),
    )
