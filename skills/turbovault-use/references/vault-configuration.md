# Vault Configuration

turbovault-use requires an available TurboVault MCP server.

## Detect TurboVault

We use a two-stage check:

1. Stage 1 (informational): check that the TurboVault CLI is installed.
   - Run: `turbovault --version`
   - If missing: tell the user to install it (https://github.com/Epistates/turbovault)

2. Stage 2 (decisive): check that the TurboVault MCP server is available (this is what the agent actually uses).
   - Call `mcp_turbovault_list_vaults`
   - If it succeeds (even with an empty list): TurboVault MCP is available.
   - If it fails: stop and instruct the user to enable/configure TurboVault MCP.

## Register and activate an existing vault

When the user provides an existing vault path that is not registered:

1. Call `list_vaults` and `get_active_vault` to establish registered and active state.
2. Call `add_vault(name, path)` for the existing directory. Registration does not require a newly created directory.
3. Call `set_active_vault(name)` explicitly. Registration and activation are separate operations.
4. Verify with `get_vault_context`; confirm the active vault name, registered path, and ready state together.

Do not assume `add_vault` also selects the vault. Do not claim success from the registration response alone.

## Pre-write orientation

Before the first write in a session — and again after a long pause (>30 min) in a long session — confirm orientation, not just availability:

1. Call `get_active_vault` and `get_vault_context`.
2. Sanity-check `current_stats.total_notes` against the content you intend to touch: a count far from the expected magnitude means the wrong vault is active — stop and ask, or switch explicitly when the target vault is unambiguous.
3. In multi-vault setups, `set_active_vault(name)` explicitly, then re-confirm with `get_active_vault`.

Example: a write request clearly aimed at the large vault, but `get_vault_context` reports ~50 notes — wrong vault active; switch explicitly before writing.

## Discover vaults from Obsidian configuration

When the user has not provided a path, discover local Obsidian vaults through `obsidian.json` where appropriate. Common locations:

- macOS: `/Users/<username>/Library/Application Support/obsidian/obsidian.json`
- Windows: `%APPDATA%\\obsidian\\obsidian.json`
- Linux: `~/.config/obsidian/obsidian.json`
- Flatpak: `~/.var/app/md.obsidian.Obsidian/config/obsidian/obsidian.json`

Register only the vaults needed for the task. If none are discoverable, ask for the vault path. Registration still requires a separate activation and `get_vault_context` verification.
