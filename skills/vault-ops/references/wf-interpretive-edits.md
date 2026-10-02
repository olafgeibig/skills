# Interpretive Edits

For edit requests against existing notes where the request describes an outcome or a problem instead of the exact change. The workflow keeps interpretive work auditable: read first, propose, confirm, then write. Literal instructions skip straight to execution.

## Two modes

| Request shape | Mode |
|---|---|
| Describes a problem or outcome — "go through the tasks and fix what is wrong", "check this", "clean that up", "audit" | **interpretive** → audit → diff → confirm → write |
| Names the change — "delete line X", "change Y to Z", "add W" | **literal** → execute directly |

If a request is ambiguous, treat it as interpretive; one short clarifying question is cheaper than an unwanted rewrite. Interpretive work always starts with a read-only audit, never with a write.

## The workflow

1. **Audit (read-only).** Read every note that could be affected — the named note plus its siblings, the enclosing MoC, and any index or list that enumerates it. Parallelize the reads. Build a model of the current state: where the complaint applies, which changes would address it, and what remains ambiguous.
2. **Diff (proposal, not change).** Present the intended changes as a compact before/after list or table: file path, exact before text, exact after text, one-sentence rationale. Group by file, keep it scannable. Nothing is written to disk in this step; every decision the agent made quietly belongs in the proposal.
3. **Confirm (wait).** Stop and wait for approval, modification, or rejection. When the diff contains a genuine choice, present the options with a recommendation instead of an ambiguous diff.
4. **Write (apply the approved diff).** Use targeted `edit_note` SEARCH/REPLACE blocks per approved change, or `write_note` overwrite where matching is fragile. Verify each write by reading the target back — a write response is not verification. Tool mechanics (dry-run preview, hash-guarded apply, the exact `edits` shape) live in the `turbovault-use` skill.

## Phases for larger approved work

An approved multi-file change of roughly ten or more notes should not run as one burst:

1. Offer phases in the audit step: propose a boundary — "I'll split this into N phases. Phase 1: X (files). Then I pause for your review."
2. Keep phases at roughly 10–25 files; the user picks the boundary. Smaller phases mean finer review, larger phases fewer round-trips.
3. After each phase, report ONE terse summary ("15 patches in 5 files, 0 unexpected findings — continue with phase 2?"), not a re-run of the discussion.
4. When a phase reveals a new pattern — a convention that was not visible during the audit — stop and ask before the next phase instead of deciding and patching on. A wrong pattern discovered at file 22 is cheap to fix; applied to the next 20 files it multiplies rework.

## After confirmation

- Execute the approved changes; do not re-open the decision, re-explain rejected alternatives, or re-ask whether the user is sure.
- If a follow-up item truly depends on an answer, ask one short question — never return to a question that was already answered.
- A new blocker surfaces in one line, then continue with what is unaffected.

## Related

- `turbovault-use` — `edit_note` mechanics, dry-run preview, hash-guarded apply, fuzzy-match handling.
- `./references/propagation-audits.md` — when a changed value or status is echoed across other notes.
