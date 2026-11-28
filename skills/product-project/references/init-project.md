# Initialize or Adopt a `product-project`

Use this reference when creating a new `product-project` under `projects/<x>/`, adopting an existing vault project onto this kind, or onboarding sparse **Project Knowledge**.

## 1. Set Up a New `product-project`

1. Confirm the active vault and target path `projects/<x>/` via `turbovault-use` (`list_vaults`, `get_vault_context`). Read the vault root `AGENTS.md`.
2. Verify that the vault root `AGENTS.md` allows a Projektskill to define project-local `type:` values. If not, note the needed amendment for the user rather than editing root `AGENTS.md` silently.
3. Choose the project's `case_prefix` (e.g. `PRJ`) and documentation language (per vault language policy).
4. Create the root files from `assets/`:
   - `projects/<x>/AGENTS.md` from `assets/project-AGENTS.md` — declare `Projektform: vault`, `Projekttyp: product-project`, `Containertyp: vault`, `case_prefix`, language, external links, and optional project-specific promotion/verification gates.
   - `projects/<x>/+<X>.md` from `assets/template-moc.md` — entry MoC with Project Knowledge (`domain`, `solution`, `masterdata`) and Cases (Active / Completed).
   - `projects/<x>/Tasks <X>.md` (or `Aufgaben <X>.md`) from `assets/template-utility.md` — single `tasks` query block scoped to `projects/<x>/`.
   - `projects/<x>/Chronology <X>.md` (or `Chronologie <X>.md`) from `assets/template-utility.md` — milestone log.
   - `projects/<x>/Bookmarks <X>.md` (`type: bookmarks`, optional) — curated external links (sits at root, not in `knowledge/kb/`).
5. Create `projects/<x>/knowledge/kb/KB Log <X>.md` (`type: utility`).
6. Create subfolders lazily as notes enter (`inbox/`, `knowledge/{raw,distilled,kb,masterdata}/`, `cases/`, `activities/raw/`, `activities/`, `artifacts/`, `product/`, `archive/`), or scaffold them upfront on explicit request.
7. Register `projects/<x>/+<X>.md` in `projects/INDEX.md` and bump its `updated:` date.
8. Read back `AGENTS.md` and `+<X>.md` and verify with `graph_report(kind="broken_links")`.

## 2. Adopt an Existing Project

Follow `hermes-projects` adoption rules — never bulk-migrate existing notes without explicit approval:

1. Inventory existing notes with `query_frontmatter_sql`:
   ```sql
   SELECT path, type, status FROM files
   WHERE path LIKE 'projects/<x>/%'
     AND path NOT LIKE 'projects/<x>/archive/%'
   ORDER BY path
   ```
2. Classify each note into **Project Knowledge** (`knowledge/raw/`, `knowledge/distilled/`, `knowledge/kb/`, `knowledge/masterdata/`), **Case Knowledge** (`cases/`, `activities/raw/`, `activities/`, `artifacts/`, `product/`), **root hubs** (`Bookmarks`, `Tasks`, `Chronology`), or `inbox/` (e.g. items belonging in another vault/project).
3. Present the read-only mapping table and wait for user confirmation.
4. Write `AGENTS.md` declaring `Projekttyp: product-project`, `Containertyp: vault`, and `case_prefix`.
5. Migrate approved notes via TurboVault (`move_note`, `update_frontmatter`, `edit_note`), update `+<X>.md`, and verify zero new broken links.

### Assess Migration to a New Skill Version (Read-Only)

1. Read the current `SKILL.md`, affected workflow references, and matching templates alongside the project's `AGENTS.md`. If skill Git history is available, inspect the relevant release delta; label an unrecorded project baseline as unknown rather than deriving a version from old formatting.
2. Inventory active notes using the scoped SQL above, then read representative bodies and every suspected exception. Compare folder/type/status, filenames, scalar relations, body citations, review gates, and navigation against the current contract. A clean graph proves link resolution, not schema conformity or factual grounding.
3. For each active case, compare all scoped `case_id` rows against outgoing case links. Separately check that notes in `product/` belong to a `complex` case and that chain targets have the required types; an artifact linked under a “Concepts” heading does not become a `concept`. Present promotion versus retaining a simple assessment as an ownership/scope decision, not an automatic conversion.
4. Build an exact old-path → proposed-path mapping from the current filename matrix and templates. Preserve existing identifiers in the inventory, but flag their mismatch explicitly; do not invent a hybrid naming pattern that retains a legacy sequence where the current schema specifies `REQ`. Plan link-aware TurboVault moves and read-back verification of inbound links, case logs, and hubs.
5. Trace conflicting dates and unsupported critical claims to raw or authoritative evidence. Distinguish an obvious typographical defect from an unresolved event date; leave the latter open rather than selecting the filename or a majority of repeated secondary claims. Apply an explicit user date correction consistently to filename, body, citations, case log, and hub links. Moving `sources:` into body citations does not validate the claims they accompany. During mechanical migration, preserve substantive wording and uncertainty qualifiers; do not turn possible propagation into confirmed exposure, absence of observed misuse into proof of no leakage, or a conditional risk assessment into an accepted decision.
6. Inspect root utilities and scratch notes for duplicated tasks or content. Recommend cleanup separately; check incoming links before proposing deletion and do not erase unique content. Treat masterdata extraction, topic-first KB compilation, and substantive grounding remediation as optional content work requiring their own approved scope, not prerequisites for mechanical schema migration.
7. Report a compact summary followed by three groups: **mandatory conformity changes**, **decisions/evidence gaps**, and **optional improvements**. Give exact affected paths and the necessary decisions. Do not ask permission for already-authorized low-risk inspection, and do not perform migration writes when only an assessment was requested.
8. Define verification before approval: rerun scoped schema/gate checks, case completeness, task checks, and graph checks after the approved moves. For vault-wide paginated graph results, consume every page before filtering to the project and asserting zero project findings; a page without project hits is not proof of a clean project. Report structural conformity separately from grounding and human review status.

## 3. External Integration (e.g. with a `cs-project`)

When a `cs-project` references a `product-project` as an external knowledge source:

- Declare the `product-project` vault name and subtree in the `cs-project`'s `AGENTS.md` as **read-only** unless explicitly requested.
- Ownership split:
  - `product-project` owns **Project Knowledge** (`knowledge/kb/`, `knowledge/masterdata/`), operational **Case Knowledge** (`cases/`, `activities/`, `artifacts/`), and product/security design chains (`product/`).
  - `cs-project` (`repos/`, `csl/`) owns source code evidence and formal compliance/security deliverables managed by that companion project.
- Reference across the boundary by link or identifier; never mirror content in both places.

## 4. Project Knowledge Onboarding (New / Early-Stage Projects)

When starting a project with sparse documentation:

1. Run a structured user interview using the `grill-me` skill covering: product/solution purpose, core domain rules & constraints, key people/systems/schedules/glossary (`knowledge/masterdata/`), and current solution state.
2. Optionally scan any initial baseline documents placed in `knowledge/raw/`.
3. Create initial user-confirmed lookup notes in `knowledge/masterdata/` (`class: people | system | schedule | glossary`; omit `status:`).
4. Record the onboarding interview synthesis in `knowledge/distilled/` (`type: extract` or `research`, `status: current`, `as_of: YYYY-MM-DD`) with `## Citations` / `## Quellen`.
5. Compile initial atomic `knowledge/kb/` `fact` notes (`scope: domain` and `scope: solution`) as `status: draft`, run the pre-review grounding check (`references/verify-and-lint.md`), log in `KB Log <X>.md`, and present to the user for review (`status: reviewed` + `reviewed_on:`).
