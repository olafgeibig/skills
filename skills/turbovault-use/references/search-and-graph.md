# Search, Metadata, Graph, and Structured Reads

Covers every read-only discovery, query, analysis, and structured-format tool in TurboVault 4.x. For the opt-in semantic plugin see `references/vector-search.md`; for mutations see `references/editing-and-mutations.md`.

## Choose the right discovery tool

| Need | Tool | Notes |
|---|---|---|
| Full-text / filtered search | `search` | Tantivy BM25 (`query`, `tags`, `frontmatter_filters`, `exclude_paths`, `related_to`). Omit `query` (or pass `"*"`) for filter-only listing; default `limit` is 10, so raise `limit` or page via `next_offset` for full coverage. |
| Single frontmatter condition | `query_metadata` | Simple condition (`status: "draft"`, `tags: contains("work")`, `priority > 3`); returns each match's frontmatter. |
| Multi-condition / aggregate / exact enumeration | `query_frontmatter_sql` (advanced) | GlueSQL over `files`, `tags`, `links`. Run `inspect_frontmatter` first to see exact column names and types. |
| Batch existence, frontmatter keys & tags | `get_notes_info` | Missing frontmatter keys return `null`. With `include_tags: true`, `tags` is an object `{frontmatter_tags, inline_tags, all_tags}`, not a flat list. |
| Lexical similarity (built-in TF-IDF) | `find_similar` | Takes either `query` (topic) or `path` (look-alike notes). Separate from the opt-in `vector_search` plugin. |
| Near-duplicates / pair comparison / link ideas | `find_duplicates`, `compare_notes`, `suggest_links` (advanced) | `compare_notes` returns both content similarity and `link_strength`. |
| Vault orientation & health | `get_vault_context`, `explain_vault`, `vault_health(depth)` | `explain_vault` summarizes counts, folders, hubs, and dead ends in one call. |
| Content & Obsidian 1.9+ validation | `validate_vault` | Checks unparsable frontmatter, pre-1.9 scalar/singular `tags`/`aliases`/`cssclasses`, and broken links (unreleased post-4.1.0 builds also list skipped non-UTF-8 / unparsable files). |

- **Concise mode:** Pass `response_format: "concise"` to `search`, `explain_vault`, or `get_vault_context` during broad discovery to omit verbose fields (`preview`, `outgoing_links`, `word_count`, folder trees, tool catalogs).
- **Paging:** List tools default to 50 items (10 for `search`, `find_similar`, `graph_report(kind="hubs")`) and return `meta.pagination` (`total`, `returned`, `truncated`, `next_offset`). Any vault-wide count or audit must loop on `next_offset`.
- **Retrieval is not enumeration:** Do not send `field:value` expressions to full-text `search` (`query` uses Tantivy syntax like `title:word`, not arbitrary frontmatter keys). For complete enumerations, query `files` with `query_frontmatter_sql` and reconcile against `get_vault_context` totals.

## Frontmatter SQL (`query_frontmatter_sql`)

Read-only GlueSQL over three auto-populated tables: `files` (schemaless: `path` + all frontmatter keys), `tags (path, tag)`, and `links (source, target, link_type, is_valid)`. Capped at 1,000 rows and 10 seconds per query.

```sql
SELECT path, type, status
FROM files
WHERE type = 'moc'
ORDER BY path
LIMIT 50
```

Known GlueSQL and TurboVault limits:

- **No SQLite extensions:** Do not assume `json_each()` or complex SQLite functions work. Quote frontmatter keys containing dashes or spaces in double quotes.
- **NULL breaks `LIKE` and string functions:** Optional frontmatter keys are `NULL` on notes without them, causing `Null LIKE Str(...)` to abort the query. Guard with `coalesce(col, '') LIKE '%x%'` (same for `lower()`). `WHERE col IS NOT NULL` works cleanly.
- **`LIKE` fails on list-valued columns:** `coalesce` does not coerce lists to strings. For array-valued fields, filter candidates with `search(frontmatter_filters: [{key, value}])` and inspect the notes directly, or query the unnested `tags` table for tags.
- **`CASE` alias in `ORDER BY` can be ignored:** Repeat the `CASE` expression directly in `ORDER BY` instead of sorting by its `SELECT` alias, and verify ranking order when it matters.
- **`links` table omits unresolvable targets:** `populate_links` loads resolved graph edges only (`all_links()`), not `unresolved_links`, so broken links do not appear in `SELECT ... FROM links`. Use `graph_report(kind: "broken_links")` for dangling links and a raw-text search for plain-text mentions.
- **`links.link_type` is syntactic, not field-typed:** It records `WikiLink`, `MarkdownLink`, or `HeadingRef` — never which frontmatter property held the link. Wikilinks inside list-valued frontmatter fields *do* create graph edges; to filter by frontmatter field, start from `get_links` and inspect each candidate's frontmatter.

## YAML-invalid frontmatter

An unquoted `: ` inside a YAML scalar invalidates the entire frontmatter block. Obsidian may still render it, but TurboVault treats its fields as missing (`NULL` in SQL, `null` in `get_notes_info`, while `has_frontmatter` remains `true`) and `update_frontmatter` fails with a YAML mapping error. Use `validate_vault` to locate unparsable frontmatter, fix the YAML quoting, and confirm visibility via `query_frontmatter_sql` or `get_notes_info`.

## Graph tools and link resolution

| Goal | Tool |
|---|---|
| Inbound links (notes + canvases) | `get_links(path)` (`direction` defaults to `"incoming"`) |
| Outbound resolved links | `get_links(path, direction: "outgoing")` |
| Multi-hop neighborhood | `get_related_notes(path, max_hops)` |
| Graph diagnostics | `graph_report(kind)` — `hubs`, `centrality`, `dead_ends`, `isolated_clusters`, `cycles`, `broken_links` |

- **Link resolution in 4.x:** `LinkGraph` resolves links case-insensitively by bare file stem first, then alias, then path suffix (ignoring `.md` and `#fragment`); 4.1.0+ also resolves relative `./` and `../` links from the source note's folder first and normalizes case/Unicode differences on macOS/Windows. When multiple notes share a basename, TurboVault prefers the shortest path — use vault-relative path wikilinks (`[[folder/note|Alias]]`) whenever disambiguation is required.
- **Hub flattening:** In hub-heavy vaults, `get_related_notes` with `max_hops >= 2` quickly fans out through index/MoC hubs; treat hop distance as navigation, not relevance.
- **Escaped pipes in tables:** `[[target\|alias]]` is valid OFM table escaping; do not split on raw `|` when parsing links externally.
- **Reconciliation freshness:** TurboVault reconciles external edits before derived reads when `reconcile_external_changes: true` (subject to a short debounce and mtime/size detection — tools that preserve mtime without changing size can hide edits). Do not assume `read_note` success proves graph freshness; verify with `get_links` in both directions if results disagree.

## Tasks, Canvases, Bases, Periodic Notes, and Validation

- **`query_tasks`:** Parses Markdown checkboxes across the vault, including Tasks plugin emoji (`📅`, `⏳`, `🛫`, `✅`, priority icons) and Dataview inline fields (`[due:: YYYY-MM-DD]`).
  - `status` is a **JSON array** of strings (e.g. `status: ["todo"]` — passing a bare string returns invalid-params `-32602`): valid items are `todo` (`[ ]`), `done` (`[x]`/`[X]`), `in_progress` (`[/]`), `cancelled` (`[-]`), `other` (custom checkbox characters; note that unparsed non-standard forms may require regex fallback). Never pass `"open"`. `priority` is likewise an array (`["highest", "high", "medium", "normal", "low", "lowest"]`).
  - Supports `due_before`/`due_after`, `scheduled_before`/`scheduled_after`, `tag`, `path` (note or folder), `priority`, `text`, and paging. Prefer `query_tasks` over full-text search for task queries.
- **Canvases (`read_canvas`, `write_canvas`):** JSON Canvas 1.0. `read_canvas` returns nodes, edges, linked notes, and a `hash` (only when all nodes fit without paging) for `write_canvas(expected_hash)`.
- **Bases (`query_base`):** Evaluates an Obsidian `.base` file's filters, formulas, sort, grouping, and limit for a chosen `view`. Unsupported Bases functions are refused by name.
- **Periodic notes (`get_periodic_note`):** Finds or creates (`create: true`) `daily`, `weekly`, `monthly`, `quarterly`, or `yearly` notes using the vault's Daily Notes / Periodic Notes plugin settings.
- **`validate_vault` vs. `vault_health`:**
  - `validate_vault` accepts a single note `path` or omits `path` for the whole vault — passing a directory path fails with an I/O error.
  - Distinguish `passed: true` from zero warnings, and report `validate_vault` separately from `vault_health` / `graph_report(kind: "broken_links")`: zero validation errors does not prove zero broken links.
  - Triage warnings against the actual note text before editing; preserve valid Markdown (such as `[label](https://...)`) if a validator reports a false positive.
- **OKF tools (`okf_validate`, `generate_index`, `append_log_entry` — advanced):** Follow Open Knowledge Format (`index.md`, folder `log.md`). Use them only in OKF vaults so they do not collide with vaults using other index conventions.

## Verification after discovery

- Confirm every returned path belongs to the intended vault and scope.
- Read candidate notes before drawing conclusions from snippets or frontmatter alone.
- Report pagination truncation (`meta.pagination.truncated`) explicitly rather than implying complete coverage.
