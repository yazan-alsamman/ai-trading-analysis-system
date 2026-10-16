#!/usr/bin/env bash
# Read-only inspection of the shared VPS. Changes nothing: only reads system state.
set -u
section() { printf '\n===== %s =====\n' "$1"; }

section "OS / resources"
cat /etc/os-release 2>/dev/null | grep -E '^(PRETTY_NAME|VERSION_ID)='
uname -r; nproc; free -h; df -h / /var/lib/docker 2>/dev/null; uptime

section "Docker"
docker version --format 'server {{.Server.Version}}' 2>&1
docker info --format 'root={{.DockerRootDir}} driver={{.Driver}} containers={{.Containers}} images={{.Images}}' 2>&1

section "Running containers (name | image | ports | status)"
docker ps --format '{{.Names}} | {{.Image}} | {{.Ports}} | {{.Status}}'

section "Compose projects"
docker compose ls 2>&1

section "Docker networks + subnets"
for n in $(docker network ls -q); do
  docker network inspect "$n" --format '{{.Name}} {{range .IPAM.Config}}{{.Subnet}} {{end}}'
done

section "Container resource usage"
docker stats --no-stream --format '{{.Name}} cpu={{.CPUPerc}} mem={{.MemUsage}}'

section "Listening TCP ports (host)"
ss -ltnH 2>/dev/null | awk '{print $4}' | sort -u

section "Reverse proxy detection"
for b in nginx caddy apache2 httpd traefik haproxy; do
  command -v "$b" >/dev/null 2>&1 && echo "binary: $b ($(command -v $b))"
done
systemctl is-active nginx caddy apache2 2>/dev/null | paste -sd' ' - | sed 's/^/systemd nginx caddy apache2: /'
ls -1 /etc/nginx/sites-enabled /etc/nginx/conf.d 2>/dev/null
ls -1 /etc/caddy 2>/dev/null
docker ps --format '{{.Names}} {{.Image}}' | grep -Ei 'nginx|traefik|caddy|proxy|haproxy' || echo "no proxy container"

section "Server names in nginx configs (domains already served)"
grep -rhoE 'server_name[^;]+' /etc/nginx/ 2>/dev/null | sort -u

section "TLS certificates (certbot)"
ls -1 /etc/letsencrypt/live 2>/dev/null || echo "no /etc/letsencrypt/live readable"

section "Firewall"
command -v ufw >/dev/null && (ufw status 2>&1 | head -20) || echo "ufw not present"

section "Our target dir"
ls -la /opt/trading
