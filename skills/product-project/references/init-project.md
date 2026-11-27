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
