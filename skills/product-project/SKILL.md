---
name: product-project
description: "Use when running a product-project: KB, cases & product."
version: "0.1.0"
author: Olaf Geibig
license: MIT
metadata:
  source: https://github.com/olafgeibig/skills
  hermes:
    category: personal
    tags:
      - projects
      - knowledge-base
      - cases
      - product
      - vault
    related_skills:
      - hermes-projects
      - vault-ops
      - turbovault-use
---

# Product Project

A project kind for product management and solution development inside a vault. It separates **timeless project knowledge** (`knowledge/raw → distilled → kb`) from **case-bound work** (`cases/`, `activities/`, `artifacts/`, `product/`), supporting both lightweight `simple` cases (investigations, assessments) and `complex` cases (product chain `requirement → concept → evaluation → spec`), guarded by human review gates and SQL-friendly scalar frontmatter relations.

Project setup, manual and Projektform belong to `hermes-projects`; generic note mechanics belong to `vault-ops`; TurboVault calls belong to `turbovault-use`. This skill owns the folders, the `type:`/`status:` vocabulary, the case wrapper, the review gates, the product chain, archive isolation, and TurboVault validation queries.

**Projekttyp `product-project`, Containertyp `vault`.** The project lives under `projects/<x>/` in a vault and is governed inside that subtree only. Always read the project's `AGENTS.md` on entry — it declares `case_prefix`, documentation language, external links, and any local deviations.

## When to Use

- Set up a new `product-project` or adopt an existing project onto this kind
- Triage `inbox/` items or compile timeless `knowledge/` sources into review-gated `fact` notes
- Open, log, or close a `simple` or `complex` case (`<CASE-ID>`) with `activities/` and `artifacts/`
- Run the `product/` chain (`requirement → concept → evaluation → spec`), revisions, or delivery tracking
- Archive retired chains or validate a `product-project` via TurboVault SQL and `graph_report`

Not for long-lived personal/legal affairs (`dossier-project`), standalone deliverable authoring (`authoring-project`), or multi-domain wikis (`vault-wiki`).

## Directory Structure

```text
projects/<x>/
├── +<X>.md                # type: moc — entry hub (KB + active/completed cases)
├── AGENTS.md              # project manual (Projekttyp, Containertyp, case_prefix, language)
├── Tasks <X>.md           # type: utility — single tasks query block scoped to projects/<x>/
├── Chronology <X>.md      # type: utility — project milestones
├── Bookmarks <X>.md       # type: bookmarks — curated external links (optional)
├── inbox/                 # unclassified quick captures & arrivals (no required frontmatter)
├── knowledge/             # timeless project knowledge (NO case_id prefix)
│   ├── raw/               # immutable primary inputs (YYYY-MM-DD <Title>.md)
│   ├── distilled/         # timeless digests & analyses
│   └── kb/                # atomic curated facts (type: fact) + KB Log <X>.md
├── cases/                 # one note per case (<CASE-ID> <Title>.md)
├── activities/            # case-bound work
│   ├── raw/               # immutable case transcripts & mails (YYYY-MM-DD <Title>.md)
│   └── ...                # distilled meetings, correspondence, notes, analyses (YYYY-MM-DD <Title>.md)
├── artifacts/             # case work products (<CASE-ID> <Title>.md)
├── product/               # product chain for complex cases (<CASE-ID> REQ/CON/EVA/SPEC <Title>.md)
└── archive/               # retired/rejected items; excluded from normal retrieval
```

- **Timeless vs. case-bound:** Put timeless project knowledge in `knowledge/` (no `case_id` prefix). Put incident/change meetings, emails, oral notes, and case analyses in `activities/` with `case_id:`.
- **`cases/` has one file per case** (`<PREFIX>-<NNN> <Title>.md`, e.g. `PRJ-001 SSO Integration.md`). `case_prefix` is declared in `AGENTS.md`.
- **`Bookmarks <X>.md`** sits at project root (navigation utility, not a review-gated KB fact). `inbox/` holds unclassified drops until triaged.
- **`knowledge/kb/` stays flat** (`scope: domain | solution`); `KB Log <X>.md` logs changes. No `kb/index.md` — `+<X>.md` navigates KB and cases.

## Folders, Types, and Status Matrix

All notes carry `description`, `type`, `status`, `updated`, `tags` (`project/<x>`), and `topics:`. Root hubs, `knowledge/` notes, and `cases/` notes set `topics: ["[[+<X>]]"]`. Case-bound notes (`activities/`, `artifacts/`, `product/`) set `topics: ["[[<CASE-ID> <Case Title>]]"]` only (omitting `[[+<X>]]`, since the case note acts as their local MoC and already links up to `+<X>.md`), while scalar `case_id:` stays short and fast for SQL queries. Schema values are English; titles, headings, and prose follow the language declared in `AGENTS.md`.

### Timeless Knowledge (`knowledge/` — no `case_id` prefix)

| Folder | `type:` | Additional required properties | Allowed `status:` | Mutability & trust |
|---|---|---|---|---|
| `knowledge/raw/` | `document`, `transcript` | `created`, `source` (path/URL/prose), `sha256` (when known) | `raw` | Immutable (`YYYY-MM-DD <Title>.md`); may contain unverified claims |
| `knowledge/distilled/` | `meeting`, `research`, `analysis` | `as_of`, `sources` (list of evidence wikilinks) | `current`, `superseded` (`superseded_by` required) | Updated when source is re-read |
| `knowledge/kb/` | `fact` | `scope` (`domain` \| `solution`), `as_of`, `sources` (list), `reviewed_on` (when `reviewed`) | `draft`, `reviewed`, `stale`, `disputed`, `superseded` (`superseded_by` required) | Current state only (history in `KB Log <X>.md`); high trust only when `reviewed` |

### Case Wrapper (`cases/`, `activities/`, `artifacts/` — scalar `case_id` required)

| Folder | `type:` | Filename pattern | Additional required properties | Allowed `status:` |
|---|---|---|---|---|
| `cases/` | `case` | `<CASE-ID> <Title>.md` | `case_id`, `case_kind` (`simple` \| `complex`) | `open`, `active`, `done`, `rejected` |
| `activities/raw/` | `document`, `transcript` | `YYYY-MM-DD <Title>.md` | `case_id`, `created`, `source` | `raw` |
| `activities/` | `meeting`, `correspondence`, `note`, `analysis` | `YYYY-MM-DD <Title>.md` | `case_id`, `sources` (optional for oral `note`) | `current`, `superseded` (`superseded_by` required) |
| `artifacts/` | `artifact` | `<CASE-ID> <Title>.md` | `case_id`, `reviewed_on` (when `reviewed`) | `draft`, `reviewed`, `final`, `superseded` |

### Product Chain (`product/` — for `complex` cases; scalar relations only)

```text
requirement  1 ──── n  concept  n ──── 1  evaluation  1 ──── 1  spec
```

All product relations in frontmatter are **one-directional scalar wikilinks** (child → parent) for GlueSQL compatibility — never YAML wikilink arrays.

| `type:` | Filename pattern | Scalar frontmatter properties | Allowed `status:` |
|---|---|---|---|
| `requirement` | `<CASE-ID> REQ <Title>.md` | `case_id`, `origin` (`feature` \| `problem` \| `compliance` \| `initiative`) | `open`, `active`, `done`, `rejected` |
| `concept` | `<CASE-ID> CON-a <Title>.md` | `case_id`, `requirement` | `draft`, `evaluated` |
| `evaluation` | `<CASE-ID> EVA <Title>.md` *(rev: `EVA-r2`)* | `case_id`, `requirement`, `chosen` (concept or empty), `decided_on` (when `decided`), optional `supersedes`, `superseded_by` | `draft`, `decided`, `superseded` |
| `spec` | `<CASE-ID> SPEC <Title>.md` *(rev: `SPEC-r2`)* | `case_id`, `concept`, `evaluation`, `reviewed_on` (when `reviewed`), optional `implementation_status` (`planned` \| `in-progress` \| `implemented`), optional `ticket` | `draft`, `reviewed`, `active`, `stale` |

## Hard Rules

1. **Human review gate:** Agent-created or agent-updated `fact` notes always land as `status: draft` — even when updating a `reviewed` note. Only explicit user approval sets `status: reviewed` + `reviewed_on:`. Likewise, `evaluation` becomes `decided` only after the decision, and `spec`/`artifact` become `reviewed` only after human check.
2. **Current-state body:** `fact`, `concept`, and `spec` hold current state only; replace obsolete claims in place and log `kb/` changes in `KB Log <X>.md`.
3. **Hand-maintained case log + completeness check:** `## Log` in a case note is a human-readable dated bullet list (never auto-generated). Check via SQL (`WHERE case_id = '<ID>'`) that every file with that `case_id` is linked in the case note and alert the user if any is missing.
4. **Self-contained deliverables (`artifacts/`):** Keep `<CASE-ID>` in the filename, **never** in the body H1 title. Do **not** put internal wikilinks in an artifact's body so it can be exported to PDF or pasted into an email cleanly — record provenance in frontmatter (`sources:`, `topics:`, `case_id:`).
5. **One fact, one place:** Never duplicate chosen/rejected state on `concept` (read from active `evaluation.chosen`). Never use YAML wikilink arrays for product relations.
6. **Every product decision has an evaluation:** Even a single-concept complex case goes through an `evaluation` so review and rationale are documented uniformly.
7. **Cascade & feedback:** Superseded `distilled/` → dependent `fact` becomes `stale`; superseded `evaluation` → its `spec` becomes `stale`. When a case completes (`spec.implementation_status: implemented` or simple-case exit criteria met), flag affected `knowledge/kb/` facts as `draft` and move the case to Completed Cases in `+<X>.md` (no `closed/` folder).
8. **Archive isolation:** Always pass `exclude_paths: ["archive/"]` in TurboVault `search`; read `archive/` only on explicit user request. Zero active notes may link into `archive/` (`KB Log` and `Chronology` may name archived notes in plain text).

## Workflows

Load only the reference matching the current task:

| Task | Reference |
|---|---|
| Set up a new `product-project` or adopt an existing one | `references/init-project.md` |
| Triage `inbox/` and compile timeless `knowledge/` (`raw → distilled → fact`) | `references/ingest-and-compile.md` |
| Run `simple` / `complex` cases, `activities/`, `artifacts/`, and log completeness checks | `references/case-workflow.md` |
| Work the `requirement → concept → evaluation → spec` chain & revisions | `references/product-chain.md` |
| Manage transition phase, archiving, and incoming-link cleanup | `references/archive-and-revise.md` |

Templates live in `assets/`. Read the matching template before creating a note.

## Validation (TurboVault First)

Run `mcp__turbovault__query_frontmatter_sql` scoped to `projects/<x>/` (`WHERE path LIKE 'projects/<x>/%'`) and `mcp__turbovault__graph_report`:

- **Case completeness:** `SELECT path, type, status FROM files WHERE case_id = '<ID>'` vs. `get_links(case_path, direction='outgoing')`.
- **Missing `case_id`:** notes under `activities/`, `artifacts/`, or `product/` where `(case_id IS NULL OR case_id = '')`.
- **Review & decision gates:** `status = 'reviewed' AND (reviewed_on IS NULL OR reviewed_on = '')`; `type = 'evaluation' AND status = 'decided' AND (decided_on IS NULL OR decided_on = '')`; `status = 'superseded' AND (superseded_by IS NULL OR superseded_by = '')`.
- **Mandatory scalar relations:** `type IN ('concept', 'evaluation') AND (requirement IS NULL OR requirement = '')`; `type = 'spec' AND (concept IS NULL OR concept = '' OR evaluation IS NULL OR evaluation = '')`.
- **Enum hygiene:** `fact.scope`, `requirement.origin`, `case.case_kind`, `spec.implementation_status`.
- **Graph health:** `graph_report(kind="broken_links")` and `graph_report(kind="isolated_clusters")`.

## Pitfalls

- Do not put case-specific meetings or investigations in `knowledge/distilled/` — they belong in `activities/` with `case_id:`.
- Do not write YAML wikilink arrays for product relations (`concepts:`, `evaluations:`) — GlueSQL cannot query them and bidirectional arrays drift.
- Do not move completed (`done`) cases into a `closed/` folder — keep them in `cases/` and separate Active vs. Completed in `+<X>.md`.
- Do not use Markdown checkboxes (`- [ ]`) for Acceptance Criteria in case notes — the Obsidian Tasks plugin treats them as personal tasks; use a numbered list (`1.`, `2.`, …) instead.
- Do not mix `scope` (`fact`) and `origin` (`requirement`), and do not copy compliance deliverables across a `cs-project` boundary.

## Verification

- Project `AGENTS.md` was read and declares `Projekttyp: product-project`, `Containertyp: vault`, `case_prefix`, and language.
- Timeless knowledge has no `case_id` prefix; every file under `cases/`, `activities/`, `artifacts/`, `product/` carries `case_id:` and is linked in its case note.
- Agent-edited `fact` notes remain `status: draft` until explicitly approved; `KB Log <X>.md` records `kb/` changes.
- TurboVault SQL checks and `graph_report(kind="broken_links")` are clean for the touched scope; no active note links into `archive/`.
