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

## Source freshness

Content-freshness policy belongs to the workflow that owns the source, such as `vault-wiki`. TurboVault provides retrieval and hashing inputs but does not define when a source should be re-ingested.
