# Optional Pitfalls

These are agent-discovered pitfalls and workflow corrections staged for user review. Do not promote any entry into core `SKILL.md` or stable references without explicit user approval.

## TurboVault SQL Is Not Full SQLite

TurboVault SQL is useful for simple filtered reports over `files`, `links`, and `tags`, but do not assume arbitrary SQLite features work.

Observed durable pattern:

- Multi-table selects such as `SELECT path FROM files, json_each(topics) ...` may fail because the SQL engine does not support that shape.
- `topics` is an array frontmatter field, so direct `LIKE` filters can fail on null/array values.
- For normal navigation, prefer TurboVault graph tools:
  - `mcp_turbovault_get_forward_links(path)` for curated outgoing links.
  - `mcp_turbovault_get_backlinks(path)` for body-wikilink backlinks.
  - `mcp_turbovault_get_related_notes(path, max_hops=1..2)` for nearby graph context.
  - `mcp_turbovault_get_metadata_value(file, "topics")` for cheap Note → MoC lookup.
- Use `mcp_turbovault_query_frontmatter_sql` mainly for simple filtered reports, for example:
  - `SELECT path, type, description FROM files WHERE type = 'moc' ORDER BY path LIMIT 50`
  - `SELECT source, target FROM links WHERE source = 'area/agents/+Agents.md' LIMIT 50`

Promotion guidance: keep this as an optional pitfall until the stable `vault-graph.md` and `vault-navigation.md` references have been reviewed and approved.

## Stable Core Must Not Be Self-Modified By Default

The user explicitly wants `SKILL.md` and stable/core references protected from automatic self-improvement. The previous failure mode was letting agent-discovered lessons accumulate directly in `SKILL.md`, which made the skill bloated and too session-specific.

Durable rule:

- Do not patch `SKILL.md` or existing stable references unless the user explicitly names that file/reference in the current task.
- Put agent-discovered improvements into `references/opt-<name>.md`.
- Put caveats and corrections into `references/opt-pitfalls.md`.
- Promotion from `opt-*` into stable references requires explicit user approval.
- Keep improvements generic: remove proper names, one-off tool names, local paths, session dates, and single-project examples unless they are intentionally generic examples.

## Bookmarks Terminology Replaces Resource Collections

Vault Ops renamed the former `resource-collection` concept to `bookmarks` because the name better reflects curated external-resource link lists.

Durable rule:

- Use `type: bookmarks` for curated external-resource lists.
- Use `references/bookmarks-writing.md` for the workflow.
- Prefer `system/templates/bookmarks.md` when a vault-local template exists.
- Do not create new references, templates, or examples using the old `resource-collection` terminology unless migrating legacy notes.