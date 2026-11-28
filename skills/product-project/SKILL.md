---
name: product-project
description: "Use when running a product-project: KB, cases & product."
version: "0.3.1"
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

A vault project kind separating **Project Knowledge** (`knowledge/raw → distilled → kb` + `masterdata/`) from **Case Knowledge** (`cases/`, `activities/`, `artifacts/`, `product/`), guarded by calibrated review gates, unified body `## Citations` / `## Quellen`, two-tier epistemic verification, and 100% TurboVault-native lint.

Project setup and Projektform belong to `hermes-projects`; generic note mechanics belong to `vault-ops`; TurboVault calls belong to `turbovault-use`. **Projekttyp `product-project`, Containertyp `vault`** under `projects/<x>/`. Always read the project's `AGENTS.md` on entry (`case_prefix`, language, external links, optional gates/promotion rules).

## When to Use

- Initialize or adopt a `product-project`, or onboard sparse Project Knowledge (`grill-me`)
- Triage `inbox/`, maintain `knowledge/masterdata/`, or compile `raw → distilled → kb` (`fact`)
- Open, log, promote mid-case, or close a `simple` or `complex` case (`<CASE-ID>`)
- Work the `product/` chain (`requirement → concept → evaluation → spec`), revisions, or delivery
- Run Tier-1/Tier-2 epistemic verification, TurboVault-native lint, or archive retired chains

## Directory Structure

```text
projects/<x>/
├── +<X>.md                # type: moc — entry hub (Project Knowledge + Master Data + Cases)
├── AGENTS.md              # project manual (Projekttyp, Containertyp, case_prefix, language)
├── Tasks <X>.md           # type: utility — single tasks query scoped to projects/<x>/
├── Chronology <X>.md      # type: utility — project milestones
├── Bookmarks <X>.md       # type: bookmarks — curated external links (optional)
├── inbox/                 # unclassified drops (no required frontmatter)
├── knowledge/             # Project Knowledge — timeless state (NO case_id)
│   ├── raw/               # immutable primary inputs (YYYY-MM-DD <Title>.md)
│   ├── distilled/         # timeless extracts, research & analyses
│   ├── kb/                # atomic curated facts (type: fact) + KB Log <X>.md
│   └── masterdata/        # user-owned lookup data (type: masterdata; no status/checkboxes)
├── cases/                 # Case Knowledge — one flat file per case (<CASE-ID> <Title>.md)
├── activities/            # Case Knowledge — case-bound work (scalar case_id required)
│   ├── raw/               # immutable originals (YYYY-MM-DD <Title>.md, NO <CASE-ID> prefix)
│   └── ...                # case extracts, research, analyses, notes (<CASE-ID> YYYY-MM-DD <Title>.md)
├── artifacts/             # Case Knowledge — deliverables (<CASE-ID> <Title>.md)
├── product/               # Case Knowledge — complex-case chain (<CASE-ID> REQ/CON/EVA/SPEC ...)
└── archive/               # retired/rejected items; excluded from normal retrieval
```

## Folders, Types, and Status Matrix

All managed notes carry `description`, `type`, `updated`, `tags` (`project/<x>`), and `topics:`. Hubs, `knowledge/`, and `cases/` set `topics: ["[[+<X>]]"]`; all case-bound notes (`activities/raw/`, `activities/`, `artifacts/`, `product/`) carry scalar `case_id` and `topics: ["[[<CASE-ID> <Case Title>]]"]`. Provenance lives in body `## Citations` / `## Quellen` (not frontmatter); only `raw/` keeps scalar `source:`.

### Project Knowledge (`knowledge/` — NO `case_id`)

| Folder | `type:` | Filename pattern | Additional properties | Allowed `status:` |
|---|---|---|---|---|
| `knowledge/raw/` | `document`, `transcript` | `YYYY-MM-DD <Title>.md` | `created`, scalar `source`, opt `sha256` | `raw`, `incomplete` |
| `knowledge/distilled/` | `extract`, `research`, `analysis` | `YYYY-MM-DD <Title>.md` *(or `<Title>.md`)* | `as_of`, opt `superseded_by` | `current`, `superseded` |
| `knowledge/kb/` | `fact` | `<Title>.md` | `scope` (`domain` \| `solution`), `as_of`, `reviewed_on`, opt `superseded_by` | `draft`, `reviewed`, `stale`, `disputed`, `superseded` |
| `knowledge/masterdata/` | `masterdata` | `<Title>.md` | `class` (`people` \| `system` \| `schedule` \| `glossary`) | *(omit `status:`)* |

### Case Knowledge (`cases/`, `activities/`, `artifacts/` — scalar `case_id` required)

| Folder | `type:` | Filename pattern | Additional properties | Allowed `status:` |
|---|---|---|---|---|
| `cases/` | `case` | `<CASE-ID> <Title>.md` | `case_id`, `case_kind` (`simple` \| `complex`) | `open`, `active`, `done`, `rejected` |
| `activities/raw/` | `document`, `transcript` | `YYYY-MM-DD <Title>.md` | `case_id`, `created`, scalar `source`, opt `sha256` | `raw` |
| `activities/` | `extract`, `research`, `analysis`, `note` | `<CASE-ID> YYYY-MM-DD <Title>.md` | `case_id`, opt `superseded_by` | `current`, `superseded` |
| `artifacts/` | `artifact` | `<CASE-ID> <Title>.md` | `case_id`, `reviewed_on`, opt `superseded_by` | `draft`, `reviewed`, `final`, `superseded` |

### Product Chain (`product/` — `complex` cases; unidirectional scalar wikilinks only)

```text
requirement  1 ──── n  concept  n ──── 1  evaluation  1 ──── 1  spec
```

| `type:` | Filename pattern | Scalar frontmatter properties | Allowed `status:` |
|---|---|---|---|
| `requirement` | `<CASE-ID> REQ <Title>.md` | `case_id`, `origin` (`feature` \| `problem` \| `compliance` \| `initiative`) | `open`, `active`, `done`, `rejected` |
| `concept` | `<CASE-ID> CON-a <Title>.md` | `case_id`, `requirement` | `draft`, `evaluated` |
| `evaluation` | `<CASE-ID> EVA <Title>.md` *(rev: `EVA-r2`)* | `case_id`, `requirement`, `chosen`, `decided_on`, opt `supersedes`, `superseded_by` | `draft`, `decided`, `superseded` |
| `spec` | `<CASE-ID> SPEC <Title>.md` *(rev: `SPEC-r2`)* | `case_id`, `concept`, `evaluation`, `reviewed_on`, opt `implementation_status` (`planned` \| `in-progress` \| `implemented`), `ticket` | `draft`, `reviewed`, `active`, `stale` |

## Hard Rules

1. **Calibrated review gate:** Substantive agent edits to `fact` notes set `status: draft` and clear `reviewed_on:`; only user approval sets `reviewed` + `reviewed_on:`. **Exception:** pure additive citation confirmation (appending to `## Citations` / `## Quellen` + bumping `as_of:` with zero body change) preserves `reviewed` and `reviewed_on:`. `evaluation` → `decided` and `spec`/`artifact` → `reviewed` require human check.
2. **Topic-first current-state body & conflict handling:** Cut `kb/fact` notes by **topic/concept/component** (never 1:1 source summaries), cross-link related `kb/fact` and `masterdata/` notes horizontally, keep `fact`/`concept`/`spec` at current state only, and log `kb/` changes in `KB Log <X>.md`. Never silently overwrite a `reviewed` fact on contradiction — set `status: disputed` with a conflict callout and surface to the user.
3. **Unified `## Citations` / `## Quellen` provenance:** List sources in body `## Citations` / `## Quellen` via `[[Wikilinks]]` (or `[Title](url)` for external URLs). Large/multi-section raw sources require section, timestamp, or short verbatim quote anchors.
4. **Primary-evidence verification:** Trace critical facts, figures, dates, and legal/compliance citations back to `raw/` or the authoritative primary source; run Tier-2 grounding checks before `draft → reviewed`. Never apply an Exhaustion Rule (`null` stays `null`, never `false`).
5. **Originals stay put & brake on note inflation:** Never edit `raw/` originals (except appending a complete newer email thread export) and never move `activities/raw/` on case close. Routine two-line emails earn a single bullet in `cases/<ID>.md` `## Log`, not a separate `activities/` note.
6. **Master data belong to the user:** Cite `knowledge/masterdata/` by `[[Wikilink]]`; never copy lookup values into prose or overwrite them unasked. Keep zero checkboxes and no history in `masterdata/`.
7. **Hand-maintained case log + completeness check:** Never auto-overwrite `## Log`; verify via scoped SQL (`WHERE case_id = '<ID>'`) vs. `get_links(case_path, direction="outgoing")`. Keep an assessment or coordination case `simple` unless its work requires the product chain; a leftover legacy requirement is not evidence that the case is unfinished or must become `complex`. Remove an approved redundant requirement only after preserving unique constraints and repairing incoming links.
8. **One fact, one place & scalar product relations:** Never duplicate chosen/rejected state on `concept` (read `evaluation.chosen`); never use YAML wikilink arrays for `product/` relations.
9. **Universal evaluation & realized-state KB feedback:** Even single-concept complex cases go through `evaluation`. Update `scope: solution` facts only for realized state (`spec.implementation_status: implemented` or verified current behavior), never unimplemented planned specs.
10. **Archive isolation:** Pass `exclude_paths: ["archive/"]` to TurboVault `search` AND `AND path NOT LIKE 'projects/<x>/archive/%'` in every SQL query. Zero active notes may link into `archive/`.

## Workflows

| Task | Reference |
|---|---|
| Set up, adopt, assess version migration, integrate, or onboard Project Knowledge (`grill-me`) | `references/init-project.md` |
| Triage `inbox/`, manage `masterdata/`, distill `raw → distilled`, 4-way Delta-Compile | `references/ingest-and-compile.md` |
| Run `simple`/`complex` cases, `activities/`, `artifacts/`, `Promote to KB`, and close | `references/case-workflow.md` |
| Work `REQ → CON → EVA → SPEC`, revisions, and implemented-state feedback | `references/product-chain.md` |
| Manage transition phase, archiving, and incoming-link cleanup | `references/archive-and-revise.md` |
| Run Tier-1/Tier-2 epistemic verification & 100% TurboVault-native Lint | `references/verify-and-lint.md` |

Templates live in `assets/`. Read the matching template before creating a note.

## Validation (TurboVault First)

Every `query_frontmatter_sql` query scopes to `WHERE path LIKE 'projects/<x>/%' AND path NOT LIKE 'projects/<x>/archive/%'` (full checklist in `references/verify-and-lint.md`):

- **Case completeness & `case_id`:** Check all 5 Case Knowledge folders for missing `case_id`; compare `WHERE case_id = '<ID>'` vs. `get_links(case_path, direction="outgoing")`.
- **Gates & scalar relations:** Check missing `reviewed_on`, `decided_on`, `superseded_by`, `concept`/`evaluation.requirement`, `spec.concept`/`spec.evaluation`, and enum hygiene (`fact.scope`, `requirement.origin`, `case.case_kind`, `spec.implementation_status`, `masterdata.class`).
- **`masterdata/`, MoC & cascades:** Confirm `masterdata` has no `status` and `query_tasks` returns zero checkboxes; verify every active `kb/fact` & `masterdata` note is linked from `+<X>.md` and cross-linked horizontally; run `get_links(superseded_path, direction="incoming")` for `→ stale` cascades and `get_links(raw_path, direction="incoming")` to spot unprocessed `raw/` notes.
- **Graph & archive:** `graph_report(kind="broken_links")`, `graph_report(kind="isolated_clusters")`, and zero incoming links into `archive/`.

## Pitfalls

- Treat migration assessment as read-only: distinguish mandatory schema changes, unresolved evidence, and optional content improvements; do not infer the project's original skill version from legacy formatting alone. Use the migration procedure in `references/init-project.md` before proposing moves or deletions.
- Do not put case meetings or investigations in `knowledge/distilled/` — route them to `activities/` with `case_id:`.
- Do not add frontmatter source arrays or invent unlisted activity types — use the matrix types and body `## Citations` / `## Quellen` only.
- Do not move `done` cases or `activities/raw/` originals on close, and do not use `- [ ]` checkboxes for Acceptance Criteria (`1.`, `2.` instead).
- Do not create custom Python lint scripts or external epistemic stores — validation is 100% TurboVault-native (`references/verify-and-lint.md`).

## Verification

- Project `AGENTS.md` read (`Projekttyp: product-project`, `Containertyp: vault`, `case_prefix`, language, optional overrides).
- Project Knowledge (`knowledge/`) has no `case_id`; all 5 Case Knowledge folders carry `case_id:` and link from their case note.
- Substantive agent edits to `fact` notes stay `status: draft` until approved; `KB Log <X>.md` logs changes and Tier-2 verification.
- TurboVault-native lint, grounding checks, and `graph_report(kind="broken_links")` pass with zero archive leakage.
