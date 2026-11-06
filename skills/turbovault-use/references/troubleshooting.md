# TurboVault Troubleshooting

## Runtime availability versus session exposure

Distinguish two layers:

1. Profile/runtime availability: the MCP server is configured and reachable.
2. Session exposure: the current chat has callable TurboVault tools.

If `list_vaults` is unavailable, check the current Hermes MCP configuration and connection before declaring TurboVault disconnected. If runtime checks pass, reload the MCP/session binding or start a fresh session.

## A failed spawn is parked, not retried

When a server fails its first connection three times the MCP manager parks it: `agent.log` and `errors.log` carry `failed initial connection after 3 attempts, parking until a reconnect is requested (state: connecting → parked)`. Parking is sticky. Correcting the config afterwards does not revive the server and nothing retries on its own, so the session keeps running without the tools and a landed fix looks ineffective. The order is two steps: fix the config, then restart the process that owns the MCP server (`hermes gateway restart` — not the desktop app, not the MCP child). Verify from `MCP server 'turbovault' (stdio): registered N tool(s)` in `agent.log`, never from the config read-back.

The usual reason a spawn never gets off the ground is the `env` block: Hermes validates MCP `env` values as strings, so an unquoted YAML `1` or `true` fails with `StdioServerParameters … Input should be a valid string`, and quoting the value yields a literal `"1"` that Clap then rejects on the flag. Put such a switch in `args` (`--no-confirm-destructive`) instead of encoding it as an environment variable, and do not "repair" a quoting mistake by quoting harder — remove the `env` key.

## A tool the skill names is missing

`tools/list` is the whole contract: a tool that is not listed cannot be called in that session, even though the server has it. TurboVault 4.0 leaves 22 advanced tools unlisted by default (`inspect_frontmatter`, `query_frontmatter_sql`, `audit_log`, `export`, `compare_notes`, `find_duplicates`, `find_stale_notes`, `suggest_links`, `note_quality`, `analyze_grounding`, `rollback_*`, `move_file`, `diff_notes`, `fanout`, …). Enable them with `tool_visibility.show_advanced_tools: true` in `~/.turbovault/config.yaml` (or `--show-advanced-tools`). A running session picks the change up through the MCP config watcher; surfaces differ in whether a manual reload command exists (the canonical `/reload_mcp` has no Desktop surface), so verify the new surface with `tool_search`/`list_vaults` instead of hunting for a reload. Do not conclude the server is old or broken before checking that setting.

## Reaching the server when the session has no TurboVault tools (mcporter bridge)

Runtime is healthy, the process runs, the YAML is correct — but this session exposes no `mcp_turbovault_*` tools and a reload is not available without restarting the user's gateway. Do not fall back to `write_file`/`patch`. Bridge to the same server through `mcporter`; it is a client, so writes still carry the server's hash guards and audit entries, and the profile config still decides which vaults are reachable.

```bash
# one-time: put the server in mcporter's config (edit the JSON directly, see below)
cat "$HOME/.mcporter/mcporter.json"   # {"mcpServers":{"turbovault":{...}}}

# then every call is plain
mcporter call turbovault.read_note  vault=<vault> path="projects/x/note.md" --output json
mcporter call turbovault.write_note  vault=<vault> path="projects/x/note.md" \
  mode=overwrite expected_hash=<hash> content=@/abs/path/new-body.md
mcporter call turbovault.edit_note   vault=<vault> path="projects/x/note.md" \
  expected_hash=<hash> edits=@/abs/path/edits.txt
```

- **Write the server entry into `$HOME/.mcporter/mcporter.json` directly.** `mcporter config add … --arg …` does not persist the args (the entry lands as `{"command": …}` only), and a dropped `--config` then makes the server exit with `error: unexpected argument '/path.yaml' found`. The shape that works:
  `"turbovault": {"command": "/Users/<user>/.local/bin/turbovault", "args": ["-p", "production", "--config=/Users/<user>/.turbovault/<profile>.yaml"], "env": {}}`
- **Use `--config=<path>`, not `--config <path>`**, and never the ad-hoc `--stdio`/`--stdio-arg` flags for a `call`: `--stdio` swallows the next token (`ENOENT …/--stdio-arg`) and `--stdio=` is rejected as an unknown tool argument because the selector has no schema yet.
- **Pass multi-line payloads as `key=@file`**, which reads a UTF-8 string from disk — the clean route for a whole note body and for SEARCH/REPLACE blocks, without nested JSON quoting.
- **Read the response at the right depth**: `{vault, operation, success, data: {path, content, hash}}` and `{…, data: {old_hash, new_hash, blocks_applied, total_blocks}}`. The flat `result.hash` of the MCP tool surface does not exist here, so a naive `d['hash']` reads `None` and looks like a broken read.
- Keep the destructive gate on: do **not** add `--no-confirm-destructive` just because it is convenient for a bridge session.
- Verify the reachable vault set first (`mcporter call turbovault.list_vaults`) and compare it with the profile's YAML — a bridge that resolves to another profile's config is exactly the access-boundary leak the per-profile config exists to prevent.

## No active vault

If tools exist but operations report no active vault:

1. list registered vaults;
2. select the intended vault explicitly;
3. verify with `get_vault_context`.

Do not guess among multiple vaults.

## Empty vault registry after a restart or model switch

If `list_vaults` returns an empty list (or `set_active_vault` reports "not found") although the vault worked earlier in the session, the server's in-memory registry was reset — the files on disk are untouched. Re-register immediately with `add_vault(name, path)` (the path must be absolute) instead of waiting out a cooldown; then `set_active_vault(name)` and verify with one read.

Do not fall back to terminal file access, and do not tell the user the vault is broken. If `add_vault` fails with a server-unreachable error, the server is still initializing — wait ~50s and retry (reconnect backoff).

## Reconnect churn and subprocesses

Repeated keepalive failures, reconnect messages, or multiple TurboVault processes are Hermes/MCP runtime symptoms, not vault-content problems.

- Inspect the owning Hermes process and parent-child relationships.
- Do not classify every TurboVault process as stale.
- Do not kill processes or restart a gateway without authorization.
- Use the relevant Hermes gateway or MCP troubleshooting skill for detailed diagnosis.
- After recovery, prove tool-call health from a fresh session.

## Stale Obsidian display

If a verified file exists but is absent from Obsidian's file tree, the UI index may be stale. Read the target through TurboVault first. If the write is confirmed, ask the user to refresh Obsidian; do not rewrite the file merely to force display.

## Editing errors

For SEARCH/REPLACE parse or match errors, load `references/editing-and-batch-operations.md`. Do not retry an unchanged malformed edit repeatedly.

A `Concurrent access conflict: File does not exist` on an `append` or `prepend` write is not a race: those modes do not create a note. Write it with `overwrite` first.

## Log-based diagnosis when the user is skeptical

When the user says a tool "always worked" and asks you to check the logs, drop into log-based diagnosis — do not speculate or re-run the failing call. Inspect the profile's own log directory, `<profile home>/logs/` (default profile: `~/.hermes/logs/`): `mcp-stderr.log` for TurboVault's spawn output, `agent.log` for the `registered N tool(s) from M server(s) (1 failed: …)` summary, `errors.log` for crash and parking lines. Grep the tool name and recent timestamps, read the actual error, then propose the fix. `hermes mcp test turbovault` is the independent check that separates a broken config from a broken session.

The MCP transport is stdio — there is no port to probe (`ps` and log tails, not network checks). An `Io(NotFound)` line is a caller-side path-resolution error: fix the vault-relative path (full `area/<folder>/` prefix), not the server.

## Source freshness

Content-freshness policy belongs to the workflow that owns the source, such as `vault-wiki`. TurboVault provides retrieval and hashing inputs but does not define when a source should be re-ingested.
