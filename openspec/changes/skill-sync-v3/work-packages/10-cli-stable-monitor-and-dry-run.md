# Packet 10 — CLI, stable monitor and dry run

**OpenSpec task group:** 10 in `../tasks.md`.
**Prerequisites:** All earlier packets through 09, parent-verified. Default execution is serialized.

## Minimal context to read

- `README.md` (dispatch protocol).
- `../proposal.md` once if the worker has no change context.
- `../specs/skill-merge-publication/spec.md`.
- `../specs/skill-source-transport/spec.md`.
- `../design.md`: D3, D7.
- Contract scope: Read contracts Proposed CLI surface, state machine and fixed exit codes.

## Allowed changed files

- `skills/skill-library-maintenance/scripts/skill-repo-consolidate.py`
- `skills/skill-library-maintenance/scripts/skill-repo-sync.py`
- `skills/skill-library-maintenance/scripts/skill_repo_workflow.py`
- `skills/skill-library-maintenance/tests/test_skill_repo_workflow.py`
- `skills/skill-library-maintenance/tests/test_skill_repo_sync.py`
- `skills/skill-library-maintenance/tests/test_skill_repo_consolidate.py`
- `skills/skill-library-maintenance/references/shared-repo-sync.md`
- `skills/skill-library-maintenance/references/install-and-update.md`
- `skills/skill-library-maintenance/assets/consolidate-monitor-script.sh.example`

No other production/config/profile/vault files. Read predecessor definitions/usages before editing; if required interface changes cross ownership, return that dependency to the parent. Parent alone updates task checkboxes.

## Required behavior and traps

Do not resurrect deprecated flags behind adapters. Snapshot every local/remote state before dry-run, including FETCH_HEAD and index. Empty-diff pending must be included; no timestamp-driven idle loops or invisible fetch errors.

## Implementation checkpoints (red → green, then review)

**E3. Stable pending, health failures and blocked retries.** Implement `pending_lines` and HELPER `--pending`. Only enabled registered `machine/*` refs plus explicitly submitted refactors; exclude other refs and consumed tips, never discard an unacknowledged empty-diff tip. Sorted lines `pending <cid>` including unacknowledged empty-diff tips; technical monitor errors stable stdout `error: monitor-unhealthy` plus stderr diagnostics, so first failure and recovery change hash. Same blocked candidate is a stable `blocked <cid>` signal, not repeated timestamp churn; agent stops/sends report, not retry unchanged work automatically. `--retry cid` increments explicit retry generation in state and monitor key once. Tests `test_pending_excludes_unsubmitted_refactor_and_consumed_tips`, `test_pending_error_signal_is_stable`, `test_retry_changes_monitor_once`.

**E4. Dry run truly writes nothing.** Parameterize CLI tests across `--stage`, `--sync-from-main`, capture, prepare, record-review, render/verify report, publish, retry and submit-refactor; snapshot state bytes, HEAD, local refs including FETCH_HEAD, index, worktree inventory, report files and bare remote refs. `--dry-run` checks cached refs and prints intended actions only; no fetch, mkdir, update-ref, worktree add or lock acquisition. In an unavailable cached context report “cannot determine without fetch” and leave bytes untouched, not fabricate a pending list. No old CLI mode remains as a hidden state-mutating bypass.

**E5. CLI adapters use CORE only.** Tests invoke real subprocess HELPER with isolated store/config for capture→prepare→record-review→render→verify→publish→reconcile. stdout machine-readable JSON for action modes, stderr diagnostics; only pending uses stable line protocol. `--help` lists new modes and explicit retired-mode guidance. `--selfcheck` reports versions, transport branch policy, config/report root presence, no fabricated hook health (separate Hermes doctor). Missing config exit 13. Refuse store publisher_repo different from explicit CLI --repo. Keep configured wrapper command path stable; do not widen hook auto-consent.

## Verification and handoff

Run each named regression node to prove its intended failure before implementation and pass after. Then run the affected test file and full package suite from the authorized worktree; exact commands are in README.md. Run `git diff --check`. Return changed paths, symbol/API deltas, actual test exit/pass results, source/ref/tree evidence where relevant, blockers and successor context. Do not commit/push, touch live jobs, archive, check global tasks, or claim an unavailable check passed.
