---
name: turbovault-use
description: "Safe and effective use of TurboVault MCP tools — vault selection, active vault management, read/write/edit_note patterns, SEARCH/REPLACE syntax, search tools, graph tools, batch operations, verification, and troubleshooting. Load this skill whenever a task uses mcp_turbovault_* tools."
metadata:
  version: "0.2.2"
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
      - vault-improvements
---

# TurboVault Use

This skill defines the **tool-level mechanics** for working with TurboVault MCP — the interface between Hermes Agent and an Obsidian markdown vault. Every skill that uses `mcp_turbovault_*` tools should either reference this skill or have it in `related_skills`.

**Division of labor:**
- `turbovault-use` = tool mechanics (vault selection, read/write/edit/search, graph, syntax, troubleshooting)
- `vault-ops` = vault structure, navigation (MoCs, INDEX, topics), note types, tags, frontmatter rules
- `vault-wiki` = wiki architecture (hub, SCHEMA, ingest, query, lint), raw source policies, linking conventions

## When This Skill Activates

This skill is a **secondary skill** — it is loaded by other skills that needs TurboVault access. Activate when:

- A task requires reading, writing, editing, or searching vault notes
- A task specifies "use TurboVault" or "use mcp_turbovault_* tools"
- A parent skill (vault-ops, vault-wiki) is loaded and enters the tool-level phase of a workflow

## Check TurboVault Availability

Before any vault operation, verify TurboVault MCP is connected **and exposed in the current session**:

```
mcp_turbovault_list_vaults
```

- **If it succeeds** (even with an empty list): TurboVault MCP is available in this session. Proceed.
- **If the `mcp_turbovault_*` tools are missing from the callable tool surface:** do **not** conclude the profile is misconfigured. First distinguish:
  1. **Profile/runtime availability** — check with `hermes mcp list` and `hermes mcp test turbovault`
  2. **Current-session tool exposure** — whether the tools are actually injected into this chat/session
- **If profile/runtime checks pass but the tools are still absent in-session:** the likely issue is stale session tool binding (for example after MCP/profile changes or gateway restart). Start a **new chat/session** or reload MCP/session tool bindings before proceeding.
- **If profile/runtime checks fail too:** TurboVault is not connected/configured. Follow `./references/vault-configuration.md` to diagnose and set up.

**Rule:** Always use `mcp_turbovault_*` tools for vault files when they are present in the current session. Never use standard filesystem tools (`read_file`, `write_file`) as a substitute for real vault operations on external vault paths.

## Vault Selection

Pick the right vault before any operation:

1. **User names a vault** → use that vault
2. **Exactly one vault exists** → use it
3. **Vault was used earlier in the same conversation** → continue using it
4. **Active vault is already set** → use it (verify with `mcp_turbovault_get_vault_context`)
5. **Unsure** → ask the user. Do not guess.

Set the vault:
```
mcp_turbovault_set_active_vault(name="<vault-name>")
mcp_turbovault_get_vault_context   # verify it worked
```

## Core Tools Quick Reference

| Tool | Purpose |
|------|---------|
| `read_note` | Read a note's full markdown content. Always read first before editing. |
| `write_note` | Overwrite, append, or prepend to a note. Modes: `overwrite` (default), `append`, `prepend`. |
| `edit_note` | Targeted SEARCH/REPLACE edits. See full section below. |
| `move_note` | Rename/move a note. Does NOT update wikilinks — check backlinks first. |
| `delete_note` | Permanently delete a note. Confirmation-protected (requires `confirm_path`). |
| `batch_execute` | Atomic multi-file operations. See section below. |

## Using `edit_note`

`mcp_turbovault_edit_note` uses SEARCH/REPLACE blocks with **git-diff style delimiters**. This is the only format that works:

```
<<<<<<< SEARCH
Old text to find — exact match, include surrounding context for uniqueness
=======
New replacement text
>>>>>>> REPLACE
```

**Required format (exact):**
- Opening delimiter: `<<<<<<< SEARCH`
- Separator: `=======`
- Closing delimiter: `>>>>>>> REPLACE`

**Common mistakes:**
- ❌ `SEARCH` / `REPLACE` without angle brackets → `"Parse error: No SEARCH/REPLACE blocks found"`
- ❌ `>>>>>>>` without `REPLACE` → `"Parse error: Incomplete SEARCH/REPLACE block"`
- ❌ Too little context in SEARCH block → matches the wrong occurrence or nothing at all

**Best practices:**
- **Always `read_note` first** — copy the exact text from the file into your SEARCH block
- **Include enough context** — 3-5 lines around the change point for uniqueness
- **If `edit_note` fails** (e.g. `"Parse error: Incomplete SEARCH/REPLACE block"`), fall back to:
  1. `mcp_turbovault_read_note(path=...)` — read full content
  2. Modify in your context
  3. `mcp_turbovault_write_note(path=..., content=..., mode="overwrite")` — full overwrite
  This bypasses the parser entirely and is always safe.
- **Prefer `write_note` for files with complex structure** — YAML frontmatter, pipe tables `|`, brackets `[]`, backticks, and multi-line lists can confuse the SEARCH/REPLACE parser. Full read + write avoids these edge cases entirely.

### Pitfall: frontmatter field queries with the wrong tool

- `mcp_turbovault_search(query="type: analysis")` is a full-text search and does NOT support field filters. It will error with messages like `Field does not exist: 'type'`.
- Use one of:
  - `mcp_turbovault_search_by_frontmatter(key="type", value="analysis")`, or
  - `mcp_turbovault_query_frontmatter_sql`:
    ```sql
    SELECT path FROM files WHERE type = 'analysis';
    ```
- For graph-derived topics, prefer `get_forward_links`/`get_backlinks` over text search.

**Pitfall:** `mcp_turbovault_search` and `advanced_search.query` are **full-text only**. They do *not* understand `field:value` filters like `type: analysis` — that syntax will error with "Field does not exist". For field-aware queries, always use `search_by_frontmatter` or `query_frontmatter_sql`.

**Scope warning:** `search`, `advanced_search`, and `semantic_search` search the **entire vault**, not a subdirectory. Always check the `path` prefix in results, or use `exclude_paths` in `advanced_search` to filter out non-target directories.

### SQL Query Limitations

`mcp_turbovault_query_frontmatter_sql` provides SQL access to three tables (`files`, `links`, `tags`), but **TurboVault SQL is NOT full SQLite.** Do not assume arbitrary SQL features work.

**Known non-working patterns:**
- ❌ Multi-table joins with `json_each()` — e.g. `SELECT path FROM files, json_each(topics) ...` fails because the SQL engine does not support that shape
- ❌ `LIKE` filters on array frontmatter fields — e.g. `WHERE topics LIKE '%MoC%'` fails on null/array values

**Working patterns (preferred):**
- ✅ Simple filtered reports: `SELECT path, type, description FROM files WHERE type = 'moc' ORDER BY path LIMIT 50`
- ✅ Link queries: `SELECT source, target FROM links WHERE source = 'area/agents/+Agents.md' LIMIT 50`

**For navigation and relationship discovery,** prefer TurboVault's graph tools — they're faster, more reliable, and avoid SQL engine quirks:
- `get_forward_links(path)` — curated outgoing links
- `get_backlinks(path)` — body-wikilink backlinks
- `get_related_notes(path, max_hops=1..2)` — nearby graph context
- `get_metadata_value(file, "topics")` — cheap Note → MoC lookup
- `inspect_frontmatter` — discover available columns before writing queries

## Graph & Connection Tools

TurboVault provides graph analysis tools for finding relationships between notes — used by vault-ops for MoC navigation and by vault-wiki for lint/orphan detection.

| Tool | What it does | Best for |
|------|-------------|----------|
| `get_backlinks` | All notes linking TO a given note | Reverse references, orphans, MoC→children |
| `get_forward_links` | All notes a given note links TO | Outbound link count, finding broken targets |
| `get_related_notes` | Notes within N hops in the link graph | Topic cluster discovery, expanding exploration |
| `recommend_related` | ML-powered recommendations | AI suggestions beyond direct link traversal |
| `find_similar_notes` | TF-IDF cosine similarity by content | Conceptual matches, finding duplicates |
| `suggest_links` | AI-powered link suggestions for a note | Finding pages a note should link to |
| `get_link_strength` | Connection strength (0.0–1.0) between two notes | Quantifying how closely two notes relate |
| `get_hub_notes` | Top N most connected notes | Finding central/organizing pages |
| `get_centrality_ranking` | Full graph centrality metrics | Understanding structural importance |
| `get_dead_end_notes` | Notes with incoming but NO outgoing links | Finding incomplete pages, knowledge dead-ends |
| `get_isolated_clusters` | Disconnected subgraphs | Orphaned wiki domains, project silos |
| `detect_cycles` | Circular reference chains | Debugging unintended link loops |
| `get_broken_links` | All broken wikilinks vault-wide | Entry point for link repair |

**Entry-point pattern:** Most interaction starts with `get_backlinks` (reverse lookup) or `get_forward_links` (forward check). Advanced tools (centrality, cycles, clusters) are usually only needed during vault health audits.

**Note:** `suggest_links` and `recommend_related` use LLM inference and cost per call — use sparingly. Prefer `get_related_notes` (zero-cost, deterministic) for routine discovery.

## Batch Operations

When creating or updating multiple files atomically:

```
mcp_turbovault_batch_execute(operations=[
  {type: "WriteNote", path: "path/to/note1.md", content: "..."},
  {type: "WriteNote", path: "path/to/note2.md", content: "..."},
  {type: "EditNote", path: "path/to/note3.md", edits: "..."},
])
```

All operations succeed or fail as one transaction. Use this for:
- Ingest passes that create/update 3+ files
- Structural changes (rename a note type across files)
- Any multi-file operation where partial writes would leave the vault inconsistent

## Verification

Tool responses are authoritative — `write_note` returns success, `edit_note` returns `blocks_applied`, `move_note` returns success. No extra `read_note` needed.

**If the user reports files missing in Obsidian:** Files exist on disk. Obsidian's file tree is cached at startup — Ctrl+R / Cmd+R refreshes it. Check with `terminal -> ls -la /path/to/vault/...` to confirm. This is not a write issue.

**For structural changes** (moves, renames, deletes): Check backlinks with `mcp_turbovault_get_backlinks` and update any broken wikilinks.

## Safe renames and refactors (link-preserving)

When renaming or moving notes inside a vault, use TurboVault so wikilinks update Obsidian-style across the vault.

Recommended procedure:

1) Move/rename the note:
   - `mcp_turbovault_move_note(from="analysis/testing-existing.md", to="analysis/vandv-existing.md")`
   - For batch jobs (multiple files), call `move_note` per file; avoid raw filesystem moves.

2) Do not assume inbound links were updated.
   - Even though the desired outcome is Obsidian-style link preservation, verify what actually happened in this session/tool version.
   - Immediately search the vault for the old basename/path and inspect backlinks or broken links.
   - If old-path wikilinks remain, patch them explicitly.

3) Fix residual MoC content, headings, aliases, and semantic drift.
   - Use `edit_note` with SEARCH/REPLACE blocks when the change is structural (e.g., `# +Testing` -> `# +VandV`).
   - After a rename, review surrounding prose for outdated terminology such as `V&V` vs `testing`, old aliases, and stale link display text. Link updates alone are not enough.
   - Important: file renames do not rename heading anchors/section IDs inside the target note. If other notes link to `[[...#OLD-ID]]`, you must rename the headings/IDs in the note body and then update all anchor links across the vault.

4) Verify:
   - `mcp_turbovault_get_broken_links` -> ensure 0 new broken links.
   - Search the vault for the old basename/old wikilink target to catch stale references outside the graph.
   - Search for old anchor IDs / section IDs (for example `VANDV-METHODS-*`) and update every reference, including compiled/docs notes that may store plain-text evidence IDs rather than wikilinks.
   - Search for literal vault-note paths like `csl/analysis/<name>.md`; convert those to wikilinks if they are note references rather than repo evidence.

5) Link style with ambiguous basenames:

   - For unique basenames prefer simple `[[basename]]`.
   - If the vault uses path-qualified wikilinks (for example `[[analysis/kafka-migration]]`), update those explicitly after the move; do not assume every reference is a plain basename link.

Pitfall: Avoid filesystem-level `mv` for vault notes. It will NOT update inbound links and MoCs; use `move_note` instead.

Pitfall: If TurboVault/MCP is unavailable in the current session, do not stop at the rename alone. Fall back to a repo-level rename plus explicit text search for both plain wikilinks (`[[basename]]`) and path-qualified wikilinks (`[[dir/basename]]`), then verify there are no remaining occurrences of the old target.

### `edit_note` Parse Errors

**Signal:** `"Parse error: No SEARCH/REPLACE blocks found"` or `"Parse error: Incomplete SEARCH/REPLACE block"`

**Likely causes (in order of frequency):**
1. **Wrong delimiter format** — used plain `SEARCH`/`REPLACE` instead of `<<<<<<< SEARCH`/`=======`/`>>>>>>> REPLACE`
2. **Missing `REPLACE`** — closing delimiter is just `>>>>>>>` instead of `>>>>>>> REPLACE`
3. **Special characters** — content contains pipes `|`, brackets `[]`, backticks, or multi-line YAML frontmatter that confuses the parser

**Fix:** Always fall back to full read + write: `read_note` → modify → `write_note(mode="overwrite")`.

### Stale Obsidian UI

**Signal:** User says "I can't see the file in Obsidian" but the file exists on disk.

**Cause:** Obsidian's file tree is cached at startup. Files written externally (via TurboVault/terminal) aren't visible until Obsidian refreshes.

**Fix:** User presses Ctrl+R (Windows/Linux) or Cmd+R (macOS) to reload the file tree. This is not a sync issue.

### Freshness Check: Re-extract, not git ls-remote

**Pitfall — don't use `git ls-remote` for source freshness:** When ingesting a GitHub repo into the wiki, only the README (and select docs) are extracted as raw source markdown files — not a git clone. `git ls-remote` compares commits, not content — a README-only change between two commits won't be detected, but a CI-only change will trigger a false positive.

**Correct approach:** Re-extract the source URL and compare the SHA256 hash of the fresh content against the stored hash. This works for all source types (articles, papers, repos) and detects actual content drift.
- Local drift: `sha256sum` on disk → compare with stored `sha256` in frontmatter
- Remote freshness: `web_extract` the `source_url` → `sha256sum` fresh content → compare with stored `sha256`

Both use the same stored SHA256. No additional frontmatter fields needed.

### No Active Vault

**Signal:** Tool calls fail because no vault is active.

**Fix:** `mcp_turbovault_set_active_vault(name="<vault-name>")` followed by `mcp_turbovault_get_vault_context` to confirm.

## Applying templates safely (frontmatter and bodies)

- Treat templates as schema, not literal values. Use `mcp_turbovault_update_frontmatter(merge=true)` to add missing keys without overwriting real content.
- Structural fields: safe to normalize automatically (e.g., `type`, version fields like `analysis`).
- Descriptive/time fields (`description`, `updated`) and navigation metadata (`tags`, `topics`) should not be stamped with placeholders across the vault; prefer empty values only when missing, and avoid overwriting existing real values.
- In frontmatter templates, put human guidance in YAML comments (lines starting with `#`) and keep the actual values empty (e.g., `description: ""`, `updated: ""`, `tags: []`, `topics: []`).
- In document bodies, use HTML comments `<!-- TEMPLATE: ... -->` for instructions that must not ship to readers.

## Frontmatter queries: pick the right tool

- `mcp_turbovault_search` is full-text only — it does NOT support field filters like `type: analysis`.
- Use `mcp_turbovault_search_by_frontmatter(key="type", value="analysis")` or `mcp_turbovault_query_frontmatter_sql` instead when you need to filter by a frontmatter column.
- Discover available columns first with `mcp_turbovault_inspect_frontmatter`.

## Self-Improvement Gate

This skill is the **stable core.** Do not edit it.

All optimizations, pitfalls, and discovered workflows belong in
**`vault-improvements`** — loaded via the `/vault` bundle alongside this skill.

Note: `vault-improvements` is expected to exist, but may be profile-local. If it’s missing, record the improvement in a local support file under a relevant skill (or ask the user to install/enable `vault-improvements`) rather than editing this stable core.

When a lesson learned emerges:
1. Do NOT edit this file or its original references — they are the stable core
2. Instead, write the finding into the `vault-improvements` skill as a new
   reference entry or section
3. Abstract properly: remove proper names, local paths, session dates,
   one-off tool names before writing
4. If a lesson is universal and user-approved, it may later be promoted
   into this skill — but the agent never promotes unilaterally

## References

- **`./references/vault-configuration.md`** — Installing TurboVault, registering vaults, diagnosing connection issues
