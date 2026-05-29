---
name: vault-ops
description: "Use this skill when working with a markdown notes vault such as Obsidian. It defines a default workflow for selecting a vault, reading vault-local instructions, navigating notes, writing regular notes, and maintaining Maps of Content (MoCs). Triggers: vault, obsidian, notes vault, moc, map of content, markdown notes."
metadata:
  version: "0.7.1"
  source: https://github.com/olafgeibig/skills
  requires: turbovault (https://github.com/Epistates/turbovault)
  hermes:
    tags:
      - obsidian
      - vault
    related_skills:
      - vault-improvements
      - vault-wiki
      - turbovault-use
---

# Vault Ops

Use this skill to manage a navigable notes-graph built from MoCs (Maps of Content) and frontmatter metadata that stays queryable and traversable.

Use this skill as the default workflow for working with markdown note vaults. Vault Ops provides an opinionated approach to managing vaults using Obsidian-oriented best practices for top-level directory structure and note types. Vault specifics can be defined in the vault's AGENTS.md. The skill works best with TurboVault to interact with the vault safely.

## Basic mandatory rules

- Always read AGENTS.md.
- Read VAULT.md when deeper understanding of the vault is needed. It contains context for understanding vault content, such as a glossary of vault-specific terms or additional structure notes.
- Load the reference file that matches the user intent before acting.

## Before starting to work on a vault

### Check prerequisites

The `turbovault-use` skill handles TurboVault availability checks, vault selection, and all tool-level mechanics. Load it — it is listed in `related_skills` and should be available. Follow its prerequisites and vault selection sections before proceeding with vault operations.

## Working with a vault
Read the vault's root `AGENTS.md`. If it doesn't exist, tell the user that it is important. If TurboVault reports "subdirectory context discovered" (AGENTS.md/VAULT.md), treat it as authoritative and read it via filesystem tools if needed.

Read additionally `VAULT.md`
- if you need to make decisions that need deeper understanding of the vault context
- if you don't understand terms used in the vault or the user request related to the vault

## Instruction Precedence

- The selected vault's root `AGENTS.md` overrides this skill.
- Files referenced by that vault `AGENTS.md` also override this skill.
- `./references/*.md` contains default conventions to use only when the vault does not define a more specific rule.

### Directory Structure

Default structure that can be overridden and extended in AGENTS.md

```
vault-root/
├── INDEX.md                # Vault-root INDEX: type:moc, links area/, projects/, wiki/ sub-INDEX files
├── area/
│   └── INDEX.md            # Area INDEX: type:moc, lists all area MoCs (+Name.md) with descriptions
├── projects/
│   └── INDEX.md            # Project INDEX: type:moc, lists all project MoCs
├── inbox/
├── sources/
├── system/
├── archive/
└── wiki/
    └── index.md            # Wiki hub: type:moc, lists all domain wikis with abstracts
```

**INDEX Convention:** Every INDEX file has `type: moc` frontmatter and `topics: ["[[INDEX]]"]` (except the root INDEX). The agent updates the relevant INDEX whenever the structure changes.

Every INDEX entry is a `##` heading with the MoC link directly in the heading, followed by an abstract paragraph and the default language. The abstract guides the agent when navigating the vault and classifying new notes:

```markdown
## [[+Agents]]
Agent frameworks, architectures, orchestration — patterns, lessons learned
from building production multi-agent systems. Covers context engineering,
agent collaboration patterns, generator-verifier loops.
Language: EN.
```

**Hierarchy:** Root `INDEX.md` links to `area/INDEX.md`, `projects/INDEX.md`, and `wiki/index.md` — not to individual MoCs. This scales better and avoids duplicates. `wiki/index.md` follows the same convention and has `type: moc` frontmatter.

- `archive/`: Archived projects and notes
- `area/`: A Zettelkasten of atomic notes for areas of interest
- `inbox/`: incoming notes, quick captures that need to be digested 
- `projects/`: note clearly related to a project
- `sources/`: Raw sources from external, web, documents
- `system/`: Internal files, templates, state, helper scripts
- `wiki/`: the root of a wiki maintained by the vault-wiki skill

### Note Types
Use default templates unless AGENTS.md defines different templates
- ./assets/note-template.md base template for all note types
- ./assets/moc-template.md for MoCs

### Tags
Default tags that can be overridden and extended in AGENTS.md
- `project/<dir>`: each note in a project directory
- `area/<dir>`: each note in an area directory
- `source`: raw source files
- `archived`: added to archived notes

### Required Tags
Mandatory, but can be extended in AGENTS.md
- Notes and MoCs in `projects/<dir>/` must include the matching `project/*` tag for that project
- Notes and MoCs in `area/<dir>/` must include the matching `area/*` tag for that area

### Frontmatter properties
Mandatory, but can be extended in AGENTS.md
```
description: One sentence adding context beyond the title that provides context for navigation (~150 chars, no period)
type: Type of note according to the definition in AGENTS.md
updated: YYYY-MM-DD
tags: [array of tags]
topics: ["[[+related-moc]]"]
```
- The `topics` property always contains links to MoCs (not tags and not notes - only MoCs) that link to this note. It can be more than one MoC. It serves as a **token-efficient parent/related link** — the agent reads it from frontmatter (~100 tokens, no extra call). **However**, `topics` is a YAML string, NOT a real wikilink — `get_backlinks("+related-moc.md")` does NOT find notes via `topics`.
- **Hybrid navigation rule:** Every note must have BOTH `topics` in frontmatter AND a body `Topics:` section after a horizontal rule with the same MoC links as real `[[wikilinks]]`:
  ```
  ---
  topics: ["[[+agents]]", "[[+vault-ops]]"]
  ---

  # Note Title

  ...

  ---

  Topics:
  - [[+agents]]
  - [[+vault-ops]]
  ```
  `topics` enables token-efficient parent lookup (Note→MoC) from frontmatter. Body `Topics:` links enable `get_backlinks` discovery (MoC→Notes) and Obsidian graph view.
- The `description` property functions as a retrieval filter, not a content summary. Optimize it for search discoverability and progressive disclosure.

## Self-Improvement Gate

This skill is the **stable core.** Do not edit it.

All optimizations, pitfalls, and discovered workflows belong in
**`vault-improvements`** — loaded via the `/vault` bundle alongside this skill.

When a lesson learned emerges:
1. Do NOT edit this file or its original references — they are the stable core
2. Instead, write the finding into the `vault-improvements` skill as a new
   reference entry or section
3. Abstract properly: remove proper names, local paths, session dates,
   one-off tool names before writing
4. If a lesson is universal and user-approved, it may later be promoted
   into this skill — but the agent never promotes unilaterally

## References
Always check if you need to read references matching your intent. Use the descriptions of the references below to make your decision.

### Basic vault operations

- Writing new notes: `./references/note-writing.md`
- Writing new MoCs: `./references/moc-writing.md`
- Writing bookmarks: `./references/bookmarks-writing.md`
- Understanding the vault graph: `./references/vault-graph.md`
- Navigating the vault: `./references/vault-navigation.md`
- Task management: `./references/task-management.md`

## Workflows 
Prefixed with `wf-`

- Create a new area: `./references/wf-new-area.md`
- Process inbox notes: `./references/wf-inbox-processing.md` — classifies, self-links, and routes incoming notes and action items.
- Run a vault health check: `./references/wf-vault-health.md` — starts with session pulse, escalates through cleanup and graph analysis. 

## Troubleshooting

### TurboVault `edit_note` — SEARCH/REPLACE parse failures
See the `turbovault-use` skill for complete `edit_note` syntax, format requirements, and troubleshooting. The `references/task-management.md` in this skill has working examples in the context of task operations.

## Templates

- Default note template: `./assets/note-template.md`
- Default MoC template: `./assets/moc-template.md`
