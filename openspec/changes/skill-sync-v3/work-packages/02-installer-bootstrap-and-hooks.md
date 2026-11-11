# Packet 02 — Installer bootstrap and hooks

**OpenSpec task group:** 2 in `../tasks.md`.
**Prerequisites:** All earlier packets through 01, parent-verified. Default execution is serialized.

## Minimal context to read

- `README.md` (dispatch protocol).
- `../proposal.md` once if the worker has no change context.
- `../specs/skill-source-transport/spec.md`.
- `../design.md`: D3.
- Contract scope: Use the existing installer_fixture/install_hermes_stub definitions after reading them; update their old policy assertions deliberately.

## Allowed changed files

- `skills/skill-library-maintenance/scripts/install-skill-repo-sync.py`
- `skills/skill-library-maintenance/tests/test_skill_repo_sync.py`
- `skills/skill-library-maintenance/references/install-and-update.md`

No other production/config/profile/vault files. Read predecessor definitions/usages before editing; if required interface changes cross ownership, return that dependency to the parent. Parent alone updates task checkboxes.

## Required behavior and traps

Never call the real Hermes config setter from tests. Parse fake config JSON, preserve exact unrelated entries, reject missing bootstrap before any writes, and preserve existing cursors.

## Implementation checkpoints (red → green, then review)

**A4. Make fresh bootstrap explicit and preserve hooks.** Modify INSTALL, SYNC_TEST. Add tests fresh state without `--bootstrap-current-ledger` refuses **before writes/chmod**, with flag records initial cursor, existing state+flag refuses. Extend fake Hermes fixture to return JSON for `config get hooks.on_session_start --json`; installer appends exact wrapper hook while preserving unrelated mappings; never blanket-clear `on_skill_lifecycle`. Existing expected `len(set_calls)==2` is obsolete; assert exact preserved list and no lifecycle set. Fail closed on malformed config response. Save engine/installer version 3.0.0 consistently once approved.

Authorized checkpoint commits: explicit paths for each changed ENGINE/HELPER/INSTALL and their actual tests. Messages `fix(sync): retire reset/rebase publication`, `fix(sync): exclude refactoring from sweeps`, `fix(sync): keep stage failures retryable`, `fix(sync): preserve hooks and require bootstrap` respectively.

### Phase B — new core capture and native merge

## Verification and handoff

Run each named regression node to prove its intended failure before implementation and pass after. Then run the affected test file and full package suite from the authorized worktree; exact commands are in README.md. Run `git diff --check`. Return changed paths, symbol/API deltas, actual test exit/pass results, source/ref/tree evidence where relevant, blockers and successor context. Do not commit/push, touch live jobs, archive, check global tasks, or claim an unavailable check passed.
