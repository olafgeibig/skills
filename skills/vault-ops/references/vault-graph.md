# Vault Graph

The vault graph is the navigable structure created by MoCs, wikilinks, and frontmatter metadata. TurboVault exposes this graph directly through link-analysis tools and metadata queries; do not reconstruct it with filesystem scans or ripgrep unless TurboVault is unavailable.

## Graph Model

Vault Ops uses two complementary link layers:

1. **Body wikilinks** — real Obsidian links parsed by TurboVault into the graph.
   - Used by `mcp_turbovault_get_forward_links`, `mcp_turbovault_get_backlinks`, `mcp_turbovault_get_related_notes`, the `links` SQL table, hub detection, centrality, and Obsidian graph view.
2. **Frontmatter `topics`** — token-efficient parent/related MoC hints.
   - Used for quick Note → MoC routing and structured filtering.
   - `topics` values are YAML strings, not real wikilinks; they do not create backlinks by themselves.

Because `topics` does not create graph edges, every note that belongs to a MoC must include the same MoC links in the body `Topics:` section as real wikilinks.

## Root And Scope

Default root navigation is:

- `INDEX.md` — vault root INDEX, links to sub-INDEX files
- `area/INDEX.md` — area MoCs
- `projects/INDEX.md` — project MoCs
- `wiki/index.md` — wiki domain hubs, maintained with `md-wiki`

By default, Vault Ops operates on `area/`, `projects/`, `inbox/`, `sources/`, `system/`, and `archive/` according to `AGENTS.md`. Do not edit `wiki/` with Vault Ops unless the user explicitly asks and the `md-wiki` skill is loaded.

## Required Graph Integration

- Regular notes and MoCs in `area/` and `projects/` should be reachable from the relevant INDEX/MoC path.
- A note should have at least one parent/related MoC in `topics` unless `AGENTS.md` defines another rule.
- A note should also contain the same MoC links as body wikilinks in its `Topics:` section.
- MoCs should link to their curated child notes through body wikilinks.
- Bidirectional links are required for navigation relationships (MoC ↔ child note, INDEX ↔ MoC). For ordinary semantic links, add reverse links only when they help navigation or retrieval.

## `topics` Frontmatter Format

`topics` MUST be an array/list because a note can belong to multiple MoCs. To keep Obsidian property editing reliable, represent each topic as a quoted string containing the wikilink.

Correct:

```yaml
topics: ["[[+Agents]]", "[[+Personal Agents]]"]
```

Also acceptable:

```yaml
topics:
  - "[[+Agents]]"
  - "[[+Personal Agents]]"
```

Incorrect:

- `topics: [[+Agents]]`
- `topics: [+Agents]`
- `topics: ["+Agents"]`
- `topics: ["Agents"]`

## Body Link Format

Mirror the same MoCs as real wikilinks in the body:

```markdown
---
topics: ["[[+Agents]]", "[[+Vault Ops]]"]
---

# Note Title

...

---

Topics:
- [[+Agents]]
- [[+Vault Ops]]
```

## TurboVault Graph Tools

Use TurboVault graph tools directly:

- `mcp_turbovault_get_forward_links(path)` — links from a note/MoC to other notes.
- `mcp_turbovault_get_backlinks(path)` — body-wikilink backlinks pointing to a note/MoC.
- `mcp_turbovault_get_related_notes(path, max_hops=1..2)` — nearby notes in the parsed graph.
- `mcp_turbovault_get_hub_notes(top_n)` — most connected notes; useful for finding existing hubs or overloaded notes.
- `mcp_turbovault_get_centrality_ranking()` — global centrality ranking; useful for structural analysis, but can be large.
- `mcp_turbovault_detect_cycles()` — circular-reference analysis.
- `mcp_turbovault_get_dead_end_notes()` — incoming links without outgoing links.

For reporting and batch checks, use `mcp_turbovault_query_frontmatter_sql` against TurboVault tables after `mcp_turbovault_inspect_frontmatter`. For single-note frontmatter lookup, use `mcp_turbovault_get_metadata_value`:

- `files` — one row per note with frontmatter columns (`path`, `type`, `topics`, `description`, etc.).
- `links` — parsed graph edges (`source`, `target`, `link_type`, `is_valid`).
- `tags` — unnested tags (`path`, `tag`).

Prefer the dedicated graph tools for normal navigation. Use SQL when you need filtering, aggregation, or batch reporting.

## SQL Caveats

TurboVault SQL support is powerful but not equivalent to SQLite. Do not assume arbitrary joins or `json_each(topics)` work. In the current tested setup, a query like `SELECT path FROM files, json_each(topics) ...` fails because multi-table selects are not supported.

Use these safer patterns instead:

```sql
-- Find MoCs
SELECT path, type, description FROM files WHERE type = 'moc' ORDER BY path LIMIT 50

-- Batch graph query via parsed body links
SELECT source, target FROM links WHERE target LIKE '%+Agents%' LIMIT 50

-- Inspect one note's topics
SELECT path, topics FROM files WHERE path = 'area/agents/example.md'
```

For exact frontmatter topic lookup, prefer `mcp_turbovault_search_by_frontmatter(key='topics', value='[[+Agents]]')` when it is sufficient. For comprehensive MoC → child discovery, prefer `get_backlinks` plus `get_forward_links`, because those operate on actual body wikilinks.
