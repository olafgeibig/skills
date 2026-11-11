# Packet 03 — Core state and source capture

**OpenSpec task group:** 3 in `../tasks.md`.
**Prerequisites:** All earlier packets through 02, parent-verified. Default execution is serialized.

## Minimal context to read

- `README.md` (dispatch protocol).
- `../proposal.md` once if the worker has no change context.
- `../specs/skill-merge-publication/spec.md`.
- `../specs/skill-refactor-integration/spec.md`.
- `../design.md`: D1, D3, D6.
- Contract scope: Read contracts sections 2.1–2.3 and Capture/prepare; paste harness from section 4. These are new APIs.

## Allowed changed files

- `skills/skill-library-maintenance/scripts/skill_repo_workflow.py`
- `skills/skill-library-maintenance/tests/test_skill_repo_workflow.py`
- `skills/skill-library-maintenance/references/shared-repo-sync.md`

No other production/config/profile/vault files. Read predecessor definitions/usages before editing; if required interface changes cross ownership, return that dependency to the parent. Parent alone updates task checkboxes.

## Required behavior and traps

Do not implement publication just to make classification pass. Empty-diff tips remain pending until ancestry acknowledges them. Source-history guards apply to transport only; explicit refactor submissions have separate rules.

## Implementation checkpoints (red → green, then review)

**B1. Create CORE with pure helpers and data validation.** Test `test_candidate_identity_and_path_safety`. Paste:

```python
def test_candidate_identity_and_path_safety(core, tmp_path):
    x = core.candidate_id("owned-skills","refs/heads/machine/testlab","a"*40,"b"*40,"p","transport")
    assert x == core.candidate_id("owned-skills","refs/heads/machine/testlab","a"*40,"b"*40,"p","transport")
    assert len(x) == 64
    assert x != core.candidate_id("owned-skills","refs/heads/machine/testlab","c"*40,"b"*40,"p","transport")
    for p in ("../escape", "/absolute"):
        with pytest.raises(core.WorkflowError): core.safe_relative(tmp_path,p)
```

Implement canonical JSON hashing, atomic unique-temp-file+`os.replace` (not shared `.tmp` races), safe paths with resolved-parent containment and symlink escape rejection. SHA identity includes kind and workflow schema. Atomic write cannot create missing parents outside store. Parse/validate registry before trusting candidate files.

**B2. Capture immutable M,T.** Test `test_capture_is_idempotent_and_pins_inputs`:

```python
def test_capture_is_idempotent_and_pins_inputs(core, lab):
    t=offer(lab)
    a=core.capture(lab["publisher"],lab["store"],lab["source"])
    b=core.capture(lab["publisher"],lab["store"],lab["source"])
    assert a["id"]==b["id"] and a["source_sha"]==t
    assert a["main_sha"]==lab["base"]
    assert g(lab["publisher"],"rev-parse",f'refs/hermes-sync/candidates/{a["id"]}/source')==t
```

Implement Section 3 capture; unknown/disabled source rejects; refactor ref cannot be passed as transport kind. Use publisher config `repo_id`, paths verified against actual checkout. No index/HEAD changes in publisher during capture.

**B2a. Reject indirect branch submission.** Add CORE `validate_source_history(repo, main, tip, known_refactors) -> None` and call it for **transport-kind candidates only** in capture and before promotion; explicit refactor submissions use Phase F's own ancestry/tree rules. Fetch known refactor refs for this diagnostic check without treating them as automatic candidates. Compute unpublished source commits with `git rev-list T ^M`. For every merge in that set (`git rev-list --parents T ^M`), require each non-first parent to be an ancestor of captured M; a producer may import published main only. Also intersect the unpublished set with `git rev-list <known refactor tip> ^M` for every known remote refactor branch: nonempty intersection blocks transport submission, including a direct fast-forward to an unsubmitted refactor tip. Add nodes `test_transport_rejects_unpublished_side_parent`, `test_transport_rejects_known_refactor_fast_forward`, and `test_transport_accepts_published_main_merge`. Fixture must create actual main-side and refactor/source-side commits, not only branch names. Diagnostic names refs/SHAs only, not prohibited content. This is an enforceable cooperative DAG rule, **not a hard security boundary** against cherry-picks, deleted refs or a malicious writer; document that limit rather than claiming perfect intent detection. Check changes added by later T2 separately when captured; publishing earlier T never implicitly approves T2. Commit CORE + TEST as `fix(sync): prevent indirect refactor submission`.

**B3. Pending classification uses ancestry, including empty diffs.** Test `test_source_status_acknowledges_empty_diff`: (a) T==M is consumed; (b) create a same-tree new commit on transport (`git commit --allow-empty`), fetch; status pending, not consumed. This test uses only source_status/capture and can go green **before** publication exists. Full empty-diff publication/acknowledgment is tested later in D4 and the end-to-end matrix. Add `test_refresh_noop_does_not_create_echo_commit` in Phase E after refresh exists: producer FFs to published main and a repeat refresh leaves HEAD unchanged. Do not reintroduce an empty-diff skip to suppress the monitor; fix producer FF behavior instead.

## Verification and handoff

Run each named regression node to prove its intended failure before implementation and pass after. Then run the affected test file and full package suite from the authorized worktree; exact commands are in README.md. Run `git diff --check`. Return changed paths, symbol/API deltas, actual test exit/pass results, source/ref/tree evidence where relevant, blockers and successor context. Do not commit/push, touch live jobs, archive, check global tasks, or claim an unavailable check passed.
