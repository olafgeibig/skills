# TurboVault Configuration Workflow (`wf-turbovault-config`)

Procedural workflow for initial TurboVault + Hermes MCP configuration, configuration audits, post-update config checks, default-vault diagnosis, and persisted default repair.

Scope split:

- Use this workflow for step-by-step audits, setup, post-upgrade checks, and default diagnosis/repair.
- Use `references/vault-configuration.md` for declarative YAML schema, cache mechanics, vault registration (`add_vault`), and isolated-test gates.
- Use `references/troubleshooting.md` for runtime failures (parked spawns, `env` typing errors, `mcporter` bridging, reconnect churn, log diagnosis).

## 1. Read-Only Inventory

Before changing any file or setting, gather all four layers without mutating state:

1. **Installed binary & CLI surface:** Run `turbovault --version` and `turbovault --help`. Record new, renamed, or removed flags and environment variables — after an upgrade, `--help` is the ground truth for whether the client launch entry needs adjustment.
2. **Client MCP launch config:** Read only the `turbovault` server entry (e.g. `hermes config get mcp_servers.turbovault`). Do not print unrelated configuration or credential-bearing sections. Inspect `command`, `args`, and `env`.
3. **Resolved `--config` YAML:** Follow the `--config <path>` argument in `args` and read that exact YAML file. (Do not assume `~/.turbovault/config.yaml` is active when `--config` points elsewhere; without `--config`, TurboVault reads `~/.turbovault/config.yaml` only for `tool_visibility`, never for `vaults:`.)
4. **Live server state:** Call `list_vaults` and `get_vault_context` through the active MCP connection. Compare names, registered absolute paths, `is_default` flags, and `active_vault` against the YAML.

Keep inspection read-only unless a change was authorized.

## 2. Baseline Configuration & Post-Update Checklist

Check both the client MCP entry and the `--config` YAML against these baseline defaults:

### Client MCP entry (`mcp_servers.turbovault`)

- **Explicit `--config <path>` in `args`:** Required so the server loads `vaults:` and per-vault settings from a single file rather than relying on the working-directory cache.
- **Profile cache isolation (`env.XDG_CACHE_HOME`) — also on single-profile setups:** Set `XDG_CACHE_HOME` to a profile-specific path (e.g. `<profile-home>/cache`). TurboVault stores its per-project registry cache under `$XDG_CACHE_HOME/turbovault/projects/<hash>/` keyed by working directory; isolating it prevents drift across gateway, dashboard, CLI, and future profiles even when only one profile exists today.
- **No non-string flags in `env`:** Never place boolean or numeric flags (such as `TURBOVAULT_NO_CONFIRM_DESTRUCTIVE`) in `env`; put switches in `args`.
- **Hermes elicitation fix (`--no-confirm-destructive` in `args`):** Hermes answers MCP elicitations with an empty object and never fills `requestedSchema`, causing `delete_note`, destination-replacing `move_note`, and forced `rollback_note` to fail while `batch_execute` remains open. Include `--no-confirm-destructive` in Hermes `args` as the baseline workaround unless the user intentionally wants those three single-call tools blocked; keep `confirm_path`, backlink checks, and audit-ID reporting discipline active (`references/audit-and-rollback.md`).
- **Optional plugins (`--plugins`):** Omit `--plugins vector_search` from the baseline configuration. The plugin binds one engine per server process to a single vault (requiring its own model load and per-vault config); do not enable it on multi-vault servers, and set it up only when explicitly requested for a dedicated single-vault server (`references/vector-search.md`, `references/vector-search-setup.md`).

### TurboVault `--config` YAML

- **Clean YAML without misleading comments:** Remove stale or false comments (for example comments claiming `~/.turbovault/config.yaml` is auto-read for `vaults:` without `--config`).
- **`tool_visibility` baseline:**
  ```yaml
  tool_visibility:
    show_advanced_tools: true
    disabled:
      - fanout
      - list_orphan_fanouts
  ```
  `show_advanced_tools: false` only hides tools from `tools/list` and does not block calls. Keep `fanout` and `list_orphan_fanouts` in `disabled` while vaults run on `write_backend: direct` — a binary upgrade does not preserve a missing block list.
- **Vault entries:** Every vault entry requires an explicit `is_default` boolean (omitting it stops startup), `write_backend: direct`, `reconcile_external_changes: true`, and an existing target directory.
- **Confirm the profile's default vault with the user:** Which vault carries `is_default: true` is profile- and instance-specific. Always present the current `is_default: true` vault (plus the other registered vaults) and ask the user explicitly whether that choice is actually the intended default — never assume an inherited entry is right.

### Post-Update Config Check

After upgrading the `turbovault` binary (`references/upgrading.md`), run steps 1 and 2 and specifically check:

1. Whether any flags in client `args` were renamed, deprecated, or newly required in `turbovault --help`. Keep client launch args minimal — an upgrade does not by itself require new flags.
2. Whether any YAML keys changed under `vaults`, `tool_visibility`, or `security` (unknown keys in `vaults` entries are ignored silently; unknown keys under `security` stop startup).
3. Whether `tool_visibility.disabled` still blocks `fanout` and `list_orphan_fanouts` and whether the live `tools/list` count matches the configured policy.

## 3. Inspect Existing Working-Vault Registrations

When checking whether project working vaults are registered:

1. Run the read-only inventory in step 1 to obtain configured names/paths from `--config` and live entries from `list_vaults`.
2. Resolve each requested project's embedded vault root from its project manual or existing registration, and check on disk that the project directory and vault directory actually exist and are non-empty.
3. If YAML and runtime disagree, compare `--config` and the server's `XDG_CACHE_HOME` / working-directory cache (`references/vault-configuration.md`) instead of guessing. Do not restart or rewrite configuration during a read-only check.
4. Report one compact row per project distinguishing configured, live-registered, and directory-present states, naming the config file used and stating that nothing changed.

## 4. Diagnose Where a Default Comes From

When asked why a given vault is treated as the default:

1. **Separate three independent facts:** the intended working target (user request or prompt convention), the persisted `is_default` flag in `--config`, and the live runtime `active_vault`. None proves the other two.
2. **Check prompt/personality layers separately:** Inspect only relevant profile/personality prompts if present. A personality prompt applies only when selected and does not prove a global startup default.
3. **Check `--config` YAML vs. live `list_vaults` + `get_vault_context`:** Remember that an unfiltered `list_vaults` response may omit `data.config`; inspect `data.vaults`, `data.active_vault`, and the `--config` YAML directly.
4. **Report unresolved mismatches honestly:** If the YAML has no `is_default: true` (or disagrees with runtime) and no cache restoration explains it, report the source as **unresolved**. Never infer persistence or startup behavior from list order, an earlier session, or a successful `set_active_vault` call (`set_active_vault` changes runtime selection only).

## 5. Repair a Persisted Vault Default

When the user asks to change the persisted default vault (not just the current session selection):

1. **Resolve the live server's `--config` path first** (step 1). Never edit a different YAML file than the one the running server uses.
2. **Edit `is_default` across all entries in place:** Set `is_default: true` on the exact vault the user requested and `is_default: false` on all other entries. Never delete the `is_default` key (startup fails if an entry omits it). Preserve `path`, `write_backend`, `reconcile_external_changes`, and unrelated settings.
3. **Verify disk and runtime separately:**
   - Read back the modified YAML entries on disk to confirm persistence.
   - Query `list_vaults` and `get_vault_context` to inspect live state; a runtime listing is not a file read-back.
   - If the running server has not picked up the YAML change, report persisted config and live state separately and reload/restart only through the owning service (`references/upgrading.md` §7).
4. **State verification scope precisely:** Matching YAML and runtime values confirm the *current* state, not restart persistence. Claim startup behavior only after an actual restart has been exercised.

## 6. Verification

1. Run the offline config probe from the skill directory:
   ```bash
   python3 scripts/probe-config.py /path/to/turbovault.yaml
   ```
   Confirm registered vaults, `is_default` flags, `active_vault`, and listed tool count (accounting for `show_advanced_tools: true` minus disabled tools).
2. After any authorized reload or restart of every affected Hermes service (gateway, dashboard), verify `list_vaults` and `get_vault_context` on the live session.
