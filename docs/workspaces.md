# Workspaces (saved trading screens)

A **workspace** is one tab of the trading screen, saved on the server. It holds which charts are
open, in which layout, with which instruments, timeframes, indicators, strategy overlays and
drawings, and the watchlist. The web app and the Flutter app read and write the same workspaces,
so a user can continue on another device, and two devices may edit at the same time (see
[Versions and conflicts](#versions-and-conflicts)).

All endpoints are under `/api/v1`, need a login token (`Authorization: Bearer <access JWT>`)
and are rate limited like the rest of the API. API keys are refused (403).

## Endpoints

| Method | Path | |
|---|---|---|
| GET | `/me/workspaces` | Summaries in tab order: `id, name, position, is_default, version, panel_count, is_shared, updated_at`. A user without workspaces gets the **default workspace** created first, so the list is never empty. |
| POST | `/me/workspaces` | `{name, state?}` or `{name, template?}` → 201 full workspace. 409 if the name exists, 400 over the limit. |
| GET | `/me/workspaces/{id}` | Full workspace (`ETag: "<version>"`). |
| PUT | `/me/workspaces/{id}` | `{state, version}` replaces the whole state → 200 with `version + 1`. 409 if `version` is stale. |
| PATCH | `/me/workspaces/{id}` | `{name?, is_default?: true, version?}`: rename, or make it the default. |
| POST | `/me/workspaces/{id}/duplicate` | Copy named `"<name> (copy)"` (then `(copy 2)`, ...), not default, not shared → 201. |
| PUT | `/me/workspaces/order` | `{ids: [...]}` with **exactly** all of your workspace ids, in the new tab order → 200 summaries. |
| DELETE | `/me/workspaces/{id}` | 204. Deleting the default makes the first remaining tab the default. Deleting the last one is allowed: the next GET recreates the default workspace. |
| POST | `/me/workspaces/{id}/share` | Analysts, experts and admins (403 for traders): `{is_shared: true, share_slug}`. |
| DELETE | `/me/workspaces/{id}/share` | Stop sharing; the old link answers 404. |
| GET | `/workspaces/shared/{slug}` | Any logged-in user: read-only copy with the owner's display name and role, no ids. |
| POST | `/workspaces/shared/{slug}/import` | Copy it into your workspaces (`{name?}`; your limit applies) → 201. |

A workspace of another user answers **404**, never 403.

Full workspace (GET/POST/PUT/PATCH response):

```json
{
  "id": "1c3e…", "name": "Main", "position": 0, "is_default": true,
  "version": 7, "schema_version": 1, "is_shared": false, "share_slug": null,
  "state": { "...": "see below" },
  "unavailable_instrument_ids": [],
  "created_at": "2026-10-16T08:00:00Z", "updated_at": "2026-10-16T09:12:03Z"
}
```

**Limits per role:** trader 5 workspaces, analyst / expert / admin 20. Names are 1–60
characters and unique per user, ignoring case (`Scalping` and `scalping` clash).

## The state document

The whole screen is one JSON document, saved in one call. `schema_version` is `1`. The JSON
Schema is in [workspace-state.schema.json](workspace-state.schema.json) (generated from the
backend models).

```json
{
  "layout": { "type": "1x2", "sizes": [0.6, 0.4] },
  "sync": { "crosshair": true, "timeframe": false, "instrument": false },
  "panels": [
    {
      "id": "p1",
      "instrument_id": "76aa70d6-069f-42a3-8500-ff324f4da1d1",
      "timeframe": "1h",
      "chart_type": "candles",
      "indicators": [
        { "id": "i1", "name": "ema", "params": { "length": 20 }, "visible": true, "color": "#2962FF" },
        { "id": "i2", "name": "rsi", "params": { "length": 14 }, "visible": true, "color": "#7E57C2" }
      ],
      "strategies": [
        { "id": "s1", "strategy_key": "ma_crossover", "params": { "fast": 9, "slow": 21, "adx_min": 0.0 }, "visible": true }
      ],
      "drawings": [
        { "id": "d1", "type": "trendline",
          "points": [ { "time": 1760000000, "price": 65000.5 }, { "time": 1760086400, "price": 67250.0 } ],
          "style": { "color": "#2196F3", "width": 1 }, "text": null },
        { "id": "d2", "type": "text", "points": [ { "time": 1760040000, "price": 66000 } ],
          "style": { "color": "#FF5252", "width": 1 }, "text": "breakout?" }
      ]
    },
    {
      "id": "p2",
      "instrument_id": "0b9d…",
      "timeframe": "15m",
      "chart_type": "line",
      "indicators": [],
      "strategies": [],
      "drawings": []
    }
  ],
  "watchlist": ["76aa70d6-069f-42a3-8500-ff324f4da1d1", "0b9d…"],
  "active_panel": "p1"
}
```

| Field | Rules |
|---|---|
| `layout.type` | `1x1` (1 panel), `1x2` (2 side by side), `2x1` (2 stacked), `2x2` (4), `1+2` (3: one large + two stacked) |
| `layout.sizes` | Optional (omitted = equal parts). Relative sizes of the main split: 1 value for `1x1`, 2 for every other layout; each in (0, 1], sum 1 (±0.01) |
| `sync` | `crosshair` (default true), `timeframe`, `instrument` (default false) |
| `panels` | As many as the layout needs |
| `panels[].id`, indicator, strategy and drawing `id`s | 1–40 chars `[A-Za-z0-9_-]`, unique across the whole workspace |
| `panels[].instrument_id` | An existing instrument, or `null` for an empty chart |
| `panels[].timeframe` | `1m`, `5m`, `15m`, `1h`, `4h`, `1d` |
| `panels[].chart_type` | `candles`, `heikin_ashi`, `line`, `area`, `bars` |
| `indicators[]` | ≤ 10 per panel. `name` and `params` as in `GET /indicators`; the stored params are resolved with defaults. `color` `#RRGGBB` or null; `visible` default true |
| `strategies[]` | ≤ 5 per panel. `strategy_key` and `params` as in `GET /strategies`; params resolved with defaults |
| `drawings[]` | ≤ 200 per panel. Points: trendline 2, horizontal 1, vertical 1, rectangle 2, fibonacci 2, text 1. `time` unix seconds, `price` finite. `style.color` `#RRGGBB`, `style.width` 1–10. `text` ≤ 200 chars, required for `text` drawings |
| `watchlist` | ≤ 50 existing instruments, no duplicates |
| `active_panel` | The id of one of the panels |
| whole `state` | ≤ 256 KB as compact JSON |

Unknown fields are rejected, so a typo such as `"colour"` is an error rather than silently lost.

Errors are 422 with FastAPI's format: every problem with its JSON path in `loc`:

```json
{ "detail": [
  { "loc": ["body", "state", "panels", 0, "indicators", 1, "params"],
    "msg": "rsi: length must be between 1 and 1000, got 0", "type": "value_error" },
  { "loc": ["body", "state", "active_panel"], "msg": "no panel with id 'p9'", "type": "value_error" }
] }
```

### Read-only fields and instruments that go away

On read, each panel also has:

- `instrument`: `{id, symbol, source, is_active}`, or `null`;
- `unavailable`: `true` if its instrument was deleted or deactivated.

The workspace also lists `unavailable_instrument_ids` (panels and watchlist). Show these panels
greyed out instead of failing. Inactive instruments may stay in a workspace, and an instrument
that was deleted may stay in the workspace it was already in, so saving never breaks. New
references must exist.

You can send a state you read back unchanged: `instrument` and `unavailable` are accepted on
write and ignored.

## Versions and conflicts

`version` starts at 1 and goes up by one on every **state** change (PUT). Every PUT must say
which version it edited, in the body (`"version": 7`) or as `If-Match: "7"`. The server
applies it only if the workspace is still at that version (one atomic
`UPDATE … WHERE version = 7`). Otherwise:

```http
HTTP/1.1 409 Conflict
ETag: "8"

{ "detail": "Workspace was changed by another client; reload it and apply your change again",
  "current_version": 8, "updated_at": "2026-10-16T09:12:03.120Z" }
```

A PUT without any version is refused with **428**. Rename and default changes (PATCH) do not
change the version; a `version` sent with PATCH is checked the same way.

Client flow:

```text
ws = GET /me/workspaces/{id}                     # remember ws.version
on every user edit (debounced ~1 s):
    res = PUT /me/workspaces/{id} {state: localState, version: ws.version}
    if res.status == 200:
        ws = res.body                            # new version
    elif res.status == 409:
        server = GET /me/workspaces/{id}
        if the user's change still applies cleanly (e.g. a different panel changed):
            localState = merge(server.state, myChange)
            retry PUT with version = server.version
        else:
            ask: "This workspace changed on another device. Reload / Keep mine?"
            # "Keep mine" = PUT localState with version = server.version
    elif res.status == 422:
        show res.body.detail (bug in the client: the path says where)
```

## Live sync between devices

After every successful change the server publishes to the owner's `user:{id}` WebSocket topic
(every connection of the user receives it, see [websocket.md](websocket.md)):

```json
{ "type": "workspace_updated", "workspace_id": "1c3e…", "version": 8, "action": "state_updated",
  "topic": "user:…", "sent_at": 1760600000000 }
```

| `action` | When | `workspace_id` / `version` |
|---|---|---|
| `created` | create, duplicate, import, default created on first GET | new workspace, 1 |
| `state_updated` | PUT | the workspace, new version |
| `renamed` | PATCH name | the workspace, its version |
| `default_changed` | PATCH `is_default`, or the default was deleted | the new default, its version |
| `deleted` | DELETE | the deleted id, `null` |
| `reordered` | PUT order | `null`, `null` (reload the list) |
| `shared`, `unshared` | share links | the workspace, its version |

If the open workspace's `version` is higher than yours, reload it (or merge as above). Ignore
messages about versions you already have (your own PUT also produces one).

## Templates

`template` in POST `/me/workspaces` (without `state`):

| Template | |
|---|---|
| `default` | 1x1: BTC/USDT 1h candles with EMA 20 + EMA 50 and RSI 14; watchlist = the seeded crypto pairs that exist. This is also the workspace created automatically for new users. |
| `blank` | 1x1: BTC/USDT 1h candles without indicators, empty watchlist (used when neither `state` nor `template` is given) |
| `multi_chart` | 2x2: BTC, ETH, BNB and SOL /USDT, 1h, timeframe sync on |

If a seeded instrument does not exist, its panel is empty (`instrument_id: null`).

## Sharing

Analysts, experts and admins can share a workspace read-only. `POST …/share` returns a random
`share_slug`; give other users the link to `GET /workspaces/shared/{slug}`. It shows the
workspace's name, state, `updated_at` and the owner's display name and role, but no user or
workspace ids. Viewers can copy it into their own workspaces with
`POST /workspaces/shared/{slug}/import`. Later changes by the owner do not change copies.
`DELETE …/share` invalidates the link. A link of a deactivated user answers 404.
