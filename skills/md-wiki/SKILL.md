---
name: md-wiki
description: "Multi-domain LLM Wiki — build and maintain a federation of interlinked markdown wiki knowledge bases. Each domain wiki has its own schema, index, and log, linked across boundaries via path-based wikilinks. Use when user wants to use a wiki (create, ingest into, query, lint)."
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
      - turbovault-use
  source: https://github.com/olafgeibig/skills
  version: "0.7.0"
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
vault managed by **TurboVault**. All operations use `mcp_turbovault_*` tools.
See the `turbovault-use` skill for tool-level mechanics (read/write/edit/search/batch).

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
│   │   ├── llm-wiki.md       # Sectioned content catalog with one-line summaries
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
│   └── ...                   # Additional domain wikis
├── area/
├── projects/
└── ...
```

Every level uses a different naming: the hub `wiki/index.md` catalogs all domain
wikis, while each domain wiki has its own `<name>-wiki.md` (e.g., `wiki/llm-wiki/llm-wiki.md`).
Each domain wiki's full structure:
`SCHEMA.md`, `<name>-wiki.md`, `log.md`, `raw/`, `entities/`, `concepts/`, `comparisons/`, and `queries/`.

**Layer 1 — Raw Sources:** Immutable by default. The agent reads but does not modify these during normal ingest/synthesis. If the user explicitly asks to correct or align a raw source itself, treat it as an intentional raw-source revision: make the narrow change and append a `log.md` entry documenting the exception.
**Layer 2 — The Wiki:** Agent-owned markdown files. Created, updated, and cross-referenced by the agent.
**Layer 3 — The Schema:** Each domain wiki's `SCHEMA.md` defines structure, conventions, and tag taxonomy for that domain.

Domain wikis are flat subdirectories directly under `wiki/` — no `wiki/wikis/` nesting.

## The Hub

The root `wiki/index.md` is the hub. It contains one section per domain wiki.

**Format:** Each section has a `## name` heading matching the wiki's directory name, followed by an abstract paragraph describing the wiki's purpose and scope.

```markdown
# Wiki Hub

## [[wiki/llm-wiki/llm-wiki-wiki|llm-wiki]]
LLM-Wiki methodology — persistent, compounding knowledge base for developing the multi-domain LLM Wiki skill itself.

## [[wiki/ai-research/ai-research-wiki|ai-research]]
AI/ML research, models, papers, benchmarks.
```

**Rules:**
- No page counts, no last-update dates, no tag lists — those live in each wiki's own `<name>-wiki.md` and `log.md`
- No separate routing file — the abstracts are the routing information
- The hub lives in the vault, not in the skill config
- The skill reads it for routing and updates it when creating new domain wikis

**Hub detection:** The root `wiki/index.md` is always a hub. If it doesn't exist, the wiki root is uninitialized.
**→ Trigger:** Load `./references/initialize-wiki.md` when no `wiki/index.md` exists, or when the user asks to create a new domain wiki.

## Routing

How the agent decides which wiki to use:

| Trigger | Behavior |
|---------|----------|
| User names the wiki explicitly | Use that wiki |
| Source or query clearly matches one wiki's abstract | Use that wiki |
| Ambiguous | Ask the user. Do not guess. |

The agent reads the abstracts in `wiki/index.md` and matches against them. No tag system, no keyword mapping — just the abstract text.

## Resuming an Existing Wiki (CRITICAL — do this every session)

When the user has an existing wiki, **always orient yourself before doing anything**:

① **Ensure the active vault is set:**
   `mcp_turbovault_set_active_vault(name="<vault-name>")`

② **Read root `wiki/index.md`** — it is always a hub.
   `mcp_turbovault_read_note(path="wiki/index.md")`

③ **Route to target wiki** — explicit naming → abstract match → ask (see Routing above).

④ **Read that wiki's `SCHEMA.md`, `<wiki>-wiki.md`, and recent `log.md`:**
   ```
   mcp_turbovault_read_note(path="wiki/<target-wiki>/SCHEMA.md")
   mcp_turbovault_read_note(path="wiki/<target-wiki>/<target-wiki>-wiki.md")
   mcp_turbovault_read_note(path="wiki/<target-wiki>/log.md")
   ```

Only after orientation should you ingest, query, or lint. This prevents:
- Creating duplicate pages for entities that already exist
- Missing cross-references to existing content
- Contradicting the schema's conventions
- Repeating work already logged
- Targeting the wrong domain wiki

For large wikis (100+ pages), also run `mcp_turbovault_search(query="<topic>")` and filter results to `wiki/<target-wiki>/` before creating anything new.

## Linking

**ALL wikilinks must use the full vault path:** `[[wiki/<wiki-name>/<type>/<page-name>]]`

This is a **mandatory rule**, not a convention — without the `wiki/` prefix, wikilinks resolve relative to the current file's directory and TurboVault's broken-link detection will flag every link as broken. Even links within the same domain wiki must use the full path.

Examples:
- `[[wiki/ai-research/concepts/llm-infrastructure]]` — same-wiki link
- `[[wiki/llm-wiki/concepts/three-layer-architecture]]` — cross-wiki link
- `[[wiki/ai/entities/andrei-karpathy|Andrej Karpathy]]` — with display text

Never write `[[ai-research/concepts/foo]]` or `[[concepts/bar]]`. These look for pages at the vault root, which doesn't exist. This is the **#1 cause of initial lint failures** on new wikis.

**Additional rules:**
- Links resolve natively in Obsidian (backlinks, graph view, manual browsing)
- No adapter pages — link directly using the full path
- No duplication — link, don't copy content between wikis

## Initializing a New Wiki

**Load and follow `references/initialize-wiki.md` precisely, in order, every step.** All steps are mandatory — especially hub registration. A wiki not registered in the hub is invisible to the routing system.

- Scenario A: First-Time Setup (no hub exists)
- Scenario B: New Domain Wiki (hub already exists)

## Core Operations

### 1. Ingest

**→ Trigger:** Load `./references/ingest-workflow.md` when the user provides a source (URL, paste, file) to integrate into a wiki, or when processing items from vault inbox.

**Key rules that apply at every ingest:**
- **Check for duplicates first** — search the target wiki before creating new pages
- **Every page needs 2+ cross-references** — isolated pages are invisible
- **Update `<name>-wiki.md` and `log.md`** — skipping this degrades the wiki
- **Handle truncated content:** If `web_extract` returns a summary instead of full text, label the source `status: incomplete` and ask the user for the full version. Never create entity/concept pages from truncated sources.

### 2. Query

When the user asks a question about the wiki's domain:

① **Read root `wiki/index.md`** — identify which wiki(s) are relevant using the hub abstracts.
② **Read the relevant wiki `<name>-wiki.md` files** to identify relevant pages.
③ **For wikis with 100+ pages**, also run `mcp_turbovault_search(query="<topic>")` across the wiki prefix — the index alone may miss relevant content.
④ **Read the relevant pages** using `mcp_turbovault_read_note(path="wiki/...")`.
⑤ **Synthesize an answer** from the compiled knowledge. Cite pages with their vault path: "Based on `[[wiki/ai-research/concepts/transformer-architecture]]` and `[[wiki/llm-wiki/concepts/three-layer-architecture]]`..."
⑥ **File valuable answers back** — if the answer is a substantial comparison, deep dive, or novel synthesis, create a page in the target wiki's `queries/` or `comparisons/`. Don't file trivial lookups — only answers that would be painful to re-derive.
⑦ **Update that wiki's `log.md`** with the query and whether it was filed.

### 3. Lint

**→ Trigger:** Load `./references/lint-workflow.md` when the user asks to lint, audit, or health-check the wiki. Covers 18 checks: broken links, outbound link count, frontmatter validation, index completeness, orphans, tag taxonomy, stale content, page size, log rotation, report, fix cascading, cross-wiki links, hub drift, and source drift (sha256).

**Lint cascades** — fixing one page often reveals the next. Re-run checks after each fix pass until clean.

## Working with the Wiki

### Searching

See the `turbovault-use` skill for available search tools and their purposes.

```bash
# Find pages in a specific domain wiki (always scope to wiki/ prefix)
mcp_turbovault_search(query="transformer")
# Then filter results manually for wiki/<target>/ prefix

# Advanced search with path exclusions to focus on wiki only
mcp_turbovault_advanced_search(query="alignment", exclude_paths=["area/", "projects/", "inbox/"])
```

**Scope warning:** TurboVault search searches the **entire vault**, not just `wiki/`. Always scope results by path prefix or use `exclude_paths`.

### Detecting Unprocessed Raw Sources

**→ Trigger:** Load `./references/detect-unprocessed-sources.md` when the user asks to process new articles in `raw/articles/`. The `raw/articles/` directory is the signal — any file there not yet referenced by a wiki page is pending processing.

### Using `edit_note` for Targeted Edits

See the `turbovault-use` skill for syntax and format requirements.

**md-wiki-specific DON'Ts:**
- **DON'T use `edit_note` for `log.md`** — SEARCH replaces the previous entry's header, leaving detail lines orphaned. Always use read-full/write-full.
- **DON'T use `edit_note` for `<name>-wiki.md`** — matching `## Entities` deletes the header. Always use read-full/write-full.
- **DON'T use `edit_note` for `SCHEMA.md`** — pipe characters `|`, brackets `[]`, and backticks trigger parser errors. Always use read-full/write-full.
- **DON'T use `edit_note` for `raw/` files** — raw sources are immutable by default. Use full read + write for corrections.

### Archiving

**→ Trigger:** Load `./references/archiving.md` when the user asks to archive a wiki page or delete an entire domain wiki.

### Source Freshness Check

**→ Trigger:** Load `./references/source-freshness-check.md` when the user asks to check if git-based sources (tools, repos) have been updated since ingest. Runs `git ls-remote` against stored `latest_commit` values and reports drift. User decides on re-ingest.

### Source Cascade Removal

**→ Trigger:** Load `./references/source-cascade-removal.md` when the user asks to remove a raw source and all pages derived from it. Depends on `sources:` frontmatter for attribution — pages without it need user review.

## Do's and Don'ts

- **Never modify `raw/` files during normal ingest** — sources are immutable. Corrections go in wiki pages. Exception: user explicitly asks for a raw-source revision.
- **Always orient first** — read hub → target SCHEMA + `<name>-wiki` + recent log before any operation in a new session.
- **Always update `<name>-wiki.md` and `log.md`** — these are the navigational backbone. Skipping them degrades the wiki.
- **Don't write summary pages** — one topic = one page. A source about "Wohnwagen-Kauf" should produce `feuchtigkeitsschaden.md` + `gasanlage.md` + `wohnwagen-marken.md`, not one summary document.
- **Don't create pages for passing mentions** — follow the Page Thresholds in the domain wiki's `SCHEMA.md`.
- **Don't create pages without cross-references** — every page must link to at least 2 other pages.
- **Don't create adapter pages** — link directly via `[[wiki/other-wiki/concepts/topic]]`. No duplication.
- **Don't guess the target wiki** — if routing is ambiguous, ask. Wrong wiki is worse than asking.
- **Frontmatter is required** — it enables search, filtering, and staleness detection.
- **Tags must come from the taxonomy** — freeform tags decay into noise. Add new tags to `SCHEMA.md` first.
- **Keep pages scannable** — split pages over 200 lines. Move detailed analysis to dedicated deep-dive pages.
- **Ask before mass-updating** — if an ingest touches 10+ existing pages, confirm with the user.
- **Rotate the log** — when `log.md` exceeds 500 entries, move it to `log-YYYY.md` and start fresh.
- **Handle contradictions explicitly** — note both claims with dates, mark in frontmatter, flag for review.
- **Keep hub abstracts current** — stale abstracts cause routing failures.
- **Annotate financial figures as brutto or netto** — never record a bare monetary amount without this annotation.
- **Verify personal names and relationships** — confirm names and relationships before writing. Never infer from context.
- **Lint cascades** — re-run checks after each fix pass until clean.
- **Raw sources can have frontmatter** — check the domain SCHEMA. When in doubt, add it.
- **Never use truncated content as a raw source** — label it `status: incomplete` and wait for the full text.
