# TurboVault integration notes (MCP)

Use this reference when the user wants to operate a markdown vault via TurboVault tools (graph-aware) instead of raw filesystem tools.

## Vault registration workflow

- List registered vaults:
  - `mcp_turbovault_list_vaults`
- Register an existing vault directory:
  - `mcp_turbovault_add_vault(name, path)`
  - Prefer registering the *vault root* (e.g. `.../Work/`) over a subfolder like `.../Work/wiki/` unless the user explicitly wants the subfolder.
- Activate the vault:
  - `mcp_turbovault_set_active_vault(name)`

### Common operations

- Context/stats snapshot:
  - `mcp_turbovault_get_vault_context`
- Quick health:
  - `mcp_turbovault_quick_health_check`
- Broken links:
  - `mcp_turbovault_get_broken_links`

## Known quirks / pitfalls

### Export bug/limitation: broken-links export may be empty

Observed: `get_broken_links` returned many entries (e.g. 139), but `export_broken_links(format="json")` returned `[]`.

Workarounds:
- Don’t rely on export for correctness; use `get_broken_links` as the source of truth.
- If the user wants a report artifact, create it manually from `get_broken_links` output (group by source or target) and write it to a safe location (e.g. `own/`), subject to vault-local rules.

## Graph navigation primitives

- Backlinks / forward links: `get_backlinks`, `get_forward_links`
- Local neighborhood: `get_related_notes` (N hops)
- Hubs / dead ends: `get_hub_notes`, `get_dead_end_notes`
- Cycles: `detect_cycles`
- Similarity: `semantic_search` for topic queries; `find_similar_notes` requires a starting note path.
