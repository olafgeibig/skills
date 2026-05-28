# Legacy Note Import Workflow

When a user copies notes from an external source (old vault, text files, personal wiki, etc.) into a project or area directory, they arrive without frontmatter, with legacy task formats, and unlinked from the vault graph. Follow this workflow to integrate them.

Pitfalls:
- `advanced_search` by keyword is NOT sufficient to find all imported files — it misses files without matching keywords.
- The same file may appear in multiple search results, giving a false sense of completeness.
- Jumping straight to frontmatter addition without a full file inventory causes orphan notes to remain unprocessed.

## Step 1: Discover All Imported Files

Do NOT rely on keyword search. Use a SQL query to list every file in the target directory:

```sql
SELECT path, type, tags, topics FROM files WHERE path LIKE 'projects/<project>%' ORDER BY path
```

Identify files where `type IS NULL` — those are the unprocessed imports.

## Step 2: Read & Assess

Read each unprocessed note. Determine:
- **Topic and scope:** What area of knowledge does it cover?
- **Clarity:** Is the content self-explanatory? Note ambiguities to ask the user about.
- **Task formats:** Does it use legacy syntax (`#tag` in tasks, `@completed(ISO-date)`, plain `✅ date`)?
- **Type fit:** Is it an atomic fact (→ `type: zettel`) or a structured list of references (→ `type: bookmarks`)?

## Step 3: Clarify with User (Before Editing)

Ask specific questions when:
- Content contains unclear terms, abbreviations, or apparent typos (e.g. "erlauft" → "verkauft"?).
- Tasks may have been completed since the note was exported — ask before marking them done.
- A decision is needed about note naming or scope consolidation.

Do NOT auto-interpret ambiguous content. The user will confirm or correct, saving rework.

## Step 4: Add Frontmatter

Per vault `AGENTS.md` conventions:

```yaml
---
description: ~150 chars, search-optimized, no trailing period
type: zettel  # OR bookmarks for structured lists of external links
created: YYYY-MM-DD
tags:
  - project/<dir>   # matching the project directory
topics:
  - "[[+<MoC-name>]]"
---
```

## Step 5: Convert Legacy Task Formats

| Legacy Format | Obsidian Tasks Equivalent |
|---|---|
| `#topic` inline tag | Remove tag; add `🆔 project-topic-id` |
| `@completed(2024-01-15T12:00:00)` | Replace with `✅ 2024-01-15` |
| `✅ 2023-03-16` (plain) | Keep as `✅ 2023-03-16` (already valid) |

Patterns for open tasks:
```
- [ ] Task description 🆔 whv-topic-id
- [ ] Task description 📅 2026-06-01 ⏫ 🆔 whv-topic-id
```

Patterns for completed tasks:
```
- [x] Task description ✅ 2024-02-03 🆔 whv-topic-id
- [x] Task description ⏫ ✅ 2024-02-03 🆔 whv-topic-id
```

## Step 6: Add Body Footer

Every note body must end with an explicit wikilink to its parent MoC for graph traversal:

```markdown
---

Topics:
- [[+<MoC-name>]]
```

## Step 7: Update the Project MoC

Add an entry for each new note in the project's `+<Project>.md` MoC under the Kernnotizen section:

```markdown
- [[WHV Topic]] — Brief description of what the note covers
```

## Step 8: Verify Zero Unprocessed Files

Run the discovery SQL from Step 1 again. Confirm every file in the target path has `type IS NOT NULL` and `tags IS NOT NULL`.

Full verification query:
```sql
SELECT path, type, tags, topics FROM files WHERE path LIKE 'projects/<project>%' ORDER BY path
```

If any row still shows `NULL`, that file was missed — return to Step 2.
