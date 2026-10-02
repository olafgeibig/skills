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
- description: {What it is and what sets it apart — 2-4 sentences for tools/repos}
- Link: {URL}
- Date: {date added}

---

Topics:
- [[+AreaMoC]]
```

## Entry Descriptions

Default `- description:` to 2-4 comparison-ready sentences for tool/repo entries, not terse one-liners — what it is / what problem it solves, the differentiating claim (benchmark, architecture, unique feature), and maturity signals (stars, version, license) when relevant. Keep `Install:` a separate field when installation is non-trivial; frontmatter `description:` rules elsewhere stay unchanged. For articles, videos, and other non-tool entries, keep to 1–2 sentences.

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

## Multi-Category Sectioning

At 3+ entries across meaningfully different sub-topics — or when a new file is built for a multi-tool domain — split a `*-bookmarks.md` into peer-level `## <Sub-Category>` headings, not one lumped `## Tools` H2. Name sub-categories by consumer purpose, not tool type ("Evaluation Harnesses" > "Eval Tools" — what is the user trying to do with these tools?); a single entry under a new sub-category is fine. Insert new sub-categories before an existing `## Tasks` section — Tasks is always last.

## Tasks in Bookmark Files

Attach a task to a bookmark file only on explicit user request ("add a task to the bookmark: …") — never as a proactive suggestion. Home is a `## Tasks` section after all bookmark entries and sub-categories, not a `- Task:` line inside an entry. This is the deliberate exception to the general inline rule in `task-management.md`. Use Obsidian Tasks syntax (`- [ ] <description> — <context> 📅 YYYY-MM-DD ⏫`), reference the entry in the task only if it adds clarity, and bump `updated:`.

## Capturing an Entry from a Shared Link

When a link is dropped with "add this to the <topic> bookmarks":

1. **Resolve the shortener first** — `curl -sIL -o /dev/null -w '%{url_effective}\n' <url>`. A `t.co`/`bit.ly` URL is not a bookmark target: it rots and hides provenance. The entry links to the resolved destination; the original post URL goes under `- Source:`, annotated with author/handle and what the post actually contains — a bare link or text that merely restates the repo description.
2. **Mine the primary source for claims, not the post.** Post text restates marketing copy. Capability claims and the install command come from the README or project site; the numbers from the API (see the API bullet above). Record a verification date ("Verified YYYY-MM-DD: …") when the neighbouring entries use one.
3. **Mirror a neighbour** — reuse the adjacent entries' field subset, order, spelling, and bold/plain `- description:` style. Never "harmonize" the file's other entries.
4. **Anchor the insert on the next `##` heading.** Two SEARCH/REPLACE blocks in ONE `edit_note` call: (1) replace the following `##` heading with `### new entry` + blank line + that heading again — the entry lands inside the intended section; (2) bump `updated:`. A block anchored on a neighbouring entry can land in the wrong category.
5. **`Date:` from the system, immediately before writing** — `date +%F`. A session header can be weeks stale, and a stale `Date:` silently reads as authoritative later.
6. **Read the target back** and confirm the entry sits in the right section — a write response is not proof it landed.
7. **Sync enumerating MoCs.** If the parent MoC or an index line lists what a section holds, add the new name and bump its `updated:` in the same session — otherwise the MoC drifts against the list.
8. **Report terse:** file, entry name, verified numbers, resolved URL.

## Related

- `./references/note-writing.md` — for atomic notes (zettel)
- `./references/moc-writing.md` — for Maps of Content
- `skill-governance` — for routing reusable improvements to the correct owning skill or project
