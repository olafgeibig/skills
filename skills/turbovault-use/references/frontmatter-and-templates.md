# Frontmatter and Template Operations

## Querying metadata

Use `inspect_frontmatter` before writing repository-specific SQL. Use `search_by_frontmatter` or `query_frontmatter_sql` for metadata filters; full-text search does not interpret `field:value` syntax.

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
