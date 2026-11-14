# QuantConnect Research notebook, cell 1: what do COMEX gold (GC) ticks look like there?
#
# Paste into a new Research notebook (Python) on quantconnect.com and run. It reads five minutes
# of front-month GC ticks inside QuantConnect's cloud (the data never leaves it) and prints their
# columns and first rows, so the order-flow code can be written for the exact layout.
from AlgorithmImports import *  # noqa: F403

qb = QuantBook()  # noqa: F405
gold = qb.add_future(
    Futures.Metals.GOLD,  # noqa: F405  (GC)
    Resolution.TICK,  # noqa: F405
    data_mapping_mode=DataMappingMode.OPEN_INTEREST,  # noqa: F405
    data_normalization_mode=DataNormalizationMode.RAW,  # noqa: F405
    contract_depth_offset=0,
)
start = datetime(2025, 12, 1, 9, 30)  # noqa: F405  New York time
end = datetime(2025, 12, 1, 9, 35)  # noqa: F405
h = qb.history(gold.symbol, start, end, Resolution.TICK)  # noqa: F405
print(type(h), getattr(h, "shape", None))
if hasattr(h, "columns"):
    print(list(h.index.names), h.columns.tolist())
    print(h.head(30).to_string())
    for col in ("lastprice", "quantity", "bidprice", "askprice"):
        if col in h.columns:
            print(col, "non-empty rows:", int(h[col].notna().sum()))
else:
    print(h)
