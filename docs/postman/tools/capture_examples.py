"""Run every request of spec.py against a running API and save the responses as examples.

Use a local stack with demo data, never production:

    docker compose up -d                      # or uvicorn + a Celery worker on queue "backtests"
    docker compose exec backend python -m app.cli seed-instruments
    docker compose exec backend python -m app.cli seed-demo-candles --symbol BTC/USDT \
        --source binance --days 30
    python docs/postman/tools/capture_examples.py --base-url http://localhost:8000 \
        --admin-email admin@example.com --admin-password '...'

Writes docs/postman/tools/examples.json; then run build_collection.py.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from spec import FOLDERS, Folder, Req, Variant  # noqa: E402

OUT = Path(__file__).resolve().parent / "examples.json"
KEEP_HEADERS = {
    "content-type",
    "etag",
    "content-disposition",
    "ratelimit-limit",
    "ratelimit-remaining",
    "ratelimit-reset",
    "retry-after",
}
# Lists longer than this are cut to TRIM_TO items in saved examples (candles, curves, ...),
# except in the responses below, whose whole content is the point.
TRIM_OVER, TRIM_TO = 6, 3
NO_TRIM = {"indicators_catalog", "strategies_catalog"}

CAPTURE_EMAIL = "trader@example.com"
CAPTURE_PASSWORD = "Trader12345"


def get_path(data: Any, path: str) -> Any:
    for part in path.split("."):
        if isinstance(data, list):
            if not part.isdigit() or int(part) >= len(data):
                return None
            data = data[int(part)]
        elif isinstance(data, dict):
            data = data.get(part)
        else:
            return None
    return data


def trim(value: Any, depth: int = 0) -> Any:
    if isinstance(value, list):
        items = value[:TRIM_TO] if len(value) > TRIM_OVER else value
        return [trim(v, depth + 1) for v in items]
    if isinstance(value, dict):
        return {k: trim(v, depth + 1) for k, v in value.items()}
    return value


class Runner:
    def __init__(self, base_url: str, admin_email: str, admin_password: str) -> None:
        self.http = httpx.Client(base_url=base_url, timeout=60)
        self.vars: dict[str, str] = {
            "api_url": "/api/v1",
            "timeframe": "1h",
            "strategy_key": "ma_crossover",
            "user_email": CAPTURE_EMAIL,
            "user_password": CAPTURE_PASSWORD,
            "user_new_password": "Changed12345",
            "register_password": "Postman123",
            "admin_email": admin_email,
            "admin_password": admin_password,
        }
        self.examples: dict[str, list[dict[str, Any]]] = {}

    # --- variables -------------------------------------------------------------------------
    def resolve(self, value: Any) -> Any:
        if isinstance(value, str):

            def sub(m: re.Match[str]) -> str:
                name = m.group(1)
                if name == "$timestamp":
                    return str(int(time.time()))
                return str(self.vars.get(name, ""))

            return re.sub(r"\{\{([^}]+)\}\}", sub, value)
        if isinstance(value, list):
            return [self.resolve(v) for v in value]
        if isinstance(value, dict):
            return {k: self.resolve(v) for k, v in value.items()}
        return value

    def typed(self, value: Any) -> Any:
        """``"{{custom_strategy_version}}"`` must reach the API as a number, as in Postman
        where the raw body text is substituted."""
        text = json.dumps(value)
        text = re.sub(r'"\{\{(custom_strategy_version)\}\}"', lambda m: self.vars[m.group(1)], text)
        return json.loads(self.resolve(text)) if isinstance(value, (dict, list)) else value

    # --- auth --------------------------------------------------------------------------------
    def login(self, prefix: str) -> None:
        email = self.vars["admin_email" if prefix else "user_email"]
        password = self.vars["admin_password" if prefix else "user_password"]
        res = self.http.post("/api/v1/auth/login", json={"email": email, "password": password})
        res.raise_for_status()
        self.vars[f"{prefix}access_token"] = res.json()["access_token"]
        self.vars[f"{prefix}refresh_token"] = res.json()["refresh_token"]

    def auth_headers(self, mode: str) -> dict[str, str]:
        if mode == "none":
            return {}
        if mode == "apikey":
            return {"X-API-Key": self.vars.get("api_key", "")}
        prefix = "admin_" if mode == "admin" else ""
        if not self.vars.get(f"{prefix}access_token"):
            self.login(prefix)
        return {"Authorization": f"Bearer {self.vars[f'{prefix}access_token']}"}

    # --- requests ----------------------------------------------------------------------------
    def send(self, req: Req, variant: Variant | None = None) -> httpx.Response:
        path = variant.path if variant and variant.path else req.path
        pvars = {k: v[0] for k, v in req.path_vars.items()}
        if variant and variant.path_vars:
            pvars.update(variant.path_vars)
        for name, value in pvars.items():
            path = path.replace(f":{name}", self.resolve(value))
        query = {k: self.resolve(v) for k, v, _ in req.query}
        if variant and variant.query is not None:
            query.update(variant.query)
        headers = self.auth_headers(variant.auth if variant and variant.auth else req.auth)
        for k, v, _ in req.headers:
            headers[k] = self.resolve(v)
        if variant and variant.headers:
            for k, v in variant.headers.items():
                if v == "":
                    headers.pop(k, None)
                else:
                    headers[k] = v
        body = variant.body if variant and variant.body is not None else req.body
        kwargs: dict[str, Any] = {"params": query, "headers": headers}
        if req.form is not None:
            kwargs["data"] = {k: self.resolve(v) for k, v, _ in req.form}
        elif isinstance(body, str):
            kwargs["content"] = self.resolve(body)
            headers["Content-Type"] = "application/json"
        elif body is not None:
            kwargs["json"] = self.typed(body)
        return self.http.request(req.method, f"/api/v1{path}", **kwargs)

    def record(self, req: Req, name: str, res: httpx.Response, variant: Variant | None) -> None:
        ctype = res.headers.get("content-type", "")
        if "json" in ctype and res.content:
            body: Any = res.json()
            if req.id not in NO_TRIM:
                body = trim(body)
            text = json.dumps(body, indent=4, ensure_ascii=False)
        else:
            text = res.text
            if req.id == "backtests_trades_csv":
                text = "\n".join(text.splitlines()[: TRIM_TO + 1]) + "\n"
        self.examples.setdefault(req.id, []).append(
            {
                "name": name,
                "code": res.status_code,
                "status": res.reason_phrase,
                "headers": {k: v for k, v in res.headers.items() if k.lower() in KEEP_HEADERS},
                "body": text,
                "variant": None if variant is None else variant.name,
            }
        )

    # --- per-request script equivalents --------------------------------------------------------
    def before(self, req: Req) -> None:
        now = datetime.now(UTC).replace(microsecond=0)
        if req.id == "auth_register":
            self.vars["register_email"] = f"qa.{int(time.time() * 1000)}@example.com"
        if req.id.startswith("backtests_create"):
            end = now - timedelta(hours=1)
            self.vars["backtest_start"] = (end - timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")
            self.vars["backtest_end"] = end.strftime("%Y-%m-%dT%H:%M:%SZ")
        if req.id == "admin_candles_upsert":
            minute = now.replace(second=0)
            for i, back in enumerate((2, 1, 0)):
                ts = minute - timedelta(minutes=back)
                self.vars[f"candle_ts_{i}"] = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
        if req.id == "ws_reorder":
            ids = json.loads(self.vars.get("workspace_ids", "[]"))
            self.vars["workspace_ids_reversed"] = json.dumps(list(reversed(ids)))

    def after(self, req: Req, res: httpx.Response) -> None:
        data = res.json() if res.content and "json" in res.headers.get("content-type", "") else None
        if res.status_code < 300 and data is not None:
            for var, path in req.captures.items():
                value = get_path(data, path)
                if value is not None:
                    self.vars[var] = str(value)
        if req.id in ("auth_login", "auth_refresh") and res.status_code == 200:
            self.vars["access_token"] = data["access_token"]
            self.vars["refresh_token"] = data["refresh_token"]
        if req.id == "auth_logout":
            self.vars.pop("refresh_token", None)
        if req.id == "users_me_password" and res.status_code == 204:
            self.vars["user_password"], self.vars["user_new_password"] = (
                self.vars["user_new_password"],
                self.vars["user_password"],
            )
        if req.id in ("ws_list", "ws_list_2"):
            self.vars["workspace_ids"] = json.dumps([w["id"] for w in data])
        cleanup = {
            "ws_delete": ("/me/workspaces/", ["workspace_copy_id", "workspace_import_id"]),
            "custom_delete": (
                "/me/custom-strategies/",
                ["custom_strategy_clone_id", "public_clone_id", "composite_strategy_id"],
            ),
            "backtests_delete": ("/backtests/", ["backtest_id_2"]),
        }
        if req.id in cleanup:
            prefix, names = cleanup[req.id]
            for name in names:
                if self.vars.get(name):
                    self.http.delete(
                        f"/api/v1{prefix}{self.vars.pop(name)}", headers=self.auth_headers("user")
                    )

    def wait_backtest(self, var: str) -> None:
        for _ in range(60):
            res = self.http.get(
                f"/api/v1/backtests/{self.vars[var]}", headers=self.auth_headers("user")
            )
            if res.json()["status"] not in ("queued", "running"):
                return
            time.sleep(1)
        raise RuntimeError("backtest did not finish: is a Celery worker on queue 'backtests'?")

    # --- setup and the run ---------------------------------------------------------------------
    def setup(self) -> None:
        """A capture user (analyst, so sharing/publishing work) and a public strategy of
        another user, so 'Browse public strategies' has something to show."""
        res = self.http.post(
            "/api/v1/auth/register",
            json={"email": CAPTURE_EMAIL, "password": CAPTURE_PASSWORD, "full_name": "Sara Trader"},
        )
        if res.status_code not in (201, 409):
            res.raise_for_status()
        admin = self.auth_headers("admin")
        users = self.http.get(
            "/api/v1/admin/users", params={"q": CAPTURE_EMAIL}, headers=admin
        ).json()
        uid = users["items"][0]["id"]
        self.http.patch(f"/api/v1/admin/users/{uid}/role", json={"role": "analyst"}, headers=admin)
        public = self.http.get(
            "/api/v1/custom-strategies/public", headers=admin, params={"search": "Trend rider"}
        ).json()
        if not public["items"]:
            from spec import EMA_CROSS

            self.http.post(
                "/api/v1/me/custom-strategies",
                headers=admin,
                json={
                    "name": "Trend rider EMA 9/21",
                    "description": "Classic EMA 9/21 crossover, shared by the platform team.",
                    "kind": "builder",
                    "definition": EMA_CROSS,
                    "visibility": "public",
                },
            ).raise_for_status()

    def run_items(self, items: list[Req | Folder]) -> None:
        for item in items:
            if isinstance(item, Folder):
                self.run_items(item.items)
                continue
            self.before(item)
            if item.id == "backtests_compare":
                self.wait_backtest("backtest_id_2")
            if item.id == "backtests_get":
                self.wait_backtest("backtest_id")
            res = self.send(item)
            if res.status_code not in item.expect:
                print(f"!! {item.id}: {res.status_code} {res.text[:300]}")
            else:
                print(f"ok {item.id}: {res.status_code}")
            self.record(item, f"{res.status_code} {res.reason_phrase}", res, None)
            self.after(item, res)
            for variant in item.variants:
                vres = self.send(item, variant)
                flag = "ok" if vres.status_code == variant.status else "!!"
                print(f"{flag}   variant {variant.name!r}: {vres.status_code} {vres.text[:200]}")
                self.record(item, variant.name, vres, variant)
                if item.id == "custom_create" and vres.status_code == 201:
                    self.vars["composite_strategy_id"] = vres.json()["id"]
            if item.id == "apikey_instruments":
                self.rate_limit_example(item)

    def rate_limit_example(self, req: Req) -> None:
        """A real 429: a throwaway key limited to 1 request per minute, called twice."""
        res = self.http.post(
            "/api/v1/me/api-keys",
            headers=self.auth_headers("user"),
            json={"name": "rate limit demo", "scopes": ["market:read"], "rate_limit_per_minute": 1},
        )
        key = res.json()
        saved = self.vars["api_key"]
        self.vars["api_key"] = key["key"]
        self.send(req)
        res = self.send(req)
        self.record(req, "429 Rate limit exceeded", res, Variant("429", 429))
        self.vars["api_key"] = saved
        self.http.delete(f"/api/v1/me/api-keys/{key['id']}", headers=self.auth_headers("user"))
        print(f"ok   variant '429': {res.status_code}")

    def run(self) -> None:
        self.setup()
        self.run_items(FOLDERS)
        OUT.write_text(json.dumps(self.examples, indent=1, ensure_ascii=False) + "\n")
        print(f"wrote {sum(len(v) for v in self.examples.values())} examples to {OUT}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--admin-email", required=True)
    parser.add_argument("--admin-password", required=True)
    args = parser.parse_args()
    Runner(args.base_url, args.admin_email, args.admin_password).run()


if __name__ == "__main__":
    main()
