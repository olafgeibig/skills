# Lint Workflow

Run this when the user asks to lint, health-check, or audit the wiki. Uses
TurboVault's built-in analysis tools and manual scoped checks.

## ① Quick Health Overview

```bash
mcp_turbovault_full_health_analysis()
```

Returns broken links, orphan analysis, link density, cluster analysis, and
recommendations. Filter results for `wiki/`-prefixed paths.

## ② Broken Wikilinks

```bash
mcp_turbovault_get_broken_links()
```

Returns all broken links in the vault. Filter to `wiki/`-prefixed source paths.
Expected: only SCHEMA.md template examples should be broken — those are fine.

## ③ Outbound Link Count (wiki pages only)

Every wiki page in entities/, concepts/, comparisons/, queries/ must have at
least 2 outbound wikilinks to OTHER wiki pages (not raw/ sources). Raw sources
are exempt.

Use `mcp_turbovault_get_dead_end_notes()` to find pages with 0 outbound links.
For pages with 1 outbound link, manually check forward links:

```bash
mcp_turbovault_get_forward_links(path="wiki/<target>/entities/<page>")
```

**This is the most common failure mode.** Add missing "Verwandte Konzepte"
or "Verwandte Seiten" sections to fix.

## ④ Frontmatter Validation

```bash
mcp_turbovault_inspect_frontmatter()
```

Check that every wiki page (entities/, concepts/, comparisons/, queries/) has
all required fields: title, created, type. Tags must be in the taxonomy.
Note: `<name>-wiki.md`, `log.md`, `SCHEMA.md` are meta-files — skip them.
Raw sources: check if they have frontmatter (check the domain wiki's `SCHEMA.md`).

## ⑤ Index Completeness

Compare the filesystem (pages with `wiki/<target>/entities/`, `concepts/`, etc.
paths) against entries in the target wiki's `<name>-wiki.md`. Use
`mcp_turbovault_search(query="")` with path prefix to discover all pages.

## ⑥ Contradictions

Find pages with `contested: true` or `contradictions:` in frontmatter:

```bash
# Pages explicitly marked as contested
mcp_turbovault_search_by_frontmatter(key="contested", value="true")

# Pages with contradictions field set (existence check)
mcp_turbovault_query_metadata(pattern="contradictions: *")
```

Also scan pages that share tags but state conflicting claims — these are
candidates for explicit contradiction frontmatter. Report all found pages
for user review.

## ⑦ Quality Signals

Find pages with `confidence: low`:

```bash
mcp_turbovault_search_by_frontmatter(key="confidence", value="low")
```

These are candidates for either finding corroboration or demoting to
`confidence: medium`. Also flag wiki pages with no `confidence` field at
all — consider whether they should have one.

## ⑧ Orphan Pages

Pages with no inbound links from other wiki pages. For each wiki page, check:

```bash
mcp_turbovault_get_backlinks(path="wiki/<target>/entities/<page>")
```

Pages in entities/, concepts/, comparisons/, queries/ with 0 backlinks from
other wiki pages = orphan. Raw/ pages are always orphans by design — skip them.
Meta files (`<name>-wiki.md`, log, SCHEMA) are always orphans — skip them.

## ⑨ Tag Taxonomy

List all tags on wiki pages, flag any not in the domain wiki's `SCHEMA.md`
taxonomy. Raw sources use their own tag conventions — skip.

## ⑩ Stale Content

```bash
mcp_turbovault_find_stale_notes(threshold_days=90)
```

Filter to `wiki/`-prefixed paths. Pages whose `updated` date is older than
90 days from the most recent source that mentions the same entities.

## ⑪ Page Size

Flag pages over 200 lines — candidates for splitting. Use
`mcp_turbovault_read_note` and check content length per note.

## ⑫ Log Rotation

If the domain wiki's `log.md` exceeds 500 entries, rotate it: read the log,
rename to `log-YYYY.md` via write_note, start fresh log.

## ⑬ Report Findings

With specific file paths and suggested actions, grouped by severity
(broken links > missing outbound links > contradictions > orphans > stale > style).

## ⑭ Fix Issues Iteratively

After fixing, re-run the relevant checks. The typical pattern is:
fix page A → discover page B now has outbound links → fix page B →
discover page C is now orphan → fix page C.
Do NOT fix all pages in one pass without re-checking.

## ⑮ Log the Lint

Append to the domain wiki's `log.md`:

```markdown
## [YYYY-MM-DD] lint | N issues found
```

## Cross-wiki Lint

### ⑯ Broken Cross-wiki Links

`mcp_turbovault_get_broken_links()` catches all broken wikilinks across the
entire vault, including `[[wiki/other-wiki/...]]` links pointing to
non-existent pages.

### ⑰ Hub Drift

Check that root `wiki/index.md` hub sections match what's on disk (directory
names under `wiki/`). Flag domain directories on disk not listed in the hub,
and hub sections with no matching domain directory.

### ⑱ Source Drift (sha256)

For every raw source file that has a `sha256` frontmatter field, verify the
content has not changed since ingest:

```bash
sha256sum /path/to/vault/wiki/<target>/raw/articles/<file>.md
```

Compare the first 16 characters against the stored `sha256` value in frontmatter.
- **Match** → content is unchanged. Skip.
- **Mismatch** or **missing sha256 field** → content has drifted.

**For each drift found, report:**
- Path to the drifted raw source
- Old hash (if present) vs new hash
- Ask the user: "This raw source has changed since ingest. Should I re-read it
  and update the wiki pages derived from it?"

**Do NOT automatically re-ingest.** A changed hash doesn't mean the new content
is better — the user decides.

**Implementation notes:**
- `mcp_turbovault_search_by_frontmatter(key="sha256")` discovers all raw sources
  that have a hash on file
- Raw sources without a `sha256` field are pre-existing (prior to this feature)
  — report them once as un-hashed sources, do not flag them every lint
- The terminal command runs on the local filesystem path, not an MCP tool
