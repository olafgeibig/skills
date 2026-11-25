# TurboVault Configuration Guide

`turbovault-use` requires an available TurboVault MCP server. This guide is where the wiring is made and repaired; it is not where the vault is operated.

## When to read this

Read it when **TurboVault** is the problem, never when a **vault** is:

| The question | Where |
|---|---|
| "How do I audit, configure, post-update check, or fix a default vault?" | `references/wf-turbovault-config.md` |
| "It is missing, unreachable, or a tool vanished" | §Detect TurboVault below, then `references/troubleshooting.md` for the symptom |
| "What is the YAML schema, cache layout, or isolated-test gate?" | this file |
| "Something misbehaves although it is there" — parked spawn, stale UI, reconnect churn | `references/troubleshooting.md`, not here |
| "How do I edit, move, query, delete?" | the tool reference for that task; none of these files |

The always-on checks stay in `SKILL.md` §Establish Availability (`list_vaults` first; an empty registry does not explain the cause, and a missing tool does not prove the server is down). Read this guide when those checks report something wrong that has to be fixed.

## Detect TurboVault

We use a two-stage check:

1. Stage 1 (informational): check that the TurboVault CLI is installed.
   - Run: `turbovault --version`
   - If missing: tell the user to install it (https://github.com/Epistates/turbovault)

2. Stage 2 (decisive): check that the TurboVault MCP server is available (this is what the agent actually uses).
   - Call `list_vaults`
   - If it succeeds (even with an empty list): TurboVault MCP is available.
   - If it fails: stop and instruct the user to enable/configure TurboVault MCP.

## Register an existing vault

When the user provides an existing vault path that is not registered:

1. Call `list_vaults` and read `data.vaults` plus `data.active_vault`.
2. Call `add_vault(name, path)` for the existing directory. Registration does not require a newly created directory and does not switch `active_vault`.
3. Prefer passing `vault: name` on subsequent scoped calls. Call `set_active_vault(name)` only when the user intentionally wants to switch the global active pointer for tools without a `vault` argument.
4. Verify with `get_vault_context(vault=name)` (or `get_vault_context` after `set_active_vault`); confirm the vault name, registered path, and ready state together.

Do not assume `add_vault` also selects the vault. Do not claim success from the registration response alone.

## Pre-write orientation

Before the first write in a session — and again after a long pause (>30 min) in a long session — confirm orientation, not just availability:

1. Call `list_vaults` and `get_vault_context`.
2. Sanity-check `current_stats.total_notes` against the content you intend to touch: a count far from the expected magnitude means the wrong vault is targeted — stop and ask, or pass the intended `vault` argument explicitly when unambiguous.
3. In multi-vault setups, prefer the `vault` argument on each scoped call; when a tool lacks it or an explicit session selection is desired, call `set_active_vault(name)` and re-confirm with `list_vaults` and `get_vault_context`. Match the registered absolute path to the intended directory. Counts are only a plausibility check, not proof of identity.

Example: a write request clearly aimed at the large vault, but `get_vault_context` reports ~50 notes — wrong vault active; switch explicitly before writing.

## Upgrade and isolated-test gates

1. Inventory the installed binary, running MCP connection, configuration source, registered paths, selected vault, and write backends separately; they can refer to different processes or configurations.
2. Stage the candidate binary and configuration outside production. Verify the release checksum and candidate `--version`; this establishes the candidate artifact, not the version of an already-running server.
3. Use a disposable vault or an explicitly authorized copy. Through the exact MCP connection intended for the test, call `list_vaults` and `get_vault_context` to confirm the disposable target's registered absolute path; pass its `vault` name on every scoped write. A scratch configuration or separate CLI process does not establish the target of session-bound tools.
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

Register only the vaults needed for the task. If none are discoverable, ask for the vault path. Pass the `vault` argument on scoped calls or verify with `get_vault_context` after any intentional `set_active_vault`.

## Vault registry and config file

The registry is not one global list. Registration combines these sources (configured entries take precedence over cached entries with the same name; this is not a guarantee of execution order):

1. vaults declared in the file passed with `--config` — the only source of a `vaults:` list: without the flag, `~/.turbovault/config.yaml` is opened for its `tool_visibility` section alone, so no vault declaration and no per-vault setting is read, and the registry comes from the project cache;
2. vaults restored from the per-project cache `$XDG_CACHE_HOME/turbovault/projects/<hash>/vaults.yaml` (default `~/.cache/turbovault/projects/<hash>/vaults.yaml`);
3. `--vault <path>`, registered as `default` if that name is free.

**A listed advanced-tool set proves the file was found, never that its `vaults:` were applied.** The `config` echo of `list_vaults(name: …)` is the proof for that half: compare it field by field with the YAML — `is_default`, `reconcile_external_changes`, `max_file_size`, `allowed_operations`. A stale cache entry produces a plausible-looking echo in which every declared value is missing (`is_default: false`, `reconcile_external_changes: null`) while `tool_visibility` and the tool count look healthy. When values are missing: put `--config <path>` into the launch entry, rename the project cache directory aside — renamed, not deleted, it is the evidence — then restart and re-read the echo.

Treat the configured `is_default`, runtime default flags, and active selection as separate observations. Do not promise active selection from the YAML alone: startup with restored cache state can select a different vault. Because the cache is keyed by the server's **working directory**, two Hermes processes (dashboard, gateway) can report different vault lists on the same machine. Declare intended entries explicitly, then verify the complete live registry and active selection after startup; cached names absent from the config may also be restored. Test both a clean cache and a disposable copy of the relevant existing cache under the intended working directory before claiming restart behavior. Keep all probe cache writes isolated from production.

**Isolate the cache per profile — including single-profile installations.** The YAML alone does not exclude entries from a shared cache, and `security.allowed_vault_roots` only limits runtime `add_vault`. Giving every profile its own cache root prevents CWD-keyed drift across gateway, dashboard, CLI, and additional profiles. Prove the result by comparing `list_vaults` with the YAML rather than by reading either alone.

Two levers separate the cache, and the cheaper one is the cache root rather than the working directory:

1. **`XDG_CACHE_HOME` in the server entry's `env`** — the cache lands below it (`<root>/turbovault/projects/<hash>/`), so each profile keeps its own directory while the client spawns from any working directory. The value is a path string, so it avoids the non-string env validation failure.
2. **A launcher that `cd`s into the profile directory before `exec`** — changes the cache key instead of the root; needed only when `XDG_CACHE_HOME` cannot be set.

Prove either lever before restarting anything: run the binary with the intended environment and working directory, then read its startup log. A separated cache prints `Project cache initialized: <id> | Cache dir: <path>`, then `No cached vaults found for this project`, then one `Registering configured vault '<name>'` line per entry in the YAML. Any `Restored vault from cache: '<name>'` line is a leak, and a restored `active_vault` overrides the `is_default` flag from the config. Restart the owning service afterwards and confirm the new registry with `list_vaults`.

```yaml
vaults:
  - name: main
    path: /home/user/vaults/main
    is_default: true          # required per entry — omitting it stops startup
    write_backend: direct     # direct (default) or git
    reconcile_external_changes: true

tool_visibility:
  show_advanced_tools: true   # or the 22 advanced tools are unlisted
  disabled:
    - fanout
    - list_orphan_fanouts
```

`allowed_operations` (`read`, `write`, `delete`, `move`, `all`) makes a vault read-only; `security.allowed_vault_roots` limits where runtime `add_vault` may register a vault. An unknown key under `security` stops startup; an unknown key in a `vaults` entry is ignored. For the step-by-step audit, post-update check, and default diagnosis/repair procedure, run `references/wf-turbovault-config.md`.
