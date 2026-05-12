# Vault Navigation

Use `rg` for navigation and discovery. If `rg` is not installed, tell the user and explain that vault navigation guidance in this skill depends on it.

## Navigation Order

Use this order unless the vault's `AGENTS.md` defines something more specific:

1. Start from the vault root `AGENTS.md` and `README.md`
2. Look for entry points such as `index.md`, `+index.md`, or top-level MoCs with a leading '+' sign in the filename.
3. Follow wiki links to move through related notes.
4. Use `rg` against filenames, frontmatter, and backlinks when you need targeted discovery.

## Ripgrep Patterns

Use these patterns as defaults. Adjust paths to match the vault layout.

### Structured Property Query

Query specific frontmatter fields.

```bash
rg '^type: tension' notes/
rg '^status: evergreen' notes/
```

### Backlink Discovery

Find notes that link to a target note.

```bash
rg '\[\[Note Title\]\]' --glob '*.md'
```

### Faceted Filter

Combine multiple frontmatter filters.

```bash
rg '^type: pattern' notes/ | xargs rg -l '^methodology: Original'
```

### Topic Query

Find notes assigned to a topic in frontmatter.

```bash
rg '^topics:.*\[\[methodology\]\]' notes/
```

### Integrity Scan

Find notes that are missing required metadata.

```bash
rg -L '^description:' notes/*.md
```

### Description Scan

Scan descriptions before opening full files.

```bash
rg '^description:' notes/
```

## Search Decision Table

Use this table as guidance:

| Task | Mode | Tool | Description |
| --- | --- | --- | --- |
| File Path/Title Check | Keyword | `rg` | Instant and precise for exact matches. |
| YAML Field Query | Keyword | `rg` | Best for deterministic structural filtering. |
| Conceptual Exploration | Semantic | `vector` | Not yet implemented. Use `rg` instead. |
| Duplicate Detection | Semantic | `vector` | Not yet implemented. Use `rg` instead. |
| High-Stakes Connection | Hybrid | `deep` | Not yet implemented. Use `rg` instead. |

## Topics Links

### Frontmatter Topics

Put topic links in frontmatter so they can be queried without reading the full note body.

Preferred format:

```yaml
topics: ["[[topic-name]]"]
```

### Body Or Footer Topics

Also include inline wiki links in the body or footer so the note participates in backlink-based navigation.

Use both: frontmatter topics for filtering, inline links for traversal.
