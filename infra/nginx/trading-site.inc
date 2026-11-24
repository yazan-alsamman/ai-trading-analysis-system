# The site itself, shared by both server blocks of default.conf (port 80 = :8080 on the VPS,
# port 8090 = the host's HTTPS proxy), so they cannot drift. Not a *.conf file: nginx loads
# every conf.d/*.conf at the http level, this one only through `include` inside a server.
#
# Each including server sets $fwd_proto (the scheme the client used) before the include; the
# client address is $remote_addr (on 8090, already the real client from the host proxy, via the
# realip module).

server_tokens off;  # no nginx version in headers and error pages

add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header X-Frame-Options $frame_options always;
add_header Content-Security-Policy $api_csp always;

client_max_body_size 1m;

# Resolve "backend" through Docker's DNS at request time (cached 10 s) instead of once at
# startup: after `docker compose up -d --build backend` the container gets a new IP, and a
# static upstream kept proxying to the old one (502) until Nginx was restarted.
# proxy_pass with a variable and no URI part forwards the original URI and query string.
resolver 127.0.0.11 valid=10s ipv6=off;
resolver_timeout 5s;
set $backend http://backend:8000;

# The client address for the rate limiter. The backend trusts X-Forwarded-For only from
# this proxy (uvicorn --forwarded-allow-ips, docker-compose.yml). Overwrite, never append
# ($proxy_add_x_forwarded_for): a client-sent X-Forwarded-For must be dropped here.
# $http_host keeps the port the client used (:8080 on the VPS; the bare name behind the host
# proxy); $host would drop it and absolute URLs built by the app (the demo checkout page) would
# point at port 80.
proxy_set_header Host $http_host;
proxy_set_header X-Forwarded-Host $http_host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $remote_addr;
proxy_set_header X-Forwarded-Proto $fwd_proto;

location /api/ {
    client_max_body_size 2m;  # candle batches (5,000) and the biggest JSON bodies
    proxy_pass $backend;
}

# the AI side's news ingestion: up to 200 articles with summaries per request
location /api/v1/ingest/ {
    client_max_body_size 10m;
    proxy_pass $backend;
}

# chart image analysis (Y14, docs/chart-analysis.md): uploads up to 5 MB (6m with the multipart
# overhead) and a synchronous model call of up to 45 s; every other route keeps its limits
location /api/v1/analysis/chart-image {
    client_max_body_size 6m;
    proxy_read_timeout 60s;
    proxy_pass $backend;
}

# economic-calendar history upload (admin, CSV up to 50 MB, docs/economic-calendar.md):
# buffered to disk here, then imported in batches by the backend (minutes, not seconds)
location = /api/v1/admin/calendar/import {
    client_max_body_size 51m;
    proxy_read_timeout 600s;
    proxy_send_timeout 600s;
    proxy_pass $backend;
}

# WebSocket hub /ws/market (Y04, docs/websocket.md)
location /ws/ {
    proxy_pass $backend;
    proxy_http_version 1.1;
    # proxy_set_header in a location replaces the inherited ones, so repeat them all
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $http_host;
    proxy_set_header X-Forwarded-Host $http_host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header X-Forwarded-Proto $fwd_proto;
    # the server sends a heartbeat every 25s; do not cut idle sockets after the 60s default
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
}

# Swagger UI and the schema exist only in development (the app disables them in production)
location /docs { proxy_pass $backend; }
location /redoc { proxy_pass $backend; }
location /openapi.json { proxy_pass $backend; }

# The web client (web/, built into this container's image by deploy.yml). Routing is
# client-side, so every other path falls back to index.html. `expires` (not add_header)
# sets Cache-Control, so the security headers above are still inherited here.
root /usr/share/nginx/html;
location /assets/ {
    expires 1y;  # content-hashed file names
    try_files $uri =404;
}
location / {
    expires -1;  # index.html: always revalidate, so a deploy shows up at once
    try_files $uri /index.html;
}
