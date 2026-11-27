# Archive and Retire (`archive/`)

Use this reference when superseding notes, archiving retired/rejected cases or chains, or cleaning up incoming links.

## 1. Transition Phase vs. Archival Trigger

| Situation | Action |
|---|---|
| Replacement is still in progress (`spec` not yet `active`, or old solution still running) | **Keep in active folder** (`knowledge/kb/`, `artifacts/`, or `product/`) with `status: superseded`, `superseded_by: "[[...]]"`, and a `> [!warning] Superseded by [[...]]` callout directly under H1. |
| Replacement is `active` / implemented | **Move superseded note(s) to `archive/`** via TurboVault `move_note`. |
| `case` (or `requirement`) is `rejected` | **Move to `archive/`** immediately together with its `activities/`, `artifacts/`, and `product/` notes (preserving decision rationale). |
| `case` is `done` (completed/implemented) or `activities/raw/` original | **Do NOT archive.** Keep files in place so `knowledge/kb/` `## Citations` / `## Quellen` links never break; move completed case entries in `+<X>.md` to Completed Cases. |

## 2. Hard Isolation Rules

1. **Search and SQL exclusion:** Always pass `exclude_paths: ["archive/"]` in `mcp__turbovault__search` during normal work, **and** include `AND path NOT LIKE 'projects/<x>/archive/%'` in every `query_frontmatter_sql` query over active notes. Only read or search `archive/` on explicit user request.
2. **Zero incoming links from active notes:** Before moving any note to `archive/`, inspect incoming links with `get_links(path, direction="incoming")`:
   - Repoint active working notes (`+<X>.md`, `knowledge/kb/`, active `cases/`, active `product/` notes) to the active successor — or remove the link if rejected.
   - Outgoing `superseded_by:` links *from* an archived note to its active successor are allowed for human traceability.
   - `KB Log <X>.md` and `Chronology <X>.md` may mention archived notes in plain text (no wikilinks) so historical records stay intact without violating graph isolation.
3. **Tagging:** Add the `archived` tag (per `vault-ops`) when moving a note into `archive/`.

## 3. Verification After Archiving

1. Run `get_links(archived_path, direction="incoming")` and confirm zero incoming links from outside `projects/<x>/archive/`.
2. Run `graph_report(kind="broken_links")` and confirm zero new broken links.
3. Record the archival in `KB Log <X>.md` (for facts) or `Chronology <X>.md` (for major cases/decisions).
