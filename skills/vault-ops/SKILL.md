---
name: vault-ops
description: "Use this skill when working with a markdown notes vault such as Obsidian. It defines a default workflow for selecting a vault, reading vault-local instructions, navigating notes, writing regular notes, and maintaining Maps of Content (MoCs). Triggers: vault, obsidian, notes vault, moc, map of content, markdown notes."
metadata:
  version: "0.3.0"
  source: https://github.com/olafgeibig/skills
  requires: turbovault (https://github.com/Epistates/turbovault)
---

# Vault Ops

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

### Vault (AGENTS.md)
Always read
- Sync method and handling
- Note types and templates
- Directory structure details
- Language preferences
- Tagging 

### Vault Context (VAULT.md)
Read if deeper understanding of the vault is needed.
Contains context to understand the vault content, e.g. a glossary of vault specific terms. More detailed context to understand the vault structure.

## Before starting to work on a vault

### Check config
Run `jq 'to_entries | .[0:3] | from_entries' ~/.vault-ops.json`
If file does not exist or version is not `2` then follow instructions in `./references/vault-configuration.md`

**If rg is not true**
Follow instructions in `./references/vault-configuration.md`

**If turbovault is true use its tools**
- If no active vault `list_vaults` and choose vault. Ask user if unclear. Then `set_active_vault`.
- If the user asks to use a vault that is not known to turbovault, but is present in `~/.vault-ops.json` then just register it in turbovault.
- If the user gives a full path to a vault and the vault is not registered, register it (`add_vault`) and add it to `~/.vault-ops.json` before proceeding.
- refer to `./refrences/turbovault-*.md` 

**If turbovault is false**
- Fallback to rg: Read `~/.vault-ops.json`  
- If the user asks to use a vault you can not match to vaults in `~/.vault-ops.json` then ask the user.
- If the user gives a full path to a vault and the vault is not in `~/.vault-ops.json` the add it.
- refer to `./refrences/rg-*.md` 

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
- `./reference/*.md` contains default conventions to use only when the vault does not define a more specific rule.

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
- ./references/note-template.md for notes
- ./references/mpc-template.md for MoCs

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

### Required frontmatter properties
Mandatory, but can be extended in AGENTS.md
```
description: One sentence adding context beyond the title (~150 chars, no period)
type: Type of note according to the definition in AGENTS.md
updated: YYYY-MM-DD
tags: [array of tags]
topics: [array of links to MoCs]
```

## Workflows 

- Create a new area: `./references/wf-new-area.md`
- MoC creation or editing: `./references/moc-writing.md`

## References
- Regular note defaults: `./references/note-writing.md`
- MoC defaults: `./references/moc-writing.md`
- Default note template: `./references/note-template.md`
- Default MoC template: `./references/moc-template.md`
- Navigation, search, discovery -> `./references/navigating-vaults.md`
- Regular note creation or editing -> `./references/note-writing.md`

- TurboVault MCP integration: `./references/turbovault.md` — Rust MCP server with automatic link updates on move/rename, BM25 search, health checks
- TurboVault MCP usage notes: `./references/turbovault-integration.md`
- TurboVault MCP workflow: `./references/turbovault-workflow.md`
- External knowledge-base integration options (OpenViking, gbrain): `./references/knowledge-base-options.md`
- Vault navigation defaults: `./references/navigating-vaults.md`
