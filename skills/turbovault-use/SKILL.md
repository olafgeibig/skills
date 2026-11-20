---
name: turbovault-use
description: "Use when operating Obsidian vaults through TurboVault."
version: "0.20.1"
author: Olaf Geibig
license: Apache-2.0
metadata:
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
- An empty list proves the tool responds, not why registration is absent. Check the intended profile, launch config, and registry before changing anything; see `references/troubleshooting.md`.
- A missing tool does not prove the configured MCP server is unavailable.
- Distinguish profile/runtime availability from current-session tool exposure.
- If runtime checks pass but tools are absent, reload the owning MCP binding; a new session can reuse the old connection.
- If Hermes logs that the connection is parked, fixing the config alone does not reconnect it. Follow `references/troubleshooting.md` and verify that the owning process registers the tools.
- When a reload is not available in this session, reach the same server through `mcporter` instead of stopping: also a client, so writes keep the hash guards and land in the audit log. Recipe and flag traps: `references/troubleshooting.md` § Reaching the server when the session has no TurboVault tools.
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

**Keep registration checks read-only.** Compare the launch YAML, live registry, and existing directories; see `references/vault-configuration.md`.

**A profile config does not isolate the registry.** A shared working-directory cache can restore other vaults. Isolate the cache and verify `list_vaults` on the owning connection; see `references/vault-configuration.md` §Vault registry.

**Disk config and the live registry are separate evidence.** Check the owning process, launch arguments, and cache before attributing discrepancies. For an authorized reload, follow `references/upgrading.md` §7.

For a temporary lookup in another vault:

1. On v4, prefer the per-call `vault` argument for vault-scoped tools; first confirm the registered name and absolute path with `list_vaults`. This avoids changing a shared active-vault pointer.
2. For pre-v4 tools or registry operations without a `vault` argument, record the original active vault from `list_vaults`, call `set_active_vault` for the lookup target, and confirm its absolute path with `get_vault_context` before reading notes.
3. Keep active-vault-dependent reads within that selection window. Do not batch a switch or restoration in parallel with note reads, because those reads resolve against mutable server state.
4. After the lookup, restore the original selection with `set_active_vault` unless the user requested a lasting switch. Verify restoration with `list_vaults` and `get_vault_context` before claiming it.
5. Distinguish note changes from selection changes in the handoff: report that no note content was edited when appropriate, rather than implying no state changed.

## Core Safety Rules

- Read the vault's `AGENTS.md` before structural or content changes.
- Read a note before editing it.
- Vault note reads and writes go through TurboVault (`read_note`, `write_note`, `edit_note`, `move_note`, `delete_note`). A missing session tool is not a reason to write the file directly: bridge to the same server (`mcporter`, see `references/troubleshooting.md`) or reload the session first, and call it a blocker only when neither path is available. Do not substitute `write_file`, `patch`, or `terminal`.
- **Not every file under a vault root is a note.** Generated operational artifacts (reports, receipts, exports) are plain files at plain paths: write them with `write_file` and verify by byte-exact read-back, even when the destination directory sits inside a vault. They carry no frontmatter, no MoC entry, and leave no TurboVault audit entry. Reserve the TurboVault write path for actual notes; when a user names a directory inside a vault as an artifact destination, treat it as plain and create no note scaffolding.
- A failed TurboVault call — including a malformed `edits`/content payload that cannot be encoded in the tool call — is not a licence to switch tools: fix the payload and retry the same TurboVault tool (`write_note` with `mode=overwrite` after a `read_note`, or `edit_note` with smaller SEARCH/REPLACE blocks).
- **Anchor `edit_note` blocks on whole lines from a fresh read.** Fuzzy matches can leave old line tails; read the whole affected region after a fuzzy warning. Details: `references/editing-and-batch-operations.md`.
- **Keep the `=======` separators out of the payload text.** A stray marker copied into the REPLACE half is not a syntax hint, it is content: it gets written into the note verbatim, where it shows up as `=======### Next Heading` and silently breaks heading parsing — entries look deleted (`^### ` counts drop) even though every line is still there. Check any multi-block edit with `grep -c '^======='` on the file plus a heading count before/after; a count that fell while the byte size grew is this bug, not data loss.
- **The `edits` payload is note content, not a scratchpad.** A drafting note left in a REPLACE half — a search instruction, a "check this", a correction written beside the value ("— verify: the real one is …") — lands in the note verbatim, and `blocks_applied: N` reports success anyway. Proofread every REPLACE half **and every `write_note` content string** as final prose before sending — typed multilingual text can pick up stray wrong-script characters and typos that land verbatim and that no validator reports; the post-write verification catches broken YAML and dead links, never prose artifacts.
- **Do not infer graph freshness from readable content.** TurboVault 4.x reconciles external edits before derived reads when `reconcile_external_changes` is enabled; older versions or disabled reconciliation may leave derived results stale. Keep TurboVault as the normal write path for hash guards and audit. If note content and graph results disagree, inspect the setting and verify with `get_links` in both directions; do not infer freshness from `read_note` alone.
- The only terminal exception is bulk removal of an entire wiki directory (`rm -rf`), named in vault-wiki under archiving, because `delete_note` requires a `confirm_path` per file. Do not extend that exception to ordinary note edits.
- Set fields and write modes explicitly.
- Preserve unrelated content.
- Use the `direct` write backend by default. Do not enable `write_backend: git` or call Git fan-out tools unless the user explicitly authorizes it for the named vault after external-sync compatibility review and testing on a copy.
- Never assume `batch_execute` is atomic. The Direct backend is sequential and fail-fast; completed operations are not rolled back. Claim all-or-nothing only when the selected backend's documented transaction contract guarantees it.
- Keep read-before-write for content context. For existing notes, use the current `expected_hash` from `read_note` or an `edit_note` dry run; do not send the removed `force` argument or use a blind overwrite without explicit user authorization. An `expected_hash` mismatch is not proof of a concurrent edit — the hash can move while the visible content is unchanged: re-read the note once and retry with the fresh hash; treat only a second mismatch as a real conflict.
- `vector_search` is opt-in; do not assume its engine follows vault switches. Verify enablement, memory, and retrieval benefit in a single-vault pilot: `references/vector-search.md`.
- Verify external writes by reading the exact target and checking the resulting links or metadata.
- Inspect backlinks before moves or deletions. On Direct, explicitly pass `move_note(update_backlinks: true)` to request inbound-link rewriting and inspect `link_sources_updated`; `delete_note` defaults to `force: true` and leaves inbound links behind, so repair or report them explicitly.
- **Do not rely on destructive elicitation.** Obtain authorization and verify recovery; do not bypass a failed prompt via batch or filesystem tools. Use `confirm_path` and `expected_hash` where available, report the audit ID, and prefer archive when content still has value. See `references/audit-and-rollback.md`.
- Treat Direct backlink rewriting as sequential, not atomic. For v4.0.2, verify both wikilinks and inline Markdown links after the move; do not infer coverage of reference-style links, canvas cards, aliases, headings, or plain-text mentions from those two link forms. Git-backed v4 moves rewrite wikilinks, Markdown links, and canvas references atomically by default; do not transfer that backend's guarantees to Direct.
- **Never issue two writes against the same file in parallel.** Every write is read-modify-write; a concurrent second write on the same path silently loses the first. Parallelize across files, sequence per file.
- **Find dead links by content search, not SQL.** The `links` table silently drops unresolvable targets, so a dangling old link is invisible to `query_frontmatter_sql`; sweep the raw text (`search_files`/ripgrep) for the old target strings after every move or rename.

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
| Read and write notes | `read_note` (full, line slice, or section selectors), `write_note` (`overwrite`/`append`/`prepend`), `edit_note` |
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

For deferred tools, load the live schema with `tool_describe` and invoke the qualified name through `tool_call`, with `calls` as an array of `{name, arguments}` objects. A routing or schema rejection is not a server failure. See `references/editing-and-batch-operations.md` for payload construction, selectors and retry rules.

### Efficiency defaults

- Read only the needed lines or sections when possible. Partial reads have no hash; use a full read or an `edit_note` dry run for `expected_hash`.
- For broad discovery pass `response_format: concise` to `search`, `explain_vault`, or `get_vault_context` — compact rows without `preview`, `outgoing_links`, and `word_count`.
- Query tasks with `query_tasks` instead of full-text search over checkboxes: `status` is one of `todo|done|in_progress|cancelled|other` (never `open`), plus `due_before`/`due_after`, `scheduled_before`/`scheduled_after`, `tag`, `path`, `priority`, `text`, and paging.

### Paths

- `mcp_turbovault_*` tools take full vault-relative paths, including the `area/<folder>/` prefix — not bare filenames. If `search_files` on vault-relative paths returns 0 hits, retry with absolute paths or use the SQL/frontmatter query tools.
- In-process tools (`read_file`, `write_file`, `patch`) require absolute filesystem paths. Never swap the two conventions: a vault-relative path passed to `patch` fails path resolution.

## 4.0 Tool Surface

TurboVault 4.0 consolidates 79 tools into 52 and changes what a client sees:

- **Discover the live tool list.** Enable advanced listing when needed; hiding tools is not access control. Use `tool_visibility.disabled` or an allow-list to restrict calls. See `references/troubleshooting.md` for missing tools.
- **`generate_index` and `append_log_entry` write OKF conventions** (`index.md`, folder `log.md` history). Use them only in vaults that follow Open Knowledge Format — in vaults with their own index naming (e.g. `INDEX.md` plus MoCs) they collide with the vault's convention.
- **Every vault-scoped tool takes an optional `vault` argument.** It defaults to the active vault, and naming a vault does not change which vault is active. Prefer it over `set_active_vault` when two sessions share one server. In a scoped call's response, `data.active_vault` echoes the call's *target* vault, not the shared pointer — verify the pointer with `list_vaults`, never from a scoped response.
- **List results page.** `limit`/`offset`, default 50, with `meta.pagination` (`total`, `returned`, `truncated`, `next_offset`). A vault-wide enumeration (broken links, stale notes, hubs) must loop on `next_offset`; the first page is not the whole answer.
- **Graph tools return vault-relative paths.** 3.x returned absolute paths on the server.
- **`write_note` modes are `overwrite`, `append` and `prepend`.** Append and prepend write inside the body — after the frontmatter block — and require an existing note; on a missing path the call fails with a misleading `Concurrent access conflict: File does not exist`.
- **`edit_note` refuses a SEARCH block that matches in more than one place** and asks for more surrounding context, which removes the silent first-match edit behind the fuzzy-match pitfall above.
- **`validate_vault` exists as a tool** (whole vault or one file `path`, `min_severity`, paging): pre-1.9 `tags`/`aliases`/`cssclasses` forms, unparsable frontmatter, broken links. A directory passed as `path` fails with an I/O error because the validator expects a file; validate each touched file or omit `path` for a whole-vault run.
- **Read `list_vaults` from `data.active_vault` and `data.vaults`.** Do not require `data.config`: an unfiltered v4 response can omit it. Inspect the current tool schema and returned fields before choosing a configuration lookup; inspect the loaded YAML separately when needed. `get_active_vault` and `get_vault_config` no longer exist.

## Audit Trail

The `audit_log` tool, its snapshots and `rollback_note` cover **only writes that went through TurboVault**. Obsidian edits, sync clients, other machines and any agent that used the filesystem tools leave no entry and no snapshot. When a question is "what changed and did TurboVault see it" — or a restore is promised — load `references/audit-and-drift.md`; it carries the log layout, the drift check (`scripts/vault-drift-check.py`, `scripts/vault-drift-all.py`), the watchdog wiring, and why syncing `.turbovault/` over Git is the wrong lever.

## Route to the Right Reference

| Task | Reference |
|---|---|
| The wiring must change — first setup, register or activate a vault, isolate a profile, upgrade | `references/vault-configuration.md` (the Configuration Guide) |
| Upgrade the server binary or migrate the skill library to a new tool surface | `references/upgrading.md` |
| `edit_note`, full writes, or multi-file batches | `references/editing-and-batch-operations.md` |
| Full-text, frontmatter, SQL, or graph discovery | `references/search-and-graph.md` |
| Enable, configure, or debug the `vector_search` plugin | `references/vector-search.md` |
| Set `vector_search` up on a fresh installation (model, config, MCP args, verification) | `references/vector-search-setup.md` |
| Audit coverage, changes made outside TurboVault, restoring an unaudited edit, wiring the drift watchdog | `references/audit-and-drift.md` |
| Rename, move, or structural refactor | `references/renames-and-refactors.md` |
| Apply templates or normalize frontmatter | `references/frontmatter-and-templates.md` |
| Destructive operations, confirmation gate, audit trail and rollback | `references/audit-and-rollback.md` |
| TurboVault misbehaves although it is there — missing tools, stale UI, reconnect churn, process symptoms | `references/troubleshooting.md` |

Do not load every reference for routine reads.

## Verification

After a write:

1. Read the exact target.
2. Confirm expected frontmatter and body changes.
3. For structural operations, check backlinks and broken links.
4. For batch operations, verify every intended target and explicitly resolve or report partial state.
5. Triage validation warnings against the exact note text before reporting them as defects. If `validate_vault` reports a URL in wikilink syntax, inspect that occurrence: `[label](https://...)` is already correct external-link syntax. Preserve valid Markdown and report a validator false positive when the read-back demonstrates it; do not rewrite correct links merely to silence the warning. Distinguish `passed: true` from a warning-free result, and report genuine unresolved warnings or client refresh requirements honestly. Report `validate_vault` findings separately from `vault_health` graph counts: zero validation issues does not establish zero broken links when the graph check reports otherwise. Inspect the paths with `graph_report(kind="broken_links")` before classifying the discrepancy; do not silently discard either result or repair links during a read-only smoke test. Without a comparable pre-change baseline, label these as current findings rather than upgrade regressions.
6. Confirm suspected character corruption by byte counts before repairing anything. Tool and terminal output is JSON-escaped in the transcript, so an ordinary quote can display as a backslash-quote pair while the file holds no backslash at all — eyeballing the read-back invents phantom defects and the "fix" then edits healthy text. Count the suspect sequence in the raw string (`text.count(...)`, `repr`) first; edit only on a real hit. The same holds for identifiers that display masked mid-token (`abc12****789`): the mask is display-only and the file holds the full token. Never write a masked token into a filename or link and never "repair" an identifier that merely looks wrong — confirm the real bytes first (exact-match search, or a resolver that checks `[[targets]]` against a basename/path map).

Use the write response as the first signal, then read back the exact target directly. See `references/editing-and-batch-operations.md` §Verification for failed, fuzzy, or multi-block edits.

## Improvement Routing

This is an owned generic skill. Follow `skill-governance`:

- generic TurboVault mechanics belong here;
- generic vault structure belongs in `vault-ops`;
- wiki-specific behavior belongs in `vault-wiki`;
- reusable project procedure belongs in the relevant `project-*` skill;
- project facts belong in project content;
- profile quirks belong in profile guidance, not a parallel skill.

Update the owning skill only after classification, abstraction, read-before-write, and required approval.
