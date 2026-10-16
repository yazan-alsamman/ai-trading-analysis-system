"""Custom strategy definitions and helpers shared by the custom strategy tests."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.custom_strategy import CustomStrategy, CustomStrategyKind, Visibility
from app.models.user import User
from app.schemas.custom_strategies import CustomStrategyCreate
from app.services import custom_strategy_service

MINE = "/api/v1/me/custom-strategies"
PUBLIC = "/api/v1/custom-strategies/public"


def ind(name: str, shift: int = 0, output: str | None = None, **params) -> dict:
    op = {"type": "indicator", "name": name, "params": params, "shift": shift}
    if output is not None:
        op["output"] = output
    return op


def const(value: float) -> dict:
    return {"type": "constant", "value": value}


def price(field: str = "close", shift: int = 0) -> dict:
    return {"type": "price", "field": field, "shift": shift}


def cond(left: dict, op: str, right: dict) -> dict:
    return {"left": left, "op": op, "right": right}


def builder(buy=None, sell=None, **extra) -> dict:
    d = {"schema_version": 1, "category": "trend", **extra}
    if buy is not None:
        d["buy"] = buy
    if sell is not None:
        d["sell"] = sell
    return d


MA_REPLICA = builder(  # ma_crossover with its defaults (EMA 9 / EMA 21)
    buy={"all": [cond(ind("ema", length=9), "crosses_above", ind("ema", length=21))]},
    sell={"all": [cond(ind("ema", length=9), "crosses_below", ind("ema", length=21))]},
)


def rsi_reversal_replica(length: int = 14, low: float = 30, high: float = 70) -> dict:
    """``rsi_reversal`` as rules: prev RSI < low <= RSI now; prev RSI > high >= RSI now."""
    return builder(
        buy={
            "all": [
                cond(ind("rsi", shift=1, length=length), "<", const(low)),
                cond(ind("rsi", length=length), ">=", const(low)),
            ]
        },
        sell={
            "all": [
                cond(ind("rsi", shift=1, length=length), ">", const(high)),
                cond(ind("rsi", length=length), "<=", const(high)),
            ]
        },
        category="mean_reversion",
    )


def rsi_below(level: float = 30, length: int = 14) -> dict:
    return builder(buy={"all": [cond(ind("rsi", length=length), "<", const(level))]})


def composite(*refs: str, mode: str = "any", **extra) -> dict:
    return {
        "schema_version": 1,
        "members": [{"ref": r} for r in refs],
        "mode": mode,
        **extra,
    }


def body(name: str, definition: dict, kind: str = "builder", **extra) -> dict:
    return {"name": name, "kind": kind, "definition": definition, **extra}


async def create(client: AsyncClient, headers, name: str, definition: dict, **extra) -> dict:
    kind = extra.pop("kind", "composite" if "members" in definition else "builder")
    res = await client.post(MINE, json=body(name, definition, kind, **extra), headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


async def make_custom(
    session: AsyncSession,
    user: User,
    name: str,
    definition: dict,
    *,
    visibility: Visibility = Visibility.private,
) -> CustomStrategy:
    """Through the service (validation, hash), without HTTP."""
    kind = CustomStrategyKind.composite if "members" in definition else CustomStrategyKind.builder
    data = CustomStrategyCreate(name=name, kind=kind, definition=definition, visibility=visibility)
    return await custom_strategy_service.create(session, user, data)
