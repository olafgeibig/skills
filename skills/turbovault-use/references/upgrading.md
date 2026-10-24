# Upgrading the TurboVault Server

Do this when a release replaces the installed `turbovault` binary. The binary swap is the small half: the skill library names this server's tools in prose and code blocks, and a renamed tool leaves those files as live instructions that fail. Ship the binary change and the skill migration as one change.

## 1. Measure the current tool surface before touching anything

- Record `turbovault --version` and the tool list the running server exposes (the live session's tools, or the count `hermes mcp test <server>` reports).
- Plan against those measured lists, not against release notes or someone else's upgrade analysis. A prebuilt binary ships every feature since 3.1.0; a source build from `cargo install turbovault` without `--features release` has no HTTP/WebSocket/TCP transports, no SQL and no vector plugin, so it exposes a different tool set than the archive you would otherwise install.

## 2. Install with a rollback path

- Verify the asset against the release's `SHA256SUMS` before installing.
- Match the asset's OS and CPU architecture first, then check libc compatibility on Linux: the `linux-gnu` builds need glibc 2.38 or newer (4.0.2 requires `GLIBC_2.38`), so an older distribution needs the matching `linux-musl` build, which is static. Run the staged binary's `--version` before moving it into place.
- Keep the old binary runnable under a versioned path (e.g. `~/.local/share/turbovault/<old-version>/turbovault`) and snapshot the server's state files (vault registry, `operations.jsonl` per vault) beside it.
- Overwriting the installed binary while a server process is running is safe — the process keeps its loaded inode — but the swap stays invisible to that process and its clients until the binding is restarted. The snapshot also covers the reverse case: an older binary reading state the newer one wrote is only as safe as the state format.

## 3. Put configuration in one file, and expect two failure modes

- When the release reads `~/.turbovault/config.yaml`, register the vaults there instead of in per-client `args` flags: one source of truth survives client restarts. Naming the file in `args` (`--config <path>`) is fine — it pins which file is read without duplicating registration data. Details in `vault-configuration.md`.
- Expect both silent and loud failures from the same file: unknown keys inside a `vaults` entry are ignored without a message, while a missing required field stops startup (`vaults[1]: missing field 'is_default'`). Start the new binary once against the migrated config and read the error instead of guessing.
- Declare intended vaults in the file, but do not treat it as an exclusive registry or proof of active selection: the server also restores per-project cache state keyed by its **working directory**. Test clean-cache startup and startup with an isolated copy of the relevant existing cache; compare the full name/path mapping, runtime default flags, and active vault. See `vault-configuration.md` for the registry and cache checks.
- Check the advanced tools explicitly: a major release may leave tools out of `tools/list` unless a visibility setting enables them (4.0 hides 22 behind `tool_visibility.show_advanced_tools: true`). Compare discovered names against the expected surface for the build and configured visibility policy, accounting for deliberately disabled tools. The release's unfiltered total is not the configured expected count; a client reporting "connected" does not establish completeness.

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

- The session's tool surface changes only when the MCP binding reloads or a new session starts, and which reload exists depends on the client surface. TUI: `/reload-mcp`; the `mcp_servers` section of `config.yaml` is also polled there and reloads on change. Hermes Desktop: its slash-command registry hides commands with no desktop surface, and a config change there does not rebind the running session — restarting the services is the reliable path.
- Never restart gateway/dashboard yourself to force the swap: each service spawns its own server child, so restarting only one leaves the other surface on the old binary, and the restart kills your in-flight turn. Hand the user the restart for every affected service and continue verification on the next turn.
- After the reload, repeat the step-5 probes through the live session's own tools and compare the negotiated server version plus measured response shapes. For v4, inspect `list_vaults.data.active_vault` and `data.vaults`; do not require `data.config`, which an unfiltered response may omit. A tool count or optional field alone does not establish the exact running version.
