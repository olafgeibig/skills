# TurboVault
If turbovault is available exclusively use turbovault tools for the vault and its files and do not use file-tools anymore for that. It provides safe operations that avoids breaking the vault and its conbsistency. It is an MCP server and it must be configured for the agent. 

## Key Tools (Selection)

- `move_note` / `rename_note` — auto-updates all backlinks
- `batch_move` / `batch_delete` — atomic all-or-nothing operations
- `search` — full-text search with BM25 (Tantivy), <100ms on 10k notes
- `quick_health_check` / `full_health_analysis` — broken links, orphans, hubs
- `get_broken_links` / `get_orphans` — vault integrity
- `get_hub_notes` / `recommend_related` — knowledge graph navigation
- `edit_note` — hash-based conflict detection (optimistic concurrency)
- Multi-vault support (add/remove/switch at runtime)
