# ruff: noqa: E501  (embedded JavaScript, Markdown and sample payloads)
"""Build the Postman collection and environments from spec.py + examples.json.

    python docs/postman/tools/build_collection.py            # write docs/postman/*.json
    python docs/postman/tools/build_collection.py --check    # fail if an API route is missing

``--check`` imports the FastAPI app (run it where the backend's dependencies are installed) and
compares its routes with the requests in spec.py.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
POSTMAN = TOOLS.parent
REPO = POSTMAN.parent.parent
sys.path.insert(0, str(TOOLS))
from spec import FOLDERS, WEBSOCKET_DOC, Folder, Req  # noqa: E402

COLLECTION_FILE = POSTMAN / "AI-Trading-Platform.postman_collection.json"
ENV_DIR = POSTMAN / "environments"
NS = uuid.UUID("6f1c8f3e-2b7a-4c55-9d0e-7c3f1a2b9e10")  # stable ids across builds
SCHEMA = "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"


def uid(name: str) -> str:
    return str(uuid.uuid5(NS, name))


def lines(js: str) -> list[str]:
    return js.strip("\n").split("\n")


# --- collection-level scripts -----------------------------------------------------------------

PRE_REQUEST = r"""/**
 * Auto-authentication. Keeps {{access_token}} (user) and {{admin_access_token}} (admin, for
 * /admin/* requests) valid: reuses the token until it expires, then refreshes it with the
 * refresh token, then logs in with user_email/user_password (admin_email/admin_password).
 * /ingest/* requests (the news ingestion API, admins only) use the admin token too.
 * Skipped for /health, the public /auth/* endpoints and requests sent with an X-API-Key.
 */
const path = pm.request.url.getPath();
const publicPath = /\/health(\/(ready|live|data))?$|\/auth\/(register|login|token|refresh)$/.test(path);
const withApiKey = pm.request.headers.has("X-API-Key");
const store = pm.environment.name ? pm.environment : pm.collectionVariables;

if (!publicPath && !withApiKey && pm.variables.get("auto_auth") !== "false") {
    const admin = /(^|\/)(admin|ingest)\//.test(path); // ingestion: news:write = an admin
    ensureToken(admin ? "admin_" : "", admin ? "admin_email" : "user_email",
        admin ? "admin_password" : "user_password");
}

function saveTokens(prefix, body) {
    store.set(prefix + "access_token", body.access_token);
    store.set(prefix + "refresh_token", body.refresh_token);
    // 30 s of margin so a token never expires on the way to the server
    store.set(prefix + "access_token_expires_at", String(Date.now() + (body.expires_in - 30) * 1000));
}

function ensureToken(prefix, emailVar, passwordVar) {
    const token = pm.variables.get(prefix + "access_token");
    const expiresAt = Number(pm.variables.get(prefix + "access_token_expires_at") || 0);
    if (token && Date.now() < expiresAt) return;

    const apiUrl = pm.variables.replaceIn("{{api_url}}");
    // POST that waits and retries (up to 3 times) when the auth endpoints are rate limited
    const post = (endpoint, body, callback, attempt = 0) => pm.sendRequest({
        url: apiUrl + endpoint,
        method: "POST",
        header: { "Content-Type": "application/json" },
        body: { mode: "raw", raw: JSON.stringify(body) },
    }, (err, res) => {
        const wait = !err && res.code === 429 ? Number(res.headers.get("Retry-After") || 1) : 0;
        if (wait && wait <= 60 && attempt < 3) {
            return setTimeout(() => post(endpoint, body, callback, attempt + 1), wait * 1000 + 250);
        }
        callback(err, res);
    });

    const login = () => {
        const email = pm.variables.get(emailVar);
        const password = pm.variables.get(passwordVar);
        if (!email || !password) {
            console.warn(`Auto-auth: set ${emailVar} / ${passwordVar} in the environment.`);
            return;
        }
        post("/auth/login", { email, password }, (err, res) => {
            if (!err && res.code === 200) saveTokens(prefix, res.json());
            else console.error(`Auto-auth: login as ${email} failed`, err || res.code, res && res.text());
        });
    };

    const refresh = pm.variables.get(prefix + "refresh_token");
    if (!refresh) return login();
    post("/auth/refresh", { refresh_token: refresh }, (err, res) => {
        if (!err && res.code === 200) return saveTokens(prefix, res.json());
        store.unset(prefix + "refresh_token");
        login();
    });
}"""

TESTS = r"""// Checks that apply to every request.
pm.test("Response time is acceptable", () => {
    pm.expect(pm.response.responseTime).to.be.below(Number(pm.variables.get("max_response_ms") || 5000));
});
// 429: wait Retry-After and send the same request again (Collection Runner / Newman), at most
// 3 times per request. The request's own tests are skipped for the rate-limited attempt.
const retryKey = `retry_429_${pm.info.requestId}`;
if (pm.response.code === 429) {
    const attempt = Number(pm.collectionVariables.get(retryKey) || 0);
    const wait = Number(pm.response.headers.get("Retry-After") || 1);
    console.warn(`Rate limited (attempt ${attempt + 1}): retrying in ${wait} s`);
    if (attempt < 3 && wait <= 60) { // a login lockout (minutes) is not waited out
        pm.collectionVariables.set(retryKey, String(attempt + 1));
        pm.variables.set("_rate_limited_retry", "true");
        setTimeout(() => {}, wait * 1000 + 250);
        pm.execution.setNextRequest(pm.info.requestId);
    }
} else {
    pm.collectionVariables.unset(retryKey);
    pm.variables.set("_rate_limited_retry", "false");
}
if (pm.response.code === 401 && pm.request.headers.has("Authorization")) {
    // A token revoked or signed with another secret: force a fresh login next time.
    const store = pm.environment.name ? pm.environment : pm.collectionVariables;
    const prefix = /(^|\/)(admin|ingest)\//.test(pm.request.url.getPath()) ? "admin_" : "";
    store.unset(prefix + "access_token_expires_at");
}"""

PREAMBLE = """if (pm.variables.get("_rate_limited_retry") === "true") return; // resent after Retry-After
const store = pm.environment.name ? pm.environment : pm.collectionVariables;
let json = null;
try { json = pm.response.json(); } catch (e) { /* empty or non-JSON body */ }"""

SAVE_TOKENS = """function saveTokens(prefix, body) {
    store.set(prefix + "access_token", body.access_token);
    store.set(prefix + "refresh_token", body.refresh_token);
    store.set(prefix + "access_token_expires_at", String(Date.now() + (body.expires_in - 30) * 1000));
}"""


# --- description ------------------------------------------------------------------------------


def collection_description(commit: str, total: int) -> str:
    return f"""# AI Trading Platform – REST API

Backend of the AI trading analysis platform (FastAPI, PostgreSQL/TimescaleDB, Redis, Celery). \
This collection covers **every endpoint** ({total} requests) with a saved example response for \
each request and its main error cases.

**Synced with backend commit `{commit}`** of `main`. The API contract is \
`docs/api/openapi.json` in the repository (WebSocket: `docs/api/asyncapi.yaml`). Swagger UI \
(`/docs`), ReDoc (`/redoc`) and `/openapi.json` are served locally, but **off in production** \
unless `API_DOCS_ENABLED=true`.

## Quick start

1. Import the collection and both files of `docs/postman/environments/`.
2. Pick an environment (**Production (VPS)** or **Local (Docker)**) and fill in `user_email` / \
`user_password` (and `admin_email` / `admin_password` for the Admin folder).
3. Send any request. Tokens are obtained, cached and refreshed automatically by the \
collection's pre-request script; you never paste a token by hand.

No account yet? Send **Auth → Register**: when `user_email` is empty, the new account becomes \
the collection's user.

## Authentication

| Method | How | Used for |
|---|---|---|
| Bearer JWT | `Authorization: Bearer {{{{access_token}}}}` (collection default) | apps, everything |
| Admin JWT | `Authorization: Bearer {{{{admin_access_token}}}}` (Admin folder) | `/admin/*` |
| API key | `X-API-Key: {{{{api_key}}}}` | external programs, read-only scopes |

Access tokens live 30 minutes, refresh tokens 14 days and are rotated on every refresh. \
Roles: `trader` (default on registration), `analyst`, `expert`, `admin`.

## Conventions

* Base path `/api/v1`; JSON in and out; all times are **UTC** (naive datetimes are taken as UTC).
* Chart data uses **unix seconds** in `time` (Lightweight Charts format).
* Lists are pages: `{{"items": [...], "total": 123, "limit": 20, "offset": 0}}`.
* Errors: `{{"detail": "message"}}`, or for validation (422) \
`{{"detail": [{{"loc": ["body", "field"], "msg": "...", "type": "..."}}]}}`.
* Someone else's resource answers **404**, never 403.
* Every response carries `X-Request-ID` (yours, if you send a sane one, else a new id): quote \
it when reporting a problem, it is on the server's log line for that request.
* An overloaded database answers **503** with `Retry-After` and `retry_after` in the body.

## Rate limits

Per identity (user, or each API key) per minute: trader 60, analyst/expert 300, admin 1,000. \
Indicator computation, strategy preview and backtest creation cost 5. Every limited response \
carries `RateLimit-Limit`, `RateLimit-Remaining`, `RateLimit-Reset`; a 429 adds `Retry-After`.

## Running the whole collection

The folders are ordered so the **Collection Runner** can execute them top to bottom: each \
folder creates what it needs (workspaces, strategies, backtests, keys), uses it and deletes it \
again. Ids are passed between requests through environment variables (`instrument_id`, \
`workspace_id`, `backtest_id`, …). Every request has tests for its status code and \
documented fields.

> On **Production**, Register, Admin and the create requests write real data. Prefer the \
Local environment for full runs.

## Folders

Health · Auth · Users (me) · Market Data · Indicators · Strategies & Signals · Risk \
Management · Custom Strategies · Backtests · Workspaces · API Keys · News · Community · Price \
Alerts · Experts & Subscriptions · Chat · Expert Studio · Notifications · Admin · Realtime \
(WebSocket)

Maintained in the repository: `docs/postman/` (generated by `docs/postman/tools/`)."""


# --- builders ---------------------------------------------------------------------------------


def url_object(
    req: Req,
    path: str | None = None,
    query_override: dict | None = None,
    path_override: dict | None = None,
) -> dict[str, Any]:
    path = path or req.path
    raw_path = path
    segments = [s for s in path.strip("/").split("/") if s]
    query = []
    for key, value, desc in req.query:
        if query_override is not None and key in query_override:
            value = query_override[key]
        query.append({"key": key, "value": value, "description": desc})
    if query_override is None:
        for key, value, desc in req.optional_query:
            query.append({"key": key, "value": value, "description": desc, "disabled": True})
    variables = []
    for name in re.findall(r":(\w+)", path):
        value, desc = req.path_vars.get(name, (f"{{{{{name}}}}}", ""))
        if path_override and name in path_override:
            value = path_override[name]
        variables.append({"key": name, "value": value, "description": desc})
    # {{base_url}} directly (not the nested {{api_url}}), so the URL bar always shows the full path
    raw = "{{base_url}}/api/v1" + raw_path
    enabled = [q for q in query if not q.get("disabled")]
    if enabled:
        raw += "?" + "&".join(f"{q['key']}={q['value']}" for q in enabled)
    out: dict[str, Any] = {
        "raw": raw,
        "host": ["{{base_url}}"],
        "path": ["api", "v1", *segments],
    }
    if query:
        out["query"] = query
    if variables:
        out["variable"] = variables
    return out


def body_object(req: Req, body: Any = None) -> dict[str, Any] | None:
    if req.form is not None:
        return {
            "mode": "urlencoded",
            "urlencoded": [
                {"key": k, "value": v, "description": d, "type": "text"} for k, v, d in req.form
            ],
        }
    body = req.body if body is None else body
    if body is None:
        return None
    if isinstance(body, str):
        raw = body
    else:
        raw = json.dumps(body, indent=4, ensure_ascii=False)
        # numbers that come from variables: "{{custom_strategy_version}}" -> {{...}}
        raw = raw.replace('"{{custom_strategy_version}}"', "{{custom_strategy_version}}")
    return {"mode": "raw", "raw": raw, "options": {"raw": {"language": "json"}}}


def headers_for(req: Req, overrides: dict[str, str] | None = None) -> list[dict[str, Any]]:
    headers = []
    if req.body is not None and req.form is None:
        headers.append({"key": "Content-Type", "value": "application/json"})
    if req.auth == "apikey":
        headers.append(
            {
                "key": "X-API-Key",
                "value": "{{api_key}}",
                "description": "API key from **API Keys → Create API key**",
            }
        )
    for key, value, desc in req.headers:
        headers.append({"key": key, "value": value, "description": desc})
    if overrides is not None:
        for key, value in overrides.items():
            headers = [h for h in headers if h["key"] != key]
            if value != "":
                headers.append({"key": key, "value": value})
    return headers


def auth_for(mode: str) -> dict[str, Any] | None:
    if mode in ("none", "apikey"):
        return {"type": "noauth"}
    if mode == "admin":
        return bearer("{{admin_access_token}}")
    return None  # inherit (collection: user bearer; Admin folder: admin bearer)


def test_script(req: Req, examples: list[dict[str, Any]]) -> str:
    parts = [PREAMBLE]
    codes = ", ".join(str(c) for c in req.expect)
    label = " or ".join(str(c) for c in req.expect)
    parts.append(
        f'pm.test("Status code is {label}", () => {{\n'
        f"    pm.expect(pm.response.code).to.be.oneOf([{codes}]);\n}});"
    )
    main = next((e for e in examples if e["variant"] is None and e["code"] in req.expect), None)
    if (
        main
        and main["body"]
        and main["headers"].get("content-type", "").startswith("application/json")
    ):
        sample = json.loads(main["body"])
        if isinstance(sample, dict) and sample:
            keys = ", ".join(json.dumps(k) for k in list(sample)[:10])
            parts.append(
                f"if (json && pm.response.code === {main['code']}) {{\n"
                f'    pm.test("Body has the documented fields", () => {{\n'
                f"        pm.expect(json).to.include.all.keys({keys});\n    }});\n}}"
            )
        elif isinstance(sample, list):
            parts.append(
                f"if (pm.response.code === {main['code']}) {{\n"
                f'    pm.test("Body is a list", () => pm.expect(json).to.be.an("array"));\n}}'
            )
    if req.captures:
        sets = "\n".join(
            f'    const {re.sub(r"[^A-Za-z0-9]", "_", var)} = _.get(json, "{path}");\n'
            f"    if ({re.sub(r'[^A-Za-z0-9]', '_', var)} !== undefined && "
            f'{re.sub(r"[^A-Za-z0-9]", "_", var)} !== null) store.set("{var}", String('
            f"{re.sub(r'[^A-Za-z0-9]', '_', var)}));"
            # a pick from a list that came back empty: clear the old id so the requests that
            # need it skip instead of hitting a stale one
            + (f'\n    else store.set("{var}", "");' if ".0" in path else "")
            for var, path in req.captures.items()
        )
        parts.append(
            f"// Save ids for the requests that follow\nif (json && pm.response.code < 300) {{\n{sets}\n}}"
        )
    if "saveTokens(" in req.tests:
        parts.append(SAVE_TOKENS)
    if req.tests:
        parts.append(req.tests.strip())
    return "\n\n".join(parts)


def example_objects(req: Req, examples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    by_name = {v.name: v for v in req.variants}
    for i, ex in enumerate(examples):
        variant = by_name.get(ex["variant"]) if ex["variant"] else None
        if variant is not None:
            body = body_object(req, variant.body) if req.body is not None or variant.body else None
            url = url_object(
                req,
                path=variant.path,
                query_override={
                    **{k: v for k, v, _ in req.query},
                    **(variant.query or {}),
                }
                if variant.query is not None
                else None,
                path_override=variant.path_vars,
            )
            headers = headers_for(req, variant.headers)
            if variant.auth == "none":
                headers = [h for h in headers if h["key"] != "Authorization"]
        else:
            body, url, headers = body_object(req), url_object(req), headers_for(req)
            if ex["variant"] == "429":  # the rate-limit demo key
                headers = headers_for(req)
        original: dict[str, Any] = {"method": req.method, "header": headers, "url": url}
        if variant is not None and variant.auth == "none":
            original["auth"] = {"type": "noauth"}
        if body is not None:
            original["body"] = body
        content_type = ex["headers"].get("content-type", "")
        language = "json" if "json" in content_type else "text"
        out.append(
            {
                "id": uid(f"{req.id}:example:{i}"),
                "name": ex["name"],
                "originalRequest": original,
                "status": ex["status"],
                "code": ex["code"],
                "_postman_previewlanguage": language,
                "header": [{"key": _title(k), "value": v} for k, v in ex["headers"].items()],
                "cookie": [],
                "body": ex["body"],
            }
        )
    return out


def _title(header: str) -> str:
    special = {
        "etag": "ETag",
        "ratelimit-limit": "RateLimit-Limit",
        "ratelimit-remaining": "RateLimit-Remaining",
        "ratelimit-reset": "RateLimit-Reset",
    }
    return special.get(header.lower(), "-".join(p.capitalize() for p in header.split("-")))


def request_item(req: Req, examples: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    desc = req.description
    meta = []
    auth_text = {
        "user": "Bearer JWT (`{{access_token}}`)",
        "admin": "Bearer JWT of an **admin** (`{{admin_access_token}}`)",
        "none": "None (public)",
        "apikey": "API key (`X-API-Key: {{api_key}}`)",
    }[req.auth]
    meta.append(f"**Auth:** {auth_text}")
    if req.cost > 1:
        meta.append(f"**Rate-limit cost:** {req.cost}")
    meta.append("**Success:** " + ", ".join(f"`{c}`" for c in req.expect))
    desc = desc + "\n\n" + " · ".join(meta)
    request: dict[str, Any] = {
        "method": req.method,
        "header": headers_for(req),
        "url": url_object(req),
        "description": desc,
    }
    body = body_object(req)
    if body is not None:
        request["body"] = body
    auth = auth_for(req.auth)
    if auth is not None:
        request["auth"] = auth
    events = []
    if req.pre:
        events.append(
            {
                "listen": "prerequest",
                "script": {
                    "id": uid(f"{req.id}:pre"),
                    "type": "text/javascript",
                    "exec": lines(req.pre),
                },
            }
        )
    req_examples = examples.get(req.id, [])
    events.append(
        {
            "listen": "test",
            "script": {
                "id": uid(f"{req.id}:test"),
                "type": "text/javascript",
                "exec": lines(test_script(req, req_examples)),
            },
        }
    )
    return {
        "id": uid(req.id),
        "name": req.name,
        "event": events,
        "request": request,
        "response": example_objects(req, req_examples),
    }


def folder_item(folder: Folder, examples: dict, prefix: str = "") -> dict[str, Any]:
    items = []
    for item in folder.items:
        if isinstance(item, Folder):
            items.append(folder_item(item, examples))
        else:
            items.append(request_item(item, examples))
    out: dict[str, Any] = {
        "id": uid(f"folder:{folder.name}:{prefix}"),
        "name": f"{prefix}{folder.name}",
        "description": folder.description,
        "item": items,
    }
    if folder.auth == "admin":
        out["auth"] = bearer("{{admin_access_token}}")
    return out


def bearer(token: str) -> dict[str, Any]:
    return {
        "type": "bearer",
        "bearer": [{"key": "token", "value": token, "type": "string"}],
    }


def iter_reqs(items: list[Req | Folder]):
    for item in items:
        if isinstance(item, Folder):
            yield from iter_reqs(item.items)
        else:
            yield item


def build_collection(examples: dict, commit: str) -> dict[str, Any]:
    total = len(list(iter_reqs(FOLDERS)))
    items = [folder_item(f, examples, f"{i:02d} · ") for i, f in enumerate(FOLDERS, start=1)]
    items.append(
        {
            "id": uid("folder:websocket"),
            "name": f"{len(FOLDERS) + 1:02d} · Realtime (WebSocket)",
            "description": WEBSOCKET_DOC,
            "item": [],
        }
    )
    return {
        "info": {
            "_postman_id": uid("collection"),
            "name": "AI Trading Platform API",
            "description": collection_description(commit, total),
            "schema": SCHEMA,
        },
        "item": items,
        "auth": bearer("{{access_token}}"),
        "event": [
            {
                "listen": "prerequest",
                "script": {
                    "id": uid("collection:pre"),
                    "type": "text/javascript",
                    "exec": lines(PRE_REQUEST),
                },
            },
            {
                "listen": "test",
                "script": {
                    "id": uid("collection:test"),
                    "type": "text/javascript",
                    "exec": lines(TESTS),
                },
            },
        ],
        "variable": [
            {
                "key": "api_url",
                "value": "{{base_url}}/api/v1",
                "description": "Every request is relative to this",
            },
            {
                "key": "base_url",
                "value": "http://localhost",
                "description": "Fallback when no environment is selected",
            },
            {
                "key": "timeframe",
                "value": "1h",
                "description": "1m | 5m | 15m | 1h | 4h | 1d",
            },
            {
                "key": "strategy_key",
                "value": "ma_crossover",
                "description": "Global strategy used by the examples",
            },
            {
                "key": "max_response_ms",
                "value": "5000",
                "description": "Response-time test threshold",
            },
            {
                "key": "auto_auth",
                "value": "true",
                "description": "false disables automatic login/refresh",
            },
        ],
    }


# --- environments -----------------------------------------------------------------------------

RUNTIME_VARS = [
    # tokens (managed by the scripts)
    ("access_token", "", "secret"),
    ("refresh_token", "", "secret"),
    ("access_token_expires_at", "", "default"),
    ("admin_access_token", "", "secret"),
    ("admin_refresh_token", "", "secret"),
    ("admin_access_token_expires_at", "", "default"),
    ("api_key", "", "secret"),
    # ids passed between requests
    *(
        (name, "", "default")
        for name in (
            "user_id",
            "target_user_id",
            "instrument_id",
            "admin_instrument_id",
            "user_strategy_id",
            "custom_strategy_id",
            "custom_strategy_key",
            "custom_strategy_version",
            "custom_strategy_clone_id",
            "public_strategy_id",
            "public_clone_id",
            "backtest_id",
            "backtest_id_2",
            "workspace_id",
            "workspace_version",
            "workspace_ids",
            "workspace_copy_id",
            "workspace_import_id",
            "share_slug",
            "api_key_id",
            "admin_api_key_id",
            "article_id",
            "news_source_id",
            "post_id",
            "other_post_id",
            "author_user_id",
            "comment_id",
            "reply_id",
            "report_id",
            "price_alert_id",
            "expert_id",
            "plan_id",
            "checkout_id",
            "subscription_id",
            "invoice_id",
            "conversation_id",
            "message_id",
            "my_plan_id",
            "notification_id",
            "device_id",
        )
    ),
]


def environment(name: str, base_url: str, ws_url: str, creds: dict[str, str]) -> dict[str, Any]:
    values = [
        {"key": "base_url", "value": base_url, "type": "default", "enabled": True},
        {"key": "ws_url", "value": ws_url, "type": "default", "enabled": True},
        {
            "key": "user_email",
            "value": creds.get("user_email", ""),
            "type": "default",
            "enabled": True,
        },
        {
            "key": "user_password",
            "value": creds.get("user_password", ""),
            "type": "secret",
            "enabled": True,
        },
        {
            "key": "user_new_password",
            "value": creds.get("user_new_password", ""),
            "type": "secret",
            "enabled": True,
        },
        {
            "key": "register_password",
            "value": "Postman123",
            "type": "secret",
            "enabled": True,
        },
        {
            "key": "admin_email",
            "value": creds.get("admin_email", ""),
            "type": "default",
            "enabled": True,
        },
        {"key": "admin_password", "value": "", "type": "secret", "enabled": True},
    ]
    values += [{"key": k, "value": v, "type": t, "enabled": True} for k, v, t in RUNTIME_VARS]
    return {
        "id": uid(f"env:{name}"),
        "name": f"AI Trading – {name}",
        "values": values,
        "_postman_variable_scope": "environment",
    }


ENVIRONMENTS = {
    "Production.postman_environment.json": (
        "Production (VPS)",
        "http://187.127.76.76:8080",
        "ws://187.127.76.76:8080",
        {},
    ),
    "Local.postman_environment.json": (
        "Local (Docker)",
        "http://localhost",
        "ws://localhost",
        {"user_new_password": "Changed12345"},
    ),
}


# --- coverage check ---------------------------------------------------------------------------


def check_coverage() -> int:
    sys.path.insert(0, str(REPO / "backend"))
    from app.main import app  # noqa: PLC0415

    def norm(path: str) -> str:
        return re.sub(r"\{\w+\}|:\w+", "{}", path)

    api = set()
    for path, ops in app.openapi()["paths"].items():
        for method in ops:
            api.add((method.upper(), norm(path.removeprefix("/api/v1"))))
    covered = {(r.method, norm(r.path)) for r in iter_reqs(FOLDERS)}
    missing = sorted(api - covered)
    stale = sorted(covered - api)
    for method, path in missing:
        print(f"MISSING  {method} {path}")
    for method, path in stale:
        print(f"STALE    {method} {path}")
    if not missing and not stale:
        print(f"OK: all {len(api)} API operations are in the collection")
    examples = json.loads((TOOLS / "examples.json").read_text())
    no_example = [r.id for r in iter_reqs(FOLDERS) if r.id not in examples]
    for rid in no_example:
        print(f"NO EXAMPLE  {rid} (run capture_examples.py)")
    return 1 if missing or stale or no_example else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="compare spec.py with the API routes")
    parser.add_argument("--commit", help="backend commit shown in the description (default: HEAD)")
    args = parser.parse_args()
    if args.check:
        sys.exit(check_coverage())
    commit = (
        args.commit
        or subprocess.run(
            ["git", "rev-parse", "--short=7", "HEAD"],
            cwd=REPO,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    examples = json.loads((TOOLS / "examples.json").read_text())
    collection = build_collection(examples, commit)
    COLLECTION_FILE.write_text(json.dumps(collection, indent=2, ensure_ascii=False) + "\n")
    ENV_DIR.mkdir(exist_ok=True)
    for filename, (name, base, ws, creds) in ENVIRONMENTS.items():
        env = environment(name, base, ws, creds)
        (ENV_DIR / filename).write_text(json.dumps(env, indent=2, ensure_ascii=False) + "\n")
    n = len(list(iter_reqs(FOLDERS)))
    e = sum(len(v) for v in examples.values())
    print(
        f"wrote {COLLECTION_FILE.name}: {n} requests, {e} examples; {len(ENVIRONMENTS)} environments"
    )


if __name__ == "__main__":
    main()
