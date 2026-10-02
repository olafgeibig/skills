# TurboVault Troubleshooting

## Runtime availability versus session exposure

Distinguish two layers:

1. Profile/runtime availability: the MCP server is configured and reachable.
2. Session exposure: the current chat has callable TurboVault tools.

If `list_vaults` is unavailable, check the current Hermes MCP configuration and connection before declaring TurboVault disconnected. If runtime checks pass, reload the MCP/session binding or start a fresh session.

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

## Log-based diagnosis when the user is skeptical

When the user says a tool "always worked" and asks you to check the logs, drop into log-based diagnosis — do not speculate or re-run the failing call. Inspect `~/.hermes/logs/` (`mcp-stderr.log` for TurboVault), grep for the tool name and recent timestamps, read the actual error, then propose the fix.

The MCP transport is stdio — there is no port to probe (`ps` and log tails, not network checks). An `Io(NotFound)` line is a caller-side path-resolution error: fix the vault-relative path (full `area/<folder>/` prefix), not the server.

## Source freshness

Content-freshness policy belongs to the workflow that owns the source, such as `vault-wiki`. TurboVault provides retrieval and hashing inputs but does not define when a source should be re-ingested.
