"""Generate the database documentation (T05) from the SQLAlchemy metadata.

    python scripts/erd.py            # write docs/erd/erd.md, docs/erd/tables.md, docs/erd/mmd/*.mmd
    python scripts/erd.py --check    # exit 1 if the committed files are out of date (CI)

``erd.md`` has one Mermaid ``erDiagram`` per domain (columns, keys, relations) and an overview
(tables and relations only); ``tables.md`` lists every table with columns, constraints,
indexes and its purpose (the model's docstring). The ``mmd/`` files are the same diagrams for
``mermaid-cli`` (``scripts/erd_images.sh`` renders them to ``docs/erd/img/``). TimescaleDB
objects that are not plain tables (hypertable, compression, continuous aggregates) are
described from migration 0003, so they cannot drift either.
"""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import sys
from pathlib import Path

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Double,
    Enum,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
OUT = ROOT / "docs" / "erd"
sys.path.insert(0, str(BACKEND))

import app.models  # noqa: E402,F401 - registers every model
from app.db.base import Base  # noqa: E402

DOMAINS: list[tuple[str, str, list[str]]] = [
    (
        "auth",
        "Auth, sessions and API keys",
        ["users", "refresh_tokens", "api_keys", "login_fingerprints"],
    ),
    (
        "market",
        "Market data, signals and price alerts",
        [
            "instruments",
            "candles_1m",
            "signals",
            "price_alerts",
            "economic_events",
            "feed_credentials",
        ],
    ),
    (
        "strategies",
        "Strategies, backtests and risk",
        [
            "user_strategies",
            "custom_strategies",
            "backtests",
            "backtest_trades",
            "risk_profiles",
            "signal_plans",
        ],
    ),
    (
        "ai",
        "AI engine (ai-service setups and models)",
        [
            "ai_setups",
            "ai_setup_events",
            "ai_model_versions",
            "ai_setup_sizes",
            "ai_setup_takes",
            "ai_setup_explanations",
            "ai_setup_outbox",
            "ai_alert_follows",
            "ai_evaluation_runs",
        ],
    ),
    ("workspaces", "Workspaces", ["workspaces"]),
    (
        "notifications",
        "Notifications",
        [
            "notifications",
            "notification_deliveries",
            "notification_preferences",
            "telegram_links",
            "user_devices",
        ],
    ),
    (
        "social",
        "News and social",
        [
            "news_sources",
            "news_articles",
            "news_article_instruments",
            "posts",
            "comments",
            "post_likes",
            "follows",
            "content_reports",
        ],
    ),
    (
        "subscriptions",
        "Subscriptions and chat",
        [
            "expert_profiles",
            "subscription_plans",
            "subscriptions",
            "invoices",
            "checkout_sessions",
            "payment_events",
            "conversations",
            "messages",
        ],
    ),
]


# --- types -----------------------------------------------------------------------------------


def short_type(col: Column) -> str:
    """One word for Mermaid (no spaces or brackets)."""
    t = col.type
    if isinstance(t, Enum):
        return f"enum_{t.name}" if t.native_enum else "string"
    for cls, name in (
        (Uuid, "uuid"),
        (JSONB, "jsonb"),
        (ARRAY, "array"),
        (Boolean, "bool"),
        (BigInteger, "bigint"),
        (Integer, "int"),
        (Double, "double"),
        (Numeric, "numeric"),
        (DateTime, "timestamptz"),
        (Text, "text"),
        (String, "varchar"),
    ):
        if isinstance(t, cls):
            return name
    return type(t).__name__.lower()


def full_type(col: Column) -> str:
    t = col.type
    if isinstance(t, Enum):
        if t.native_enum:
            return f"enum {t.name} ({', '.join(t.enums)})"
        return f"varchar({t.length}) ({', '.join(t.enums)})"
    try:
        return t.compile(dialect=postgresql.dialect()).lower()
    except Exception:  # noqa: BLE001
        return str(t).lower()


def server_default(col: Column) -> str:
    d = col.server_default
    if d is None:
        return ""
    arg = getattr(d, "arg", d)
    text = getattr(arg, "text", None) or str(arg)
    return text.replace("|", "\\|")


# --- relations -------------------------------------------------------------------------------


def foreign_keys(table: Table) -> list[ForeignKeyConstraint]:
    return sorted(
        (c for c in table.constraints if isinstance(c, ForeignKeyConstraint)),
        key=lambda c: [col.name for col in c.columns],
    )


def unique_sets(table: Table) -> list[set[str]]:
    sets = [{c.name for c in table.primary_key.columns}]
    sets += [
        {c.name for c in u.columns} for u in table.constraints if isinstance(u, UniqueConstraint)
    ]
    # unique indexes count only when they are plain column lists: (user_id, lower(name)) or a
    # partial index (WHERE is_default) does not make user_id unique
    sets += [
        {c.name for c in i.columns}
        for i in table.indexes
        if i.unique
        and i.columns
        and len(i.expressions) == len(i.columns)
        and i.dialect_options["postgresql"].get("where") is None
    ]
    sets += [{c.name} for c in table.columns if c.unique]
    return sets


def relation_line(table: Table, fk: ForeignKeyConstraint) -> str:
    cols = [c.name for c in fk.columns]
    parent = fk.referred_table.name
    one_to_one = set(cols) in unique_sets(table)
    optional = any(c.nullable for c in fk.columns)
    child_side = "|o" if one_to_one else "}o"
    parent_side = "o|" if optional else "||"
    return f'    {table.name} {child_side}--{parent_side} {parent} : "{", ".join(cols)}"'


def key_marks(table: Table, col: Column) -> str:
    marks = []
    if col.primary_key:
        marks.append("PK")
    if col.foreign_keys:
        marks.append("FK")
    if not col.primary_key and {col.name} in unique_sets(table):
        marks.append("UK")
    return ", ".join(marks)


# --- Mermaid ---------------------------------------------------------------------------------


def entity(table: Table) -> list[str]:
    lines = [f"    {table.name} {{"]
    for col in table.columns:
        marks = key_marks(table, col)
        lines.append(f"        {short_type(col)} {col.name}{' ' + marks if marks else ''}")
    lines.append("    }")
    return lines


def domain_diagram(tables: list[Table]) -> str:
    names = {t.name for t in tables}
    lines = ["erDiagram"]
    for t in tables:
        lines += entity(t)
    relations = []
    for t in tables:
        for fk in foreign_keys(t):
            relations.append(relation_line(t, fk))
            parent = fk.referred_table.name
            if parent not in names:
                names.add(parent)
                lines.append(f"    {parent}")  # another domain's table, without columns
    return "\n".join(lines + sorted(set(relations))) + "\n"


def overview_diagram(tables: list[Table]) -> str:
    """Tables and relations, no columns, grouped by domain (a flowchart with one box per
    domain: an erDiagram of 36 tables cannot be laid out on one page). Arrows go from the
    referencing table to the referenced one; links to ``users`` are dotted."""
    lines = ["flowchart LR"]
    by_name = {t.name: t for t in tables}
    for key, title, names in DOMAINS:
        lines.append(f'    subgraph domain_{key}["{title}"]')
        lines.append("        direction TB")
        lines += [f"        {n}[{n}]" for n in names if n in by_name]
        lines.append("    end")
    edges = set()
    for t in tables:
        for fk in foreign_keys(t):
            parent = fk.referred_table.name
            if parent == t.name:
                continue  # self references (replies, clones) are in the domain diagrams
            arrow = "-.->" if parent == "users" else "-->"
            edges.add(f"    {t.name} {arrow} {parent}")
    return "\n".join(lines + sorted(edges)) + "\n"


def user_owned(tables: list[Table]) -> list[str]:
    return sorted(
        {
            f"`{t.name}` ({', '.join(c.name for c in fk.columns)})"
            for t in tables
            for fk in foreign_keys(t)
            if fk.referred_table.name == "users"
        }
    )


# --- Markdown --------------------------------------------------------------------------------


def purpose(table: Table) -> str:
    for mapper in Base.registry.mappers:
        if mapper.local_table is table:
            doc = inspect.getdoc(mapper.class_) or ""
            return " ".join(doc.split("\n\n")[0].split())
    return ""


def table_section(table: Table) -> str:
    out = [f"### `{table.name}`", "", purpose(table), ""]
    out += ["| Column | Type | Null | Default | Keys |", "|---|---|---|---|---|"]
    for col in table.columns:
        out.append(
            f"| `{col.name}` | {full_type(col)} | {'yes' if col.nullable else 'no'} "
            f"| {('`' + server_default(col) + '`') if server_default(col) else ''} "
            f"| {key_marks(table, col)} |"
        )
    cons = []
    pk = table.primary_key
    cons.append(f"- PK `{pk.name or 'pk'}` ({', '.join(c.name for c in pk.columns)})")
    for fk in foreign_keys(table):
        target = f"{fk.referred_table.name} ({', '.join(e.column.name for e in fk.elements)})"
        on_delete = f" ON DELETE {fk.ondelete}" if fk.ondelete else ""
        cols = ", ".join(c.name for c in fk.columns)
        cons.append(f"- FK ({cols}) → {target}{on_delete}")
    for c in sorted(table.constraints, key=lambda c: str(c.name)):
        if isinstance(c, UniqueConstraint):
            cons.append(f"- UNIQUE `{c.name}` ({', '.join(col.name for col in c.columns)})")
        elif isinstance(c, CheckConstraint):
            cons.append(f"- CHECK `{c.name}`: `{str(c.sqltext).replace('|', '\\|')}`")
    for col in table.columns:
        if col.unique:
            cons.append(f"- UNIQUE ({col.name})")
    out += ["", "**Constraints**", "", *cons]
    idx = []
    for i in sorted(table.indexes, key=lambda i: str(i.name)):
        exprs = [str(e) for e in i.expressions] if i.expressions else [c.name for c in i.columns]
        where = i.dialect_options["postgresql"].get("where")
        using = i.dialect_options["postgresql"].get("using")
        line = f"- `{i.name}`{' UNIQUE' if i.unique else ''}"
        line += f" ({', '.join(exprs)})".replace("|", "\\|")
        if using:
            line += f" USING {using}"
        if where is not None:
            line += f" WHERE `{str(where)}`"
        idx.append(line)
    if idx:
        out += ["", "**Indexes**", "", *idx]
    return "\n".join(out) + "\n"


def timescale_notes() -> str:
    spec = importlib.util.spec_from_file_location(
        "m0003", BACKEND / "alembic" / "versions" / "0003_market_data.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = [
        f"| `{view}` | `{source}` | {bucket} | {start} | {end} | {schedule} |"
        for view, source, bucket, start, end, schedule in module.AGGREGATES
    ]
    return "\n".join(
        [
            "## TimescaleDB objects",
            "",
            "These are not plain tables, so the diagrams above show only `candles_1m` itself:",
            "",
            "- **`candles_1m` is a hypertable** partitioned by `ts` in 7-day chunks "
            "(`create_hypertable(..., by_range('ts', INTERVAL '7 days'))`, without Timescale's "
            "default `ts` index: the primary key `(instrument_id, ts)` serves every query).",
            "- **Compression**: chunks older than 30 days are compressed "
            "(`compress_segmentby = 'instrument_id'`, `compress_orderby = 'ts DESC'`).",
            "- **No retention policy**: candles are kept (only news and notifications have "
            "retention, done by Celery tasks).",
            "- **Continuous aggregates** (real-time: `materialized_only = false`, so the newest "
            "bucket is computed from the raw rows on read). Each has an index on "
            "`(instrument_id, ts DESC)` and a refresh policy:",
            "",
            "| View | From | Bucket | Refresh start offset | End offset | Every |",
            "|---|---|---|---|---|---|",
            *rows,
            "",
            "Higher timeframes are read from these views (`Timeframe.relation`); late "
            "backfills older than the refresh window trigger an explicit refresh "
            "(`market_service.refresh_aggregates`).",
            "",
        ]
    )


def build() -> dict[Path, str]:
    tables = Base.metadata.tables
    covered = {name for _, _, names in DOMAINS for name in names}
    missing = sorted(set(tables) - covered)
    if missing:
        raise SystemExit(f"tables without a domain in scripts/erd.py: {missing}")
    files: dict[Path, str] = {}
    sections = [
        "# Database (ERD)",
        "",
        "<!-- Generated by backend/scripts/erd.py from the SQLAlchemy models; do not edit. -->",
        "",
        f"{len(tables)} tables in {len(DOMAINS)} domains (PostgreSQL 16 + TimescaleDB 2.17). "
        "Column-level details: [tables.md](tables.md). Images: [img/](img/).",
        "",
        "Relations: `}o--||` many-to-one, `}o--o|` many-to-optional-one (nullable FK), "
        "`|o--||` one-to-one. Tables of another domain appear without columns.",
        "",
    ]
    ordered = [tables[n] for _, _, names in DOMAINS for n in names]
    overview = overview_diagram(ordered)
    files[OUT / "mmd" / "overview.mmd"] = overview
    sections += [
        "## Overview (tables and relations)",
        "",
        "```mermaid",
        overview,
        "```",
        "",
        "Boxes are the domains below; solid arrows point from a table to the table it "
        "references, dotted arrows to `users`. Foreign keys to `users`: "
        + ", ".join(user_owned(ordered))
        + ".",
        "",
    ]
    for key, title, names in DOMAINS:
        diagram = domain_diagram([tables[n] for n in names])
        files[OUT / "mmd" / f"{key}.mmd"] = diagram
        sections += [f"## {title}", "", "```mermaid", diagram, "```", ""]
    sections.append(timescale_notes())
    files[OUT / "erd.md"] = "\n".join(sections)
    detail = [
        "# Tables",
        "",
        "<!-- Generated by backend/scripts/erd.py from the SQLAlchemy models; do not edit. -->",
        "",
    ]
    for _, title, names in DOMAINS:
        detail += [f"## {title}", ""]
        detail += [table_section(tables[n]) for n in names]
    files[OUT / "tables.md"] = "\n".join(detail)
    return files


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if the files are stale")
    args = parser.parse_args()
    files = build()
    stale = []
    for path, content in files.items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != content:
            stale.append(path)
            if not args.check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8", newline="\n")
    if args.check:
        if stale:
            for path in stale:
                print(f"out of date: {path.relative_to(ROOT)}")
            print("run: python backend/scripts/erd.py")
            return 1
        print(f"ERD docs up to date ({len(files)} files)")
        return 0
    print(f"wrote {len(stale)} of {len(files)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
