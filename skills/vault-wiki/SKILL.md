---
name: vault-wiki
description: "Use when maintaining a multi-domain Obsidian wiki."
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
  version: "0.8.0"
---

# Multi-Domain LLM Wiki

Build and maintain a persistent federation of domain knowledge bases as interlinked Markdown files inside an Obsidian vault. Each domain wiki has its own schema, index, log, sources, and derived pages.

The human curates sources and directs analysis. The agent summarizes, cross-references, files, and maintains consistency.

## When to Use

- Create or extend a domain wiki.
- Ingest a source into an existing wiki.
- Answer a question from compiled wiki knowledge.
- Audit, lint, archive, or refresh wiki content.
- Route work among several domain wikis.

For general vault structure and MoCs, load `vault-ops`. For all TurboVault mechanics, load `turbovault-use`.

## Required Orientation

Before every operation on an existing wiki:

1. Verify and select the active vault through `turbovault-use`.
2. Read `wiki/index.md`.
3. Route to the target domain by explicit user choice or hub abstract; ask if ambiguous.
4. Read the domain `SCHEMA.md`, `<name>-wiki.md`, and recent `log.md`.
5. For large wikis, search within the target `wiki/<domain>/` path before creating content.

Do not create or update pages before completing this orientation.

Load `references/wiki-architecture-and-navigation.md` for the directory model, hub rules, routing, session orientation, and mandatory full-path wikilinks.

## Core Invariants

- All wiki content lives below `wiki/` in the active vault.
- Domain wikis are flat children of `wiki/`; do not add a `wiki/wikis/` layer.
- Raw sources are immutable during normal ingest. Modify one only on explicit request and log the exception.
- Wiki pages are agent-maintained synthesis; each domain's `SCHEMA.md` defines its taxonomy and page rules.
- Every created page must meet the domain schema's page threshold and contain at least two meaningful cross-references.
- Use full vault-path wikilinks: `[[wiki/<domain>/<type>/<page>]]`.
- Update the domain index and `log.md` after every material operation.
- Do not guess a target domain.

## Operation Routing

| Task | Reference |
|---|---|
| Initialize the hub or a domain wiki | `references/initialize-wiki.md` |
| Ingest a URL, file, or inbox source | `references/ingest-workflow.md` |
| Detect unprocessed raw articles | `references/detect-unprocessed-sources.md` |
| Lint or audit a wiki | `references/lint-workflow.md` |
| Check source freshness | `references/source-freshness-check.md` |
| Remove a source and derived pages | `references/source-cascade-removal.md` |
| Archive a page or domain wiki | `references/archiving.md` |
| Source an X/Twitter article | `references/x-article-sourcing.md` |

Load only references required for the current operation.

## Ingest Rules

- Search the target wiki for duplicates before creating pages.
- Preserve the source and distinguish source claims from interpretation.
- Never use truncated content as a complete source. Mark it incomplete and obtain the full content before deriving knowledge pages.
- Do not create pages for passing mentions.
- Prefer atomic topic pages over one source-summary page.
- Update `<name>-wiki.md` and `log.md`.

## Query Rules

1. Route through `wiki/index.md` and the relevant domain index.
2. Read the pages that support the answer.
3. Use scoped search when indexes do not provide enough coverage.
4. Cite wiki pages with full vault-path wikilinks.
5. File only substantial synthesis that would be costly to reproduce.
6. Log filed queries and material maintenance actions.

## Editing Constraints

Use `turbovault-use` for editing syntax. In this wiki model:

- do not use fragile targeted edits for `log.md`, domain indexes, or `SCHEMA.md`; use full read-modify-write;
- do not edit raw sources during normal ingest;
- read back changed files and rerun affected lint checks;
- ask before an ingest or refactor that updates ten or more existing pages.

## Content Integrity

- Record conflicting claims with dates and mark them for review.
- Use only tags defined by the domain `SCHEMA.md`; add taxonomy terms there first.
- Keep pages scannable and split independent subjects rather than enforcing a blind line threshold.
- Annotate financial figures as gross or net when that distinction matters.
- Verify personal names and relationships; never infer them from context.
- Keep hub abstracts current because they drive routing.

## Improvement Routing

This is an owned generic skill. Follow `skill-governance`:

- domain-wiki architecture and workflows belong here;
- generic vault and MoC rules belong in `vault-ops`;
- TurboVault mechanics belong in `turbovault-use`;
- project-specific procedure belongs in a `project-*` skill;
- wiki-local schema and taxonomy belong in `SCHEMA.md`;
- profile quirks belong in profile guidance or a profile-local adaptation.

## Verification

Before completion:

- active vault and target domain are confirmed;
- schema and indexes were read;
- created pages satisfy source, linking, and taxonomy rules;
- full-path links resolve;
- domain index and log are current;
- relevant lint checks pass after changes;
- external writes were read back.
