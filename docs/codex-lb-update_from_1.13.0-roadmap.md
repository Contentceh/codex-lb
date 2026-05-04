# codex-lb update from 1.13.0 to 1.15.0 Roadmap

Repo: `/home/vgoro/codex-lb`
Upstream: `https://github.com/Soju06/codex-lb`
Target upstream release: `v1.15.0`
Post-1.15 feature target: `Soju06/codex-lb#498` — OpenAI-compatible `/v1/images` API for `gpt-image-2` via the internal `image_generation` tool.
Created: 2026-05-03
Mode: Tech Lead roadmap and sprint planning only; implementation work happens in later coding sprints.

## Objective

Upgrade the current `codex-lb` deployment from the local 1.13.0-derived state to upstream `v1.15.0`, preserving existing accounts, API keys, dashboard settings, OAuth/encryption material, request history, and Docker runtime assumptions. After the 1.15.0 upgrade is stable, add a maintainable `gpt-image-2` capability based on PR #498 in a way that can be replaced or rebased cleanly when upstream 1.16 is released.

## Research snapshot

- `docs/roadmap.md` and `docs/codex-lb-update_from_1.13.0-roadmap.md` were not present before this roadmap was created.
- After Sprint 1 and Sprint 2, source/runtime version markers are on `1.15.0` in `pyproject.toml`, `frontend/package.json`, and `app/__init__.py`; live Docker cutover evidence is recorded under `/home/vgoro/codex-lb-backups/20260504-073434/sprint2/`.
- Runtime containers observed on `Debian-n8n`: `codex-lb-server-1` and `codex-lb-frontend-1`, using local images `codex-lb-server` and `codex-lb-frontend`.
- The active Docker data volume is `localai_codex-lb-data`; it must be preserved because it contains account/session/settings state under `/var/lib/codex-lb`.
- `docker-compose.yml` models the observed two-service local build deployment (`server`, `frontend`). `docker-compose.prod.yml` currently contains a stale single-service image reference to `ghcr.io/soju06/codex-lb:1.8.1`; do not blindly use it for cutover without reconciling it with the actual runtime.
- Current stable upgrade branch: `upgrade/from-1.13.0-to-1.15.0`; Sprint 2 final docs/evidence commit is `a6b32756c2a91620536b031bcd7eff6241f160ca`. Remotes remain `origin=https://github.com/Contentceh/codex-lb.git`, `upstream=https://github.com/Soju06/codex-lb.git`.
- Upstream tags fetched for planning: `v1.13.1`, `v1.14.0`, `v1.14.1`, `v1.15.0`. PR #498 was fetched as `upstream/pr/498` for inspection only.
- Retained unstaged non-doc/code work remains after Sprint 2 and must be preserved before Sprint 3 branch isolation; do not discard it without an explicit operator decision.
- Upstream `v1.15.0` includes important proxy fixes and GPT-5.5/GPT-5.5 Pro support, plus migrations for request log lookup and plan type metadata.
- PR #498 is merged into upstream `main` but is not part of `v1.15.0`. It is available locally as `upstream/pr/498` for patch-source inspection. The `v1.15.0...upstream/pr/498` range touches `app/core/openai/images.py`, `app/core/openai/strict_schema.py`, `app/modules/proxy/images_service.py`, `app/modules/proxy/api.py`, `app/modules/proxy/service.py`, `app/core/clients/proxy.py`, `app/core/config/settings.py`, `app/core/usage/pricing.py`, `app/modules/request_logs/repository.py`, OpenSpec docs, and image/proxy tests. Keep this isolated so it can be dropped or rebased when upstream 1.16 lands.
- Sprint 3 implementation checklist created at `docs/codex-lb-update_from_1.13.0-sprint3-checklist.md`; it plans an isolated code/test integration sprint with no live Docker cutover and no real image-generation smoke until Sprint 4.

## Non-negotiable constraints

- Preserve existing accounts/settings/API keys by preserving the Docker data volume and encryption key material.
- Never store raw account backups, OAuth tokens, `.env` values, or database dumps under `docs/` or in Git.
- Use tests and linters together as sprint artifacts; no code sprint is complete with tests-only evidence.
- Keep the PR #498 image work as a separate patch series on top of the stable 1.15.0 branch so it can be dropped or rebased when upstream 1.16 lands.
- Do not change public DNS, Telegram/OpenClaw config, or unrelated services as part of this roadmap.

## Roadmap

### [x] Sprint 1 — Upgrade foundation to upstream v1.15.0

Purpose: create a safe, reviewable branch that converges the local fork with upstream `v1.15.0`, protects current local hotfixes, and proves data/runtime compatibility in a controlled Docker smoke environment.

Includes:

- Capture current repo, container, and volume baseline without exposing secrets.
- Back up the Docker data volume outside the Git repository.
- Preserve the current `stream_incomplete` hotfix patch before merging.
- Merge or rebase upstream `v1.15.0` into the local branch.
- Resolve conflicts in proxy, OpenSpec, tests, compose, and version files.
- Verify Alembic migration heads and request log schema compatibility.
- Run backend tests plus `ruff`/`ty`; run frontend lint/typecheck/test/build.
- Reconcile Docker compose strategy with the observed `server` + `frontend` runtime.

Exit criteria:

- A branch exists that reports version `1.15.0` and includes required local hotfix behavior or a documented reason it is no longer needed.
- Tests and linters pass with logs captured in a non-secret artifact.
- Existing Docker data can boot through `/health/live` and `/health/ready` in a controlled smoke run.
- No PR #498 image API code is included yet.

### [x] Sprint 2 — Docker cutover and live 1.15.0 compatibility validation

Purpose: deploy the 1.15.0 branch on `Debian-n8n` while preserving the current account/settings data and keeping a clean rollback path.

Includes:

- Take a fresh pre-cutover data volume backup outside the repository.
- Build/pull final images according to the selected compose strategy.
- Restart only the `codex-lb` stack, not unrelated Docker services.
- Confirm migrations complete against the real data store.
- Validate dashboard login/settings, account list, API key list, model list, request logs, and basic proxy calls.
- Document rollback commands and the exact pre-upgrade image/commit/volume backup.

Exit criteria:

- Live deployment is on 1.15.0.
- Existing accounts and dashboard/API settings remain visible and usable.
- Health endpoints and a minimal authenticated proxy smoke test pass.
- Rollback instructions and backup location are documented privately outside Git if they contain secrets.
- Sprint 2 evidence bundle and completion docs commit are recorded.

### [ ] Sprint 3 — Integrate PR #498 as an isolated image API patch

Purpose: add OpenAI-compatible `/v1/images` support for `gpt-image-2` on top of the stable 1.15.0 deployment branch without mixing unrelated upstream drift.

Includes:

- Create an isolated branch on top of `upgrade/from-1.13.0-to-1.15.0` after the Sprint 2 completion commit.
- Preserve retained unstaged local work before importing the image patch; do not discard worktree changes without an operator decision.
- Port PR #498 as a separable patch source from `upstream/pr/498` / `v1.15.0...upstream/pr/498`.
- Add OpenAI Images request/response schemas, strict validation, and `gpt-image-*` parameter rules.
- Add `/v1/images/generations` and `/v1/images/edits` as a translation layer over internal Responses `image_generation` tool calls.
- Keep `/v1/images/variations` explicitly unsupported.
- Force safer HTTP/SSE upstream transport for image-generation tool traffic when auto transport would otherwise choose websocket.
- Apply API-key allowed-model policy, request reservations, request logs, usage summaries, and pricing against the public `gpt-image-*` model, not the hidden host model.
- Port PR #498 OpenSpec docs and tests, then run targeted image tests plus existing 1.15.0 proxy/accounting regressions with `ruff`.

Exit criteria:

- Image API unit/integration tests from the PR pass on the 1.15.0 branch.
- Existing 1.15.0 Responses/Chat/Audio/Models/Usage/Request-log regressions still pass.
- The patch is kept in small commits that can be rebased or replaced when upstream 1.16 includes equivalent functionality.
- No Sprint 3 artifact contains raw keys, token JSON, database dumps, encryption key material, or full Authorization headers.
- Sprint 3 evidence is recorded and the roadmap/checklist are updated only after tests and linters pass.

### [ ] Sprint 4 — gpt-image-2 hardening and live smoke

Purpose: validate the image API behavior with real accounts and operational limits without destabilizing text proxy traffic.

Includes:

- Live smoke for non-streaming and streaming image generation with conservative limits.
- Confirm `n > 1` and unsupported models/sizes/backgrounds fail predictably.
- Confirm request logs show the public `gpt-image-*` model rather than the internal host model.
- Document operational settings (`images_default_model`, `images_host_model`, image limits) and rollback.

Exit criteria:

- `gpt-image-2` works through the `codex-lb` API with existing account pool auth.
- Text/model proxy surfaces remain healthy after image traffic.
- Runtime settings are documented and no secrets are committed.

### [ ] Sprint 5 — 1.16 readiness and upstream alignment

Purpose: minimize long-term fork burden once upstream 1.16 appears.

Includes:

- Track upstream release notes and compare `v1.15.0..v1.16.0` against the local image branch.
- Decide whether to drop, rebase, or keep the PR #498 patch depending on upstream inclusion.
- Re-run the 1.15.0 upgrade and image API quality gates against the 1.16 candidate.
- Update deployment docs with the final chosen path.

Exit criteria:

- The local fork has a clear migration path to 1.16.
- Any temporary PR #498 patch is either removed, rebased cleanly, or documented as intentionally retained.

## First sprint selected

Sprint 1 — Upgrade foundation to upstream `v1.15.0` and Sprint 2 — Docker cutover and live 1.15.0 compatibility validation are completed. Sprint 3 — Integrate PR #498 as an isolated image API patch is now selected and planned in `docs/codex-lb-update_from_1.13.0-sprint3-checklist.md`.

## Open risks

- The observed runtime and `docker-compose.prod.yml` disagree; deploying the stale prod compose could downgrade or replace the current two-container setup unexpectedly.
- The account/settings data is tied to the existing Docker volume and encryption key. A volume rename, missing key, or accidental fresh volume would look like data loss even if the code upgrade is correct.
- PR #498 is large and touches proxy routing, request logs, OAuth/service behavior, and strict schema validation. It should not be mixed into the base 1.15.0 merge.
- Image-generation Responses events can carry large base64 payloads; Sprint 3 must force HTTP/SSE where appropriate and keep websocket behavior unchanged for non-image traffic.
- The internal image host model must never leak into public model policy, request logs, pricing, or `/v1/models`; use the public `gpt-image-*` value for external accounting.
