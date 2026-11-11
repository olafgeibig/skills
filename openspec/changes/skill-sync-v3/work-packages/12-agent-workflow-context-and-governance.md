# Packet 12 — Agent workflow, context and governance

**OpenSpec task group:** 12 in `../tasks.md`.
**Prerequisites:** All earlier packets through 11, parent-verified. Default execution is serialized.

## Minimal context to read

- `README.md` (dispatch protocol).
- `../proposal.md` once if the worker has no change context.
- `../specs/skill-review-reporting/spec.md`.
- `../specs/skill-source-transport/spec.md`.
- `../specs/skill-refactor-integration/spec.md`.
- `../design.md`: D7, D8, Migration Plan.
- Contract scope: Use all already-tested CLI names; this packet owns orchestration/templates and narrow governance reconciliation, not live job edits.

## Allowed changed files

- `skills/skill-library-maintenance/scripts/skill_repo_workflow.py`
- `skills/skill-library-maintenance/tests/test_skill_repo_workflow.py`
- `skills/skill-library-maintenance/references/shared-repo-sync.md`
- `skills/skill-library-maintenance/references/install-and-update.md`
- `skills/skill-library-maintenance/references/repository-sync-safety.md`
- `skills/skill-library-maintenance/SKILL.md`
- `skills/skill-library-maintenance/assets/consolidator-cron-prompt.md.example`
- `skills/skill-library-maintenance/assets/pre-consolidation-cron-prompt.md.example`
- `skills/skill-library-maintenance/assets/consolidate-monitor-script.sh.example`
- `skills/skill-library-maintenance/assets/stage-sweep-script.sh.example`
- `skills/skill-library-maintenance/assets/soul-instance-block.md.example`
- `skills/skill-library-maintenance/assets/skill-review-cron-prompt.md.example`
- `skills/skill-library-maintenance/assets/skill-sync-report.md.example`
- `skills/skill-governance/SKILL.md`

No other production/config/profile/vault files. Read predecessor definitions/usages before editing; if required interface changes cross ownership, return that dependency to the parent. Parent alone updates task checkboxes.

## Required behavior and traps

Add bounded packet generation that includes deletions, conflict/section context and targeted expansion; do not repeatedly load full versions. Add usage fields: measured/estimated/unavailable, no claim a 35-turn limit is a token cap. User chose a small pilot, not a new provider SDK or mandatory hard-budget implementation. Run semantic fixture cases, periodic cursor test and report feedback procedure tests. Preserve foreign dirty lessons in shared skills.

## Implementation checkpoints (red → green, then review)

**G1. Replace consolidator prompt with exact workflow, not promises.** Modify existing consolidator template and RUNBOOK. Prompt sequence: health check → capture one pending cid → prepare → read full change manifest/conflict packets and focused file context → classify/add/correct/replace/reject → resolve/stage candidate → record review & real checks → render report → TurboVault write `expected_hash=absent` or idempotent verified-existing report → exact read-back → verify-report → publish → reconcile if ambiguous → render/write/read/verify-result. Never self-invent Git merge/push/reset shell steps. Normal conflict resolution is autonomous, not escalated to daily human approval. If context budget insufficient mark technical/incomplete-review failure with report; don't claim semantic coverage from a truncated diff. Hard limit 35 turns for normal candidates; refactors use separately scheduled stronger final review, not blind same-size budget.

**G2. Source pre-consolidation prompt and shims.** Modify existing pre-consolidation template/monitor shim and INSTALL_DOC. Source refresh uses merges (normal phase E), no “always push current branch HEAD” after later changes. Push exact reviewed T; unsupported attribution/mixed trust blocks source publication without sending work context to private vault. Monitor shim takes approved publisher --repo and --store; stage shim uses runtime wrapper only. Remove old reset, replay, implicit resume catch-up and human-gate language. These are rendered templates; no live job edit in this phase.

**G3. Report folder and chat feedback procedure.** REPORT_TEMPLATE/RUNBOOK/INSTALL_DOC: `reports/+reports.md` created via TurboVault with first report, linked once from project MoC; per-candidate review/result notes contain hybrid topics/footer and project tag, short description, current timestamps from actual clock. Source input and tree immutable; outcome goes result note, not edited review. Manual feedback names report; agent reads report/current skill, asks only if ambiguous, records feedback interpretation in a **new feedback note or result-linked correction report**, and creates normal corrective candidate. Never blind `git revert` older merge under later work. No approve CLI, no human backlog requirement, no invented current result.

**G4. Periodic whole-skill review.** New AUDIT_PROMPT plus RUNBOOK procedure; schedule proposed weekly (configurable deployment value, not a claimed live job). Cycle owned skills deterministically, one skill per run so coverage is bounded; examine existing instructions, support references, duplication, contradictions and previously accepted errors. Findings create a report even if no automatic fix. Small justified correction enters normal source workflow; architectural rewrite uses explicit refactor branch, not a giant automatic main rewrite. Store progress cursor in local publisher state, not memory/skill content. Test `test_periodic_review_cursor_visits_each_skill_once`: sorted list, last cursor resumes and wraps; missing/deleted skill handled, no repeated first skill. Need only a small pure `next_skill(skills,last)->str|None` helper in CORE; no new scheduler implementation. Existing cron supports prompt jobs.

**G5. Governance and specification cleanup.** MAIN_SKILL, RUNBOOK, INSTALL_DOC, SAFETY plus `skills/skill-governance/SKILL.md`: narrowly amend canonical-write gate to acknowledge the explicitly configured autonomous merge workflow and reports, without granting arbitrary foreground agents general permission. Distinguish addition/correction/replacement; reject profile/instance instructions but allow generic examples. Remove contradictions: “clean main normal no-op”, force reset, old helper version parity, human approval mandatory, auto-merged files ignored, ledger proves hunk ownership. Preserve pre-existing dirty lessons by coordinating/merging rather than rewriting from HEAD. Proposed version: engine/helper/installer all 3.0.0; skill-library-maintenance 0.23.0 (or next actual unclaimed minor), governance next actual minor. Repository code and templates have no hardcoded actual installation paths/names beyond existing personal source facts; report config holds deployment paths. Do not remove valid portable commands merely because scan sees a path/date.

Phase G checkpoint commits list only actually changed explicit template/reference/core/test/skill paths; use descriptive `docs(sync): ...`/`feat(sync): ...` messages. No runtime cron or vault report writes in this phase.

## Verification and handoff

Run each named regression node to prove its intended failure before implementation and pass after. Then run the affected test file and full package suite from the authorized worktree; exact commands are in README.md. Run `git diff --check`. Return changed paths, symbol/API deltas, actual test exit/pass results, source/ref/tree evidence where relevant, blockers and successor context. Do not commit/push, touch live jobs, archive, check global tasks, or claim an unavailable check passed.
