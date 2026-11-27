# Product Chain (`product/` — for `complex` Cases)

Use this reference when a `complex` case runs through the formal product development chain:

```text
requirement  1 ──── n  concept  n ──── 1  evaluation  1 ──── 1  spec
```

All product notes live flat in `product/`, carry the parent case's `case_id:` in frontmatter and basename prefix (`<CASE-ID>`), use **one-directional scalar wikilinks** (child → parent) for GlueSQL compatibility, and record evidence in body `## Citations` / `## Quellen`.

## 1. Create a `requirement`

- Use `assets/template-requirement.md`, named `<CASE-ID> REQ <Title>.md`.
- Set `case_id: "<CASE-ID>"`, `status: open`, and `origin:` (`feature` | `problem` | `compliance` | `initiative`).
- Document who/what triggered it under `## Trigger` / `## Auslöser` and cite sources in `## Citations` / `## Quellen`.
- Link the requirement under `## Deliverables` (and `## Log`) of `cases/<CASE-ID> <Title>.md`.
- Maintain `## Chain` / `## Kette` in the requirement body as the quick hub for its concepts, evaluation(s), and spec(s).

## 2. Develop `concept` Option(s)

- Use `assets/template-concept.md`, named `<CASE-ID> CON-a <Title>.md`, `<CASE-ID> CON-b <Title>.md`, etc.
- Set `case_id: "<CASE-ID>"`, `requirement: "[[<CASE-ID> REQ <Title>]]"`, and `status: draft`.
- Set `requirement.status: active` (if still `open`) and link the concept in both the requirement's `## Chain` and the case's `## Log`.
- Concepts are updated in place while in discussion; cite supporting notes/facts in `## Citations` / `## Quellen`.

## 3. Run an `evaluation`

Every complex case goes through an `evaluation` — **including single-concept reviews** — so every decision and its rationale are captured uniformly.

- Use `assets/template-evaluation.md`, named `<CASE-ID> EVA <Title>.md`.
- Set `case_id: "<CASE-ID>"`, `requirement: "[[<CASE-ID> REQ <Title>]]"`, and `status: draft`.
- Compare candidate concepts under `## Comparison` / `## Vergleich` (linking each concept in the body) and cite evidence in `## Citations` / `## Quellen`.
- **Optional constraint check:** On user request or when configured in `projects/<x>/AGENTS.md`, run the Constraint Satisfaction Check (`references/verify-and-lint.md`, `mode: constraints`) against `requirement` constraints and `knowledge/kb/` facts, persisting a compact `## Verification` table inside `## Comparison` / `## Rationale` (or `## Vergleich` / `## Begründung`).
- After the decision meeting / user confirmation:
  - Set `status: decided`, `decided_on: YYYY-MM-DD`, and `chosen: "[[<CASE-ID> CON-x <Title>]]"` (or leave empty if all concepts were rejected).
  - Set `status: evaluated` on every compared `concept` (never duplicate chosen/rejected on the concept itself).
  - Link the evaluation in the requirement's `## Chain` and the case's `## Log`.
  - If `chosen:` is empty, either return the requirement to `status: open` or reject the case (`references/archive-and-revise.md`).

## 4. Author and Track a `spec`

- Use `assets/template-spec.md`, named `<CASE-ID> SPEC <Title>.md`.
- Set `case_id: "<CASE-ID>"`, `concept: "[[<CASE-ID> CON-x <Title>]]"`, and `evaluation: "[[<CASE-ID> EVA <Title>]]"`.
- **Pre-review verification:** Run the Tier-2 Grounding Check (`references/verify-and-lint.md`, `mode: grounding`) before `spec` transitions `draft → reviewed` — verifying critical claims, numbers, and rules against `raw/`, `activities/`, and `knowledge/kb/` via `## Citations` / `## Quellen`.
- **Document lifecycle (`status:`):** `draft` → `reviewed` (human approval + `reviewed_on:`) → `active` (handed over to team). Updated in place for refinements within the decided concept.
- **Team delivery tracking (optional scalar properties):**
  - `implementation_status:` `planned` → `in-progress` → `implemented`
  - `ticket:` Jira key or URL (e.g. `PROJ-123` or `https://...`)
- Link the spec in the requirement's `## Chain` and the case's `## Deliverables`.

## 5. Completion & Feedback Loop

Explicitly distinguish `spec.status: active` (handed over / planned — do **NOT** write planned state into `knowledge/kb/`) from realized implementation:

When `spec.implementation_status` reaches `implemented`:

1. Run **State-Delta-Compile** (`references/ingest-and-compile.md` §5–§6) from the final `spec` plus any cited domain `analysis` into `knowledge/kb/` (updating `scope: solution` and any newly settled `scope: domain` facts via 4-way Delta-Compile + Tier-2 grounding check, logged in `KB Log <X>.md`).
2. Set `requirement.status: done` and `case.status: done`.
3. Move the case entry in `+<X>.md` from **Active Cases** to **Completed Cases** (keep all files in place; no `closed/` folder).

## 6. Revising a Decision

When product evolution requires reversing an earlier decision:

1. Create `<CASE-ID> EVA-r2 <Title>.md` with `case_id:`, `requirement:`, and `supersedes: "[[<CASE-ID> EVA ...]]"`.
2. Once decided, set the old evaluation to `status: superseded` + `superseded_by: "[[<CASE-ID> EVA-r2 ...]]"`.
3. Query active specs referencing the superseded evaluation and set them to `status: stale`:
   ```sql
   SELECT path, status FROM files
   WHERE path LIKE 'projects/<x>/product/%'
     AND path NOT LIKE 'projects/<x>/archive/%'
     AND type = 'spec'
     AND evaluation = '[[<CASE-ID> EVA ...]]'
   ```
4. Author `<CASE-ID> SPEC-r2 <Title>.md` pointing to the newly chosen `concept:` and `evaluation: "[[<CASE-ID> EVA-r2 ...]]"`.
5. Update the requirement's `## Chain` and the case's `## Log`. Old evaluation and stale spec move to `archive/` once the replacement spec is `active` (`references/archive-and-revise.md`).
