# Ingest, Masterdata, and Compile (Project Knowledge)

Use this reference when triaging `inbox/`, maintaining `knowledge/masterdata/`, or compiling **Project Knowledge** (`knowledge/raw → distilled → kb`). Notes under `knowledge/` carry **no `case_id`**.

If an email, transcript, or analysis belongs to a specific finite incident, investigation, or change request, route it to `activities/` under its `case_id` instead (`references/case-workflow.md`).

## 1. Triage & Intake Routing

Quick captures, pasted links, or unprocessed drops land in `inbox/` without required frontmatter. Route each item using this table:

| Input kind | Destination | Rule |
|---|---|---|
| Pure external pointer / bookmark | `Bookmarks <X>.md` | Append link and remove inbox item |
| Stable user-owned lookup data (people, systems, schedules, glossary) | `knowledge/masterdata/` | `type: masterdata`, `class: people \| system \| schedule \| glossary`; no review gate, no checkboxes |
| Case original (email, transcript, case-specific report) | `activities/raw/` (`YYYY-MM-DD <Title>.md`, no `<CASE-ID>` prefix) | Originals stay in place permanently; never moved on close |
| Short oral case alignment / brief case decision (no raw file) | `activities/` (`<CASE-ID> YYYY-MM-DD <Title>.md`, `type: note`) | Or single bullet in `cases/<ID>.md` `## Log` if trivial (brake on note inflation) |
| Project-wide baseline doc obtained during a case (standard, handbook, architecture doc) | `knowledge/raw/` (directly on arrival, no `case_id`) | Avoids later file moves; link it from the case |
| Large, unstructured, or multi-use timeless source (paper, long spec, transcript) | `knowledge/raw/` → `knowledge/distilled/` (`extract \| research \| analysis`) → `knowledge/kb/` | Preserves raw text, enforces passage anchors, enables `superseded` cascades |
| Short, already-structured timeless primary source | `knowledge/raw/` → `knowledge/kb/` (direct) | Skips boilerplate `distilled/` wrapper; cites `knowledge/raw/` note directly |
| Timeless domain/solution research conducted during a case (e.g., compliance rule) | Directly into `knowledge/distilled/` (`research`) → `knowledge/kb/` (`fact`) | Link from the case rather than isolating timeless knowledge inside a finite case |
| New bounded work item | `cases/<CASE-ID> <Title>.md` | Open `simple` or `complex` case (`references/case-workflow.md`) |

## 2. Managing `knowledge/masterdata/`

- Use `assets/template-masterdata.md` (`type: masterdata`, `class: people | system | schedule | glossary`; omit `status:`).
- `masterdata/` holds user-owned lookup tables only. Agents create or update values **only on explicit user instruction**; otherwise cite by `[[Wikilink]]` (never copy lookup values into prose).
- Enforce zero tasks/checkboxes (`query_tasks` returns empty) and no inline history sections.

## 3. Step 1 — Ingest Raw (`knowledge/raw/`)

- Use `assets/template-document.md` (`type: document` or `type: transcript`, `status: raw`).
- Name with a date prefix: `YYYY-MM-DD <Short Title>.md`.
- Record `created`, scalar `source` (relative path, URL, or prose — never a wikilink), and `sha256` when known.
- Keep body verbatim; **never edit a raw note after ingest** (exception: appending a complete newer email thread export if applicable).

## 4. Step 2 — Distill (`knowledge/distilled/`)

- Use `assets/template-distilled.md`:
  - `type: extract` — structured extraction from a meeting transcript, document, or interview.
  - `type: research` — digest of external standards, compliance rules, or technical docs.
  - `type: analysis` — multi-source reasoning about timeless project knowledge.
- Filename: `YYYY-MM-DD <Title>.md` *(or `<Title>.md` for timeless topic analyses)*.
- Set `status: current`, `as_of: YYYY-MM-DD`, and record provenance in body `## Citations` (English) / `## Quellen` (German) at the bottom of the body (above any optional `Topics:` footer):
  ```markdown
  ## Citations

  - [[2026-02-07 Ko et al - When Is Enough Not Enough]] — §3.5, "We set N=3 empirically."
  - [Vendor API Spec](https://example.org/api) — rate-limit section
  ```
- **Why Obsidian `[[Wikilinks]]`:** They keep frontmatter slim, preserve Obsidian auto-rename and filename spaces, and resolve to full vault-relative paths via TurboVault `get_links`. (Do not force `%20`-encoded relative Markdown links for TurboVault `4.1.0` OKF v0.1 `parse_citations` regex compatibility.)
- **Grounding & anchor rule:** Every substantive claim must trace to a source in `## Citations` / `## Quellen`. Section numbers, timestamps, or short verbatim quote anchors are **mandatory** when citing large or multi-section raw sources (papers, long transcripts, policy documents) and optional only for short atomic notes. Separate verified facts from assumptions; never add ungrounded parametric knowledge.
- **Pre-close superseding check:** Search `knowledge/distilled/` (`exclude_paths: ["archive/"]`). If replacing an older note, set the older note to `status: superseded` + `superseded_by: "[[...]]"`, then call `get_links(old_path, direction="incoming")` and flag every active dependent `knowledge/kb/` `fact` as `status: stale` (logged in `KB Log <X>.md`).
- For dense or high-stakes sources, optionally run a Tier-2 grounding check (`references/verify-and-lint.md`).

## 5. Step 3 — 4-Way Delta-Compile into `knowledge/kb/`

**Mandatory pre-query before writing:** Run scoped SQL + BM25 search:

```sql
SELECT path, scope, status, as_of FROM files
WHERE path LIKE 'projects/<x>/knowledge/kb/%'
  AND path NOT LIKE 'projects/<x>/archive/%'
  AND type = 'fact'
ORDER BY path
```

plus `mcp__turbovault__search(query=..., exclude_paths=["archive/"], frontmatter_filters=[{"key": "type", "value": "fact"}])`.

Decompose distilled insights into atomic verifiable claims and reconcile each against existing `fact` notes:

1. **Confirm (Satisfied, body unchanged):** Append source to `## Citations` / `## Quellen`, bump `as_of:`, **keep `status: reviewed` and `reviewed_on:` untouched**, and log one line in `KB Log <X>.md`.
2. **Expand / Refine:** Rewrite body in place to current state only, update `## Citations` / `## Quellen` and `as_of:`, reset `status: draft` and clear `reviewed_on:`, and log in `KB Log <X>.md`.
3. **Contradict (Refuted):** Never silently overwrite a `reviewed` fact. Set `status: disputed`, add the conflicting source to `## Citations` / `## Quellen`, insert the conflict callout directly under H1, log in `KB Log <X>.md`, and surface to the user:
   ```markdown
   > [!warning] Disputed — awaiting human resolution
   > - **Existing claim:** <claim A> ([[Source A]] — "<short verbatim quote>")
   > - **Conflicting claim:** <claim B> ([[Source B]] — "<short verbatim quote>")
   > - **Resolution needed:** Which claim reflects current truth?
   ```
4. **New (Unknown):** Create from `assets/template-fact.md` (`scope: domain | solution`, `status: draft`, `## Citations` / `## Quellen`), link from `+<X>.md`, and log in `KB Log <X>.md`.

## 6. Step 4 — Pre-Review Grounding Check & Human Approval

- Run the Tier-2 verifier subagent (`references/verify-and-lint.md`, `mode: grounding`) over new or substantively modified `draft` facts (individually or as a batch) against their `## Citations` / `## Quellen` and active `reviewed` facts **before** asking the user to approve `draft → reviewed`.
- Fix any flagged bare assertions or surface conflicts (`disputed`), append a one-line `verified` entry to `KB Log <X>.md`:
  `- YYYY-MM-DD | verified | [[Fact]] — grounded against citations (verifier subagent)`
- Request explicit user approval to transition `status: reviewed` and set `reviewed_on: YYYY-MM-DD`.
