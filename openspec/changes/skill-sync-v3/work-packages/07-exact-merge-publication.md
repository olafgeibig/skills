# Packet 07 — Exact merge publication

**OpenSpec task group:** 7 in `../tasks.md`.
**Prerequisites:** All earlier packets through 06, parent-verified. Default execution is serialized.

## Minimal context to read

- `README.md` (dispatch protocol).
- `../proposal.md` once if the worker has no change context.
- `../specs/skill-merge-publication/spec.md`.
- `../design.md`: D1, D5, D6.
- Contract scope: Read contracts Promotion; require prepare/review/report/lock primitives from packets 03–06.

## Allowed changed files

- `skills/skill-library-maintenance/scripts/skill_repo_workflow.py`
- `skills/skill-library-maintenance/tests/test_skill_repo_workflow.py`
- `skills/skill-library-maintenance/references/shared-repo-sync.md`

No other production/config/profile/vault files. Read predecessor definitions/usages before editing; if required interface changes cross ownership, return that dependency to the parent. Parent alone updates task checkboxes.

## Required behavior and traps

Use actual local bare pushes. P parents=[M,T] and tree=reviewed_tree; remote main freshness and normal FF push guard races. T2 untouched. Reject-only and empty-diff acknowledgment retain source history. Persist P before push now; packet 08 adds failure/reconciliation adversarial coverage, not permission to omit intent here.

## Implementation checkpoints (red → green, then review)

**D1. Automatic publication has exact merge parents.** Paste:

```python
def test_publish_preserves_source_ancestry(core,lab):
    t=offer(lab); c=reviewed(core,lab)
    r=core.publish(lab["publisher"],lab["store"],c["id"],lab["vault"])
    p=r["result_sha"]
    assert g(lab["publisher"],"show","-s","--format=%P",p).split()==[lab["base"],t]
    assert g(lab["publisher"],"show","-s","--format=%T",p)==c["reviewed_tree"]
    assert g(lab["producer"],"ls-remote","origin","refs/heads/machine/testlab").split()[0]==t
    assert g(lab["producer"],"ls-remote","origin","refs/heads/main").split()[0]==p
```

Implement promotion algorithm. Expected red missing publish or wrong parents; green real local bare remote P and untouched source. No test may simulate consolidation by `git merge` outside the code under test and claim it verified the publisher.

**D2. Source advances during review.** `test_publish_T_preserves_T2`: offer T and reviewed c, then `offer` again with extra novel text T2; publish c, assert source remote T2 untouched, T ancestor P, T2 not ancestor P, next capture T2 pending. Prepare next candidate and assert T's original rule occurs **once** and extra T2 text present. This is the critical snapshot isolation test; no force-with-lease/reset function may be called.

**D3. Main advances during review.** `test_stale_main_never_pushes`: reviewed c, independently add an unrelated commit on main in a second clone; publish c raises stale error, remote equals independent commit, no source reset, report unchanged. Capture new c with new M, distinct id; revalidate review/report rather than editing old report. Push FF check is the race guard after preliminary refetch.

**D4. Reject-only contribution is consumed transparently.** `test_reject_only_merge_keeps_original_source`: prepare T real text, restore candidate index/worktree to M's text using explicit path checkout, record `decision=reject` with exact source quote/reason; publish. Assert P parents M,T, P tree equals M tree, source ref T untouched, `source_status(P,T)==consumed`, rejection report retains text/reason. Do not invoke `git merge -s ours` as a blanket conflict handler; the explicit decision changes the candidate index after review.

## Verification and handoff

Run each named regression node to prove its intended failure before implementation and pass after. Then run the affected test file and full package suite from the authorized worktree; exact commands are in README.md. Run `git diff --check`. Return changed paths, symbol/API deltas, actual test exit/pass results, source/ref/tree evidence where relevant, blockers and successor context. Do not commit/push, touch live jobs, archive, check global tasks, or claim an unavailable check passed.
