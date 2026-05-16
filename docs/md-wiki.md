# Multi-Domain LLM Wiki (md-wiki)

> A persistent, compounding federation of markdown knowledge bases — compiled
> once by an agent, curated by a human, and linked across domain boundaries.

## The Concept

The Multi-Domain LLM Wiki (md-wiki) is an alternative to traditional Retrieval
Augmented Generation (RAG). Where RAG re-discovers knowledge from scratch on
every query — scattering fragments of context across vector stores, losing
cross-references between queries, and never resolving contradictions — the wiki
**compiles knowledge once** and keeps it current.

This is the difference between **sight-reading** (RAG) and **studying** (wiki).
A pianist sight-reading a piece plays it note-by-note, never seeing the full
structure. A pianist who has studied the score knows the key changes, the
recurring themes, the structural repetitions — and can play with understanding.
The wiki is that studied score: cross-references are already there,
contradictions have already been flagged, and synthesis reflects everything
that has been ingested, not just whatever chunks happen to fit in a context
window.

## Why Not Just RAG?

RAG makes sense for ephemeral question-answering over large corpora. But it has
fundamental limitations:

| Aspect | RAG | Wiki |
|--------|-----|------|
| Memory | Stateless per query | Stateful, compounding |
| Cross-references | Rediscovered every time | Pre-linked, permanent |
| Contradictions | Silently mixed into context | Explicitly flagged |
| Knowledge decay | Implicit (re-embedding drifts) | Explicit (staleness checks) |
| Human oversight | None (black-box retrieval) | Full (human curates sources) |
| Query cost | Every query hits N sources | Answers from compiled pages |

For a focused knowledge domain — a specific research area, a personal project,
a startup's competitive intelligence — the wiki compounds value with every
source ingested. Each new source doesn't just answer the current question; it
enriches every future answer.

## Architecture

### Federation of Domains

A single wiki root contains multiple **domain wikis** — focused knowledge bases
each with their own scope, schema, and conventions. They live side-by-side under
one `wiki/` directory and link across domain boundaries using path-based wikilinks.

```
wiki/                          # Root — hub index.md lives here
├── index.md                   # Hub: lists all domains with abstracts
├── llm-wiki/                  # Domain wiki 1
│   ├── SCHEMA.md              # Domain conventions and structure
│   ├── index.md               # Content catalog
│   ├── log.md                 # Action log (append-only)
│   ├── raw/                   # Immutable source material
│   │   ├── articles/
│   │   ├── papers/
│   │   └── transcripts/
│   ├── entities/              # People, orgs, products, models
│   ├── concepts/              # Topics and ideas
│   ├── comparisons/           # Side-by-side analyses
│   └── queries/               # Filed query results
├── ai-research/               # Domain wiki 2
│   └── ...                    # (same structure)
└── ...                        # More domain wikis
```

### Three Layers

**Layer 1 — Raw Sources** (`raw/`): Immutable original material. The agent
reads but never modifies these. They provide provenance for every claim in the
wiki.

**Layer 2 — The Wiki** (`entities/`, `concepts/`, `comparisons/`, `queries/`):
Agent-owned markdown pages. Created, updated, linked, and cross-referenced by
the agent as new sources are ingested. One topic = one page.

**Layer 3 — The Schema** (`SCHEMA.md`): Each domain defines its own conventions:
frontmatter requirements, tag taxonomy, page thresholds, and update policies.
The schema is the constitution of that domain wiki.

### The Hub

The root `wiki/index.md` is the **hub** — a lightweight directory of all domain
wikis. Each domain has one `## name` heading and an abstract paragraph
describing its purpose and scope. The agent reads the hub to route sources and
queries to the correct domain. No tags, no counts, no dates — just abstracts.

## Division of Labor

| Role | Does |
|------|------|
| **Human** | Curates sources, directs analysis, validates claims, resolves contradictions |
| **Agent** | Summarizes sources, creates/updates wiki pages, cross-references, maintains index and log, lints for quality |

The human decides *what* to study. The agent does the *studying* — filing,
linking, and maintaining consistency across all domains.

## Linking Convention

All wikilinks use the full vault path from the vault root:

```
[[wiki/<domain>/<type>/<page-name>]]
```

This works natively in Obsidian (backlinks, graph view, manual browsing) and
enables cross-wiki links without adapter pages. A page in `llm-wiki` can link
directly to a concept in `ai-research` with the same path convention.

## The Compounding Effect

When a new source is ingested, it doesn't just create one page. It triggers
updates across 5–15 wiki pages:

- **New pages** for entities and concepts that appear in the source (but meet
  the page thresholds)
- **Updates** to existing pages with new information, corrected facts, or
  additional cross-references
- **Cross-links** between the new content and everything already in the wiki
- **Index and log updates** to keep navigation current

Each ingest leaves the wiki richer than before. Over time, the wiki becomes a
dense, interlinked knowledge graph — not a flat collection of documents.

## Storage

All wiki content lives in an **Obsidian vault** managed by **TurboVault**
(v1.5+). All operations use TurboVault's MCP tools: reading, writing, editing,
searching, batch operations, broken-link detection, and quality analysis.

The wiki is fully browsable in Obsidian — backlinks, graph view, and manual
navigation all work because the files are plain markdown with standard
Obsidian wikilinks.

## Key Principles

- **One topic, one page.** Never a single summary document. A source about
  "Wohnwagen-Kauf" produces `feuchtigkeitsschaden.md`, `gasanlage.md`,
  `wohnwagen-marken.md`, etc.
- **Raw sources are immutable.** Never modify `raw/`. Corrections and
  syntheses go in wiki pages.
- **Every page has at least 2 outgoing wikilinks.** Isolated pages are
  invisible pages.
- **Frontmatter on every page.** Enables search, filtering, and staleness
  detection.
- **Tags come from the taxonomy.** Freeform tags decay into noise.
- **Contradictions are explicit, not silently overwritten.** Mark both
  positions with dates and flag for review.
- **The log is append-only.** Every action is recorded chronologically.
- **The index is always current.** Every page is listed under its type.

## Origin

Based on [Andrej Karpathy's LLM Wiki
pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f),
extended for multiple coordinated domain wikis and agent-driven operation.
