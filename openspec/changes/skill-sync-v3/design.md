# Design

## Context

See `proposal.md` for motivation and the four capability specs for observable requirements. The engineering discussion is in the `hermes-agent` vault project: `drafts/draft-skill-sync-update.md` and `.hermes/plans/2026-11-10_101814-skill-repo-sync-hardening.md`. Those are background, not default context for every worker. This change's specs, decisions below and `contracts.md` form the implementation handoff.

Observed source baseline on durin at change creation: HEAD `5005b54c6f75f6fb915104c67a3370380fa16c59`, runtime checkout on `main`, pre-existing dirty `skills/skill-library-maintenance/SKILL.md`, `references/repository-sync-safety.md`, and `skills/turbovault-use/SKILL.md`. `openspec/` was already initialized but untracked; no existing changes or capability specs. Recheck before implementation; these are observations, not safe-state assertions.

## Goals / Non-Goals

**Goals:** give cheaper implementation subagents small ownership-scoped work packets, preserve exact Git ancestry/tree and concurrent work, require real end-to-end tests, and make autonomous semantic review observable and bounded.

**Non-Goals:** implementation in this planning run; commits/pushes; changing live cron/config/consent; compulsory daily human reviews; reset/rebase queues; new services or model-provider SDKs; automatic migration of dirty or mixed-trust checkouts.

## Decisions

### D1. Native merges, no rewritten-history consumption heuristics

Normal integration P has ordered parents M,T; its tree is exactly reviewed. Source refs never reset. Consumption is `T ancestor main`, including rejected/empty-diff contributions. Contributor refresh fast-forwards when possible, creates merges only for genuine divergence. This removes central consumed watermarks and replay rebases; a newer T2 stays pending naturally. An empty diff is not a shortcut to consumption.

Alternative rejected: patching text reconstruction plus force-with-lease resets. It retains fragile file-kind handling and requires extra state to recover history that true merges preserve.

### D2. Three checkouts have different roles

Runtime transport checkout is the loader/sweep target. A separate publisher **clone** owns central config and avoids shared Git config with runtime. Candidate worktrees are detached review artifacts under durable local store, outside discovery/report roots. A deliberate development refactor worktree is yet another explicit branch; it is neither a transport nor automatically ready. Tool code for a candidate runs from trusted publisher baseline, not the candidate's unreviewed replacement scripts.

No worktree/branch creation is authorized by generating these artifacts. Work package 00 resolves that before apply. Planning artifacts currently reside in the initialized runtime repository; a later implementation must bring them into its authorized refactor worktree without moving or sweeping unrelated changes.

### D3. Shared core and stable CLI adapters

Existing entries:
- `skills/skill-library-maintenance/scripts/skill-repo-sync.py`: producer staging/refresh/selfcheck.
- `skills/skill-library-maintenance/scripts/skill-repo-consolidate.py`: publisher and pending CLI.
- `skills/skill-library-maintenance/scripts/install-skill-repo-sync.py`: installation/hook preservation.

New proposed entries:
- `skills/skill-library-maintenance/scripts/skill_repo_workflow.py`: Git/state/candidate/review/report/publication primitives.
- `skills/skill-library-maintenance/tests/test_skill_repo_workflow.py`: disposable-repo contract/e2e suite.

`contracts.md` specifies proposed interfaces, JSON state/review formats, algorithms and fixture code. New definitions there are design targets, not currently existing symbols. Keep policy in one core implementation. Retire old reset/rebase/publication bypass CLI modes rather than operating v2 and v3 simultaneously.

### D4. Final index tree and review evidence are independent checks

Use native merge index; review covers clean changes, deleted paths and conflicts. Each decision names exact source anchors and its reason, with explicit old→new replacements when rules intentionally change. Scope regex hits are advisory, not a path/date veto. Validate index coverage, modes, conflict completeness, syntax, required tests and the exact reviewed tree. Unsupported binary/symlink/submodule content blocks the first release. Changed or untracked candidate content after checks invalidates them.

Alternative rejected: final gate that rescans original incoming diff forever, or “clean Git merge” as semantic proof.

### D5. Report before push, receipt after push, durable intent between them

Python renders payloads only to candidate state storage. Live agent writes notes using TurboVault and reads them back; core verifies exact configured report bytes. Before pushing, persist result P and intended parents/tree, pin P, then non-force push. Remote read-back confirms publication; reconcile uses exact saved P after uncertainty, never creates a duplicate integration merge. Receipt failure after P is delivery work, not rollback or republish. Git and vault do not share a transaction.

Agreed deployment destination is vault `akademeia`, `projects/hermes-agent/reports/`, held in **local** publisher config. Runtime reviewer receives only permitted shared-generic content; rejected forbidden history cannot be erased by removing its final-tree text. Source-side controls must operate before push; existing exposure is an incident.

### D6. Lock and refactoring readiness

Publisher lock is derived from Git **common directory**, not a worktree gitdir or state-store location; owner token checked on release, no TTL-only breaking or broad cron PID heuristic. Main freshness and non-force push remain final race guards. Normal transport capture checks unpublished side-parent imports and overlap with known unfinished refactor history; this is cooperative provenance, not an adversarial access boundary.

Refactor submission names exact ref, T, identity and intended replacements. Require M ancestor T, then P parents M,T and tree(P)==tree(T). Final content changes require a new submitted tip. Only the final publisher promotion interval freezes; producers continue. Preparation and long review release the lock and revalidate freshness later.

### D7. Token-cost guardrails begin with bounded evidence and measurement

Do not feed the entire plan, three full file versions or repeated full reports to runtime review. Prepare complete added **and removed** hunks, conflict packets, headings and bounded context windows; targeted retrieval supplies additional context. Keep mechanical checks/report rendering out of LLM loops. Normal candidate turn target remains at most 35 but is **not** a token cap. Pilot usage captures actual provider counters when exposed; absent counters are `unavailable`, estimates explicitly labeled. Do not silently expand scope to provider instrumentation or promise the previously suggested numeric budgets are enforced. Budget exhaustion preserves candidate/decisions as incomplete, never auto-publishes or endlessly restarts.

### D8. Subagent context and write ownership

`tasks.md` is the authoritative progress checklist. `work-packages/README.md` is the dispatch protocol; each numbered brief specifies prerequisite package IDs, exact files, targeted spec/design/contract sections, tests, red→green evidence and completion handoff. A worker reads only its packet plus cited dependencies, not every work packet or the whole engineering plan. Since most code units touch CORE and TEST, they are **serialized**. Installer work can run independently only in isolated worktrees with parent-controlled integration. Workers never mark global tasks complete, commit/push, deploy or edit another unit's files by implication.

## Risks / Trade-offs

- Agent judgments can be wrong → retain exact source and decisions, optional chat feedback and periodic bounded whole-skill review; no guaranteed eventual correction claim.
- True merges preserve rejected history → prohibited/secret content must be screened before shared push; tree redaction is not history remediation.
- Refactor import checks cannot identify every cherry-pick → scope/provenance/semantic review still required; do not claim hard isolation from a branch name.
- Native merging may invoke external drivers/hooks → disable hooks in publisher, reject custom external merge drivers and unsupported file kinds before preparation.
- Cheaper workers may weaken tests to pass → explicit adversarial fixtures, parent-owned completion, independent stronger-model final review.
- Runtime staging could sweep planning/WIP files → don't run stage during preparation; establish authorized isolated worktree before implementation and preserve runtime dirty work.

## Migration Plan

1. Preparation only: proposal, specs, design, contracts, task list and worker briefs; validate OpenSpec strict mode and apply instructions. No code task checked complete.
2. After explicit implementation/worktree authorization, capture actual dirty baseline and establish isolated `refactor/skill-sync` worktree. Do not checkout/reset runtime main or auto-commit planning artifacts.
3. Execute task dependency order with disposable local Git remotes and isolated HERMES_HOME. Integrate worker results deliberately; final full package tests, validators/audits and stronger-reviewer acceptance are mandatory.
4. Separate deployment approval: preserve legacy refs/dirty work/cursors, resolve real source ownership and report vault, stop old publisher and verify no in-flight run, then configure v3 clone/store/hooks/prompts/jobs. No v2/v3 simultaneous publishers.
5. Supervised pilot: verify exact remote P, parents/tree, unchanged source refs, report/receipt and refresh; record real usage. Update operational vault record only after observed deployment.
6. Rollback is reviewed corrective Git work plus explicit job/config recovery, not source history deletion or blind reset. Retain candidate journals and publication intent for reconciliation.
