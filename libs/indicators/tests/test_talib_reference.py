"""Our numbers vs TA-Lib (dev-only reference) on synthetic and real BTCUSDT data."""

import numpy as np
import pandas as pd
import pytest

import trading_indicators as ti

talib = pytest.importorskip("talib")

RTOL = ATOL = 1e-8


def _arrays(df: pd.DataFrame):
    return tuple(df[c].to_numpy(np.float64) for c in ("open", "high", "low", "close", "volume"))


def _cases(df: pd.DataFrame):
    _, h, lo, c, v = _arrays(df)
    close = df["close"]
    m = ti.macd(close, 12, 26, 9)
    tm = talib.MACD(c, 12, 26, 9)
    a = ti.adx(df, 14)
    bb = ti.bollinger(close, 20, 2.0)
    tbb = talib.BBANDS(c, 20, 2.0, 2.0, 0)
    st = ti.stoch(df, 14, 3, 3)
    tst = talib.STOCH(h, lo, c, 14, 3, 0, 3, 0)
    raw = ti.stochrsi(close, 14, 14, 1, 3)
    traw = talib.STOCHRSI(c, 14, 14, 3, 0)
    srsi = ti.stochrsi(close, 14, 14, 3, 3)
    r = talib.RSI(c, 14)
    tsrsi = talib.STOCH(r, r, r, 14, 3, 0, 3, 0)  # smoothed StochRSI = STOCH applied to RSI
    return {
        "sma": (ti.sma(close, 20), talib.SMA(c, 20)),
        "ema": (ti.ema(close, 20), talib.EMA(c, 20)),
        "ema_50": (ti.ema(close, 50), talib.EMA(c, 50)),
        "wma": (ti.wma(close, 20), talib.WMA(c, 20)),
        "macd.macd": (m["macd"], tm[0]),
        "macd.signal": (m["signal"], tm[1]),
        "macd.histogram": (m["histogram"], tm[2]),
        "rsi": (ti.rsi(close, 14), talib.RSI(c, 14)),
        "adx.adx": (a["adx"], talib.ADX(h, lo, c, 14)),
        "adx.plus_di": (a["plus_di"], talib.PLUS_DI(h, lo, c, 14)),
        "adx.minus_di": (a["minus_di"], talib.MINUS_DI(h, lo, c, 14)),
        "bollinger.upper": (bb["upper"], tbb[0]),
        "bollinger.middle": (bb["middle"], tbb[1]),
        "bollinger.lower": (bb["lower"], tbb[2]),
        "atr": (ti.atr(df, 14), talib.ATR(h, lo, c, 14)),
        "stoch.k": (st["k"], tst[0]),
        "stoch.d": (st["d"], tst[1]),
        "stochrsi_raw.k": (raw["k"], traw[0]),
        "stochrsi_raw.d": (raw["d"], traw[1]),
        "stochrsi.k": (srsi["k"], tsrsi[0]),
        "stochrsi.d": (srsi["d"], tsrsi[1]),
        "cci": (ti.cci(df, 20), talib.CCI(h, lo, c, 20)),
        "williams_r": (ti.williams_r(df, 14), talib.WILLR(h, lo, c, 14)),
        "roc": (ti.roc(close, 10), talib.ROC(c, 10)),
        "mfi": (ti.mfi(df, 14), talib.MFI(h, lo, c, v, 14)),
        "obv": (ti.obv(df), talib.OBV(c, v)),
        "keltner.middle": (ti.keltner(df)["middle"], talib.EMA(c, 20)),
        "keltner.upper": (ti.keltner(df)["upper"], talib.EMA(c, 20) + 2 * talib.ATR(h, lo, c, 10)),
    }


def max_abs_diff(ours: pd.Series, ref: np.ndarray) -> float:
    ours = np.asarray(ours, np.float64)
    valid = ~np.isnan(ref)
    return float(np.max(np.abs(ours[valid] - ref[valid]))) if valid.any() else 0.0


@pytest.mark.parametrize(
    "case",
    [
        "sma", "ema", "ema_50", "wma", "macd.macd", "macd.signal", "macd.histogram", "rsi",
        "adx.adx", "adx.plus_di", "adx.minus_di", "bollinger.upper", "bollinger.middle",
        "bollinger.lower", "atr", "stoch.k", "stoch.d", "stochrsi_raw.k", "stochrsi_raw.d",
        "stochrsi.k", "stochrsi.d", "cci", "williams_r", "roc", "mfi", "obv", "keltner.middle",
        "keltner.upper",
    ],
)  # fmt: skip
def test_matches_talib(dataset: pd.DataFrame, case: str) -> None:
    ours, ref = _cases(dataset)[case]
    ours = np.asarray(ours, np.float64)
    valid = ~np.isnan(ref)
    assert valid.sum() > len(ref) * 0.9
    # once TA-Lib has a value we have one too, and it is the same
    assert not np.isnan(ours[valid]).any()
    np.testing.assert_allclose(ours[valid], ref[valid], rtol=RTOL, atol=ATOL)
    # we never produce a value before TA-Lib, except outputs TA-Lib aligns to a common start
    first_ours, first_ref = np.argmax(~np.isnan(ours)), np.argmax(valid)
    assert first_ours <= first_ref
