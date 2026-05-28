# Initializing a New Wiki

Two scenarios — first wiki ever vs. adding a new domain to an existing hub.

Before choosing a scenario, check whether `wiki/index.md` already exists in the
active vault:

- If not, treat it as a greenfield root and proceed with **Scenario A**.
- If yes, treat it as an initialized federation hub and use **Scenario B** for
  additional domain wikis.

## Scenario A: First-Time Setup (no hub exists)

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

## Scenario B: New Domain Wiki (hub already exists)

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
3. **CRITICAL — Update the hub:**
   - Add a section to root `wiki/index.md` with the new wiki's abstract
   - The abstract is used by the agent for routing (see Routing section)
   - Use read-full/write-full on `wiki/index.md`; do **not** use `mcp_turbovault_edit_note` for index files because SEARCH/REPLACE can accidentally delete or corrupt section headers
   - Format: `## <wiki-name>` followed by an abstract paragraph
4. **If the vault has INDEX.md files** (vault-ops convention):
   - No change needed to `INDEX.md` (root) — it already links to `wiki/index.md`
   - No change needed to `area/INDEX.md` or `projects/INDEX.md` — the wiki hub is its own INDEX

Write this file completely — do not reference an external template. Adapt to
the user's domain:

```markdown
# Wiki Schema

## Domain
[What this wiki covers — e.g., "AI/ML research", "personal health", "startup intelligence"]

## Conventions
- File names: lowercase, hyphens, no spaces (e.g., `transformer-architecture.md`)
- Every wiki page starts with YAML frontmatter (see below)
- All wikilinks use the full vault path: `[[wiki/<wiki-name>/<type>/<page-name>]]` (minimum 2 outbound links per page). Never use bare `[[pagename]]` or omit the `wiki/` prefix.
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
  sources: [wiki/<wiki-name>/raw/articles/source-name.md]
  # Optional quality signals:
  confidence: high | medium | low      # how well-supported the claims are
  contested: true                      # set when the page has unresolved contradictions
  contradictions: [other-page-slug]    # pages this one conflicts with
  ---
  ```

`confidence` and `contested` are optional but recommended for opinion-heavy or
fast-moving topics. Lint surfaces `contested: true` and `confidence: low` pages
for review so weak claims don't silently harden into accepted wiki fact.

## Raw Source Frontmatter

Raw sources ALSO get a small frontmatter block:

```yaml
---
source_url: https://example.com/article   # original URL, if applicable
ingested: YYYY-MM-DD
sha256:                                    # optional — set automatically on ingest for drift detection
---

[raw content starts here]
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

## index.md Template

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

## log.md Template

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
