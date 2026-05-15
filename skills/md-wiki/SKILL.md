---
name: md-wiki
description: "Multi-domain LLM Wiki — build and maintain a federation of interlinked markdown knowledge bases via TurboVault. Each domain wiki has its own schema, index, and log, linked across boundaries via path-based wikilinks. Extends Karpathy's single-wiki pattern for multiple domains under one root."
license: MIT
metadata:
  hermes:
    tags:
      - wiki
      - knowledge-base
      - research
      - notes
      - markdown
      - rag-alternative
      - multi-domain
      - federation
    category: research
    related_skills:
      - llm-wiki
      - obsidian
      - arxiv
      - vault-ops
    # config removed — wiki lives at wiki/ in active TurboVault vault
  source: https://github.com/olafgeibig/skills
  version: "0.3.0"
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

- Asks to create, build, or start a wiki or knowledge base
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

**Tool mapping (quick reference):**

| Operation | Tool |
|-----------|------|
| Read a note | `mcp_turbovault_read_note(path="wiki/...")` |
| Write/overwrite a note | `mcp_turbovault_write_note(path="wiki/...", content="...")` |
| Targetted edits | `mcp_turbovault_edit_note(path="wiki/...", edits="SEARCH/REPLACE blocks")` |
| Move/rename a note | `mcp_turbovault_move_note(from="wiki/...", to="wiki/...")` |
| Search content | `mcp_turbovault_search(query="...")` |
| Advanced search | `mcp_turbovault_advanced_search(query="...", exclude_paths=[...])` |
| Atomic batch ops | `mcp_turbovault_batch_execute(operations=[...])` |
| Broken links | `mcp_turbovault_get_broken_links()` |
| Dead-end notes | `mcp_turbovault_get_dead_end_notes()` |
| Health analysis | `mcp_turbovault_full_health_analysis()` |
| Frontmatter schema | `mcp_turbovault_inspect_frontmatter()` |
| Forward links | `mcp_turbovault_get_forward_links(path="wiki/...")` |
| Backlinks | `mcp_turbovault_get_backlinks(path="wiki/...")` |

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

**Layer 1 — Raw Sources:** Immutable. The agent reads but never modifies these.
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

**ALL wikilinks use the full path format:** `[[<wiki-name>/<type>/<page-name>]]`

This is the universal convention — within-wiki and cross-wiki links use the
same format. Bare `[[pagename]]` links resolve relative to the current file's
directory and will **always be flagged as broken**.

Examples:

- `[[ai-research/concepts/llm-infrastructure]]` — same-wiki link (from any page in ai-research)
- `[[llm-wiki/concepts/three-layer-architecture]]` — cross-wiki link
- `[[ai/entities/andrei-karpathy|Andrej Karpathy]]` — with display text

**Pitfall — bare wikilinks:** Never use `[[embeddings]]` or `[[reinforcement-learning]]`
within a wiki page. Instead, write `[[ai/concepts/embeddings]]` — the full path
with wiki name prefix. This is the #1 cause of initial lint failures on new wikis.

**Rules:**

- These resolve natively in Obsidian (backlinks, graph view, manual browsing)
- No adapter pages — just link directly using the path
- No duplication — link, don't copy content between wikis

## Initializing a New Wiki

Two scenarios — first wiki ever vs. adding a new domain to an existing hub:

Before choosing a scenario, check whether `wiki/index.md` already exists in the
active vault:

- If not, treat it as a greenfield root and proceed with **Scenario A**.
- If yes, treat it as an initialized federation hub and use **Scenario B** for additional domain wikis.

### A. First-Time Setup (no hub exists)

When the user asks to create or start a wiki and nothing exists yet, the first
wiki is always created as a domain wiki under a new hub:

1. Ask the user what domain the first wiki covers — be specific
2. Choose a directory name for the first domain wiki (lowercase, hyphens, no spaces)
3. Scaffold the domain wiki by writing its files via `mcp_turbovault_write_note`:
   - `wiki/<domain-name>/SCHEMA.md`
   - `wiki/<domain-name>/index.md`
   - `wiki/<domain-name>/log.md`
   - `wiki/<domain-name>/raw/.gitkeep` (placeholder — directories are implicit in note paths)
   - `wiki/<domain-name>/entities/.gitkeep`
   - `wiki/<domain-name>/concepts/.gitkeep`
   - `wiki/<domain-name>/comparisons/.gitkeep`
   - `wiki/<domain-name>/queries/.gitkeep`
4. Write the root `wiki/index.md` as a hub with the first domain's section and abstract
5. Confirm the wiki is ready and suggest first sources to ingest

Root `wiki/index.md` for first-time setup:

```markdown
# Wiki Hub

## <domain-name>
<One-paragraph abstract describing the domain and scope.>
```

### B. New Domain Wiki (hub already exists)

When the user asks to add a new domain wiki to an existing federation:

1. Determine wiki name from the user (lowercase, hyphens, no spaces)
2. Write the scaffolding files via `mcp_turbovault_write_note`:
   - `wiki/<name>/SCHEMA.md` — customize to the domain
   - `wiki/<name>/index.md` — sectioned header
   - `wiki/<name>/log.md` — creation entry
   - `wiki/<name>/raw/.gitkeep`
   - `wiki/<name>/entities/.gitkeep`
   - `wiki/<name>/concepts/.gitkeep`
   - `wiki/<name>/comparisons/.gitkeep`
   - `wiki/<name>/queries/.gitkeep`
3. Add section to root `wiki/index.md` hub with the wiki's abstract
   (use `mcp_turbovault_edit_note` or read-full/write-full on `wiki/index.md`)

#### SCHEMA.md Template

Write this file completely — do not reference an external template. Adapt to
the user's domain:

```markdown
# Wiki Schema

## Domain
[What this wiki covers — e.g., "AI/ML research", "personal health", "startup intelligence"]

## Conventions
- File names: lowercase, hyphens, no spaces (e.g., `transformer-architecture.md`)
- Every wiki page starts with YAML frontmatter (see below)
- All wikilinks use the full path format: `[[wiki-name/<type>/<page-name>]]` (minimum 2 outbound links per page). Never use bare `[[pagename]]`.
- When updating a page, always bump the `updated` date
- Every new page must be added to `index.md` under the correct section
- Every action must be appended to `log.md`

## Frontmatter
  ```yaml
  ---
  title: Page Title
  created: YYYY-MM-DD
  updated: YYYY-MM-DD
  type: entity | concept | comparison | query | summary
  tags: [from taxonomy below]
  sources: [raw/articles/source-name.md]
  ---
  ```

## Tag Taxonomy
[Define 10-20 top-level tags for the domain. Add new tags here BEFORE using them.]

Example for AI/ML:
- Models: model, architecture, benchmark, training
- People/Orgs: person, company, lab, open-source
- Techniques: optimization, fine-tuning, inference, alignment, data
- Meta: comparison, timeline, controversy, prediction

Rule: every tag on a page must appear in this taxonomy. If a new tag is needed,
add it here first, then use it. This prevents tag sprawl.

## Page Thresholds
- **Create a page** when an entity/concept appears in 2+ sources OR is central to one source
- **Add to existing page** when a source mentions something already covered
- **DON'T create a page** for passing mentions, minor details, or things outside the domain
- **Split a page** when it exceeds ~200 lines — break into sub-topics with cross-links
- **Archive a page** when its content is fully superseded — move to `_archive/`, remove from index

## Entity Pages
One page per notable entity. Include:
- Overview / what it is
- Key facts and dates
- Relationships to other entities ([[wikilinks]])
- Source references

## Concept Pages
One page per concept or topic. Include:
- Definition / explanation
- Current state of knowledge
- Open questions or debates
- Related concepts ([[wikilinks]])

## Comparison Pages
Side-by-side analyses. Include:
- What is being compared and why
- Dimensions of comparison (table format preferred)
- Verdict or synthesis
- Sources

## Update Policy
When new information conflicts with existing content:
1. Check the dates — newer sources generally supersede older ones
2. If genuinely contradictory, note both positions with dates and sources
3. Mark the contradiction in frontmatter: `contradictions: [page-name]`
4. Flag for user review in the lint report
```

#### index.md Template

Write this file completely:

```markdown
# Wiki Index

> Content catalog. Every wiki page listed under its type with a one-line summary.
> Read this first to find relevant pages for any query.
> Last updated: YYYY-MM-DD | Total pages: 0

## Entities
<!-- Alphabetical within section -->

## Concepts

## Comparisons

## Queries
```

**Scaling rule:** When any section exceeds 50 entries, split it into sub-sections
by first letter or sub-domain. When the index exceeds 200 entries total, create
a `_meta/topic-map.md` that groups pages by theme for faster navigation.

#### log.md Template

Write this file completely:

```markdown
# Wiki Log

> Chronological record of all wiki actions. Append-only.
> Format: `## [YYYY-MM-DD] action | subject`
> Actions: ingest, update, query, lint, create, archive, delete
> When this file exceeds 500 entries, rotate: rename to log-YYYY.md, start fresh.

## [YYYY-MM-DD] create | Wiki initialized
- Domain: [domain]
- Structure created with SCHEMA.md, index.md, log.md
```

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
     path-based links like `[[other-wiki/concepts/topic-name]]`.
     Check that existing pages link back.
   - **Tags:** Only use tags from the taxonomy in the target wiki's `SCHEMA.md`

⑥ **Update navigation** in the target wiki:
   - Add new pages to the target wiki's `index.md` under the correct section, alphabetically
   - Update the "Total pages" count and "Last updated" date in the target wiki's index header
   - Append to the target wiki's `log.md`: `## [YYYY-MM-DD] ingest | Source Title`
   - List every file created or updated in the log entry

⑧ **Report what changed** — list every file created or updated to the user.

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
   vault path: "Based on `[[ai-research/concepts/transformer-architecture]]`
   and `[[llm-wiki/concepts/three-layer-architecture]]`..."
⑥ **File valuable answers back** — if the answer is a substantial comparison,
   deep dive, or novel synthesis, create a page in the explicit target wiki or
   the clearest primary wiki's `queries/` or `comparisons/`. If no primary wiki
   is clear and filing would write new content, ask the user before filing.
   Don't file trivial lookups — only answers that would be painful to re-derive.
⑦ **Update that wiki's `log.md`** with the query and whether it was filed.

### 3. Lint

When the user asks to lint, health-check, or audit the wiki, use TurboVault's
built-in analysis tools and manual scoped checks:

**① Quick health overview:**
```
mcp_turbovault_full_health_analysis()
```
Returns broken links, orphan analysis, link density, cluster analysis, and
recommendations. Filter results for `wiki/`-prefixed paths.

**② Broken wikilinks:**
```
mcp_turbovault_get_broken_links()
```
Returns all broken links in the vault. Filter to `wiki/`-prefixed source paths.
Expected: only SCHEMA.md template examples should be broken — those are fine.

**③ Outbound link count (wiki pages only):**
Every wiki page in entities/, concepts/, comparisons/, queries/ must have at
least 2 outbound wikilinks to OTHER wiki pages (not raw/ sources). Raw sources
are exempt.

Use `mcp_turbovault_get_dead_end_notes()` to find pages with 0 outbound links.
For pages with 1 outbound link, manually check forward links:
```
mcp_turbovault_get_forward_links(path="wiki/<target>/entities/<page>")
```
**This is the most common failure mode.** Add missing "Verwandte Konzepte"
or "Verwandte Seiten" sections to fix.

**④ Frontmatter validation:**
```
mcp_turbovault_inspect_frontmatter()
```
Check that every wiki page (entities/, concepts/, comparisons/, queries/) has
all required fields: title, created, type. Tags must be in the taxonomy.
Note: index.md, log.md, SCHEMA.md are meta-files — skip them.
Raw sources: check if they have frontmatter (Olaf's wiki expects it).

**⑤ Index completeness:**
Compare the filesystem (pages with `wiki/<target>/entities/`, `concepts/`, etc.
paths) against entries in the target wiki's `index.md`. Use
`mcp_turbovault_search(query="")` with path prefix to discover all pages.

**⑥ Orphan pages:**
Pages with no inbound links from other wiki pages. For each wiki page, check:
```
mcp_turbovault_get_backlinks(path="wiki/<target>/entities/<page>")
```
Pages in entities/, concepts/, comparisons/, queries/ with 0 backlinks from
other wiki pages = orphan. Raw/ pages are always orphans by design — skip them.
Meta files (index, log, SCHEMA) are always orphans — skip them.

**⑦ Tag taxonomy:**
List all tags on wiki pages, flag any not in the domain wiki's `SCHEMA.md`
taxonomy. Raw sources use their own tag conventions — skip.

**⑧ Stale content:**
```
mcp_turbovault_find_stale_notes(threshold_days=90)
```
Filter to `wiki/`-prefixed paths. Pages whose `updated` date is older than
90 days from the most recent source that mentions the same entities.

**⑨ Page size:**
Flag pages over 200 lines — candidates for splitting. Use
`mcp_turbovault_read_note` and check content length per note.

**⑩ Log rotation:**
If the domain wiki's `log.md` exceeds 500 entries, rotate it: read the log,
write to `log-YYYY.md` via write_note, start fresh log.

**⑪ Report findings** with specific file paths and suggested actions, grouped by
   severity (broken links > missing outbound links > orphans > stale > style).

**⑫ Fix issues iteratively:** After fixing, re-run the relevant checks.
   The typical pattern is: fix page A → discover page B now has outbound links
   → fix page B → discover page C is now orphan → fix page C.
   Do NOT fix all pages in one pass without re-checking.

**⑬ Append to the domain wiki's `log.md`:**
   `## [YYYY-MM-DD] lint | N issues found`

**Cross-wiki lint:**

**⑭ Broken cross-wiki links:**
`mcp_turbovault_get_broken_links()` catches all broken wikilinks across the
entire vault, including `[[other-wiki/...]]` links pointing to non-existent pages.

**⑮ Hub drift:**
Check that root `wiki/index.md` hub sections match what's on disk (directory
names under `wiki/`). Flag domain directories on disk not listed in the hub,
and hub sections with no matching domain directory.

## Working with the Wiki

### Searching

```
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

# SQL queries on frontmatter
mcp_turbovault_query_frontmatter_sql(sql="SELECT path FROM files WHERE path LIKE 'wiki/ai-research/%' AND tags LIKE '%model%'")

# Recent activity in a specific domain wiki
mcp_turbovault_read_note(path="wiki/ai-research/log.md")
```

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

### Using `edit_note` for Targetted Edits

`mcp_turbovault_edit_note` uses SEARCH/REPLACE blocks (similar to the `patch`
tool but within TurboVault). The `edits` parameter contains one or more
SEARCH/REPLACE pairs:

```
<<<<<<< SEARCH
Old text to find
=======
New replacement text
>>>>>>>
```

**Best practices:**
- Include enough context around the SEARCH text to ensure uniqueness
- When adding a new entry to log.md, read the file fully first, prepend the
  new entry in your response content, use `mcp_turbovault_write_note` with
  full overwrite. This is safer than edit_note for log.md.
- For index.md, also prefer read-full/write-full over edit_note to avoid
  duplicate headers from partial matches.

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

### Obsidian Integration

Since the wiki lives within an Obsidian vault managed by TurboVault, all
Obsidian features work natively:

- `[[wikilinks]]` render as clickable links
- Cross-wiki links like `[[ai-research/concepts/llm-infrastructure]]`
  resolve natively in Obsidian's graph view and backlinks
- Graph View visualizes the full multi-domain knowledge network — cross-wiki
  links appear as edges between domain clusters
- YAML frontmatter powers Dataview queries
- The `raw/assets/` folders in each domain wiki hold images referenced via
  `![[image.png]]`

For best results:

- Set Obsidian's attachment folder to `raw/assets/`
- Enable "Wikilinks" in Obsidian settings (usually on by default)
- Install Dataview plugin for queries like
  `TABLE tags FROM "wiki/ai-research/entities" WHERE contains(tags, "company")`

## Do's and Don'ts

- **Never modify files in `raw/`** — sources are immutable. Corrections go in wiki pages.
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
  `[[other-wiki/concepts/topic]]`. No adapter pages, no duplication.
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
- **Prefer full read + write over edit_note for log.md and index.md.** These
  files have complex structure (lists, headers, chronological ordering) where
  SEARCH/REPLACE can accidentally match the wrong occurrence or consume a
  header line. Read the full file, modify in your context, write the complete
  result back. This is always safer.

## Pitfalls

### edit_note on log.md can destroy the previous entry's header

When you use `edit_note` to prepend a new entry to `log.md`, the SEARCH block
that matches the top of the previous entry will **replace** that header text —
leaving the previous entry's detail lines orphaned with no header.

**Example of what goes wrong:**
```
edits: "<<<<<<< SEARCH\n## [2026-05-03] ingest | Previous Entry\n=======\n## [2026-05-05] ingest | New Entry\n- details...\n>>>>>>>"
```
After this edit, `## [2026-05-03] ingest | Previous Entry` is gone but its
detail lines remain, now incorrectly under the new entry.

**Safer approach for log.md:** Use read-full/write-full instead:
1. `mcp_turbovault_read_note(path="wiki/<target>/log.md")` — get full content
2. Prepend the new entry in your response context
3. `mcp_turbovault_write_note(path="wiki/<target>/log.md", content="...")` — write it all back

This avoids fragile SEARCH matching on multi-line blocks entirely.

### edit_note on index.md creates duplicate headers

When adding entries via `edit_note`, the SEARCH block must be specific enough
to match exactly one location. If you match `## Entities` as the SEARCH target,
the REPLACE will delete that header. Instead, match on a line **inside** the
section (like a specific existing entry) and include the surrounding markers in
your replacement.

Better: read the full index.md, modify it, write it back.

### Searching across vault finds non-wiki content

TurboVault search (`mcp_turbovault_search`) searches the entire vault, not just
the `wiki/` directory. When scoping results to the wiki, filter client-side by
checking the `path` prefix: only results where `path` starts with `wiki/` are
relevant. For `mcp_turbovault_advanced_search`, use `exclude_paths` to exclude
known non-wiki directories (area/, projects/, inbox/, resources/, own/, archive/).
