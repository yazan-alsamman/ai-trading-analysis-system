# QuantConnect Research notebook, cell 2: where is the GC tick data?
#
# Cell 1 returned an empty frame for the continuous contract at tick resolution. This tries three
# ways and prints which one has rows: (A) the continuous contract at minute resolution, (B) the
# list of GC contracts trading that day, (C) the nearest contracts themselves at tick and minute.
from AlgorithmImports import *  # noqa: F403

qb = QuantBook()  # noqa: F405
gold = qb.add_future(
    Futures.Metals.GOLD,  # noqa: F405
    Resolution.MINUTE,  # noqa: F405
    data_mapping_mode=DataMappingMode.OPEN_INTEREST,  # noqa: F405
    data_normalization_mode=DataNormalizationMode.RAW,  # noqa: F405
    contract_depth_offset=0,
)
d0 = datetime(2025, 12, 1, 9, 30)  # noqa: F405  New York time
d1 = datetime(2025, 12, 1, 9, 35)  # noqa: F405


def show(name, h):
    print(f"--- {name}: {type(h).__name__} {getattr(h, 'shape', None)}")
    if hasattr(h, "columns") and len(h):
        print(list(h.index.names), h.columns.tolist())
        print(h.head(8).to_string())


try:
    show("A continuous, minute", qb.history(gold.symbol, d0, d1, Resolution.MINUTE))  # noqa: F405
except Exception as e:
    print("A error:", e)

contracts = []
try:
    contracts = sorted(qb.future_chain_provider.get_future_contract_list(gold.symbol, d0),
                       key=lambda s: s.id.date)  # fmt: skip
    print("--- B contracts:", [f"{c.value} expires {c.id.date:%Y-%m-%d}" for c in contracts[:6]])
except Exception as e:
    print("B error:", e)

for c in contracts[:3]:
    try:
        qb.add_future_contract(c, Resolution.TICK)  # noqa: F405
        show(f"C tick {c.value}", qb.history(c, d0, d1, Resolution.TICK))  # noqa: F405
        show(f"C minute {c.value}", qb.history(c, d0, d1, Resolution.MINUTE))  # noqa: F405
    except Exception as e:
        print("C error:", c, e)
