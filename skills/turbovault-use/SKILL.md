---
name: turbovault-use
description: "Use when operating Obsidian vaults through TurboVault."
metadata:
  version: "0.7.0"
  source: https://github.com/olafgeibig/skills
  hermes:
    tags:
      - turbovault
      - mcp
      - vault
      - tools
      - obsidian
    related_skills:
      - vault-ops
      - vault-wiki
---

# TurboVault Use

Use TurboVault MCP safely as the tool layer for Obsidian vault operations.

Division of responsibility:

- `turbovault-use` owns tool mechanics, selection, editing, search, graph operations, and troubleshooting.
- `vault-ops` owns generic vault structure, notes, MoCs, tasks, and navigation.
- `vault-wiki` owns domain-wiki architecture, ingest, query, source, and lint workflows.

## When to Use

Load this skill whenever a task calls TurboVault tools or another skill enters a TurboVault-backed operation.

## Establish Availability

Start with `list_vaults`.

- Success, including an empty list, proves the tool is exposed in this session.
- An empty list after an MCP restart or model switch means the in-memory registry was reset: re-register with `add_vault` immediately instead of waiting out a cooldown or retrying.
- A missing tool does not prove the configured MCP server is unavailable.
- Distinguish profile/runtime availability from current-session tool exposure.
- If runtime checks pass but tools are absent, reload the MCP/session binding or start a new session.
- If runtime checks fail, load `references/vault-configuration.md`.

Do not describe TurboVault as disconnected when only the current session lacks its tool surface.

## Select the Vault

Use this order:

1. A vault explicitly named by the user.
2. The only registered vault.
3. A vault established earlier in the same conversation.
4. The currently active vault after verifying it with `get_vault_context`.
5. If ambiguity remains, ask; do not guess.

Registration and activation are separate operations. For existing-vault setup, use `references/vault-configuration.md`.

## Core Safety Rules

- Read the vault's `AGENTS.md` before structural or content changes.
- Read a note before editing it.
- Use TurboVault for external vault files when its tools are available; do not silently substitute filesystem writes.
- Do not use `terminal` or `python3 -c` for vault edits — use the in-process tools (`read_file`, `write_file`, `patch`); keep `terminal` for installs, git, and system work.
- Set fields and write modes explicitly.
- Preserve unrelated content.
- Prefer atomic batch operations when partial writes would leave the vault inconsistent.
- Verify external writes by reading the exact target and checking the resulting links or metadata.
- Inspect backlinks before moves or deletions.
- Do not assume a move updated every inbound path, alias, heading anchor, or plain-text reference.

Before the first write of a session, orient explicitly:

- Confirm the active vault with `get_active_vault` and `get_vault_context`; with multiple vaults, `set_active_vault` explicitly and re-confirm.
- Check existence before creating (`search`, `get_metadata_value`).
- Probe liveness with a trivial call (`get_active_vault`) when a tool seems dead.
- Never claim success without a tool response — cite the response or the resulting path in the same reply.
- Treat `success: true` as unproven until checked: it can mean (A) nothing was written, (B) the write landed in the wrong vault, or (C) the report was confabulated.

## Core Tools

| Operation | Tool family |
|---|---|
| Read and write notes | `read_note`, `write_note`, `edit_note` |
| Register and select vaults | `list_vaults`, `add_vault`, `set_active_vault`, `get_vault_context` |
| Move or delete notes | `move_note`, `delete_note` |
| Atomic multi-file updates | `batch_execute` |
| Frontmatter | `inspect_frontmatter`, `get_metadata_value`, `search_by_frontmatter`, `update_frontmatter` |
| Full-text discovery | `search`, `advanced_search`, `semantic_search` |
| Graph traversal | `get_forward_links`, `get_backlinks`, `get_related_notes` |
| Structural analysis | `get_broken_links`, `get_dead_end_notes`, `get_isolated_clusters`, `detect_cycles` |

Use the exact tool names exposed in the current session; MCP prefixes may differ between clients.

Deferred tools: call through `tool_call` with both `name` and `arguments` on every entry, and run `tool_describe` before first use. Parameter names are exact and snake_case — `read_note` takes `path`; `edit_note` takes the SEARCH/REPLACE blocks as a single `edits` string.

### Paths

- `mcp_turbovault_*` tools take full vault-relative paths, including the `area/<folder>/` prefix — not bare filenames. If `search_files` on vault-relative paths returns 0 hits, retry with absolute paths or use the SQL/frontmatter query tools.
- In-process tools (`read_file`, `write_file`, `patch`) require absolute filesystem paths. Never swap the two conventions: a vault-relative path passed to `patch` fails path resolution.

## Route to the Right Reference

| Task | Reference |
|---|---|
| Install, register, activate, or diagnose basic availability | `references/vault-configuration.md` |
| `edit_note`, full writes, or atomic batches | `references/editing-and-batch-operations.md` |
| Full-text, frontmatter, SQL, or graph discovery | `references/search-and-graph.md` |
| Rename, move, or structural refactor | `references/renames-and-refactors.md` |
| Apply templates or normalize frontmatter | `references/frontmatter-and-templates.md` |
| Missing tools, stale UI, reconnect churn, or process symptoms | `references/troubleshooting.md` |

Do not load every reference for routine reads.

## Verification

After a write:

1. Read the exact target.
2. Confirm expected frontmatter and body changes.
3. For structural operations, check backlinks and broken links.
4. For batches, confirm every intended target and the absence of partial state.
5. Report unresolved warnings or client refresh requirements honestly.

Tool responses are the primary verification — trust a mutating call's response as the first-line signal, and never delegate a verification read to a subagent; delegation adds no signal over a direct call. Direct read-back of the exact target (steps 1-4 above, performed as plain tool calls) stays the reserved check for silent-success-risk writes: first writes in a session, registry/state changes, and structural operations. The stricter per-operation read-backs in `references/editing-and-batch-operations.md` §Verification (external-state claims, fuzzy-matched blocks) remain in force.

## Improvement Routing

This is an owned generic skill. Follow `skill-governance`:

- generic TurboVault mechanics belong here;
- generic vault structure belongs in `vault-ops`;
- wiki-specific behavior belongs in `vault-wiki`;
- reusable project procedure belongs in the relevant `project-*` skill;
- project facts belong in project content;
- profile quirks belong in profile guidance or a profile-local adaptation.

Update the owning skill only after classification, abstraction, read-before-write, and required approval.
