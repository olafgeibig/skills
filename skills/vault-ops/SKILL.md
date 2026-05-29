---
name: vault-ops
description: "Use this skill when working with a markdown notes vault such as Obsidian. It defines a default workflow for selecting a vault, reading vault-local instructions, navigating notes, writing regular notes, and maintaining Maps of Content (MoCs). Triggers: vault, obsidian, notes vault, moc, map of content, markdown notes."
metadata:
  version: "0.6.0"
  source: https://github.com/olafgeibig/skills
  requires: turbovault (https://github.com/Epistates/turbovault)
  hermes:
    tags:
      - obsidian
      - vault
    related_skills:
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

When a session produces a lesson learned, do **not** paste the concrete session story into this skill. First abstract it:

- **NEVER edit SKILL.md instructions and original references.** These files are the stable core. You may only add new references and edit references prefixed with `opt-`.
- Put optimizations and discovered workflows into  `references/opt-<name>.md`.
- Put pitfalls into `references/opt-pitfalls.md` as new entries. 
- Write generic instructions so the improvements can be merged into upstream, remove or generalize proper names, one-off tool names, personal task names, local paths, session dates, and single-project examples unless they are clearly labeled as generic examples.
- **No duplication between SKILL.md and references/.** If a workflow exists in a reference, the SKILL.md says nothing more than *"Follow the reference."* This prevents drift when the reference is updated.

Good abstraction examples:
- Bad: "For <specific-tool>, always create a wiki entity first."
- Good: "For tool evaluation, create an agent-managed wiki entity before user synthesis in area notes."
- Bad: "Search <specific-personal-task> with this exact query."
- Good: "For known task topics, use the user's concrete topic as the keyword query; use pattern search for checkbox status."

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

## Optimizations

- Optional pitfalls staged for review: `./references/opt-pitfalls.md` — agent-discovered caveats and corrections that must not be promoted without explicit user approval.
- Promote a sub-MoC to a top-level project: `./references/opt-promote-subproject.md` — assessment criteria, note moves, tag/topics updates, wikilink fixup, INDEX restructuring, parent MoC cleanup, optional task note creation.
- Import legacy notes: `./references/opt-import-legacy.md` — discover all files via SQL, read, clarify ambiguous content, add frontmatter, convert legacy task formats, link to MoC, verify zero unprocessed files.
- Rename a note type across a vault: `./references/opt-rename-note-type.md` — bulk refactor frontmatter types, templates, governance docs, MoC prose, and verify old type is gone while preserving immutable raw sources.
- Review concept drift against current Vault Ops rules: `./references/opt-concept-drift-review.md` — compare design/concept notes with live skill references, catch scope, precedence, hybrid-linking, bookmarks, SQL, and raw-source exception drift.

## Troubleshooting

### TurboVault `edit_note` — SEARCH/REPLACE parse failures
See the `turbovault-use` skill for complete `edit_note` syntax, format requirements, and troubleshooting. The `references/task-management.md` in this skill has working examples in the context of task operations.

## Templates

- Default note template: `./assets/note-template.md`
- Default MoC template: `./assets/moc-template.md`
