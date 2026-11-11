# Packet 04 — Native merge preparation

**OpenSpec task group:** 4 in `../tasks.md`.
**Prerequisites:** All earlier packets through 03, parent-verified. Default execution is serialized.

## Minimal context to read

- `README.md` (dispatch protocol).
- `../proposal.md` once if the worker has no change context.
- `../specs/skill-merge-publication/spec.md`.
- `../design.md`: D2, D4.
- Contract scope: Read contracts Capture/prepare and fixture harness; require packet 03 APIs.

## Allowed changed files

- `skills/skill-library-maintenance/scripts/skill_repo_workflow.py`
- `skills/skill-library-maintenance/tests/test_skill_repo_workflow.py`
- `skills/skill-library-maintenance/references/shared-repo-sync.md`

No other production/config/profile/vault files. Read predecessor definitions/usages before editing; if required interface changes cross ownership, return that dependency to the parent. Parent alone updates task checkboxes.

## Required behavior and traps

Native index is the complete candidate, not text scratch. Same-line fixture must actually move both sides after fork. Block external drivers/hooks and unsupported binary/link/submodule modes without touching runtime.

## Implementation checkpoints (red → green, then review)

**B4. Prepare creates a real uncommitted merge in isolated candidate dir.** Test:

```python
def test_prepare_materializes_clean_addition(core,lab):
    t=offer(lab)
    c=core.capture(lab["publisher"],lab["store"],lab["source"])
    p=core.prepare(lab["publisher"],lab["store"],c)
    w=Path(p["worktree"])
    assert "A useful generic rule." in (w/"skills/demo/SKILL.md").read_text()
    assert g(w,"rev-parse","HEAD")==lab["base"]
    assert g(w,"rev-parse","MERGE_HEAD")==t
    assert g(lab["producer"],"branch","--show-current")=="machine/testlab"
```

Use native Git algorithm; no `.merged` text scratch applier. Set protected hooks/rerere config **only** on publisher/candidate repository, not producer/global. Avoid setting shared-worktree config in a way that changes runtime clone: publisher is a separate clone. Candidate worktrees share publisher refs; use detached HEAD.

**B5. Exact file-kind regression tests.** Add separate nodes `test_prepare_preserves_deleted_and_empty_files`, `test_prepare_preserves_executable_mode`, `test_prepare_blocks_binary_and_symlink`, `test_prepare_handles_rename`. Fixture: commit `old.md`, `empty.md` and executable text script before fork, branch deletes old, empties another existing file, toggles executable bit, renames a text file; compare index via `git ls-files --stage -z` and `git diff --cached --name-status`. Parameterized unsupported blob fixture must actually add NUL or symlink mode in T, not merely name file `binary`. On blocked unsupported input all runtime/publisher main refs unchanged.

**B6. Real conflict fixture, not a false green merge.** `test_prepare_exposes_conflicts_without_ours_default`: fork transport then commit **different edits to the same original line** in main and T, push both, capture/prepare. Assert conflict_paths contains file and `git ls-files -u` is nonempty; expect status prepared-with-conflicts (store prepared + conflict_paths), not silent exit-0 keep-ours. Other merge errors (bad ref, missing object, unsupported drivers) must block. Precheck `.gitattributes` custom merge drivers: don't execute configured external drivers from the candidate; support builtin text/normal only, otherwise block. Test a configured custom driver that would create a sentinel; sentinel must not be created.

## Verification and handoff

Run each named regression node to prove its intended failure before implementation and pass after. Then run the affected test file and full package suite from the authorized worktree; exact commands are in README.md. Run `git diff --check`. Return changed paths, symbol/API deltas, actual test exit/pass results, source/ref/tree evidence where relevant, blockers and successor context. Do not commit/push, touch live jobs, archive, check global tasks, or claim an unavailable check passed.
