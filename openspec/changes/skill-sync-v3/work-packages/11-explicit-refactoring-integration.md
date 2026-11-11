# Packet 11 — Explicit refactoring integration

**OpenSpec task group:** 11 in `../tasks.md`.
**Prerequisites:** All earlier packets through 10, parent-verified. Default execution is serialized.

## Minimal context to read

- `README.md` (dispatch protocol).
- `../proposal.md` once if the worker has no change context.
- `../specs/skill-refactor-integration/spec.md`.
- `../design.md`: D2, D6.
- Contract scope: Read contracts refactor CLI/config identity and Promotion; require existing common publisher lock.

## Allowed changed files

- `skills/skill-library-maintenance/scripts/skill_repo_workflow.py`
- `skills/skill-library-maintenance/tests/test_skill_repo_workflow.py`
- `skills/skill-library-maintenance/references/shared-repo-sync.md`

No other production/config/profile/vault files. Read predecessor definitions/usages before editing; if required interface changes cross ownership, return that dependency to the parent. Parent alone updates task checkboxes.

## Required behavior and traps

Unsubmitted backup branches are not ready. Refactor M ancestor T and tree(P)==tree(T); fixes require new T. Producer work continues while publisher lock is held. Never create/migrate live refactor worktrees inside a test.

## Implementation checkpoints (red → green, then review)

**F1. Branch readiness is explicit.** `submit_refactor` stores only operator-submitted exact ref+T+brief, resolves and pins T, verifies ref prefix, no automatic pickup of a random backup branch. Submission identity/scope comes from configured `publisher_identity`, not a caller-supplied arbitrary profile; only the authorized publisher profile may submit. The existing `capture(..., kind="refactor")` requires a matching pinned submission record and never adds `refactor/*` to transport discovery. Brief required `{summary, intended_replacements:[{path,old_quote,new_instruction,reason}], validation_notes}`; no arbitrary commands. T must be actual remote tip and must contain captured M (`is_ancestor(M,T)`). `test_refactor_requires_explicit_tip_submission`: push refactor remote, pending excludes it; submit, now pending; advance source tip afterward doesn't change submission T. Submission with absent M ancestry returns stale/needs-main-merge, not a rebase. Invalid source content scope still blocks.

**F2. True refactor merge retains exact reviewed tree.** `test_refactor_promotion_tree_equals_submitted_tip`: fork refactor, make intended replacement, merge newer main into it with `git merge` (fixture actually changes main after fork), push new T, submit, review/check/report, publish. Assert P parents `[M,T]`, tree(P)==tree(T), source branch untouched, main ancestry preserved. For refactor `validate_tree` must reject any agent-added file edits after submission (unlike normal transport semantic curation). If a fix is needed, commit it on refactor branch and submit a **new T/cid**. No surprise edits during final promotion.

**F3. Integration freeze blocks publisher, not producers.** `test_refactor_freeze_allows_producer_commits`: hold publisher lock in a refactor-integration test; another publisher action refuses, but separate producer stage+normal push succeeds to T2; after release normal source remains pending. Test final main move causes stale refactor submission and requires merge-main/review again. Never block by locking the shared runtime repo for the whole refactoring duration. For prolonged final review, release short lock and retry against new M.

**F4. Refactor worktree creation/use runbook, not automatic branch switching.** In RUNBOOK document exact future commands with resolved variables:

```bash
# Values must be resolved/approved before use; these are FUTURE execution examples.
git -C "$SOURCE_REPO" fetch origin
git -C "$SOURCE_REPO" worktree add -b refactor/skill-sync "$REFACTOR_WORKTREE" origin/main
git -C "$REFACTOR_WORKTREE" merge origin/main
# Normal small explicit-path commits during implementation; no rebase.
# Push for backup is not readiness:
git -C "$REFACTOR_WORKTREE" push origin HEAD:refs/heads/refactor/skill-sync
```

A refactor worktree is not a skills discovery root. Run candidate workflow tool code from trusted publisher baseline, not the candidate's unreviewed new scripts. Before self-updating publisher logic restart between completed runs from verified main; do not swap tool code midway through promotion. No copies of raw production keys or config are placed in test homes. If background review can reach this development worktree, disable it only for the actual editing profile/pass with notification and restore afterward; do not claim a global cross-machine freeze was necessary.

## Verification and handoff

Run each named regression node to prove its intended failure before implementation and pass after. Then run the affected test file and full package suite from the authorized worktree; exact commands are in README.md. Run `git diff --check`. Return changed paths, symbol/API deltas, actual test exit/pass results, source/ref/tree evidence where relevant, blockers and successor context. Do not commit/push, touch live jobs, archive, check global tasks, or claim an unavailable check passed.
