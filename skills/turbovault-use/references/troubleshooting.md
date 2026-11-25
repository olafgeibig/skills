# TurboVault Troubleshooting

Read this when TurboVault **exists but misbehaves at runtime** — missing session tools, failed/parked spawns, reconnect churn, stale Obsidian UI, or log diagnosis.

- For config setup, audits, post-update checks, or default repair: `references/wf-turbovault-config.md`.
- For declarative YAML schema and cache precedence: `references/vault-configuration.md`.
- For binary upgrades and reload mechanics: `references/wf-upgrading.md`.

## 1. Runtime availability vs. session exposure

Separate two layers before diagnosing:

1. **Profile/runtime availability:** TurboVault is configured and reachable (`hermes mcp test turbovault` succeeds).
2. **Session exposure:** the active conversation has callable TurboVault tools.

If `list_vaults` is missing in the session while `hermes mcp test turbovault` passes, reload the owning MCP binding (`references/wf-upgrading.md` §6) — a fresh chat can still reuse an old connection. Never declare TurboVault disconnected when only session exposure is missing.

## 2. Failed spawns are parked, not retried

After three failed initial connection attempts, Hermes parks the MCP server (`agent.log` / `errors.log`: `failed initial connection after 3 attempts, parking until a reconnect is requested (state: connecting → parked)`). Parking is sticky — fixing the config alone does not revive the server.

1. Fix the root cause in config.
2. Restart the owning Hermes service (e.g. `hermes gateway restart` — not the desktop UI and not the MCP child).
3. Verify from `MCP server 'turbovault' (stdio): registered N tool(s)` in `agent.log`, not from config read-back.

**Most common spawn cause (`env` typing):** Hermes validates MCP `env` values as strings. An unquoted YAML `1` or `true` fails with `StdioServerParameters ... Input should be a valid string`, while quoting it passes literal `"1"` that Clap rejects on boolean flags. Move boolean/switch flags (`--no-confirm-destructive`, `--show-advanced-tools`) to `args` and delete the `env` key instead of quoting harder.

## 3. A named tool is missing from `tools/list`

A tool absent from `tools/list` cannot be called through deferred tool discovery even when the binary implements it. TurboVault omits 22 advanced tools by default. Check `tool_visibility` (`show_advanced_tools: true`, `disabled`, `allowed`, `require_read_only`) in the active `--config` YAML before concluding the server is outdated or broken (`references/vault-configuration.md` §4).

## 4. Bridging with `mcporter` when the session has no TurboVault tools

If runtime is healthy and a reload is unavailable without interrupting the user's gateway, bridge through `mcporter` instead of falling back to `write_file`/`patch`. `mcporter` is an MCP client, so writes retain hash preconditions and audit logging.

```bash
# Inspect registered vaults first — confirm the bridge targets the exact profile config
mcporter call turbovault.list_vaults --output json

# Read / write / edit (pass multi-line bodies and SEARCH/REPLACE blocks via @file)
mcporter call turbovault.read_note vault=<vault> path="projects/note.md" --output json
mcporter call turbovault.write_note vault=<vault> path="projects/note.md" \
  mode=overwrite expected_hash=<hash> content=@/abs/path/body.md
mcporter call turbovault.edit_note vault=<vault> path="projects/note.md" \
  expected_hash=<hash> edits=@/abs/path/edits.txt
```

`mcporter` pitfalls:

- **Edit `$HOME/.mcporter/mcporter.json` directly:** `mcporter config add ... --arg ...` drops args; write the exact `command`, `args` (mirroring the profile's own launch flags, including `-p production` and `--config=<path>`), and `env` (`XDG_CACHE_HOME`) directly. Do not alter safety flags opportunistically — match the profile's authorized MCP launch entry.
- **Use `--config=<path>` (equals sign)** and avoid ad-hoc `--stdio`/`--stdio-arg` on `mcporter call`.
- **Use `key=@/abs/path`** for multi-line `content` and `edits` to avoid nested JSON escaping.
- **Response nesting:** `mcporter` returns the full envelope `{vault, operation, success, data: {path, content, hash}}`; read `data.hash` / `data.new_hash`, not a top-level `hash`.

## 5. Empty registry, wrong vault, or reconnect churn

- **No active vault / unexpected default:** Call `list_vaults`, pass `vault: "<name>"` explicitly on scoped calls, and use `references/wf-turbovault-config.md` §4–5 to diagnose or repair a persisted default.
- **Empty registry after restart:** Do not assume data loss — inspect `--config` and `XDG_CACHE_HOME` / CWD cache (`references/wf-turbovault-config.md` §1) before calling `add_vault`.
- **Reconnect churn & multiple subprocesses:** Inspect parent-child ownership (`ps -eo pid,ppid,etime,args | grep '[t]urbovault'`). Multiple services (gateway, dashboard, CLI) legitimately spawn their own children; never kill processes or restart services without authorization.

## 6. Stale Obsidian display & write errors

- **Stale Obsidian UI:** If `read_note` confirms the file exists on disk, ask the user to refresh Obsidian — do not rewrite the note merely to trigger UI refresh.
- **Editing / SEARCH-REPLACE errors:** Load `references/editing-and-mutations.md`; never retry an unchanged malformed edit.
- **`Concurrent access conflict: File does not exist`:** Caused by `write_note` with `mode: append|prepend` on a non-existent path; create with `mode: overwrite` first.
- **`Io(NotFound)` in logs:** Caller passed a bare filename or wrong vault-relative path; pass the full vault-relative path including folders and `.md`.

## 7. Log-based diagnosis

When a tool fails unexpectedly (or the user reports it previously worked), inspect logs before guessing or re-running failing calls:

- Profile log directory: `<profile-home>/logs/` (`~/.hermes/logs/` for the default profile).
  - `mcp-stderr.log`: TurboVault's own stderr (startup, cache init, config errors, skipped notes).
  - `agent.log`: MCP tool registration summary (`registered N tool(s) from M server(s)`).
  - `errors.log`: spawn crashes and parking transitions.
- Stdio transport has no TCP port — diagnose with `ps`, log tails, and `hermes mcp test turbovault` (which separates broken config from a broken session).
