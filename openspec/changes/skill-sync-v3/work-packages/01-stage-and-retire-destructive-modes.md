# Packet 01 — Stage and retire destructive modes

**OpenSpec task group:** 1 in `../tasks.md`.
**Prerequisites:** All earlier packets through 00, parent-verified. Default execution is serialized.

## Minimal context to read

- `README.md` (dispatch protocol).
- `../proposal.md` once if the worker has no change context.
- `../specs/skill-source-transport/spec.md`.
- `../specs/skill-merge-publication/spec.md`.
- `../design.md`: D1, D3.
- Contract scope: No CORE dependency yet; keep retired CLI modes fail-closed while new workflow is built.

## Allowed changed files

- `skills/skill-library-maintenance/scripts/skill-repo-sync.py`
- `skills/skill-library-maintenance/scripts/skill-repo-consolidate.py`
- `skills/skill-library-maintenance/tests/test_skill_repo_sync.py`
- `skills/skill-library-maintenance/tests/test_skill_repo_consolidate.py`
- `skills/skill-library-maintenance/references/shared-repo-sync.md`

No other production/config/profile/vault files. Read predecessor definitions/usages before editing; if required interface changes cross ownership, return that dependency to the parent. Parent alone updates task checkboxes.

## Required behavior and traps

Tests must prove actual unchanged bare refs for reset refusal, no rebase invocation, branch exclusion, missing ledger path handling, rollback on failure, and cursor snapshot under a concurrent append.

## Implementation checkpoints (red → green, then review)

**A1. Retire dangerous publication operations.** Modify HELPER and OLD_TEST; add `test_retired_reset_never_writes_remote` that offers a pending T, invokes real HELPER with `--reset-branch testlab --confirm-consumed --repo <publisher>` and isolated HERMES_HOME, asserts exit 12 and bare-remote `main`/transport refs unchanged. Add equivalent rebase prohibition test by mocking subprocess to raise if `rebase` is invoked. Retire old `reset_branches` and refresh rebase implementation; old flags cannot still work behind new docs. Red initially: reset succeeds and moves the remote; green: exact `retired:` diagnostic. Update old tests deliberately, retaining no-data-loss intent.

**A2. Skip refactor worktrees, refuse main.** Modify ENGINE, SYNC_TEST. Using existing `setup_repo` fixture: checkout `refactor/topic`, dirty tracked skill, run `--stage`; assert no commit/index/state change and diagnostic `refactor branch: excluded from sweep`. On `main` even clean return 12 for policy mismatch, not green health; preserve dirty main too. Explicitly no branch checkout performed by stage.

**A3. Fix stale ledger path and retry.** Modify ENGINE, SYNC_TEST. Add `test_stage_skips_missing_untracked_ledger_path`: one missing never-tracked ledger path plus valid tracked edit; commit only valid path, record skip in stage report and advance processed cursor. Preserve real tracked deletions. Add `test_stage_whitespace_failure_is_retryable`: trailing-space failure leaves index empty, fix file then next stage succeeds. Because initial index must be empty, rollback **only paths added by this invocation** with `git reset -q -- <paths>` on whitespace/commit failure; don't alter file bytes. Cursor advances to **the entries snapshot read before staging**, not a fresh `len(read_ledger())` that could acknowledge a later writer's entries. Add test appending ledger during commit to prove new row remains pending. NUL-separated Git path enumeration; no shell path interpolation.

## Verification and handoff

Run each named regression node to prove its intended failure before implementation and pass after. Then run the affected test file and full package suite from the authorized worktree; exact commands are in README.md. Run `git diff --check`. Return changed paths, symbol/API deltas, actual test exit/pass results, source/ref/tree evidence where relevant, blockers and successor context. Do not commit/push, touch live jobs, archive, check global tasks, or claim an unavailable check passed.
