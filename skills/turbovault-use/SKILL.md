---
name: turbovault-use
description: "Use when operating Obsidian vaults through TurboVault."
metadata:
  version: "0.8.0"
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
- Vault note reads and writes go through TurboVault (`read_note`, `write_note`, `edit_note`, `move_note`, `delete_note`). A missing tool is a blocker, not a reason to write the file directly. Do not substitute `write_file`, `patch`, or `terminal`.
- A failed TurboVault call — including a malformed `edits`/content payload that cannot be encoded in the tool call — is not a licence to switch tools: fix the payload and retry the same TurboVault tool (`write_note` with `mode=overwrite` after a `read_note`, or `edit_note` with smaller SEARCH/REPLACE blocks).
- **Anchor `edit_note` blocks on complete lines.** The tool falls back to fuzzy (Levenshtein) matching when an exact match fails, and a fuzzy match that catches only the *prefix* of a line replaces the prefix while **concatenating the remainder of the old line onto your new text**. Seen twice in practice: a date became `2026-10-019`, and a MoC bullet ended up carrying two descriptions glued together. So pull the whole line into SEARCH (or several whole lines), and after any `edit_note` whose response reports fuzzy matching, read the touched region back and confirm no orphaned tail remains.
- **Keep the `=======` separators out of the payload text.** A stray marker copied into the REPLACE half is not a syntax hint, it is content: it gets written into the note verbatim, where it shows up as `=======### Next Heading` and silently breaks heading parsing — entries look deleted (`^### ` counts drop) even though every line is still there. Check any multi-block edit with `grep -c '^======='` on the file plus a heading count before/after; a count that fell while the byte size grew is this bug, not data loss.
- **Out-of-band writes leave the link index stale.** A note created or edited with `write_file`/`patch` is readable through TurboVault but its edges are not extracted: `get_backlinks` on the new note returns empty and the linking note's `get_forward_links` silently omits it, so `success: true` on the surrounding edits looks correct while the graph does not connect. Repair by writing through TurboVault once (e.g. `edit_note`, or `update_frontmatter` with a merge) and then re-check `get_backlinks` — link extraction happens on the TurboVault write pass, not on read.
- The only terminal exception is bulk removal of an entire wiki directory (`rm -rf`), named in vault-wiki under archiving, because `delete_note` confirms per file. Do not extend that exception to ordinary note edits.
- Set fields and write modes explicitly.
- Preserve unrelated content.
- Use the `direct` write backend by default. Do not enable `write_backend: git` or call Git fan-out tools unless the user explicitly authorizes it for the named vault after external-sync compatibility review and testing on a copy.
- Never assume `batch_execute` is atomic. The Direct backend is sequential and fail-fast; completed operations are not rolled back. Claim all-or-nothing only when the selected backend's documented transaction contract guarantees it.
- Keep read-before-write for content context. For existing notes, use the current `expected_hash` from `read_note` or an `edit_note` dry run; do not send the removed `force` argument or use a blind overwrite without explicit user authorization.
- Treat `vector_search` as optional. Configure a local compatible model and remember that one engine per process is bound to the vault active when first built; do not assume it follows later vault switches.
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
| Multi-file batches | `batch_execute` (transaction guarantee depends on backend) |
| Frontmatter | `inspect_frontmatter`, `get_metadata_value`, `search_by_frontmatter`, `update_frontmatter` |
| Full-text and semantic discovery | `search`, `advanced_search`, `semantic_search`; optional `vector_search_search` |
| Graph traversal | `get_forward_links`, `get_backlinks`, `get_related_notes` |
| Structural analysis | `get_broken_links`, `get_dead_end_notes`, `get_isolated_clusters`, `detect_cycles` |

Use the exact tool names exposed in the current session; MCP prefixes may differ between clients.

Deferred tools: call through `tool_call` with both `name` and `arguments` on every entry, and run `tool_describe` before first use. Parameter names are exact and snake_case — `read_note` takes `path`; `edit_note` takes the SEARCH/REPLACE blocks as a single `edits` string.

**Pass `calls` as a real array, never as a JSON string.** The bridge tolerates a stringified envelope (it parses it and reports `tool_call 'calls' is not valid JSON: ...` on failure — see `tools/tool_search_validation.py`), but a long, quote-heavy note body then has to survive two levels of quoting, and one slip invalidates the whole payload before any MCP call:

- the failure is caught by Hermes's own argument validation, so the tool is never invoked — no server-side symptom to diagnose, and retrying the identical payload reproduces nothing;
- keep single-payload writes moderate: write the skeleton first and add the long sections as separate `edit_note` blocks instead of one 15 KB content string full of escaped quotes and `"*..."*` emphasis;
- on this failure, fix the payload and re-issue the *same* TurboVault tool. Switching to `write_file`/`patch` trades an encoding error for a stale link index (see the out-of-band write rule above).

### Paths

- `mcp_turbovault_*` tools take full vault-relative paths, including the `area/<folder>/` prefix — not bare filenames. If `search_files` on vault-relative paths returns 0 hits, retry with absolute paths or use the SQL/frontmatter query tools.
- In-process tools (`read_file`, `write_file`, `patch`) require absolute filesystem paths. Never swap the two conventions: a vault-relative path passed to `patch` fails path resolution.

## Route to the Right Reference

| Task | Reference |
|---|---|
| Install, register, activate, or diagnose basic availability | `references/vault-configuration.md` |
| `edit_note`, full writes, or multi-file batches | `references/editing-and-batch-operations.md` |
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
4. For batch operations, verify every intended target and explicitly resolve or report partial state.
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
