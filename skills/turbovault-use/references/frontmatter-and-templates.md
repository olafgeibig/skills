# Frontmatter and Template Operations

## Querying metadata

Use `inspect_frontmatter` before writing repository-specific SQL. Use `search` with `frontmatter_filters` or `query_frontmatter_sql` for metadata filters; full-text search does not interpret `field:value` syntax.

`get_notes_info(paths, frontmatter_keys, include_tags)` reports requested keys that are absent as `null`, and `include_tags: true` returns `tags` as an object — `{frontmatter_tags, inline_tags, all_tags}` — not a plain list.

## Writing frontmatter

`update_frontmatter` merges the given keys into the existing frontmatter by default; `merge: false` replaces the whole block. In 4.0 an empty object is a no-op that still reports `success: true` with `keys_set` echoing what was already there — so pass at least one key, and read the note back instead of trusting success alone. A `write_note` whose content already includes the frontmatter line needs no separate stamp.

`manage_tags` only adds or removes (`operation: add|remove`, `tags` as a list); listing a note's tags is `get_notes_info` with `include_tags: true`.

## YAML-invalid frontmatter

An unquoted `: ` inside a YAML value (e.g. `description: … Sprache: DE.`) invalidates the entire frontmatter. Obsidian still shows it, but `query_frontmatter_sql` returns NULL for its fields, `get_notes_info` returns `null` for its frontmatter keys, and `update_frontmatter` fails with "mapping values are not allowed in this context" — while `get_notes_info` still reports `has_frontmatter: true`. Such notes are metadata-blind (routing, health report, `search (frontmatter_filters)`), though their body links stay in the graph. Fix: quote or shorten the value, then verify against `query_frontmatter_sql`, not Obsidian. Vault-wide scan: `yaml.safe_load` every frontmatter block (regex gives false positives), collect non-UTF8 files separately, leave `wiki/` hits alone.

## Applying templates

`list_templates` returns TurboVault's own templates (built-ins such as `task`, `doc`, `research`, plus whatever `template_dirs` adds) — **not** the files in a vault's `system/templates/`. `create_from_template` fills one of those, takes `fields` as a string and records the template in the note's frontmatter; it refuses to replace an existing note. A vault that keeps its own template files is therefore still hand-written (read the template, write the note), which is what the rest of this section covers.

Treat templates as schemas, not literal values.

- Use `update_frontmatter` with merge behavior for missing structural keys.
- Do not overwrite real descriptions, dates, tags, or topics with template placeholders.
- Keep instructional text in YAML comments when it must stay in a frontmatter template.
- Use HTML comments for body guidance that must not appear in published content.
- Follow the selected vault's `AGENTS.md` before generic templates.

Structural fields may be normalized when their target value is known. Descriptive, temporal, and navigation fields require note-specific decisions.

## Bulk normalization

Before a bulk pass:

1. inventory current fields and missing values;
2. define target scope and exclusions;
3. separate structural changes from content-derived fields;
4. use atomic operations when partial state would be invalid;
5. read back representative and exceptional notes;
6. rerun the metadata query and graph checks.

Never stamp placeholder values across a vault merely to make fields non-null.
