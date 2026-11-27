# Case Workflow (Case Knowledge)

Use this reference when opening, working on, promoting from, checking, or closing a case in a `product-project`.

## 1. Opening a Case

1. Check `AGENTS.md` for `case_prefix` (e.g. `PRJ`) and find the next unused sequential ID via scoped SQL:
   ```sql
   SELECT case_id, path FROM files
   WHERE path LIKE 'projects/<x>/cases/%'
     AND path NOT LIKE 'projects/<x>/archive/%'
   ORDER BY case_id
   ```
2. Choose `case_kind:`:
   - `simple` — investigation, incident, compliance check, stakeholder alignment → `activities/` + `artifacts/`.
   - `complex` — full product or security solution development → `product/` chain (`requirement → concept → evaluation → spec`) + optional `activities/` and `artifacts/`.
   - A `simple` case can be promoted to `complex` later by changing `case_kind: complex` and adding `product/` notes under the same `case_id`.
3. Create `cases/<CASE-ID> <Title>.md` from `assets/template-case.md` (`type: case`, `case_id`, `case_kind`, `status: open`).
4. Define concrete **Goal & Acceptance Criteria** (`## Goal & Acceptance Criteria` / `## Ziel & Abnahmekriterien`) using a numbered list (`1.`, `2.`, …), **never** Markdown checkboxes (`- [ ]`), so the Obsidian Tasks plugin does not capture acceptance criteria as personal tasks.
5. Add the case to **Active Cases** in `+<X>.md`.

## 2. Working on a Case (`activities/` and `artifacts/`)

Every file across all 5 Case Knowledge folders MUST carry scalar `case_id: "<CASE-ID>"` in frontmatter **and** point `topics:` directly to its case note (`topics: ["[[<CASE-ID> <Case Title>]]"]` — omitting `[[+<X>]]`). The case note acts as the local MoC (linking up to `+<X>.md`), while `case_id:` stays short for SQL queries.

- **Raw case inputs (`activities/raw/`):** Immutable meeting transcripts, exported emails, or arrived documents. Named `YYYY-MM-DD <Title>.md` (**no** `<CASE-ID>` filename prefix; `type: document | transcript`, `status: raw`, `case_id:`, scalar `source`). Originals stay permanently in place — never move them on case close so KB citations never break.
- **Distilled case activities (`activities/`):** Named `<CASE-ID> YYYY-MM-DD <Title>.md` (`case_id:`, `status: current | superseded`, optional `superseded_by`), with a one-line `Case: [[<CASE-ID> <Case Title>]]` pointer directly under H1 and body `## Citations` / `## Quellen` when derived:
  - `type: extract` — digest of a case meeting transcript or document.
  - `type: research` — targeted investigation of external docs, standards, or behavior for the case.
  - `type: analysis` — case-specific technical, architectural, or risk reasoning.
  - `type: note` — short oral alignment or decision without a raw source document.
  - **Brake on note inflation:** Routine two-line emails in `activities/raw/` earn a single bullet in `cases/<ID>.md` `## Log`, not a separate `activities/` note.
  - **Grounding on decision-bearing analyses:** `analysis` and `research` notes follow the same anti-*bare assertion* grounding and passage-anchor rules as `knowledge/distilled/`; run Tier-2 grounding verification (`references/verify-and-lint.md`) when they serve as the basis for an `artifact`, `EVA`, `SPEC`, or KB promotion (or when configured in `AGENTS.md`).
- **Case deliverables (`artifacts/`):** Named `<CASE-ID> <Title>.md` (`type: artifact`, `status: draft | reviewed | final | superseded`, `case_id:`, `reviewed_on` when `reviewed`, optional `superseded_by`). Examples: risk assessment, incident memo, customer response draft.
  - Keep `<CASE-ID>` in the filename and omit it from the body H1 heading (`# <Title>`).
  - Use uniform body `## Citations` / `## Quellen` with Obsidian `[[Wikilinks]]`.
  - Run a Tier-2 grounding check (`references/verify-and-lint.md`) before `draft → reviewed`.

## 3. Case Log & Completeness Check

`## Log` in `cases/<CASE-ID> <Title>.md` is a **hand-maintained bulleted list with date and note type** (`- YYYY-MM-DD — **<Type>** [[Link]] — short note`, using `Extract`, `Research`, `Analysis`, `Note`, `Artifact`, `Requirement`, `Concept`, `Evaluation`, `Spec`):

```markdown
- 2026-11-16 — **Extract** [[PRJ-001 2026-11-16 Stakeholder Alignment]] — Scope alignment; target rollout scheduled for Q1 2027.
- 2026-11-16 — **Artifact** [[PRJ-001 Migration Proposal]] — Drafted proposed rollout approach.
- 2026-09-24 — **Analysis** [[PRJ-001 2026-09-24 Dependency Surface Analysis]] — Working inventory of affected services and CI pipelines.
```

Never auto-overwrite `## Log`. Verify completeness whenever touching a case:

1. Query all active files belonging to the case:
   ```sql
   SELECT path, type, status FROM files
   WHERE path LIKE 'projects/<x>/%'
     AND path NOT LIKE 'projects/<x>/archive/%'
     AND case_id = '<CASE-ID>'
   ORDER BY path
   ```
2. Read outgoing links of `cases/<CASE-ID> <Title>.md` via `get_links(path, direction="outgoing")`.
3. If any file with `case_id = '<CASE-ID>'` is not linked in the case note (`## Log` or `## Deliverables`), **alert the user** and propose the missing link entry.

## 4. Mid-Case Promotion (`Promote to KB`)

Triggered explicitly by the user (or proposed by the agent during long-running cases) whenever an `analysis`, `research`, `artifact`, or `spec` yields durable knowledge.

- **Generic promotion criteria (owned by skill):**
  1. *Timeless relevance:* Useful beyond this single case.
  2. *Current-state truth only:* Already-valid domain rules (`scope: domain`) or already-existing solution behavior (`scope: solution`). Unimplemented target-state proposals remain in the case/`product/` until realized.
  3. *Grounded:* Backed by a concrete cited source (`activities/raw/`, `activities/`, `artifact`, or `spec`).
- **Project-specific criteria:** Check `projects/<x>/AGENTS.md` for additional domain-specific promotion rules or exclusions.
- **Execution:** Run the **4-way Delta-Compile** (`references/ingest-and-compile.md` §5–§6 — preserving `reviewed` on pure additive confirmation, setting `draft` on substantive edits, running Tier-2 pre-review grounding check, logging in `KB Log <X>.md`).

## 5. Closing a Case (`State-Delta-Compile`)

1. User confirms all **Goal & Acceptance Criteria** are satisfied and no open tasks remain undecided. Run the Constraint Satisfaction Check (`references/verify-and-lint.md`) only on demand or if required by `AGENTS.md`.
2. Run **State-Delta-Compile** for remaining unpromoted current-state changes (via 4-way Delta-Compile in `references/ingest-and-compile.md`):
   - `simple` case: read the final `artifact`, or — if no `artifact` exists — `cases/<ID>.md` (`## Summary`) plus designated closing `analysis`. Ignore routine `extract`/`note` chatter unless explicitly cited.
   - `complex` case: triggered once `spec.implementation_status: implemented` (`references/product-chain.md` §5).
   - Also check briefly whether any timeless `scope: domain` insights remain unpromoted.
3. Update `## Summary` with the final outcome and set `status: done` (or `rejected` — `references/archive-and-revise.md`).
4. Move the case entry in `+<X>.md` from **Active Cases** to **Completed Cases** (keep all files in place so KB citations into `activities/raw/` never break; no `closed/` folder).
5. Add a milestone line to `Chronology <X>.md` if significant.
