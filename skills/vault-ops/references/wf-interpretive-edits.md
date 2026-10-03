# Interpretive Edits

For edit requests against existing notes where the request describes an outcome or a problem instead of the exact change. The workflow keeps interpretive work auditable: read first, propose, confirm, then write. Literal instructions skip straight to execution.

## Two modes

| Request shape | Mode |
|---|---|
| Describes a problem or outcome — "go through the tasks and fix what is wrong", "check this", "clean that up", "audit" | **interpretive** → audit → diff → confirm → write |
| Names the change — "delete line X", "change Y to Z", "add W" | **literal** → execute directly |

If a request is ambiguous, treat it as interpretive; one short clarifying question is cheaper than an unwanted rewrite. Interpretive work always starts with a read-only audit, never with a write. A clear correction — a wrong/strip value, or a replace with an unambiguous target — is not interpretive work: execute the grep → classify → patch pass directly (see Patch scope / Correction intent) and report the inventory afterwards. Confirm applies only when scope or intent is genuinely ambiguous.

## The workflow

1. **Audit (read-only).** Read every note that could be affected — the named note plus its siblings, the enclosing MoC, and any index or list that enumerates it. Parallelize the reads. Build a model of the current state: where the complaint applies, which changes would address it, and what remains ambiguous.
2. **Diff (proposal, not change).** Present the intended changes as a compact before/after list or table: file path, exact before text, exact after text, one-sentence rationale. Group by file, keep it scannable. Nothing is written to disk in this step; every decision the agent made quietly belongs in the proposal.
3. **Confirm (wait).** Stop and wait for approval, modification, or rejection. When the diff contains a genuine choice, present the options with a recommendation instead of an ambiguous diff.
4. **Write (apply the approved diff).** Use targeted `edit_note` SEARCH/REPLACE blocks per approved change, or `write_note` overwrite where matching is fragile. Verify each write by reading the target back — a write response is not verification. Tool mechanics (dry-run preview, hash-guarded apply, the exact `edits` shape) live in the `turbovault-use` skill.

## Pre-write checklist (before the first change)

1. **Project skill loaded** — the skill owning the affected notes' conventions (for `projects/<dir>/` or `area/<dir>/` paths: the `project-<dir>` skill, if it exists).
2. **Search before write** — `search_files` for the filename the user named before the first change: it often already exists under a different scope. Read the target file and check its section headings before any patch/write.
3. **Template/sibling check** — missing template → derive the shape from siblings, only after (1), which may already document the de facto template.
4. **Patch-scope class** — sort every old-value hit into class 1/2/3 (below).
5. **Correction intent** — strip vs replace vs forward-looking (below).

## Patch scope: classify every hit

- **Class 1 — direct fact** (the table/list cell holding the old value): **patch** — leaving it is an inconsistency.
- **Class 2 — derived quantity** (computed from sub-values that all stay unchanged — not a restatement of the changed value; a restatement is class 1 and does get the new value): **keep** — the result cannot change.
- **Class 3 — logic block** (a calculation, plan, or recommendation built on the changed value): **keep** — strict-keep when the user says the logic stays, even if a small numeric inconsistency results.

Minimal-invasive default for a value patch (time, number, ID, dimension): `grep` the old value, patch class 1, keep 2–3, no confirm menu for an obvious default. Send an inventory table ("N×1, N×2, N×3 — patch N, keep N?") only when the scope exceeds ~5 locations or the classification is genuinely ambiguous; otherwise patch and report what was deliberately left untouched.

## Correction intent: strip vs replace

| Phrasing | Intent | Action |
|---|---|---|
| "X is wrong / drop it / strip it / false information / it doesn't hold" | **Wrong/strip** | Global grep for X; patch every occurrence in one pass, **no transitional language** ("formerly X"); inventory at the end as an audit trail, not up front as a question — at any hit count (the ~5-location inventory table applies to scopes with class-2/3 keeps that need sign-off, not to a clear strip). |
| "change X to Y" / "correct to Y" / "replace X with Y" | **Replace** | Only the user-named locations; old value in parentheses is fine when structurally useful. |
| "X no longer applies" / "we now use Y" / "from now on Y" | **Forward-looking** | Document the old value as superseded; the new value is current. |

Unclear intent defaults to replace (old → new, without quoting the old). A confirm menu is only for a genuinely ambiguous request — a clear strip intent needs none.

## Phases for larger approved work

An approved multi-file change of ten or more notes should not run as one burst unless the request explicitly asks for one go:

1. Offer phases in the audit step: propose a boundary — "I'll split this into N phases. Phase 1: X (files). Then I pause for your review."
2. Keep phases at roughly 10–25 files; the user picks the boundary. Smaller phases mean finer review, larger phases fewer round-trips.
3. After each phase, report ONE terse summary ("15 patches in 5 files, 0 unexpected findings — continue with phase 2?"), not a re-run of the discussion.
4. When a phase reveals a new pattern — a convention that was not visible during the audit — stop and ask before the next phase instead of deciding and patching on. A wrong pattern discovered at file 22 is cheap to fix; applied to the next 20 files it multiplies rework.

## After confirmation

- Execute the approved changes; do not re-open the decision, re-explain rejected alternatives, re-survey the file, or re-ask whether the user is sure.
- If a follow-up item truly depends on an answer, ask one short question — never return to a question that was already answered.
- A new blocker surfaces in one line, then continue with what is unaffected.

## Related

- `turbovault-use` — `edit_note` mechanics, dry-run preview, hash-guarded apply, fuzzy-match handling.
- `./references/propagation-audits.md` — when a changed value or status is echoed across other notes.
