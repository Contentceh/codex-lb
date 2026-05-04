# codex-lb / Sprint 4 — gpt-image-2 Hardening and Live Smoke Implementation Checklist
Repo: /home/vgoro/codex-lb
Purpose: Prove the isolated PR #498 image API patch works safely on the live 1.15.0 Docker deployment with existing account pool authentication, conservative image-generation limits, public-model accounting, and a clean rollback path.

## Sprint scope
Covers:
- Capture the current live Docker/repository/config baseline without exposing secrets.
- Document operational image settings and safe defaults for `gpt-image-2` support.
- Run validation-only `/v1/images/*` negative smokes before any real image generation.
- Run one conservative non-streaming `gpt-image-2` live smoke and one conservative streaming `gpt-image-2` live smoke after health and negative gates pass.
- Verify request logs, request-log filter options, usage/cost summaries, and API-key model policy use the public `gpt-image-*` model instead of the hidden `images_host_model`.
- Re-check text proxy, model listing, health endpoints, and dashboard-facing request/usage APIs after image traffic.
- Produce a redacted Sprint 4 evidence bundle and rollback notes under `/home/vgoro/codex-lb-backups/<timestamp>/sprint4/`.

Does not cover:
- Updating to upstream `1.16` or merging unrelated upstream `main` changes.
- Redesigning the image adapter or adding client-side fan-out for `n > 1`.
- Implementing `/v1/images/variations`; it remains explicitly unsupported.
- Docker volume deletion, recreation, pruning, or renaming.
- Changing OAuth credentials, account tokens, dashboard users/passwords, API keys, encryption key material, DNS, reverse proxy, Telegram/OpenClaw config, or unrelated services.
- Committing raw generated image binaries, base64 image payloads, API keys, OAuth token JSON, database dumps, `.env.local`, or encryption key material.

## Operating rules for this sprint
- Work on `Debian-n8n` in `/home/vgoro/codex-lb`; do not run project commands on the local OpenClaw host.
- Treat the current branch `feature/pr-498-images-api-on-1.15.0` as the Sprint 4 candidate unless the operator explicitly selects another branch.
- Preserve the Docker data volume `localai_codex-lb-data`; never run `docker volume rm`, `docker compose down -v`, `docker system prune --volumes`, or equivalent destructive volume commands.
- Use the observed two-service runtime (`codex-lb-server-1`, `codex-lb-frontend-1`) and `docker-compose.yml`; do not blindly use `docker-compose.prod.yml` because it still has a stale single-service image reference.
- Health order is always `/health/live` then `/health/ready`; do not use the legacy `/health` route as the readiness gate.
- Source operational API keys from the existing environment or a private operator-provided shell session without echoing them, writing them to shell history, or saving them unredacted in artifacts.
- Before real image generation, run validation-only cases that fail before upstream dispatch: unsupported image model, invalid `gpt-image-2` size/background/input-fidelity, `n > 1`, `/v1/images/variations`, and model-scope rejection where an allowed-model test key can be created safely.
- Real generation smokes must be conservative: `n=1`, small allowed size such as `1024x1024`, no uploaded private images, no sensitive prompts, and at most one non-streaming plus one streaming request unless the operator approves more.
- Do not write generated binary image content or base64 payloads into Git or evidence files. Evidence may record HTTP status, response shape, event counts, byte counts, image metadata, request IDs, and redacted hashes only.
- Request logs, request-log options, model-scoped API-key checks, reservations, usage summaries, and pricing must refer to the public `gpt-image-*` model. The hidden `images_host_model` must not appear in public dashboard/API evidence for image requests. Treat this as an explicit public/private model boundary:
  - `images_host_model` is a private adapter implementation detail used only for upstream Responses dispatch.
  - Client-facing routing, `/v1/models`, dashboard/API evidence, accounting, and model-scope policy use the requested or default public `gpt-image-*` model.
  - Evidence should prove the boundary with positive public model markers such as `gpt-image-2`/`gpt-image-*` and negative checks for `images_host_model` leakage.
- Every code/doc-changing issue must include tests and linters in its artifact: at minimum `git diff --check`, targeted `uv run pytest ... -q`, and `uvx ruff check ...` for touched Python paths. Documentation-only issues still run `git diff --check` and targeted grep checks.
- Prepend `export PATH="/tmp/codex-lb-uv-tool/bin:$PATH"` before backend verification commands because `uv`/`uvx` may not be on the default PATH.
- If `uv run` mutates `uv.lock` without an explicitly approved dependency change, restore `uv.lock` before marking the issue complete.
- Stop after three failed attempts on any live-smoke task, record the blocker in `docs/codex-lb-update_from_1.13.0-blockers.md`, and do not keep retrying paid image generation.

## Phase A — Baseline, config, and safe runbook
### Issue 1 — Capture live Sprint 4 baseline and candidate commit
Status: [x] Completed
Files:
- docs/codex-lb-update_from_1.13.0-sprint4-checklist.md
- /home/vgoro/codex-lb-backups/<timestamp>/sprint4/baseline/live-runtime.txt
- /home/vgoro/codex-lb-backups/<timestamp>/sprint4/baseline/repo-state.txt
Checklist:
- [x] Create `/home/vgoro/codex-lb-backups/<timestamp>/sprint4/` with a `baseline/` subdirectory outside Git.
- [x] Record branch, HEAD, remotes, `git status --short --branch`, Docker container names/images/status, compose file identity, and health endpoint statuses without printing secrets.
- [x] Record sanitized image settings presence (`images_default_model`, `images_host_model`, `images_max_partial_images`) and whether overrides exist, without printing `.env.local` values.
- [x] Verify `git diff --check`, `git diff --cached --check`, `git diff --exit-code -- uv.lock`, and `git diff --cached --exit-code -- uv.lock` before live-smoke work.
Planned commit: [x] docs(upgrade): start sprint 4 live image hardening

### Issue 2 — Document operational image settings and rollback runbook
Status: [x] Completed
Files:
- docs/codex-lb-update_from_1.13.0-sprint4-checklist.md
- docs/codex-lb-update_from_1.13.0-roadmap.md
- /home/vgoro/codex-lb-backups/<timestamp>/sprint4/rollback-notes.md
Checklist:
- [x] Document `CODEX_LB_IMAGES_DEFAULT_MODEL`, `CODEX_LB_IMAGES_HOST_MODEL`, and `CODEX_LB_IMAGES_MAX_PARTIAL_IMAGES` in a docs/runbook artifact without committing environment values.
- [x] Document the operational meaning of the hidden host model versus public `gpt-image-*` model.
- [x] Record rollback commands that preserve `localai_codex-lb-data` and avoid volume-destructive operations.
- [x] Verify docs with `git diff --check` and grep checks for the image setting names.
Planned commit: [x] docs(images): document sprint 4 image runtime settings

## Phase B — Validation-only live route hardening
### Issue 3 — Run validation-only Images API negative smokes
Status: [x] Completed
Files:
- docs/codex-lb-update_from_1.13.0-sprint4-checklist.md
- /home/vgoro/codex-lb-backups/<timestamp>/sprint4/tests/images-validation-negative-smoke.txt
Checklist:
- [x] Confirm `/health/live` and `/health/ready` return success before route checks.
- [x] Using a redacted operational API key, call `/v1/images/generations` with an unsupported model and verify a 400 OpenAI-style `invalid_request_error` without upstream dispatch.
- [x] Verify `gpt-image-2` rejects `n > 1`, invalid size, `background=transparent`, and `input_fidelity` before upstream dispatch.
- [x] Verify `/v1/images/variations` returns the explicit `not_supported` error.
- [x] Save only statuses, error codes, and redacted request IDs in the evidence artifact.
Planned commit: [x] test(images): record validation-only live image smokes

### Issue 4 — Verify live API-key model scope for public image models
Status: [x] Completed
Files:
- docs/codex-lb-update_from_1.13.0-sprint4-checklist.md
- /home/vgoro/codex-lb-backups/<timestamp>/sprint4/tests/images-api-key-scope-smoke.txt
Checklist:
- [x] Create or identify a temporary API key scoped to a non-requested image model without exposing the key material.
- [x] Verify a `gpt-image-2` image request with that key returns `403 model_not_allowed` before upstream dispatch.
- [x] Verify the request-limit/reservation path uses the public `gpt-image-2` model, not `images_host_model`.
- [x] Remove or disable any temporary key if it was created solely for the smoke, and record only the redacted key name/id.
Planned commit: [x] test(images): record live image api-key scope smoke

## Phase C — Conservative real image generation
### Issue 5 — Run one non-streaming `gpt-image-2` live generation smoke
Status: [x] Completed
Files:
- docs/codex-lb-update_from_1.13.0-sprint4-checklist.md
- /home/vgoro/codex-lb-backups/<timestamp>/sprint4/tests/images-generation-live-smoke.txt
Checklist:
- [x] Confirm health and Phase B validation artifacts are present before generating a real image.
- [x] Send one non-sensitive `gpt-image-2` `/v1/images/generations` request with `n=1` and conservative size/quality settings.
- [x] Verify HTTP success and OpenAI Images response shape without storing the returned image/base64 content.
- [x] Record response metadata, elapsed time, payload byte count, and redacted request identifiers only.
- [x] Run `git diff --check` and ensure no generated binary/base64 artifacts were written under Git.
Planned commit: [x] test(images): record non-streaming live gpt-image-2 smoke

### Issue 6 — Run one streaming `gpt-image-2` live generation smoke
Status: [x] Completed
Files:
- docs/codex-lb-update_from_1.13.0-sprint4-checklist.md
- /home/vgoro/codex-lb-backups/<timestamp>/sprint4/tests/images-generation-stream-live-smoke.txt
Checklist:
- [x] Send one non-sensitive streaming `gpt-image-2` `/v1/images/generations` request with `n=1` and conservative settings.
- [x] Verify the stream emits `image_generation.partial_image` and/or `image_generation.completed`, then terminates with `[DONE]`.
- [x] Confirm event-size handling does not trigger local SSE/websocket frame failures.
- [x] Record only event names, counts, total bytes, elapsed time, and redacted request identifiers.
Planned commit: [x] test(images): record streaming live gpt-image-2 smoke

## Phase D — Accounting, dashboard evidence, and post-smoke regressions
### Issue 7 — Verify request logs and usage show public image model
Status: [x] Completed
Files:
- docs/codex-lb-update_from_1.13.0-sprint4-checklist.md
- /home/vgoro/codex-lb-backups/<timestamp>/sprint4/tests/images-accounting-live-smoke.txt
Checklist:
- [x] Query dashboard request logs or repository state for the live image requests and verify `model` is `gpt-image-2` or another public `gpt-image-*` value.
- [x] Query request-log filter options and verify public image model options are available without exposing the hidden host model.
- [x] Query usage/cost summary paths and verify image costs/pricing group under public `gpt-image-*` metadata.
- [x] Record only redacted request IDs, model names, statuses, and aggregate cost/usage fields needed for evidence.
Planned commit: [x] test(images): record public-model accounting smoke

### Issue 8 — Confirm text proxy and model surfaces after image traffic
Status: [x] Completed
Files:
- docs/codex-lb-update_from_1.13.0-sprint4-checklist.md
- /home/vgoro/codex-lb-backups/<timestamp>/sprint4/tests/post-image-proxy-regression-smoke.txt
Checklist:
- [x] Re-check `/health/live` and `/health/ready` after image traffic.
- [x] Verify `/v1/models` still returns the expected text/model surface and does not leak `images_host_model` as an image model.
- [x] Run one minimal authenticated text proxy smoke or existing safe compatibility live-check subset.
- [x] Inspect recent server logs for image-related errors without printing secrets or request bodies.
Planned commit: [x] test(proxy): record post-image live regression smoke

## Phase E — Evidence bundle and closure
### Issue 9 — Create Sprint 4 evidence bundle
Status: [x] Completed
Files:
- docs/codex-lb-update_from_1.13.0-sprint4-checklist.md
- /home/vgoro/codex-lb-backups/<timestamp>/sprint4/sprint4-evidence.md
Checklist:
- [x] Summarize baseline, validation-only smokes, real generation smokes, public-model accounting, post-image regressions, rollback notes, and secret-scan results.
- [x] Include `image_validation_gate=PASS`, `live_generation_gate=PASS`, `public_model_accounting_gate=PASS`, `post_image_proxy_gate=PASS`, and `secret_scan=PASS` markers only after the underlying artifacts pass.
- [x] Run a suppressed secret scan for Sprint 4 artifacts that never prints matched line contents.
- [x] Verify `test -s /home/vgoro/codex-lb-backups/<timestamp>/sprint4/sprint4-evidence.md`, required marker greps, `git diff --check`, and `git diff --exit-code -- uv.lock`.
Planned commit: [x] docs(upgrade): record sprint 4 evidence

### Issue 10 — Complete Sprint 4 docs and roadmap
Status: [x] Completed
Files:
- docs/codex-lb-update_from_1.13.0-roadmap.md
- docs/codex-lb-update_from_1.13.0-sprint4-checklist.md
Checklist:
- [x] Mark Sprint 4 quality gates and all completed issues as `Status: [x] Completed` only after evidence and rollback notes are ready.
- [x] Update the roadmap to mark Sprint 4 complete and select Sprint 5 / 1.16 readiness as the next planned sprint.
- [x] Verify no unchecked Sprint 4 checklist tasks remain except explicitly deferred out-of-scope work.
- [x] Run `git diff --check`, `git diff --cached --check`, `git diff --exit-code -- uv.lock`, and `git status --short --branch`.
Planned commit: [x] docs(upgrade): complete sprint 4 live smoke

## Sprint quality gates
- [x] Live Docker baseline captured with branch, commit, container health, compose strategy, and sanitized runtime setting presence.
- [x] Image runtime settings and rollback path are documented without secrets.
- [x] Validation-only negative image smokes pass before any real generation.
- [x] `gpt-image-2` non-streaming live smoke passes with no image/base64 content committed.
- [x] `gpt-image-2` streaming live smoke passes with no image/base64 content committed.
- [x] API-key allowed-model policy rejects unauthorized public image models before upstream dispatch.
- [x] Request logs, request-log filter options, usage summaries, and pricing evidence show public `gpt-image-*` metadata, not `images_host_model`.
- [x] Health, `/v1/models`, and text proxy smoke remain healthy after image traffic.
- [x] `git diff --check`, `git diff --cached --check`, targeted `pytest`, and `uvx ruff check` pass for any touched project code/tests.
- [x] `uv.lock` remains clean unless an explicitly approved dependency change is introduced.
- [x] Sprint 4 evidence artifacts pass suppressed secret scan and contain no raw API keys, OAuth token JSON, database dumps, encryption key material, full Authorization headers, generated binary images, or base64 image payloads.

## Quick verification commands
```bash
# Baseline and health
cd /home/vgoro/codex-lb
SPRINT4=/home/vgoro/codex-lb-backups/<timestamp>/sprint4
mkdir -p "$SPRINT4/baseline" "$SPRINT4/tests"
{
  git status --short --branch
  git rev-parse HEAD
  git remote -v
  docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' | grep -E 'codex-lb|NAMES'
  curl -fsS -o /dev/null -w 'health_live=%{http_code}\n' http://127.0.0.1:2455/health/live
  curl -fsS -o /dev/null -w 'health_ready=%{http_code}\n' http://127.0.0.1:2455/health/ready
} > "$SPRINT4/baseline/live-runtime.txt"
```

```bash
# Backend focused regression tests plus linter for image/live-smoke touched surfaces
cd /home/vgoro/codex-lb
export PATH="/tmp/codex-lb-uv-tool/bin:$PATH"
uv run pytest \
  tests/integration/test_proxy_images.py \
  tests/integration/test_request_logs_api.py \
  tests/integration/test_v1_usage.py \
  tests/integration/test_v1_models.py \
  tests/integration/test_api_keys_api.py \
  -q
uvx ruff check \
  app/core/openai/images.py \
  app/modules/proxy/images_service.py \
  app/modules/proxy/api.py \
  app/modules/request_logs \
  app/modules/usage \
  tests/integration/test_proxy_images.py \
  tests/integration/test_request_logs_api.py \
  tests/integration/test_v1_usage.py \
  tests/integration/test_v1_models.py \
  tests/integration/test_api_keys_api.py
```

```bash
# Validation-only image route smoke; must not generate a real image.
# CODEX_LB_API_KEY must be set privately and must never be echoed.
cd /home/vgoro/codex-lb
: "${CODEX_LB_API_KEY:?set a non-printed operational API key first}"
auth_header="Authorization: Bearer ${CODEX_LB_API_KEY}"
base=http://127.0.0.1:2455/v1
curl -sS -o /tmp/codex-lb-images-invalid-model.json -w 'invalid_model_http=%{http_code}\n' \
  -H "$auth_header" -H 'Content-Type: application/json' \
  -d '{"model":"not-an-image-model","prompt":"validation only"}' \
  "$base/images/generations"
python3 - <<'PY'
from pathlib import Path
body = Path('/tmp/codex-lb-images-invalid-model.json').read_text()
assert 'invalid_request_error' in body
assert 'not-an-image-model' in body
print('invalid_model_gate=PASS')
PY
```

```bash
# Conservative real non-streaming image smoke; store metadata only, omit raw base64 image payloads.
cd /home/vgoro/codex-lb
: "${CODEX_LB_API_KEY:?set a non-printed operational API key first}"
python3 - <<'PY'
import json, os, time, urllib.request
req = urllib.request.Request(
    'http://127.0.0.1:2455/v1/images/generations',
    data=json.dumps({
        'model': 'gpt-image-2',
        'prompt': 'A tiny friendly crab icon on a plain background',
        'n': 1,
        'size': '1024x1024',
        'quality': 'low',
        'output_format': 'png',
    }).encode(),
    headers={
        'Authorization': 'Bearer ' + os.environ['CODEX_LB_API_KEY'],
        'Content-Type': 'application/json',
    },
    method='POST',
)
start = time.monotonic()
with urllib.request.urlopen(req, timeout=300) as resp:
    payload = json.loads(resp.read().decode())
elapsed_ms = int((time.monotonic() - start) * 1000)
assert payload.get('data') and isinstance(payload['data'], list)
first = payload['data'][0]
assert first.get('b64_' + 'json') or first.get('url')
print(json.dumps({
    'live_generation_gate': 'PASS',
    'elapsed_ms': elapsed_ms,
    'created_present': 'created' in payload,
    'data_count': len(payload['data']),
    'first_keys': sorted(k for k in first if k != 'b64_' + 'json'),
    'image_bytes_omitted': True,
}))
PY
```

```bash
# Final cleanliness and secret scan
cd /home/vgoro/codex-lb
SPRINT4=/home/vgoro/codex-lb-backups/<timestamp>/sprint4
python3 - <<'PY'
from pathlib import Path
root = Path('/home/vgoro/codex-lb-backups/<timestamp>/sprint4')
patterns = ['sk-' + 'clb', 'Bearer' + ' ', 'OPENAI_' + 'OAUTH', 'CODEX_LB_' + 'ENCRYPTION_KEY', 'b64_' + 'json']
failures = []
for path in root.rglob('*'):
    if path.is_file():
        text = path.read_text(encoding='utf-8', errors='ignore')
        hits = [p for p in patterns if p in text]
        if hits:
            failures.append((str(path), len(hits)))
if failures:
    for path, count in failures:
        print(f'{path}: {count} forbidden pattern category hit(s)')
    raise SystemExit(1)
print('secret_scan=PASS')
PY
git diff --check
git diff --cached --check
git diff --exit-code -- uv.lock >/dev/null
git diff --cached --exit-code -- uv.lock >/dev/null
git status --short --branch
```

## Operational image runtime settings
- `CODEX_LB_IMAGES_DEFAULT_MODEL` maps to `images_default_model`; default `gpt-image-2`. It is the public image model used when a client omits `model` on `/v1/images/*` requests, so operator changes must remain in the supported public `gpt-image-*` family.
- `CODEX_LB_IMAGES_HOST_MODEL` maps to `images_host_model`; default `gpt-5.5`. It is the internal Responses host used by the adapter to reach the upstream image tool, and its value must stay out of public request logs, API-key model policy, `/v1/models`, usage, and pricing surfaces.
- `CODEX_LB_IMAGES_MAX_PARTIAL_IMAGES` maps to `images_max_partial_images`; default `3`, accepted range `0..3`. It caps requested streaming `partial_images`; values above the stream contract are rejected before upstream dispatch.
- Do not commit live values from `.env.local`. Sprint 4 evidence records only presence/override status in `/home/vgoro/codex-lb-backups/<timestamp>/sprint4/baseline/image-settings-presence.txt`.

## Important gotchas
- Real image generation can consume paid/limited account quota. Keep Sprint 4 to one non-streaming and one streaming request until the operator explicitly approves more.
- The hidden `images_host_model` (currently a text Responses host such as `gpt-5.5`) is an implementation detail. Public logs, API-key policy, request limits, `/v1/models`, usage, and costs must show `gpt-image-*`, never the host model.
- The live deployment uses `codex-lb-server-1` and `codex-lb-frontend-1` with the named volume `localai_codex-lb-data`; using the stale single-service `docker-compose.prod.yml` can accidentally change runtime shape or downgrade images.
- Streaming image responses can carry large base64 SSE payloads. Evidence must record event counts/byte counts only, and local transport must not fall back into websocket frame-size failures.
- `n > 1` remains intentionally rejected. Do not add a runtime knob that promises multi-image support until fan-out is designed, implemented, and tested.
