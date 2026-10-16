"""Examples of the main request bodies in the OpenAPI document (docs/api/openapi.json). They are
the bodies the Postman collection runs against the API, with placeholders for ids."""

INSTRUMENT = "3f2b8c1e-7a4d-4c2b-9e1f-5a6b7c8d9e01"
POST_ID = "6a1c2d3e-4f50-4617-8293-a4b5c6d7e8f9"
PLAN = "9b8a7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d"
EXPERT = "1c2d3e4f-5a6b-4c7d-8e9f-0a1b2c3d4e5f"

EXAMPLES: dict[str, dict] = {
    "UserCreate": {"email": "trader@example.com", "password": "Passw0rd123", "full_name": "Omar"},
    "LoginRequest": {"email": "trader@example.com", "password": "Passw0rd123"},
    "ApiKeyCreate": {
        "name": "my bot",
        "scopes": ["market:read", "indicators:read", "signals:read", "news:read", "stream"],
        "expires_in_days": 30,
        "rate_limit_per_minute": 30,
    },
    "IndicatorsRequest": {
        "timeframe": "1h",
        "limit": 200,
        "indicators": [
            {"name": "rsi", "params": {"length": 14}},
            {"name": "ema", "params": {"length": 21}},
            {"name": "bollinger", "params": {"length": 20, "std": 2}},
        ],
    },
    "StrategyPreviewRequest": {
        "instrument_id": INSTRUMENT,
        "timeframe": "1h",
        "params": {"fast": 9, "slow": 21},
        "limit": 300,
    },
    "UserStrategyCreate": {
        "strategy_key": "ma_crossover",
        "instrument_id": INSTRUMENT,
        "timeframe": "1h",
        "params": {"fast": 9, "slow": 21},
        "name": "BTC 1h EMA cross",
        "is_active": True,
        "notify": True,
        "risk_override": None,
    },
    "RiskProfileUpdate": {
        "account_size": 25000,
        "quote_currency": "USDT",
        "config": {
            "stop": {"type": "atr", "length": 14, "multiplier": 2.0},
            "take_profit": {
                "type": "r_multiple",
                "levels": [{"r": 1, "close_pct": 50}, {"r": 2, "close_pct": 50}],
            },
            "sizing": {"mode": "risk", "risk_pct": 1.0, "max_position_pct": 100},
            "fee_bps": 10,
        },
    },
    "PositionSizeRequest": {"instrument_id": INSTRUMENT, "timeframe": "1h", "side": "buy"},
    "CustomStrategyCreate": {
        "name": "RSI + Bollinger dip",
        "description": "Buy oversold closes under the lower band, sell RSI > 65.",
        "kind": "builder",
        "definition": {
            "schema_version": 1,
            "category": "mean_reversion",
            "strength": "fixed",
            "buy": {
                "all": [
                    {
                        "left": {"type": "indicator", "name": "rsi", "params": {"length": 14}},
                        "op": "<",
                        "right": {"type": "constant", "value": 35},
                    },
                    {
                        "left": {"type": "price", "field": "close"},
                        "op": "<",
                        "right": {
                            "type": "indicator",
                            "name": "bollinger",
                            "params": {"length": 20, "std": 2},
                            "output": "lower",
                        },
                    },
                ]
            },
            "sell": {
                "any": [
                    {
                        "left": {"type": "indicator", "name": "rsi", "params": {"length": 14}},
                        "op": ">",
                        "right": {"type": "constant", "value": 65},
                    }
                ]
            },
        },
        "visibility": "private",
    },
    "BacktestCreate": {
        "instrument_id": INSTRUMENT,
        "timeframe": "1h",
        "strategy_key": "ma_crossover",
        "params": {"fast": 9, "slow": 21},
        "start": "2026-08-01T00:00:00Z",
        "end": "2026-10-01T00:00:00Z",
        "config": {
            "initial_capital": 10000,
            "fee_bps": 10,
            "slippage_bps": 5,
            "sizing": {"mode": "risk", "risk_pct": 1.0},
            "stop": {"type": "atr", "length": 14, "multiplier": 2},
        },
    },
    "WorkspaceCreate": {"name": "Scalping", "template": "multi_chart"},
    "PostCreate": {
        "title": "BTC: range break or fake-out?",
        "body": "## Plan\n\nWatching **64k** as resistance. A 1h close above it targets 66k.",
        "instrument_id": INSTRUMENT,
        "timeframe": "1h",
        "direction": "bullish",
        "attachments": [],
        "visibility": "public",
    },
    "CommentCreate": {"body": "What about ETH? Same structure on the 4h."},
    "ReportCreate": {"target_type": "post", "target_id": POST_ID, "reason": "pump and dump"},
    "PriceAlertCreate": {
        "instrument_id": INSTRUMENT,
        "condition": "crosses_above",
        "value": 70000,
        "repeat": "every",
        "cooldown_minutes": 120,
        "note": "breakout above 70k",
    },
    "PreferencesIn": {
        "matrix": {"signal": {"telegram": True, "email": True, "push": True}},
        "min_signal_strength": 0.6,
        "quiet_hours": {"start": "23:00", "end": "07:00", "tz": "Asia/Damascus"},
        "language": "en",
    },
    "IngestRequest": {
        "articles": [
            {
                "source_key": "finnhub",
                "external_id": "finnhub-123456",
                "url": "https://example.com/news/bitcoin-etf-inflows",
                "title": "Bitcoin climbs as spot ETF inflows hit a weekly record",
                "published_at": "2026-10-16T12:30:00Z",
                "instruments": [{"symbol": "BTC/USDT", "relevance": 1.0}],
                "sentiment": {"label": "positive", "score": 0.71, "model": "finbert-ft-v1"},
            }
        ]
    },
    "ExpertProfileIn": {
        "headline": "BTC swing trades with clear stops",
        "bio": "## About\n\n10 years of **crypto** trading.",
        "markets": ["crypto", "gold"],
        "languages": ["ar", "en"],
        "response_time_hint": "within 24h",
    },
    "PlanIn": {
        "name": "Monthly Pro",
        "price": "29.00",
        "interval": "month",
        "trial_days": 7,
        "perks": {"premium_posts": True, "chat": True, "signals_feed": True},
    },
    "CheckoutRequest": {"plan_id": PLAN, "return_url": "http://localhost:5173/billing/done"},
    "ConversationOpen": {"expert_id": EXPERT},
    "MessageCreate": {
        "body": "What is your stop for BTC?",
        "client_id": "6f1c2a3b-4d5e-4f60-8172-9a0b1c2d3e4f",
        "attachments": [],
    },
}
