# Proposal

## Why

The current cross-machine skill sync can omit clean merge results, confuse consumed commits with unpublished work, and discard concurrent contributions during transport resets. Replace rewritten-history heuristics with native Git ancestry and make autonomous review observable without imposing a daily human approval queue.

## What Changes

- **BREAKING:** Integrate reviewed snapshots as genuine merge commits with parents `(captured main, captured source)`; retire transport force resets, replay rebases and old publication bypasses.
- Keep runtime producer checkouts separate from candidate/publisher worktrees; preserve T2 if it arrives while T is under review.
- Automatically review additions, corrections and explicit rule replacements, with final-tree validation and immutable review reports plus publication receipts.
- Store deployment reports in the configured vault directory; the agreed private deployment destination is `akademeia`, `projects/hermes-agent/reports/`. User feedback is optional and dictated in a normal chat.
- Add explicit exact-tip refactoring submissions, merge-main development and a short publisher-only integration freeze; never auto-discover unfinished refactor branches.
- Fix staging retries, producer interlocks, explicit ledger bootstrap, hook preservation, non-mutating dry runs, health signals and interrupted-push reconciliation.
- Use bounded change/context packets and measured usage reporting; measure a pilot before claiming a token ceiling. Do not load the entire implementation plan or full source versions into each runtime review.
- Prepare focused subagent work packets and a stronger-model final verification gate. This change prepares artifacts only; implementation, commits and live rollout are not authorized by artifact creation.

## Capabilities

### New Capabilities

- `skill-source-transport`: safe producer staging, merge-based refresh and exact reviewed-tip publication.
- `skill-merge-publication`: immutable candidates, native merge preparation, final-tree gates, owned publisher lock and recoverable non-force publication.
- `skill-review-reporting`: autonomous semantic decisions, bounded review context, immutable reports, receipts, optional chat feedback and periodic skill review.
- `skill-refactor-integration`: isolated refactoring worktrees, explicit readiness submission and exact-tree integration without stopping producers.

### Modified Capabilities

None. The local OpenSpec capability inventory was empty at creation; these establish requirements for existing behavior being replaced, not a claim that the implementation is new from scratch.

## Impact

Python stdlib scripts, tests, templates and references in `skills/skill-library-maintenance/`; a narrowly scoped governance update in `skills/skill-governance/SKILL.md`. Add `skill_repo_workflow.py` as a shared core; keep existing CLI filenames as adapters. No new service, provider SDK, database or mandatory human gate.

The project concept and detailed engineering plan remain in the `hermes-agent` vault project. This change's proposal/specs/design/tasks are the executable OpenSpec contract; per-work-packet briefs point to only the relevant sections. No live Git/config/cron/profile migration occurs during planning or ordinary code tasks. Existing dirty changes in the runtime checkout are preserved and not attributed to this implementation.
