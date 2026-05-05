# codex-lb / Sprint 5 — 1.16 Readiness and Upstream Alignment Implementation Checklist
Repo: /home/vgoro/codex-lb
Purpose: Prepare a low-risk path from the live `1.15.0` + PR #498 image branch to upstream `1.16` once it is published, while preserving live account/settings data and minimizing long-term fork burden.

## Sprint scope
Covers:
- Upstream release availability tracking for `v1.16*`, including an explicit no-tag blocker if no official upstream ref exists.
- Current live baseline capture for branch, commit, Docker services, compose strategy, health endpoints, and non-secret image/runtime settings.
- Delta mapping between `feature/pr-498-images-api-on-1.15.0`, `v1.15.0`, `upstream/pr/498`, `upstream/main`, and a future `v1.16` tag or release candidate.
- A drop/rebase/retain decision matrix for PR #498-derived image code, local hotfixes, request-log/accounting changes, API-key model policy, and Docker/frontend changes.
- Candidate-branch rules, validation gates, rollback plan, and evidence requirements for a later 1.16 alignment or cutover.
- Tests plus linters for any candidate validation: backend `pytest` with `ruff`, and frontend lint/typecheck/test/build.

Does not cover:
- Blindly changing project code before the upstream ref, patch-retirement decision, and issue boundary are documented.
- Live cutover to `1.16` without operator approval and a successful non-live validation bundle.
- Docker volume deletion, recreation, pruning, renaming, or any operation that risks `localai_codex-lb-data`.
- Exposing or committing raw API keys, OAuth token JSON, `.env.local`, database dumps, encryption key material, full Authorization headers, generated binary images, or `b64_json`.
- Adding new image features beyond the upstream/PR #498 alignment goal.
- Using stale `docker-compose.prod.yml` as the deployment source without reconciling it with the observed two-service runtime.

## Operating rules for this sprint
- Work on `Debian-n8n` in `/home/vgoro/codex-lb`; do not run project commands on the local OpenClaw host.
- This sprint is allowed to create and update documentation under `docs/` and non-secret evidence under `/home/vgoro/codex-lb-backups/<timestamp>/sprint5/`.
- Do not edit project code until the relevant Sprint 5 implementation issue is selected by the operator. The Tech Lead planning step only writes documentation.
- Treat `feature/pr-498-images-api-on-1.15.0` as the current live image-candidate branch unless the operator selects another branch.
- First gate for `1.16` work is release availability: if `git ls-remote --tags upstream 'refs/tags/v1.16*'` returns nothing, record the blocker and do not create a fake 1.16 candidate.
- Preserve `localai_codex-lb-data`; never run `docker volume rm`, `docker compose down -v`, `docker system prune --volumes`, or equivalent destructive volume commands.
- Health order is always `/health/live` then `/health/ready`; do not use legacy `/health` as the readiness gate.
- Use the observed two-service runtime (`codex-lb-server-1`, `codex-lb-frontend-1`) and reconcile compose files before any future deployment action.
- Keep the public/private image model boundary intact: public APIs, request logs, usage/cost summaries, API-key policy, and `/v1/models` use `gpt-image-*`; the hidden `images_host_model` remains an upstream adapter detail only.
- Every code- or config-affecting Sprint 5 issue must include tests and linters in its artifact: at minimum `git diff --check`, targeted `uv run pytest ... -q`, and `uvx ruff check ...` for touched backend paths.
- Frontend-affecting issues must include `bun run lint`, `bun run typecheck`, `bun run test`, and `bun run build` from `frontend/`, unless the evidence records a missing-tool blocker.
- Prepend `export PATH="/tmp/codex-lb-uv-tool/bin:$PATH"` before backend verification commands because `uv`/`uvx` may not be on the default PATH.
- If `uv run` mutates `uv.lock` without an explicitly approved dependency change, restore `uv.lock` before marking the issue complete.
- Stop after three failed attempts on a candidate validation or live-smoke task, record the blocker in `docs/codex-lb-update_from_1.13.0-blockers.md`, and do not keep retrying paid image generation.

## Phase A — Release availability and current baseline
### Issue 1 — Capture upstream 1.16 availability and live branch baseline
Status: [ ] Planned
Files:
- docs/codex-lb-update_from_1.13.0-roadmap.md
- docs/codex-lb-update_from_1.13.0-sprint5-checklist.md
- /home/vgoro/codex-lb-backups/<timestamp>/sprint5/baseline/release-availability.txt
- /home/vgoro/codex-lb-backups/<timestamp>/sprint5/baseline/live-runtime.txt
Checklist:
- [ ] Fetch upstream refs and record `git ls-remote --tags upstream 'refs/tags/v1.16*'` without assuming a tag exists.
- [ ] Record current branch, HEAD, remotes, `git status --short --branch`, and whether the worktree contains non-doc changes.
- [ ] Record Docker service names/images/status and health statuses for `/health/live` then `/health/ready` without printing secrets.
- [ ] Record sanitized presence of image/runtime settings, including `CODEX_LB_IMAGES_DEFAULT_MODEL`, `CODEX_LB_IMAGES_HOST_MODEL`, and `CODEX_LB_IMAGES_MAX_PARTIAL_IMAGES`, without saving values.
- [ ] If no upstream `v1.16*` ref exists, mark later candidate/cutover issues as blocked by release availability instead of inventing a target.
Planned commit: [ ] docs(upgrade): start sprint 5 upstream alignment planning

### Issue 2 — Build upstream delta map for the 1.16 risk surface
Status: [ ] Planned
Files:
- docs/codex-lb-update_from_1.13.0-sprint5-checklist.md
- /home/vgoro/codex-lb-backups/<timestamp>/sprint5/research/upstream-delta-map.md
Checklist:
- [ ] Compare `v1.15.0..upstream/main` and, once available, `v1.15.0..v1.16.0` with `git diff --stat`, `git log --oneline`, and targeted file lists.
- [ ] Identify changes touching proxy routes, Responses/Chat/Image compatibility, request logs, usage/pricing, API keys, accounts/OAuth, Alembic migrations, Docker/compose, and frontend dashboard surfaces.
- [ ] Use targeted `grep` and `head -n 50` for changed files before writing risk notes.
- [ ] Record whether any upstream changes supersede local Sprint 1-4 patches or create likely conflicts.
- [ ] Keep the artifact text-only and free of secrets, request bodies, generated images, or base64 payloads.
Planned commit: [ ] docs(upgrade): map upstream 1.16 candidate deltas

## Phase B — PR #498 patch retirement strategy
### Issue 3 — Compare local image patch against upstream inclusion
Status: [ ] Planned
Files:
- docs/codex-lb-update_from_1.13.0-sprint5-checklist.md
- /home/vgoro/codex-lb-backups/<timestamp>/sprint5/research/pr498-alignment.md
Checklist:
- [ ] Compare the local image branch against `v1.15.0...upstream/pr/498` and latest upstream refs to identify duplicate, changed, and still-local image patches.
- [ ] Review `/v1/images/generations`, `/v1/images/edits`, explicit `/v1/images/variations` unsupported behavior, schema validation, transport selection, request logs, usage/cost pricing, and API-key allowed-model policy.
- [ ] Decide per patch chunk: drop because upstream includes it, rebase because upstream changed nearby code, or retain because it remains a local requirement.
- [ ] Preserve the public `gpt-image-*` accounting/model-policy boundary and verify no public evidence requires `images_host_model`.
- [ ] Document expected tests and linters for whichever path is selected.
Planned commit: [ ] docs(images): document 1.16 image patch alignment strategy

### Issue 4 — Define candidate branch and conflict-resolution policy
Status: [ ] Planned
Files:
- docs/codex-lb-update_from_1.13.0-roadmap.md
- docs/codex-lb-update_from_1.13.0-sprint5-checklist.md
- docs/codex-lb-update_from_1.13.0-blockers.md
Checklist:
- [ ] Name the candidate branch pattern for a future upstream ref, for example `upgrade/from-1.15.0-images-to-1.16.0`.
- [ ] Require a clean worktree or documented stash/patch backup before branch creation.
- [ ] Define conflict-resolution priority: upstream 1.16 behavior first, then live-data preservation, then local PR #498 compatibility only where upstream lacks equivalent behavior.
- [ ] Define when to stop and record a blocker instead of resolving ambiguous conflicts, especially around migrations, Docker volume paths, OAuth/account storage, and image accounting.
- [ ] Confirm `uv.lock` changes are allowed only when caused by an explicit upstream dependency change and recorded in evidence.
Planned commit: [ ] docs(upgrade): define sprint 5 candidate branch policy

## Phase C — Candidate validation matrix
### Issue 5 — Run non-live backend compatibility gates on the 1.16 candidate
Status: [ ] Planned
Files:
- docs/codex-lb-update_from_1.13.0-sprint5-checklist.md
- tests/integration/test_migrations.py
- tests/integration/test_proxy_responses.py
- tests/integration/test_proxy_chat_completions.py
- tests/integration/test_proxy_images.py
- tests/integration/test_request_logs_api.py
- tests/integration/test_v1_usage.py
- tests/integration/test_v1_models.py
- tests/integration/test_api_keys_api.py
- tests/unit/test_images_schemas.py
- tests/unit/test_images_translation.py
- /home/vgoro/codex-lb-backups/<timestamp>/sprint5/tests/backend-candidate-gates.txt
Checklist:
- [ ] Run migration/head checks against a non-live database fixture before touching the live Docker volume.
- [ ] Run targeted backend regressions for migrations, proxy Responses/Chat, image routes, model listing, API keys, request logs, usage/pricing, and account compatibility.
- [ ] Run `uvx ruff check` for touched backend paths and targeted tests.
- [ ] Run `git diff --check`, `git diff --cached --check`, `git diff --exit-code -- uv.lock`, and `git diff --cached --exit-code -- uv.lock`.
- [ ] Record failures with exact command, exit code, and redacted logs; do not proceed to live rehearsal while backend gates fail.
Planned commit: [ ] test(upgrade): validate 1.16 candidate backend compatibility

### Issue 6 — Run frontend and dashboard compatibility gates
Status: [ ] Planned
Files:
- docs/codex-lb-update_from_1.13.0-sprint5-checklist.md
- frontend/src
- frontend/package.json
- /home/vgoro/codex-lb-backups/<timestamp>/sprint5/tests/frontend-candidate-gates.txt
Checklist:
- [ ] Review dashboard API calls for accounts, settings, API keys, request logs, usage summaries, and model options against any upstream 1.16 API changes.
- [ ] Run `bun run lint`, `bun run typecheck`, `bun run test`, and `bun run build` from `frontend/`.
- [ ] If `bun` or frontend dependencies are unavailable, record the missing-tool blocker and do not mark this issue complete.
- [ ] Verify no frontend artifact contains secrets, live request bodies, or generated image/base64 data.
Planned commit: [ ] test(frontend): validate 1.16 candidate dashboard compatibility

### Issue 7 — Prepare live rehearsal and rollback plan
Status: [ ] Planned
Files:
- docs/codex-lb-update_from_1.13.0-sprint5-checklist.md
- /home/vgoro/codex-lb-backups/<timestamp>/sprint5/rollback-notes.md
- /home/vgoro/codex-lb-backups/<timestamp>/sprint5/tests/live-rehearsal-plan.txt
Checklist:
- [ ] Document exact build, restart, and rollback commands for the observed `server` + `frontend` stack without using volume-destructive flags.
- [ ] Require fresh pre-rehearsal backup location and current image/commit identifiers before any Docker restart.
- [ ] Define live smoke order: `/health/live`, `/health/ready`, dashboard/API surface checks, minimal authenticated text proxy smoke, `/v1/models`, request logs/usage, then conservative image validation/live smokes only if needed.
- [ ] Limit paid image generation to at most one non-streaming and one streaming `gpt-image-2` request unless the operator approves more.
- [ ] Record rollback criteria and stop conditions for migration errors, missing accounts/settings, model-scope failures, public/private model leaks, or health regressions.
Planned commit: [ ] docs(upgrade): prepare 1.16 live rehearsal rollback plan

## Phase D — Evidence and roadmap closure
### Issue 8 — Create Sprint 5 evidence bundle and update roadmap status
Status: [ ] Planned
Files:
- docs/codex-lb-update_from_1.13.0-roadmap.md
- docs/codex-lb-update_from_1.13.0-sprint5-checklist.md
- /home/vgoro/codex-lb-backups/<timestamp>/sprint5/sprint5-evidence.md
Checklist:
- [ ] Summarize release availability, upstream delta map, PR #498 drop/rebase/retain decision, candidate branch policy, validation gates, and rollback plan.
- [ ] Include `release_availability_gate=PASS|BLOCKED`, `delta_map_gate=PASS`, `patch_alignment_gate=PASS`, `validation_matrix_gate=PASS`, `rollback_plan_gate=PASS`, and `secret_scan=PASS` markers only after underlying artifacts exist.
- [ ] Run a suppressed secret scan for Sprint 5 artifacts that never prints matched line contents.
- [ ] Update roadmap Sprint 5 status to Completed only if exit criteria are met; otherwise mark the explicit upstream-release blocker and keep future cutover work planned.
- [ ] Run `git diff --check`, `git diff --cached --check`, `git diff --exit-code -- uv.lock`, `git diff --cached --exit-code -- uv.lock`, and `git status --short --branch`.
Planned commit: [ ] docs(upgrade): record sprint 5 upstream alignment evidence

## Sprint quality gates
- [ ] Upstream `v1.16*` release availability is recorded with exact refs inspected, including an explicit blocker if no tag exists.
- [ ] Current branch, commit, remotes, live Docker service names, compose strategy, and health endpoints are captured without secrets.
- [ ] Delta map covers backend proxy, `/v1/images/*`, request logs, usage/pricing, API keys, accounts/OAuth, migrations, Docker/compose, and frontend dashboard surfaces.
- [ ] PR #498-derived local patches have a documented drop/rebase/retain decision matrix before any candidate coding work begins.
- [ ] Candidate branch policy preserves `localai_codex-lb-data`, existing accounts/settings/API keys, OAuth/encryption material, and current service names.
- [ ] Backend candidate gates include targeted `pytest` plus `uvx ruff check` for touched paths.
- [ ] Frontend candidate gates include lint, typecheck, tests, and build.
- [ ] `git diff --check`, `git diff --cached --check`, and `uv.lock` clean checks pass before closure.
- [ ] Live rehearsal/cutover remains blocked until a valid upstream ref, non-live validation, rollback notes, and operator approval exist.
- [ ] Sprint 5 artifacts pass suppressed secret scan and contain no raw API keys, OAuth token JSON, `.env.local`, database dumps, encryption key material, full Authorization headers, generated binary images, or `b64_json`.

## Quick verification commands
```bash
# Release availability and baseline capture
cd /home/vgoro/codex-lb
SPRINT5=/home/vgoro/codex-lb-backups/<timestamp>/sprint5
mkdir -p "$SPRINT5/baseline" "$SPRINT5/research" "$SPRINT5/tests"
git fetch --tags upstream
git ls-remote --tags upstream 'refs/tags/v1.16*' | tee "$SPRINT5/baseline/release-availability.txt"
{
  git status --short --branch
  git rev-parse HEAD
  git remote -v
  docker ps --format 'table {{.Names}}	{{.Image}}	{{.Status}}	{{.Ports}}' | grep -E 'codex-lb|NAMES'
  curl -fsS -o /dev/null -w 'health_live=%{http_code}
' http://127.0.0.1:2455/health/live
  curl -fsS -o /dev/null -w 'health_ready=%{http_code}
' http://127.0.0.1:2455/health/ready
} > "$SPRINT5/baseline/live-runtime.txt"
```

```bash
# Upstream delta map; use v1.16.0 only after the tag exists
cd /home/vgoro/codex-lb
git fetch upstream main --tags
git diff --stat v1.15.0..upstream/main > /home/vgoro/codex-lb-backups/<timestamp>/sprint5/research/upstream-main-diffstat.txt
git log --oneline --decorate v1.15.0..upstream/main > /home/vgoro/codex-lb-backups/<timestamp>/sprint5/research/upstream-main-log.txt
# Once available:
# git diff --stat v1.15.0..v1.16.0 > /home/vgoro/codex-lb-backups/<timestamp>/sprint5/research/v1.16.0-diffstat.txt
# git log --oneline --decorate v1.15.0..v1.16.0 > /home/vgoro/codex-lb-backups/<timestamp>/sprint5/research/v1.16.0-log.txt
```

```bash
# Backend candidate tests and linter after a real candidate branch exists
cd /home/vgoro/codex-lb
export PATH="/tmp/codex-lb-uv-tool/bin:$PATH"
uv run pytest   tests/integration/test_migrations.py   tests/integration/test_proxy_responses.py   tests/integration/test_proxy_chat_completions.py   tests/integration/test_proxy_images.py   tests/integration/test_request_logs_api.py   tests/integration/test_v1_usage.py   tests/integration/test_v1_models.py   tests/integration/test_api_keys_api.py   tests/unit/test_images_schemas.py   tests/unit/test_images_translation.py   -q
uvx ruff check   app/core/openai   app/core/clients   app/modules/proxy   app/modules/request_logs   app/modules/usage   app/modules/api_keys   tests/integration/test_proxy_images.py   tests/integration/test_request_logs_api.py   tests/integration/test_v1_usage.py   tests/integration/test_v1_models.py   tests/integration/test_api_keys_api.py   tests/unit/test_images_schemas.py   tests/unit/test_images_translation.py
git diff --check
git diff --cached --check
git diff --exit-code -- uv.lock
git diff --cached --exit-code -- uv.lock
```

```bash
# Frontend candidate gates
cd /home/vgoro/codex-lb/frontend
bun run lint
bun run typecheck
bun run test
bun run build
```

## Important gotchas
- No upstream `v1.16` tag is visible at Sprint 5 planning time; release-watch and delta mapping can proceed, but candidate/cutover work must wait for an official upstream ref and operator approval.
- PR #498 is already merged into upstream `main` but not into `v1.15.0`; if `1.16` includes it or an evolved image API, blindly replaying the local patch can duplicate routes, schemas, request-log fields, or usage/pricing entries.
- Live runtime uses `codex-lb-server-1`, `codex-lb-frontend-1`, and `localai_codex-lb-data`; stale `docker-compose.prod.yml` references can accidentally model the wrong deployment shape.
- Public surfaces must continue to show `gpt-image-*`, never the hidden `images_host_model`, for model listing, request logs, usage/cost summaries, and API-key model policy.
