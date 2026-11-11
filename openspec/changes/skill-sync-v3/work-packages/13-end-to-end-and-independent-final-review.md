# Packet 13 — End-to-end and independent final review

**OpenSpec task group:** 13 in `../tasks.md`.
**Prerequisites:** All earlier packets through 12, parent-verified. Default execution is serialized.

## Minimal context to read

- `README.md` (dispatch protocol).
- `../proposal.md` once if the worker has no change context.
- `../specs/skill-source-transport/spec.md`.
- `../specs/skill-merge-publication/spec.md`.
- `../specs/skill-review-reporting/spec.md`.
- `../specs/skill-refactor-integration/spec.md`.
- `../design.md`: Risks / Trade-offs, Migration Plan.
- Contract scope: Read all acceptance scenarios and relevant contracts; require packets 00–12 verified by parent.

## Allowed changed files

- `skills/skill-library-maintenance/tests/test_skill_repo_workflow.py`
- `skills/skill-library-maintenance/tests/test_skill_repo_sync.py`
- `skills/skill-library-maintenance/tests/test_skill_repo_consolidate.py`

No other production/config/profile/vault files. Read predecessor definitions/usages before editing; if required interface changes cross ownership, return that dependency to the parent. Parent alone updates task checkboxes.

## Required behavior and traps

Run the full integration matrix and final suite/validators/audit after the last edit. Return exact branch/base/HEAD, actual command results and local Git SHAs. The stronger reviewing assistant reruns checks and reviews actual code; do not self-certify implementation complete from a worker narrative. Live rollout remains separate.

## 6. End-to-end acceptance (must be executed, not just described)

Add TEST nodes below; run from final implementation worktree with real subprocess Git/local bare remote. No network or live state. Use the CORE API rather than manually simulating a successful publisher and declaring the test passed.

| Node name | Fixture and exact required assertions |
|---|---|
| `test_e2e_two_producers_curated_merge` | Two clones edit disjoint paths and same file separate regions; native candidate merges + actual review metadata/checks/report fixture + actual publish; main contains both, each source tip ancestor main, refs never reset. |
| `test_e2e_same_line_semantic_replacement` | Main and source deliberately edit same original instruction; candidate conflict stages nonempty, agent fixture synthesizes ONE replacement, no markers and no duplicated instruction, report old/new anchors validated. |
| `test_e2e_concurrent_T2_after_capture` | T2 pushed while T review prepared; publish T, source still T2, next candidate contains only new effect, no duplicate T text. |
| `test_e2e_refactor_while_transport_continues` | Real refactor worktree from M, main advances through normal contribution, merge main into refactor, explicit new exact tip submission, reviewed true merge integrates; producer C continues throughout, no sweep stages refactor, no rebase/reset/force push. |
| `test_e2e_report_failure_then_retry` | Missing report blocks before push, unchanged main; fixture report later written, exact verify, same candidate publishes once. |
| `test_e2e_crash_after_publish_then_reconcile` | Actual push P succeeds, injected status write exception, reconcile marks P already published, no duplicate commit; receipt idempotent. |
| `test_e2e_invalid_scope_does_not_leak_report` | Unregistered/mixed-trust source capture blocked before source content rendered; no private vault file, diagnostic only non-sensitive source ID. |
| `test_e2e_optional_feedback_corrects_current_state` | Publish P; later another contribution edits same skill; corrective candidate based on **latest M** reflects user's report-specific feedback without restoring unrelated old bytes; original report immutable. |
| `test_e2e_no_change_monitor_is_quiet` | Same-tree unacknowledged source gets one reported merge; producer FF refresh makes no new commit; monitor then quiet, no endless main/transport back-and-forth. |

Full commands (expected results, not claims already executed):

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider skills/skill-library-maintenance/tests -q
# Expected: all collected tests pass, record actual collected/pass count and revision.
python3 skills/skill-library-maintenance/scripts/audit-skill-library.py skills --json
# Expected summary.errors == 0 for changed artifact; classify pre-existing baseline errors separately.
./skills/skill-builder/scripts/skills-ref.sh validate ./skills/skill-library-maintenance
./skills/skill-builder/scripts/skills-ref.sh validate ./skills/skill-governance
# Expected both valid; if validator cannot run, report blocked, not passed.
git diff --check
git status --short --branch
# Expected no whitespace errors, only intended changes or authorized checkpoint commits.
```

Also parse/import all three entrypoints plus CORE in isolated environment; each --help/--version works without installed live state. Run relevant suite on Linux and macOS before claiming cross-platform deployment. Linux-only execution proves Linux only. Avoid GNU-specific `stat`, `flock` or shell `readlink -f` in portable scripts. Git worktree/common-dir and path-with-spaces fixtures must be covered. Register actual final test count in the handoff, not a number invented here.

## 7. Final stronger-model review gate

After the cheaper implementation model finishes, it must hand back:

1. implementation branch, base and exact HEAD; changed-path list; all authorized commit SHAs;
2. unaltered test outputs (red/green evidence per phase, final full suite), validators/audit results;
3. one real disposable end-to-end transcript with M,T,T2,P/tree/parents/remote values;
4. generated example review/result **from the disposable fixture**, explicitly labeled test data, plus crash/reconcile evidence;
5. list of unimplemented acceptance rows, if any. No “done” when an item is omitted.

The stronger reviewing assistant then independently re-runs final package tests and inspects Git ancestry, input snapshot isolation, index coverage, report gating, post-push recovery, hook preservation, staging concurrency, forbidden-mode retirement, profile scope, refactor exact-tree handling and governance contradictions. Verify final files rather than trusting the cheaper model's narrative. Check cheap-model work against concept **and** this plan. Any defect is returned as a precise correction task; only after independent review passes can rollout be proposed. This gate is a one-time implementation-quality review, not a daily human candidate gate.


## Verification and handoff

Run each named regression node to prove its intended failure before implementation and pass after. Then run the affected test file and full package suite from the authorized worktree; exact commands are in README.md. Run `git diff --check`. Return changed paths, symbol/API deltas, actual test exit/pass results, source/ref/tree evidence where relevant, blockers and successor context. Do not commit/push, touch live jobs, archive, check global tasks, or claim an unavailable check passed.
