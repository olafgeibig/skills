# Ingest Workflow

Follow this when the user provides a source (URL, file, paste) to integrate into a wiki, or asks to process inbox items.

## 1. Standard Ingest

① **Read the hub:** `mcp_turbovault_read_note(path="wiki/index.md")` to determine
the target wiki. Route using the hub abstracts (explicit naming → abstract match → ask).

② **Capture the raw source** in the target wiki:
   - URL → use `web_extract` to get markdown, save via
     `mcp_turbovault_write_note(path="wiki/<target>/raw/articles/<name>.md", content=...)`
   - PDF → use `web_extract` (handles PDFs), save to `wiki/<target>/raw/papers/`
   - X Article → use xurl CLI (JS-rendered, web_extract can't reach). See `references/x-article-sourcing.md`.
   - Local file → use `web_extract` with file:// URL or copy content, save to `raw/articles/`
   - Pasted text → save to appropriate `raw/` subdirectory in the target wiki
   - Name the file descriptively: `raw/articles/karpathy-llm-wiki-2026.md`
   - **Add raw frontmatter** with `source_url` and `ingested` date for provenance.
   - **⚠️ Paywall/truncated content check:** After extraction, verify the content is the FULL original text. If `web_extract` returns a short summary (<30% of expected article length), a truncated version, or an LLM-generated summary — **DO NOT silently use it as a raw source.** Instead:
     - Label the source `type: extract` and `status: incomplete` in frontmatter
     - Add a prominent warning at the top of the file
     - Tell the user immediately: the full article could not be retrieved (paywall, blocking, etc.)
     - Ask them to provide the full text via inbox, PDF, or alternative method
     - Do NOT create entity/concept pages based on a truncated summary — the synthesis would be unreliable

③ **Discuss takeaways** with the user — what's interesting, what matters for
   the domain. (Skip this in automated/cron contexts — proceed directly.)

④ **Check what already exists** — search the target wiki with
   `mcp_turbovault_search(query="<topic>")` and filter results for
   `wiki/<target-wiki>/` prefix.

⑤ **Write or update wiki pages** in the target wiki:
   - **New entities/concepts:** Create pages only if they meet the Page Thresholds
     in the target wiki's `SCHEMA.md` (2+ source mentions, or central to one source)
   - **Existing pages:** Add new information, update facts, bump `updated` date.
     When new info contradicts existing content, follow the Update Policy.
   - **Cross-reference:** Every new or updated page must link to at least 2 other
     pages via `[[wikilinks]]`. For references to other domain wikis, use direct
     path-based links like `[[wiki/other-wiki/concepts/topic-name]]`.
     Check that existing pages link back.
   - **Tags:** Only use tags from the taxonomy in the target wiki's `SCHEMA.md`

⑥ **Update navigation** in the target wiki:
   - Add new pages to the target wiki's `index.md` under the correct section, alphabetically
   - Update the "Total pages" count and "Last updated" date in the target wiki's index header
   - Append to the target wiki's `log.md`: `## [YYYY-MM-DD] ingest | Source Title`
   - List every file created or updated in the log entry

⑦ **Report what changed** — list every file created or updated to the user.

A single source can trigger updates across 5-15 wiki pages. This is normal
and desired — it's the compounding effect.

## 2. Bulk Ingest

When ingesting multiple sources at once, batch the updates:

1. Read the hub and determine target wikis — sources may span multiple domains
2. Group sources by target wiki
3. For each target wiki, read all sources first
4. Identify all entities and concepts across all sources (per wiki)
5. Check existing pages for all of them in the target wiki (one search pass, not N)
6. Cross-wiki search if topics might exist in other wikis
7. Create/update pages in one pass per wiki (avoids redundant updates)

   For atomic batch execution, use `mcp_turbovault_batch_execute`:
   ```
   mcp_turbovault_batch_execute(operations=[
     {type: "WriteNote", path: "wiki/<target>/entities/foo.md", content: "..."},
     {type: "WriteNote", path: "wiki/<target>/entities/bar.md", content: "..."},
     {type: "WriteNote", path: "wiki/<target>/index.md", content: "..."},
     {type: "WriteNote", path: "wiki/<target>/log.md", content: "..."},
   ])
   ```
   This ensures all operations succeed or fail atomically.

8. Update each wiki's `index.md` once at the end
9. Write a single log entry per wiki covering the batch

## 3. Ingest from Vault Inbox

When the user has an article/note in the vault's `inbox/` directory and asks you to ingest it into a wiki:

**Workflow (two options, let the user choose):**

① User tells me the inbox path + target wiki → I handle everything:
   - Read the inbox file via `mcp_turbovault_read_note(path="inbox/<filename>.md")`
   - Copy it as a raw source: `mcp_turbovault_write_note(path="wiki/<target>/raw/articles/<name>.md", content=...)`
   - The inbox original stays untouched
   - Proceed with normal ingest: check existing pages → create/update → index + log

② User pre-copies the file to `wiki/<target>/raw/articles/` and tells me to process it:
   - Skip the copy step, start directly at checking existing pages

**Frontmatter for inbox-sourced raw sources:**
```yaml
---
source_url: inbox/<original-filename.md>  # reference back to inbox original
ingested: YYYY-MM-DD
---
```

**Pitfall:** The inbox file is the user's original — never modify it. Only copy content into the wiki.
