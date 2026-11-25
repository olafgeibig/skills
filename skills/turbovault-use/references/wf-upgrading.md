# Upgrading the TurboVault Server (`wf-upgrading`)

Procedural workflow for upgrading or replacing the `turbovault` binary, testing safely against a disposable vault, migrating the skill library if the tool surface changed, and verifying the live reload.

When the user asks for an upgrade **plan**, deliver the plan read-only without replacing binaries, editing config, or restarting services — planning is not deployment authorization.

## 1. Inventory before touching anything

- Record `turbovault --version`, the live session's tool list/count (or `hermes mcp test turbovault`), the owning process, `--config` YAML, registered paths, selected vault, and write backends separately — they can diverge across processes.
- Plan against measured tool lists, not release notes alone. Prebuilt release archives ship all features (`--features release`); a bare `cargo install turbovault` builds stdio-only without HTTP/WebSocket/TCP transports, SQL, or plugins.

## 2. Stage and install with a durable rollback path

1. Stage the candidate archive outside production and verify its `.sha256` checksum (and optionally `gh attestation verify`).
2. Match OS, CPU architecture, and libc (`linux-musl` on older Linux distributions where `linux-gnu` requires newer glibc). Run `<staged> --version` and `<staged> --help` before moving it into place.
3. Archive the currently installed binary to a durable rollback path (e.g. `~/.local/share/turbovault/<old-version>/turbovault` — never an auto-pruned scratch directory), recording its version, SHA-256, and path. Pair it with backups of `--config` YAML, client MCP config, and per-vault audit logs (`operations.jsonl`). Distinguish planned archives from created archives.
4. **macOS code-signature inode trap:** Never `cp` directly over the existing executable. Copying onto the existing path preserves its inode and macOS kills subsequent starts with `Killed: 9` (exit 137). Move the old path aside first so the copy gets a fresh inode:
   ```bash
   mv ~/.local/bin/turbovault ~/.local/bin/turbovault.old
   cp <staged>/turbovault ~/.local/bin/turbovault
   ```
   Overwriting/swapping on disk leaves already-running server processes on their loaded inode until restarted.

## 3. Isolated disposable test gate (before touching production)

Never use a production vault as an implicit smoke-test fixture.

1. Run the candidate binary against a disposable vault copy with **isolated `HOME`, `XDG_CACHE_HOME`, and working directory** so cached registrations cannot redirect to production vaults.
2. Through that exact test MCP connection, call `list_vaults` and `get_vault_context` to verify the disposable vault's absolute path, and inspect the candidate's live `tools/list` and schemas.
3. Exercise a full lifecycle on collision-checked fixture notes (containing both a wikilink and an inline Markdown link): create → `read_note` (capture hash) → guarded `edit_note` → `move_note(update_backlinks: true)` → read back target and source links → `delete_note(confirm_path)` → confirm absence.
4. If a write ever lands in an unexpected vault, stop immediately and inspect actual changes before deciding on restoration.
5. Run `validate_vault` (an MCP tool, not a CLI subcommand) on a vault copy or under `--profile read-only`. Treat any metadata/content normalization findings as a separate scoped decision — do not silently rewrite vault notes during a binary upgrade.
6. Test config parsing with `scripts/probe-config.py` (both isolated cache and, if relevant, a disposable copy of the existing cache). Keep production-config probes strictly read-only (`list_vaults`, one `read_note`, `vault_health`).

## 4. Check configuration deltas

Run `references/wf-turbovault-config.md` §1–2 against the new binary:

- Confirm client `args` match the new `turbovault --help`; keep optional plugin evaluation (`vector_search`) separate from the base upgrade.
- Confirm `tool_visibility` (`show_advanced_tools: true`, and configured `disabled` entries per `references/vault-configuration.md` §4) and explicit `is_default` flags + vault order.
- Compare live `tools/list` against the expected count for the build and visibility policy — "connected" does not prove tool completeness.

## 5. Migrate the skill library in the same change (when tools change)

- Build any tool rename map from measured before/after `tools/list` outputs, not changelog prose.
- Update affected skills across all roots (repo checkouts, profile-local skills, `external_dirs`) respecting `skill-governance` locks; sweep for collapsed duplicate names (e.g. `` `X`/`X` ``) and guard against cross-domain name collisions.
- Verify behavioral claims (accepted parameters, defaults, response shapes) directly against the candidate binary over stdio JSON-RPC on the throwaway vault.

## 6. Reload and re-verify live

- `hermes mcp test turbovault` opens a fresh process and sees the new binary immediately, while an existing session keeps its cached child until reloaded.
- Reload the owning MCP binding (`/reload-mcp` where supported). Do not assume a new chat or config edit reloads a cached connection.
- **Never restart gateway/dashboard yourself:** each service owns its own child process, and restarting kills the active turn. Hand the user restart instructions for every affected service and continue verification on the next turn.
- After restart, verify the live session's negotiated server version, `list_vaults` (`data.active_vault`, `data.vaults`), `list_vaults(name: "<vault>")` (`data.config`), `get_vault_context`, and a read-only smoke check. Report staged artifacts, installed binaries, running process state, and executed tests separately.
