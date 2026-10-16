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
                {
                    "id": "i1",
                    "name": "ema",
                    "params": {"length": 21},
                    "color": "#FF9800",
                },
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

RISK_CONFIG = {
    "stop": {"type": "atr", "length": 14, "multiplier": 2.0},
    "trailing": {"type": "atr", "length": 14, "multiplier": 3.0, "breakeven_r": 1},
    "take_profit": {
        "type": "r_multiple",
        "levels": [{"r": 1, "close_pct": 50}, {"r": 2, "close_pct": 50}],
    },
    "sizing": {
        "mode": "risk",
        "risk_pct": 1.0,
        "max_position_pct": 100,
        "min_notional": 10,
    },
    "guards": {"max_daily_loss_pct": 3, "max_drawdown_pct": 10, "cooldown_bars": 5},
    "fee_bps": 10,
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

FEED_TESTS = """// Another user's readable post (to report) and an analyst or expert (to follow); unset when none.
if (json && pm.response.code === 200) {
    const me = pm.variables.get("user_id");
    const other = json.items.find((p) => p.author.id !== me && !p.locked);
    const followable = json.items.find((p) => p.author.id !== me && ["analyst", "expert"].includes(p.author.role));
    other ? store.set("other_post_id", other.id) : store.unset("other_post_id");
    followable ? store.set("author_user_id", followable.author.id) : store.unset("author_user_id");
}"""

CREATE_POST_TESTS = """// Traders cannot publish: skip the requests that work on the new post.
if (pm.response.code === 403) {
    store.unset("post_id");
    pm.execution.setNextRequest("Follow user");
}"""

SKIP_NO_AUTHOR = """// No analyst or expert in the feed yet: nothing to follow.
if (!pm.variables.get("author_user_id")) pm.execution.skipRequest();"""

SKIP_NO_OTHER_POST = """// No post of another user in the feed yet: nothing to report.
if (!pm.variables.get("other_post_id")) pm.execution.skipRequest();"""

SKIP_NO_REPORT = """// Only when Community → Report post created a report in this run.
if (!pm.variables.get("report_id")) pm.execution.skipRequest();"""

ARTICLE = {
    "source_key": "postman",
    "external_id": "postman-demo-1",
    "url": "https://example.com/news/bitcoin-etf-inflows",
    "title": "Bitcoin climbs as spot ETF inflows hit a weekly record",
    "summary": "<p>Spot bitcoin ETFs took in <b>$1.2bn</b> this week, the most since launch.</p>",
    "published_at": "2026-10-16T12:30:00Z",
    "language": "en",
    "image_url": "https://example.com/img/btc-etf.jpg",
    "author": "Postman demo",
    "instruments": [
        {"symbol": "BTC/USDT", "relevance": 1.0},
        {"symbol": "ETH", "relevance": 0.4},
    ],
    "sentiment": {"label": "positive", "score": 0.71, "model": "finbert-ft-v1"},
}

EXPERTS_TESTS = """// Another expert (to subscribe to and chat with); unset when there is none.
if (json && pm.response.code === 200) {
    const me = pm.variables.get("user_id");
    const expert = json.items.find((e) => e.id !== me);
    expert ? store.set("expert_id", expert.id) : store.unset("expert_id");
}"""

EXPERT_TESTS = """if (json && pm.response.code === 200 && !_.get(json, "plans.0.id")) store.unset("plan_id");"""

SKIP_NO_EXPERT = """// No other expert listed yet: nothing to subscribe to.
if (!pm.variables.get("expert_id")) pm.execution.skipRequest();"""

SKIP_NO_PLAN = """// The expert has no active plan: nothing to buy.
if (!pm.variables.get("plan_id")) pm.execution.skipRequest();"""

CHECKOUT_TESTS = """// Already subscribed to this expert (one live subscription per expert): skip the payment.
if (pm.response.code === 409) pm.execution.setNextRequest("My subscriptions");"""

MY_SUBS_TESTS = """// The subscription to {{expert_id}} (a live one first) and its first invoice.
if (json && pm.response.code === 200) {
    const mine = json.filter((s) => s.expert.id === pm.variables.get("expert_id"));
    const sub = mine.find((s) => ["trialing", "active", "past_due"].includes(s.status)) || mine[0];
    if (sub) {
        store.set("subscription_id", sub.id);
        if (sub.invoices.length) store.set("invoice_id", sub.invoices[0].id);
    } else {
        store.unset("subscription_id");
    }
}"""

SKIP_NO_SUBSCRIPTION = """// No subscription to work on.
if (!pm.variables.get("subscription_id")) pm.execution.skipRequest();"""

OPEN_CONVERSATION_TESTS = """// No chat perk (403): skip the chat requests.
if (pm.response.code >= 300) store.unset("conversation_id");"""

SKIP_NO_CONVERSATION = """// No conversation (no subscription with the chat perk).
if (!pm.variables.get("conversation_id")) pm.execution.skipRequest();"""

CHAT_CLIENT_ID_PRE = """// One client_id per message, made by the app; a retry with the same one never duplicates.
pm.variables.set("chat_client_id", pm.variables.replaceIn("{{$guid}}"));
if (!pm.variables.get("conversation_id")) pm.execution.skipRequest();"""

EXPERT_PROFILE_TESTS = """// Only experts have a profile: skip the expert-side requests for other roles.
if (pm.response.code === 403) pm.execution.setNextRequest("Get notification preferences");"""

SKIP_NO_INVOICE = """// Only when Experts → My subscriptions found an invoice in this run.
if (!pm.variables.get("invoice_id")) pm.execution.skipRequest();"""

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
                "health_live",
                "Liveness probe",
                "GET",
                "/health/live",
                'Returns `200 {"status": "ok"}` as long as the process answers; no dependency is '
                "checked. Meant for container liveness probes (a slow database must not get the "
                "API restarted). Successful health calls are not written to the request log.",
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
                        body={
                            "email": "{{user_email}}",
                            "password": "Secret123",
                            "full_name": "x",
                        },
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
                "the **Authorize** button of Swagger UI (`/docs`, served outside production only, or when "
                "`API_DOCS_ENABLED=true`); apps use `/auth/login`.",
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
                    Variant(
                        "401 Invalid refresh token",
                        401,
                        body={"refresh_token": "not-a-jwt"},
                    )
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
                        body={
                            "current_password": "Nope12345",
                            "new_password": "Another123",
                        },
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
                "`notify: true` each new signal is pushed to the user's WebSocket topic, with a "
                "**trade plan** from `risk_override` (per-activation risk rules) or, when it is "
                "`null`, from the user's risk profile.",
                body={
                    "strategy_key": "{{strategy_key}}",
                    "instrument_id": "{{instrument_id}}",
                    "timeframe": "{{timeframe}}",
                    "params": {"fast": 9, "slow": 21},
                    "name": "BTC 1h EMA cross",
                    "is_active": True,
                    "notify": True,
                    "risk_override": None,
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
                "Change `name`, `params`, `is_active`, `notify` or `risk_override` (risk rules "
                "for this activation's plans; `null` = back to the risk profile). Only the "
                "fields sent change.",
                path_vars={"user_strategy_id": ("{{user_strategy_id}}", "Activation UUID")},
                body={
                    "params": {"fast": 12, "slow": 26},
                    "notify": False,
                    "risk_override": {
                        "stop": {"type": "percent", "value": 1.5},
                        "take_profit": {"type": "r_multiple", "value": 2},
                        "sizing": {"mode": "risk", "risk_pct": 0.5},
                    },
                },
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
        "Risk Management",
        "Stops, trailing stops, targets, position sizing and account guards "
        "(`docs/risk-management.md`). The same rules run in backtests and in the **trade plan** "
        "attached to every live signal (entry, stop, targets, quantity, money at risk, R:R).\n\n"
        "* Risk profile and signal plans: JWT only.\n"
        "* Schema and position-size calculator: JWT or API key `strategies:read`.\n"
        "* Templates: `conservative`, `balanced` (default), `aggressive`.",
        [
            Req(
                "risk_schema",
                "Risk schema & templates",
                "GET",
                "/risk/schema",
                "JSON Schema of a risk config (`stop`, `trailing`, `take_profit`, `sizing`, "
                "`guards`, `fee_bps`) and the normalised templates. Editors are generated from "
                "this.",
            ),
            Req(
                "risk_profile_get",
                "Get my risk profile",
                "GET",
                "/me/risk-profile",
                "Created on first read with the `balanced` template and 10,000 USDT. "
                "`account_size` is what the user declares; the platform never connects to an "
                "exchange. `template` is set while the config is unchanged from a template.",
            ),
            Req(
                "risk_profile_put",
                "Update my risk profile",
                "PUT",
                "/me/risk-profile",
                "`{account_size, quote_currency, config}` or `{template}` (not both; neither "
                "changes only the account). The config is stored normalised. 422 lists every "
                "config error with its `path` (e.g. `stop.multiplier`).",
                body={
                    "account_size": 25000,
                    "quote_currency": "USDT",
                    "config": RISK_CONFIG,
                },
                variants=[
                    Variant(
                        "200 From a template",
                        200,
                        body={"account_size": 10000, "template": "conservative"},
                    ),
                    Variant(
                        "422 Invalid config (paths)",
                        422,
                        body={
                            "config": {
                                "stop": {"type": "atr", "length": 14, "multiplier": 0},
                                "take_profit": {"type": "r_multiple", "value": 2},
                            }
                        },
                    ),
                ],
            ),
            Req(
                "risk_position_size",
                "Position-size calculator",
                "POST",
                "/risk/position-size",
                "A trade plan on the **last closed bar**: stop, targets, quantity, notional, "
                "money at risk and R:R. Omitted `entry` / `stop` come from that bar (its close and "
                "the stop rule); omitted `config` / `account_size` from your risk profile. A "
                "`stop` price replaces the stop rule.",
                body={
                    "instrument_id": "{{instrument_id}}",
                    "timeframe": "{{timeframe}}",
                    "side": "buy",
                },
                variants=[
                    Variant(
                        "200 Explicit entry, stop, rules and account",
                        200,
                        body={
                            "instrument_id": "{{instrument_id}}",
                            "timeframe": "{{timeframe}}",
                            "side": "sell",
                            "entry": 72000,
                            "stop": 73500,
                            "account_size": 5000,
                            "config": {
                                "take_profit": {
                                    "type": "r_multiple",
                                    "levels": [
                                        {"r": 1.5, "close_pct": 50},
                                        {"r": 3, "close_pct": 50},
                                    ],
                                },
                                "sizing": {"mode": "risk", "risk_pct": 2},
                            },
                        },
                    ),
                ],
            ),
            Req(
                "risk_signal_plans",
                "My signal trade plans",
                "GET",
                "/me/signal-plans",
                "The trade plans of your live signals (one per signal and activation), newest "
                "bar first, each with its `signal`. A plan with `invalid_reason` set (e.g. "
                "`stop_unavailable`) should not be traded. Each plan carries `risk_source` "
                "(`override`, `profile` or `default`) and the exact `risk_config` used.",
                query=[("limit", "20", "1–100"), ("offset", "0", "")],
                optional_query=[
                    ("instrument_id", "{{instrument_id}}", ""),
                    ("timeframe", "{{timeframe}}", ""),
                    ("strategy_key", "{{strategy_key}}", ""),
                    ("since", "2026-10-01T00:00:00Z", "bar_time >= since"),
                ],
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
                body={
                    "version": "{{custom_strategy_version}}",
                    "definition": EMA_CROSS,
                },
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
                "optional (defaults are stored resolved). `config` takes the risk rules of "
                "`docs/risk-management.md` (`stop`, `trailing`, `take_profit` with partial "
                '`levels`, `sizing`, `guards`, `check_entry_bar`); `"risk_profile": true` uses '
                "your risk profile instead. 422: unknown strategy, bad params or config (with "
                "`path`, e.g. `stop.multiplier`), `start ≥ end`, `end` in the future, no "
                "candles in the range.",
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
                        "sizing": {"mode": "risk", "risk_pct": 1.0},
                        "stop": {"type": "atr", "length": 14, "multiplier": 2},
                        "take_profit": {
                            "type": "r_multiple",
                            "levels": [
                                {"r": 1, "close_pct": 50},
                                {"r": 2, "close_pct": 50},
                            ],
                        },
                        "trailing": {"type": "atr", "length": 14, "multiplier": 3},
                        "guards": {"max_drawdown_pct": 15},
                        "check_entry_bar": True,
                        "exits": {
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
                "The simulated trades, paginated (`limit` up to 500), with `initial_stop`, "
                "`risk_amount`, `r_multiple` and every exit `fill` (partial take-profits "
                "included).",
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
                'Same endpoint as **Queue backtest**, with `rsi_reversal` and `"risk_profile": '
                "true` (the rules, fee and account size of your risk profile, snapshotted into "
                "`config.risk_profile`), so **Compare** has two backtests to put side by side.",
                body={
                    "instrument_id": "{{instrument_id}}",
                    "timeframe": "{{timeframe}}",
                    "strategy_key": "rsi_reversal",
                    "start": "{{backtest_start}}",
                    "end": "{{backtest_end}}",
                    "config": {"risk_profile": True},
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
                    (
                        "status",
                        "completed",
                        "queued | running | completed | failed | cancelled",
                    ),
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
                        body={
                            "name": "BTC split {{$timestamp}}",
                            "state": WORKSPACE_STATE,
                        },
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
        "| `backtests:read` | reading your backtests |\n"
        "| `news:read` | news list, article, sentiment; WebSocket `news` topics |\n"
        "| `news:write` | the news ingestion API (**admins only**; the key stops working if its "
        "owner is no longer an admin) |\n\n"
        "Active keys per account: trader 2, analyst/expert 5, admin 10. Each key has its own "
        "rate-limit bucket.",
        [
            Req(
                "keys_scopes",
                "List API key scopes",
                "GET",
                "/me/api-keys/scopes",
                "Every scope with its description, `admin_only`, and `grantable` (whether you may "
                "put it on a key: `news:write` is for admins only). For the key forms of the "
                "apps.",
            ),
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
                    "scopes": [
                        "market:read",
                        "indicators:read",
                        "signals:read",
                        "news:read",
                        "stream",
                    ],
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
                    "scopes": ["market:read", "signals:read", "news:read", "stream"],
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
                        "apikey_news",
                        "List news (API key)",
                        "GET",
                        "/news",
                        "Needs `news:read`.",
                        auth="apikey",
                        query=[("limit", "3", "")],
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
        "News",
        "Market news from the built-in RSS fetcher and from the AI side's ingestion API, with "
        "FinBERT sentiment (`docs/news-posts.md`, `docs/news-ingestion.md`). Reading works with a "
        "login or an API key with `news:read`; new articles are also pushed on the WebSocket "
        "`news` topics.\n\n"
        "The first two requests are the **ingestion API of the AI side**: they need `news:write` "
        "(an admin key, or an admin's own login, used here). The demo article has a fixed "
        "`external_id`, so sending it again is `skipped`, not duplicated.\n\n"
        "> ⚠️ On the production environment the ingestion requests store a real (demo) article "
        "under the source `postman`.",
        [
            Req(
                "news_ingest",
                "Ingest articles (AI side)",
                "POST",
                "/ingest/news",
                "Upsert up to 200 articles, idempotent on `source_key` + `external_id`. An "
                "unknown `source_key` creates an `api` source. Each item is validated on its "
                "own: invalid ones are listed in `errors` by index and the rest is stored; "
                "unknown symbols are reported in `warnings`. HTML is stripped from titles and "
                "summaries. `instruments` (when given) replace the article's tags: `BTC/USDT` "
                "is that pair, `ETH` every pair with that base.\n\n"
                "Answer: `inserted`, `updated` (a field changed), `skipped` (identical).",
                auth="admin",
                body={"articles": [ARTICLE]},
                variants=[
                    Variant(
                        "200 Per-item errors and warnings",
                        200,
                        body={
                            "articles": [
                                {
                                    **ARTICLE,
                                    "external_id": "postman-demo-2",
                                    "instruments": [{"symbol": "DOGE/XYZ"}],
                                },
                                {
                                    **ARTICLE,
                                    "external_id": "postman-bad",
                                    "url": "ftp://x",
                                },
                            ]
                        },
                    ),
                    Variant(
                        "403 Missing news:write",
                        403,
                        auth="user",
                    ),
                ],
            ),
            Req(
                "news_ingest_sentiment",
                "Push sentiment (AI side)",
                "POST",
                "/ingest/news/sentiment",
                "Set the FinBERT sentiment of up to 500 existing articles, by `article_id` or by "
                "`source_key` + `external_id`; the last write wins. `score`: −1 (very negative) "
                "… +1 (very positive). Unknown articles are listed in `errors`.",
                auth="admin",
                body={
                    "items": [
                        {
                            "source_key": "postman",
                            "external_id": "postman-demo-1",
                            "label": "positive",
                            "score": 0.82,
                            "model": "finbert-ft-v1",
                        },
                        {
                            "article_id": "00000000-0000-0000-0000-000000000000",
                            "label": "neutral",
                            "score": 0.0,
                            "model": "finbert-ft-v1",
                        },
                    ]
                },
            ),
            Req(
                "news_list",
                "List news",
                "GET",
                "/news",
                "Newest first. `q` is a full-text search in title + summary (whole words, no "
                'stemming; `"exact phrase"`, `or` and `-word` work as in web searches). '
                "`summary` is plain text; `sentiment` is `null` until the AI side scores the "
                "article; `instruments` are the tags, most relevant first. The first article is "
                "stored as `article_id`.",
                query=[("limit", "10", "1–100 (default 30)"), ("offset", "0", "")],
                optional_query=[
                    (
                        "instrument_id",
                        "{{instrument_id}}",
                        "Only articles tagged with it",
                    ),
                    ("sentiment", "positive", "positive | neutral | negative"),
                    ("source", "coindesk_rss", "Source key"),
                    ("language", "en", ""),
                    ("since", "2026-10-01T00:00:00Z", "Published at or after"),
                    ("q", "bitcoin etf", "Full-text search"),
                ],
                captures={"article_id": "items.0.id"},
            ),
            Req(
                "news_get",
                "Get article",
                "GET",
                "/news/:article_id",
                "One article, same shape as in the list.",
                path_vars={"article_id": ("{{article_id}}", "Article UUID")},
                variants=[
                    Variant(
                        "404 Article not found",
                        404,
                        path_vars={"article_id": "00000000-0000-0000-0000-000000000000"},
                    )
                ],
            ),
            Req(
                "news_sentiment",
                "News sentiment",
                "GET",
                "/news/sentiment",
                "Aggregate for the dashboard over `1h`, `24h` (default) or `7d`: per instrument "
                "the articles published in the window, counts per label and the mean score of "
                "the scored ones (`weighted_score`: weighted by tag relevance); `overall` covers "
                "every article of the window.",
                query=[("window", "7d", "1h | 24h | 7d")],
                optional_query=[("instrument_id", "{{instrument_id}}", "One instrument only")],
                variants=[Variant("422 Unknown window", 422, query={"window": "30d"})],
            ),
            Req(
                "news_sources",
                "List news sources",
                "GET",
                "/news/sources",
                "RSS feeds and API sources with their state (`is_active`, "
                "`fetch_interval_minutes`, `last_fetched_at`, `last_error`) and stored article "
                "count. Admins change them in **Admin → News & Moderation**. The first source is "
                "stored as `news_source_id`. JWT only.",
                captures={"news_source_id": "0.id"},
            ),
        ],
    ),
    Folder(
        "Community",
        "Posts, comments, likes, follows, public profiles and reports (`docs/news-posts.md`). JWT "
        "only.\n\n"
        "- Analysts, experts and admins publish posts (traders get 403, and the runner skips "
        "to **Follow user**); everyone can read, comment and like.\n"
        "- `visibility`: `public`, `followers`, or `subscribers` (experts only): readers without "
        "the expert's `premium_posts` perk get a teaser (`locked: true`, the first 200 "
        "characters, no attachments, comments hidden and closed).\n"
        "- Bodies are **Markdown stored as written**: render them with raw HTML disabled. Raw "
        "HTML and `javascript:` links are refused (422).\n"
        "- Comments have two levels: a reply to a reply is stored under the top-level "
        "comment.\n"
        "- Followers get `new_post`, authors `comment_reply` and a batched `post_liked` "
        "notification; nobody is notified about their own actions.\n\n"
        "Daily limits: 10 posts per 24 h, 60 comments per hour, 20 reports per day (429 with "
        "`Retry-After`).",
        [
            Req(
                "posts_feed",
                "Feed",
                "GET",
                "/posts",
                "Newest first. `scope=following`: only authors you follow. Followers-only posts "
                "appear for the author's followers; your own hidden posts appear with "
                '`status: "hidden"`. `attachments` are resolved (`available: false` once the '
                "target is gone or private). No e-mail addresses are ever returned.\n\n"
                "Stores another user's post as `other_post_id` and an analyst or expert as "
                "`author_user_id` for the requests below.",
                query=[
                    ("scope", "all", "all | following"),
                    ("limit", "20", "1–50"),
                    ("offset", "0", ""),
                ],
                optional_query=[
                    ("instrument_id", "{{instrument_id}}", ""),
                    ("author_id", "{{author_user_id}}", ""),
                    ("direction", "bullish", "bullish | bearish | neutral"),
                ],
                tests=FEED_TESTS,
            ),
            Req(
                "posts_create",
                "Create post",
                "POST",
                "/posts",
                "Analysts, experts and admins. `title` one line (≤ 140), `body` Markdown "
                "(≤ 20,000), optional `instrument_id` / `timeframe` / `direction`, up to 5 "
                "`attachments` (`backtest` and `custom_strategy` of your own or a public "
                "strategy, a shared workspace, any `signal`), `visibility` `public` or "
                "`followers`. Your followers get a `new_post` notification.",
                body={
                    "title": "BTC: range break or fake-out?",
                    "body": "## Plan\n\nWatching **64k** as resistance. A 1h close above it "
                    "targets 66k; below 61.5k the idea is invalid.\n\n- Entry: retest of 64k\n"
                    "- Stop: 62.8k",
                    "instrument_id": "{{instrument_id}}",
                    "timeframe": "1h",
                    "direction": "bullish",
                    "attachments": [],
                    "visibility": "public",
                },
                expect=[201, 403],
                captures={"post_id": "id"},
                tests=CREATE_POST_TESTS,
                cost=2,
                variants=[
                    Variant(
                        "422 Raw HTML and bad attachment",
                        422,
                        body={
                            "title": "Hello",
                            "body": "<script>alert(1)</script> [click](javascript:alert(1))",
                            "attachments": [
                                {
                                    "type": "backtest",
                                    "id": "00000000-0000-0000-0000-000000000000",
                                }
                            ],
                        },
                    )
                ],
            ),
            Req(
                "posts_get",
                "Get post",
                "GET",
                "/posts/:post_id",
                "404 when you may not see it (deleted, hidden, followers-only). `can_edit` tells "
                "the UI whether **Update post** is allowed.",
                path_vars={"post_id": ("{{post_id}}", "Post UUID")},
            ),
            Req(
                "posts_update",
                "Update post",
                "PATCH",
                "/posts/:post_id",
                "Any subset of the create fields. The author within **24 hours** of publishing, "
                "admins at any time (403 otherwise); `edited_at` is set.",
                path_vars={"post_id": ("{{post_id}}", "Post UUID")},
                body={"direction": "neutral", "visibility": "followers"},
            ),
            Req(
                "posts_like",
                "Like post",
                "POST",
                "/posts/:post_id/like",
                "Idempotent. The author gets one batched `post_liked` notification per post and "
                'day ("N people liked your post"). 409 on a post that is not published.',
                path_vars={"post_id": ("{{post_id}}", "Post UUID")},
            ),
            Req(
                "comments_create",
                "Add comment",
                "POST",
                "/posts/:post_id/comments",
                "1–2,000 characters, same Markdown rules as posts. The post's author is notified "
                "(`comment_reply`). 409 on a post that is not published.",
                path_vars={"post_id": ("{{post_id}}", "Post UUID")},
                body={"body": "What about ETH? Same structure on the 4h."},
                expect=[201],
                captures={"comment_id": "id"},
                cost=2,
            ),
            Req(
                "comments_reply",
                "Reply to comment",
                "POST",
                "/posts/:post_id/comments",
                "With `parent_id`: a reply. A reply to a reply is stored under the top-level "
                "comment, and the author of the comment you answered is notified.",
                path_vars={"post_id": ("{{post_id}}", "Post UUID")},
                body={
                    "body": "Similar, but weaker: waiting for 2.6k.",
                    "parent_id": "{{comment_id}}",
                },
                expect=[201],
                captures={"reply_id": "id"},
                cost=2,
            ),
            Req(
                "comments_list",
                "List comments",
                "GET",
                "/posts/:post_id/comments",
                "Top-level comments **oldest first**, each with its first 20 replies inline "
                "(`replies_count`, `more_replies`). With `parent_id`: all replies of one "
                "top-level comment, paginated. Deleted comments keep a placeholder (`author` and "
                "`body` null); hidden ones show `body: null` to everyone but their author.",
                path_vars={"post_id": ("{{post_id}}", "Post UUID")},
                query=PAGE_QUERY,
                optional_query=[("parent_id", "{{comment_id}}", "Replies of this comment")],
            ),
            Req(
                "comments_update",
                "Update comment",
                "PATCH",
                "/comments/:comment_id",
                "The author, at any time while it is published; `edited_at` is set.",
                path_vars={"comment_id": ("{{reply_id}}", "Comment UUID")},
                body={"body": "Similar, but weaker: waiting for a close above 2.6k."},
            ),
            Req(
                "comments_delete",
                "Delete comment",
                "DELETE",
                "/comments/:comment_id",
                "The author or an admin. Soft delete: the thread keeps a placeholder.",
                path_vars={"comment_id": ("{{reply_id}}", "Comment UUID")},
                expect=[204],
            ),
            Req(
                "posts_unlike",
                "Unlike post",
                "DELETE",
                "/posts/:post_id/like",
                "Idempotent.",
                path_vars={"post_id": ("{{post_id}}", "Post UUID")},
            ),
            Req(
                "posts_delete",
                "Delete post",
                "DELETE",
                "/posts/:post_id",
                "The author or an admin. Soft delete: 404 for everyone afterwards (admins still "
                'get it by id with `status: "deleted"`). Does not refill the daily limit.',
                path_vars={"post_id": ("{{post_id}}", "Post UUID")},
                expect=[204],
            ),
            Req(
                "users_follow",
                "Follow user",
                "POST",
                "/users/:user_id/follow",
                "Idempotent. Only analysts and experts can be followed: 400 for yourself or "
                "another role, 404 for an unknown user. Their new posts then appear with "
                "`scope=following` and notify you (`new_post`).",
                path_vars={"user_id": ("{{author_user_id}}", "User UUID (analyst or expert)")},
                pre=SKIP_NO_AUTHOR,
            ),
            Req(
                "users_profile",
                "Public profile",
                "GET",
                "/users/:user_id/profile",
                "Display name, role, counters, `followable` / `is_following`, up to 5 recent "
                "posts you may see and the user's public strategies. No e-mail. 404 for unknown "
                "or deactivated users.",
                path_vars={"user_id": ("{{author_user_id}}", "User UUID")},
                pre=SKIP_NO_AUTHOR,
            ),
            Req(
                "me_following",
                "Who I follow",
                "GET",
                "/me/following",
                "Newest first: `{user: {id, display_name, role}, since}`.",
                query=PAGE_QUERY,
            ),
            Req(
                "me_followers",
                "My followers",
                "GET",
                "/me/followers",
                "The people following you, newest first.",
                query=PAGE_QUERY,
            ),
            Req(
                "users_unfollow",
                "Unfollow user",
                "DELETE",
                "/users/:user_id/follow",
                "Idempotent.",
                path_vars={"user_id": ("{{author_user_id}}", "User UUID")},
                pre=SKIP_NO_AUTHOR,
            ),
            Req(
                "reports_create",
                "Report post",
                "POST",
                "/reports",
                "Report a post, comment or chat message (`target_type` `post` | `comment` | "
                "`message`) to the moderators. "
                "201 for a new report, 200 with the existing one if you already reported it. "
                "400 for your own content, 404 for content you cannot see. Stored as "
                "`report_id` for **Admin → News & Moderation**.",
                body={
                    "target_type": "post",
                    "target_id": "{{other_post_id}}",
                    "reason": "Promises guaranteed profits (pump and dump).",
                },
                expect=[201, 200],
                captures={"report_id": "id"},
                pre=SKIP_NO_OTHER_POST,
                cost=2,
            ),
        ],
    ),
    Folder(
        "Price Alerts",
        "Alerts on a price, checked on every **closed 1m candle** about 10 s after the minute "
        "(`docs/price-alerts.md`). A fired alert is a `price_alert` notification (in-app, push, "
        "Telegram by default) and a `price_alert` WebSocket message. JWT only.\n\n"
        "| `condition` | `value` | fires when |\n|---|---|---|\n"
        "| `above` | price | the bar's high ≥ value |\n"
        "| `below` | price | the bar's low ≤ value |\n"
        "| `crosses_above` | price | previous close < value ≤ close |\n"
        "| `crosses_below` | price | previous close > value ≥ close |\n"
        "| `change_pct` | percent (0–100] + `window_minutes` | \\|close / close `window_minutes` ago − 1\\| ≥ value % |\n\n"
        "`repeat`: `once` (then switched off) or `every` (after `cooldown_minutes`, default 60). "
        "Active alerts: trader 20, analyst / expert / admin 100.",
        [
            Req(
                "alerts_create",
                "Create price alert",
                "POST",
                "/me/price-alerts",
                "201 with `current_price` (close of the latest 1m candle) and "
                "`would_trigger_now` (an above/below alert the latest price already meets: it "
                "is created anyway and fires on the next closed minute). 400 over your limit, "
                "404 for an unknown instrument. `expires_at` (optional, future) switches it "
                "off.",
                body={
                    "instrument_id": "{{instrument_id}}",
                    "condition": "crosses_above",
                    "value": 70000,
                    "repeat": "every",
                    "cooldown_minutes": 120,
                    "note": "breakout above 70k",
                    "expires_at": "2027-12-31T00:00:00Z",
                },
                expect=[201],
                captures={"price_alert_id": "id"},
                variants=[
                    Variant(
                        "422 Invalid combination",
                        422,
                        body={
                            "instrument_id": "{{instrument_id}}",
                            "condition": "change_pct",
                            "value": 2.5,
                            "repeat": "once",
                            "cooldown_minutes": 30,
                        },
                    )
                ],
            ),
            Req(
                "alerts_list",
                "List price alerts",
                "GET",
                "/me/price-alerts",
                "Newest first, with `trigger_count` and `last_triggered_at`.",
                query=[("limit", "50", "1–100"), ("offset", "0", "")],
                optional_query=[
                    ("instrument_id", "{{instrument_id}}", ""),
                    ("is_active", "true", ""),
                ],
            ),
            Req(
                "alerts_update",
                "Update price alert",
                "PATCH",
                "/me/price-alerts/:alert_id",
                'Any field; the combination is checked again as a whole. `{"is_active": '
                "false}` pauses an alert (it no longer counts against the limit); switching to "
                "`change_pct` needs `window_minutes`.",
                path_vars={"alert_id": ("{{price_alert_id}}", "Price alert UUID")},
                body={
                    "condition": "change_pct",
                    "value": 2.5,
                    "window_minutes": 15,
                    "note": "volatility",
                },
                variants=[
                    Variant(
                        "404 Price alert not found",
                        404,
                        path_vars={"alert_id": "00000000-0000-0000-0000-000000000000"},
                    )
                ],
            ),
            Req(
                "alerts_history",
                "Price alert history",
                "GET",
                "/me/price-alerts/history",
                "The last triggers with the price that met the condition and the bar, newest "
                "first (from your notifications: kept 90 days after reading, 180 unread).",
                query=[("limit", "50", "1–100"), ("offset", "0", "")],
                optional_query=[("alert_id", "{{price_alert_id}}", "One alert only")],
            ),
            Req(
                "alerts_delete",
                "Delete price alert",
                "DELETE",
                "/me/price-alerts/:alert_id",
                "404 if it is not yours.",
                path_vars={"alert_id": ("{{price_alert_id}}", "Price alert UUID")},
                expect=[204],
            ),
        ],
    ),
    Folder(
        "Experts & Subscriptions",
        "The experts directory and buying a subscription (`docs/subscriptions.md`). **Payments "
        "are demo only: no real money.** The flow still works like a real provider: a hosted "
        "checkout page, a signed webhook, renewals, failed payments, cancellation, refunds and "
        "invoices.\n\n"
        "A subscription unlocks the perks of its plan: `premium_posts` (posts with visibility "
        "`subscribers`; others get a teaser with `locked: true`), `chat` (the **Chat** folder) and "
        "`signals_feed`. Statuses: `trialing` and `active` (access), `past_due` (access during a "
        "3-day grace period), `canceled` and `expired` (no access).\n\n"
        "| Test card | Result |\n|---|---|\n"
        "| `4242 4242 4242 4242` | succeeds, renewals succeed |\n"
        "| `4000 0000 0000 0002` | declined at checkout |\n"
        "| `4000 0000 0000 9995` | succeeds now, renewals fail |\n\n"
        "Any future expiry (MM/YY) and any 3-digit CVC. In the runner the payment requests are "
        "skipped when you already have a live subscription with the expert (409).",
        [
            Req(
                "experts_list",
                "Experts directory",
                "GET",
                "/experts",
                "Listed experts, most subscribers first, with their cheapest plan and "
                "`is_subscribed`. `rating` is a placeholder (null). No e-mails. Stores the first "
                "other expert as `expert_id`.",
                query=[("limit", "20", "1–50"), ("offset", "0", "")],
                optional_query=[
                    (
                        "market",
                        "crypto",
                        "crypto | forex | gold | commodities | stocks | indices",
                    ),
                    ("language", "ar", "ar | en | fr | de | es | tr"),
                    ("q", "gold", "Name or headline"),
                ],
                tests=EXPERTS_TESTS,
            ),
            Req(
                "experts_get",
                "Expert profile",
                "GET",
                "/experts/:expert_id",
                "The card plus `bio`, the active `plans`, **your `entitlements`** "
                "(`premium_posts`, `chat`, `signals_feed`) and 5 recent posts (subscriber posts "
                "as teasers unless you are entitled). Unlisted experts are still reachable by "
                "id. Stores the first plan as `plan_id`.",
                path_vars={"expert_id": ("{{expert_id}}", "Expert (user) UUID")},
                captures={"plan_id": "plans.0.id"},
                tests=EXPERT_TESTS,
                pre=SKIP_NO_EXPERT,
            ),
            Req(
                "subs_checkout",
                "Start checkout",
                "POST",
                "/subscriptions/checkout",
                "Opens a checkout (valid 30 minutes): send the user to `checkout_url` (browser "
                "or WebView). `checkout_url` is absolute when the server sets "
                "`PUBLIC_BASE_URL`, otherwise prefix the path with the API origin. "
                "`return_url` (optional) must be on an allowed origin (`CORS_ORIGINS`), else "
                "422. The result comes back through the payment webhook: follow it with **My "
                "subscriptions** (and the `subscription_started` notification).\n\n"
                "404 unknown or inactive plan, 400 your own plan, 409 you already have a live "
                "subscription with this expert.",
                body={"plan_id": "{{plan_id}}"},
                expect=[201, 409],
                captures={"checkout_id": "checkout_id"},
                tests=CHECKOUT_TESTS,
                pre=SKIP_NO_PLAN,
                variants=[
                    Variant(
                        "422 Return URL not allowed",
                        422,
                        body={
                            "plan_id": "{{plan_id}}",
                            "return_url": "https://evil.example/x",
                        },
                    )
                ],
            ),
            Req(
                "pay_page",
                "Demo payment page",
                "GET",
                "/pay/demo/:checkout_id",
                "The demo provider's hosted payment page (HTML, no login), titled **\"Demo "
                'payment — no real money"**: the plan, the amount due today (0.00 during a '
                "trial), a card form and the test cards. 409 page for a completed, declined or "
                "expired checkout. Open it in a browser to see it as users do.",
                auth="none",
                path_vars={"checkout_id": ("{{checkout_id}}", "Checkout UUID")},
            ),
            Req(
                "pay_confirm",
                "Pay with a test card",
                "POST",
                "/pay/demo/:checkout_id/confirm",
                "The form of the payment page (no login). The demo provider charges the test "
                "card, sends the signed `checkout.completed` / `checkout.failed` event to the "
                "payment webhook handler, then redirects (**303**) to `return_url` (or the "
                "result page) with `?checkout_id=…&status=succeeded|failed`. Postman follows the "
                "redirect, so it shows the result page (200). Unknown cards or bad fields "
                "re-show the form (422). Only the brand and last 4 digits are kept.",
                auth="none",
                path_vars={"checkout_id": ("{{checkout_id}}", "Checkout UUID")},
                form=[
                    (
                        "card_number",
                        "4242 4242 4242 4242",
                        "A test card (see the folder)",
                    ),
                    ("expiry", "12/30", "MM/YY in the future"),
                    ("cvc", "123", "3 or 4 digits"),
                    ("name", "Sara Trader", "Name on the card"),
                ],
                expect=[303, 200],
            ),
            Req(
                "pay_done",
                "Payment result page",
                "GET",
                "/pay/demo/:checkout_id/done",
                "The default return page (HTML, no login) when the checkout had no "
                '`return_url`: "Payment successful" with the period end, or the failure '
                "reason.",
                auth="none",
                path_vars={"checkout_id": ("{{checkout_id}}", "Checkout UUID")},
            ),
            Req(
                "subs_mine",
                "My subscriptions",
                "GET",
                "/me/subscriptions",
                "Newest first: `status`, the price bought at, the period, `next_charge_at`, "
                "`grace_ends_at`, `payment_method` (brand, last 4, test behavior), the copied "
                "`perks` and the `invoices` (`INV-2026-000123`, kind `trial` | `initial` | "
                "`renewal`, status `open` | `paid` | `failed` | `refunded` | `void`). Stores the "
                "subscription to `expert_id` as `subscription_id` and its first invoice as "
                "`invoice_id`.",
                tests=MY_SUBS_TESTS,
            ),
            Req(
                "experts_signals",
                "Expert signals feed",
                "GET",
                "/experts/:expert_id/signals",
                "Signals of the expert's public custom strategies that the expert runs, newest "
                "first, with the expert's trade plan. Subscribers with the `signals_feed` perk "
                "(403 otherwise).",
                path_vars={"expert_id": ("{{expert_id}}", "Expert (user) UUID")},
                query=[("limit", "50", "1–100"), ("offset", "0", "")],
                expect=[200, 403],
                pre=SKIP_NO_EXPERT,
            ),
            Req(
                "subs_cancel",
                "Cancel subscription",
                "POST",
                "/me/subscriptions/:subscription_id/cancel",
                "At period end: access continues until `current_period_end` "
                "(`cancel_at_period_end: true`), then the status becomes `canceled`. 409 if it "
                "already ended.",
                path_vars={"subscription_id": ("{{subscription_id}}", "Subscription UUID")},
                pre=SKIP_NO_SUBSCRIPTION,
            ),
            Req(
                "subs_resume",
                "Resume subscription",
                "POST",
                "/me/subscriptions/:subscription_id/resume",
                "Undo the cancel before the period ends: it renews again.",
                path_vars={"subscription_id": ("{{subscription_id}}", "Subscription UUID")},
                pre=SKIP_NO_SUBSCRIPTION,
            ),
            Req(
                "pay_webhook",
                "Payment webhook (provider)",
                "POST",
                "/payments/webhook/:provider",
                "Called by the payment provider, not by the apps (no login). Events: "
                "`checkout.completed`, `checkout.failed`, `invoice.paid`, "
                "`invoice.payment_failed`. Every event is signed with HMAC-SHA256: "
                '`Demo-Signature: t=<unix>,v1=<hex(hmac(secret, "<t>." + body))>`, 5-minute '
                'tolerance; a repeated event id answers `{"status": "duplicate"}`. Sent here '
                "with a wrong signature, so it shows the 401.",
                auth="none",
                path_vars={"provider": ("demo", "Payment provider (demo)")},
                headers=[("Demo-Signature", "t=1792170000,v1=0000", "HMAC signature")],
                body={
                    "id": "evt_demo_1",
                    "type": "invoice.paid",
                    "data": {"invoice_id": "00000000-0000-0000-0000-000000000000"},
                },
                expect=[401],
            ),
        ],
    ),
    Folder(
        "Chat",
        "One conversation per expert and subscriber (`docs/chat.md`). REST for sending and "
        "history; live delivery on the WebSocket topic `chat:<conversation id>` "
        "(`chat_message`, `chat_message_updated`, `chat_read`, `chat_typing`; see the "
        "**Realtime** folder).\n\n"
        "- A subscriber with the `chat` perk opens the conversation and writes; the expert can "
        "always reply. When the subscription ends the conversation is read-only for the "
        "subscriber.\n"
        "- Either side can block; only the side that blocked unblocks. Admins read every "
        "conversation but do not write.\n"
        "- The recipient gets a `chat_message` notification only while none of their "
        "connections is subscribed to the conversation (at most one external notification per "
        "conversation per 5 minutes).\n\n"
        "Limits: 30 messages per minute, 2,000 per day (429).",
        [
            Req(
                "chat_open",
                "Open conversation",
                "POST",
                "/conversations",
                "Opens (201) or returns (200) your conversation with an expert. 403 without a "
                "subscription with the `chat` perk or when the expert disabled chat; 404 unknown "
                "expert.",
                body={"expert_id": "{{expert_id}}"},
                expect=[201, 200],
                captures={"conversation_id": "id"},
                tests=OPEN_CONVERSATION_TESTS,
                pre=SKIP_NO_EXPERT,
            ),
            Req(
                "chat_send",
                "Send message",
                "POST",
                "/conversations/:conversation_id/messages",
                "1–4,000 characters (plain text or light Markdown, raw HTML refused) and up to 5 "
                "`attachments` (`signal`, `backtest`, `post`, `custom_strategy`). **Idempotent "
                "on `client_id`**: the app makes one UUID per message and keeps it until the "
                "server confirms; a retry answers 200 with the first message. Render the "
                "message at once (optimistic, keyed by `client_id`); the `chat_message` event "
                "confirms it on every device.\n\n"
                "403 read-only, blocked or admin; 429 over the limits.",
                path_vars={"conversation_id": ("{{conversation_id}}", "Conversation UUID")},
                body={
                    "body": "Hi! What is your stop for the BTC long you posted?",
                    "client_id": "{{chat_client_id}}",
                    "attachments": [],
                },
                expect=[201, 200],
                captures={"message_id": "id"},
                pre=CHAT_CLIENT_ID_PRE,
                variants=[Variant("200 Retry with the same client_id", 200)],
            ),
            Req(
                "chat_history",
                "Message history",
                "GET",
                "/conversations/:conversation_id/messages",
                "Newest first. Pass `next_before` as `before` for older messages (`null` at the "
                "start). Deleted messages stay as tombstones (`deleted: true`, `body: null`); "
                "`client_id` is only returned to its sender.",
                path_vars={"conversation_id": ("{{conversation_id}}", "Conversation UUID")},
                query=[("limit", "50", "1–100")],
                optional_query=[("before", "{{message_id}}", "A message id (exclusive)")],
                pre=SKIP_NO_CONVERSATION,
            ),
            Req(
                "chat_edit",
                "Edit message",
                "PATCH",
                "/messages/:message_id",
                "The sender, within **15 minutes** (403 after); `edited_at` is set and the "
                "other side gets `chat_message_updated`.",
                path_vars={"message_id": ("{{message_id}}", "Message UUID")},
                body={"body": "Hi! What is your stop for the BTC long from this morning?"},
                pre=SKIP_NO_CONVERSATION,
            ),
            Req(
                "chat_read",
                "Mark as read",
                "POST",
                "/conversations/:conversation_id/read",
                "Moves your read marker to a message (or to now without a body); markers only "
                'move forward. The other side gets `chat_read` ("seen" ticks).',
                path_vars={"conversation_id": ("{{conversation_id}}", "Conversation UUID")},
                body={"message_id": "{{message_id}}"},
                pre=SKIP_NO_CONVERSATION,
            ),
            Req(
                "chat_get",
                "Get conversation",
                "GET",
                "/conversations/:conversation_id",
                "`other` (the other participant), `my_role`, `can_send` and "
                "`read_only_reason`, `unread`, `last_message`, `other_last_read_at`. 404 if you "
                "are not a participant.",
                path_vars={"conversation_id": ("{{conversation_id}}", "Conversation UUID")},
                pre=SKIP_NO_CONVERSATION,
            ),
            Req(
                "chat_list",
                "List conversations",
                "GET",
                "/conversations",
                "Yours, as subscriber or expert, most recent first.",
            ),
            Req(
                "chat_block",
                "Block conversation",
                "POST",
                "/conversations/:conversation_id/block",
                "Either side: no new messages from anyone until the side that blocked unblocks.",
                path_vars={"conversation_id": ("{{conversation_id}}", "Conversation UUID")},
                pre=SKIP_NO_CONVERSATION,
            ),
            Req(
                "chat_unblock",
                "Unblock conversation",
                "POST",
                "/conversations/:conversation_id/unblock",
                "Only the side that blocked (or an admin).",
                path_vars={"conversation_id": ("{{conversation_id}}", "Conversation UUID")},
                pre=SKIP_NO_CONVERSATION,
            ),
            Req(
                "chat_delete",
                "Delete message",
                "DELETE",
                "/messages/:message_id",
                "The sender. A tombstone stays in the history and the other side gets "
                "`chat_message_updated`. Messages can also be reported (`POST /reports` with "
                '`target_type: "message"`).',
                path_vars={"message_id": ("{{message_id}}", "Message UUID")},
                expect=[204],
                pre=SKIP_NO_CONVERSATION,
            ),
        ],
    ),
    Folder(
        "Expert Studio",
        "The expert side (role `expert`; other roles get 403 and the runner skips this "
        "folder): the public profile, up to 3 active plans and the earnings.\n\n"
        "A new price never changes a running period: a subscription keeps the price it was "
        "bought at and moves to the plan's current price and perks at its next renewal. Plans "
        "are never deleted, only deactivated.",
        [
            Req(
                "expert_profile_put",
                "Update my expert profile",
                "PUT",
                "/me/expert-profile",
                "Created on the first PUT. `bio` is Markdown (≤ 5,000, same input rules as "
                "posts); `markets`: crypto, forex, gold, commodities, stocks, indices; "
                "`languages`: ar, en, fr, de, es, tr. `is_listed: false` hides you from the "
                "directory (still reachable by id).",
                body={
                    "headline": "Swing trader · BTC & gold · 8 years",
                    "bio": "I trade **4h–1d** structure with strict risk: 1% per trade.\n\n"
                    "- Weekly outlook every Sunday\n- Live trade plans in the chat",
                    "markets": ["crypto", "gold"],
                    "languages": ["ar", "en"],
                    "chat_enabled": True,
                    "response_time_hint": "usually within a few hours",
                    "is_listed": True,
                },
                expect=[200, 403],
                tests=EXPERT_PROFILE_TESTS,
            ),
            Req(
                "expert_profile_get",
                "Get my expert profile",
                "GET",
                "/me/expert-profile",
                "404 until created.",
            ),
            Req(
                "plans_create",
                "Create plan",
                "POST",
                "/me/plans",
                "`price` as a decimal string (≤ 100,000), `currency` USD | EUR, `interval` month "
                "| year, `trial_days` 0–30, `perks` (`premium_posts`, `chat`, `signals_feed`). "
                "**At most 3 active plans** (409).",
                body={
                    "name": "Pro monthly",
                    "description": "Premium analyses, chat and my live signals.",
                    "price": "29.00",
                    "currency": "USD",
                    "interval": "month",
                    "trial_days": 7,
                    "perks": {
                        "premium_posts": True,
                        "chat": True,
                        "signals_feed": True,
                    },
                },
                expect=[201],
                captures={"my_plan_id": "id"},
            ),
            Req(
                "plans_list",
                "List my plans",
                "GET",
                "/me/plans",
                "Active and inactive.",
            ),
            Req(
                "plans_update",
                "Update plan",
                "PATCH",
                "/me/plans/:plan_id",
                "Any field except `currency` and `interval`. A new price applies to new "
                "subscriptions and to each subscription's next renewal.",
                path_vars={"plan_id": ("{{my_plan_id}}", "Plan UUID")},
                body={"price": "24.00", "trial_days": 3},
            ),
            Req(
                "experts_earnings",
                "My earnings",
                "GET",
                "/me/earnings",
                "Active subscribers by status, **MRR** (paying subscriptions; yearly prices / 12; "
                "trials excluded), 30-day churn, the last 12 months (gross, platform fee 20 %, "
                "net, refunded) and recent invoices. Subscribers appear by display name only.",
            ),
            Req(
                "plans_deactivate",
                "Deactivate plan",
                "DELETE",
                "/me/plans/:plan_id",
                "Deactivates the plan (it is never deleted). Existing subscriptions keep "
                "renewing at their price.",
                path_vars={"plan_id": ("{{my_plan_id}}", "Plan UUID")},
                expect=[204],
            ),
        ],
    ),
    Folder(
        "Notifications",
        "The notification inbox, per-event / per-channel preferences, the Telegram link and push "
        "devices (`docs/notifications.md`). JWT only: API keys get 403.\n\n"
        "| `type` | Produced by |\n|---|---|\n"
        "| `signal` | live signal engine, for your activations with `notify: true` (carries your trade plan) |\n"
        "| `backtest_completed` / `backtest_failed` | backtest worker |\n"
        "| `security` | sign-in from a new IP / device, password changed, API key created or revoked, account locked |\n"
        "| `system` | admin broadcast, test messages |\n"
        "| `new_post` / `comment_reply` | someone you follow published / a comment on your post or a reply to yours |\n"
        '| `post_liked` | "N people liked your post": one row per post and day, **in-app only** |\n'
        "| `content_hidden` | moderation hid your post or comment |\n"
        "| `price_alert` | one of your price alerts fired |\n"
        "| `chat_message` | a chat message while you are not looking at the conversation (one external notification per conversation per 5 min) |\n"
        "| `subscription_started` / `_renewed` / `_payment_failed` / `_canceled` | your subscription to an expert |\n"
        "| `new_subscriber` | someone subscribed to your plan (experts) |\n\n"
        "Every event is stored in the inbox and pushed on the WebSocket as `notification`. "
        "Telegram, email and push follow your preferences: event on for the channel → signal "
        "filters → quiet hours → hourly cap (held deliveries go out later as one digest). A "
        "channel the server has no settings for reports `enabled_on_server: false` and its "
        "deliveries are `skipped`.\n\n"
        "By the time the Collection Runner gets here, the inbox already holds real events from "
        "the folders before (password changed, API key created / revoked, backtest completed).\n\n"
        "The Telegram webhook (`POST /telegram/webhook/{secret}`) is called by Telegram itself, "
        "only in `TELEGRAM_MODE=webhook` behind HTTPS, and is not a client endpoint: the server "
        "uses long polling for now.",
        [
            Req(
                "notif_prefs_get",
                "Get notification preferences",
                "GET",
                "/me/notification-preferences",
                "Created with the defaults on first read: Telegram for signals and system "
                "messages, push for signals, backtests and system messages, email for security "
                "events; no quiet hours, 30 per hour per channel, Arabic.",
            ),
            Req(
                "notif_prefs_put",
                "Update notification preferences",
                "PUT",
                "/me/notification-preferences",
                "The whole document: a missing field takes its default, and a missing matrix "
                "entry keeps the default for that event and channel. `quiet_hours` is local "
                "time in `tz` (`23:00`–`07:00` spans midnight); deliveries held by quiet hours "
                "or by `max_per_hour` are sent later as one digest. `critical` events ignore "
                "both.\n\n"
                "A 422 lists every error with its path in `loc`. **Reset preferences** at the end "
                "of the folder puts the defaults back.",
                body={
                    "matrix": {
                        "signal": {"telegram": True, "email": True, "push": True},
                        "backtest_completed": {"telegram": True},
                    },
                    "min_signal_strength": 0.6,
                    "only_valid_plans": True,
                    "quiet_hours": {
                        "start": "23:00",
                        "end": "07:00",
                        "tz": "Asia/Damascus",
                    },
                    "language": "en",
                    "max_per_hour": {"telegram": 20},
                },
                variants=[
                    Variant(
                        "422 Invalid quiet hours",
                        422,
                        body={
                            "quiet_hours": {
                                "start": "25:00",
                                "end": "07:00",
                                "tz": "Mars/Olympus",
                            },
                            "max_per_hour": {"push": 0},
                        },
                    )
                ],
            ),
            Req(
                "notif_channels",
                "Notification channels",
                "GET",
                "/me/notifications/channels",
                "What each channel can do for you: configured on this server "
                "(`enabled_on_server`), the linked Telegram account, the email address, the "
                "number of push devices. Show a channel with `enabled_on_server: false` as "
                '"not available".',
            ),
            Req(
                "notif_test",
                "Send test notification",
                "POST",
                "/me/notifications/test",
                "A `system` test message on one channel (`in_app`, `telegram`, `email`, "
                "`push`), ignoring preferences, quiet hours and caps. A channel the server has "
                "no settings for gives a `skipped` delivery; Telegram without a linked chat or "
                "push without a device answers 409. The new notification is stored as "
                "`notification_id`.",
                body={"channel": "in_app"},
                expect=[201],
                captures={"notification_id": "notification_id"},
                cost=5,
                variants=[
                    Variant("409 Telegram not linked", 409, body={"channel": "telegram"}),
                    Variant("422 Unknown channel", 422, body={"channel": "sms"}),
                ],
            ),
            Req(
                "notif_list",
                "List notifications",
                "GET",
                "/me/notifications",
                "Your inbox, newest first. `title` and `body` are rendered in your language when "
                "the event is stored; `data` carries the event's details (the signal and your "
                "trade plan, the backtest metrics, the security event).\n\n"
                "Read notifications are deleted after 90 days, unread ones after 180.",
                query=PAGE_QUERY,
                optional_query=[
                    (
                        "type",
                        "security",
                        "signal | backtest_completed | backtest_failed | security | system",
                    ),
                    ("unread", "true", "true = unread only, false = read only"),
                ],
            ),
            Req(
                "notif_unread_count",
                "Unread count",
                "GET",
                "/me/notifications/unread-count",
                "For the bell badge. Live updates arrive on the WebSocket as `notification` "
                "messages.",
            ),
            Req(
                "notif_read",
                "Mark notification as read",
                "POST",
                "/me/notifications/:notification_id/read",
                "Idempotent. Another user's notification answers 404. Push messages carry "
                "`notification_id` in their `data`, so the app can mark them read.",
                path_vars={"notification_id": ("{{notification_id}}", "Notification UUID")},
                expect=[204],
                variants=[
                    Variant(
                        "404 Notification not found",
                        404,
                        path_vars={"notification_id": "00000000-0000-0000-0000-000000000000"},
                    )
                ],
            ),
            Req(
                "notif_read_all",
                "Mark all as read",
                "POST",
                "/me/notifications/read-all",
                "Every unread notification of yours.",
                expect=[204],
            ),
            Req(
                "notif_telegram_link",
                "Get Telegram link code",
                "POST",
                "/me/notifications/telegram/link",
                "A one-time code, valid for 10 minutes. Open `deep_link` in Telegram (or send "
                "`/start <code>` to the bot): the bot links that chat to your account, and "
                "**Notification channels** then shows `telegram.linked: true`. `/stop` in the "
                "bot or **Unlink Telegram** removes the link.\n\n"
                "409 when the server has no bot configured.",
                expect=[200, 409],
            ),
            Req(
                "notif_telegram_unlink",
                "Unlink Telegram",
                "DELETE",
                "/me/notifications/telegram",
                "Idempotent (204 also when nothing was linked). Blocking the bot unlinks "
                "automatically.",
                expect=[204],
            ),
            Req(
                "notif_device_register",
                "Register push device",
                "POST",
                "/me/devices",
                "Registers an FCM registration token for push (Flutter app). Call it on every "
                "app start and whenever FCM rotates the token: **201** the first time, **200** "
                "for a known token (refreshed, and moved to this account if another one had "
                "it). The response never contains the token, only `token_suffix`. "
                "`platform`: `android`, `ios` or `web`.\n\n"
                "Tokens FCM reports as invalid are deleted by the server.",
                body={
                    "token": "postman-demo-fcm-token-{{$timestamp}}",
                    "platform": "android",
                    "app_version": "1.0.0",
                    "locale": "ar",
                },
                expect=[201, 200],
                captures={"device_id": "id"},
                variants=[
                    Variant(
                        "422 Unknown platform",
                        422,
                        body={"token": "postman-demo-fcm-token", "platform": "windows"},
                    )
                ],
            ),
            Req(
                "notif_devices",
                "List push devices",
                "GET",
                "/me/devices",
                "Your registered devices, oldest first.",
            ),
            Req(
                "notif_device_delete",
                "Delete push device",
                "DELETE",
                "/me/devices/:device_id",
                "Call it on sign-out so the device stops receiving your notifications.",
                path_vars={"device_id": ("{{device_id}}", "Device UUID")},
                expect=[204],
                variants=[
                    Variant(
                        "404 Device not found",
                        404,
                        path_vars={"device_id": "00000000-0000-0000-0000-000000000000"},
                    )
                ],
            ),
            Req(
                "notif_delete",
                "Delete notification",
                "DELETE",
                "/me/notifications/:notification_id",
                "Removes it from your inbox (here: the test notification sent above).",
                path_vars={"notification_id": ("{{notification_id}}", "Notification UUID")},
                expect=[204],
            ),
            Req(
                "notif_prefs_reset",
                "Reset preferences",
                "PUT",
                "/me/notification-preferences",
                "An empty document puts every field back to its default (it undoes **Update "
                "notification preferences**).",
                body={},
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
                                body={
                                    "symbol": "AAPL",
                                    "source": "nasdaq",
                                    "market": "stock",
                                },
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
                        path_vars={
                            "instrument_id": (
                                "{{admin_instrument_id}}",
                                "Instrument UUID",
                            )
                        },
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
                        path_vars={
                            "instrument_id": (
                                "{{admin_instrument_id}}",
                                "Instrument UUID",
                            )
                        },
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
                "Every user's keys, rate-limit monitoring and the system status.",
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
                    Req(
                        "admin_system_status",
                        "System status",
                        "GET",
                        "/admin/system/status",
                        "The operations view in one call: version and uptime, database (size, "
                        "connections, migration, slowest queries when `pg_stat_statements` is "
                        "installed), Redis, Celery (queue lengths, live workers, last run of each "
                        "scheduled task), market data freshness per active instrument, WebSocket "
                        "clients of this API process, notification channels, unhandled errors in "
                        "the last hour and the last daily summary.",
                        auth="admin",
                    ),
                ],
            ),
            Folder(
                "News & Moderation",
                "News sources and the report queue of the community.",
                [
                    Req(
                        "admin_news_source",
                        "Update news source",
                        "PATCH",
                        "/admin/news/sources/:source_id",
                        "Enable or disable a source and change how often an RSS feed is fetched "
                        "(5–1440 minutes). A disabled RSS source is not fetched; a disabled `api` "
                        "source refuses ingested items. Existing articles stay listed. Here: the "
                        "first source of **News → List news sources**, kept active at the default "
                        "15 minutes.",
                        auth="admin",
                        path_vars={"source_id": ("{{news_source_id}}", "News source UUID")},
                        body={"is_active": True, "fetch_interval_minutes": 15},
                        variants=[
                            Variant(
                                "422 Interval out of range",
                                422,
                                body={"fetch_interval_minutes": 2},
                            )
                        ],
                    ),
                    Req(
                        "admin_reports",
                        "List reports",
                        "GET",
                        "/admin/reports",
                        "Newest first, with the reporter, an excerpt of the reported content and "
                        "the number of open reports on it.",
                        auth="admin",
                        query=[
                            ("status", "open", "open | resolved | all"),
                            ("limit", "50", "1–100"),
                            ("offset", "0", ""),
                        ],
                    ),
                    Req(
                        "admin_report_resolve",
                        "Resolve report",
                        "POST",
                        "/admin/reports/:report_id/resolve",
                        "`hide`: the post or comment disappears for everyone but its author, who "
                        "gets a `content_hidden` notification (with `note` as the reason); "
                        "`dismiss`: no change. Every open report on the same content is resolved. "
                        "409 if already resolved. Points at the report made in **Community → "
                        "Report post**, and dismisses it (409 on a repeated run: reporting the "
                        "same post again returns the first, resolved report).",
                        auth="admin",
                        path_vars={"report_id": ("{{report_id}}", "Report UUID")},
                        body={
                            "action": "dismiss",
                            "note": "Opinion, not a scam: no action.",
                        },
                        expect=[200, 409],
                        pre=SKIP_NO_REPORT,
                        variants=[
                            Variant(
                                "409 Already resolved",
                                409,
                            )
                        ],
                    ),
                ],
            ),
            Folder(
                "Subscriptions & Chat",
                "Subscriptions, demo payments and conversations.",
                [
                    Req(
                        "admin_subscriptions",
                        "List subscriptions",
                        "GET",
                        "/admin/subscriptions",
                        "Every subscription with subscriber, expert, status and period.",
                        auth="admin",
                        query=[("limit", "50", "1–100"), ("offset", "0", "")],
                        optional_query=[
                            (
                                "status",
                                "active",
                                "trialing | active | past_due | canceled | expired",
                            ),
                            ("expert_id", "{{expert_id}}", ""),
                            ("user_id", "{{user_id}}", ""),
                        ],
                    ),
                    Req(
                        "admin_payment_stats",
                        "Payment stats",
                        "GET",
                        "/admin/payments/stats",
                        "Invoices per status (count, amount), platform fees, subscriptions per "
                        "status and MRR across experts.",
                        auth="admin",
                    ),
                    Req(
                        "admin_fast_forward",
                        "Fast-forward subscription (demo)",
                        "POST",
                        "/admin/subscriptions/:subscription_id/fast-forward",
                        "**Demo only**, to show renewals without waiting a month: `period_end` "
                        "ends the current period now and processes it like the hourly task "
                        "(renewal, failed payment or cancel); `grace_end` ends the grace period "
                        "of a `past_due` one. 403 in production unless `PAYMENT_DEMO_TOOLS=true`. "
                        "Points at the subscription of **Experts & Subscriptions**.",
                        auth="admin",
                        path_vars={
                            "subscription_id": (
                                "{{subscription_id}}",
                                "Subscription UUID",
                            )
                        },
                        body={"to": "period_end"},
                        expect=[200, 403],
                        pre=SKIP_NO_SUBSCRIPTION,
                    ),
                    Req(
                        "admin_refund",
                        "Refund invoice",
                        "POST",
                        "/admin/invoices/:invoice_id/refund",
                        "A paid invoice becomes `refunded` and its subscription ends **now** "
                        "(`canceled`, the subscriber is notified). 409 if the invoice is not "
                        "paid. Points at the invoice of **Experts & Subscriptions → My "
                        "subscriptions**, so a later run can subscribe again.",
                        auth="admin",
                        path_vars={"invoice_id": ("{{invoice_id}}", "Invoice UUID")},
                        expect=[200, 409],
                        pre=SKIP_NO_INVOICE,
                        variants=[
                            Variant(
                                "404 Invoice not found",
                                404,
                                path_vars={"invoice_id": "00000000-0000-0000-0000-000000000000"},
                            )
                        ],
                    ),
                    Req(
                        "admin_conversations",
                        "List conversations",
                        "GET",
                        "/admin/conversations",
                        "E.g. `status=blocked`. Admins read any conversation through the normal "
                        "chat endpoints (read-only).",
                        auth="admin",
                        query=[("limit", "50", "1–100"), ("offset", "0", "")],
                        optional_query=[("status", "blocked", "open | closed | blocked")],
                    ),
                ],
            ),
            Folder(
                "Notifications",
                "Broadcasts and delivery monitoring.",
                [
                    Req(
                        "admin_notif_broadcast",
                        "Broadcast notification",
                        "POST",
                        "/admin/notifications/broadcast",
                        "A `system` notification to every active user, or only to `roles`, sent "
                        "in batches by a background task (202 with the number of recipients). "
                        "Sending the same `id` again creates nothing new.\n\n"
                        '> ⚠️ Here limited to `roles: ["admin"]`: remove `roles` to reach every '
                        "user.",
                        auth="admin",
                        body={
                            "title": "Scheduled maintenance",
                            "body": "The platform will be unavailable on Saturday from 02:00 to 02:30 (Damascus time).",
                            "severity": "warning",
                            "roles": ["admin"],
                        },
                        expect=[202],
                        variants=[
                            Variant(
                                "422 Empty title",
                                422,
                                body={"title": "", "body": "…", "severity": "urgent"},
                            )
                        ],
                    ),
                    Req(
                        "admin_notif_stats",
                        "Notification stats",
                        "GET",
                        "/admin/notifications/stats",
                        "Last 24 h: deliveries per channel and status, the circuit breaker of "
                        "each channel (open for 5 minutes after 5 consecutive failures), "
                        "deliveries held by quiet hours / caps / an open circuit, and the "
                        "length of the `notifications` queue.",
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
{"op": "subscribe",   "topic": "news"}                                    # every new article
{"op": "subscribe",   "topic": "news", "instrument_id": "{{instrument_id}}"}  # articles tagged with it
{"op": "subscribe",   "topic": "chat", "conversation_id": "{{conversation_id}}"}  # participants and admins
{"op": "typing",      "conversation_id": "{{conversation_id}}"}               # while the user types, ≤ 1 per 3 s
{"op": "ping"}
```

### Server → client

```json
{"type": "subscribed", "topic": "candles:<uuid>:1m"}
{"type": "snapshot",   "topic": "candles:<uuid>:1m", "candle": {"time": 1760000000, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}}
{"type": "candle",     "topic": "candles:<uuid>:1m", "instrument_id": "<uuid>", "timeframe": "1m", "candle": {"time": 1760000040, "open": 1.0, "high": 1.2, "low": 0.9, "close": 1.1, "volume": 3.5}, "sent_at": 1760000041234}
{"type": "signal",     "topic": "signals:<uuid>", "signal": {"strategy_key": "rsi_reversal", "side": "buy", "time": 1760000000, "price": 61234.5, "...": "..."}}
{"type": "news",       "topic": "news", "article": {"id": "<uuid>", "source": {"key": "coindesk_rss", "name": "CoinDesk"}, "title": "…", "url": "…", "sentiment": {"label": "positive", "score": 0.82}, "instruments": [{"instrument_id": "<uuid>", "symbol": "BTC/USDT", "relevance": 1.0}], "...": "..."}}
{"type": "chat_message",         "topic": "chat:<uuid>", "conversation_id": "<uuid>", "message": {"id": "<uuid>", "sender_id": "<uuid>", "body": "…", "attachments": [], "client_id": "<uuid>", "edited_at": null, "deleted": false, "created_at": "…"}}
{"type": "chat_message_updated", "topic": "chat:<uuid>", "conversation_id": "<uuid>", "message": {"...": "edited, or a tombstone with deleted: true"}}
{"type": "chat_read",            "topic": "chat:<uuid>", "conversation_id": "<uuid>", "user_id": "<uuid>", "read_at": "…"}
{"type": "chat_typing",          "topic": "chat:<uuid>", "conversation_id": "<uuid>", "user_id": "<uuid>"}
{"type": "pong"}
{"type": "heartbeat"}
{"type": "error", "code": "unknown_instrument", "message": "instrument not found"}
```

Pushed to the user's own topic without subscribing: `notification` (every inbox item, see \
the **Notifications** folder), `signal` (with `user_strategy_ids`, the user's trade `plan` and \
`plans` per activation) for activations with `notify: true`, `price_alert` (a fired alert: \
`alert_id`, `instrument`, `condition`, `value`, `price`, `bar_time`, `note`), \
`workspace_updated`, `backtest_progress`, `backtest_completed`, `backtest_failed`.

```json
{"type": "notification", "topic": "user:<uuid>", "sent_at": 1792156510640, "notification": {"id": "<uuid>", "type": "signal", "title": "SELL signal: BTC/USDT 1m", "body": "…", "data": {"...": "..."}, "severity": "info", "created_at": "…", "read_at": null}}
```

A participant subscribed to a `chat` topic counts as **present**: no `chat_message` \
notifications for that conversation. Ignore `chat_typing` with your own `user_id` and hide the \
indicator after ~5 s without a new one.

### Limits and close codes

| | |
|---|---|
| Subscriptions per connection | 50 (candles, signals, news and chat topics) |
| Server heartbeat | every 25 s; send `{"op":"ping"}` every ~30 s |
| Idle timeout | 75 s without a client frame → **1001** |
| Slow consumer | > 256 undelivered messages → **1013** |
| Bad / expired token or key | **4401** |
| Connections | 5 per identity, 20 new per minute per IP → **4429** |

Reconnect with exponential backoff (1 s → 30 s, with jitter) and send your `subscribe` ops \
again after every reconnect."""
