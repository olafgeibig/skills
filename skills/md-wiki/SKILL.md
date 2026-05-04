---
name: md-wiki
description: "Multi-domain LLM Wiki — build and maintain a federation of interlinked markdown knowledge bases. Each domain wiki has its own schema, index, and log, linked across boundaries via path-based wikilinks. Extends Karpathy's single-wiki pattern for multiple domains under one root."
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
    config:
      - key: wiki.path
        description: "Path to the wiki root directory"
        default: "~/wiki"
        prompt: Wiki directory path
  source: https://github.com/olafgeibig/skills
  version: "0.2.1"
---

# Multi-Domain LLM Wiki

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

## When This Skill Activates

Use this skill when the user:

- Asks to create, build, or start a wiki or knowledge base
- Asks to ingest, add, or process a source into their wiki
- Asks a question and an existing wiki is present at the configured path
- Asks to lint, audit, or health-check their wiki
- References their wiki, knowledge base, or "notes" in a research context
- Mentions a specific domain wiki by name (e.g., "add this to my ai-research wiki")
- Asks to create a new domain wiki

## Wiki Location

Configured via `skills.config.wiki.path` in `~/.hermes/config.yaml` (prompted
during `hermes config migrate` or `hermes setup`):

```yaml
skills:
  config:
    wiki:
      path: ~/wiki
```

Falls back to `~/wiki` default. The resolved path is injected when this
skill loads — check the `[Skill config: ...]` block above for the active value.

`wiki.path` points to the wiki root directory. This root contains the hub
`index.md` and one subdirectory per domain wiki. No extra nesting — domain
wikis are flat subdirectories directly under the root.

The wiki is just a directory of markdown files — open it in Obsidian, VS Code,
or any editor. No database, no special tooling required.

## Architecture

```
wiki/                         # wiki.path points here
├── index.md                  # Hub: one section per domain wiki with abstract
├── llm-wiki/                 # Domain Wiki 1
│   ├── SCHEMA.md             # Conventions, structure rules, domain config
│   ├── index.md              # Sectioned content catalog with one-line summaries
│   ├── log.md                # Chronological action log (append-only, rotated yearly)
│   ├── raw/                  # Layer 1: Immutable source material
│   │   ├── articles/         # Web articles, clippings
│   │   ├── papers/           # PDFs, arxiv papers
│   │   ├── transcripts/      # Meeting notes, interviews
│   │   └── assets/           # Images, diagrams referenced by sources
│   ├── entities/             # Entity pages (people, orgs, products, models)
│   ├── concepts/             # Concept/topic pages
│   ├── comparisons/          # Side-by-side analyses
│   └── queries/              # Filed query results worth keeping
├── ai-research/              # Domain Wiki 2
│   ├── SCHEMA.md
│   ├── index.md
│   ├── log.md
│   ├── raw/
│   ├── entities/
│   ├── concepts/
│   ├── comparisons/
│   └── queries/
└── ...                       # Additional domain wikis
```

Every level uses `index.md`. The root `index.md` is the hub — it lists all
domain wikis with abstracts. Each domain wiki has its own full structure:
`SCHEMA.md`, `index.md`, `log.md`, `raw/`, `entities/`, `concepts/`, `comparisons/`, and `queries/`.

**Layer 1 — Raw Sources:** Immutable. The agent reads but never modifies these.
**Layer 2 — The Wiki:** Agent-owned markdown files. Created, updated, and
cross-referenced by the agent.
**Layer 3 — The Schema:** Each domain wiki's `SCHEMA.md` defines structure,
conventions, and tag taxonomy for that domain.

Domain wikis are flat subdirectories directly under the root — no `wikis/`
nesting, no extra hierarchy.

## The Hub

The root `index.md` is the hub. It contains one section per domain wiki.

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

**Hub detection:** In this M1 skill, the root `index.md` is always a hub. This version assumes a greenfield federated wiki root.

## Routing

How the agent decides which wiki to use:

| Trigger | Behavior |
|---------|----------|
| User names the wiki explicitly | Use that wiki |
| Source or query clearly matches one wiki's abstract | Use that wiki |
| Ambiguous | Ask the user. Do not guess. |

The agent reads the abstracts in root `index.md` and matches against them.
No tag system, no keyword mapping — just the abstract text.

## Resuming an Existing Wiki (CRITICAL — do this every session)

When the user has an existing wiki, **always orient yourself before doing
anything**:

① **Read root `index.md`** — it is always a hub.

② **Route to target wiki** — explicit naming → abstract match → ask (see Routing above).

③ **Read that wiki's `SCHEMA.md`, `index.md`, and recent `log.md`.**

```bash
WIKI="<resolved wiki.path>"
# Step 1: Read root index (always a hub)
read_file "$WIKI/index.md"

# Step 2: Route to target wiki and read its files:
read_file "$WIKI/<target-wiki>/SCHEMA.md"
read_file "$WIKI/<target-wiki>/index.md"
read_file "$WIKI/<target-wiki>/log.md" offset=<last 30 lines>
```

Only after orientation should you ingest, query, or lint. This prevents:

- Creating duplicate pages for entities that already exist
- Missing cross-references to existing content
- Contradicting the schema's conventions
- Repeating work already logged
- Targeting the wrong domain wiki

For large wikis (100+ pages), also run a quick `search_files` for the topic
at hand before creating anything new.

## Cross-Wiki Linking

Path-based wikilinks connect pages across domain wikis.

**Format:** `[[<wiki-name>/<type>/<page-name>]]`

Examples:

- `[[ai-research/concepts/llm-infrastructure]]`
- `[[llm-wiki/concepts/three-layer-architecture]]`
- `[[health-wiki/entities/who-recommendations]]`

**Rules:**

- These resolve natively in Obsidian (backlinks, graph view, manual browsing)
- No adapter pages — just link directly using the path
- No duplication — link, don't copy content between wikis

## Initializing a New Wiki

Two scenarios — first wiki ever vs. adding a new domain to an existing hub:

Before choosing a scenario, check the state of the resolved `wiki.path`:

- If `wiki.path` does not exist yet, treat it as a greenfield root: confirm or accept the resolved path, create the root directory, then proceed with Scenario A.
- If `wiki.path` exists but is empty or has no root `index.md`, treat it as an uninitialized federation root and proceed with Scenario A.
- If `wiki.path/index.md` exists, treat it as an initialized federation root and use Scenario B for additional domain wikis.

### A. First-Time Setup (no wiki root exists)

When the user asks to create or start a wiki and nothing exists yet, the first
wiki is always created as a domain wiki under a new hub:

1. Determine the wiki root path from the resolved `wiki.path` skill config (default `~/wiki`)
2. Create the root directory
3. Ask the user what domain the first wiki covers — be specific
4. Choose a directory name for the first domain wiki (lowercase, hyphens, no spaces)
5. Create the domain wiki subdirectory and scaffold its structure:
   ```
   <domain-name>/
   ├── SCHEMA.md
   ├── index.md
   ├── log.md
   ├── raw/
   │   ├── articles/
   │   ├── papers/
   │   ├── transcripts/
   │   └── assets/
   ├── entities/
   ├── concepts/
   ├── comparisons/
   └── queries/
   ```
6. Write the root `index.md` as a hub with the first domain's section and abstract
7. Confirm the wiki is ready and suggest first sources to ingest

Root `index.md` for first-time setup:

```markdown
# Wiki Hub

## <domain-name>
<One-paragraph abstract describing the domain and scope.>
```

### B. New Domain Wiki (hub already exists)

When the user asks to add a new domain wiki to an existing federation:

1. Determine wiki name from the user (lowercase, hyphens, no spaces)
2. Create the full directory structure under wiki root:
   ```
   <name>/
   ├── SCHEMA.md
   ├── index.md
   ├── log.md
   ├── raw/
   │   ├── articles/
   │   ├── papers/
   │   ├── transcripts/
   │   └── assets/
   ├── entities/
   ├── concepts/
   ├── comparisons/
   └── queries/
   ```
   Every subdirectory must exist, even if empty.
3. Write `SCHEMA.md` customized to the domain
4. Write `index.md` with sectioned header
5. Write `log.md` with creation entry
6. Add section to root `index.md` hub with the wiki's abstract

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
- Use `[[wikilinks]]` to link between pages (minimum 2 outbound links per page)
- Cross-wiki links: `[[wiki-name/<type>/<page-name>]]`
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

① **Read the hub:** Read root `index.md` to determine the target wiki. Route
using the rules above (explicit → abstract match → ask).

② **Capture the raw source** in the target wiki:
   - URL → use `web_extract` to get markdown, save to target wiki's `raw/articles/`
   - PDF → use `web_extract` (handles PDFs), save to target wiki's `raw/papers/`
   - Pasted text → save to appropriate `raw/` subdirectory in the target wiki
   - Name the file descriptively: `raw/articles/karpathy-llm-wiki-2026.md`

③ **Discuss takeaways** with the user — what's interesting, what matters for
   the domain. (Skip this in automated/cron contexts — proceed directly.)

④ **Check what already exists** — search the target wiki's `index.md` and use
   `search_files` within the target wiki to find existing pages for mentioned
   entities/concepts. If the topic might exist in another domain wiki, broaden
   the `search_files` to the entire wiki root. This is the difference between
   a growing wiki and a pile of duplicates.

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

⑥ **Propagate cross-links to related pages in other wikis:**
   When a new or updated page in wiki A relates to an existing concept in wiki B,
   add a wikilink from that existing wiki B page to the new wiki A page — don't
   wait to be asked. Example: adding `recursive-mode` (file-based solution) to RLM
   wiki triggered adding `context-rot` concept to RLM and linking it from the
   existing `repl-based-inference` page. This keeps the federation coherent and
   ensures cross-wiki relationships surface in Obsidian's graph view.

   Steps:
   a. After creating the new page, scan it for topics that likely exist elsewhere
      (e.g., shared problem: "context rot", shared technique: "reflection")
   b. `search_files` across the entire wiki root for those topics
   c. If found in another wiki, add a wikilink from that existing page to the
      new page, with a brief note in the link text

⑦ **Update navigation** in the target wiki:
   - Add new pages to the target wiki's `index.md` under the correct section, alphabetically
   - Update the "Total pages" count and "Last updated" date in the target wiki's index header
   - Append to the target wiki's `log.md`: `## [YYYY-MM-DD] ingest | Source Title`
   - List every file created or updated in the log entry

⑦ **Report what changed** — list every file created or updated to the user.

A single source can trigger updates across 5-15 wiki pages. This is normal
and desired — it's the compounding effect.

### 2. Query

When the user asks a question about the wiki's domain:

① **Read root `index.md`** — identify which wiki(s) are relevant using the
   hub abstracts.
② **Read the relevant wiki `index.md` files** to identify relevant pages.
③ **For wikis with 100+ pages**, also `search_files` across those wiki `.md`
   files for key terms — the index alone may miss relevant content.
④ **Read the relevant pages** using `read_file`.
⑤ **Synthesize an answer** from the compiled knowledge. Cite pages with their
   wiki path: "Based on `[[ai-research/concepts/transformer-architecture]]`
   and `[[llm-wiki/concepts/three-layer-architecture]]`..."
⑥ **File valuable answers back** — if the answer is a substantial comparison,
   deep dive, or novel synthesis, create a page in the explicit target wiki or
   the clearest primary wiki's `queries/` or `comparisons/`. If no primary wiki
   is clear and filing would write new content, ask the user before filing.
   Don't file trivial lookups — only answers that would be painful to re-derive.
⑦ **Update that wiki's `log.md`** with the query and whether it was filed.

### 3. Lint

When the user asks to lint, health-check, or audit the wiki:

**Scripted lint** (preferred — runs all checks in one pass):
```bash
python3 ./scripts/lint_wiki.py \
  --wiki /path/to/wiki/root/directory \
  [--domain rlm]
```
Output: broken links, low-outbound pages (with targets), orphans.
The script is a **scanner only** — the agent interprets the output and fixes each issue manually. A script cannot judge whether a link replacement is semantically correct; only the agent can pick the right substitute page. Usually lint only the domain wiki where changes were applied. Link without domainj if cross-domain updates had been made.

**Per-wiki lint** — same checks as the original skill, scoped to one domain wiki:

① **Broken wikilinks:** Find `[[links]]` that point to pages that don't exist.
   ```
   Scan all .md files in entities/, concepts/, comparisons/, queries/ (NOT raw/).
   Build set of all valid page targets (without .md extension).
   For each [[wikilink]] found, check if target resolves.
   Broken links: [[wikilinks]] pointing to non-existent pages.
   Expected: only SCHEMA.md template examples are broken — those are fine.
   ```

② **Outbound link count (wiki pages only):** Every wiki page in entities/,
   concepts/, comparisons/, queries/ must have at least 2 outbound wikilinks
   to OTHER wiki pages (not raw/ sources). Raw sources are exempt.
   ```
   For each wiki .md file (skip raw/):
     Extract all [[wikilinks]] → outbound count
     Filter out raw/ links
     If count < 2 → flag as issue
   ```
   **This is the most common failure mode.** Add missing "Verwandte Konzepte"
   or "Verwandte Seiten" sections to fix.

③ **Frontmatter validation:** Every wiki page (entities/, concepts/,
   comparisons/, queries/) must have all required fields:
   title, created, type. Tags must be in the taxonomy.
   ```
   Note: index.md, log.md, SCHEMA.md are meta-files — skip them.
   Raw sources: check if they have frontmatter (Olaf's wiki expects it).
   ```

④ **Index completeness:** Every wiki page should appear in the domain wiki's
   `index.md`. Compare the filesystem against index entries.

⑤ **Orphan pages:** Pages with no inbound links from other wiki pages.
   ```
   Build inbound-link map from all wikilinks.
   Pages in entities/, concepts/, comparisons/, queries/ with 0 inbound = orphan.
   Raw/ pages are always orphans by design — skip them.
   Meta files (index, log, SCHEMA) are always orphans — skip them.
   ```

⑥ **Tag taxonomy:** List all tags on wiki pages, flag any not in the domain
   wiki's `SCHEMA.md` taxonomy. Raw sources use their own tag conventions — skip.

⑦ **Stale content:** Pages whose `updated` date is >90 days older than the
   most recent source that mentions the same entities.

⑧ **Page size:** Flag pages over 200 lines — candidates for splitting.

⑨ **Log rotation:** If the domain wiki's `log.md` exceeds 500 entries, rotate it.

⑩ **Report findings** with specific file paths and suggested actions, grouped by
   severity (broken links > missing outbound links > orphans > stale > style).

⑪ **Fix issues iteratively:** After fixing, re-run the relevant checks.
   The typical pattern is: fix page A → discover page B now has outbound links
   → fix page B → discover page C is now orphan → fix page C.
   Do NOT fix all pages in one pass without re-checking.

⑫ **Append to the domain wiki's `log.md`:** `## [YYYY-MM-DD] lint | N issues found`

**Cross-wiki lint** — new checks that span the entire federation:

⑬ **Hub drift:** Check that root `index.md` hub sections match what's on disk.
    Flag domain directories on disk not listed in the hub, and hub sections
    with no matching domain directory.
    ```bash
    # Hub sections (from index.md):
    grep "^## " "$WIKI/index.md" | sed 's/^## //'
    # Disk wikis (with SCHEMA.md):
    for d in "$WIKI"/*/; do [ -f "$d/SCHEMA.md" ] && basename "$d"; done
    ```
    A wiki must have a SCHEMA.md to count as a real domain wiki.

## Working with the Wiki

### Searching

```bash
# Find pages by content within one domain wiki
search_files "transformer" path="$WIKI/ai-research" file_glob="*.md"

# Cross-wiki search — search across ALL domain wikis
search_files "transformer" path="$WIKI" file_glob="*.md"

# Find pages by filename
search_files "*.md" target="files" path="$WIKI/ai-research"

# Find pages by tag within one wiki
search_files "tags:.*alignment" path="$WIKI/ai-research" file_glob="*.md"

# Cross-wiki tag search
search_files "tags:.*alignment" path="$WIKI" file_glob="*.md"

# Recent activity in a specific domain wiki
read_file "$WIKI/ai-research/log.md" offset=<last 20 lines>
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
8. Update each wiki's `index.md` once at the end
9. Write a single log entry per wiki covering the batch

### Archiving

When content is fully superseded or the domain scope changes:

1. Create `_archive/` directory in the domain wiki if it doesn't exist
2. Move the page to `_archive/` with its original path
   (e.g., `_archive/entities/old-page.md`)
3. Remove from the domain wiki's `index.md`
4. Update any pages that linked to it — replace wikilink with plain text +
   "(archived)"
5. Log the archive action in the domain wiki's `log.md`

### Obsidian Integration

The wiki root directory works as an Obsidian vault out of the box:

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
  `TABLE tags FROM "ai-research/entities" WHERE contains(tags, "company")`

If using the Obsidian skill alongside this one, set `OBSIDIAN_VAULT_PATH` to the
same directory as the wiki root path.

## Wiki Area Setup

The wiki is structured as an **internal knowledge base** — wiki pages link only to other wiki pages via `[[wikilinks]]`. Cross-linking from the vault (area/ notes, MoCs) into the wiki is one-directional: vault notes reference the wiki, but wiki pages do **not** back-link to vault area notes or MoCs.

This means:
- **MoC linking**: Area MoCs may contain a `## Wiki` section with links like `[[wiki/hermes-agent/index|Wiki]]` to point users from the vault into the wiki for a domain
- **No wiki backlinks**: Wiki pages should never contain `[[area/...]]` links or back-link to vault MoCs or area notes
- **Cross-wiki only**: Wiki pages link to other wiki pages (`[[other-wiki/concepts/page]]`) or external URLs

- **Never modify files in `raw/`** — sources are immutable. Corrections go in wiki pages.
- **Always orient first** — read root `index.md` (hub) then the target wiki's
  SCHEMA + index + recent log before any operation in a new session. Skipping
  this causes duplicates and missed cross-references.
- **Always read index.md before patching it** — when adding entries via `patch`,
  read the file first to see what already exists. Targeted patches can easily
  create duplicate headers or duplicate entries. Use `write_file` for index.md
  if unsure, or read-before-patch to avoid duplication.
- **Always read the hub first** — before any operation, read root `index.md` (the hub).
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
- **Rotate the log** — when a domain wiki's `log.md` exceeds 500 entries, rename
  it `log-YYYY.md` and start fresh. The agent should check log size during lint.
- **Handle contradictions explicitly** — don't silently overwrite. Note both
  claims with dates, mark in frontmatter, flag for user review.
- **Keep hub abstracts current** — when a domain wiki's scope changes, update
  the abstract in root `index.md`. Stale abstracts cause routing failures.
- **Lint fixes cascade — always re-check.** The outbound-link check is the
  most common failure. Fixing one page often reveals the next. Run lint
  iteratively until clean.
- **Raw sources may need frontmatter.** In Olaf's camp wiki, raw sources have
  title/created/type frontmatter. In other wikis, they may not. Check the
  domain SCHEMA and user preferences. If in doubt, add it — it enables linting.
