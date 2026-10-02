# Frontmatter and Template Operations

## Querying metadata

Use `inspect_frontmatter` before writing repository-specific SQL. Use `search_by_frontmatter` or `query_frontmatter_sql` for metadata filters; full-text search does not interpret `field:value` syntax.

## Empty frontmatter object

`update_frontmatter` with `frontmatter: {}` fails with `frontmatter must be a JSON object` — the validator reads empty as missing. Pass at least one key (e.g. `{"sha256": "<value>"}`), or patch the frontmatter line directly with the `patch` tool anchored on the closing `---`. A `write_note` whose content already includes the new frontmatter line does not trigger `update_frontmatter`; stamp separately or patch it in.

## YAML-invalid frontmatter

An unquoted `: ` inside a YAML value (e.g. `description: … Sprache: DE.`) invalidates the entire frontmatter. Obsidian still shows it, but `query_frontmatter_sql` returns NULL for its fields, `get_metadata_value` reports "No frontmatter in file", and `update_frontmatter` fails with "mapping values are not allowed in this context" — while `get_notes_info` still reports `has_frontmatter: true`. Such notes are metadata-blind (routing, health report, `search_by_frontmatter`), though their body links stay in the graph. Fix: quote or shorten the value, then verify against `query_frontmatter_sql`, not Obsidian. Vault-wide scan: `yaml.safe_load` every frontmatter block (regex gives false positives), collect non-UTF8 files separately, leave `wiki/` hits alone.

## Applying templates

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
