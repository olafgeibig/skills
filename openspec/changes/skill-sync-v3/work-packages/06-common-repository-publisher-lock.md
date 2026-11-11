# Packet 06 — Common-repository publisher lock

**OpenSpec task group:** 6 in `../tasks.md`.
**Prerequisites:** All earlier packets through 05, parent-verified. Default execution is serialized.

## Minimal context to read

- `README.md` (dispatch protocol).
- `../proposal.md` once if the worker has no change context.
- `../specs/skill-merge-publication/spec.md`.
- `../design.md`: D6.
- Contract scope: Implement lock primitive before publication; future publish/reconcile must acquire it once, not recursively.

## Allowed changed files

- `skills/skill-library-maintenance/scripts/skill_repo_workflow.py`
- `skills/skill-library-maintenance/tests/test_skill_repo_workflow.py`
- `skills/skill-library-maintenance/references/shared-repo-sync.md`

No other production/config/profile/vault files. Read predecessor definitions/usages before editing; if required interface changes cross ownership, return that dependency to the parent. Parent alone updates task checkboxes.

## Required behavior and traps

Test alternate stores pointing to linked publisher worktrees, wrong owner, backdated lock and an independently writable producer. The lock path is Git common-dir, never per-worktree gitdir or arbitrary store.

## Implementation checkpoints (red → green, then review)

**D5. Lock ownership and exclusion.** Add core `acquire_publisher_lock(store) -> str` and `release_publisher_lock(store, token)`; both load publisher_repo from config and derive its Git **common directory**, never a per-worktree gitdir. `test_publisher_lock_is_owned_and_never_age_broken`: acquire; second acquire refuses; wrong token release refuses; artificially backdate the common-dir lock then still refuses; correct release succeeds. Add `test_linked_worktrees_and_alternate_stores_share_publisher_lock`: create two store configs pointing at linked worktrees of one publisher clone, acquire through the first, assert the second refuses; an unrelated producer clone remains writable. `publish`, `reconcile` and explicit refactor integration share this single lock. Remove arbitrary executions.db cron claim scan. Any manual break requires observed executor absence and an explicit recovery command naming the stored owner token; never infer death from a helper CLI PID that already exited.

## Verification and handoff

Run each named regression node to prove its intended failure before implementation and pass after. Then run the affected test file and full package suite from the authorized worktree; exact commands are in README.md. Run `git diff --check`. Return changed paths, symbol/API deltas, actual test exit/pass results, source/ref/tree evidence where relevant, blockers and successor context. Do not commit/push, touch live jobs, archive, check global tasks, or claim an unavailable check passed.
