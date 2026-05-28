# Ingest from Vault Inbox into a Wiki

When the user has an article/note already saved in their Obsidian vault's `inbox/`
directory and wants it ingested into one of their domain wikis.

## Prerequisites

- The inbox file exists at a path like `inbox/<filename>.md` in the active vault
- The user has told you the target wiki (or you route via hub abstracts)
- TurboVault is the active vault interface

## Workflow (Two Options)

The user can choose between two approaches:

### Option A: User tells path, agent does everything

Preferred by Olaf (established in session 2026-05-16):

1. User message: `"Ingest inbox/mein-artikel.md in Wiki agents"`
2. Agent reads the inbox file: `mcp_turbovault_read_note(path="inbox/mein-artikel.md")`
3. Agent copies the content as a raw source:
   `mcp_turbovault_write_note(path="wiki/<target>/raw/articles/<descriptive-name>.md", content=...)`
   - Add frontmatter: `source_url: inbox/mein-artikel.md`, `ingested: YYYY-MM-DD`
4. Proceed with normal ingest (check existing → create/update pages → index + log)
5. The inbox original stays untouched — never modify it

### Option B: User pre-copies, agent processes

1. User drags/copies the file into `wiki/<target>/raw/articles/` directly
2. User message: `"Verarbeite raw/articles/datei.md im Wiki agents"`
3. Skip the copy step, start directly at the ingest workflow

## Routing

- If the user names the target wiki, use it
- If unsure, read `wiki/index.md` (the hub) and match the article's topic against
  the wiki abstracts
- If ambiguous, ask the user — don't guess

## Frontmatter for Inbox-Sourced Raw Sources

```yaml
---
title: Original Title
source_url: inbox/original-filename.md    # link back to inbox
ingested: YYYY-MM-DD
type: article | resource | clipping       # match the content
---
```

## Pitfalls

- **Never modify the inbox original.** The inbox is the user's domain. Only
  copy content into the wiki.
- **Check if the source already exists** in the target wiki's raw/ before
  creating a duplicate. Search by title or source_url.
- **Inbox files may lack frontmatter.** Add proper wiki frontmatter in the
  copy, don't rely on the inbox file's metadata.
