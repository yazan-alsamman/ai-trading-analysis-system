"""The built-in tagger's map: instrument symbol -> words that mean it in a headline.

Codes (``BTC``) match case-sensitively as whole words; names (``Bitcoin``) case-insensitively;
Arabic names as substrings (they take prefixes such as "ال" or "و"). Symbols are matched against
``instruments.symbol`` of every source, so ``BTC/USDT`` tags the Binance pair. Instruments not
listed here are tagged by their base asset code when it is at least three letters (crypto only).
The AI side can replace an article's tags through ``POST /ingest/news``.
"""

ALIASES: dict[str, dict[str, tuple[str, ...]]] = {
    "BTC/USDT": {"codes": ("BTC", "XBT"), "names": ("bitcoin",), "ar": ("بيتكوين", "بتكوين")},
    "ETH/USDT": {"codes": ("ETH",), "names": ("ethereum", "ether"), "ar": ("إيثريوم", "ايثريوم")},
    "BNB/USDT": {"codes": ("BNB",), "names": ("binance coin",), "ar": ()},
    "SOL/USDT": {"codes": ("SOL",), "names": ("solana",), "ar": ("سولانا",)},
    "XRP/USDT": {"codes": ("XRP",), "names": ("ripple",), "ar": ("ريبل",)},
    "EUR/USD": {"codes": ("EUR/USD", "EURUSD"), "names": ("euro",), "ar": ("اليورو",)},
    "GBP/USD": {
        "codes": ("GBP/USD", "GBPUSD"),
        "names": ("sterling", "cable"),
        "ar": ("الإسترليني",),
    },
    "USD/JPY": {"codes": ("USD/JPY", "USDJPY"), "names": ("japanese yen",), "ar": ("الين",)},
    "XAU/USD": {"codes": ("XAU/USD", "XAUUSD", "XAU"), "names": ("gold",), "ar": ("الذهب",)},
}

TITLE_RELEVANCE = 1.0  # the instrument is named in the title
SUMMARY_RELEVANCE = 0.6  # only in the summary
