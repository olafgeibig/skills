# Writing Bookmarks

## When to Use

Bookmarks are curated, structured lists of external resources (tools, articles, services, products, books, videos, etc.) on a topic. Each entry links to an external source with lightweight metadata. Create or extend bookmark notes on explicit user request or when AGENTS.md defines them as the correct place for external-resource lists.

**Use bookmarks for:** Curated lists of external resources.
**Use notes/zettel for:** Atomic knowledge about a single concept/entity.
**Use MoCs for:** Navigable hubs linking your own vault notes.

## Template

The vault's `system/templates/bookmarks.md` defines the canonical format when it exists. If the vault has no template, use this default:

```markdown
---
description: Curated bookmarks for {topic}
type: bookmarks
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags:
  - area/<area-name>
topics:
  - "[[+AreaMoC]]"
---

# 🔖 {topic} Bookmarks

(short explanation of the scope of the bookmark list)

## {Category}

### {Resource Title}
- description: {What is it? One concise paragraph}
- Link: {URL}
- Date: {date added}

---

Topics:
- [[+AreaMoC]]
```

## Workflow

1. **Identify the area:** Map the user's topic to the vault's area structure (area/INDEX.md → area map).
2. **Read the template:** prefer `system/templates/bookmarks.md` when present.
   - The vault template is the default for **new** files.
   - Extensions keep the target file's format — bold vs plain `- description:` stays per file, never unified globally.
3. **Read an existing example** in the same or a similar area for live format reference.
4. **Check for an Area MoC** — if the vault's area has a `+AreaName` MoC, link to it in `topics:` and in the body `Topics:` section. If none exists, leave `topics: []`.
5. **Create the note** with proper frontmatter:
   - `type: bookmarks`
   - `tags: [area/<name>]`
   - `topics: ["[[+AreaMoC]]"]` (or empty if no MoC)
6. **Structure entries** into logical categories (e.g. "Official", "Community", "Tools", "Articles", "Videos").
7. **Each entry needs:** description, Link, Date. Optional: Source, Install, Price, Author, Version.
8. **Register the file in both MoCs** when it mirrors the area MoC's `## Bookmarks` section: the area MoC **and** the sub-MoC, each with a one-liner in the MoC body's language.
   - Without a MoC entry the file is invisible in the graph — no backlink, no triage.
   - Bump `updated:` in both MoCs.
9. **Add a `See also` section** with 3–4 path links to sibling files and the next related note.

## Adding Entries to Existing Bookmark Notes

Always:

- Read the current content first (`mcp_turbovault_read_note`).
- Use `mcp_turbovault_write_note` with `mode="overwrite"` with the full updated content, OR use `mcp_turbovault_edit_note` with targeted SEARCH/REPLACE.
- Never overwrite without reading first.
- Keep duplicate links out unless the duplicate is intentionally listed in another category with a distinct purpose.
- Get repo facts from the API, not the page: `curl -s https://api.github.com/repos/<owner>/<repo>` returns `stargazers_count`, `license.spdx_id`, `language`, `created_at`, `pushed_at`.
- Repo pages and search hits give contradictory or stale numbers; the API is the evidence base for `- Stars:` / `- License:` in the entry.
- Don't invent fields: use only the target file's field set (`- Link`, `- License`, `- Stars`, `- Date`, …).
- If the file has no `- Related:`, put cross-references inline in the `description` instead of adding a bullet.
- Cite the canonical repo, not a dead mirror: when the API `description` says `MOVED TO …` with `archived: true` and a years-old `pushed_at`, those numbers are frozen — don't quote them.
- Frozen numbers often sit above the real ones — query the forge named in `homepage` instead.
- If the project explicitly asks not to back-fork there, keep the mirror as a remark in the entry, not as a link.

## Related

- `./references/note-writing.md` — for atomic notes (zettel)
- `./references/moc-writing.md` — for Maps of Content
- `skill-governance` — for routing reusable improvements to the correct owning skill or project
