# Vault Navigation

Prefer TurboVault graph and metadata tools over filesystem scans. TurboVault already parses wikilinks, backlinks, frontmatter, tags, and graph structure.

Scope note: by default, exclude `wiki/` and `system/` from Vault Ops navigation/search unless the user explicitly asks for them. Use the `vault-wiki` skill for wiki maintenance.

Goal: follow the vault's intended navigation path (INDEX → MoC → notes) before falling back to global keyword search.

## 1) Start From The Routing INDEX

Default entry points:

- `INDEX.md` — vault root INDEX
- `area/INDEX.md` — areas
- `projects/INDEX.md` — projects
- `wiki/index.md` — wiki domains, maintained with `vault-wiki`

Workflow:

1. Read root `AGENTS.md` first.
2. Read the relevant INDEX note.
3. Use INDEX abstracts and `description` frontmatter to choose the relevant MoC.
4. Read or traverse that MoC before doing broad search.

## 2) Hybrid MoC Navigation

The vault uses two complementary directions.

### Note → Parent/Related MoCs

Use when you already have a note and need to understand where it belongs.

Preferred tools:

- If the note is already read, inspect its `topics` frontmatter directly.
- Otherwise use `mcp_turbovault_get_metadata_value(file, 'topics')` for a cheap lookup.
- For batch/reporting, use `mcp_turbovault_query_frontmatter_sql` against the `files` table.

Steps:

1. Read `topics` from frontmatter.
2. Extract `[[+MoC]]` entries.
3. Navigate directly to those MoCs.
4. If graph correctness matters, verify that the same MoCs also appear as body links in the note's `Topics:` section.

### MoC → Child Notes

Use when you have a MoC and need its curated or related notes.

Preferred tools:

1. `mcp_turbovault_get_forward_links(moc_path)` — curated links explicitly listed in the MoC.
2. `mcp_turbovault_get_backlinks(moc_path)` — notes that body-link back to the MoC.
3. `mcp_turbovault_get_related_notes(moc_path, max_hops=1..2)` — nearby graph context when exploring.
4. SQL against the `links` table for batch/reporting.

Interpretation:

- Forward links are the MoC author's curated navigation.
- Backlinks show notes that claim this MoC as parent/related context through real body wikilinks.
- `topics` frontmatter is useful for cheap parent lookup, but body links are the graph edge TurboVault can traverse.

## 3) Structured Metadata Queries

Use structured metadata queries when you know the property you need.

1. Inspect schema once per vault/session when writing SQL:
   - `mcp_turbovault_inspect_frontmatter`
2. Exact frontmatter lookup:
   - `mcp_turbovault_search_by_frontmatter(key, value)`
3. Single-note metadata lookup:
   - `mcp_turbovault_get_metadata_value(file, key)`
4. Reporting and filtering:
   - `mcp_turbovault_query_frontmatter_sql`

Useful SQL examples:

```sql
-- List MoCs
SELECT path, type, description FROM files WHERE type = 'moc' ORDER BY path LIMIT 50

-- Inspect topics for one note
SELECT path, topics FROM files WHERE path = 'projects/example/example-note.md'

-- Graph edges pointing to a MoC or note
SELECT source, target, link_type, is_valid FROM links WHERE target LIKE '%+Agents%' LIMIT 50

-- Forward edges from a MoC
SELECT source, target FROM links WHERE source = 'area/agents/+Agents.md' LIMIT 50
```

Caveat: do not assume arbitrary SQLite features. In the current tested TurboVault SQL engine, multi-table selects such as `files, json_each(topics)` are not supported. Prefer dedicated TurboVault tools for graph traversal and SQL only for simple filtered reports.

## 4) Keyword And Semantic Search

Use search when:

- the right MoC is unknown,
- you need a specific phrase,
- the INDEX/MoC path is incomplete,
- or you want to confirm coverage after graph traversal.

Tools:

- `mcp_turbovault_search(query)` — BM25 full-text search. Use 2–5 distinctive terms.
- `mcp_turbovault_advanced_search(...)` — full-text search with tags/frontmatter/path filters.
- `mcp_turbovault_semantic_search(query, limit)` — conceptual similarity search.
- `mcp_turbovault_recommend_related(path)` — ML-powered recommendations for a known note.
- `mcp_turbovault_suggest_links(file, limit)` — link suggestions for improving a note.

After selecting a candidate note from search, validate it through the graph:

1. Read its `topics` frontmatter.
2. Check backlinks/forward links.
3. Confirm it integrates with the expected MoC/INDEX path.

## 5) Hub And Structure Analysis

Use these for architecture and cleanup tasks, not for ordinary lookup:

- `mcp_turbovault_get_hub_notes(top_n)` — notes with the most graph connections.
- `mcp_turbovault_get_centrality_ranking()` — centrality metrics across the vault; can return large output.
- `mcp_turbovault_get_isolated_clusters()` — disconnected subgraphs.
- `mcp_turbovault_get_dead_end_notes()` — notes with backlinks but no outgoing links.
- `mcp_turbovault_detect_cycles()` — circular reference chains.

Hub interpretation:

1. Check whether top hubs are intentional MoCs, INDEX files, or domain wiki hubs.
2. If a non-MoC note becomes a hub, inspect whether it should become or link to a MoC.
3. Do not promote a note to MoC automatically; report the candidate and ask the user before restructuring.

## 6) Safety Checks Before Structural Changes

Before reorganizing, renaming, promoting, archiving, or doing bulk edits:

1. Run `mcp_turbovault_quick_health_check`.
2. Check backlinks for any note that will move:
   - `mcp_turbovault_get_backlinks(path)`
3. For large changes, run `mcp_turbovault_full_health_analysis` or targeted SQL/reporting.
4. After changes, verify:
   - changed notes read back correctly,
   - backlinks/forward links resolve,
   - relevant INDEX/MoC entries were updated,
   - no new broken links were introduced.

## 7) Output Expectations

When answering user questions about vault content, report:

1. The navigation path followed (INDEX → MoC → note).
2. The TurboVault tools used when relevant.
3. The specific notes/sections that justify the answer.
4. Search results only as supporting evidence when graph navigation was insufficient.
