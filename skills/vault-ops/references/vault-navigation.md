# TurboVault navigation

Use this when TurboVault MCP tools are available. Prefer graph- and metadata-aware queries over filesystem scanning.

Scope note: by default, exclude `wiki/` and `system/` from navigation/search unless the user explicitly asks for them.

Goal: follow the vault’s intended navigation path (MoCs -> notes) instead of doing global keyword search first.

1) Find the entry MoC.
- Default entry point is `+Index.md` (or a vault-local equivalent defined in `AGENTS.md`).

2) Traverse outward.
- From a MoC note, use:
  - `mcp_turbovault_get_forward_links` to enumerate outgoing links.
  - `mcp_turbovault_get_backlinks` when you need incoming context or to find “where is this referenced?”.

3) Expand selectively.
- Use `mcp_turbovault_get_related_notes` (max_hops=1..2) to discover nearby notes, then read the most relevant ones.
- Prefer breadth-limited traversal: stay on MoC nodes (+*.md) first, then drill into linked notes.

4) Handle nested MoCs explicitly.
- Treat MoCs as a hierarchy: a MoC can link to sub-MoCs (also +*.md).
- During traversal, expand MoC -> sub-MoC links before expanding MoC -> regular note links.
- If a MoC is too broad, expect navigation to continue via sub-MoCs; do not stop at the parent MoC.

5) Read notes as needed.
- Use `mcp_turbovault_read_note` to read full content.
- Use `mcp_turbovault_get_notes_info` for cheap metadata checks before reading full content.

## 2) Search frontmatter (structured)

Use when you know what metadata you want (type, tags, updated, topics, etc.).

1) Quick match:
- `mcp_turbovault_search_by_frontmatter` for exact key/value matches.

2) Pattern match:
- `mcp_turbovault_query_metadata` for existence and comparison-style filters.

3) Complex queries / reporting:
- `mcp_turbovault_query_frontmatter_sql` when you need joins/aggregations/sorting across many notes.
- Start by inspecting schema once per vault with `mcp_turbovault_inspect_frontmatter`.

## 3) Keyword / full-text search (BM25)

Use when:
- you don’t know the right MoC yet,
- you need to find a specific phrase,
- or you want to confirm coverage after graph traversal.

1) Use `mcp_turbovault_search` with a focused query.
- Prefer 2–5 distinctive keywords.
- If results are too broad, add another term rather than making the query long.

2) For conceptual matches (optional):
- Use `mcp_turbovault_semantic_search` for “find notes like this concept” style queries.

3) Validate through the graph:
- After selecting a candidate note, jump to its MoCs via `mcp_turbovault_get_forward_links`/`get_backlinks` and confirm it integrates where expected.

## 4) Safety / integrity checks (when changing structure)

Before reorganizing, renaming, or doing bulk edits:
- Run `mcp_turbovault_quick_health_check`.
- For deeper analysis, run `mcp_turbovault_full_health_analysis`.
- If moving notes, check impact with `mcp_turbovault_get_backlinks` first.

## 5) Output expectations

When answering user questions, prefer:
- the MoC path you followed (which MoCs led to which notes),
- then the specific note excerpts/sections that justify the answer,
- then (only if needed) keyword search results as supporting evidence.
