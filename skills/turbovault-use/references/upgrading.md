# Upgrading the TurboVault Server

Do this when a release replaces the installed `turbovault` binary. The binary swap is the small half: the skill library names this server's tools in prose and code blocks, and a renamed tool leaves those files as live instructions that fail. Ship the binary change and the skill migration as one change.

When the user asks for a migration **plan**, deliver the plan read-only without replacing binaries, editing runtime configuration, or restarting services — planning is not deployment authorization.

## 1. Measure the current tool surface before touching anything

- Record `turbovault --version` and the tool list the running server exposes (the live session's tools, or the count `hermes mcp test <server>` reports).
- Compare the installed binary, the running MCP process and its owner, the persisted `--config` YAML, and the live registry; report discrepancies before proposing changes.
- Plan against measured lists, not against release notes or someone else's upgrade analysis. A prebuilt release archive ships every feature; a source build from `cargo install turbovault` without `--features release` has no HTTP/WebSocket/TCP transports, no SQL, and no vector plugin, so it exposes a different tool set than the archive you would otherwise install.

## 2. Install with a rollback path

- Verify the asset against the release's `SHA256SUMS` before installing.
- Match the asset's OS and CPU architecture first, then check libc compatibility on Linux: `linux-gnu` builds require current glibc (e.g. `GLIBC_2.38`), so an older distribution needs the matching static `linux-musl` build. Run the staged binary's `--version` before moving it into place.
- Archive the existing executable under a versioned path (e.g. `~/.local/share/turbovault/<old-version>/turbovault`), recording its version, SHA-256 checksum, and archive path. Pair it with backups of the affected configuration files (`--config` YAML and client MCP server config) and server state files (registry cache, `operations.jsonl` per vault) so rollback restores both the binary and its startup contract. Distinguish planned archives from archives actually created.
- Overwriting the installed binary while a server process is running is safe — the process keeps its loaded inode — but the swap stays invisible to that process and its clients until the binding is restarted. The snapshot also covers the reverse case: an older binary reading state the newer one wrote is only as safe as the state format.
- **On macOS, do not `cp` over the installed binary — move the old one aside and copy to a fresh path.** Copying onto the existing file keeps its inode, and macOS then kills every start with `Killed: 9` (exit 137) while the identical bytes run fine from a scratch directory: the code-signature decision is cached per inode, not per content. `mv ~/.local/bin/turbovault ~/.local/bin/turbovault.old && cp <staged> ~/.local/bin/turbovault` produces a new inode and starts normally. Keep the versioned rollback copy anyway, because the file you just moved aside holds the *new* bytes, not the old ones.

## 3. Check configuration and post-update deltas

- Separate client MCP launch arguments from TurboVault YAML settings. Propose only parameter changes supported by the target release's `--help` output or schema — a binary upgrade does not by itself require new client arguments. Keep optional plugin evaluation (`vector_search`) separate from the base migration.
- Run `references/wf-turbovault-config.md` §1–2 against the new binary to verify `--config`, `env.XDG_CACHE_HOME`, `tool_visibility` (`show_advanced_tools: true` and `disabled: [fanout, list_orphan_fanouts]`), and required `is_default` flags.
- Expect both silent and loud failures from the YAML file: unknown keys inside a `vaults` entry are ignored without a message, while a missing required field stops startup (`vaults[1]: missing field 'is_default'`), and an unknown key under `security` stops startup. Start the new binary once against the config (`scripts/probe-config.py`) and read the output instead of guessing.
- Do not treat the YAML alone as an exclusive registry or proof of active selection when cache state is shared: test both a clean cache and an isolated copy of the relevant existing cache (`references/vault-configuration.md`).
- Compare discovered `tools/list` names against the expected surface for the build and configured `tool_visibility` policy (`show_advanced_tools: true` exposes 22 additional tools minus any explicitly disabled entries). A client reporting "connected" does not establish completeness.

## 4. Validate vault content before the swap

- `validate_vault` is an **MCP tool**, not a CLI subcommand — the binary takes options only. Run it over a vault copy or under a read-only profile, and keep its findings as a separate decision: content rewrites (pre-1.9 `tags`/`aliases`/`cssclasses` forms, unparsable frontmatter, link style) do not belong inside the binary upgrade.

## 5. Verify the new server standalone before reloading

- `hermes mcp test <server>` opens a fresh client connection, so it sees the new binary immediately while the running session's cached child still serves the old one. It proves connection and tool count — nothing more; it runs no vault call.
- Start the binary once against the real config (`--profile <name>`, `--config <path>`) and check `list_vaults`, one read and a health call before wiring it into any client. Keep this production-config probe read-only; perform lifecycle writes only through the separately verified disposable connection.
- For the disposable lifecycle probe, isolate `HOME` and the working directory as well as the vault, because registry restoration can otherwise redirect a scratch-config test. Confirm the absolute target through that same connection, then create collision-checked target and source fixtures with both a wikilink and an inline Markdown link. Read the target's current hash, perform a guarded edit, move it with `update_backlinks: true`, and read back the target and source links. Delete only those fixtures with explicit `confirm_path`, then verify their absence and removal of test references. Use the configured backend and report only the link forms actually exercised; a successful lifecycle probe does not certify every backend or reference syntax.

## 6. Migrate the skill library in the same change

- Build the rename map from the measured before/after tool lists; changelog prose is not a mapping.
- Codemod every skill that names an old tool, in every location the library spans (repo checkouts, profile-local `skills/`, `external_dirs`), then sweep for artifacts of collapsed names: wherever two old names map to one new name, literal pairs like `` `X`/`X` `` or `` `X`, `X` `` land in the edited prose.
- Watch cross-domain collisions: an old bare name may belong to a different tool family (a provider's own search tools, for instance). Scope the codemod by domain and restore collateral files rather than deleting that family's references.
- Audit last: every `mcp_<server>_*` token must exist in the new tool list, and old names may survive only as deliberate migration notes that name their replacement.
- A name audit is not enough: prose claims about **behavior** go stale too — which operations a tool accepts, which flags are required, what a response contains. Verify each such claim against the new binary by driving it directly over stdio JSON-RPC against a throwaway vault (fake `HOME` so no real registry or config is touched, `--vault` pointing at a scratch directory), one probe per claim. Changelog prose and another installation's analysis are hypotheses; only the probe settles the claim.

## 7. Reload and re-verify live

- Reload the MCP binding in the process that owns it. Use `/reload-mcp` where the client supports it (e.g. TUI); do not assume a new chat or a config watcher will reload a cached connection. The Desktop command can be unavailable even when the command registry lists it as advanced; if the surface does not expose a working reload, ask the user to restart the owning service. Verify the actual session after reload.
- Never restart gateway/dashboard yourself to force the swap: each service spawns its own server child, so restarting only one leaves the other surface on the old binary, and the restart kills your in-flight turn. Hand the user the restart for every affected service and continue verification on the next turn.
- After the reload, repeat the step-5 probes through the live session's own tools, verify the negotiated server version and response shapes (`list_vaults` `data.active_vault` and `data.vaults` — do not require `data.config`, which an unfiltered response may omit), and complete the post-update check in `references/wf-turbovault-config.md`. Label read-only smoke tests as such; a tool count or optional field alone does not establish the exact running version.
