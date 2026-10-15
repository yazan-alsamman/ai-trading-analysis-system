# Deployment

## Local development

```bash
pnpm install
pnpm dev                 # http://localhost:5173 (demo mode)
```

## Production build

```bash
pnpm build               # tsc -b + vite build → dist/
pnpm preview             # serve dist/ at http://localhost:4173
```

`dist/` is a static site: `index.html` plus hashed assets. Measured on 15 Oct 2026 (sizes are gzip):

| Chunk | Size (gzip) | Notes |
| --- | --- | --- |
| App code (`index-*.js`) | ~64 KB | Workspace and shared code |
| `react-*.js` | ~100 KB | Long-cached vendor chunk |
| `charts-*.js` | ~57 KB | Lightweight Charts engine |
| `zod-*.js` | ~14 KB | |
| CSS | ~11 KB | |
| Each secondary page | 0.5–5 KB | Lazy-loaded on first visit |
| Fonts | woff2 files | Self-hosted, cached |

## Hosting requirements

1. **SPA fallback.** Every unknown path must serve `index.html`, because routing is client-side (`/signals`, `/community/news`, …):
   - **Nginx:** `try_files $uri /index.html;`
   - **Laravel (same domain):** serve `dist/` from `public/` with a catch-all web route that returns `index.html` for non-API paths.
   - **Netlify / Vercel / Cloudflare Pages:** enable the SPA rewrite to `/index.html`.
2. **Caching.**
   - `assets/*` are content-hashed: `Cache-Control: public, max-age=31536000, immutable`.
   - `index.html`: `no-cache`.
3. **HTTPS.** Required in production. Authentication tokens must never travel over HTTP.
4. **Environment variables are build-time.** Set `VITE_DATA_SOURCE` and `VITE_API_BASE_URL` before `pnpm build`. Changing them requires a rebuild.
5. **CORS.** If the API is on a different origin, the backend must allow it (Laravel `config/cors.php`). Hosting the web app and the API on the same domain avoids CORS entirely.

## Suggested release flow (when GitHub is set up)

1. CI on every push runs `pnpm install --frozen-lockfile && pnpm check && pnpm e2e`.
2. Build with production environment variables, then upload `dist/`.
3. Smoke test:
   - Sign in.
   - Workspace loads real data, and **no "Simulated" labels appear** in API mode.
   - Alerts CRUD works.

Nothing has been published yet. The repository is local only (`git init`, no remote, no commits).
