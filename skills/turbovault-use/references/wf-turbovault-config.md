# TurboVault Configuration Workflow (`wf-turbovault-config`)

Procedural workflow for initial TurboVault + Hermes setup, configuration audits, post-update config verification, working-vault registration checks, and diagnosing or repairing a persisted default vault.

- Declarative schema, startup/cache precedence, and backend rules: `references/vault-configuration.md`.
- Binary upgrades and isolated test gates: `references/wf-upgrading.md`.
- Runtime failures (parked spawns, `env` typing, `mcporter` bridge): `references/troubleshooting.md`.

## 1. Read-only inventory

Gather all four layers before changing anything:

1. **Binary & CLI surface:** Run `turbovault --version` and `turbovault --help`. Note any renamed, deprecated, or newly added flags.
2. **Client MCP launch entry:** Read only the `turbovault` entry (e.g. `hermes config get mcp_servers.turbovault`). Never print unrelated config or credential sections. Inspect `command`, `args`, and `env`.
3. **Resolved `--config` YAML:** Read the exact file named by `--config` in `args` (or `~/.turbovault/config.yaml` if `--config` is absent). Note the **order** of entries under `vaults:`.
4. **Live server state:** Call `list_vaults` and `get_vault_context`. Compare `data.active_vault`, each entry's `path`, top-level `is_default` (active pointer), and nested `config` (`config.is_default`, `reconcile_external_changes`, `write_backend`) against the YAML.

Keep inspection strictly read-only until changes are authorized.

## 2. Hermes baseline checklist & post-update check

### Client MCP entry (`mcp_servers.turbovault`)

- **Explicit `--config <path>` in `args`:** Binds the profile to its own YAML rather than sharing `~/.turbovault/config.yaml`.
- **`-p production` in `args`:** Info-level structured stderr logs without debug noise.
- **Isolated `env.XDG_CACHE_HOME`:** Set to a profile-local cache path string (even on single-profile hosts) to prevent project-cache drift across gateway, dashboard, and CLI (`references/vault-configuration.md` §2).
- **String-only `env`:** Put boolean/switch flags in `args`, never in `env` (`references/troubleshooting.md` §2).
- **Destructive confirmation (`--no-confirm-destructive`):** Do **not** add blindly as a default — interactive MCP clients with form elicitation prompt the user directly. Enable `--no-confirm-destructive` in `args` only when the user explicitly authorizes unattended destructive calls or uses a client/headless mode that cannot answer form elicitations, after verifying audit recovery (`references/audit-and-drift.md` §2). Remember that the flag is read at server spawn and requires a restart to take effect.
- **No `--plugins vector_search` in baseline:** The plugin binds one engine per server process to a single vault; enable only on a dedicated single-vault server when explicitly requested (`references/vector-search.md`).

### TurboVault `--config` YAML

- **`tool_visibility`:** `show_advanced_tools: true` and `disabled: [fanout, list_orphan_fanouts]` on Direct-backend setups (`references/vault-configuration.md` §4).
- **Vault entries & order:** Put the intended startup default vault **first** under `vaults:` (`references/vault-configuration.md` §1–2 — the first entry becomes `active_vault` on a clean cache; `is_default: true` alone does not move the active pointer). Every entry still requires an explicit `is_default: true|false`, `write_backend: direct`, `reconcile_external_changes: true`, and an existing target path.
- **Confirm the default vault explicitly:** Present the first/active vault and all other registered vaults, and ask the user to confirm which vault is the intended startup default — never assume an inherited order is right.
- **Clean YAML comments:** Remove stale or inaccurate comments without deleting truthful notes about config behavior.

### Post-update delta check

After a binary upgrade (`references/wf-upgrading.md`), run steps 1–2 and verify:

1. Every flag in client `args` still matches `turbovault --help` (keep `args` minimal; upgrades rarely need new flags).
2. No YAML key broke under `vaults`, `tool_visibility`, or `security`.
3. `tool_visibility.disabled` still enforces the configured policy and live `tools/list` matches the expected count.

## 3. Inspect existing working-vault registrations (read-only)

1. Run step 1 to get configured YAML entries and live `list_vaults` entries.
2. Resolve each requested project's vault directory and verify on disk that it exists and is non-empty.
3. If YAML and runtime disagree, inspect `--config` and the server's `XDG_CACHE_HOME` project cache (`references/vault-configuration.md` §2) instead of guessing. Do not edit or restart during a read-only check.
4. Report one compact row per vault: configured, live-registered, directory-present, config file inspected, and confirm no state was modified.

## 4. Diagnose where the active vault comes from

1. Separate four independent facts: the user's intended target, the **first entry** in `--config`'s `vaults:`, each entry's YAML `is_default` (`data.vaults[].config.is_default`), and the live `active_vault` (which may come from a cached `active_vault` written by an earlier `set_active_vault`/`add_vault`).
2. Check profile/personality prompts separately — they apply only when selected, not as global server defaults.
3. Compare `--config` YAML against `list_vaults` (`data.active_vault` + `data.vaults[].config`; top-level `data.config` is included only when `name` is passed).
4. If neither cache metadata nor YAML order explains `active_vault`, report the source as **unresolved** — never guess startup persistence from a prior session.

## 5. Repair a persisted startup default vault

1. Resolve the running server's exact `--config` path first (step 1).
2. **Reorder `vaults:` and update `is_default`:** Move the requested default vault to be the **first entry** under `vaults:`, set `is_default: true` on it and `is_default: false` on every other entry, and preserve all other per-vault settings. (Editing `is_default` without moving the entry first does not change startup `active_vault` on TurboVault 4.0.x/4.1.x.)
3. **Clear or rotate the project cache for that profile:** If `$XDG_CACHE_HOME/turbovault/projects/<project-id>/` holds cached state from an earlier `set_active_vault`/`add_vault`, it overrides both YAML order and per-vault settings for matching `(name, path)` entries (`references/vault-configuration.md` §2). Rename that project cache directory aside before restarting.
4. Read back the modified YAML on disk, restart only through the owning service (`references/wf-upgrading.md` §6), and verify `list_vaults` and `get_vault_context` on the live session.
5. State verification scope precisely: claim restart persistence only after an actual restart has been exercised and observed.

## 6. Verification

Treat **clean-start config verification** and **effective live verification** as two separate checks (a clean-start probe cannot prove that a running server is free of stale project-cache overrides such as `allowed_operations: all` masking a YAML change to `read`):

1. **Clean-start config probe (isolated cache by default):**
   ```bash
   python3 scripts/probe-config.py --list-tools /path/to/turbovault.yaml
   ```
   Confirm exit `0`, every vault's `path`, `write_backend`, `allowed_operations`, `reconcile_external_changes`, `active` vs. `yaml:is_default` (no mismatch warning), and the exact listed tool names (not just count). Pass `--use-existing-cache` only when intentionally inspecting interaction with an existing project cache.
2. **Effective live verification:** After any authorized reload/restart of affected Hermes services (gateway, dashboard), inspect live `list_vaults` (comparing `path`, `write_backend`, `allowed_operations`, `reconcile_external_changes`, and `active_vault` against the YAML) and `get_vault_context`.
