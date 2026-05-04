# codex-lb / Sprint 3 — Integrate PR #498 as an Isolated Image API Patch Implementation Checklist
Repo: /home/vgoro/codex-lb
Purpose: Add OpenAI-compatible `gpt-image-2` support from `Soju06/codex-lb#498` on top of the stable 1.15.0 upgrade branch, keeping the patch isolated and easy to drop, rebase, or replace when upstream 1.16 is released.

## Sprint scope
Covers:
- Create an isolated integration branch on top of the completed 1.15.0 upgrade baseline.
- Inventory PR #498 against `v1.15.0` and port only the image API compatibility changes needed for `/v1/images/generations` and `/v1/images/edits`.
- Add public OpenAI Images request/response schemas for the `gpt-image-*` family, including the `gpt-image-2` parameter matrix.
- Add a translation layer from OpenAI Images requests to internal Responses requests with the built-in `image_generation` tool.
- Add `/v1/images/generations`, `/v1/images/edits`, and an explicit unsupported `/v1/images/variations` response on the existing `/v1` router.
- Preserve existing `/v1/responses`, `/v1/chat/completions`, `/v1/audio/transcriptions`, `/v1/models`, request log, usage, sticky-session, API-key, and dashboard behavior from the 1.15.0 baseline.
- Record image requests under the public `gpt-image-*` model for API-key allowed-model checks, request logs, pricing, and usage summaries while hiding the internal host model.
- Add PR #498 image API tests and run targeted existing proxy/accounting regressions with `ruff` checks.
- Produce a Sprint 3 evidence artifact under `/home/vgoro/codex-lb-backups/<timestamp>/sprint3/` without secrets.

Does not cover:
- Live Docker cutover or production restart; Sprint 3 is an isolated code/test integration sprint.
- Real paid image generation smoke against live accounts; that belongs to Sprint 4 after mocked and local quality gates pass.
- Updating to upstream `1.16` or mixing unrelated upstream main commits beyond the PR #498 image patch.
- Implementing `/v1/images/variations`; it remains explicitly unsupported.
- Client-side fan-out for `n > 1`; requests must reject multi-image counts until a later design implements safe fan-out.
- Dashboard UI redesign for image settings; environment/config defaults are sufficient for this sprint unless the PR port requires minimal schema exposure.
- Deleting, recreating, renaming, or pruning Docker volumes.
- Changing account credentials, OAuth token material, dashboard users/passwords, API keys, or encryption settings.

## Operating rules for this sprint
- Work on `Debian-n8n` in `/home/vgoro/codex-lb`; do not run project commands on the local OpenClaw host.
- Start from the completed 1.15.0 baseline branch `upgrade/from-1.13.0-to-1.15.0` after Sprint 2 commit `a6b32756c2a91620536b031bcd7eff6241f160ca` unless a newer approved baseline is recorded first.
- Create an isolated branch for this sprint, for example `feature/pr-498-images-api-on-1.15.0`; keep the PR #498 port as small, reviewable commits so the branch can be dropped or rebased when upstream 1.16 lands.
- Preserve all retained unstaged non-doc/code changes from the Sprint 2 worktree. Do not discard them. If they block branch isolation, save an explicit patch/status artifact outside Git and ask for an operator decision before overwriting anything.
- Direct code edits are allowed only for files named in a Sprint 3 issue or for tightly related tests/docs needed by that issue. No unrelated cleanup.
- Never print or commit `.env`, OAuth token JSON, account exports, API keys, database dumps, encryption key material, or full Authorization headers.
- Use redacted artifacts under `/home/vgoro/codex-lb-backups/<timestamp>/sprint3/` for evidence. Secret scans must suppress matched line contents and record only pass/fail plus counts.
- Every code-changing issue must include both tests and linters in its artifact: at minimum `git diff --check`, targeted `uv run pytest ... -q`, and `uvx ruff check ...` for touched Python paths.
- Because `uv`/`uvx` may be absent from PATH on `Debian-n8n`, prepend `export PATH="/tmp/codex-lb-uv-tool/bin:$PATH"` before backend verification commands.
- If `uv run` mutates `uv.lock` without an issue explicitly requiring dependency changes, restore `uv.lock` before marking the issue complete.
- Keep `/health/live` then `/health/ready` as the runtime health order for any optional local container smoke; do not use the legacy `/health` endpoint as the readiness gate.
- Authenticated local route smokes must source an existing operational API key without echoing it, writing it to shell history, or storing it unredacted in artifacts.
- Do not run `docker volume rm`, `docker compose down -v`, `docker system prune --volumes`, or any equivalent volume-destructive command.
- For image routes, validate the public `gpt-image-*` model before swapping to the internal host Responses model. API-key allowed-model policy and request accounting must see the public image model.
- For image-generation internal Responses requests, force the safer HTTP/SSE path when auto transport would otherwise choose websocket, because image payload events can be large.
- Keep `/v1/chat/completions` rejection/normalization behavior for built-in tools unchanged unless the issue explicitly proves a PR #498 compatibility requirement.

## Phase A — Baseline isolation and PR intake
### Issue 1 — Confirm Sprint 2 baseline and isolate the Sprint 3 branch
Status: [ ] Planned
Files:
- docs/codex-lb-update_from_1.13.0-roadmap.md
- docs/codex-lb-update_from_1.13.0-sprint2-checklist.md
- docs/codex-lb-update_from_1.13.0-sprint3-checklist.md
Checklist:
- [ ] Verify Sprint 2 is marked complete in the roadmap and checklist.
- [ ] Record branch, HEAD, remotes, `git status --short --branch`, and retained unstaged changes in `/home/vgoro/codex-lb-backups/<timestamp>/sprint3/baseline/repo-state.txt`.
- [ ] Create or confirm an isolated Sprint 3 branch on top of the approved 1.15.0 baseline without discarding retained worktree changes.
- [ ] Verify `git diff --check` and `git diff --exit-code -- uv.lock` before importing the PR #498 patch.
Planned commit: [ ] chore(upgrade): start isolated sprint 3 image branch

### Issue 2 — Capture PR #498 patch inventory and conflict map
Status: [ ] Planned
Files:
- docs/codex-lb-update_from_1.13.0-sprint3-checklist.md
- /home/vgoro/codex-lb-backups/<timestamp>/sprint3/pr498-inventory.txt
Checklist:
- [ ] Record `gh pr view 498 --repo Soju06/codex-lb` or an equivalent `git diff --name-status v1.15.0...upstream/pr/498` inventory.
- [ ] Identify every PR #498 file that conflicts with the current 1.15.0 branch or retained local work.
- [ ] Decide whether to cherry-pick the PR merge commit, cherry-pick individual commits, or port manually by file; record the selected strategy before editing code.
- [ ] Confirm the selected strategy keeps the image patch separable from later upstream 1.16 work.
Planned commit: [ ] docs(upgrade): record sprint 3 pr498 intake

## Phase B — Public schemas, settings, and pricing
### Issue 3 — Add OpenAI Images public schema and validation layer
Status: [ ] Planned
Files:
- app/core/openai/images.py
- app/core/openai/strict_schema.py
- app/core/openai/exceptions.py
- tests/unit/test_images_schemas.py
- tests/unit/test_strict_schema_validation.py
Checklist:
- [ ] Add request models for `/v1/images/generations` JSON bodies and `/v1/images/edits` multipart form fields.
- [ ] Add response models for non-streaming image results and streaming image events.
- [ ] Enforce `gpt-image-2` quality, size, background, output format, moderation, `input_fidelity`, `partial_images`, and `n` validation before any upstream request is opened.
- [ ] Preserve legacy `gpt-image-1.5`, `gpt-image-1`, and `gpt-image-1-mini` validation exactly where PR #498 requires it.
- [ ] Add strict text-format validation helpers only where needed by the PR, and verify they do not regress existing Responses/Chat request validation.
- [ ] Run schema tests and `ruff check` for touched schema/helper files.
Planned commit: [ ] feat(images): add public image request schemas

### Issue 4 — Add image configuration and pricing metadata
Status: [ ] Planned
Files:
- app/core/config/settings.py
- app/core/usage/pricing.py
- tests/unit/test_images_schemas.py
- tests/integration/test_v1_usage.py
Checklist:
- [ ] Add `images_host_model`, `images_default_model`, and `images_max_partial_images` settings with safe defaults and validation.
- [ ] Do not add an `images_max_n` setting unless fan-out is implemented in the same issue; `n > 1` must still reject deterministically.
- [ ] Add model pricing aliases for `gpt-image-2` and legacy `gpt-image-*` entries so model-scoped API-key limits and usage cost summaries do not resolve to zero by accident.
- [ ] Verify configuration defaults do not expose the internal host model in public responses.
- [ ] Run targeted pricing/settings tests and `ruff check` for touched files.
Planned commit: [ ] feat(images): add image settings and pricing metadata

## Phase C — Translation service and `/v1/images` routes
### Issue 5 — Add image-to-Responses translation service
Status: [ ] Planned
Files:
- app/modules/proxy/images_service.py
- app/core/openai/images.py
- tests/unit/test_images_translation.py
Checklist:
- [ ] Build internal Responses requests with `tools: [{"type": "image_generation", ...}]` and deterministic instructions that force one image-generation tool call.
- [ ] Convert generation prompts and edit image/mask parts into valid Responses input content, including base64 data URL handling.
- [ ] Keep the internal host model hidden from public responses while preserving the public `gpt-image-*` model in image tool config and downstream metadata.
- [ ] Convert upstream non-streaming Responses output into OpenAI Images envelopes with image data, revised prompt, created timestamp, and usage metadata.
- [ ] Convert upstream stream events into canonical `image_generation.*` or `image_edit.*` SSE events and terminate cleanly.
- [ ] Map upstream image failures and content policy failures into OpenAI-compatible error envelopes.
- [ ] Run translation tests and `ruff check` for the service and schema files.
Planned commit: [ ] feat(images): translate image requests through responses tool

### Issue 6 — Expose `/v1/images/generations`, `/v1/images/edits`, and unsupported variations
Status: [ ] Planned
Files:
- app/modules/proxy/api.py
- app/modules/proxy/images_service.py
- tests/integration/test_proxy_images.py
Checklist:
- [ ] Add `POST /v1/images/generations` with JSON input and JSON or `text/event-stream` output depending on `stream`.
- [ ] Add `POST /v1/images/edits` with multipart `image`, `image[]`, optional `mask`, and image parameter fields.
- [ ] Add explicit `POST /v1/images/variations` unsupported response with OpenAI error shape.
- [ ] Apply API-key authentication, OpenAI error formatting, request limit enforcement, and rate-limit headers consistently with existing `/v1` routes.
- [ ] Return validation errors before account selection or upstream dispatch whenever the request is invalid.
- [ ] Run image route integration tests and `ruff check` for touched API files.
Planned commit: [ ] feat(proxy): expose openai images endpoints

### Issue 7 — Route image-generation traffic over safe HTTP/SSE transport
Status: [ ] Planned
Files:
- app/core/clients/proxy.py
- app/modules/proxy/service.py
- app/modules/proxy/request_policy.py
- tests/unit/test_proxy_load_balancer_refresh.py
- tests/unit/test_proxy_utils.py
- tests/integration/test_openai_compat_features.py
Checklist:
- [ ] Detect internal Responses payloads that contain the built-in `image_generation` tool.
- [ ] In auto transport mode, force upstream HTTP/SSE for image-generation requests while preserving explicit operator transport settings.
- [ ] Preserve existing websocket and HTTP bridge behavior for non-image Responses and Chat traffic.
- [ ] Keep stream size/budget handling compatible with large base64 image events.
- [ ] Run transport-selection regressions plus existing OpenAI compatibility tests and `ruff check` for touched proxy/client files.
Planned commit: [ ] fix(proxy): route image generation over http transport

## Phase D — API-key policy, request logs, and usage accounting
### Issue 8 — Enforce public image model policy for API keys and reservations
Status: [ ] Planned
Files:
- app/modules/proxy/api.py
- app/modules/api_keys/service.py
- tests/integration/test_proxy_images.py
- tests/integration/test_api_keys_api.py
Checklist:
- [ ] Resolve the effective public model before request validation and before the internal host model swap.
- [ ] Apply `validate_model_access` and model-scoped API-key limit reservations to the public `gpt-image-*` model.
- [ ] Ensure API keys that do not allow `gpt-image-2` receive `model_not_allowed` before any upstream request is opened.
- [ ] Ensure reservation finalization failures are logged and do not corrupt a successful image response.
- [ ] Run image/API-key integration tests and `ruff check` for touched policy files.
Planned commit: [ ] feat(images): enforce api key image model policy

### Issue 9 — Record request logs and usage under the public image model
Status: [ ] Planned
Files:
- app/modules/proxy/service.py
- app/modules/request_logs/repository.py
- app/core/usage/pricing.py
- tests/integration/test_request_logs_api.py
- tests/integration/test_v1_usage.py
- tests/unit/test_request_logs_repository.py
- tests/integration/test_proxy_images.py
Checklist:
- [ ] Add a safe way for translated image requests to rewrite request-log model metadata from the internal host model to the public `gpt-image-*` model.
- [ ] Preserve response id/account lookup behavior for previous-response and sticky-session flows.
- [ ] Confirm dashboard request-log filters and usage summaries can surface `gpt-image-2` without mixing it with the host model.
- [ ] Confirm costs are calculated from the public image pricing metadata.
- [ ] Run request-log/usage tests and `ruff check` for touched accounting files.
Planned commit: [ ] feat(images): account image requests under public model

## Phase E — Specs, regression gates, and evidence
### Issue 10 — Add OpenSpec compatibility notes for Images API
Status: [ ] Planned
Files:
- openspec/changes/add-images-api-compat/proposal.md
- openspec/changes/add-images-api-compat/specs/images-api-compat/spec.md
- openspec/changes/add-images-api-compat/tasks.md
- openspec/specs/responses-api-compat/spec.md
- docs/codex-lb-update_from_1.13.0-roadmap.md
Checklist:
- [ ] Port PR #498 OpenSpec change docs and adapt them to the 1.15.0 branch state.
- [ ] Document that `/v1/images/generations` and `/v1/images/edits` are supported through the internal Responses `image_generation` tool.
- [ ] Document that `/v1/images/variations` remains unsupported.
- [ ] Document that direct Chat/Responses built-in-tool compatibility remains unchanged except for the internal image adapter path.
- [ ] Run `git diff --check` for all docs/spec files.
Planned commit: [ ] docs(images): document images api compatibility patch

### Issue 11 — Run focused image quality gate and existing proxy regressions
Status: [ ] Planned
Files:
- tests/integration/test_proxy_images.py
- tests/unit/test_images_schemas.py
- tests/unit/test_images_translation.py
- tests/unit/test_strict_schema_validation.py
- tests/integration/test_openai_compat_features.py
- tests/integration/test_v1_models.py
- tests/integration/test_v1_usage.py
- tests/integration/test_request_logs_api.py
- tests/unit/test_proxy_utils.py
- tests/unit/test_proxy_load_balancer_refresh.py
Checklist:
- [ ] Run the focused image unit/integration test suite.
- [ ] Run existing proxy, request-log, usage, models, and API-key regression tests that guard 1.15.0 behavior.
- [ ] Run `uvx ruff check` for every touched backend source and test path.
- [ ] Verify `git diff --check`, `git diff --cached --check`, and `uv.lock` cleanliness after the test run.
- [ ] Save test and linter logs to `/home/vgoro/codex-lb-backups/<timestamp>/sprint3/tests/`.
Planned commit: [ ] test(images): prove images patch and proxy regressions

### Issue 12 — Produce Sprint 3 evidence and update completion docs
Status: [ ] Planned
Files:
- docs/codex-lb-update_from_1.13.0-roadmap.md
- docs/codex-lb-update_from_1.13.0-sprint3-checklist.md
- /home/vgoro/codex-lb-backups/<timestamp>/sprint3/sprint3-evidence.md
Checklist:
- [ ] Create a Sprint 3 evidence bundle linking branch baseline, PR intake, patch strategy, tests, linters, request-log/usage verification, and secret scan results.
- [ ] Scan Sprint 3 runtime/test artifacts for secret-bearing patterns using suppressed match output and record pass/fail only.
- [ ] Update the roadmap to show Sprint 3 completion only after all quality gates pass.
- [ ] Update this checklist from `Planned` to `Completed` only after evidence and final commit are ready.
- [ ] Create a clean final docs/evidence commit without staging unrelated code.
Planned commit: [ ] docs(upgrade): complete sprint 3 evidence

## Sprint quality gates
- [ ] Sprint 3 branch starts from the approved 1.15.0 Sprint 2 baseline and keeps the image patch isolated from unrelated upstream drift.
- [ ] `/v1/images/generations` supports valid `gpt-image-2` non-streaming and streaming requests in mocked integration tests.
- [ ] `/v1/images/edits` supports multipart image input and rejects invalid edit-only parameters in mocked integration tests.
- [ ] `/v1/images/variations` returns an explicit unsupported OpenAI-shaped error.
- [ ] Invalid public models, invalid `gpt-image-2` sizes, transparent background, invalid `input_fidelity`, and `n > 1` all fail before upstream dispatch.
- [ ] API-key allowed-model and model-scoped reservation checks use the public `gpt-image-*` model, not the internal host model.
- [ ] Request logs, usage summaries, and pricing metadata surface the public `gpt-image-*` model.
- [ ] Existing `/v1/responses`, `/v1/chat/completions`, `/v1/audio/transcriptions`, `/v1/models`, request-log, and usage regression tests still pass.
- [ ] `git diff --check`, `git diff --cached --check`, targeted `pytest`, and `uvx ruff check` pass.
- [ ] `uv.lock` is clean unless an explicitly approved dependency issue requires changing it.
- [ ] Sprint 3 artifacts and docs contain no raw API keys, OAuth token JSON, database dumps, encryption key material, or full Authorization headers.

## Quick verification commands
```bash
# Baseline and PR inventory
cd /home/vgoro/codex-lb
git status --short --branch
git rev-parse --short HEAD
git diff --name-status v1.15.0...upstream/pr/498 -- app tests openspec frontend docs | sed -n '1,220p'
```

```bash
# Focused image API tests plus linter
cd /home/vgoro/codex-lb
export PATH="/tmp/codex-lb-uv-tool/bin:$PATH"
uv run pytest \
  tests/unit/test_images_schemas.py \
  tests/unit/test_images_translation.py \
  tests/unit/test_strict_schema_validation.py \
  tests/integration/test_proxy_images.py \
  -q
uvx ruff check \
  app/core/openai/images.py \
  app/core/openai/strict_schema.py \
  app/modules/proxy/images_service.py \
  app/modules/proxy/api.py \
  app/modules/proxy/service.py \
  app/core/clients/proxy.py \
  app/core/config/settings.py \
  app/core/usage/pricing.py \
  app/modules/request_logs/repository.py \
  tests/unit/test_images_schemas.py \
  tests/unit/test_images_translation.py \
  tests/unit/test_strict_schema_validation.py \
  tests/integration/test_proxy_images.py
```

```bash
# Existing proxy/accounting regression gate
cd /home/vgoro/codex-lb
export PATH="/tmp/codex-lb-uv-tool/bin:$PATH"
uv run pytest \
  tests/integration/test_openai_compat_features.py \
  tests/integration/test_v1_models.py \
  tests/integration/test_v1_usage.py \
  tests/integration/test_request_logs_api.py \
  tests/integration/test_api_keys_api.py \
  tests/unit/test_proxy_utils.py \
  tests/unit/test_proxy_load_balancer_refresh.py \
  tests/unit/test_request_logs_repository.py \
  -q
uvx ruff check \
  app/core/openai \
  app/modules/proxy \
  app/modules/request_logs \
  app/core/usage \
  tests/integration/test_openai_compat_features.py \
  tests/integration/test_v1_models.py \
  tests/integration/test_v1_usage.py \
  tests/integration/test_request_logs_api.py \
  tests/integration/test_api_keys_api.py \
  tests/unit/test_proxy_utils.py \
  tests/unit/test_proxy_load_balancer_refresh.py \
  tests/unit/test_request_logs_repository.py
```

```bash
# Optional local validation-only route smoke after the app is running.
# This must not generate a real image; it validates request rejection before upstream dispatch.
cd /home/vgoro/codex-lb
: "${CODEX_LB_API_KEY:?set a non-printed operational API key first}"
auth_scheme="Bearer"
auth_header="${auth_scheme} ${CODEX_LB_API_KEY}"
curl -fsS -o /tmp/codex-lb-images-invalid-model.json -w '%{http_code}\n' \
  -H "Authorization: ${auth_header}" \
  -H 'Content-Type: application/json' \
  -d '{"model":"not-an-image-model","prompt":"validation only"}' \
  http://127.0.0.1:2455/v1/images/generations
python3 - <<'PY'
from pathlib import Path
body = Path('/tmp/codex-lb-images-invalid-model.json').read_text()
assert 'invalid_request_error' in body
assert 'not-an-image-model' in body
PY
```

```bash
# Secret-pattern scan for Sprint 3 artifacts without printing matched lines.
cd /home/vgoro/codex-lb
SPRINT3=/home/vgoro/codex-lb-backups/<timestamp>/sprint3
python3 - <<'PY'
from pathlib import Path
root = Path('/home/vgoro/codex-lb-backups/<timestamp>/sprint3')
patterns = [
    'sk-' + 'clb',
    'Bearer' + ' ',
    'OPENAI_' + 'OAUTH',
    'CODEX_LB_' + 'ENCRYPTION_KEY',
]
failures = []
for path in root.rglob('*'):
    if path.is_file():
        data = path.read_bytes()
        text = data.decode('utf-8', errors='ignore')
        hits = [p for p in patterns if p in text]
        if hits:
            failures.append((str(path), len(hits)))
if failures:
    for path, count in failures:
        print(f'{path}: {count} forbidden pattern category hit(s)')
    raise SystemExit(1)
print('secret_scan=PASS')
PY
```

```bash
# Final cleanliness gate
cd /home/vgoro/codex-lb
git diff --check
git diff --cached --check
git diff --exit-code -- uv.lock >/dev/null
git diff --cached --exit-code -- uv.lock >/dev/null
git status --short --branch
```

## Important gotchas
- PR #498 is merged into upstream `main` but is not part of `v1.15.0`; treat `upstream/pr/498` or the `v1.15.0...upstream/pr/498` range as a patch source, not as permission to merge unrelated upstream drift.
- The PR is API-heavy: `app/modules/proxy/api.py` grows substantially and `app/modules/proxy/service.py` has local Sprint 1/Sprint 2 changes. Resolve conflicts manually and preserve 1.15.0 text proxy behavior.
- The public model is `gpt-image-*`, but the internal Responses host model is a text model such as `gpt-5.5`. If accounting, request logs, or API-key limits use the host model after the swap, dashboards and limits will be wrong.
- Image responses can contain large base64 SSE events. Auto transport should prefer HTTP/SSE for internal `image_generation` tool calls; websocket-preferred model behavior is not safe for large image payloads.
- `n > 1` is intentionally rejected until a later fan-out design exists. Do not add a config knob that promises multi-image support without implementing and testing fan-out.
- `/v1/images/edits` multipart handling must accept repeated `image` fields and `image[]`; it must avoid writing uploaded binary image content into logs or artifacts.
