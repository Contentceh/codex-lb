# codex-lb / Sprint 1 — Upgrade Foundation to 1.15.0 Implementation Checklist
Repo: `/home/vgoro/codex-lb`
Purpose: Safely converge the current 1.13.0-derived fork with upstream `v1.15.0`, preserve existing Docker data/accounts/settings, and produce a green, reviewable base before adding the PR #498 `gpt-image-2` image API work.

## Sprint scope
Covers: current-state inventory; non-secret runtime baseline; external data-volume backup; preservation of local uncommitted hotfixes; upstream `v1.15.0` merge/rebase; version and migration alignment; Docker compose reconciliation for the observed `server` + `frontend` runtime; backend tests with `ruff`/`ty`; frontend lint/typecheck/test/build; health smoke with existing data | Does not cover: implementing PR #498; exposing `/v1/images/*`; upgrading to 1.16; rotating account tokens/API keys; changing DNS/TLS/reverse proxy; deleting or recreating Docker volumes; public release publishing

## Operating rules for this sprint
- Treat `localai_codex-lb-data` as production state. Back it up outside the repository before any migration or container replacement; never put database or token backups under `docs/`.
- Do not run destructive Docker commands against volumes (`docker volume rm`, `down -v`, `system prune --volumes`) during this sprint.
- Capture `git status --short` and `git diff` before merge work. Preserve the existing non-doc changes in `app/modules/proxy/service.py`, `openspec/specs/responses-api-compat/spec.md`, and `tests/unit/test_proxy_utils.py`.
- Check health in this order around runtime changes: `/health/live`, `/health/ready`, then authenticated API smoke. If `/health/ready` fails, inspect logs before retrying.
- Retry limit: at most 2 container restart attempts per failed smoke, and inspect `docker compose logs --tail=200 server` or equivalent logs between attempts.
- Every implementation issue must end with both tests and linters. Backend acceptance requires relevant `pytest` plus `uvx ruff check .`, `uvx ruff format --check .`, and `uv run ty check`. Frontend acceptance requires `bun run lint`, `bun run typecheck`, `bun run test`, and `bun run build` when frontend files or lockfiles change.
- Keep PR #498 out of this sprint branch except as a fetched comparison reference. Image API work begins only after the 1.15.0 base is green.
- Do not print or commit `.env`, OAuth token JSON, account exports, API keys, database dumps, or encryption keys. Use redacted key names only.

## Phase A — Baseline and state protection
### Issue 1 — Preserve current worktree, refs, and runtime facts
Status: [x] Completed
Files: `docs/codex-lb-update_from_1.13.0-roadmap.md`; `docs/codex-lb-update_from_1.13.0-sprint1-checklist.md`; `app/modules/proxy/service.py`; `openspec/specs/responses-api-compat/spec.md`; `tests/unit/test_proxy_utils.py`; `docker-compose.yml`; `docker-compose.prod.yml`
Checklist:
- [ ] Record current branch, remotes, HEAD, and `git status --short` in a non-secret local note.
- [ ] Save the current non-doc diff to a patch outside the repository or in a private backup path, not as an accidental code commit.
- [ ] Confirm upstream refs exist locally: `v1.13.1`, `v1.14.0`, `v1.14.1`, `v1.15.0`, and `upstream/pr/498` for comparison only.
- [ ] Record running containers and images: expected observed baseline is `codex-lb-server-1` and `codex-lb-frontend-1`.
- [ ] Record redacted environment key names only; do not copy values.
Completed evidence group: [x] docs(upgrade): capture 1.15 upgrade baseline

### Issue 2 — Back up data and identify migration boundaries
Status: [x] Completed
Files: `docker-compose.yml`; `docker-compose.prod.yml`; `app/db/alembic/versions/*`; `app/db/models.py`; `app/core/config/settings.py`; external backup path outside repo
Checklist:
- [ ] Create a timestamped backup directory outside Git, for example `/home/vgoro/codex-lb-backups/YYYYMMDD-HHMMSS/`.
- [ ] Back up Docker volume `localai_codex-lb-data` into that external directory.
- [ ] Verify the backup archive can be listed with `tar tzf` without extracting secrets into the repository.
- [ ] Identify upstream 1.15.0 Alembic additions: request log response lookup index, request log plan type, and merge head.
- [ ] Confirm current deployment uses SQLite-in-volume unless `CODEX_LB_DATABASE_URL` is set in the effective env; document only the safe redacted result.
Completed evidence group: [x] docs(upgrade): document data protection checklist

## Phase B — Upstream 1.15.0 convergence
### Issue 3 — Create upgrade branch and merge upstream v1.15.0
Status: [x] Completed
Files: `pyproject.toml`; `app/__init__.py`; `frontend/package.json`; `uv.lock`; `app/**`; `frontend/**`; `tests/**`; `openspec/**`; `deploy/**`; `docker-compose*.yml`
Checklist:
- [ ] Create an upgrade branch from the current local branch, for example `upgrade/from-1.13.0-to-1.15.0`.
- [ ] Merge `v1.15.0` with a non-fast-forward merge, or rebase only if the team intentionally wants a linear fork history.
- [ ] Resolve conflicts while preserving local runtime assumptions and the existing pre-text `stream_incomplete` retry behavior if still needed.
- [ ] Ensure version markers resolve to `1.15.0` in `pyproject.toml`, `app/__init__.py`, and `frontend/package.json`.
- [ ] Keep PR #498 files out of this merge: no `app/core/openai/images.py`, no `app/modules/proxy/images_service.py`, and no `/v1/images/*` routes unless they are already in upstream 1.15.0.
Completed evidence group: [x] refactor(upgrade): align fork with upstream 1.15.0

### Issue 4 — Reconcile Docker compose with actual runtime
Status: [x] Completed
Files: `docker-compose.yml`; `docker-compose.prod.yml`; `Dockerfile`; `frontend/package.json`; `frontend/bun.lock`; `.env.local` or `.env` read-only/redacted
Checklist:
- [x] Decided: Sprint 1 keeps the observed two-service local build runtime (`server` + `frontend`) and defers any single-server production compose adoption to a separate cutover.
- [ ] Preserve the existing `localai_codex-lb-data` volume name for compatibility.
- [ ] Update health checks to use `/health/ready` where appropriate, while keeping `/health/live` for liveness checks.
- [ ] Preserve required proxy/OAuth env behavior: `CODEX_LB_OAUTH_REDIRECT_URI`, `CODEX_LB_FIREWALL_TRUST_PROXY_HEADERS`, proxy env variables, and `CODEX_LB_HOSTNAME`-derived settings.
- [ ] Ensure the frontend still points to the backend service name used by the selected compose file.
Completed evidence group: [x] chore(docker): align compose runtime for 1.15 upgrade

## Phase C — Data and API compatibility
### Issue 5 — Validate migrations and request-log schema changes
Status: [x] Completed
Files: `app/db/alembic/versions/*`; `app/db/migrate.py`; `app/db/models.py`; `app/modules/request_logs/repository.py`; `tests/integration/test_migrations.py`; `tests/unit/test_db_migrate.py`; `tests/unit/test_request_logs_repository.py`
Checklist:
- [ ] Run Alembic head checks after merge and ensure only expected heads remain.
- [ ] Run migration tests for SQLite and any configured external database path if applicable.
- [ ] Verify request log additions from 1.15.0 do not break existing rows in the current volume.
- [ ] Confirm request log plan type fields are nullable/backfilled safely for old data.
- [ ] Confirm startup migration behavior still fails closed on unsupported schema drift.
Completed evidence group: [x] test(db): verify 1.15 migration compatibility

### Issue 6 — Verify accounts, settings, API keys, and model registry compatibility
Status: [x] Completed
Files: `app/modules/accounts/*`; `app/modules/settings/*`; `app/modules/api_keys/*`; `app/modules/proxy/api.py`; `app/core/openai/model_registry.py`; `tests/integration/test_accounts_api.py`; `tests/integration/test_settings_api.py`; `tests/integration/test_api_keys_api.py`; `tests/integration/test_openai_compat_features.py`
Checklist:
- [ ] Confirm existing account records remain listable and do not require re-import.
- [ ] Confirm dashboard settings and bootstrap/dashboard auth behavior still work after the merge.
- [ ] Confirm existing API keys still authenticate `/v1/models`, `/responses`, and `/chat/completions` according to their configured scopes.
- [ ] Confirm upstream 1.15.0 GPT-5.5/GPT-5.5 Pro model support is present without introducing PR #498 image endpoints.
- [ ] Confirm local `stream_incomplete` retry behavior either has an upstream equivalent or remains covered by a test.
Completed evidence group: [x] test(api): verify 1.15 account and model compatibility

## Phase D — Quality gates and smoke deployment
### Issue 7 — Backend test, lint, and typecheck gate
Status: [x] Completed
Files: `app/**`; `tests/**`; `pyproject.toml`; `uv.lock`
Checklist:
- [ ] Run targeted migration/proxy/account/API-key tests first for fast feedback.
- [ ] Run full unit and integration tests unless a named external dependency blocker is documented.
- [ ] Run `uvx ruff check .` and fix lint issues.
- [ ] Run `uvx ruff format --check .` and format only if needed.
- [ ] Run `uv run ty check` and fix new type diagnostics.
Completed evidence group: [x] test(upgrade): pass backend quality gates for 1.15

### Issue 8 — Frontend test, lint, typecheck, and build gate
Status: [x] Completed
Files: `frontend/package.json`; `frontend/bun.lock`; `frontend/src/**`; `frontend/vite.config.ts`; `frontend/eslint.config.js`
Checklist:
- [ ] Run `bun install --frozen-lockfile` from `frontend/`.
- [ ] Run `bun run lint`.
- [ ] Run `bun run typecheck`.
- [ ] Run `bun run test`.
- [ ] Run `bun run build`.
- [ ] Smoke the dashboard shell against the selected backend service after Docker build.
Completed evidence group: [x] test(frontend): pass frontend quality gates for 1.15

### Issue 9 — Docker smoke with preserved data semantics
Status: [x] Completed
Files: `docker-compose.yml`; `docker-compose.prod.yml`; `Dockerfile`; `frontend/package.json`; external volume backup path; runtime logs
Checklist:
- [ ] Build the selected Docker services without deleting the existing data volume.
- [ ] Start the upgraded stack using the chosen compose file.
- [ ] Check `/health/live` and `/health/ready` locally.
- [ ] Confirm containers are stable for at least one healthcheck interval after startup.
- [ ] Run a minimal authenticated API smoke using an existing API key without printing the key.
- [ ] If smoke fails, stop after 2 restart attempts and document logs plus rollback recommendation.
Completed evidence group: [x] chore(deploy): validate docker smoke for 1.15 base

## Sprint quality gates
- [ ] Current uncommitted pre-sprint code diff is preserved before merge work begins.
- [ ] Docker volume `localai_codex-lb-data` is backed up outside Git and backup listing is verified.
- [ ] Upgrade branch reports `1.15.0` in backend and frontend version markers.
- [ ] Backend gate passes: `uv run pytest tests/unit tests/integration -q` plus `uvx ruff check .`, `uvx ruff format --check .`, and `uv run ty check`.
- [ ] Frontend gate passes: `bun run lint`, `bun run typecheck`, `bun run test`, and `bun run build`.
- [ ] Docker smoke passes with `/health/live` and `/health/ready`.
- [ ] Existing accounts/settings/API keys are verified against preserved data.
- [x] PR #498 image API files/routes are not included in Sprint 1.
- [ ] Rollback path is documented before any live cutover is attempted in Sprint 2.

## Quick verification commands
- `cd /home/vgoro/codex-lb && git status --short && git branch --show-current && git rev-parse --short HEAD && git remote -v`
- `cd /home/vgoro/codex-lb && docker compose -f docker-compose.yml ps && curl -fsS http://127.0.0.1:2455/health && echo && curl -fsS http://127.0.0.1:2455/health/ready && echo`
- `cd /home/vgoro/codex-lb && BACKUP_DIR="/home/vgoro/codex-lb-backups/$(date +%Y%m%d-%H%M%S)" && mkdir -p "$BACKUP_DIR" && docker run --rm -v localai_codex-lb-data:/data:ro -v "$BACKUP_DIR:/backup" alpine sh -c 'tar czf /backup/localai_codex-lb-data.tgz -C /data .' && tar tzf "$BACKUP_DIR/localai_codex-lb-data.tgz" >/dev/null`
- `cd /home/vgoro/codex-lb && git fetch upstream refs/tags/v1.15.0:refs/tags/v1.15.0 refs/pull/498/head:refs/remotes/upstream/pr/498 && git switch -c upgrade/from-1.13.0-to-1.15.0 && git merge --no-ff v1.15.0`
- `cd /home/vgoro/codex-lb && uv run pytest tests/unit tests/integration -q && uvx ruff check . && uvx ruff format --check . && uv run ty check`
- `cd /home/vgoro/codex-lb/frontend && bun install --frozen-lockfile && bun run lint && bun run typecheck && bun run test && bun run build`
- `cd /home/vgoro/codex-lb && docker compose -f docker-compose.yml build server frontend && docker compose -f docker-compose.yml up -d server frontend && docker compose -f docker-compose.yml ps && curl -fsS http://127.0.0.1:2455/health/live && echo && curl -fsS http://127.0.0.1:2455/health/ready && echo`

## Important gotchas
- The observed runtime is `codex-lb-server-1` + `codex-lb-frontend-1`, but `docker-compose.prod.yml` still references a stale single image `ghcr.io/soju06/codex-lb:1.8.1`. Reconcile compose before cutover; do not deploy the wrong file by habit.
- Existing accounts/settings depend on the `localai_codex-lb-data` volume and encryption key material. A fresh volume or missing key can look like account loss even if migrations succeed.
- PR #498 is a large patch over `v1.15.0` and touches proxy routing, OAuth, request logs, strict schemas, and tests. Keeping it out of Sprint 1 is what makes the later 1.16 rebase tractable.
