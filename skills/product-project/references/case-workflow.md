# Case Workflow (`cases/`, `activities/`, `artifacts/`)

Use this reference when opening, updating, checking, or closing a case in a `product-project`.

## 1. Opening a Case

1. Check `AGENTS.md` for `case_prefix` (e.g. `PRJ`) and find the next unused sequential ID via SQL:
   ```sql
   SELECT case_id, path FROM files WHERE path LIKE 'projects/<x>/cases/%' ORDER BY case_id
   ```
2. Choose `case_kind:`:
   - `simple` — investigation, incident, compliance check, stakeholder alignment → `activities/` + `artifacts/`.
   - `complex` — full product or security solution development → `product/` chain (`requirement → concept → evaluation → spec`) + optional `activities/` and `artifacts/`.
   - A `simple` case can be promoted to `complex` later by changing `case_kind: complex` and adding `product/` notes under the same `case_id`.
3. Create `cases/<CASE-ID> <Title>.md` from `assets/template-case.md` (`type: case`, `case_id`, `case_kind`, `status: open`).
4. Define a concrete **Goal & Acceptance Criteria** (`## Goal & Acceptance Criteria` / `## Ziel & Abnahmekriterien`) so completion is unambiguous. Use a numbered list (`1.`, `2.`, …), **never** Markdown checkboxes (`- [ ]`), so the Obsidian Tasks plugin does not pick up acceptance criteria as tasks.
5. Add the case to **Active Cases** in `+<X>.md`.

## 2. Working on a Case (`activities/` and `artifacts/`)

Every file belonging to the case MUST carry `case_id: "<CASE-ID>"` in frontmatter **and** point `topics:` directly to its case note (`topics: ["[[<CASE-ID> <Case Title>]]"]` — omitting `[[+<X>]]`). The case note acts as the local MoC for human navigation in Obsidian (and links up to `+<X>.md`), while `case_id:` stays short for SQL queries.

- **Raw case inputs (`activities/raw/`):** Immutable meeting transcripts, exported emails, or arrived documents. Named `YYYY-MM-DD <Title>.md` (`type: document | transcript`, `status: raw`, `case_id:`).
- **Distilled case activities (`activities/`):** Named `YYYY-MM-DD <Title>.md` (chronological, no `case_id` prefix in filename — linkage is via `case_id:` in frontmatter):
  - `type: meeting` — digest of a case meeting (links raw transcript in `sources:` if present).
  - `type: correspondence` — email thread or external communication summary.
  - `type: note` — short oral alignment or decision without a raw source document.
  - `type: analysis` — case-specific technical or risk investigation.
- **Case deliverables (`artifacts/`):** Named `<CASE-ID> <Title>.md` (`type: artifact`, `status: draft | reviewed | final | superseded`, `case_id:`, `sources:`). Examples: risk assessment, incident memo, customer response draft.
  - **Export-ready body:** Omit `<CASE-ID>` from the body H1 heading (`# <Title>`), and put **no internal wikilinks** in the body so the text can be exported to PDF or copy-pasted into an email cleanly. Keep all source/case links in frontmatter (`sources:`, `topics:`, `case_id:`).

## 3. Case Log & Completeness Check

`## Log` in `cases/<CASE-ID> <Title>.md` is a **hand-maintained bulleted list with date and note type** (`- YYYY-MM-DD — **<Type>** [[Link]] — short note`, e.g. `Meeting`, `Analysis`, `Note`, `Correspondence`, `Artifact`, `Requirement`, `Concept`, `Evaluation`, `Spec`):

```markdown
- 2026-11-16 — **Meeting** [[2026-11-16 Stakeholder Alignment]] — Scope alignment; target rollout scheduled for Q1 2027.
- 2026-11-16 — **Artifact** [[PRJ-001 Migration Proposal]] — Drafted proposed rollout approach.
- 2026-09-24 — **Analysis** [[2026-09-24 Dependency Surface Analysis]] — Working inventory of affected services and CI pipelines.
```

Never auto-overwrite `## Log`. Instead, verify completeness whenever touching a case:

1. Query all files belonging to the case:
   ```sql
   SELECT path, type, status FROM files WHERE path LIKE 'projects/<x>/%' AND case_id = '<CASE-ID>' ORDER BY path
   ```
2. Read outgoing links of `cases/<CASE-ID> <Title>.md` via `get_links(path, direction="outgoing")`.
3. If any file with `case_id = '<CASE-ID>'` is not linked in the case note (`## Log` or `## Deliverables`), **alert the user** and propose the missing link entry.

## 4. Closing a Case

1. Verify all **Goal & Acceptance Criteria** are satisfied and no open tasks remain undecided.
2. Check whether the case outcome changes any timeless facts in `knowledge/kb/` — if so, update those `fact` notes in place (resetting them to `status: draft`) and log in `KB Log <X>.md`.
3. Update `## Summary` with the final outcome and set `status: done` (or `rejected` — see `references/archive-and-revise.md`).
4. Move the case entry in `+<X>.md` from **Active Cases** to **Completed Cases** (keep the files in place; no `closed/` folder).
5. Add a milestone line to `Chronology <X>.md` if significant.
