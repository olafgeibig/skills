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
| Very large or unstructured timeless source where only selective aspects are needed, or feeding multiple topics (long transcript, contract, dense paper) | `knowledge/raw/` → `knowledge/distilled/` (`extract \| research \| analysis`) → `knowledge/kb/` | Use `distilled/` only when an intermediate extract or cross-source `analysis` adds real value — never duplicate 1:1 into `kb/` |
| Structured timeless primary source (most articles, specs, short papers, companion repos) | `knowledge/raw/` → `knowledge/kb/` (direct, topic-first) | **Default path:** compile directly into thematic `kb/fact` notes without a redundant `distilled/` wrapper |
| Timeless domain/solution research conducted during a case (e.g., compliance rule) | Directly into `knowledge/kb/` (`fact`, or `knowledge/distilled/` `research` if multi-source/large) | Link from the case rather than isolating timeless knowledge inside a finite case |
| New bounded work item | `cases/<CASE-ID> <Title>.md` | Open `simple` or `complex` case (`references/case-workflow.md`) |

## 2. Managing `knowledge/masterdata/`

- Use `assets/template-masterdata.md` (`type: masterdata`, `class: people | system | schedule | glossary`; omit `status:`).
- `masterdata/` holds user-owned lookup tables only. Agents create or update values **only on explicit user instruction**; otherwise cite by `[[Wikilink]]` (never copy lookup values into prose).
- Enforce zero tasks/checkboxes (`query_tasks` returns empty) and no inline history sections.

## 3. Step 1 — Ingest Raw (`knowledge/raw/`)

- Use `assets/template-document.md` (`type: document` or `type: transcript`, `status: raw`).
- Name with a date prefix: `YYYY-MM-DD <Short Title>.md`.
- Record `created`, scalar `source` (relative path, URL, or prose — never a wikilink), and `sha256` when known.
- Keep body verbatim; **never edit a raw note after ingest** (exception: appending a complete newer email thread export if applicable). Do **not** add processing flags to raw frontmatter — discover unprocessed raw sources via `get_links(raw_path, direction="incoming")`.
- **Truncated / paywall source guard:** Never compile `kb/fact` notes from truncated extracts or paywall-clipped summaries. If full text could not be captured, set `status: incomplete` at ingest, add a top warning, and ask the user for the full source.

## 4. Step 2 — Distill (`knowledge/distilled/`, Only When Needed)

Skip `knowledge/distilled/` by default whenever a raw source can be compiled directly into topic-oriented `knowledge/kb/` notes without losing traceability. Create a `knowledge/distilled/` note **only** for:
- Very large or unstructured primary sources (long transcripts, contracts, dense papers) where selective extraction or a dated `as_of` snapshot feeds multiple topics; or
- Cross-source syntheses and comparisons (`type: analysis`).

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

Decompose source insights into atomic, explicit, verifiable claims and map them onto **topic/concept/component** `fact` notes (never 1:1 source-summary facts):

- **Topic-first & page threshold:** Create a new `fact` note only for a central domain concept, mechanism, or solution component (or a topic recurring across ≥2 sources) — never for passing mentions. Default on overlap is **enriching an existing topic `fact`**.
- **Canonicalize aliases & bundle companion sources:** Check for synonyms/aliases across existing `fact` notes before creating a new file so different terms for the same mechanism aggregate into one canonical note. Compile companion sources for the same work (e.g., paper + reference GitHub repo) together into the same thematic `fact` notes.

Reconcile each atomic claim against existing `fact` notes:

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

**Post-compile horizontal enrichment pass:** A compile is not done until new or updated `kb/fact` notes link **horizontally** to related `kb/fact` and `knowledge/masterdata/` notes (inline or under `## Related` / `## Verwandte Fakten`). When adding a new topic `fact`, add concise see-also cross-links in 2–3 closely related existing `kb/fact` notes where meaningful (keeping `reviewed` untouched if only a see-also link is added, or batching with substantive edits).

## 6. Step 4 — Pre-Review Grounding Check & Human Approval

- Run the Tier-2 verifier subagent (`references/verify-and-lint.md`, `mode: grounding`) over new or substantively modified `draft` facts (individually or as a batch) against their `## Citations` / `## Quellen` and active `reviewed` facts **before** asking the user to approve `draft → reviewed`.
- Fix any flagged bare assertions or surface conflicts (`disputed`), append a one-line `verified` entry to `KB Log <X>.md`:
  `- YYYY-MM-DD | verified | [[Fact]] — grounded against citations (verifier subagent)`
- Request explicit user approval to transition `status: reviewed` and set `reviewed_on: YYYY-MM-DD`.
