---
name: md-wiki
description: "Multi-domain LLM Wiki — build and maintain a federation of interlinked markdown wiki knowledge bases. Each domain wiki has its own schema, index, and log, linked across boundaries via path-based wikilinks. Use when user wants to use a wiki (create, ingest into, query, lint)"
license: MIT
metadata:
  hermes:
    tags:
      - wiki
      - knowledge-base
      - research
      - multi-domain
      - federation
    category: research
    related_skills:
      - arxiv
      - vault-ops
  source: https://github.com/olafgeibig/skills
  version: "0.4.3"
---

# Multi-Domain LLM Wiki (TurboVault)

Build and maintain a persistent, compounding federation of knowledge bases as
interlinked markdown files. Based on [Andrej Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f),
extended for multiple domains.

Unlike traditional RAG (which rediscovers knowledge from scratch per query), each
wiki compiles knowledge once and keeps it current. Cross-references are already
there. Contradictions have already been flagged. Synthesis reflects everything
ingested. Multiple focused wikis live under one root — each with its own schema,
index, and log — linked across domain boundaries via path-based wikilinks.

**Division of labor:** The human curates sources and directs analysis. The agent
summarizes, cross-references, files, and maintains consistency across domains.

**Storage:** All wiki content lives in the `wiki/` directory within an Obsidian
vault managed by **TurboVault**. All operations use `mcp_turbovault_*` tools
(read_note, write_note, edit_note, search, batch_execute, get_broken_links, etc.).
Paths are relative to the vault root with a `wiki/` prefix.

## When This Skill Activates

Use this skill when the user:

- Asks to create, build, or start a wiki
- Asks to ingest, add, or process a source into their wiki
- Asks a question and an existing wiki exists in the active vault's `wiki/` directory
- Asks to lint, audit, or health-check their wiki
- References their wiki, knowledge base, or "notes" in a research context
- Mentions a specific domain wiki by name (e.g., "add this to my ai-research wiki")
- Asks to create a new domain wiki

## Wiki Location

The wiki lives at `wiki/` within the **active TurboVault vault**. Set the active
vault at the start of each session:

```
mcp_turbovault_set_active_vault(name="<vault-name>")
```

All paths in this skill are relative to the vault root with a `wiki/` prefix.

**Example paths:**
- Hub: `wiki/index.md`
- Schema: `wiki/llm-wiki/SCHEMA.md`
- Entity page: `wiki/llm-wiki/entities/transformer-architecture.md`

## Architecture

```
vault-root/                   # active TurboVault vault
├── wiki/                     # wiki root — hub index.md lives here
│   ├── index.md              # Hub: one section per domain wiki with abstract
│   ├── llm-wiki/             # Domain Wiki 1
│   │   ├── SCHEMA.md         # Conventions, structure rules, domain config
│   │   ├── index.md          # Sectioned content catalog with one-line summaries
│   │   ├── log.md            # Chronological action log (append-only, rotated yearly)
│   │   ├── raw/              # Layer 1: Immutable source material
│   │   │   ├── articles/     # Web articles, clippings
│   │   │   ├── papers/       # PDFs, arxiv papers
│   │   │   ├── transcripts/  # Meeting notes, interviews
│   │   │   └── assets/       # Images, diagrams referenced by sources
│   │   ├── entities/         # Entity pages (people, orgs, products, models)
│   │   ├── concepts/         # Concept/topic pages
│   │   ├── comparisons/      # Side-by-side analyses
│   │   └── queries/          # Filed query results worth keeping
│   ├── ai-research/          # Domain Wiki 2
│   │   ├── SCHEMA.md
│   │   ├── index.md
│   │   ├── log.md
│   │   ├── raw/
│   │   ├── entities/
│   │   ├── concepts/
│   │   ├── comparisons/
│   │   └── queries/
│   └── ...                   # Additional domain wikis
├── area/
├── projects/
└── ...
```

Every level uses `index.md`. The root `wiki/index.md` is the hub — it lists all
domain wikis with abstracts. Each domain wiki has its own full structure:
`SCHEMA.md`, `index.md`, `log.md`, `raw/`, `entities/`, `concepts/`, `comparisons/`, and `queries/`.

**Layer 1 — Raw Sources:** Immutable by default. The agent reads but does not modify these during normal ingest/synthesis. If the user explicitly asks to correct or align a raw source itself, treat it as an intentional raw-source revision: load the target wiki context, make the narrow change, and append a `log.md` entry documenting the exception.
**Layer 2 — The Wiki:** Agent-owned markdown files. Created, updated, and
cross-referenced by the agent.
**Layer 3 — The Schema:** Each domain wiki's `SCHEMA.md` defines structure,
conventions, and tag taxonomy for that domain.

Domain wikis are flat subdirectories directly under `wiki/` — no `wiki/wikis/`
nesting, no extra hierarchy.

## The Hub

The root `wiki/index.md` is the hub. It contains one section per domain wiki.

**Format:** Each section has a `## name` heading matching the wiki's directory
name, followed by an abstract paragraph describing the wiki's purpose and scope.

Example:

```markdown
# Wiki Hub

## llm-wiki
LLM-Wiki methodology — persistent, compounding knowledge base for developing
the multi-domain LLM Wiki skill itself.

## ai-research
AI/ML research, models, papers, benchmarks.
```

**Rules:**

- No page counts, no last-update dates, no tag lists — those live in each
  wiki's own `index.md` and `log.md`
- No separate routing file — the abstracts are the routing information
- The hub lives in the vault, not in the skill config
- The skill reads it for routing and updates it when creating new domain wikis

**Hub detection:** The root `wiki/index.md` is always a hub. If it doesn't
exist, the wiki root is uninitialized — use Scenario A (First-Time Setup).

## Routing

How the agent decides which wiki to use:

| Trigger | Behavior |
|---------|----------|
| User names the wiki explicitly | Use that wiki |
| Source or query clearly matches one wiki's abstract | Use that wiki |
| Ambiguous | Ask the user. Do not guess. |

The agent reads the abstracts in `wiki/index.md` and matches against them.
No tag system, no keyword mapping — just the abstract text.

## Resuming an Existing Wiki (CRITICAL — do this every session)

When the user has an existing wiki, **always orient yourself before doing
anything**:

① **Ensure the active vault is set:**
   `mcp_turbovault_set_active_vault(name="<vault-name>")`

② **Read root `wiki/index.md`** — it is always a hub.
   `mcp_turbovault_read_note(path="wiki/index.md")`

③ **Route to target wiki** — explicit naming → abstract match → ask (see Routing above).

④ **Read that wiki's `SCHEMA.md`, `index.md`, and recent `log.md`:**
   ```
   mcp_turbovault_read_note(path="wiki/<target-wiki>/SCHEMA.md")
   mcp_turbovault_read_note(path="wiki/<target-wiki>/index.md")
   mcp_turbovault_read_note(path="wiki/<target-wiki>/log.md")
   ```

Only after orientation should you ingest, query, or lint. This prevents:

- Creating duplicate pages for entities that already exist
- Missing cross-references to existing content
- Contradicting the schema's conventions
- Repeating work already logged
- Targeting the wrong domain wiki

For large wikis (100+ pages), also run a quick
`mcp_turbovault_search(query="<topic>")` and filter results to `wiki/<target-wiki>/`
before creating anything new.

## Linking

**ALL wikilinks use the full vault path:** `[[wiki/<wiki-name>/<type>/<page-name>]]`

The `wiki/` prefix is mandatory — wikilinks resolve relative to the vault root,
not relative to the `wiki/` directory. Without it, TurboVault's broken-link
detection (and Obsidian's link resolution) will flag every link as broken.

This is the universal convention — within-wiki and cross-wiki links use the
same format. Bare `[[pagename]]` links resolve relative to the current file's
directory and will **always be flagged as broken**.

Examples:

- `[[wiki/ai-research/concepts/llm-infrastructure]]` — same-wiki link (from any page in ai-research)
- `[[wiki/llm-wiki/concepts/three-layer-architecture]]` — cross-wiki link
- `[[wiki/ai/entities/andrei-karpathy|Andrej Karpathy]]` — with display text

**Pitfall — missing wiki/ prefix:** Never write `[[ai-research/concepts/foo]]`
or `[[test/concepts/bar]]`. These look for `ai-research/concepts/foo.md` at the
vault root, which doesn't exist. Always write `[[wiki/ai-research/concepts/foo]]`.
This is the #1 cause of initial lint failures on new wikis.
This is the #1 cause of initial lint failures on new wikis.

**Rules:**

- These resolve natively in Obsidian (backlinks, graph view, manual browsing)
- No adapter pages — just link directly using the path
- No duplication — link, don't copy content between wikis

## Initializing a New Wiki

**Observe-then-Formalize (Sparse Wiki Mapping):** Do not prematurely create a new domain wiki for every new area or project. Let structure emerge from friction. If no matching domain wiki exists for a new raw source, store it as a generic `resource` in a fallback location (e.g., `sources/clippings/`). Only when a critical mass of **5+ related sources** accumulates should you initialize a new domain wiki.

**Load and follow `references/initialize-wiki.md` precisely, in order, every step.** All steps are mandatory — especially hub registration. A wiki not registered in the hub is invisible to the routing system.

- Scenario A: First-Time Setup (no hub exists)
- Scenario B: New Domain Wiki (hub already exists)

## Core Operations

### 1. Ingest

When the user provides a source (URL, file, paste), integrate it into the wiki:

① **Read the hub:** `mcp_turbovault_read_note(path="wiki/index.md")` to determine
the target wiki. Route using the rules above (explicit → abstract match → ask).

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
   `wiki/<target-wiki>/` prefix. This is the difference between a growing wiki
   and a pile of duplicates.

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

### 2. Query

When the user asks a question about the wiki's domain:

① **Read root `wiki/index.md`** — identify which wiki(s) are relevant using the
   hub abstracts.
② **Read the relevant wiki `index.md` files** to identify relevant pages.
③ **For wikis with 100+ pages**, also run `mcp_turbovault_search(query="<topic>")`
   across the wiki prefix — the index alone may miss relevant content.
④ **Read the relevant pages** using `mcp_turbovault_read_note(path="wiki/...")`.
⑤ **Synthesize an answer** from the compiled knowledge. Cite pages with their
   vault path: "Based on `[[wiki/ai-research/concepts/transformer-architecture]]`
   and `[[wiki/llm-wiki/concepts/three-layer-architecture]]`..."
⑥ **File valuable answers back** — if the answer is a substantial comparison,
   deep dive, or novel synthesis, create a page in the explicit target wiki or
   the clearest primary wiki's `queries/` or `comparisons/`. If no primary wiki
   is clear and filing would write new content, ask the user before filing.
   Don't file trivial lookups — only answers that would be painful to re-derive.
⑦ **Update that wiki's `log.md`** with the query and whether it was filed.

### 3. Lint

When the user asks to lint, health-check, or audit the wiki, **load the
reference file first** — it contains the complete step-by-step workflow.

See [`references/lint-workflow.md`](references/lint-workflow.md) for details on
all 17 checks: broken links, outbound link count, frontmatter validation, index
completeness, orphans, tag taxonomy, stale content, page size, log rotation,
reporting, iterative fixing, cross-wiki links, and hub drift.

## Working with the Wiki

### Searching

```bash
# Find pages by content across the whole wiki
mcp_turbovault_search(query="transformer")
# Filter results to wiki/<target>/ prefix for domain-scoped search

# Advanced search with path exclusions
mcp_turbovault_advanced_search(query="alignment", exclude_paths=["area/", "projects/", "inbox/"])

# Find pages by frontmatter field
mcp_turbovault_search_by_frontmatter(key="type", value="entity")
# Then filter results for wiki/<target>/ prefix

# Semantic search (conceptual matches beyond keywords)
mcp_turbovault_semantic_search(query="reinforcement learning safety")

# Find pages by frontmatter value
mcp_turbovault_search_by_frontmatter(key="tags", value="model")

# Recent activity in a specific domain wiki
mcp_turbovault_read_note(path="wiki/ai-research/log.md")
```

**Scope warning:** TurboVault search (`mcp_turbovault_search`) searches the
**entire vault**, not just the `wiki/` directory. Always scope results by
checking the `path` prefix or use `exclude_paths` in advanced search to
exclude non-wiki directories (area/, projects/, inbox/, resources/, own/,
archive/).

### Detecting Unprocessed Raw Sources

When the user says "process the new articles in raw/articles/" or you want to find sources that haven't been ingested yet:

1. List all files in `wiki/<target>/raw/articles/` (via `terminal` or by reading the directory)
2. For each file, search entity and concept pages for a `sources:` reference to that filename:
   `mcp_turbovault_search(query="raw/articles/<filename>")`
3. If no entity/concept page references it → the source is **unprocessed**
4. Report the list to the user and ask which to ingest

This is the file-based QUEUE pattern: `raw/articles/` IS the queue. A cron job can automate step 2-3 daily.

### Bulk Ingest

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

### Ingest from Vault Inbox

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

### Using `edit_note` for Targetted Edits

`mcp_turbovault_edit_note` uses SEARCH/REPLACE blocks (similar to the `patch`
tool but within TurboVault). The `edits` parameter contains one or more
SEARCH/REPLACE pairs:

```
<<<<<<< SEARCH
Old text to find
=======
New replacement text
>>>>>>> REPLACE
```

**Best practices:**

- Use the exact git-diff style delimiters required by TurboVault: `<<<<<<< SEARCH`, `=======`, and `>>>>>>> REPLACE`. Plain `SEARCH`/`REPLACE` or a closing `>>>>>>>` without `REPLACE` is invalid.
- Include enough context around the SEARCH text to ensure uniqueness
- **DON'T use `edit_note` for `log.md`** — the SEARCH block that matches the
  previous entry's header **replaces** that header, leaving its detail lines
  orphaned. Always use read-full/write-full instead.
- **DON'T use `edit_note` for `index.md`** — matching a section header like
  `## Entities` deletes the header. Always use read-full/write-full instead.
- **DON'T use `edit_note` for `SCHEMA.md`** — schema files contain pipe characters `|`,
  brackets `[]`, and backticks that trigger parser errors (`Parse error: Incomplete
  SEARCH/REPLACE block`). Always use read-full/write-full instead.
- For other files, `edit_note` is fine with enough context for uniqueness.
  But when it fails, fall back to read-full/write-full.
- **If `edit_note` fails with a parse error** (e.g., `Parse error: Incomplete SEARCH/REPLACE block`), the SEARCH/REPLACE content likely contains special characters (pipes `|`, brackets `[]`, path-separators `/`, or multi-line YAML frontmatter) that confuse the parser. Fall back to `mcp_turbovault_read_note` + `mcp_turbovault_write_note` (full read, modify in context, full overwrite) — this bypasses the parser entirely.
- **After writing, verify files exist on disk** if the user reports them missing in Obsidian. Check the vault path with `terminal -> ls -la /path/to/vault/wiki/<target>/` or read back via `mcp_turbovault_read_note`. TurboVault writes directly to the filesystem; if Obsidian doesn't show the files, the user may need to reload the Obsidian file tree (Ctrl+R / Cmd+R). This is not a sync issue — the files are on disk.

### Archiving

When content is fully superseded or the domain scope changes:

1. Create `_archive/` directory in the domain wiki if it doesn't exist
   (via `mcp_turbovault_write_note` with a placeholder)
2. Move the page to `_archive/` with its original path:
   `mcp_turbovault_move_note(from="wiki/<target>/entities/old-page.md", to="wiki/<target>/_archive/entities/old-page.md")`
3. Remove the page from the domain wiki's `index.md`
4. Update any pages that linked to it — replace wikilink with plain text +
   "(archived)"
5. Log the archive action in the domain wiki's `log.md`

### Removing a Domain Wiki (deleting an entire wiki)

When the user says "delete wiki X" or "remove wiki Y":

1. **List all files in the wiki directory** via terminal or search:
   `mcp_turbovault_search(query="wiki/X/")` to find all pages
2. **Delete all files** — use the terminal tool:
   `rm -rf /path/to/vault/wiki/X/`
   (This is faster than individual TurboVault deletes for an entire directory.)
3. **Remove the entry** from the root `wiki/index.md` (the hub):
   Read the hub, delete the `## wiki-name` section, write back.
4. **Log the deletion** — write a short note to the wiki's `log.md` before
   deleting it, OR if already deleted, note it in the hub changes.
5. **No INDEX.md updates needed** — the root INDEX.md links to `wiki/index.md`,
   which now reflects the change.

**Pitfall — check for cross-references first:** Before deleting, search for
`[[wiki/<wiki-name>/` across the vault to find pages in other wikis that link
to content in the wiki being deleted. Report these to the user and offer to
update or remove the links.

**Pitfall — don't use TurboVault delete for bulk removal:** `delete_note`
requires confirmation per file and is slow for 10+ files. Terminal `rm -rf`
is the right tool for removing an entire wiki directory.

## Do's and Don'ts

- **Never use standard filesystem tools (`read_file`, `write_file`) for vault/wiki files.** These tools are sandboxed to the Hermes Agent workspace and will fail with 'File not found' on absolute paths outside the workspace. Always use the proper `mcp_turbovault_*` tools.
- **Do not modify files in `raw/` during normal ingest/synthesis** — sources are immutable by default. Corrections usually go in wiki pages. Exception: if the user explicitly asks to correct/adapt the raw source itself, make the narrow requested change and append a `log.md` entry that documents the raw-source revision.
- **Always set the active vault first** — before any wiki operation, ensure
  `mcp_turbovault_set_active_vault` has been called for the correct vault.
- **Always orient first** — read root `wiki/index.md` (hub) then the target wiki's
  SCHEMA + index + recent log before any operation in a new session. Skipping
  this causes duplicates and missed cross-references.
- **Always read index.md before editing it** — when adding entries via
  `edit_note` or full rewrite, read the file first to see what already exists.
  Use full read + write for index.md if unsure.
- **For log.md, prefer read-full/write-full over edit_note.** Read the full
  log, prepend the new entry in your response, use `write_note` with overwrite.
  This completely avoids the boundary-matching risks that plague targetted edits
  on list/chronological files.
- **If `edit_note` fails with a parse error** (e.g., `Parse error: Incomplete SEARCH/REPLACE block`), the SEARCH/REPLACE content likely contains special characters (pipes `|`, brackets `[]`, path-separators `/`, or multi-line YAML frontmatter) that confuse the parser. Fall back to `mcp_turbovault_read_note` + `mcp_turbovault_write_note` (full read, modify in context, full overwrite) — this is always safer and bypasses the parser entirely.
- **After writing, verify files exist on disk** if the user reports them missing in Obsidian. Check the vault path with `terminal -> ls -la /path/to/vault/wiki/<target>/` or read back via `mcp_turbovault_read_note`. TurboVault writes directly to the filesystem; if Obsidian doesn't show the files, the user may need to reload the Obsidian file tree (Ctrl+R / Cmd+R). This is not a sync issue — the files are on disk.
- **When deleting a wiki, check cross-references first.** Search for `[[wiki/<wiki-name>/` across the vault before removing the directory. Offer to update or remove links found in other wikis.
- **Always read the hub first** — before any operation, read root `wiki/index.md` (the hub).
  Never skip orientation.
- **Always update index.md and log.md** — skipping this makes the wiki degrade.
  These are the navigational backbone. Update them in the correct domain wiki.
- **Don't create a "summary page" instead of wiki pages** — when ingesting sources,
  the output is N individual wiki pages (one per entity/concept), NOT a single
  summary document. A source about "Wohnwagen-Kauf" should produce:
  `feuchtigkeitsschaden.md` + `gasanlage.md` + `wohnwagen-marken.md` + etc.
  If you find yourself writing one long file that summarizes everything, STOP —
  you are making a summary, not a wiki. The schema demands one topic = one page.
- **Don't create pages for passing mentions** — follow the Page Thresholds in
  the domain wiki's SCHEMA.md. A name appearing once in a footnote doesn't
  warrant an entity page.
- **Don't create pages without cross-references** — isolated pages are invisible.
  Every page must link to at least 2 other pages.
- **Don't create adapter pages** — when referencing content in another domain
  wiki, use direct path-based wikilinks like
  `[[wiki/other-wiki/concepts/topic]]`. No adapter pages, no duplication.
- **Don't guess the target wiki** — if routing is ambiguous, ask the user.
  Putting content in the wrong wiki is worse than asking.
- **Frontmatter is required** — it enables search, filtering, and staleness
  detection.
- **Tags must come from the taxonomy** — freeform tags decay into noise. Add new
  tags to the domain wiki's SCHEMA.md first, then use them.
- **Keep pages scannable** — a wiki page should be readable in 30 seconds. Split
  pages over 200 lines. Move detailed analysis to dedicated deep-dive pages.
- **Ask before mass-updating** — if an ingest would touch 10+ existing pages,
  confirm the scope with the user first.
- **Rotate the log** — when a domain wiki's `log.md` exceeds 500 entries, move it
  to `log-YYYY.md` and start fresh. Check log size during lint.
- **Handle contradictions explicitly** — don't silently overwrite. Note both
  claims with dates, mark in frontmatter, flag for user review.
- **Keep hub abstracts current** — when a domain wiki's scope changes, update
  the abstract in root `wiki/index.md`. Stale abstracts cause routing failures.
- **Annotate financial figures as brutto or netto** — when recording income,
  asset values, tax calculations, or any monetary amounts on wiki pages,
  always explicitly label them as `brutto` (gross/pre-tax) or `netto`
  (net/post-tax). Never record a bare number without this annotation.
  Mixing brutto and netto caused a correction cascade: the user corrected
  one figure, which invalidated all derived calculations (effective tax
  rates, net income comparisons, B2B model projections) across multiple
  pages. Each downstream page had to be found, recalculated, and patched.
  The annotation is a single-word cost that prevents an N-page repair.
- **Verify personal names and relationships** — when adding personal-profile
  data to entity pages (family members, contacts, associates), explicitly
  verify each person's name and their relationship. Do not infer from context
  or assume two different people mentioned close together are the same person.
  A friend's name was used as the spouse's name, requiring corrections across
  entity pages, concept pages, index entries, and log files. When in doubt,
  ask: "Just to confirm — Joanna is your wife, and Ewa is the friend with
  the land. Did I get that right?"
- **Lint fixes cascade — always re-check.** The outbound-link check is the
  most common failure. Fixing one page often reveals the next. Run lint
  iteratively until clean.
- **Raw sources may need frontmatter.** In Olaf's camp wiki, raw sources have
  title/created/type frontmatter. In other wikis, they may not. Check the
  domain SCHEMA and user preferences. If in doubt, add it — it enables linting.
- **For bulk operations, use batch_execute.** When creating or updating multiple
  wiki pages in one ingest pass, wrap all writes in
  `mcp_turbovault_batch_execute` for atomic consistency. This prevents partial
  updates where only half the pages were written.
- **Never use truncated content as a raw source.** If `web_extract` returns a summary
  instead of a full article (paywall, blocking, timeout), label the source `type: extract`
  `status: incomplete`, warn the user, and wait for the full text. Entity/concept pages
  derived from truncated sources are unreliable.
- **Prefer full read + write over edit_note for log.md, index.md, and SCHEMA.md.** These
  files have complex structure (lists, headers, chronological ordering, pipe characters) where
  SEARCH/REPLACE can accidentally match the wrong occurrence or trigger parser errors.
  Read the full file, modify in your context, write the complete
  result back. This is always safer.

