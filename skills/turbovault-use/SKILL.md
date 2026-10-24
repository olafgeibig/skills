---
name: turbovault-use
description: "Use when operating Obsidian vaults through TurboVault."
metadata:
  version: "0.13.0"
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

Load this skill whenever a task calls TurboVault tools, another skill enters a TurboVault-backed operation, or a task upgrades or replaces the TurboVault server.

## Establish Availability

Start with `list_vaults`.

- A successful response (even one with `vaults: []`) proves the tool is exposed in this session.
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

A **vault-relative path in the request is itself vault evidence.** When the user names a note path (`area/tools/<note>`) and the active vault has no such file, look for it in the other registered vaults (`list_vaults`, then a filename check or `search` per candidate) instead of concluding the note is missing or creating it in the active vault. Once found, pass that vault's name as the `vault` argument on every call and leave the shared active-vault pointer alone.

Registration and activation are separate operations. For existing-vault setup, use `references/vault-configuration.md`.

**Profile-scoped config files are the access boundary.** When profiles on one machine must not see the same vaults, give each its own config (`~/.turbovault/<profile>.yaml`) and start the server with `--config`; a vault absent from that file cannot be addressed by name or path, so the restriction is enforced by the server rather than by instruction. `is_default: true` marks the one vault used without naming it, so a single-vault config needs no `set_active_vault`. Verify what a config really registers — vault names, default flag, tool count — with `scripts/probe-config.py <config.yaml>` before restarting the client with it; that probe is the read-back for the change.

For a temporary lookup in another vault:

1. On v4, prefer the per-call `vault` argument for vault-scoped tools; first confirm the registered name and absolute path with `list_vaults`. This avoids changing a shared active-vault pointer.
2. For pre-v4 tools or registry operations without a `vault` argument, record the original active vault from `list_vaults`, call `set_active_vault` for the lookup target, and confirm its absolute path with `get_vault_context` before reading notes.
3. Keep active-vault-dependent reads within that selection window. Do not batch a switch or restoration in parallel with note reads, because those reads resolve against mutable server state.
4. After the lookup, restore the original selection with `set_active_vault` unless the user requested a lasting switch. Verify restoration with `list_vaults` and `get_vault_context` before claiming it.
5. Distinguish note changes from selection changes in the handoff: report that no note content was edited when appropriate, rather than implying no state changed.

## Core Safety Rules

- Read the vault's `AGENTS.md` before structural or content changes.
- Read a note before editing it.
- Vault note reads and writes go through TurboVault (`read_note`, `write_note`, `edit_note`, `move_note`, `delete_note`). A missing tool is a blocker, not a reason to write the file directly. Do not substitute `write_file`, `patch`, or `terminal`.
- A failed TurboVault call — including a malformed `edits`/content payload that cannot be encoded in the tool call — is not a licence to switch tools: fix the payload and retry the same TurboVault tool (`write_note` with `mode=overwrite` after a `read_note`, or `edit_note` with smaller SEARCH/REPLACE blocks).
- **Anchor `edit_note` blocks on complete lines.** The tool falls back to fuzzy (Levenshtein) matching when an exact match fails, and a fuzzy match that catches only the *prefix* of a line replaces the prefix while **concatenating the remainder of the old line onto your new text**. Seen twice in practice: a date became `2026-10-019`, and a MoC bullet ended up carrying two descriptions glued together. So pull the whole line into SEARCH (or several whole lines). The response never reveals whether a match was exact or fuzzy (it returns only hashes and `blocks_applied`), so after any `edit_note` whose SEARCH is not byte-identical to a complete line, read the touched region back and confirm no orphaned tail remains.
- **Keep the `=======` separators out of the payload text.** A stray marker copied into the REPLACE half is not a syntax hint, it is content: it gets written into the note verbatim, where it shows up as `=======### Next Heading` and silently breaks heading parsing — entries look deleted (`^### ` counts drop) even though every line is still there. Check any multi-block edit with `grep -c '^======='` on the file plus a heading count before/after; a count that fell while the byte size grew is this bug, not data loss.
- **Do not infer graph freshness from readable content.** TurboVault 4.x reconciles external edits before derived reads when `reconcile_external_changes` is enabled; older versions or disabled reconciliation may leave derived results stale. Keep TurboVault as the normal write path for hash guards and audit. If note content and graph results disagree, inspect the setting and verify with `get_links` in both directions; do not infer freshness from `read_note` alone.
- The only terminal exception is bulk removal of an entire wiki directory (`rm -rf`), named in vault-wiki under archiving, because `delete_note` requires a `confirm_path` per file. Do not extend that exception to ordinary note edits.
- Set fields and write modes explicitly.
- Preserve unrelated content.
- Use the `direct` write backend by default. Do not enable `write_backend: git` or call Git fan-out tools unless the user explicitly authorizes it for the named vault after external-sync compatibility review and testing on a copy.
- Never assume `batch_execute` is atomic. The Direct backend is sequential and fail-fast; completed operations are not rolled back. Claim all-or-nothing only when the selected backend's documented transaction contract guarantees it.
- Keep read-before-write for content context. For existing notes, use the current `expected_hash` from `read_note` or an `edit_note` dry run; do not send the removed `force` argument or use a blind overwrite without explicit user authorization. An `expected_hash` mismatch is not proof of a concurrent edit — the hash can move while the visible content is unchanged: re-read the note once and retry with the fresh hash; treat only a second mismatch as a real conflict.
- Treat `vector_search` as optional, compiled-in and off unless `--plugins vector_search` names it. It needs a local Model2Vec model and one engine per process is bound to the vault active when first built; do not assume it follows later vault switches. Enablement, config keys, index location and verification: `references/vector-search.md`.
- Verify external writes by reading the exact target and checking the resulting links or metadata.
- Inspect backlinks before moves or deletions. On Direct, explicitly pass `move_note(update_backlinks: true)` to request inbound-link rewriting and inspect `link_sources_updated`; `delete_note` defaults to `force: true` and leaves inbound links behind, so repair or report them explicitly.
- **Destructive calls are gated by client-side confirmation, and only the audit trail makes them safe to grant.** `delete_note`, a `move_note` that replaces its destination, a forced `rollback_note`, a `batch_execute` that deletes or replaces, and `add_vault` ask the client through elicitation first. A client that answers in the wrong shape gets `Couldn't confirm with the user (… required field 'confirm' is missing)` and **nothing is changed** — that is a client protocol mismatch, not a server problem, so do not resend the identical call and never route around it with `rm`, `write_file` or `patch`. Turning the gate off (`TURBOVAULT_NO_CONFIRM_DESTRUCTIVE=1` in the server's environment) is a user decision: verify the recovery guarantee before asking, report the audit id of every destructive operation you then perform, and archive instead of deleting when the content still has reference value. Semantics, limits and the verification recipe: `references/audit-and-rollback.md`.
- Treat Direct backlink rewriting as sequential, not atomic. For v4.0.2, verify both wikilinks and inline Markdown links after the move; do not infer coverage of reference-style links, canvas cards, aliases, headings, or plain-text mentions from those two link forms. Git-backed v4 moves rewrite wikilinks, Markdown links, and canvas references atomically by default; do not transfer that backend's guarantees to Direct.

Before the first write of a session, orient explicitly:

- Call `list_vaults` and `get_vault_context`; confirm the intended registered absolute path, not just the vault name. In v4, pass the optional `vault` argument to scoped calls when possible instead of changing the shared active-vault pointer. For tools without that argument or pre-v4 servers, use `set_active_vault` explicitly and re-confirm with `list_vaults`.
- Before migration or smoke-test writes, verify the disposable vault's absolute path through the exact MCP connection that will perform the writes. A scratch configuration or separate CLI process does not establish the target of session-bound tools. Stop if the connection resolves to a real vault; never use production content as an implicit test fixture. See `references/vault-configuration.md` for the upgrade gates.
- Check existence before creating (`search`, `get_notes_info`).
- Probe liveness with a trivial `list_vaults` call when a tool seems dead.
- Never claim success without a tool response — cite the response or the resulting path in the same reply.
- Treat `success: true` as unproven until checked: it can mean (A) nothing was written, (B) the write landed in the wrong vault, or (C) the report was confabulated.

## Core Tools

| Operation | Tool family |
|---|---|
| Read and write notes | `read_note` (whole, or one selector: `head_lines`, `tail_lines`, `heading_equals`, `heading_level`, `last_sections`), `write_note` (`overwrite`/`append`/`prepend`), `edit_note` |
| Register and select vaults | `list_vaults`, `add_vault`, `set_active_vault`, `get_vault_context` |
| Move or delete notes | `move_note` (`update_backlinks` rewrites inbound links), `delete_note` (`confirm_path` required) |
| Multi-file batches | `batch_execute` (transaction guarantee depends on backend) |
| Frontmatter | `inspect_frontmatter`, `get_notes_info`, `search` with `frontmatter_filters`, `update_frontmatter` |
| Full-text and semantic discovery | `search` (query, tags, frontmatter_filters, related_to), `find_similar`; optional `vector_search_search` |
| Graph traversal | `get_links(direction="outgoing")`, `get_links`, `get_related_notes` |
| Structural analysis | `graph_report(kind="broken_links")`, `graph_report(kind="dead_ends")`, `graph_report(kind="isolated_clusters")`, `graph_report(kind="cycles")` |
| Overview, health, validation | `get_vault_context`, `explain_vault`, `vault_health(depth)`, `validate_vault` |
| Tasks | `query_tasks` — see `references/search-and-graph.md` |

Use the exact tool names exposed in the current session; MCP prefixes may differ between clients.

Deferred tools: call through `tool_call` with both `name` and `arguments` on every entry, and run `tool_describe` before first use. Parameter names are exact and snake_case — `read_note` takes `path` plus at most one selector (`head_lines`, `tail_lines`, `heading_equals`, `heading_level`, `last_sections`), and a partial read carries no `hash` for `expected_hash`; `edit_note` takes the SEARCH/REPLACE blocks as a single `edits` string. The vault-mutating tools are where guessed keys cost the most round trips: `move_note` takes `from`/`to` (not `path`/`new_path`, and not `source`/`destination`), `write_note` takes `path`/`content`/`mode`/`expected_hash`, `query_frontmatter_sql` takes the statement as `sql` (not `query`), and `read_note` has no `offset` — page with its selectors. A wrong key fails Hermes-side argument validation (`Additional properties are not allowed` or `missing required argument(s)`), so the tool never runs and nothing changes: correct the key and re-issue, and do not read the rejection as a server problem or a reason to switch tools.

**Pass `calls` as a real array, never as a JSON string.** The bridge tolerates a stringified envelope (it parses it and reports `tool_call 'calls' is not valid JSON: ...` on failure — see `tools/tool_search_validation.py`), but a long, quote-heavy note body then has to survive two levels of quoting, and one slip invalidates the whole payload before any MCP call:

- the failure is caught by Hermes's own argument validation, so the tool is never invoked — no server-side symptom to diagnose, and retrying the identical payload reproduces nothing;
- keep single-payload writes moderate: write the skeleton first and add the long sections as separate `edit_note` blocks instead of one 15 KB content string full of escaped quotes and `"*..."*` emphasis;
- **An oversized payload fails in Hermes, not on the server**, with `tool_call calls[0] requires a 'name'`: the arguments never parsed, so no MCP call happened, no server-side symptom exists, and resending the identical string reproduces it. The fix is to split the content — `write_note(mode=overwrite)` the frontmatter plus the first sections, then `write_note(mode=append)` one section per call, with the `Topics:`/`Related:` footer in the LAST append, because append writes inside the body and an early footer strands the later sections beneath it.
- on this failure, fix the payload and re-issue the *same* TurboVault tool. Switching to `write_file`/`patch` bypasses the guarded write path and introduces reconciliation uncertainty (see the graph-freshness rule above).

### Efficiency defaults

- Read a large note with at most one `read_note` selector instead of the whole file; use a full read (or an `edit_note` dry run) whenever you need `expected_hash`.
- For broad discovery pass `response_format: concise` to `search`, `explain_vault`, or `get_vault_context` — compact rows without `preview`, `outgoing_links`, and `word_count`.
- Query tasks with `query_tasks` instead of full-text search over checkboxes: `status` is one of `todo|done|in_progress|cancelled|other` (never `open`), plus `due_before`/`due_after`, `scheduled_before`/`scheduled_after`, `tag`, `path`, `priority`, `text`, and paging.

### Paths

- `mcp_turbovault_*` tools take full vault-relative paths, including the `area/<folder>/` prefix — not bare filenames. If `search_files` on vault-relative paths returns 0 hits, retry with absolute paths or use the SQL/frontmatter query tools.
- In-process tools (`read_file`, `write_file`, `patch`) require absolute filesystem paths. Never swap the two conventions: a vault-relative path passed to `patch` fails path resolution.

## 4.0 Tool Surface

TurboVault 4.0 consolidates 79 tools into 52 and changes what a client sees:

- **`tools/list` shows 30 core tools.** The 22 advanced ones are omitted unless `tool_visibility.show_advanced_tools: true` (or `--show-advanced-tools`) is set. The server still accepts direct calls by exact name, but clients such as Hermes that register schemas only from `tools/list` cannot use an unlisted tool in that session. Enable listing for needed advanced tools; use `tool_visibility.disabled` to block unsafe tools, because hiding is not a security control. Under Hermes Tool Search the context argument for trimming disappears — MCP tools sit in a deferred catalogue behind `tool_search`/`tool_describe`/`tool_call`, so `show_advanced_tools: true` costs catalogue entries rather than schemas. Keep it on, and use `disabled`/`allowed` as policy (least privilege, disabling a backend's tool family) rather than as token saving. Tool Search is disclosure, not an access boundary. Advanced: `inspect_frontmatter`, `query_frontmatter_sql`, `audit_log`, `export`, `compare_notes`, `find_duplicates`, `find_stale_notes`, `suggest_links`, `note_quality`, `analyze_grounding`, `rollback_preview`, `rollback_note`, `move_file`, `diff_notes`, `list_orphan_fanouts`, `find_notes_from_template`, `remove_vault`, `fanout`, `okf_validate`, `generate_index`, `append_log_entry`, `visualize`.
- **`generate_index` and `append_log_entry` write OKF conventions** (`index.md`, folder `log.md` history). Use them only in vaults that follow Open Knowledge Format — in vaults with their own index naming (e.g. `INDEX.md` plus MoCs) they collide with the vault's convention.
- **Every vault-scoped tool takes an optional `vault` argument.** It defaults to the active vault, and naming a vault does not change which vault is active. Prefer it over `set_active_vault` when two sessions share one server.
- **List results page.** `limit`/`offset`, default 50, with `meta.pagination` (`total`, `returned`, `truncated`, `next_offset`). A vault-wide enumeration (broken links, stale notes, hubs) must loop on `next_offset`; the first page is not the whole answer.
- **Graph tools return vault-relative paths.** 3.x returned absolute paths on the server.
- **`write_note` modes are `overwrite`, `append` and `prepend`.** Append and prepend write inside the body — after the frontmatter block — and require an existing note; on a missing path the call fails with a misleading `Concurrent access conflict: File does not exist`.
- **`edit_note` refuses a SEARCH block that matches in more than one place** and asks for more surrounding context, which removes the silent first-match edit behind the fuzzy-match pitfall above.
- **`validate_vault` exists as a tool** (whole vault or one `path`, `min_severity`, paging): pre-1.9 `tags`/`aliases`/`cssclasses` forms, unparsable frontmatter, broken links.
- **Read `list_vaults` from `data.active_vault` and `data.vaults`.** Do not require `data.config`: an unfiltered v4 response can omit it. Inspect the current tool schema and returned fields before choosing a configuration lookup; inspect the loaded YAML separately when needed. `get_active_vault` and `get_vault_config` no longer exist.

## Audit Trail

The `audit_log` tool, its snapshots and `rollback_note` cover **only writes that went through TurboVault**. Obsidian edits, sync clients, other machines and any agent that used the filesystem tools leave no entry and no snapshot. When a question is "what changed and did TurboVault see it" — or a restore is promised — load `references/audit-and-drift.md`; it carries the log layout, the drift check (`scripts/vault-drift-check.py`, `scripts/vault-drift-all.py`), the watchdog wiring, and why syncing `.turbovault/` over Git is the wrong lever.

## Route to the Right Reference

| Task | Reference |
|---|---|
| Install, register, activate, or diagnose basic availability | `references/vault-configuration.md` |
| Upgrade the server binary or migrate the skill library to a new tool surface | `references/upgrading.md` |
| `edit_note`, full writes, or multi-file batches | `references/editing-and-batch-operations.md` |
| Full-text, frontmatter, SQL, or graph discovery | `references/search-and-graph.md` |
| Audit coverage, changes made outside TurboVault, restoring an unaudited edit | `references/audit-and-drift.md` |
| Rename, move, or structural refactor | `references/renames-and-refactors.md` |
| Apply templates or normalize frontmatter | `references/frontmatter-and-templates.md` |
| Destructive operations, confirmation gate, audit trail and rollback | `references/audit-and-rollback.md` |
| Missing tools, stale UI, reconnect churn, or process symptoms | `references/troubleshooting.md` |
| Enable, configure, or debug the vector-search plugin | `references/vector-search.md` |

Do not load every reference for routine reads.

## Verification

After a write:

1. Read the exact target.
2. Confirm expected frontmatter and body changes.
3. For structural operations, check backlinks and broken links.
4. For batch operations, verify every intended target and explicitly resolve or report partial state.
5. Triage validation warnings against the exact note text before reporting them as defects. If `validate_vault` reports a URL in wikilink syntax, inspect that occurrence: `[label](https://...)` is already correct external-link syntax. Preserve valid Markdown and report a validator false positive when the read-back demonstrates it; do not rewrite correct links merely to silence the warning. Distinguish `passed: true` from a warning-free result, and report genuine unresolved warnings or client refresh requirements honestly.

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
