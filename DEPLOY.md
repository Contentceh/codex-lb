# Deploying codex-lb next to n8n-install

This directory is the **codex-lb** application sources. Production runtime uses the published image `ghcr.io/soju06/codex-lb` (same version as previously wired in `n8n-install`).

## Layout

- `docker-compose.yml` — upstream dev stack (build + hot reload).
- `docker-compose.prod.yml` — production: GHCR image, ports **2455** (API) and **1455** (OAuth callback), persistent data in Docker volume `localai_codex-lb-data` (created earlier by the `localai` compose project).

## Environment

1. Copy `deploy.env.example` to `.env` or merge variables from your `n8n-install/.env`:
   - `CODEX_LB_HOSTNAME` — public hostname (OAuth redirect uses `https://<host>/auth/callback`).
   - `GOST_PROXY_URL` / `GOST_NO_PROXY` — optional; same meaning as in n8n-install when using Gost.

Do not commit `.env`.

## Commands

```bash
cd /home/vgoro/codex-lb
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps
curl -fsS http://127.0.0.1:2455/health
```

After changing `n8n-install/Caddyfile`, reload Caddy in the main stack:

```bash
cd /path/to/n8n-install && docker exec caddy caddy reload --config /etc/caddy/Caddyfile
```

## n8n-install integration

Caddy in `n8n-install` forwards `{$CODEX_LB_HOSTNAME}` to `host.docker.internal:2455`, so this container must keep publishing **2455** (and **1455** for OAuth) on the host.

Remove `codex-lb` from `COMPOSE_PROFILES` in `n8n-install` (already done when migrating).
