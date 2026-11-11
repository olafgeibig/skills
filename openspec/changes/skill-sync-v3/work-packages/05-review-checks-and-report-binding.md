# Packet 05 — Review, checks and report binding

**OpenSpec task group:** 5 in `../tasks.md`.
**Prerequisites:** All earlier packets through 04, parent-verified. Default execution is serialized.

## Minimal context to read

- `README.md` (dispatch protocol).
- `../proposal.md` once if the worker has no change context.
- `../specs/skill-review-reporting/spec.md`.
- `../specs/skill-merge-publication/spec.md`.
- `../design.md`: D4, D5, D7.
- Contract scope: Read contracts review schema, Final gate, API return/persistence rules and Reviewed candidate fixture.

## Allowed changed files

- `skills/skill-library-maintenance/scripts/skill_repo_workflow.py`
- `skills/skill-library-maintenance/tests/test_skill_repo_workflow.py`
- `skills/skill-library-maintenance/assets/skill-sync-report.md.example`
- `skills/skill-library-maintenance/references/shared-repo-sync.md`

No other production/config/profile/vault files. Read predecessor definitions/usages before editing; if required interface changes cross ownership, return that dependency to the parent. Parent alone updates task checkboxes.

## Required behavior and traps

Copy the shared reviewed fixture from contracts, not guessed helper APIs. Provide real check evidence; demo fixtures have no maintenance-package runner and may mark absent optional checks not-applicable. Live report writes stay in TurboVault; tests use temporary fixture files.

## Implementation checkpoints (red → green, then review)

**C1. Review coverage and source quotes.** Test `test_review_rejects_missing_paths_or_invented_quotes`: prepare real offer; provide empty files array then fabricated quote; both raise WorkflowError, complete accurate record passes. Test `test_review_replacement_requires_old_and_new_anchors`: final candidate replaces “Base instruction.” with portable new instruction, record old quote at M/new quote in index; missing old/new/reason fails. `validate_review` has no execution fields. Warn on a date/path but permit a **labeled example**; a live profile instruction must be generalized/rejected by agent, not accepted merely by adding an example flag. The semantic part is evaluated in final review fixtures, not a regex truth claim.

**C2. Final gate checks the actual staged tree.** `test_final_gate_ignores_fixed_incoming_pointer`: incoming T contains a real instance instruction, candidate replaces it with generic text, review explains correction; validate succeeds. Leave it unchanged with no justification -> review failure, but scanner alone is advisory. Separate `test_final_gate_blocks_unmerged_and_unstaged`: merge conflicts or extra dirty edit fails. `test_final_gate_preserves_all_manifest_paths` verifies new, deleted and deliberately rejected paths have coverage. Compute tree from index; preserve full source paths and staged code syntax checks. No `preflight` scan of other pending branches in final gate.

**C3. Validation command results are actual evidence.** `test_failed_check_blocks_publication` uses a fixture repo with an allowlisted package test deliberately failing; store code/stdout/stderr, no green flag. Implement `run_checks` using fixed adapters based on changed packages, `PYTHONDONTWRITEBYTECODE=1`, no cacheprovider; require no unexpected files changed by checks (even code-generated files). Tests must mock the *process runner only* to test dispatch, plus one real failing subprocess fixture to prove failure propagation. Never run local fixture's CLI against real HERMES_HOME.

**C4. Deterministic report rendering and file read-back.** `test_report_binds_inputs_review_and_tree`: renderer includes M,T,tree,cid, review reasons, pass/fail/not-run and no approval demand. Repeated rendering of same inputs yields same bytes; generated time is from captured candidate (not current clock). Save payload to candidate store only. `verify_report` checks exact content of `<report_root>/<configured directory>/skill-sync-<cid>-review.md`, compares SHA-256 against rendered payload and refuses missing, changed or path-escape file. In live run agent writes via TurboVault then calls verification. Tests explicitly place rendered payload in **lab["vault"]**, never a real vault, and assert tampering blocks.

**C5. Shared helper for later tests** (complete test helper to add after C4, not a bypass in production):

```python
def reviewed(core, lab):
    c=core.capture(lab["publisher"],lab["store"],lab["source"])
    c=core.prepare(lab["publisher"],lab["store"],c)
    w=Path(c["worktree"])
    r={"schema":1,"candidate_id":c["id"],"main_sha":c["main_sha"],"source_sha":c["source_sha"],
       "summary":"Accept a useful generic addition",
       "files":[{"path":"skills/demo/SKILL.md","change_type":"addition","decision":"accept",
                 "source_anchors":[{"ref":c["source_sha"],"path":"skills/demo/SKILL.md","quote":"A useful generic rule."}],
                 "reason":"Useful generic addition","replacements":[]}]}
    core.validate_review(c,r,lab["publisher"],w)
    checks=core.run_checks(c,w)
    v=core.validate_tree(c,w,r)
    # Implementation must persist normalized review/checks/tree in this API call:
    core.record_review(lab["store"],c["id"],r,checks,v)
    c=core.load_candidate(lab["store"],c["id"])
    text=core.render_review(c,r,checks,v["tree"])
    # TEST ADAPTER ONLY; live run writes these bytes with TurboVault.
    target=lab["vault"] / c["report_relative_path"]
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(text,encoding="utf-8")
    core.verify_report(c,text,lab["vault"])
    return core.load_candidate(lab["store"],c["id"])
```

Add the required `record_review(store,cid,review,checks,validation) -> dict` API to CORE: validate cid/refs, full path coverage, checks green and tree; persist review/checks, exact review hash and reviewed_tree atomically, status reviewed. `verify_report` transitions to report-verified via store location carried by validated candidate. Don't trust caller's arbitrary paths or status booleans; load authoritative candidate/config again.

## Verification and handoff

Run each named regression node to prove its intended failure before implementation and pass after. Then run the affected test file and full package suite from the authorized worktree; exact commands are in README.md. Run `git diff --check`. Return changed paths, symbol/API deltas, actual test exit/pass results, source/ref/tree evidence where relevant, blockers and successor context. Do not commit/push, touch live jobs, archive, check global tasks, or claim an unavailable check passed.
