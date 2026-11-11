# Tasks

Preparation is complete only when OpenSpec validates; **none of the implementation boxes below is complete yet**. Dispatch protocol and minimal shared context: `work-packages/README.md`. Each group has a matching numbered worker brief; the brief is part of the task, not optional background. Execute small red→green checkpoints and update this checklist only after parent verification. No code apply, worktree creation, commits, pushes or deployment was authorized by preparing this change.

## 0. Establish safe implementation context — packet 00

- [x] 0.1 Recheck HEAD, branch, dirty files and worktrees; deliver a baseline handoff preserving every foreign change, verified by `git status --short --branch` and explicit diff inventory.
- [x] 0.2 Obtain implementation/worktree authorization, establish the isolated refactor workspace and bring this OpenSpec change into it without auto-staging runtime WIP; verify runtime branch/files unchanged and implementation path is outside discovery roots.
- [x] 0.3 Run and save the real baseline package tests in the implementation workspace; record actual pass/fail count and revision, not the historical 35-test claim.

## 1. Prevent destructive legacy and staging behavior — packet 01

- [x] 1.1 Retire reset/rebase publication modes with explicit errors; verify remote refs unchanged by `test_retired_reset_never_writes_remote` and a test proving no rebase invocation.
- [x] 1.2 Exclude refactor branches and refuse unexpected main staging; verify dirty bytes, index, HEAD and cursor stay unchanged in branch-policy tests.
- [x] 1.3 Filter missing never-tracked ledger paths while preserving tracked deletions and recording skips; verify `test_stage_skips_missing_untracked_ledger_path`.
- [x] 1.4 Roll back only this attempt's staged paths on whitespace/commit failure and use the original ledger snapshot cursor; verify correction/retry and concurrent-append regressions.
- [x] 1.5 Update only the affected staging/retired-mode runbook instructions; verify documented refusal and retry semantics match the tested CLI.

## 2. Preserve installer intent and hooks — packet 02

- [x] 2.1 Require explicit fresh bootstrap before any writes and reject bootstrap on existing state; verify state/wrapper/config/file-mode snapshots in installer tests.
- [x] 2.2 Read hook lists as JSON and append the exact session hook without replacing unrelated entries or clearing lifecycle hooks; verify exact fake-CLI calls and fail-closed parse behavior.
- [x] 2.3 Update installation guidance and version policy for this behavior; verify examples parse and package installer regressions pass without real Hermes config mutation.

## 3. Define core state, source capture and provenance — packet 03

- [x] 3.1 Add shared core helpers, strict state validation, canonical identity, safe paths and atomic writes; verify `test_candidate_identity_and_path_safety`.
- [x] 3.2 Implement fetched immutable input capture, local pins and idempotent candidates; verify `test_capture_is_idempotent_and_pins_inputs` and unknown/disabled source refusal.
- [x] 3.3 Refuse unpublished side-parent imports and known unfinished refactor ancestry in transport-kind candidates; verify both indirect-import tests and the allowed-main-merge case.
- [x] 3.4 Define consumed versus pending solely by ancestry, including empty-diff tips; verify classification tests without depending on publication code not yet implemented.
- [x] 3.5 Document the implemented state/capture contract and cooperative-security limits; verify full SHAs, registry checks and no publisher/runtime HEAD mutation.

## 4. Prepare complete native merge candidates — packet 04

- [x] 4.1 Create detached candidate worktrees outside runtime/report roots and prepare exact M,T native merges with hooks/unsafe drivers disabled; verify `test_prepare_materializes_clean_addition`.
- [x] 4.2 Preserve clean additions, deletions, empty files, renames and executable text modes; verify exact staged contents and mode tests, not scratch-only artifacts.
- [x] 4.3 Block binary, symlink and submodule changes before unsafe materialization; verify unsupported fixtures actually contain the unsupported Git object modes/bytes.
- [x] 4.4 Expose real same-line conflicts without blanket keep-ours and distinguish merge errors; verify conflict index stages and custom-driver sentinel tests.
- [x] 4.5 Update merge-preparation guidance with exact candidate-edit scope; verify no active skill-tool resolution points to the runtime checkout.

## 5. Validate decisions, final tree and reports — packet 05

- [x] 5.1 Validate complete path coverage, source quotes and addition/correction/replacement decisions; verify missing/invented evidence and old→new replacement tests.
- [x] 5.2 Gate the actual staged tree, conflict completeness and dirty content; verify corrected incoming findings can pass while unresolved/unstaged states cannot.
- [x] 5.3 Run fixed required validation commands and capture real results; verify actual subprocess failure blocks and absent demo-only package runners are honestly not-applicable.
- [x] 5.4 Render deterministic review payloads and verify exact configured vault bytes without Python writing live notes; verify missing/tampered reports block.
- [x] 5.5 Add the reviewed-candidate fixture and report template; verify fixture setup records real checks/tree and uses only temporary fixture report directories.

## 6. Own the publisher lock — packet 06

- [x] 6.1 Implement token-owned locking at the publisher Git common directory; verify wrong-owner release, simultaneous acquisition and age-only-break refusal.
- [x] 6.2 Prove linked worktrees and alternate state stores share that lock while separate producer clones remain writable; verify `test_linked_worktrees_and_alternate_stores_share_publisher_lock`.
- [x] 6.3 Remove broad cron-claim heuristics and document explicit recovery; verify no nested lock acquisition or helper-PID death assumption is used.

## 7. Publish exact reviewed merge snapshots — packet 07

- [x] 7.1 Create P with ordered parents M,T and exact reviewed tree, persist intent before non-force push and verify remote; verify `test_publish_preserves_source_ancestry`.
- [x] 7.2 Preserve a source T2 arriving after T capture; verify source refs unchanged and later candidate does not duplicate accepted T text.
- [x] 7.3 Refuse stale main before push and respect FF rejection races; verify remote independent commit survives and new M produces a new candidate/report.
- [x] 7.4 Publish documented reject-only and empty-diff acknowledgments without deleting history; verify exact tree/parents, source retention and consumed ancestry.
- [x] 7.5 Update publication guidance and prove repeated published-candidate calls cannot create fresh integration commits.

## 8. Recover publication and receipt failures — packet 08

- [x] 8.1 Preserve exact P after a failed/uncertain push and retry that same result only when safe; verify real commit intent plus injected push failure.
- [x] 8.2 Reconcile a crash after actual remote publication without duplicate commit/push; verify actual remote ancestry and candidate trailers on process restart.
- [x] 8.3 Render and verify separate idempotent receipts, retaining immutable review; verify delivery failure/recovery and post-push report tampering incidents.
- [x] 8.4 Document stale, unavailable, already-published and incident outcomes; verify each state has an observable non-fabricated diagnostic.

## 9. Refresh and publish producer snapshots — packet 09

- [x] 9.1 Implement conservative session refresh by FF/no-op/deferral, never reset/rebase; verify real v3 integration refresh and divergent unpublished-work preservation.
- [x] 9.2 Serialize short producer index/publication operations using a common-repo lock; verify stage/pre-consolidation contention leaves files/index unchanged.
- [x] 9.3 Push exact reviewed T even if local branch advances to T2 and verify the remote tip; verify T2 stays local/unreviewed.
- [x] 9.4 Replace old reset/replay tests and pre-consolidation instructions with merge ancestry and FF-first tests; verify no refresh echo commit and no false resume-trigger claim.
- [x] 9.5 Review the entire unpublished source history before sharing, not only the latest tree, and block prohibited-profile or suspected credential content without echoing values; verify `test_source_history_removed_exposure_still_blocks_push` using synthetic fixture history and unchanged bare-remote refs.

## 10. Adapt CLI, monitor and dry runs — packet 10

- [x] 10.1 Route new candidate/review/report/publish/reconcile CLI modes through the shared core and enforce explicit repo/store agreement; verify real isolated CLI round-trip and help/version/errors.
- [x] 10.2 Emit stable pending, blocked and unhealthy signals; verify unsubmitted refactors excluded, empty-diff pending included, recovery changes health signal, and explicit retry changes its generation once.
- [x] 10.3 Make every dry-run leave all state, refs including fetch state, index, files and remote refs unchanged; verify parameterized before/after snapshots for each mutating CLI mode.
- [x] 10.4 Make selfcheck report only observed state/version/policy and retire all legacy publication bypasses; verify missing installation exit 13 and no fabricated hook-health assertions.
- [x] 10.5 Update CLI/monitor documentation and rendered shim inputs; verify examples target the publisher and runtime roles correctly without editing live jobs.

## 11. Submit and integrate deliberate refactoring — packet 11

- [x] 11.1 Register explicit exact remote refactor tip plus brief from configured publisher identity; verify backup branches remain undiscovered and stale/unsubmitted tips refuse.
- [x] 11.2 Require current main ancestry and exact submitted tree during refactor publication; verify real merge-main development, ordered parents and tree equality.
- [x] 11.3 Prove the narrow integration freeze blocks other publishers but not producer commits/pushes; verify new transport work remains pending afterward.
- [x] 11.4 Document separate worktree development, no rebase, renewed tip submission after final edits and trusted tool-code baseline; verify sweep exclusions and no implicit branch cleanup.

## 12. Finish agent workflow, feedback and bounded reviews — packet 12

- [x] 12.1 Update consolidator/pre-consolidation prompts for exact CLI sequencing, autonomous semantics and TurboVault report/read-back; verify no mandatory approval queue or old reset/replay path remains.
- [x] 12.2 Specify and test bounded change packets with additions and deletions, conflict/section context and targeted expansion; verify small fixtures never default to full three-version reads or whole-plan loading.
- [x] 12.3 Add measured/estimated/unavailable usage fields and incomplete-budget reporting; verify no numeric hard-cap guarantee is claimed before a measured pilot or unsupported provider counters are invented.
- [x] 12.4 Document report-specific chat feedback against current skill state and add periodic whole-skill review prompt/cursor; verify cursor visits all skills and older-report correction preserves later unrelated edits.
- [x] 12.5 Reconcile canonical-write governance narrowly for this configured autonomous workflow, retain foreground approval rules and bump actual package versions; verify affected package validators, audit and no contradictory rules.
- [x] 12.6 Update source/history exposure guidance and deployment-separated instructions; verify existing dirty lessons are preserved and no live vault/config/cron writes were performed by code tasks.

## 13. Execute integration and stronger-reviewer acceptance — packet 13

- [x] 13.1 Run real disposable e2e two-producer, semantic replacement, T2, refactor-in-parallel, empty-diff/FF and prohibited-scope cases; record exact SHAs/parents/trees and file outcomes.
- [x] 13.2 Run missing-report retry, crash-after-push reconciliation, receipt retry and optional-feedback cases; prove idempotency using real local bare remotes rather than fabricated successful process output.
- [x] 13.3 Rerun the complete final package suite, affected validators, library audit, syntax/import checks and diff checks; record actual revision and collected/pass counts plus any baseline failures separately.
- [x] 13.4 Have the stronger reviewing assistant independently inspect concept/spec compliance and actual final code, rerun acceptance checks, and resolve findings before declaring implementation complete.
- [x] 13.5 Deliver implementation branch/base/HEAD, explicit changed files, authorized commit handles, test outputs, fixture report examples labeled test data, and unresolved limitations; verify no missing task is hidden behind an aggregate success claim.

## Workflow follow-up

- Only after explicit rollout approval, perform the deployment/migration gate in `design.md` and the engineering plan: preserve dirty state/legacy history, resolve real ownership, stop old publisher, configure v3, verify exact hooks/jobs/vault paths and supervised pilot.
- Measure pilot token usage before deciding whether additional hard budgeting/instrumentation is necessary; do not substitute a 35-turn target for a token ceiling.
- Archive this OpenSpec change only after implementation and independent acceptance, using the OpenSpec archive flow; do not mark deployment completed merely because planning is apply-ready.
