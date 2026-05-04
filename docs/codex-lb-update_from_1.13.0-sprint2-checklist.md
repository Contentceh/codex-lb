# codex-lb / Sprint 2 — Docker Cutover and Live 1.15.0 Compatibility Validation Implementation Checklist
Repo: /home/vgoro/codex-lb
Purpose: Validate the upgraded 1.15.0 deployment on the real Docker runtime while preserving the existing `localai_codex-lb-data` accounts/settings volume, confirming dashboard/API compatibility, and keeping a clean rollback path before any PR #498 image work.

## Sprint scope
Covers:
- Confirm Sprint 1 artifacts, current Git state, and active Docker runtime before touching containers.
- Take a fresh non-secret runtime baseline and fresh preserved-volume backup outside the repository.
- Reconcile the production compose/runtime story for the observed two-service stack (`server` + `frontend`) and the external `localai_codex-lb-data` volume.
- Rebuild/restart only the `codex-lb` `server` and `frontend` services from the 1.15.0 upgrade branch.
- Validate `/health/live`, `/health/ready`, dashboard surfaces, accounts/settings/API-key visibility, model list, request logs, usage surfaces, and one minimal authenticated proxy call without printing secrets.
- Capture redacted post-cutover evidence and rollback notes outside Git when they may contain sensitive operational details.

Does not cover:
- PR #498 or any `/v1/images` / `gpt-image-2` routes, schemas, settings, or tests.
- Updating beyond upstream `v1.15.0` or rebasing toward a future `1.16` release.
- Changing account credentials, OAuth tokens, dashboard users/passwords, API keys, encryption keys, or production settings except read-only verification.
- Deleting, recreating, renaming, or pruning Docker volumes.
- Refactoring backend/frontend code unrelated to deployment validation.

## Operating rules for this sprint
- Work on `Debian-n8n` in `/home/vgoro/codex-lb`; do not run project commands on the local OpenClaw host.
- Documentation is the only allowed direct edit during planning. During execution, code changes are allowed only when a specific Sprint 2 issue requires them; no unrelated code cleanup.
- Never print or commit `.env`, OAuth token JSON, account exports, API keys, database dumps, encryption keys, or full Authorization headers.
- Use redacted artifacts under `/home/vgoro/codex-lb-backups/<timestamp>/` for runtime evidence; keep secret-bearing operational notes outside Git.
- Before restart/cutover, verify the active volume is still `localai_codex-lb-data` and create a fresh backup. Do not run `docker volume rm`, `docker compose down -v`, or `docker system prune --volumes`.
- Restart only `server` and `frontend` with `docker compose -f docker-compose.yml ...`; do not stop unrelated Docker services.
- Health order is strict: call `/health/live` first, then `/health/ready`. If `/health/ready` fails, inspect server logs before retrying; allow at most two container restart attempts per failed smoke.
- Authenticated API smoke must source an existing valid key without echoing it, writing it to shell history, or storing it unredacted in artifacts.
- Every issue that changes code or compose must have tests/linters in its artifact: at minimum `git diff --check`, targeted backend `pytest` plus `ruff check` for touched backend paths, or frontend `bun run lint && bun run typecheck && bun run test` for touched frontend paths.
- Because `uv`/`uvx` may be absent from PATH on `Debian-n8n`, prepend `export PATH="/tmp/codex-lb-uv-tool/bin:$PATH"` before backend verification commands. If a command mutates `uv.lock` without an issue explicitly requiring it, restore `uv.lock` before marking the issue complete.
- Use `bun` for frontend verification; do not assume `node` or `bunx` are available.

## Phase A — Pre-cutover state and safety net
### Issue 1 — Confirm Sprint 1 completion and repository state
Status: [x] Completed
Files:
- docs/codex-lb-update_from_1.13.0-roadmap.md
- docs/codex-lb-update_from_1.13.0-sprint1-checklist.md
- docs/codex-lb-update_from_1.13.0-sprint1-todo.md
- docs/codex-lb-update_from_1.13.0-sprint2-checklist.md
Checklist:
- [x] Verify Sprint 1 is marked complete in the roadmap and Sprint 1 checklist.
- [x] Verify Sprint 1 TODO has `29` completed task lines and `0` open task lines.
- [x] Record current branch, HEAD, remotes, and `git status --short` in a redacted Sprint 2 baseline artifact.
- [x] Confirm PR #498 image API files/routes are still absent from the Sprint 2 baseline.
Completed in final docs commit: [x] docs(upgrade): capture sprint 2 baseline

### Issue 2 — Capture fresh Docker runtime and volume baseline
Status: [x] Completed
Files:
- docker-compose.yml
- docker-compose.prod.yml
- DEPLOY.md
- README.md
Checklist:
- [x] Record `docker compose -f docker-compose.yml ps`, relevant container image IDs, and mounts for `codex-lb-server-1` and `codex-lb-frontend-1`.
- [x] Confirm `localai_codex-lb-data` is the volume mounted at `/var/lib/codex-lb`.
- [x] Record `/health/live` then `/health/ready` responses before any restart.
- [x] Redact logs and scan the artifact for `sk-clb`, `Bearer `, OAuth token fields, and encryption-key-like values.
Completed in final docs commit: [x] docs(upgrade): record sprint 2 runtime baseline

### Issue 3 — Take a fresh preserved-volume backup
Status: [x] Completed
Files:
- /home/vgoro/codex-lb-backups/<timestamp>/
Checklist:
- [x] Create a new timestamped backup directory outside the repository.
- [x] Archive `localai_codex-lb-data` read-only into `localai_codex-lb-data.tgz` without deleting or recreating the volume.
- [x] Verify the archive with `tar tzf` and record size/checksum in a non-secret artifact.
- [x] Record the backup path for rollback notes.
Completed in final docs commit: [x] docs(upgrade): document sprint 2 backup location

## Phase B — Compose/runtime reconciliation
### Issue 4 — Finalize two-service compose strategy for live runtime
Status: [x] Completed
Files:
- docker-compose.yml
- docker-compose.prod.yml
- docker-compose.prod copy.yml
- DEPLOY.md
- README.md
Checklist:
- [x] Confirm `docker-compose.yml` remains the cutover file for `server` + `frontend` and uses `localai_codex-lb-data` by name.
- [x] Decide whether prod compose files should be clearly marked stale/non-cutover or aligned to the same external-volume strategy before operators can use them safely.
- [x] Ensure docs warn against the stale `ghcr.io/soju06/codex-lb:1.8.1` production image path until intentionally updated.
- [x] Run `docker compose -f docker-compose.yml config >/dev/null` and, if prod compose files are edited, `docker compose -f docker-compose.prod.yml config >/dev/null`.
- [x] Run `git diff --check` and targeted lint/checks for any touched YAML/docs paths where available.
Decision: `docker-compose.yml` is the only Sprint 2 cutover file. `docker-compose.prod.yml` and `docker-compose.prod copy.yml` are explicitly non-cutover/stale for Sprint 2 because they still reference `ghcr.io/soju06/codex-lb:1.8.1`; do not deploy either file until intentionally updated and revalidated.
Completed in final docs commit: [x] chore(docker): document live compose cutover strategy

### Issue 5 — Confirm healthcheck and startup semantics after compose reconciliation
Status: [x] Completed
Files:
- docker-compose.yml
- docker-compose.prod.yml
- DEPLOY.md
- README.md
- app/modules/health/api.py
- app/modules/health/schemas.py
Checklist:
- [x] Confirm compose healthchecks use `/health/ready` while operational smoke keeps `/health/live` before `/health/ready`.
- [x] Confirm legacy `/health` remains compatibility-only and is not used as the deployment readiness gate.
- [x] If health-related docs/compose changed, run `docker compose -f docker-compose.yml config >/dev/null`, `git diff --check`, and `uvx ruff check app/modules/health`.
- [x] Record the exact expected JSON fields from live and ready endpoints in the Sprint 2 evidence artifact.
Evidence: `/home/vgoro/codex-lb-backups/20260504-073434/sprint2/healthcheck-semantics.txt` records `/health/ready` compose/docs references, `/health/live` then `/health/ready` smoke ordering, expected endpoint JSON fields (`status`, optional `checks`, optional `bridge_ring` with ring metadata), legacy `/health` compatibility-only status, and `uvx ruff check app/modules/health` PASS.
Completed in final docs commit: [x] docs(deploy): lock live and ready health gates

## Phase C — Cutover execution
### Issue 6 — Rebuild final 1.15.0 server and frontend images
Status: [x] Completed
Files:
- Dockerfile
- frontend/Dockerfile
- docker-compose.yml
- pyproject.toml
- app/__init__.py
- frontend/package.json
Checklist:
- [x] Confirm backend and frontend version markers are `1.15.0` before build.
- [x] Run `docker compose -f docker-compose.yml build server frontend` without any volume deletion commands.
- [x] Record new image IDs/digests/sizes for `codex-lb-server:latest` and `codex-lb-frontend:latest`.
- [x] Verify `localai_codex-lb-data` still exists after build.
Completed in final docs commit: [x] chore(deploy): record final sprint 2 image build

### Issue 7 — Restart only the codex-lb stack on the preserved data volume
Status: [x] Completed
Files:
- docker-compose.yml
- /home/vgoro/codex-lb-backups/<timestamp>/runtime-cutover.log
Checklist:
- [x] Run `docker compose -f docker-compose.yml up -d server frontend` and do not use `down -v`.
- [x] Verify only `codex-lb-server-1` and `codex-lb-frontend-1` were recreated/started.
- [x] Inspect mounts and confirm `localai_codex-lb-data -> /var/lib/codex-lb` is still present.
- [x] Capture `docker compose -f docker-compose.yml ps` and redacted `docker inspect` summary.
Completed in final docs commit: [x] chore(deploy): record live stack restart

### Issue 8 — Validate live and ready health after cutover
Status: [x] Completed
Files:
- app/modules/health/api.py
- /home/vgoro/codex-lb-backups/<timestamp>/health-cutover.log
Checklist:
- [x] Call `curl -fsS http://127.0.0.1:2455/health/live` first.
- [x] Call `curl -fsS http://127.0.0.1:2455/health/ready` second.
- [x] If ready fails, inspect `docker compose -f docker-compose.yml logs --tail=200 server` before any retry.
- [x] Record final health responses and restart-attempt count in the evidence artifact.
Completed in final docs commit: [x] test(deploy): verify cutover health gates

## Phase D — Data compatibility validation
### Issue 9 — Verify dashboard settings and account data survive cutover
Status: [x] Completed
Files:
- app/modules/accounts/api.py
- app/modules/accounts/schemas.py
- app/modules/settings/api.py
- app/modules/settings/schemas.py
- frontend/src/features/accounts/
- frontend/src/features/settings/
Checklist:
- [x] Use authenticated dashboard/API access without printing credentials to verify settings are readable.
- [x] Verify account list count and non-secret account metadata remain present.
- [x] Verify no OAuth token JSON, account secret, or encryption key is exported into artifacts.
- [x] Run or cite passing targeted gates: `uv run pytest tests/integration/test_accounts_api.py tests/integration/test_settings_api.py -q`, `uvx ruff check app/modules/accounts app/modules/settings tests/integration/test_accounts_api.py tests/integration/test_settings_api.py`, and relevant frontend `bun run lint && bun run typecheck && bun run test` if frontend files changed.
Completed in final docs commit: [x] test(upgrade): verify account and settings compatibility

### Issue 10 — Verify API-key, model-list, and auth behavior without exposing keys
Status: [x] Completed
Files:
- app/modules/api_keys/api.py
- app/modules/api_keys/service.py
- app/core/auth/dependencies.py
- app/modules/proxy/api.py
- frontend/src/features/api-keys/
Checklist:
- [x] Verify existing API-key records are visible through dashboard/API metadata without printing token values.
- [x] Run authenticated `/v1/models` smoke using an existing valid key sourced without echoing the secret.
- [x] Confirm unauthorized or invalid-key behavior remains a controlled 401 without logging the supplied token.
- [x] Run or cite passing targeted gates: `uv run pytest tests/integration/test_api_keys_api.py tests/integration/test_auth_middleware.py tests/integration/test_v1_models.py -q`, `uvx ruff check app/modules/api_keys app/core/auth app/modules/proxy tests/integration/test_api_keys_api.py tests/integration/test_auth_middleware.py tests/integration/test_v1_models.py`, and frontend API-key tests if frontend files changed.
Completed in final docs commit: [x] test(upgrade): verify api key auth and model list

### Issue 11 — Verify request logs and usage surfaces after live proxy smoke
Status: [x] Completed
Files:
- app/modules/request_logs/api.py
- app/modules/request_logs/repository.py
- app/modules/usage/api.py
- app/modules/usage/repository.py
- frontend/src/features/dashboard/
- frontend/src/features/api-keys/
Checklist:
- [x] Run one minimal authenticated `/v1/chat/completions` smoke and store only redacted response metadata.
- [x] Verify request logs show the new smoke entry with non-secret model/status metadata.
- [x] Verify usage summary/window endpoints still return sane non-secret data.
- [x] Run or cite passing targeted gates: `uv run pytest tests/integration/test_request_logs_api.py tests/integration/test_request_logs_filters.py tests/integration/test_usage_api.py tests/integration/test_v1_usage.py tests/unit/test_request_logs_repository.py -q` and `uvx ruff check app/modules/request_logs app/modules/usage tests/integration/test_request_logs_api.py tests/integration/test_request_logs_filters.py tests/integration/test_usage_api.py tests/integration/test_v1_usage.py tests/unit/test_request_logs_repository.py`.
Completed in final docs commit: [x] test(upgrade): verify request logs and usage after smoke

## Phase E — Post-cutover evidence and rollback readiness
### Issue 12 — Capture post-cutover stability logs and secret scan
Status: [x] Completed
Files:
- /home/vgoro/codex-lb-backups/<timestamp>/post-cutover-state.txt
Checklist:
- [x] Capture `docker compose -f docker-compose.yml ps` and `docker compose -f docker-compose.yml logs --tail=200 server frontend` after smoke.
- [x] Redact logs before writing final artifact.
- [x] Confirm both containers are running, server is healthy, and no crash loops are present.
- [x] Scan artifacts for `sk-clb`, unredacted `Bearer`, OAuth token fields, and database/encryption-key material.
Completed in final docs commit: [x] docs(upgrade): capture post cutover stability evidence

### Issue 13 — Update rollback notes for the live Sprint 2 cutover
Status: [x] Completed
Files:
- /home/vgoro/codex-lb-backups/<timestamp>/rollback-sprint2.md
- docs/codex-lb-update_from_1.13.0-sprint2-checklist.md
Checklist:
- [x] Record previous Sprint 1 commit, Sprint 2 cutover commit, image IDs/digests, preserved volume name, and fresh backup archive path.
- [x] Document non-destructive rollback: stop/recreate containers without deleting volumes, check out prior commit, rebuild/start `server frontend`, then verify `/health/live` and `/health/ready`.
- [x] Document that backup restore is a last resort and requires a separate safety copy before overwriting the volume.
- [x] Keep any secret-bearing rollback notes outside Git; Git docs may link paths only.
Completed in final docs commit: [x] docs(upgrade): document sprint 2 rollback path

### Issue 14 — Produce Sprint 2 evidence bundle and completion marker
Status: [x] Completed
Files:
- docs/codex-lb-update_from_1.13.0-roadmap.md
- docs/codex-lb-update_from_1.13.0-sprint2-checklist.md
- /home/vgoro/codex-lb-backups/20260504-073434/sprint2/sprint2-evidence.md
Checklist:
- [x] Create a redacted evidence bundle linking baseline, backup, compose validation, build, health, dashboard/API checks, proxy smoke, logs, and rollback notes.
- [x] Verify Sprint 2 checklist issues are complete and quality gates passed.
- [x] Mark Sprint 2 complete in the roadmap only after evidence and rollback notes exist.
- [x] Run `git diff --check` and create a clean docs commit for Sprint 2 completion.
Evidence: `/home/vgoro/codex-lb-backups/20260504-073434/sprint2/sprint2-evidence.md` links Sprint 2 baseline, backup, compose validation, build, cutover, health, dashboard/API smokes, tests/linters, logs, rollback, dirty-code review, and secret scan.
Completed in final docs commit: [x] docs(upgrade): complete sprint 2 evidence

## Sprint quality gates — Completed — Completed
- [x] Roadmap points to `docs/codex-lb-update_from_1.13.0-sprint2-checklist.md` as the current first incomplete sprint plan.
- [x] A fresh Sprint 2 backup archive for `localai_codex-lb-data` exists outside Git and passes archive listing verification.
- [x] `docker compose -f docker-compose.yml config >/dev/null` succeeds.
- [x] If prod compose files are edited, `docker compose -f docker-compose.prod.yml config >/dev/null` succeeds or the file is explicitly documented as non-cutover/stale.
- [x] Final build for `server` and `frontend` succeeds without deleting/recreating volumes.
- [x] Runtime uses `codex-lb-server-1` and `codex-lb-frontend-1` with `localai_codex-lb-data` mounted at `/var/lib/codex-lb`.
- [x] `/health/live` and `/health/ready` both return successful responses after cutover.
- [x] Existing accounts, settings, API-key metadata, model list, request logs, and usage surfaces are verified without exposing secrets.
- [x] Minimal authenticated `/v1/models` and `/v1/chat/completions` smoke tests pass with redacted evidence.
- [x] Targeted backend tests and ruff checks for touched/runtime-critical areas pass; frontend lint/typecheck/test pass if frontend files change.
- [x] `git diff --check` passes.
- [x] Post-cutover logs show no crash loops and secret scans report OK.
- [x] PR #498 image API work remains out of Sprint 2.
- [x] Rollback path and fresh backup path are documented without committing secrets.

## Quick verification commands
- `cd /home/vgoro/codex-lb && git status --short --branch && git rev-parse HEAD && git remote -v`
- `cd /home/vgoro/codex-lb && python3 - <<'PY'
from pathlib import Path
s=Path('docs/codex-lb-update_from_1.13.0-sprint1-todo.md').read_text().splitlines()
print('done', sum(1 for line in s if line.startswith('- [x]')))
print('open', sum(1 for line in s if line.startswith('- [' + ' ]')))
PY`
- `cd /home/vgoro/codex-lb && docker compose -f docker-compose.yml config >/dev/null && docker compose -f docker-compose.yml ps`
- `cd /home/vgoro/codex-lb && curl -fsS http://127.0.0.1:2455/health/live && echo && curl -fsS http://127.0.0.1:2455/health/ready && echo`
- `cd /home/vgoro/codex-lb && BACKUP_DIR="/home/vgoro/codex-lb-backups/$(date +%Y%m%d-%H%M%S)-sprint2" && mkdir -p "$BACKUP_DIR" && docker run --rm -v localai_codex-lb-data:/data:ro -v "$BACKUP_DIR:/backup" alpine sh -c 'tar czf /backup/localai_codex-lb-data.tgz -C /data .' && tar tzf "$BACKUP_DIR/localai_codex-lb-data.tgz" >/dev/null && du -h "$BACKUP_DIR/localai_codex-lb-data.tgz"`
- `cd /home/vgoro/codex-lb && export PATH="/tmp/codex-lb-uv-tool/bin:$PATH" && uv run pytest tests/integration/test_accounts_api.py tests/integration/test_settings_api.py tests/integration/test_api_keys_api.py tests/integration/test_auth_middleware.py tests/integration/test_v1_models.py tests/integration/test_request_logs_api.py tests/integration/test_usage_api.py tests/unit/test_request_logs_repository.py -q && uvx ruff check app/modules/accounts app/modules/settings app/modules/api_keys app/core/auth app/modules/proxy app/modules/request_logs app/modules/usage tests/integration/test_accounts_api.py tests/integration/test_settings_api.py tests/integration/test_api_keys_api.py tests/integration/test_auth_middleware.py tests/integration/test_v1_models.py tests/integration/test_request_logs_api.py tests/integration/test_usage_api.py tests/unit/test_request_logs_repository.py`
- `cd /home/vgoro/codex-lb/frontend && bun run lint && bun run typecheck && bun run test`
- `cd /home/vgoro/codex-lb && docker compose -f docker-compose.yml build server frontend && docker compose -f docker-compose.yml up -d server frontend && docker compose -f docker-compose.yml ps`
- `cd /home/vgoro/codex-lb && git diff --check`

## Important gotchas
- `docker-compose.yml` is the observed live two-service runtime, while `docker-compose.prod.yml` and `docker-compose.prod copy.yml` still contain the stale `ghcr.io/soju06/codex-lb:1.8.1` image path; using the wrong compose file can downgrade or replace the upgraded stack.
- The current preserved data volume is named `localai_codex-lb-data` even though compose may warn it was created for project `localai`; this warning is expected, but a new unnamed/default volume would look like account/settings loss.
- Authenticated smoke must not leak tokens: do not echo Bearer values, do not store shell commands with literal API keys, and scan artifacts for `sk-clb` and `Bearer ` before marking issues complete.
- `/health/live` only proves the process is alive; `/health/ready` is the readiness gate and includes database plus bridge-ring state. Inspect logs before retrying if ready fails.
- Frontend tooling uses `bun`; `node`/`bunx` may not exist on `Debian-n8n`. Backend tooling may require `/tmp/codex-lb-uv-tool/bin` on PATH.
