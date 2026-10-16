# ruff: noqa: E501  (embedded JavaScript, Markdown and sample payloads)
"""Single source of truth for the Postman collection.

Every endpoint of the API is one ``Req`` below, grouped in ``Folder``s in the order a
Collection Runner (and ``capture_examples.py``) executes them: each folder creates what it
needs, uses it and cleans up after itself.

* ``path`` uses Postman path variables (``:workspace_id``); their values default to the
  variable of the same name (``{{workspace_id}}``).
* ``captures`` store response values in the environment (``{"var": "items.0.id"}``).
* ``variants`` are extra saved examples (errors, alternative bodies) captured right after the
  main request; they never become requests of their own.

Run ``python docs/postman/tools/build_collection.py --check`` after adding an endpoint: it
fails if a route of the FastAPI app has no ``Req`` here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Variant:
    name: str
    status: int
    body: Any = None  # replaces the request body (None = keep)
    query: dict[str, str] | None = None  # overrides query values
    path_vars: dict[str, str] | None = None
    headers: dict[str, str] | None = None
    auth: str | None = None  # override auth mode
    path: str | None = None  # another path of the API (e.g. to show a missing scope)


@dataclass
class Req:
    id: str
    name: str
    method: str
    path: str  # relative to {{api_url}} unless it starts with "/ws" or "{{"
    description: str
    auth: str = "user"  # user | admin | none | apikey
    query: list[tuple[str, str, str]] = field(default_factory=list)  # key, value, description
    optional_query: list[tuple[str, str, str]] = field(default_factory=list)  # disabled
    path_vars: dict[str, tuple[str, str]] = field(default_factory=dict)  # name -> value, desc
    headers: list[tuple[str, str, str]] = field(default_factory=list)
    body: Any = None
    form: list[tuple[str, str, str]] | None = None  # x-www-form-urlencoded
    expect: list[int] = field(default_factory=lambda: [200])
    captures: dict[str, str] = field(default_factory=dict)
    pre: str = ""  # extra pre-request JS
    tests: str = ""  # extra test JS
    variants: list[Variant] = field(default_factory=list)
    cost: int = 1  # rate-limit cost, shown in the description


@dataclass
class Folder:
    name: str
    description: str
    items: list[Req | Folder]
    auth: str | None = None  # admin folders: bearer {{admin_access_token}}


# --- reusable bodies --------------------------------------------------------------------------

RSI_BOLLINGER = {
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
}

EMA_CROSS = {
    "schema_version": 1,
    "category": "trend",
    "buy": {
        "all": [
            {
                "left": {"type": "indicator", "name": "ema", "params": {"length": 9}},
                "op": "crosses_above",
                "right": {"type": "indicator", "name": "ema", "params": {"length": 21}},
            }
        ]
    },
    "sell": {
        "all": [
            {
                "left": {"type": "indicator", "name": "ema", "params": {"length": 9}},
                "op": "crosses_below",
                "right": {"type": "indicator", "name": "ema", "params": {"length": 21}},
            }
        ]
    },
}

COMPOSITE = {
    "schema_version": 1,
    "members": [
        {"ref": "rsi_reversal", "params": {"oversold": 25}, "weight": 1.0},
        {"ref": "bollinger_reversion", "weight": 1.0},
        {"ref": "macd_cross", "weight": 2.0},
    ],
    "mode": "weighted",
    "window": 3,
    "threshold": 0.5,
}

WORKSPACE_STATE = {
    "layout": {"type": "1x2", "sizes": [0.6, 0.4]},
    "sync": {"crosshair": True, "timeframe": False, "instrument": False},
    "panels": [
        {
            "id": "p1",
            "instrument_id": "{{instrument_id}}",
            "timeframe": "1h",
            "chart_type": "candles",
            "indicators": [
                {"id": "i1", "name": "ema", "params": {"length": 21}, "color": "#FF9800"},
                {"id": "i2", "name": "rsi", "params": {"length": 14}},
            ],
            "strategies": [{"id": "s1", "strategy_key": "ma_crossover", "params": {}}],
            "drawings": [
                {
                    "id": "d1",
                    "type": "horizontal",
                    "points": [{"time": 1760000000, "price": 60000}],
                    "style": {"color": "#4CAF50", "width": 2},
                }
            ],
        },
        {"id": "p2", "instrument_id": "{{instrument_id}}", "timeframe": "1d"},
    ],
    "watchlist": ["{{instrument_id}}"],
    "active_panel": "p1",
}

PAGE_QUERY = [
    ("limit", "20", "Page size"),
    ("offset", "0", "Items to skip"),
]

# --- JS snippets ------------------------------------------------------------------------------

BACKTEST_DATES = """// Last 14 days up to one hour ago: inside the data of a freshly seeded environment.
const end = new Date(Date.now() - 3600 * 1000);
const start = new Date(end.getTime() - 14 * 24 * 3600 * 1000);
pm.variables.set("backtest_start", start.toISOString().slice(0, 19) + "Z");
pm.variables.set("backtest_end", end.toISOString().slice(0, 19) + "Z");"""

POLL_BACKTEST = """// Collection Runner: poll until the worker has finished (max ~20 tries).
if (json && ["queued", "running"].includes(json.status)) {
    const tries = Number(pm.collectionVariables.get("backtest_poll") || 0);
    if (tries < 20) {
        pm.collectionVariables.set("backtest_poll", String(tries + 1));
        setTimeout(() => {}, 1500);
        pm.execution.setNextRequest(pm.info.requestId);
    }
} else {
    pm.collectionVariables.unset("backtest_poll");
}"""

WAIT_SECOND_BACKTEST = """// Compare needs completed backtests: wait (max ~30 s) until the second one has finished.
const poll = (attempt) => pm.sendRequest({
    url: pm.variables.replaceIn("{{api_url}}/backtests/{{backtest_id_2}}"),
    header: { Authorization: `Bearer ${pm.variables.get("access_token")}` },
}, (err, res) => {
    const status = !err && res.code === 200 ? res.json().status : null;
    if (["queued", "running"].includes(status) && attempt < 30) {
        setTimeout(() => poll(attempt + 1), 1000);
    }
});
if (pm.variables.get("backtest_id_2")) poll(0);"""

CANDLES_NOW = """// Three 1m candles ending at the current minute (UTC, aligned to the minute).
const minute = Math.floor(Date.now() / 60000) * 60000;
[2, 1, 0].forEach((back, i) => pm.variables.set(`candle_ts_${i}`,
    new Date(minute - back * 60000).toISOString().replace(".000", "")));"""

REGISTER_PRE = """// A unique e-mail per send, so the request can be repeated.
pm.variables.set("register_email", `qa.${Date.now()}@example.com`);"""

REGISTER_TESTS = """// Use the new account for the rest of the collection when no user is configured yet.
if (pm.response.code === 201 && !pm.environment.get("user_email")) {
    store.set("user_email", json.email);
    store.set("user_password", pm.variables.get("register_password"));
}"""

LOGIN_TESTS = """if (pm.response.code === 200) saveTokens("", json);"""

LOGOUT_TESTS = """// The refresh token is revoked: forget it (the access token stays valid until it expires).
if (pm.response.code === 204) store.unset("refresh_token");"""

PASSWORD_TESTS = """// Swap the passwords so the next run changes it back.
if (pm.response.code === 204) {
    const old = pm.variables.get("user_password");
    store.set("user_password", pm.variables.get("user_new_password"));
    store.set("user_new_password", old);
}"""

WORKSPACE_CLEANUP = """// Also remove the copies made by Duplicate / Import, so the runner stays under the limit.
["workspace_copy_id", "workspace_import_id"].forEach((name) => {
    const id = pm.variables.get(name);
    if (!id) return;
    pm.sendRequest({
        url: pm.variables.replaceIn(`{{api_url}}/me/workspaces/${id}`),
        method: "DELETE",
        header: { Authorization: `Bearer ${pm.variables.get("access_token")}` },
    }, () => store.unset(name));
});"""

CUSTOM_CLEANUP = """// Also remove the clones, so the runner stays under the per-role limit.
["custom_strategy_clone_id", "public_clone_id", "composite_strategy_id"].forEach((name) => {
    const id = pm.variables.get(name);
    if (!id) return;
    pm.sendRequest({
        url: pm.variables.replaceIn(`{{api_url}}/me/custom-strategies/${id}`),
        method: "DELETE",
        header: { Authorization: `Bearer ${pm.variables.get("access_token")}` },
    }, () => store.unset(name));
});"""

BACKTEST_CLEANUP = """const second = pm.variables.get("backtest_id_2");
if (second) {
    pm.sendRequest({
        url: pm.variables.replaceIn(`{{api_url}}/backtests/${second}`),
        method: "DELETE",
        header: { Authorization: `Bearer ${pm.variables.get("access_token")}` },
    }, () => store.unset("backtest_id_2"));
}"""

WORKSPACE_IDS = """if (pm.response.code === 200) store.set("workspace_ids", JSON.stringify(json.map((w) => w.id)));"""

WORKSPACE_REORDER_PRE = """// Current order reversed: the body must list exactly all of your workspace ids.
const ids = JSON.parse(pm.variables.get("workspace_ids") || "[]");
pm.variables.set("workspace_ids_reversed", JSON.stringify(ids.reverse()));"""

SHARE_TESTS = """// Traders cannot share: skip the two shared-link requests in the Collection Runner.
if (pm.response.code === 403) pm.execution.setNextRequest("Stop sharing");"""

ETAG_TESTS = """const etag = pm.response.headers.get("ETag");
pm.test("ETag carries the version", () => pm.expect(etag).to.eql(`"${json.version}"`));"""

# --- the collection ---------------------------------------------------------------------------

FOLDERS: list[Folder] = [
    Folder(
        "Health",
        "Liveness and readiness probes. **Not authenticated and not rate limited**; used by the "
        "deploy workflow and Docker health checks.",
        [
            Req(
                "health",
                "Liveness",
                "GET",
                "/health",
                'Returns `200 {"status": "ok"}` while the API process is up. Does not touch '
                "the database or Redis.",
                auth="none",
            ),
            Req(
                "health_ready",
                "Readiness (DB + Redis)",
                "GET",
                "/health/ready",
                "Checks PostgreSQL/TimescaleDB and Redis. `status` is `ok` or `degraded`; the "
                "per-dependency result is in `checks`. Always answers 200 so dashboards can read "
                "the body.",
                auth="none",
            ),
        ],
    ),
    Folder(
        "Auth",
        "Registration and JWT sessions.\n\n"
        "* **Access token**: short lived (`expires_in` seconds, 30 min by default), sent as "
        "`Authorization: Bearer <token>`.\n"
        "* **Refresh token**: 14 days, **rotated** on every refresh (the old one stops working).\n"
        "* API keys are always refused here (403).\n\n"
        "**Per-IP limits** on top of the normal rate limit: login 10/min (and 5/min per e-mail), "
        "register 5/min, refresh 30/min. 10 failed logins for one e-mail within 15 min lock that "
        "e-mail for 15 min.\n\n"
        "> You rarely need to call Login yourself: the collection's pre-request script logs in "
        "with `user_email` / `user_password` and refreshes the token automatically.",
        [
            Req(
                "auth_register",
                "Register",
                "POST",
                "/auth/register",
                "Self-registration always creates a **trader** (a `role` field is ignored). "
                "Password: 8–128 characters with at least one letter and one digit. The e-mail is "
                "stored lowercase.\n\nThe pre-request script generates a unique "
                "`register_email`; if no `user_email` is configured yet, the new account becomes "
                "the collection's user.",
                auth="none",
                body={
                    "email": "{{register_email}}",
                    "password": "{{register_password}}",
                    "full_name": "Postman QA",
                },
                expect=[201],
                pre=REGISTER_PRE,
                tests=REGISTER_TESTS,
                variants=[
                    Variant(
                        "409 Email already registered",
                        409,
                        body={"email": "{{user_email}}", "password": "Secret123", "full_name": "x"},
                    ),
                    Variant(
                        "422 Weak password",
                        422,
                        body={"email": "weak@example.com", "password": "short"},
                    ),
                ],
            ),
            Req(
                "auth_login",
                "Login",
                "POST",
                "/auth/login",
                "Exchanges e-mail + password for a token pair and stores both tokens in the "
                "environment (`access_token`, `refresh_token`, `access_token_expires_at`).",
                auth="none",
                body={"email": "{{user_email}}", "password": "{{user_password}}"},
                tests=LOGIN_TESTS,
                variants=[
                    Variant(
                        "401 Wrong password",
                        401,
                        body={"email": "{{user_email}}", "password": "WrongPassword1"},
                    ),
                ],
            ),
            Req(
                "auth_token",
                "Login (OAuth2 form)",
                "POST",
                "/auth/token",
                "The same login as an OAuth2 password form (`username` = e-mail). It exists for "
                "the **Authorize** button of Swagger UI (`/docs`); apps use `/auth/login`.",
                auth="none",
                form=[
                    ("username", "{{user_email}}", "The account e-mail"),
                    ("password", "{{user_password}}", ""),
                ],
            ),
            Req(
                "auth_refresh",
                "Refresh tokens",
                "POST",
                "/auth/refresh",
                "Rotates the refresh token: the response holds a **new** pair and the old "
                "refresh token is revoked. Reusing a revoked refresh token answers 401.",
                auth="none",
                body={"refresh_token": "{{refresh_token}}"},
                tests=LOGIN_TESTS,
                variants=[
                    Variant("401 Invalid refresh token", 401, body={"refresh_token": "not-a-jwt"})
                ],
            ),
            Req(
                "auth_logout",
                "Logout",
                "POST",
                "/auth/logout",
                "Revokes the given refresh token of the current user. The access token keeps "
                "working until it expires, so clients should simply drop it.",
                body={"refresh_token": "{{refresh_token}}"},
                expect=[204],
                tests=LOGOUT_TESTS,
            ),
        ],
    ),
    Folder(
        "Users (me)",
        "The logged-in user's own profile. JWT only: API keys get 403.",
        [
            Req(
                "users_me",
                "Get my profile",
                "GET",
                "/users/me",
                "The current user, including `role` (`trader`, `analyst`, `expert`, `admin`).",
                captures={"user_id": "id"},
                variants=[Variant("401 Not authenticated", 401, auth="none")],
            ),
            Req(
                "users_me_update",
                "Update my profile",
                "PATCH",
                "/users/me",
                "Only `full_name` (1–200 characters, or `null` to clear it) can be changed here; "
                "role and status are admin operations.",
                body={"full_name": "Yazan Alsamman"},
            ),
            Req(
                "users_me_password",
                "Change my password",
                "POST",
                "/users/me/password",
                "Needs the current password. The test script swaps `user_password` and "
                "`user_new_password`, so running it twice restores the original password.",
                body={
                    "current_password": "{{user_password}}",
                    "new_password": "{{user_new_password}}",
                },
                expect=[204],
                tests=PASSWORD_TESTS,
                variants=[
                    Variant(
                        "400 Current password is incorrect",
                        400,
                        body={"current_password": "Nope12345", "new_password": "Another123"},
                    )
                ],
            ),
        ],
    ),
    Folder(
        "Market Data",
        "Instruments and OHLCV candles from TimescaleDB (1m hypertable + continuous aggregates "
        "for 5m, 15m, 1h, 4h, 1d).\n\n"
        "* JWT, or an API key with the `market:read` scope.\n"
        "* Candle `time` is the bucket start in **unix seconds (UTC)**: the format Lightweight "
        "Charts expects (`series.setData(candles)`).\n"
        "* Naive datetimes in queries are taken as UTC.",
        [
            Req(
                "market_instruments",
                "List instruments",
                "GET",
                "/market/instruments",
                "Paginated (`Page`: `items`, `total`, `limit`, `offset`). The first match is "
                "stored as `instrument_id` for every chart request that follows.",
                query=[
                    ("limit", "50", "1–100"),
                    ("offset", "0", ""),
                    ("q", "BTC", "Symbol contains"),
                ],
                optional_query=[
                    ("market", "crypto", "crypto | forex | stock | index | commodity"),
                    ("source", "binance", "Data source"),
                    ("is_active", "true", ""),
                ],
                captures={"instrument_id": "items.0.id"},
            ),
            Req(
                "market_instrument",
                "Get instrument",
                "GET",
                "/market/instruments/:instrument_id",
                "One instrument by id.",
                path_vars={"instrument_id": ("{{instrument_id}}", "Instrument UUID")},
                variants=[
                    Variant(
                        "404 Instrument not found",
                        404,
                        path_vars={"instrument_id": "00000000-0000-0000-0000-000000000000"},
                    )
                ],
            ),
            Req(
                "market_candles",
                "Get candles",
                "GET",
                "/market/instruments/:instrument_id/candles",
                "Candles ascending by time. With `start`: the first `limit` candles from "
                "`start`; otherwise the latest `limit` candles (up to `end` if given). "
                "`limit` max 5,000.",
                query=[
                    ("timeframe", "{{timeframe}}", "1m | 5m | 15m | 1h | 4h | 1d"),
                    ("limit", "200", "1–5000"),
                ],
                optional_query=[
                    ("start", "2026-10-01T00:00:00Z", "ISO 8601, inclusive"),
                    ("end", "2026-10-15T00:00:00Z", "ISO 8601, inclusive"),
                ],
                path_vars={"instrument_id": ("{{instrument_id}}", "Instrument UUID")},
                variants=[Variant("422 Invalid timeframe", 422, query={"timeframe": "2h"})],
            ),
        ],
    ),
    Folder(
        "Indicators",
        "The shared technical-indicator library (`libs/indicators`): the same code runs in the "
        "API, the backtester and the live signal engine.\n\n"
        "JWT, or an API key with `indicators:read`. Computing costs **5** rate-limit units.",
        [
            Req(
                "indicators_catalog",
                "Indicator catalog",
                "GET",
                "/indicators",
                "Every indicator with its params (type, default, min, max), outputs, placement "
                "(`overlay` on the price chart or a separate `pane`), reference levels and warm-up "
                "(`lookback`). Editors are generated from this.",
            ),
            Req(
                "indicators_compute",
                "Compute indicators",
                "POST",
                "/market/instruments/:instrument_id/indicators",
                "Up to 10 indicators over the same window `GET …/candles` returns for these "
                "parameters. Warm-up history is loaded automatically, so a value is `null` only "
                "when not enough history exists. Points are `{time, value}` (Lightweight Charts "
                "line data).",
                path_vars={"instrument_id": ("{{instrument_id}}", "Instrument UUID")},
                body={
                    "timeframe": "{{timeframe}}",
                    "limit": 200,
                    "indicators": [
                        {"name": "rsi", "params": {"length": 14}},
                        {"name": "ema", "params": {"length": 21}},
                        {"name": "bollinger", "params": {"length": 20, "std": 2}},
                    ],
                },
                cost=5,
                variants=[
                    Variant(
                        "422 Unknown indicator",
                        422,
                        body={"timeframe": "1h", "indicators": [{"name": "nope"}]},
                    )
                ],
            ),
        ],
    ),
    Folder(
        "Strategies & Signals",
        "Global strategies (`libs/strategies`), per-user activations that the live signal "
        "engine runs on every closed bar, and the signals it produced.\n\n"
        "* Catalog and preview: JWT or API key `strategies:read`; signals: `signals:read`.\n"
        "* `/me/strategies`: JWT only.\n"
        "* A custom strategy works everywhere with the key `custom:<uuid>`.",
        [
            Req(
                "strategies_catalog",
                "Strategy catalog",
                "GET",
                "/strategies",
                "The global strategies: description, params (type, default, min, max), the "
                "indicator lines to draw with each one and the history (bars) it needs before its "
                "first signal.",
            ),
            Req(
                "strategies_preview",
                "Preview strategy on chart",
                "POST",
                "/strategies/:key/preview",
                "Runs a strategy over the same candle window `GET …/candles` returns. Response: "
                "`signals` (time, side, strength, price, reason, details), Lightweight Charts "
                "`markers` and the strategy's `indicators` lines.\n\n`key` is a global key "
                "(`ma_crossover`, `rsi_reversal`, `macd_cross`, `bollinger_reversion`, "
                "`supertrend_flip`, `donchian_breakout`) or `custom:<uuid>`.",
                path_vars={"key": ("{{strategy_key}}", "Global key or custom:<uuid>")},
                body={
                    "instrument_id": "{{instrument_id}}",
                    "timeframe": "{{timeframe}}",
                    "params": {"fast": 9, "slow": 21},
                    "limit": 300,
                },
                cost=5,
                variants=[
                    Variant(
                        "422 Unknown strategy",
                        422,
                        path_vars={"key": "does_not_exist"},
                    ),
                    Variant(
                        "422 Invalid params",
                        422,
                        body={
                            "instrument_id": "{{instrument_id}}",
                            "timeframe": "1h",
                            "params": {"fast": 50, "slow": 10},
                        },
                    ),
                ],
            ),
            Req(
                "me_strategies_create",
                "Activate strategy",
                "POST",
                "/me/strategies",
                "Runs a strategy live on one instrument + timeframe for the current user. With "
                "`notify: true` each new signal is pushed to the user's WebSocket topic.",
                body={
                    "strategy_key": "{{strategy_key}}",
                    "instrument_id": "{{instrument_id}}",
                    "timeframe": "{{timeframe}}",
                    "params": {"fast": 9, "slow": 21},
                    "name": "BTC 1h EMA cross",
                    "is_active": True,
                    "notify": True,
                },
                expect=[201],
                captures={"user_strategy_id": "id"},
            ),
            Req(
                "me_strategies_list",
                "List my strategies",
                "GET",
                "/me/strategies",
                "All activations of the current user (not paginated).",
            ),
            Req(
                "me_strategies_update",
                "Update activation",
                "PATCH",
                "/me/strategies/:user_strategy_id",
                "Change `name`, `params`, `is_active` or `notify`. Only the fields sent change.",
                path_vars={"user_strategy_id": ("{{user_strategy_id}}", "Activation UUID")},
                body={"params": {"fast": 12, "slow": 26}, "notify": False},
            ),
            Req(
                "signals_list",
                "List signals",
                "GET",
                "/signals",
                "Signals, newest bar first. `mine=true`: only signals of my active strategies. "
                "`time` is `bar_time` in unix seconds; a signal is actionable at the open of the "
                "next bar.",
                query=[("limit", "20", "1–100"), ("offset", "0", "")],
                optional_query=[
                    ("instrument_id", "{{instrument_id}}", ""),
                    ("timeframe", "{{timeframe}}", ""),
                    ("strategy_key", "{{strategy_key}}", ""),
                    ("since", "2026-10-01T00:00:00Z", "bar_time >= since"),
                    ("mine", "true", "Only my active strategies"),
                ],
            ),
            Req(
                "me_strategies_delete",
                "Delete activation",
                "DELETE",
                "/me/strategies/:user_strategy_id",
                "Stops the live strategy. Signals already produced are kept.",
                path_vars={"user_strategy_id": ("{{user_strategy_id}}", "Activation UUID")},
                expect=[204],
            ),
        ],
    ),
    Folder(
        "Custom Strategies",
        "No-code strategies built by users (`docs/custom-strategies.md`):\n\n"
        "* **Builder**: indicator/price/constant conditions combined with `all` (AND) / `any` "
        "(OR).\n"
        "* **Composite**: 2–5 strategies (global or custom) that vote.\n\n"
        "A custom strategy has the key `custom:<uuid>` and works in preview, backtests and "
        "activations. Someone else's private strategy always answers **404**. Limits: trader 5, "
        "other roles 50; only analysts, experts and admins can publish.",
        [
            Req(
                "custom_schema",
                "Definition schema & editor catalog",
                "GET",
                "/custom-strategies/schema",
                "JSON Schema of both definitions plus everything an editor needs: indicators "
                "(params, outputs), price fields, ops with their operands, composite modes, the "
                "global strategies and every limit. JWT or API key `strategies:read`.",
            ),
            Req(
                "custom_validate",
                "Validate definition",
                "POST",
                "/custom-strategies/validate",
                "Checks a definition without saving it. **Always 200**: `{valid, errors[], "
                "history, definition, definition_hash}`; each error has the JSON path of the "
                "problem. Rate-limit cost 2.",
                body={"kind": "builder", "definition": RSI_BOLLINGER},
                cost=2,
                variants=[
                    Variant(
                        "200 Invalid definition (errors with paths)",
                        200,
                        body={
                            "kind": "builder",
                            "definition": {
                                "schema_version": 1,
                                "category": "trend",
                                "buy": {
                                    "all": [
                                        {
                                            "left": {
                                                "type": "indicator",
                                                "name": "rsi",
                                                "params": {"length": 0},
                                            },
                                            "op": "<",
                                            "right": {"type": "constant", "value": 30},
                                        }
                                    ]
                                },
                            },
                        },
                    )
                ],
            ),
            Req(
                "custom_create",
                "Create custom strategy",
                "POST",
                "/me/custom-strategies",
                "`kind` = `builder` or `composite`. 422 lists every definition error, 409 name "
                "taken (case-insensitive), 400 over your limit, 403 `public` as a trader. The "
                "stored definition is normalised (defaults written out).",
                body={
                    "name": "RSI + Bollinger dip {{$timestamp}}",
                    "description": "Buy oversold closes under the lower band, sell RSI > 65.",
                    "kind": "builder",
                    "definition": RSI_BOLLINGER,
                    "visibility": "private",
                },
                expect=[201],
                captures={
                    "custom_strategy_id": "id",
                    "custom_strategy_key": "key",
                    "custom_strategy_version": "version",
                },
                variants=[
                    Variant(
                        "201 Composite strategy",
                        201,
                        body={
                            "name": "Reversal vote {{$timestamp}}",
                            "kind": "composite",
                            "definition": COMPOSITE,
                        },
                    ),
                    Variant(
                        "422 Invalid definition",
                        422,
                        body={
                            "name": "Broken",
                            "kind": "builder",
                            "definition": {"schema_version": 1, "category": "trend"},
                        },
                    ),
                ],
            ),
            Req(
                "custom_list",
                "List my custom strategies",
                "GET",
                "/me/custom-strategies",
                "Your strategies without definitions, newest first.",
                query=[("limit", "50", "1–100"), ("offset", "0", "")],
                optional_query=[("kind", "builder", "builder | composite")],
            ),
            Req(
                "custom_get",
                "Get custom strategy",
                "GET",
                "/me/custom-strategies/:strategy_id",
                "Full strategy: `key`, `definition`, `valid` + `errors` (false if a member was "
                "deleted or made private), `history` (warm-up bars) and `usage` counts.",
                path_vars={"strategy_id": ("{{custom_strategy_id}}", "Custom strategy UUID")},
            ),
            Req(
                "custom_replace",
                "Replace definition",
                "PUT",
                "/me/custom-strategies/:strategy_id",
                "Replaces the definition. `version` must be the version you edited: a change by "
                "another client in between answers **409** with `current_version`. Active setups "
                "follow the new definition from the next bar.",
                path_vars={"strategy_id": ("{{custom_strategy_id}}", "Custom strategy UUID")},
                body={"version": "{{custom_strategy_version}}", "definition": EMA_CROSS},
                captures={"custom_strategy_version": "version"},
                variants=[
                    Variant(
                        "409 Stale version",
                        409,
                        body={"version": 1, "definition": EMA_CROSS},
                    )
                ],
            ),
            Req(
                "custom_update",
                "Update name / visibility",
                "PATCH",
                "/me/custom-strategies/:strategy_id",
                "`name`, `description`, `visibility` (`private` | `public`). Publishing needs the "
                "analyst, expert or admin role (403 for traders).",
                path_vars={"strategy_id": ("{{custom_strategy_id}}", "Custom strategy UUID")},
                body={
                    "description": "EMA 9/21 cross, shared with the team.",
                    "visibility": "public",
                },
                expect=[200, 403],
            ),
            Req(
                "custom_clone",
                "Clone my strategy",
                "POST",
                "/me/custom-strategies/:strategy_id/clone",
                'A private copy named `"<name> (copy)"`.',
                path_vars={"strategy_id": ("{{custom_strategy_id}}", "Custom strategy UUID")},
                expect=[201],
                captures={"custom_strategy_clone_id": "id"},
            ),
            Req(
                "custom_public",
                "Browse public strategies",
                "GET",
                "/custom-strategies/public",
                "Everyone's public strategies, most recently updated first, with the author's "
                "display name and role (never user ids). JWT or API key `strategies:read`.",
                query=[("limit", "20", "1–100"), ("offset", "0", "")],
                optional_query=[
                    ("search", "EMA", "Part of the name"),
                    ("kind", "builder", "builder | composite"),
                ],
                captures={"public_strategy_id": "items.0.id"},
            ),
            Req(
                "custom_public_clone",
                "Clone public strategy",
                "POST",
                "/custom-strategies/public/:strategy_id/clone",
                "Copies a public strategy into your list (private, `cloned_from` set; your limit "
                "applies).",
                path_vars={"strategy_id": ("{{public_strategy_id}}", "Public strategy UUID")},
                expect=[201],
                captures={"public_clone_id": "id"},
            ),
            Req(
                "custom_delete",
                "Delete custom strategy",
                "DELETE",
                "/me/custom-strategies/:strategy_id",
                "Deactivates its activations; signals and backtests are kept. 409 if one of your "
                "composites uses it. The test script also deletes the clones made above.",
                path_vars={"strategy_id": ("{{custom_strategy_id}}", "Custom strategy UUID")},
                expect=[204],
                tests=CUSTOM_CLEANUP,
            ),
        ],
    ),
    Folder(
        "Backtests",
        "Historical simulation of a strategy (`docs/backtesting.md`). Runs on a dedicated "
        "Celery queue; progress is pushed on the user's WebSocket topic (`backtest_progress`, "
        "`backtest_completed`, `backtest_failed`) or can be polled.\n\n"
        "* Create, compare, cancel/delete: JWT. Reading: also API key `backtests:read`.\n"
        "* Creating costs **5** rate-limit units; per-role limits on running and daily "
        "backtests apply.",
        [
            Req(
                "backtests_create",
                "Queue backtest",
                "POST",
                "/backtests",
                "Answers **202** with the id while the worker runs it. `params` and `config` are "
                "optional (defaults are stored resolved). 422: unknown strategy, bad params or "
                "config, `start ≥ end`, `end` in the future, no candles in the range.",
                body={
                    "instrument_id": "{{instrument_id}}",
                    "timeframe": "{{timeframe}}",
                    "strategy_key": "{{strategy_key}}",
                    "params": {"fast": 9, "slow": 21},
                    "start": "{{backtest_start}}",
                    "end": "{{backtest_end}}",
                    "config": {
                        "initial_capital": 10000,
                        "fee_bps": 10,
                        "slippage_bps": 5,
                        "direction": "long_only",
                        "sizing": {"mode": "fraction", "value": 1.0},
                        "exits": {
                            "stop_loss_pct": 2,
                            "take_profit_pct": 4,
                            "max_bars_held": None,
                            "exit_on_opposite_signal": True,
                        },
                    },
                },
                expect=[202],
                captures={"backtest_id": "id"},
                pre=BACKTEST_DATES,
                cost=5,
                variants=[
                    Variant(
                        "422 start must be before end",
                        422,
                        body={
                            "instrument_id": "{{instrument_id}}",
                            "timeframe": "1h",
                            "strategy_key": "ma_crossover",
                            "start": "2026-10-10T00:00:00Z",
                            "end": "2026-10-01T00:00:00Z",
                        },
                    )
                ],
            ),
            Req(
                "backtests_get",
                "Get backtest result",
                "GET",
                "/backtests/:backtest_id",
                "Everything a results page needs: config, status/progress, metrics, equity and "
                "drawdown curves (at most 2,000 Lightweight Charts points) and entry/exit "
                "markers. In the Collection Runner this request repeats until the backtest has "
                "finished.",
                path_vars={"backtest_id": ("{{backtest_id}}", "Backtest UUID")},
                tests=POLL_BACKTEST,
            ),
            Req(
                "backtests_trades",
                "List trades",
                "GET",
                "/backtests/:backtest_id/trades",
                "The simulated trades, paginated (`limit` up to 500).",
                path_vars={"backtest_id": ("{{backtest_id}}", "Backtest UUID")},
                query=[("limit", "100", "1–500"), ("offset", "0", "")],
            ),
            Req(
                "backtests_trades_csv",
                "Export trades (CSV)",
                "GET",
                "/backtests/:backtest_id/trades.csv",
                "All trades as `text/csv` (one header row, ISO 8601 UTC times), served as an "
                "attachment `backtest-<id>-trades.csv`.",
                path_vars={"backtest_id": ("{{backtest_id}}", "Backtest UUID")},
            ),
            Req(
                "backtests_create_2",
                "Queue second backtest (for compare)",
                "POST",
                "/backtests",
                "Same endpoint as **Queue backtest**, with `rsi_reversal`, so **Compare** has two "
                "backtests to put side by side.",
                body={
                    "instrument_id": "{{instrument_id}}",
                    "timeframe": "{{timeframe}}",
                    "strategy_key": "rsi_reversal",
                    "start": "{{backtest_start}}",
                    "end": "{{backtest_end}}",
                },
                expect=[202],
                captures={"backtest_id_2": "id"},
                pre=BACKTEST_DATES,
                cost=5,
            ),
            Req(
                "backtests_list",
                "List my backtests",
                "GET",
                "/backtests",
                "Newest first, with headline metrics once completed.",
                query=[("limit", "20", "1–100"), ("offset", "0", "")],
                optional_query=[
                    ("status", "completed", "queued | running | completed | failed | cancelled"),
                    ("strategy_key", "{{strategy_key}}", ""),
                    ("instrument_id", "{{instrument_id}}", ""),
                ],
            ),
            Req(
                "backtests_compare",
                "Compare backtests",
                "POST",
                "/backtests/compare",
                "2–6 of your **completed** backtests: metrics side by side and equity normalised "
                "to 100 at the start.",
                body={"ids": ["{{backtest_id}}", "{{backtest_id_2}}"]},
                pre=WAIT_SECOND_BACKTEST,
            ),
            Req(
                "backtests_delete",
                "Cancel / delete backtest",
                "DELETE",
                "/backtests/:backtest_id",
                "Cancels a queued/running backtest (it stops at its next checkpoint); otherwise "
                "deletes it with its trades. The test script also deletes the second backtest.",
                path_vars={"backtest_id": ("{{backtest_id}}", "Backtest UUID")},
                expect=[204],
                tests=BACKTEST_CLEANUP,
            ),
        ],
    ),
    Folder(
        "Workspaces",
        "Saved trading screens shared by the web and mobile apps (`docs/workspaces.md`). JWT "
        "only.\n\n"
        "**Optimistic concurrency:** `version` goes up on every state change. `PUT` must say "
        'which version it edited (body `version` or `If-Match: "7"`); a stale version answers '
        "**409** with `current_version`, no version at all **428**.\n\n"
        "Limits: trader 5 workspaces, other roles 20. Sharing: analysts, experts, admins.",
        [
            Req(
                "ws_list",
                "List workspaces",
                "GET",
                "/me/workspaces",
                "Summaries in tab order. A user without any gets the default workspace created "
                "first, so the list is never empty.",
                tests=WORKSPACE_IDS,
            ),
            Req(
                "ws_create",
                "Create workspace",
                "POST",
                "/me/workspaces",
                "From a full `state`, or from a `template` (`default`, `blank`, `multi_chart`; "
                "`blank` if neither). 409 name exists, 400 over the limit.",
                body={"name": "Scalping {{$timestamp}}", "template": "multi_chart"},
                expect=[201],
                captures={"workspace_id": "id", "workspace_version": "version"},
                variants=[
                    Variant(
                        "201 From a full state",
                        201,
                        body={"name": "BTC split {{$timestamp}}", "state": WORKSPACE_STATE},
                    ),
                    Variant(
                        "422 Invalid state (paths in loc)",
                        422,
                        body={
                            "name": "Broken",
                            "state": {
                                "layout": {"type": "2x2"},
                                "panels": [{"id": "p1"}],
                                "active_panel": "p9",
                            },
                        },
                    ),
                ],
            ),
            Req(
                "ws_get",
                "Get workspace",
                "GET",
                "/me/workspaces/:workspace_id",
                'The full workspace with `ETag: "<version>"`. Panels carry read-only '
                "`instrument` info and `unavailable` flags.",
                path_vars={"workspace_id": ("{{workspace_id}}", "Workspace UUID")},
                captures={"workspace_version": "version"},
                tests=ETAG_TESTS,
            ),
            Req(
                "ws_replace",
                "Save workspace state",
                "PUT",
                "/me/workspaces/:workspace_id",
                "Replaces the whole `state` (layout, panels, indicators, strategy overlays, "
                "drawings, watchlist). Sends the edited version as `If-Match`; answers the new "
                "workspace with `version + 1`.",
                path_vars={"workspace_id": ("{{workspace_id}}", "Workspace UUID")},
                headers=[("If-Match", '"{{workspace_version}}"', "The version you edited")],
                body={"state": WORKSPACE_STATE},
                captures={"workspace_version": "version"},
                variants=[
                    Variant(
                        "409 Version conflict",
                        409,
                        headers={"If-Match": '"1"'},
                    ),
                    Variant(
                        "428 Version required",
                        428,
                        headers={"If-Match": ""},
                    ),
                ],
            ),
            Req(
                "ws_update",
                "Rename / make default",
                "PATCH",
                "/me/workspaces/:workspace_id",
                "`name` and/or `is_default: true` (the previous default is unset in the same "
                "transaction). Does not change `version`.",
                path_vars={"workspace_id": ("{{workspace_id}}", "Workspace UUID")},
                body={"name": "Scalping BTC {{$timestamp}}", "is_default": True},
            ),
            Req(
                "ws_duplicate",
                "Duplicate workspace",
                "POST",
                "/me/workspaces/:workspace_id/duplicate",
                'A copy named `"<name> (copy)"`, not default and not shared.',
                path_vars={"workspace_id": ("{{workspace_id}}", "Workspace UUID")},
                expect=[201],
                captures={"workspace_copy_id": "id"},
            ),
            Req(
                "ws_list_2",
                "List workspaces (refresh ids)",
                "GET",
                "/me/workspaces",
                "Same as **List workspaces**; refreshes `workspace_ids` for the reorder below.",
                tests=WORKSPACE_IDS,
            ),
            Req(
                "ws_reorder",
                "Reorder tabs",
                "PUT",
                "/me/workspaces/order",
                "`ids` must contain **exactly** all of your workspace ids, in the new tab order. "
                "The pre-request script sends the current order reversed.",
                body='{\n    "ids": {{workspace_ids_reversed}}\n}',
                pre=WORKSPACE_REORDER_PRE,
            ),
            Req(
                "ws_share",
                "Share (read-only link)",
                "POST",
                "/me/workspaces/:workspace_id/share",
                "Analysts, experts and admins (403 for traders): returns the `share_slug` of "
                "the read-only link `/workspaces/shared/{slug}`.",
                path_vars={"workspace_id": ("{{workspace_id}}", "Workspace UUID")},
                expect=[200, 403],
                captures={"share_slug": "share_slug"},
                tests=SHARE_TESTS,
            ),
            Req(
                "ws_shared_get",
                "Open shared workspace",
                "GET",
                "/workspaces/shared/:slug",
                "Any logged-in user: a read-only copy with the owner's display name and role, "
                "never ids.",
                path_vars={"slug": ("{{share_slug}}", "share_slug from Share")},
            ),
            Req(
                "ws_shared_import",
                "Import shared workspace",
                "POST",
                "/workspaces/shared/:slug/import",
                "Copies a shared workspace into your own (`name` optional, made unique; your "
                "limit applies).",
                path_vars={"slug": ("{{share_slug}}", "share_slug from Share")},
                body={"name": "Imported {{$timestamp}}"},
                expect=[201],
                captures={"workspace_import_id": "id"},
            ),
            Req(
                "ws_unshare",
                "Stop sharing",
                "DELETE",
                "/me/workspaces/:workspace_id/share",
                "The old link answers 404 afterwards.",
                path_vars={"workspace_id": ("{{workspace_id}}", "Workspace UUID")},
            ),
            Req(
                "ws_delete",
                "Delete workspace",
                "DELETE",
                "/me/workspaces/:workspace_id",
                "Deleting the default makes the first remaining tab the default. The test script "
                "also deletes the duplicate and the imported copy.",
                path_vars={"workspace_id": ("{{workspace_id}}", "Workspace UUID")},
                expect=[204],
                tests=WORKSPACE_CLEANUP,
            ),
        ],
    ),
    Folder(
        "API Keys",
        "Personal API keys (`tk_…`) for bots, notebooks and scripts (`docs/api-keys.md`). "
        "Managed with a JWT only, never with another key.\n\n"
        "| Scope | Grants |\n|---|---|\n"
        "| `market:read` | instruments, candles |\n"
        "| `indicators:read` | indicator catalog + compute |\n"
        "| `strategies:read` | strategy catalog + preview, custom-strategy schema + public list |\n"
        "| `signals:read` | `GET /signals` |\n"
        "| `stream` | WebSocket `/ws/market` |\n"
        "| `backtests:read` | reading your backtests |\n\n"
        "Active keys per account: trader 2, analyst/expert 5, admin 10. Each key has its own "
        "rate-limit bucket.",
        [
            Req(
                "keys_create",
                "Create API key",
                "POST",
                "/me/api-keys",
                "The full `key` is in **this response only** (the server stores a SHA-256 hash). "
                "It is saved to the `api_key` environment variable for the requests in "
                "**Using an API key**.",
                body={
                    "name": "Postman bot {{$timestamp}}",
                    "scopes": ["market:read", "indicators:read", "signals:read", "stream"],
                    "expires_in_days": 30,
                    "rate_limit_per_minute": 30,
                },
                expect=[201],
                captures={"api_key_id": "id", "api_key": "key"},
            ),
            Req(
                "keys_list",
                "List my API keys",
                "GET",
                "/me/api-keys",
                "Prefix, name, scopes, limits, `last_used_at` (updated at most once a minute), "
                "`expires_at`, `revoked`. Never the key itself.",
            ),
            Req(
                "keys_update",
                "Update API key",
                "PATCH",
                "/me/api-keys/:key_id",
                "Change `name`, `scopes` or `rate_limit_per_minute` (`null` = back to your tier).",
                path_vars={"key_id": ("{{api_key_id}}", "API key UUID")},
                body={
                    "name": "Postman bot (market only)",
                    "scopes": ["market:read", "signals:read", "stream"],
                    "rate_limit_per_minute": None,
                },
            ),
            Folder(
                "Using an API key",
                "Requests sent with `X-API-Key: {{api_key}}` instead of a JWT, as an external "
                "program would. The key needs the endpoint's scope; `/auth/*`, `/users/me`, "
                "`/me/*` and `/admin/*` never accept keys.",
                [
                    Req(
                        "apikey_instruments",
                        "List instruments (API key)",
                        "GET",
                        "/market/instruments",
                        "Needs `market:read`.",
                        auth="apikey",
                        query=[("q", "BTC", "Symbol contains"), ("limit", "5", "")],
                    ),
                    Req(
                        "apikey_candles",
                        "Get candles (API key)",
                        "GET",
                        "/market/instruments/:instrument_id/candles",
                        "Needs `market:read`.",
                        auth="apikey",
                        path_vars={"instrument_id": ("{{instrument_id}}", "Instrument UUID")},
                        query=[("timeframe", "1h", ""), ("limit", "3", "")],
                    ),
                    Req(
                        "apikey_signals",
                        "List signals (API key)",
                        "GET",
                        "/signals",
                        "Needs `signals:read`. `mine=true` = signals of the key owner's active "
                        "strategies.",
                        auth="apikey",
                        query=[("limit", "5", "")],
                    ),
                    Req(
                        "apikey_forbidden",
                        "Account endpoint with a key (403)",
                        "GET",
                        "/users/me",
                        "Shows the refusal: account, `/me/*` and admin endpoints never accept "
                        "API keys, whatever the scopes.",
                        auth="apikey",
                        expect=[403],
                        variants=[Variant("403 Key lacks the scope", 403, path="/backtests")],
                    ),
                ],
            ),
            Req(
                "keys_usage",
                "API key usage (7 days)",
                "GET",
                "/me/api-keys/:key_id/usage",
                "Allowed requests and 429 rejections per UTC day for the last 7 days, oldest "
                "first.",
                path_vars={"key_id": ("{{api_key_id}}", "API key UUID")},
            ),
            Req(
                "keys_revoke",
                "Revoke API key",
                "DELETE",
                "/me/api-keys/:key_id",
                "Immediate and permanent. Requests with the key answer 401 afterwards.",
                path_vars={"key_id": ("{{api_key_id}}", "API key UUID")},
                expect=[204],
            ),
        ],
    ),
    Folder(
        "Admin",
        "Admin-only endpoints (role `admin`; everyone else gets 403). Authenticated with "
        "`{{admin_access_token}}`, obtained automatically from `admin_email` / "
        "`admin_password`.\n\n"
        "> ⚠️ On the production environment these requests change real data (roles, "
        "instruments, candles). Review the body before sending.",
        [
            Folder(
                "Users",
                "User management.",
                [
                    Req(
                        "admin_users",
                        "List users",
                        "GET",
                        "/admin/users",
                        "Filter by `role`, `is_active` or e-mail (`q`). The first match is stored as "
                        "`target_user_id`.",
                        auth="admin",
                        query=[
                            ("limit", "20", "1–100"),
                            ("offset", "0", ""),
                            ("q", "{{user_email}}", "E-mail contains"),
                        ],
                        optional_query=[
                            ("role", "trader", "trader | analyst | expert | admin"),
                            ("is_active", "true", ""),
                        ],
                        captures={"target_user_id": "items.0.id"},
                    ),
                    Req(
                        "admin_user_role",
                        "Change user role",
                        "PATCH",
                        "/admin/users/:user_id/role",
                        "Takes effect on existing tokens at once (the role is read from the "
                        "database on every request). Admins cannot demote themselves.",
                        auth="admin",
                        path_vars={"user_id": ("{{target_user_id}}", "User UUID")},
                        body={"role": "analyst"},
                        variants=[
                            Variant(
                                "422 Unknown role",
                                422,
                                body={"role": "superuser"},
                            )
                        ],
                    ),
                    Req(
                        "admin_user_status",
                        "Activate / deactivate user",
                        "PATCH",
                        "/admin/users/:user_id/status",
                        "An inactive user gets 403 on every request and cannot log in. Admins "
                        "cannot deactivate themselves.",
                        auth="admin",
                        path_vars={"user_id": ("{{target_user_id}}", "User UUID")},
                        body={"is_active": True},
                    ),
                ],
            ),
            Folder(
                "Market Data",
                "Instrument catalogue and candle ingestion (backfill scripts, collectors).",
                [
                    Req(
                        "admin_instrument_create",
                        "Create instrument",
                        "POST",
                        "/admin/instruments",
                        "`symbol` + `source` are unique. `BASE/QUOTE` symbols derive "
                        "`base_asset` / `quote_asset`; other symbols must send both.",
                        auth="admin",
                        body={
                            "symbol": "PM{{$timestamp}}/USDT",
                            "source": "postman",
                            "market": "crypto",
                            "price_precision": 2,
                            "quantity_precision": 6,
                            "is_active": True,
                        },
                        expect=[201],
                        captures={"admin_instrument_id": "id"},
                        variants=[
                            Variant(
                                "422 Assets required",
                                422,
                                body={"symbol": "AAPL", "source": "nasdaq", "market": "stock"},
                            )
                        ],
                    ),
                    Req(
                        "admin_instrument_update",
                        "Update instrument",
                        "PATCH",
                        "/admin/instruments/:instrument_id",
                        "Precisions, assets and `is_active`. Here: deactivates the instrument "
                        "created above (it disappears from charts and live feeds).",
                        auth="admin",
                        path_vars={"instrument_id": ("{{admin_instrument_id}}", "Instrument UUID")},
                        body={"price_precision": 4, "is_active": False},
                    ),
                    Req(
                        "admin_candles_upsert",
                        "Upsert 1m candles",
                        "POST",
                        "/admin/instruments/:instrument_id/candles",
                        "Bulk upsert of **1m** candles (max 5,000 per request). `ts` (alias "
                        "`time`) is the UTC minute start, ISO 8601 or unix seconds. Old batches "
                        "also refresh the higher-timeframe aggregates; recent candles are pushed "
                        "to WebSocket subscribers.",
                        auth="admin",
                        path_vars={"instrument_id": ("{{admin_instrument_id}}", "Instrument UUID")},
                        body={
                            "candles": [
                                {
                                    "ts": "{{candle_ts_0}}",
                                    "open": 100.0,
                                    "high": 101.5,
                                    "low": 99.8,
                                    "close": 101.2,
                                    "volume": 12.5,
                                    "trades": 41,
                                },
                                {
                                    "ts": "{{candle_ts_1}}",
                                    "open": 101.2,
                                    "high": 102.0,
                                    "low": 100.9,
                                    "close": 101.7,
                                    "volume": 9.1,
                                    "trades": 33,
                                },
                                {
                                    "ts": "{{candle_ts_2}}",
                                    "open": 101.7,
                                    "high": 101.9,
                                    "low": 100.4,
                                    "close": 100.6,
                                    "volume": 15.0,
                                    "trades": 52,
                                },
                            ]
                        },
                        pre=CANDLES_NOW,
                        variants=[
                            Variant(
                                "422 Invalid candle",
                                422,
                                body={
                                    "candles": [
                                        {
                                            "ts": "2026-10-16T10:00:30Z",
                                            "open": 1,
                                            "high": 0.5,
                                            "low": 1,
                                            "close": 1,
                                            "volume": 1,
                                        }
                                    ]
                                },
                            )
                        ],
                    ),
                ],
            ),
            Folder(
                "API Keys & Rate Limits",
                "Every user's keys, and rate-limit monitoring.",
                [
                    Req(
                        "admin_keys",
                        "List all API keys",
                        "GET",
                        "/admin/api-keys",
                        "All keys with `user_id` and `owner_email`.",
                        auth="admin",
                        query=[("limit", "50", "1–100"), ("offset", "0", "")],
                        optional_query=[
                            ("user_id", "{{target_user_id}}", "Owner"),
                            ("revoked", "false", ""),
                        ],
                        captures={"admin_api_key_id": "items.0.id"},
                    ),
                    Req(
                        "admin_key_revoke",
                        "Revoke any API key",
                        "DELETE",
                        "/admin/api-keys/:key_id",
                        "Revokes another user's key (e.g. a leaked one). Points at `api_key_id` "
                        "(the key created in **API Keys**, already revoked there), so running the "
                        "collection never revokes someone else's key by accident.",
                        auth="admin",
                        path_vars={"key_id": ("{{api_key_id}}", "API key UUID")},
                        expect=[204],
                        variants=[
                            Variant(
                                "404 API key not found",
                                404,
                                path_vars={"key_id": "00000000-0000-0000-0000-000000000000"},
                            )
                        ],
                    ),
                    Req(
                        "admin_rate_limits",
                        "Rate-limit stats",
                        "GET",
                        "/admin/rate-limits/stats",
                        "429s of the last hour by tier and route group (all API processes, from "
                        "Redis), and requests let through while Redis was unreachable (this "
                        "process only).",
                        auth="admin",
                    ),
                    Req(
                        "admin_realtime",
                        "WebSocket hub stats",
                        "GET",
                        "/admin/realtime/stats",
                        "Connections, subscriptions and message counters of the WebSocket hub of "
                        "the API process that serves the request.",
                        auth="admin",
                    ),
                ],
            ),
        ],
        auth="admin",
    ),
]

# Documented in the collection but not executable as HTTP requests (Postman collection format
# v2.1 cannot store WebSocket requests): rendered as the "Realtime (WebSocket)" folder text.
WEBSOCKET_DOC = """Live candles, signals and user notifications over **one** WebSocket connection. \
Postman collections (v2.1) cannot store WebSocket requests: open **New → WebSocket** in Postman \
and use the URL and messages below. Full protocol: `docs/websocket.md`.

### Connect

```
{{ws_url}}/ws/market?token={{access_token}}     # user (access JWT)
{{ws_url}}/ws/market?api_key={{api_key}}        # external program (key with the `stream` scope)
```

Invalid/expired credentials: the server accepts, then closes with **4401**. Refresh the token \
and reconnect.

### Client → server (JSON text frames, max 4 KB)

```json
{"op": "subscribe",   "topic": "candles", "instrument_id": "{{instrument_id}}", "timeframe": "1m"}
{"op": "unsubscribe", "topic": "candles", "instrument_id": "{{instrument_id}}", "timeframe": "1m"}
{"op": "subscribe",   "topic": "signals", "instrument_id": "{{instrument_id}}"}
{"op": "ping"}
```

### Server → client

```json
{"type": "subscribed", "topic": "candles:<uuid>:1m"}
{"type": "snapshot",   "topic": "candles:<uuid>:1m", "candle": {"time": 1760000000, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}}
{"type": "candle",     "topic": "candles:<uuid>:1m", "instrument_id": "<uuid>", "timeframe": "1m", "candle": {"time": 1760000040, "open": 1.0, "high": 1.2, "low": 0.9, "close": 1.1, "volume": 3.5}, "sent_at": 1760000041234}
{"type": "signal",     "topic": "signals:<uuid>", "signal": {"strategy_key": "rsi_reversal", "side": "buy", "time": 1760000000, "price": 61234.5, "...": "..."}}
{"type": "pong"}
{"type": "heartbeat"}
{"type": "error", "code": "unknown_instrument", "message": "instrument not found"}
```

Pushed to the user's own topic without subscribing: `signal` (with `user_strategy_ids`) for \
activations with `notify: true`, `workspace_updated`, `backtest_progress`, \
`backtest_completed`, `backtest_failed`.

### Limits and close codes

| | |
|---|---|
| Subscriptions per connection | 50 |
| Server heartbeat | every 25 s; send `{"op":"ping"}` every ~30 s |
| Idle timeout | 75 s without a client frame → **1001** |
| Slow consumer | > 256 undelivered messages → **1013** |
| Bad / expired token or key | **4401** |
| Connections | 5 per identity, 20 new per minute per IP → **4429** |

Reconnect with exponential backoff (1 s → 30 s, with jitter) and send your `subscribe` ops \
again after every reconnect."""
