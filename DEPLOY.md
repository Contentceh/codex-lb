# Deploying codex-lb next to n8n-install

This directory is the **codex-lb** application sources. During the Sprint 2 cutover, the observed live runtime is the checked-out source tree started with `docker-compose.yml` and the `server` + `frontend` services only.

## Layout

- `docker-compose.yml` — live Sprint 2 cutover stack: builds `server` and `frontend` locally and mounts the preserved Docker volume `localai_codex-lb-data` at `/var/lib/codex-lb`.
- `docker-compose.prod.yml` — **non-cutover/stale for Sprint 2**: still points at `ghcr.io/soju06/codex-lb:1.8.1`. Do not deploy it for the 1.15.0 cutover until it is intentionally updated and revalidated.
- `docker-compose.prod copy.yml` — historical copy with the same stale production image path; do not use for Sprint 2 cutover.

## Environment

1. Copy `deploy.env.example` to `.env` or merge variables from your `n8n-install/.env`:
   - `CODEX_LB_HOSTNAME` — public hostname (OAuth redirect uses `https://<host>/auth/callback`).
   - `GOST_PROXY_URL` / `GOST_NO_PROXY` — optional; same meaning as in n8n-install when using Gost.

Do not commit `.env`.

## Commands

```bash
cd /home/vgoro/codex-lb
docker compose -f docker-compose.yml up -d server frontend
docker compose -f docker-compose.yml ps
curl -fsS http://127.0.0.1:2455/health/live
echo
curl -fsS http://127.0.0.1:2455/health/ready
echo
```

Use `/health/live` first to confirm the process is reachable, then `/health/ready` to confirm dependencies and bridge readiness before authenticated API smoke checks.

After changing `n8n-install/Caddyfile`, reload Caddy in the main stack:

```bash
cd /path/to/n8n-install && docker exec caddy caddy reload --config /etc/caddy/Caddyfile
```

## n8n-install integration

Caddy in `n8n-install` forwards `{$CODEX_LB_HOSTNAME}` to `host.docker.internal:2455`, so this container must keep publishing **2455** (and **1455** for OAuth) on the host.

Remove `codex-lb` from `COMPOSE_PROFILES` in `n8n-install` (already done when migrating).
