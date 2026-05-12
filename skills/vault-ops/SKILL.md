---
name: vault-ops
description: "Use this skill when working with a markdown notes vault such as Obsidian. It defines a default workflow for selecting a vault, reading vault-local instructions, navigating notes, writing regular notes, and maintaining Maps of Content (MoCs). Triggers: vault, obsidian, notes vault, moc, map of content, markdown notes."
metadata:
  version: "0.3.0"
  source: https://github.com/olafgeibig/skills
  requires: turbovault (https://github.com/Epistates/turbovault)
---

# Vault Ops

Use this skill to manage a navigable notes-graph built from MoCs (Maps of Content) and frontmatter metadata that stays queryable and traversable.

Use this skill as the default workflow for working with a vault of markdown notes. Vault-ops has an opinionated approach how to manage a vault following Obsidian vault best-practices regarding the top level directory structure and note types. Vault specifics can be defined in the vault's AGENTS.md. The skill works best with turbovault to interact with the vault safely. 

## Responsibility Split
### Skill
Always read
- vault-ops configuration
- How to interact with the vault (turbovault, rg)
- Navigation of the vault with MoCs
- Mandatory frontmatter
- Main directory structure
- Decide if references needs to be read

### Vault instructions
Always read AGENTS.md
- Sync method and handling
- Note types and templates
- Directory structure details
- Language preferences
- Tagging 

### Vault Context (optional)
Read VAULT.md if deeper understanding of the vault is needed.
Contains context to understand the vault content, e.g. a glossary of vault specific terms. More detailed context to understand the vault structure.

## Before starting to work on a vault

### Check config
Run `jq 'to_entries | .[0:3] | from_entries' ~/.vault-ops.json`
If file does not exist or property `version` is not `2` then follow instructions in `./references/vault-configuration.md` 

**If property `rg` is not true**
Follow instructions in `./references/vault-configuration.md`

**If turbovault is true use its tools**
- If no active vault `list_vaults` and choose vault. Ask user if unclear. Then `set_active_vault`.
- If the user asks to use a vault that is not known to turbovault, but is present in `~/.vault-ops.json` then just register it in turbovault.
- If the user gives a full path to a vault and the vault is not registered, register it (`add_vault`) and add it to `~/.vault-ops.json` before proceeding.
- refer to `./references/vault-configuration.md`

**If turbovault is false**
- Fallback to rg: Read `~/.vault-ops.json`  
- If the user asks to use a vault you can not match to vaults in `~/.vault-ops.json` then ask the user.
- If the user gives a full path to a vault and the vault is not in `~/.vault-ops.json` the add it.
- refer to `./references/vault-configuration.md`

If the user asks to check or validate the vault-ops configuration, then perform the instructions in `./references/vault-configuration.md` 

### Vault selection
- If the user names a vault, use it.
- If exactly one vault exists, use it.
- If a vault was used before in the same conversation, continue to use it.
- If an active vault is set, use it
- If you are not sure which vault to use, ask the user.

## Working with a vault
Read the vault's root `AGENTS.md`. If it doesn't exist, tell the user that it is important. If turbovault reports "subdirectory context discovered" (AGENTS.md/VAULT.md), treat it as authoritative and read it via filesystem tools if needed.

Read additionally `VAULT.md`
- if you need to make decisions that need deeeper understanding of the vault context
- if you don't understand terms used in the vault or the user request related to the vault

## Instruction Precedence

- The selected vault's root `AGENTS.md` overrides this skill.
- Files referenced by that vault `AGENTS.md` also override this skill.
- `./references/*.md` contains default conventions to use only when the vault does not define a more specific rule.

### Directory Structure
Default structure that can be overridden and  extended in AGENTS.md
- `archive/`: Archived projects and notes
- `area/`: A Zettelkasten of atomic notes for areas of interest
- `inbox/`: incoming notes, quick captures that need to be digested 
- `projects/`: note clearly related to a project
- `sources/`: Raw sources from external, web, documents
- `system/`: Internal files, templates, state, helper scripts
- `wiki/`: the root of a wiki maintained by a wiki skill defined in AGENTS.md

### Note Types
Use default templates unless defined different in AGENTS.md
- ./assets/note-template.md for notes
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
topics: [array of links to MoCs]
```
- The topics property always contains links to MoCs, not tags
- The `description` property functions as a retrieval filter, not a content summary. Optimize it for search discoverability and progressive disclosure.

## References

### Basic vault operations

- Writing new notes: `./references/note-writing.md`
- Writing new MoCs: `./references/moc-writing.md`
- Understanding the vault graph: `./references/vault-graph.md`
- Navigating the vault with rg: `./references/rg-navigation.md`
- Navigating the vault with turbovault: `./references/tv-navigation.md`

## Workflows 

- Create a new area: `./references/wf-new-area.md`

## Templates

- Default note template: `./assets/note-template.md`
- Default MoC template: `./assets/moc-template.md`
