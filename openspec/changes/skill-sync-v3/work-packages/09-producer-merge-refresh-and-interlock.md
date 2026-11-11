# Packet 09 — Producer merge refresh and interlock

**OpenSpec task group:** 9 in `../tasks.md`.
**Prerequisites:** All earlier packets through 08, parent-verified. Default execution is serialized.

## Minimal context to read

- `README.md` (dispatch protocol).
- `../proposal.md` once if the worker has no change context.
- `../specs/skill-source-transport/spec.md`.
- `../design.md`: D1, D2.
- Contract scope: Read contracts Producer refresh; use actual v3 publisher tests/fixtures from prior packets where needed.

## Allowed changed files

- `skills/skill-library-maintenance/scripts/skill-repo-sync.py`
- `skills/skill-library-maintenance/scripts/skill_repo_workflow.py`
- `skills/skill-library-maintenance/tests/test_skill_repo_sync.py`
- `skills/skill-library-maintenance/tests/test_skill_repo_workflow.py`
- `skills/skill-library-maintenance/references/shared-repo-sync.md`
- `skills/skill-library-maintenance/assets/pre-consolidation-cron-prompt.md.example`

No other production/config/profile/vault files. Read predecessor definitions/usages before editing; if required interface changes cross ownership, return that dependency to the parent. Parent alone updates task checkboxes.

## Required behavior and traps

FF whenever possible to avoid echo loops. Divergence preserves local work and requires deliberate merge. Push exact reviewed T rather than current branch name; a later staged T2 must remain unreviewed/unpublished.

## Implementation checkpoints (red → green, then review)

**E1. Session refresh is no-op/FF-only.** Modify ENGINE, SYNC_TEST. `test_refresh_fast_forwards_consumed_source` creates an **actual v3 publisher merge**, then refreshes clean producer branch; HEAD FFs to main, no reset/rebase, source branch name preserved. `test_refresh_diverged_work_is_preserved`: producer C beyond T, main P parents M,T; session hook reports pre-consolidation merge required, preserves C/index and dirty bytes. Pre-consolidation test merges P into C using Git merge; both new lesson C and curated P remain (genuine same-line conflicts require an agent resolution, not an automatic ours strategy). Remove all rev-list last_pushed_tip reset/replay tests, replace with merge ancestry assertions plus reason comments. Daily push is normal FF; no claim of automatic resume-triggered LLM.

**E2. Staging/pre-consolidation interlock.** Existing stage and manual pre-consolidation can overlap; add a producer-repo lock under `git rev-parse --git-common-dir` for the short staging and push/merge operations. Background writers of files still require read-before-write; do not lock for an entire chat. `test_stage_refuses_preconsolidation_lock` and reciprocal test verify no index/status change. Before a push, capture reviewed HEAD T and push `T:source_ref`, **not current branch name** that a later sweep might advance; verify remote T, then record last_pushed_tip=T. Test a new local commit arriving between review and push is not published. This retains the pre-consolidation push gate without pretending every working-copy change is ready.

**History exposure gate (OpenSpec task 9.5).** Before sharing a source snapshot T, inspect the unpublished commit range relative to the last verified remote source tip, including additions in intermediate commits that the latest tree deleted. Mechanical screening emits only path/category diagnostics for forbidden file names and suspected credential patterns; do not print detected values. Semantic source pre-consolidation must explicitly classify profile scope across that history, not claim a regex proves all content safe. Persist its review result bound to exact T; push must refuse a missing or mismatched history review. Add `test_source_history_removed_exposure_still_blocks_push`: a temporary producer commit introduces clearly synthetic fixture-only prohibited content, another removes it, final tree looks clean, but attempted source publication is blocked and the bare remote ref remains unchanged. Never read or use real credentials as fixtures; already-pushed exposure is a separate incident, not automatically repaired through force or main-tree redaction.

## Verification and handoff

Run each named regression node to prove its intended failure before implementation and pass after. Then run the affected test file and full package suite from the authorized worktree; exact commands are in README.md. Run `git diff --check`. Return changed paths, symbol/API deltas, actual test exit/pass results, source/ref/tree evidence where relevant, blockers and successor context. Do not commit/push, touch live jobs, archive, check global tasks, or claim an unavailable check passed.
