# Source Cascade Removal

Remove a raw source and its derived wiki pages (entities, concepts, etc.)
while preserving multi-sourced pages.

## Prerequisites

This workflow depends on consistent `sources:` tracking in page frontmatter.
Every wiki page that was created from a raw source should list it in frontmatter:

```yaml
---
sources:
  - wiki/<domain>/raw/articles/source-article.md
  - wiki/<domain>/raw/articles/another-source.md
---
```

Pages without `sources:` frontmatter cannot be automatically attributed — they
must be manually reviewed.

## How to Determine Causality

| Evidence | Reliability | Method |
|----------|-------------|--------|
| `sources:` in frontmatter references the source | ✅ High — explicit attribution | `search_by_frontmatter` for the source path |
| Page title/text matches source filename/title | ⚠️ Medium — heuristic | Full-text search for source-related terms |
| Page created on same date as source was ingested | ⚠️ Medium — assume correlation | Cross-reference `log.md` entries with page `created` dates |
| No evidence at all | ❌ Low — skip | Report for manual review |

**Default mode:** Use `sources:` frontmatter as authoritative evidence.
Only fall back to heuristic or date-based matching if the user asks for
aggressive cleanup.

## Workflow

### ① Identify the raw source to remove

The user provides the path: `wiki/<domain>/raw/articles/<file>.md` or
`wiki/<domain>/raw/papers/<file>.md`.

Read its frontmatter for reference metadata.

### ② Find all pages that reference this source

```bash
mcp_turbovault_search(query="raw/articles/<filename>")
```

Filter results for `wiki/<domain>/entities/`, `concepts/`, `comparisons/`,
`queries/` paths. Each match is a candidate.

Also check `sources:` via frontmatter:

```bash
mcp_turbovault_advanced_search(
  query="sources",
  frontmatter_filters=[{key: "sources", value: "<filename>"}]
)
```

### ③ Classify each candidate page

For each page found, read its frontmatter:

| If `sources:` contains... | Classification |
|---------------------------|---------------|
| **Only this source** | **Delete candidate** — page is entirely derived from this source |
| **This source + others** | **Update candidate** — remove this source from frontmatter; page survives |
| **No `sources:` field** | **Review candidate** — cannot attribute; flag for user |

### ④ Execute the cascade

**For each delete candidate (single-source):**

1. Report to user: "`<page.md>` is derived only from this source. Should I
   delete it?"
2. If confirmed: `mcp_turbovault_delete_note(path="wiki/<domain>/entities/<page>.md")`
3. Update `<name>-wiki.md`: remove the entry for this page
4. Log the deletion in log.md

**For each update candidate (multi-source):**

1. Read the page content
2. Update frontmatter: remove the deleted source from `sources:`
3. Optionally update the page body if it heavily relied on this source
4. Write back via `write_note` or `edit_note`

**For review candidates (no sources):**

1. Read the page content
2. Ask the user: "`<page.md>` has no `sources:` field. Should I delete it,
   keep it, or review manually?"
3. Delete or keep based on user decision

### ⑤ Clean up cross-references

After deletions, run lint check ② (broken links) and ③ (outbound link count)
to catch any remaining broken wikilinks from deleted pages.

### ⑥ Delete the raw source itself

After all derived pages are handled:

```bash
mcp_turbovault_delete_note(path="wiki/<domain>/raw/articles/<file>.md")
```

Or for bulk (multiple raw sources): `terminal rm` like archiving.

### ⑦ Update wiki metadata

1. Update `<name>-wiki.md` — remove any entries for deleted pages
2. Log the operation in `log.md`
3. Re-run lint to verify no breakage

## Limitations

| Scenario | What happens |
|----------|-------------|
| Page has `sources:` — only this source | 🟢 Delete candidate — clean removal |
| Page has `sources:` — multiple sources | 🟢 Update candidate — survives |
| Page has NO `sources:` field | 🟡 Review candidate — needs user decision |
| Entity mentioned in other pages' wikilinks | 🟡 Broken links — need cleanup (step ⑤) |
| 10+ pages affected by cascade | 🟡 Ask before bulk deletion — user may prefer selective review |

## Pitfalls

- **Don't delete a page just because it references this source** — the page
  may contain knowledge from other sources or the user's own synthesis.
  Always check `sources:` first, ask if unsure.
- **Don't skip the cross-reference cleanup** — deleted pages leave broken
  wikilinks in other pages. Always run lint after cascade.
- **Don't cascade automatically** — always report the plan and ask before
  deleting. A page derived from one source may still be valuable (user
  added their own analysis).
