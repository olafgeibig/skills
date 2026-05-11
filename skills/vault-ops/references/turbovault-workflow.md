# TurboVault workflow notes (MCP)

This reference captures a proven workflow for using TurboVault MCP to operate on markdown vaults.

## When to prefer TurboVault vs filesystem

Prefer TurboVault when you need:
- indexed search (fast/advanced)
- backlinks/forward-links and related-note recommendations
- health checks (broken links, orphans)
- metadata queries / frontmatter updates

Fallback to filesystem tools when:
- TurboVault is unavailable
- you need to read non-note files that TurboVault doesn’t index
- you need to honor vault-local policies that restrict editing certain folders

## Minimal vault lifecycle

1) List existing vaults
- `list_vaults()`

2) Register a vault
- `add_vault(name, path)`
  - Example names used successfully: `work-vault`, `akademeia`

3) Activate a vault
- `set_active_vault(name)`

4) Confirm context/stats
- `get_vault_context()`

5) Quick health
- `quick_health_check()`
  - Useful fields: `broken_links_count`, `orphaned_notes_count`, `health_score`

6) Unregister
- `remove_vault(name)`

## Session-learned behavior

- Adding a vault may surface “subdirectory context discovered: …/AGENTS.md”. Treat that vault-local AGENTS.md as authoritative operating rules.
- Users may want both:
  - a sub-vault for `./wiki` (for specialized agents), and
  - the whole vault root.
  TurboVault supports registering both, but the user may later remove the sub-vault.

## Compliance/policy pitfall

TurboVault can technically edit anything under the vault path. Still enforce vault-local rules (commonly: do not edit `./wiki` except via `md-wiki`/`llm-wiki`).
