# codex-lb Sprint 1 blockers

No active blocker.

# codex-lb Sprint 5 release availability blocker

- ID: T7 / release availability for upstream `v1.16` candidate
- Status: BLOCKED pending official upstream ref
- Evidence: `/home/vgoro/codex-lb-backups/20260504-231326/sprint5/baseline/release-availability.txt`
- Marker: release_availability_gate=BLOCKED
- Details: `git ls-remote --tags upstream refs/tags/v1.16*` returned no refs during Sprint 5 baseline capture, so Sprint 5 must not create a fake 1.16 candidate or run 1.16 cutover tasks until an official upstream `v1.16*` ref exists and the operator approves candidate work.

## Sprint 5 blocker — T22 frontend candidate gates
- ID: T22 / frontend candidate gates
- Status: SUPERSEDED by explicit operator approval for `refs/pull/490/head` / `1c305eb6913255757744470b829ad589f69d1f24`.
- Problem: official `refs/tags/v1.16*` remained absent, but the operator explicitly approved PR490 as the release-candidate ref for T22.
- Error/output: historical baseline had `refs_found_1=0`, `refs_found_2=0`, `refs_found_3=0`.
- Artifact: `/home/vgoro/codex-lb-backups/20260504-231326/sprint5/tests/frontend-candidate-gates.txt`
- Current action: T22 rerun against operator-approved PR490 candidate with a minimal candidate/worktree test-env patch; final gate passed.

### Sprint 5 T22 frontend candidate gates blocker
- `refs/pull/490/head` / `1c305eb6913255757744470b829ad589f69d1f24` was operator-approved as the `1.16.0` release-candidate ref despite no `refs/tags/v1.16*` tag.
- Live cutover was not run.
- Artifact: `/home/vgoro/codex-lb-backups/20260504-231326/sprint5/tests/frontend-candidate-gates.txt`.
- Initial result: `frontend_candidate_gates_gate=BLOCKED_BY_VALIDATION_FAILURE`; `bun run test` failed in the candidate worktree due to Vitest/Vite SSR resolving `import { z } from "zod"` as undefined.
- Resolution: minimal candidate/worktree patch added `test.server.deps.inline: ["zod"]` in `frontend/vite.config.ts`. Patched gates passed: `bun run lint`, `bun run typecheck`, `bun run test`, and `bun run build`. T22 is no longer blocked by this validation failure; live cutover was not run.


### Sprint 5 T22 resolution — PR490 frontend gates passed with minimal patch
- Candidate ref: `refs/pull/490/head` / `1c305eb6913255757744470b829ad589f69d1f24`.
- Minimal patch artifact: `/home/vgoro/codex-lb-backups/20260504-231326/sprint5/tests/t22-zod-vitest-minimal.patch`.
- Gate evidence: `/home/vgoro/codex-lb-backups/20260504-231326/sprint5/tests/t22-zod-vitest-patch-gates.txt`.
- Final T22 artifact: `/home/vgoro/codex-lb-backups/20260504-231326/sprint5/tests/frontend-candidate-gates.txt`.
- Final marker: `frontend_candidate_gates_gate=PASS`.
- Live cutover: not performed.
