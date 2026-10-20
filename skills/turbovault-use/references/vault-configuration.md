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

1. Call `list_vaults` and read `data.vaults` plus `data.active_vault` (4.0 returns them in one object; `get_active_vault` is gone).
2. Call `add_vault(name, path)` for the existing directory. Registration does not require a newly created directory.
3. Call `set_active_vault(name)` explicitly. Registration and activation are separate operations.
4. Verify with `get_vault_context`; confirm the active vault name, registered path, and ready state together.

Do not assume `add_vault` also selects the vault. Do not claim success from the registration response alone.

## Pre-write orientation

Before the first write in a session — and again after a long pause (>30 min) in a long session — confirm orientation, not just availability:

1. Call `list_vaults` and `get_vault_context`.
2. Sanity-check `current_stats.total_notes` against the content you intend to touch: a count far from the expected magnitude means the wrong vault is active — stop and ask, or switch explicitly when the target vault is unambiguous.
3. In multi-vault setups, `set_active_vault(name)` explicitly, then re-confirm with `list_vaults`.

Example: a write request clearly aimed at the large vault, but `get_vault_context` reports ~50 notes — wrong vault active; switch explicitly before writing.

## Discover vaults from Obsidian configuration

When the user has not provided a path, discover local Obsidian vaults through `obsidian.json` where appropriate. Common locations:

- macOS: `/Users/<username>/Library/Application Support/obsidian/obsidian.json`
- Windows: `%APPDATA%\\obsidian\\obsidian.json`
- Linux: `~/.config/obsidian/obsidian.json`
- Flatpak: `~/.var/app/md.obsidian.Obsidian/config/obsidian/obsidian.json`

Register only the vaults needed for the task. If none are discoverable, ask for the vault path. Registration still requires a separate activation and `get_vault_context` verification.

## Vault registry and config file (4.0)

The registry is not one global list. In 4.0 the server reads, in this order:

1. vaults declared in `~/.turbovault/config.yaml` (auto-read) or the file passed with `--config`;
2. vaults restored from the per-project cache `~/.cache/turbovault/projects/<hash>/vaults.yaml`;
3. `--vault <path>`, registered as `default` if that name is free.

The active vault is the entry with `is_default: true`, otherwise whatever the cache last had active. Because the cache is keyed by the server's **working directory**, two Hermes processes (dashboard, gateway) can report different vault lists on the same machine. Declaring the vaults in the config file is the only way to make the list deterministic.

```yaml
vaults:
  - name: main
    path: /home/user/vaults/main
    is_default: true          # required per entry — omitting it stops startup
    write_backend: direct     # direct (default) or git
    reconcile_external_changes: true

tool_visibility:
  show_advanced_tools: true   # or the 22 advanced tools are unlisted
```

`allowed_operations` (`read`, `write`, `delete`, `move`, `all`) makes a vault read-only; `security.allowed_vault_roots` limits where runtime `add_vault` may register a vault. An unknown key under `security` stops startup, an unknown key in a `vaults` entry is ignored.
