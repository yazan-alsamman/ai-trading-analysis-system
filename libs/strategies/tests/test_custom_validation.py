"""Validation of Builder and Composite definitions: every limit and error path, with the JSON
path in the message; normalisation, snapshots, hashes and the editor schema."""

import copy
import json

import pytest

import trading_strategies as ts
from tests.custom_utils import (
    MA_CROSSOVER_REPLICA,
    UUID_A,
    UUID_B,
    builder,
    cond,
    const,
    ind,
    price,
)
from trading_strategies.builder import MAX_CONDITIONS, builder_errors

CLOSE = price("close")
OK = cond(CLOSE, ">", const(1))


def errors(definition) -> list[tuple[str, str]]:
    checked = ts.validate("builder", definition)
    assert not checked.valid
    return [(e["path"], e["message"]) for e in checked.errors]


def one_error(definition) -> tuple[str, str]:
    found = errors(definition)
    assert len(found) == 1, found
    return found[0]


def with_buy(*nodes, kind: str = "all") -> dict:
    return builder(buy={kind: list(nodes)})


# --- Builder structure ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("definition", "path", "message"),
    [
        ({**with_buy(OK), "extra": 1}, "extra", "Extra inputs are not permitted"),
        ({**with_buy(OK), "schema_version": 2}, "schema_version", "Input should be 1"),
        (
            {k: v for k, v in with_buy(OK).items() if k != "category"},
            "category",
            "Field required",
        ),
        ({**with_buy(OK), "category": "magic"}, "category", "Input should be 'trend'"),
        ({**with_buy(OK), "strength": "max"}, "strength", "Input should be 'fixed'"),
        (builder(), "", "give buy and/or sell rules"),
        (builder(buy=OK), "buy", "must be a group"),
        (builder(buy={"all": []}), "buy.all", "List should have at least 1 item"),
        (builder(buy={"all": [OK], "any": [OK]}), "buy.any", "Extra inputs are not permitted"),
        (with_buy(OK, {"x": 1}), "buy.all[1]", "expected a condition with 'op'"),
        (with_buy(OK, 5), "buy.all[1]", "expected a condition with 'op'"),
        (with_buy(cond(CLOSE, "==", const(1))), "buy.all[0].op", "Input should be '>'"),
        (with_buy({"op": ">", "left": CLOSE}), "buy.all[0].right", "Field required"),
        (
            with_buy({**OK, "value": CLOSE}),
            "buy.all[0].value",
            "Extra inputs are not permitted",
        ),
        (
            with_buy(cond({"type": "formula", "text": "1+1"}, ">", const(1))),
            "buy.all[0].left",
            "an operand needs 'type'",
        ),
        (with_buy(cond({"field": "close"}, ">", const(1))), "buy.all[0].left", "needs 'type'"),
        (
            with_buy(cond(price("vwap"), ">", const(1))),
            "buy.all[0].left.field",
            "Input should be 'open'",
        ),
        (
            with_buy(cond(CLOSE, ">", const(True))),
            "buy.all[0].right.value",
            "must be a number",
        ),
        (
            with_buy(cond(CLOSE, ">", const("30"))),
            "buy.all[0].right.value",
            "must be a number",
        ),
        (
            with_buy(cond(CLOSE, ">", {"type": "constant", "value": float("inf")})),
            "buy.all[0].right.value",
            "finite number",
        ),
        (
            with_buy(cond(price(shift=-1), ">", const(1))),
            "buy.all[0].left.shift",
            "greater than or equal to 0",
        ),
        (
            with_buy(cond(price(shift=101), ">", const(1))),
            "buy.all[0].left.shift",
            "less than or equal to 100",
        ),
        (with_buy(cond(price(shift=1.5), ">", const(1))), "buy.all[0].left.shift", "integer"),
        (
            with_buy({"op": "rising", "value": CLOSE, "bars": 0}),
            "buy.all[0].bars",
            "greater than or equal to 1",
        ),
        (
            with_buy({"op": "falling", "value": CLOSE, "bars": 51}),
            "buy.all[0].bars",
            "less than or equal to 50",
        ),
        (with_buy({"op": "rising", "value": CLOSE}), "buy.all[0].bars", "Field required"),
        (
            with_buy({"op": "between", "value": CLOSE, "lower": const(1)}),
            "buy.all[0].upper",
            "Field required",
        ),
    ],
)
def test_structure_errors(definition, path: str, message: str) -> None:
    got_path, got_message = errors(definition)[0]
    assert got_path == path
    assert message in got_message


def test_not_an_object() -> None:
    assert errors([1, 2])[0][0] == ""
    assert errors(None)[0][0] == ""


# --- Builder registry rules ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("operand", "path", "message"),
    [
        (ind("nope"), "right.name", "unknown indicator 'nope' (available: adx"),
        (ind("rsi", length=0), "right.params.length", "length must be between 1 and 1000"),
        (ind("rsi", length=2.5), "right.params.length", "length must be an integer"),
        (ind("rsi", length="14"), "right.params.length", "length must be a number"),
        (ind("rsi", period=14), "right.params.period", "unknown parameter of rsi"),
        (
            ind("macd", output="macd", fast=30),
            "right.params",
            "macd: fast (30) must be smaller than slow (26)",
        ),
        (ind("macd"), "right.output", "required: macd has several outputs"),
        (ind("bollinger", output="mid"), "right.output", "bollinger has no output 'mid'"),
        (ind("rsi", output="value"), "right.output", "rsi has no output 'value'"),
    ],
)
def test_indicator_errors(operand: dict, path: str, message: str) -> None:
    definition = with_buy(OK, {"any": [OK, cond(CLOSE, ">", operand)]})
    got_path, got_message = one_error(definition)
    assert got_path == f"buy.all[1].any[1].{path}"
    assert message in got_message


def test_all_registry_errors_are_listed() -> None:
    definition = builder(
        buy={"all": [cond(ind("nope"), ">", ind("rsi", length=0))]},
        sell={"any": [cond(ind("macd"), ">", const(1))]},
    )
    assert [p for p, _ in errors(definition)] == [
        "buy.all[0].left.name",
        "buy.all[0].right.params.length",
        "sell.any[0].left.output",
    ]


def test_depth_limit() -> None:
    depth3 = with_buy({"any": [{"all": [OK]}]})
    assert ts.validate("builder", depth3).valid
    depth4 = with_buy({"any": [{"all": [{"any": [OK]}]}]})
    assert one_error(depth4) == (
        "buy.all[0].any[0].all[0]",
        "groups can be nested at most 3 levels deep",
    )


def test_condition_limit() -> None:
    assert ts.validate("builder", with_buy(*[OK] * MAX_CONDITIONS)).valid
    too_many = builder(buy={"all": [OK] * 30}, sell={"any": [OK] * 21})
    assert one_error(too_many) == ("", "at most 50 conditions, got 51")


def test_error_message_joins_paths() -> None:
    with pytest.raises(ts.DefinitionError) as exc:
        ts.BuilderStrategy(with_buy(cond(CLOSE, ">", ind("rsi", length=0))))
    assert str(exc.value) == (
        "buy.all[0].right.params.length: length must be between 1 and 1000, got 0"
    )
    assert exc.value.errors == [
        {
            "path": "buy.all[0].right.params.length",
            "loc": ["buy", "all", 0, "right", "params", "length"],
            "message": "length must be between 1 and 1000, got 0",
        }
    ]
    assert isinstance(exc.value, ValueError)


def test_normalisation() -> None:
    raw = with_buy(cond(ind("rsi"), "<", const(30)))
    raw.pop("strength")
    normalised, errs = builder_errors(raw)
    assert errs == []
    assert normalised == {
        "schema_version": 1,
        "buy": {
            "all": [
                {
                    "left": {
                        "type": "indicator",
                        "name": "rsi",
                        "params": {"length": 14},
                        "output": "rsi",
                        "shift": 0,
                    },
                    "op": "<",
                    "right": {"type": "constant", "value": 30.0, "shift": 0},
                }
            ]
        },
        "sell": None,
        "strength": "fixed",
        "category": "trend",
    }
    assert builder_errors(normalised)[0] == normalised  # idempotent
    json.dumps(normalised)


def test_definitions_are_never_evaluated_as_code() -> None:
    sneaky = with_buy(cond(ind("__import__('os').system('x')"), ">", const(1)))
    assert errors(sneaky)[0][0] == "buy.all[0].left.name"
    sneaky = with_buy(cond(CLOSE, "__class__", const(1)))
    assert errors(sneaky)[0][0] == "buy.all[0].op"


# --- Composite -----------------------------------------------------------------------------------


def composite(*members, mode: str = "any", **extra) -> dict:
    return {"schema_version": 1, "members": list(members), "mode": mode, **extra}


def resolver_for(defs: dict):
    def resolve(ref: str):
        if ref not in defs:
            raise LookupError(ref)
        return defs[ref]

    return resolve


def comp_errors(definition, resolver=None, key=None) -> list[tuple[str, str]]:
    checked = ts.validate("composite", definition, resolver, key=key)
    assert not checked.valid
    return [(e["path"], e["message"]) for e in checked.errors]


RSI = {"ref": "rsi_reversal"}
MACD = {"ref": "macd_cross"}


@pytest.mark.parametrize(
    ("definition", "path", "message"),
    [
        (composite(RSI), "members", "at least 2 items"),
        (composite(*[RSI] * 6), "members", "at most 5 items"),
        (composite(RSI, MACD, mode="vote"), "mode", "Input should be 'all'"),
        (composite(RSI, MACD, window=0), "window", "greater than or equal to 1"),
        (composite(RSI, MACD, window=21), "window", "less than or equal to 20"),
        (composite(RSI, MACD, threshold=0), "threshold", "greater than 0"),
        (composite(RSI, MACD, threshold=1.5), "threshold", "less than or equal to 1"),
        (composite(RSI, {"ref": "nope"}), "members[1].ref", "unknown strategy 'nope'"),
        (composite(RSI, {"ref": "custom:123"}), "members[1].ref", "custom:<uuid>"),
        (composite(RSI, {**MACD, "weight": 0}), "members[1].weight", "greater than 0"),
        (composite(RSI, {**MACD, "extra": 1}), "members[1].extra", "Extra inputs"),
        (
            composite(RSI, {"ref": "macd_cross", "params": {"fast": 40}}),
            "members[1].params",
            "macd_cross: fast (40) must be smaller than slow (26)",
        ),
        (
            composite(RSI, {"ref": UUID_A, "params": {"x": 1}}),
            "members[1].params",
            "custom strategies take no params",
        ),
        (composite(RSI, {"ref": UUID_A}), "members[1].ref", "unknown or inaccessible"),
    ],
)
def test_composite_errors(definition, path: str, message: str) -> None:
    got_path, got_message = comp_errors(definition, resolver_for({}))[0]
    assert got_path == path
    assert message in got_message


def test_composite_without_resolver() -> None:
    assert comp_errors(composite(RSI, {"ref": UUID_A})) == [
        ("members[1].ref", f"cannot resolve {UUID_A} (no resolver)")
    ]


def test_invalid_custom_member_is_reported_on_its_ref() -> None:
    defs = {UUID_A: ("builder", with_buy(cond(ind("rsi", length=0), ">", const(1))))}
    assert comp_errors(composite(RSI, {"ref": UUID_A}), resolver_for(defs)) == [
        (
            "members[1].ref",
            f"{UUID_A} is invalid: buy.all[0].left.params.length: length must be between "
            "1 and 1000, got 0",
        )
    ]


def test_cycles_are_rejected() -> None:
    a = composite(RSI, {"ref": UUID_B})
    defs = {UUID_A: ("composite", a), UUID_B: ("composite", composite(MACD, {"ref": UUID_A}))}
    path, message = comp_errors(a, resolver_for(defs), key=UUID_A)[0]
    assert path == "members[1].ref"
    assert message.endswith(f"cycle: {UUID_A} -> {UUID_B} -> {UUID_A}")
    # a composite that contains itself
    selfish = composite(RSI, {"ref": UUID_A})
    assert comp_errors(selfish, resolver_for({UUID_A: ("composite", selfish)}), key=UUID_A) == [
        ("members[1].ref", f"cycle: {UUID_A} -> {UUID_A}")
    ]
    # without its own key, the cycle is found one level down
    path, message = comp_errors(a, resolver_for(defs))[0]
    assert "cycle:" in message


def test_nesting_limit() -> None:
    from tests.custom_utils import UUID_C, UUID_D

    leaf = ("builder", MA_CROSSOVER_REPLICA)
    defs = {
        UUID_D: leaf,
        UUID_C: ("composite", composite(RSI, {"ref": UUID_D})),  # level 3
        UUID_B: ("composite", composite(RSI, {"ref": UUID_C})),  # level 2
    }
    assert ts.validate("composite", composite(MACD, {"ref": UUID_B}), resolver_for(defs)).valid
    defs[UUID_A] = ("composite", composite(MACD, {"ref": UUID_B}))  # A would be level 2: B 3, C 4
    path, message = comp_errors(composite(RSI, {"ref": UUID_A}), resolver_for(defs))[0]
    assert path == "members[1].ref"
    assert "composites can be nested at most 3 levels deep" in message


def test_unknown_kind() -> None:
    assert ts.validate("python", {}).errors == [
        {"path": "kind", "loc": ["kind"], "message": "must be one of builder, composite"}
    ]


# --- snapshots, hashes, schema --------------------------------------------------------------------


def test_snapshot_and_hash() -> None:
    defs = {UUID_A: ("builder", MA_CROSSOVER_REPLICA)}
    definition = composite(
        {"ref": "rsi_reversal", "params": {"oversold": 25}},
        {"ref": UUID_A.upper().replace("CUSTOM:", "custom:"), "weight": 2},
        mode="weighted",
        window=3,
        threshold=0.6,
    )
    snap = ts.snapshot("composite", definition, resolver_for(defs))
    json.dumps(snap)
    assert snap["definition"]["members"] == [
        {
            "ref": "rsi_reversal",
            "params": {"length": 14, "oversold": 25.0, "overbought": 70.0},
            "weight": 1.0,
        },
        {"ref": UUID_A, "params": {}, "weight": 2.0},
    ]
    assert set(snap["members"]) == {UUID_A}
    rebuilt = ts.from_snapshot(snap, key="custom:x")
    assert rebuilt.key == "custom:x" and rebuilt.history() > 0
    h = ts.snapshot_hash(snap)
    assert len(h) == 32 and h == ts.snapshot_hash(copy.deepcopy(snap))
    # a change in a member's definition changes the composite's hash
    changed = copy.deepcopy(MA_CROSSOVER_REPLICA)
    changed["buy"]["all"][0]["left"]["params"]["length"] = 8
    other = ts.snapshot("composite", definition, resolver_for({UUID_A: ("builder", changed)}))
    assert ts.snapshot_hash(other) != h
    # the same setup written differently hashes the same
    same = copy.deepcopy(definition)
    same["members"][0]["params"] = {"oversold": 25.0, "length": 14}
    assert ts.snapshot_hash(ts.snapshot("composite", same, resolver_for(defs))) == h


def test_validation_reports_history() -> None:
    checked = ts.validate("builder", MA_CROSSOVER_REPLICA)
    assert checked.valid and checked.history == ts.BuilderStrategy(MA_CROSSOVER_REPLICA).history()


def test_editor_schema_and_catalog() -> None:
    schemas = ts.json_schemas()
    json.dumps(schemas)
    assert schemas["builder"]["additionalProperties"] is False
    assert {"Node", "AllGroup"} & set(schemas["builder"]["$defs"]) == {"AllGroup"}
    assert schemas["composite"]["properties"]["members"]["maxItems"] == 5
    catalog = ts.operand_catalog()
    json.dumps(catalog)
    names = {i["name"]: i for i in catalog["builder"]["indicators"]}
    assert names["macd"]["outputs"] == ["macd", "signal", "histogram"]
    assert names["macd"]["output_required"] and not names["rsi"]["output_required"]
    ops = {o["op"]: o for o in catalog["builder"]["ops"]}
    assert ops["between"]["operands"] == ["value", "lower", "upper"]
    assert ops["rising"]["bars"] == {"min": 1, "max": 50}
    assert catalog["limits"]["max_conditions"] == 50 and catalog["limits"]["max_depth"] == 3
    assert [s["key"] for s in catalog["composite"]["strategies"]] == list(ts.STRATEGIES)
