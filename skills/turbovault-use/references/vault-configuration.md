# TurboVault Configuration Reference

Declarative reference for TurboVault 4.x configuration, startup/cache mechanics, multi-vault registration, write backends, and tool visibility.

- For step-by-step setup, config audits, post-update checks, or default diagnosis/repair, follow `references/wf-turbovault-config.md`.
- For binary upgrades and isolated upgrade testing, follow `references/wf-upgrading.md`.
- For runtime failures (parked spawns, `env` typing, missing session tools, `mcporter`), follow `references/troubleshooting.md`.

## 1. Config file schema (`config.yaml`)

TurboVault reads `--config <PATH>` (`TURBOVAULT_CONFIG`), or automatically falls back to `~/.turbovault/config.yaml` when it exists. Always pass an explicit `--config <PATH>` in client launch `args` so each profile is bound to one known file instead of sharing `~/.turbovault/config.yaml`.

```yaml
vaults:
  - name: main                     # FIRST entry becomes active_vault on a clean cache (see §2)
    path: /abs/path/to/vault       # ~ and $VAR are expanded from config/--vault
    is_default: true               # REQUIRED boolean on every entry (omitting stops startup), but does NOT choose active_vault
    write_backend: direct          # direct (default) or git
    reconcile_external_changes: true
    # optional per-vault overrides:
    # max_file_size: 10485760      # bytes (default 10 MiB)
    # allowed_extensions: [.md, .txt, .canvas, .base]
    # excluded_paths: [.trash]     # added to server defaults (.obsidian, .git, .DS_Store, node_modules); .turbovault is separately hard-protected
    # allowed_operations: all      # read | write | delete | move | all (string or list)
    # git:                         # only when write_backend: git
    #   branch: main
    #   merge_strategy: merge-commit   # merge-commit | fast-forward
    #   include_ignored: true
    #   require_commit_message: false
    #   author: { name: "...", email: "..." }

tool_visibility:
  show_advanced_tools: true        # false hides 22 advanced tools from tools/list (still callable by name)
  disabled:
    - fanout
    - list_orphan_fanouts

security:
  # allowed_vault_roots: [~/Vaults]   # CLI/env: --allowed-vault-roots / TURBOVAULT_ALLOWED_VAULT_ROOTS
  allow_unauthenticated_network: false
```

Schema quirks verified against TurboVault 4.x source (`turbovault-core/src/config.rs`, `multi_vault.rs`, `cli.rs`):

- **`is_default` is mandatory on every `vaults:` entry, yet does not control `active_vault`:** `VaultConfig.is_default: bool` has no serde default, so omitting it fails startup. However, `ObsidianMcpServer` starts vault-agnostic (`MultiVaultManager::empty()`) and registers configured vaults via `add_vault` in list order, where only the **first** vault added sets `default_vault`. Put the desired default vault **first** under `vaults:` (and keep `is_default: true` on it / `false` on others for clarity and forward compatibility).
- **Distinguish `list_vaults` fields:** Top-level `data.vaults[].is_default` reflects the **active vault pointer**, not the YAML key; the YAML value lives at `data.vaults[].config.is_default`.
- **Silent vs. loud unknown keys:** Unknown keys inside `vaults:` entries are silently ignored (legacy pre-4.0 keys like `enable_caching`, `cache_ttl`, `template_dirs`, `watch_for_changes` are dead/ignored; `watch_for_changes` deserializes only as a serde alias for `reconcile_external_changes`). Unknown keys under `security:` fail startup.
- **Profiles (`-p` / `--profile`):** `development` (debug), `production` (info — recommended baseline), `read-only` (warn, refuses all mutating tools), `high-performance` (warn), `minimal` (error, disables external-edit reconciliation), `multi-vault`, `collaboration`.

## 2. Startup order, project cache & search index

TurboVault stores both its per-project vault registry cache and per-vault search indexes under `$XDG_CACHE_HOME/turbovault/` (default `~/.cache/turbovault/`):

- **Project registry cache:** `$XDG_CACHE_HOME/turbovault/projects/<project-id>/` (`vaults.yaml` + metadata). The project ID is hashed from the nearest ancestor of the server's working directory containing `.git`, `.obsidian`, `Cargo.toml`, `package.json`, or `.project` — falling back to the working directory itself (`cache.rs`).
- **Search index:** `$XDG_CACHE_HOME/turbovault/search/<vault-hash>/` (set `TURBOVAULT_SEARCH_INDEX=memory` for in-memory only).
- **When the project cache is written:** Pure startup from `--config` does **not** write `vaults.yaml`; the cache is written when runtime `add_vault` or `set_active_vault` runs (which then persists *all* currently registered vaults, including YAML ones, plus `active_vault`).

Actual startup order (`crates/turbovault/src/cli.rs`):

1. **Cache recovery runs first:** Restores cached vaults (re-checked against `allowed_vault_roots` and path confinement — paths under hidden home directories are silently skipped with a warning) and restores cached `active_vault`.
2. **Configured vaults (`--config` or `~/.turbovault/config.yaml`) run second:**
   - If a vault `name` is **not** in the cache, it is registered with all YAML settings (the first registered vault becomes `active_vault` if cache did not set one).
   - If the same `name` is already in the cache with a **different** `path`, the YAML entry replaces the cached one.
   - **Critical trap:** If the same `name` and **same `path`** already exist in the cache, TurboVault executes `continue` and **skips the YAML entry completely**. Stale cached settings (`reconcile_external_changes`, `allowed_operations`, `max_file_size`, `write_backend`, `config.is_default`) and the cached `active_vault` stay active and mask edits made to the YAML!
3. **`--vault <PATH>` runs third:** Registered as `default` only if that name is free.

### Consequences & cache isolation

- **Verify applied per-vault settings via `data.vaults[].config` (or `list_vaults(name: "<vault>")`):** Seeing the expected `tools/list` count proves `tool_visibility` was read, **not** that every `vaults:` field took effect. Compare `config` fields against the YAML; if a cached `(name, path)` masks YAML edits, rename the project cache directory aside (for evidence, rather than blind deletion), restart the server, and re-verify.
- **Isolate `XDG_CACHE_HOME` per profile — even on single-profile hosts:** Set `XDG_CACHE_HOME` to a profile-local cache path string in the client's MCP `env`. This prevents project-root-keyed cache drift across gateway, dashboard, CLI, and future profiles.
- **Prove isolation from startup logs:** A clean isolated startup logs `Project cache initialized: <id> | Cache dir: <path>`, then `No cached vaults found for this project`, then `Registering configured vault '<name>'` for each YAML entry. Any unexpected `Restored vault from cache` line indicates a cache leak.

## 3. Registering existing vaults & Obsidian discovery

When adding an existing vault at runtime:

1. Inspect `list_vaults` (`data.vaults` and `data.active_vault`).
2. Call `add_vault(name, path)` (`create: false` default). Runtime paths expand `~` only (not `$VAR`). Registration is confined — filesystem roots, home directories, hidden/app-data directories under home, and system directories are refused; `security.allowed_vault_roots` / `--allowed-vault-roots` narrows it further (and is required on network transports).
3. Registration does **not** switch `active_vault` (unless it is the very first vault). Prefer passing `vault: "<name>"` on scoped calls; call `set_active_vault(name)` only when a global pointer switch is intentional (remembering it persists the project cache).
4. Verify with `get_vault_context(vault: "<name>")` — confirm name, registered path, and ready state.

If the user has not supplied a vault path, local Obsidian registrations live in `obsidian.json`:

- macOS: `~/Library/Application Support/obsidian/obsidian.json`
- Linux: `~/.config/obsidian/obsidian.json` (Flatpak: `~/.var/app/md.obsidian.Obsidian/config/obsidian/obsidian.json`)
- Windows: `%APPDATA%\obsidian\obsidian.json`

Register only the vaults needed for the task; ask if none are discoverable.

## 4. Write backend & tool visibility policy

- **Default backend is `direct`.** Atomic temp-file renames with `expected_hash` guards and `.turbovault/audit/` snapshots. Works alongside Obsidian Sync, iCloud, Dropbox, or Syncthing.
- **Git backend (`write_backend: git`) is opt-in per vault:** Requires an initialized Git repo (`git init`), refuses uncommitted changes on touched files, makes every write/batch one commit, and disables `audit_log`/`rollback_note`. Enable it **only** with explicit user authorization for that named vault, after confirming no competing sync layer writes to the same directory and after testing on a copy.
- **Tool visibility (`tool_visibility`):**
  - `show_advanced_tools: false` (server default) hides 22 advanced tools from `tools/list`, **but leaves them callable by name** — hiding is not access control.
  - Use `disabled` (or `--disabled-tools` / `allowed`) to enforce real blocks. Keep `fanout` and `list_orphan_fanouts` in `disabled` on Direct-backend servers.
