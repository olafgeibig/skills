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
3. In multi-vault setups, prefer the v4 `vault` argument on each scoped call; when a tool lacks it or the server is pre-v4, call `set_active_vault(name)` and re-confirm with `list_vaults` and `get_vault_context`. Match the registered absolute path to the intended directory. Counts are only a plausibility check, not proof of identity.

Example: a write request clearly aimed at the large vault, but `get_vault_context` reports ~50 notes — wrong vault active; switch explicitly before writing.

## Upgrade and isolated-test gates

1. Inventory the installed binary, running MCP connection, configuration source, registered paths, selected vault, and write backends separately; they can refer to different processes or configurations.
2. Stage the candidate binary and configuration outside production. Verify the release checksum and candidate `--version`; this establishes the candidate artifact, not the version of an already-running server.
3. Use a disposable vault or an explicitly authorized copy. Through the exact MCP connection intended for the test, call `list_vaults` and `get_vault_context` to confirm the disposable target's registered absolute path; on v4, pass its `vault` name on every scoped write. A scratch configuration or separate CLI process does not establish the target of session-bound tools.
4. Inspect the candidate's exposed tools and schemas before planning test calls. Do not infer a public MCP tool from an internal function or a tool mentioned in another release.
5. Test reads, guarded edits, moves, link handling, and deletion only after target verification. Use collision-checked fixture names and retain pre-write content/hashes for every touched existing file. If a write lands in an unexpected vault, stop the test; inspect actual changes before deciding on restoration. Do not assume deleting the filenames restores pre-existing content or removes sync history.
6. Keep Direct as the default and Git/fan-out disabled unless the standing per-vault authorization gate is met. Test non-Git and externally synchronized vault compatibility on copies, not by enabling Git on the originals.
7. Treat metadata normalization as a separate scoped change. Audit notes and templates against the candidate parser; report findings without silently rewriting vault content during a binary upgrade.
8. Before authorized replacement, preserve the installed binary and production configuration in a durable rollback location, not an auto-pruned scratch directory. After the controlled restart, verify the new running connection's version, registrations, paths, default selection, and backend settings before further writes.
9. Report staged artifacts, installed artifacts, running process state, and verified tests separately. A checksum or smoke test is not a completed migration; an expected missing-file result after deletion is cleanup evidence, not a reason to retry the same read indefinitely.

## Discover vaults from Obsidian configuration

When the user has not provided a path, discover local Obsidian vaults through `obsidian.json` where appropriate. Common locations:

- macOS: `/Users/<username>/Library/Application Support/obsidian/obsidian.json`
- Windows: `%APPDATA%\\obsidian\\obsidian.json`
- Linux: `~/.config/obsidian/obsidian.json`
- Flatpak: `~/.var/app/md.obsidian.Obsidian/config/obsidian/obsidian.json`

Register only the vaults needed for the task. If none are discoverable, ask for the vault path. Registration still requires a separate activation and `get_vault_context` verification.

## Vault registry and config file (4.0)

The registry is not one global list. In 4.0 registration combines these sources (configured entries take precedence over cached entries with the same name; this is not a guarantee of execution order):

1. vaults declared in `~/.turbovault/config.yaml` (auto-read) or the file passed with `--config`;
2. vaults restored from the per-project cache `~/.cache/turbovault/projects/<hash>/vaults.yaml`;
3. `--vault <path>`, registered as `default` if that name is free.

Treat the configured `is_default`, runtime default flags, and active selection as separate observations. Do not promise active selection from the YAML alone: a v4 startup with restored cache state can select a different vault. Because the cache is keyed by the server's **working directory**, two Hermes processes (dashboard, gateway) can report different vault lists on the same machine. Declare intended entries explicitly, then verify the complete live registry and active selection after startup; cached names absent from the config may also be restored. Test both a clean cache and a disposable copy of the relevant existing cache under the intended working directory before claiming restart behavior. Keep all probe cache writes isolated from production.

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
