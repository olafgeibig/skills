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

## Detect vaults and register them in TurboVault

Goal: if vaults are discoverable locally (e.g. via Obsidian), register them in TurboVault so the agent can select them via MCP.

1. Discover Obsidian vaults via `obsidian.json`.
   Common locations:
   - macOS: `/Users/<username>/Library/Application Support/obsidian/obsidian.json`
   - Windows: `%APPDATA%\\obsidian\\obsidian.json`
   - Linux: `~/.config/obsidian/obsidian.json`
   - Flatpak: `~/.var/app/md.obsidian.Obsidian/config/obsidian/obsidian.json`

2. For each discovered vault path, register it with TurboVault:
   - `mcp_turbovault_add_vault` (use a stable name, preferably the vault folder name)

3. If no vaults are discoverable, ask the user for vault paths and register those with TurboVault.

Notes:
- If the user provides a vault path directly and it is not registered yet, register it with TurboVault before proceeding.
