# Packet 08 — Recovery and publication receipts

**OpenSpec task group:** 8 in `../tasks.md`.
**Prerequisites:** All earlier packets through 07, parent-verified. Default execution is serialized.

## Minimal context to read

- `README.md` (dispatch protocol).
- `../proposal.md` once if the worker has no change context.
- `../specs/skill-merge-publication/spec.md`.
- `../specs/skill-review-reporting/spec.md`.
- `../design.md`: D5.
- Contract scope: Read contracts Promotion and state machine; use saved P from packet 07.

## Allowed changed files

- `skills/skill-library-maintenance/scripts/skill_repo_workflow.py`
- `skills/skill-library-maintenance/tests/test_skill_repo_workflow.py`
- `skills/skill-library-maintenance/references/shared-repo-sync.md`

No other production/config/profile/vault files. Read predecessor definitions/usages before editing; if required interface changes cross ownership, return that dependency to the parent. Parent alone updates task checkboxes.

## Required behavior and traps

Inject failures around real Git, not fabricated success. Crash after actual push must reconcile without duplicate integration; unavailable remote is unknown outcome. Result receipt is separate immutable/idempotent delivery, not overwrite of pre-push report.

## Implementation checkpoints (red → green, then review)

**D6. Durable intent before push.** `test_push_failure_retains_same_result_for_retry`: simulate push process failing (read real commit-tree result first); state has publish-intent and P, source unchanged. Restore remote, `reconcile` pushes the **same P** if main still M; no second integration commit. Use `monkeypatch` on CORE.git only to fail args starting `push`; don't fake successful Git output.

**D7. Crash after remote push and before status update.** `test_reconcile_after_push_does_not_duplicate`: test hook raises after actual local bare-remote push, reload process/module, journal still intent, remote P. `reconcile` proves P ancestors and trailers; marks published/receipt-pending without creating/pushing another commit. Repeat again idempotently. Add missing/tampered report after push -> incident reported, not reinterpret as never published.

**D8. Publication receipt retries are separate.** `test_receipt_failure_does_not_republish`: render_result includes exact P and remote verified status; fixture destination unavailable initially, then receipt write/read-back succeeds. Result verify method `verify_result(store,cid,report_root)` compares expected bytes and marks complete. No overwrite of immutable review. Result filename `<cid>-result.md`, generated timestamp fixed when publication observed to retain idempotency.

## Verification and handoff

Run each named regression node to prove its intended failure before implementation and pass after. Then run the affected test file and full package suite from the authorized worktree; exact commands are in README.md. Run `git diff --check`. Return changed paths, symbol/API deltas, actual test exit/pass results, source/ref/tree evidence where relevant, blockers and successor context. Do not commit/push, touch live jobs, archive, check global tasks, or claim an unavailable check passed.
