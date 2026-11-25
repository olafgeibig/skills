---
name: turbovault-use
description: "Use when operating Obsidian/OKF vaults via TurboVault."
version: "0.22.0"
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

Operate Obsidian vaults safely and accurately through the TurboVault 4.x MCP server.

Division of responsibility:

- `turbovault-use` owns TurboVault MCP mechanics, vault selection, read/write/graph/audit tools, configuration, upgrades, and troubleshooting.
- `vault-ops` owns generic vault structure, note types, MoCs, tasks, and navigation conventions.
- `vault-wiki` owns domain-wiki architecture, ingest, query, source, and lint workflows.

## When to Use

Load this skill whenever a task calls TurboVault tools, another skill enters a TurboVault-backed operation, or a task configures, troubleshoots, or upgrades the TurboVault server.

## Establish Availability & Orient

Start with `list_vaults` (and `get_vault_context` before the first write in a session, or after a long pause):

- A successful `list_vaults` response (even `vaults: []`) proves the tool is exposed in this session.
- Separate **runtime availability** (`hermes mcp test turbovault`) from **session exposure**. Never call TurboVault disconnected when only the current session lacks its tools — reload the owning MCP binding or bridge via `mcporter` (`references/troubleshooting.md`).
- Confirm the intended vault's **registered absolute path**, not just its name, and sanity-check `current_stats.total_notes` against the vault you expect to touch.

### Vault selection order

1. A vault explicitly named by the user.
2. The only registered vault.
3. A vault established earlier in the same conversation.
4. The currently active vault after confirming its path with `get_vault_context`.
5. If ambiguity remains, ask; do not guess.

- **A vault-relative path in the request is vault evidence.** If the active vault lacks a named path, check the other registered vaults (`list_vaults` + `get_notes_info`/`search` with explicit `vault`) before concluding it is missing or creating it in the active vault.
- **Prefer the per-call `vault` argument** on every vault-scoped tool — it leaves the shared `active_vault` pointer untouched. Note that a scoped call's response echoes the *target* vault in `data.active_vault`; verify the shared pointer with `list_vaults`.
- **When a tool lacks `vault`**, do **not** treat `set_active_vault` as a harmless read fallback: it mutates the shared server pointer and persists it to the project cache (`references/vault-configuration.md` §2), and restoring it later does not protect concurrent sessions. Restrict `set_active_vault` to single-session / isolated connections: record the original active vault (`list_vaults`), switch, confirm with `get_vault_context`, keep reads sequential inside that window, then restore and verify unless the user requested a lasting switch.

## Core Invariants

- **Read the vault's `AGENTS.md`** before structural or content changes, and read a note before editing it.
- **All vault notes go through TurboVault** (`read_note`, `write_note`, `edit_note`, `move_note`, `delete_note`, `batch_execute`, `update_frontmatter`, `manage_tags`, `write_canvas`, `create_from_template`). A missing session tool or malformed payload is not a license to fall back to `write_file`/`patch`/`terminal`: fix the payload, reload, or bridge via `mcporter` (`references/troubleshooting.md`).
- **Narrow filesystem exceptions:** Use filesystem tools only for (1) server state under `.turbovault/` (e.g. plugin `config.json`, blocked by TurboVault by design), (2) non-note operational artifacts written to plain paths (no frontmatter/MoC scaffolding), or (3) explicitly delegated bulk directory removal where no bulk MCP delete exists. Never extend these exceptions to ordinary note edits, moves, or deletes.
- **Require explicit user authorization for destructive operations** — deletes, destination-replacing moves, destructive batches, and forced rollbacks — regardless of client, elicitation support, or bridge. MCP elicitation is a client-dependent UX prompt, never an authorization boundary (`references/audit-and-drift.md` §2).
- **Guard writes with `expected_hash`.** Use the hash from a full `read_note` (or `edit_note(dry_run: true)`) on existing notes; partial reads return no hash. Never pass `expected_hash: "blind"` without explicit user authorization, and never blindly replay an edit with a fresh hash after a mismatch without reconciling the diff (`references/editing-and-mutations.md`).
- **Never issue two writes to the same note in parallel.** Parallelize across distinct files; serialize per file.
- **Respect backend differences.** Keep `write_backend: direct` by default and disable Git fan-out tools unless Git backend is explicitly authorized per vault (`references/vault-configuration.md` §4). Never claim atomic batches or atomic backlink rewrites on Direct (`references/editing-and-mutations.md`).
- **Use vault-relative paths for TurboVault tools** (including folder prefixes and `.md`, e.g. `projects/Plan.md`) and absolute paths for local filesystem tools — never mix the two.
- **Respect pagination and concise output.** List tools page via `limit`/`offset` (`meta.pagination.next_offset`); vault-wide counts must loop to exhaustion. Pass `response_format: "concise"` on `search`, `explain_vault`, and `get_vault_context` for broad discovery.
- **Never claim success without a verified tool response.** Treat `success: true` as a first signal, not proof; confirm the exact target by read-back.

## 4.x Tool Surface

Every vault-scoped tool accepts an optional `vault` parameter. Core tools are always listed; *(advanced)* tools require `tool_visibility.show_advanced_tools: true` to appear in `tools/list`; *(plugin)* tools require `--plugins`.

| Domain | Core tools (listed by default) | Advanced / Plugin tools |
|---|---|---|
| Orientation & vaults | `get_vault_context`, `list_vaults`, `add_vault`, `set_active_vault` | `remove_vault` *(adv)* |
| Notes & batches | `read_note`, `write_note`, `edit_note`, `move_note`, `delete_note`, `get_notes_info`, `batch_execute` | `move_file`, `diff_notes`, `fanout`, `list_orphan_fanouts` *(adv)* |
| Frontmatter, tags & templates | `update_frontmatter`, `manage_tags`, `list_templates`, `create_from_template`, `get_ofm_guide` | `inspect_frontmatter`, `query_frontmatter_sql`, `find_notes_from_template` *(adv)* |
| Search & similarity | `search`, `find_similar`, `query_metadata` | `find_duplicates`, `compare_notes`, `suggest_links` *(adv)*; `vector_search_*` *(plugin)* |
| Graph & health | `get_links`, `get_related_notes`, `graph_report`, `vault_health`, `explain_vault`, `validate_vault` | `note_quality`, `find_stale_notes`, `analyze_grounding`, `visualize`, `okf_validate`, `generate_index`, `append_log_entry` *(adv)* |
| Structured Obsidian | `query_tasks`, `read_canvas`, `write_canvas`, `query_base`, `get_periodic_note` | — |
| Audit & export | — | `audit_log`, `rollback_preview`, `rollback_note`, `export` *(adv)* |

Use the exact MCP tool names exposed in the active client (prefixes vary by host).

## Route to the Right Reference

Load only the reference matching the task at hand:

| Task | Reference |
|---|---|
| Localized edits, writes, frontmatter/tags, templates, moves, deletes, or batches | `references/editing-and-mutations.md` |
| Search, SQL frontmatter queries, graph traversal, tasks, canvases/bases/periodic notes, or `validate_vault` | `references/search-and-graph.md` |
| Audit trail, snapshots, rollback, destructive confirmation gates (`--no-confirm-destructive`), or external drift watchdog | `references/audit-and-drift.md` |
| Declarative YAML schema, startup/cache precedence, `XDG_CACHE_HOME` isolation, `add_vault` / `obsidian.json`, or backend/visibility policy | `references/vault-configuration.md` |
| Step-by-step setup, config audit, post-update check, working-vault check, or default-vault diagnosis/repair | `references/wf-turbovault-config.md` |
| Upgrading the TurboVault binary, isolated test gates, skill migration, or live reload | `references/wf-upgrading.md` |
| Runtime failures — missing session tools, parked spawns, `env` typing, `mcporter` bridge, reconnect churn, stale Obsidian UI, logs | `references/troubleshooting.md` |
| Opt-in `vector_search` plugin — capability check, model setup/pruning, config, pilot, pitfalls, rollback | `references/vector-search.md` |

## Verification

After any mutation:

1. Read back each modified target with `read_note` and verify frontmatter and body.
2. On `edit_note`, confirm `blocks_applied == total_blocks` and inspect the entire touched region whenever a fuzzy-match warning appears.
3. On moves or deletes, check `link_sources_updated`, `get_links`, `graph_report(kind: "broken_links")`, and sweep raw text for leftover target mentions; for destructive operations, record the audit `id` from `audit_log` (on Direct — `delete_note` does not return it) or the Git commit reference.
4. On Direct-backend batches, inspect `records[]` per operation and resolve or report any partial state explicitly.
5. Distinguish `validate_vault` warnings from `vault_health` / `graph_report(kind: "broken_links")` counts; verify flagged lines against actual note content before editing.

## Improvement Routing

This is an owned generic skill (follow `skill-governance`): generic TurboVault mechanics belong here; vault structure belongs in `vault-ops`; wiki workflows belong in `vault-wiki`; project procedures belong in `project-*`; project facts stay in project files; profile quirks stay in profile guidance.
