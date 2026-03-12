---
name: vault-ops
description: "Use this skill when working with a markdown notes vault such as Obsidian. It defines a default workflow for selecting a vault, reading vault-local instructions, navigating notes, writing regular notes, and maintaining Maps of Content (MoCs). Triggers: vault, obsidian, notes vault, moc, map of content, markdown notes."
metadata:
  version: "0.1.1"
  source: https://github.com/olafgeibig/skills
---

# Vault Ops

Use this skill as the default workflow for working with a vault of markdown notes.

## Workflow

1. Read `~/.vault-ops.json` from the user's home directory to discover known vaults. If it does not exist, follow `./reference/managing-vaults.md`.
2. Select the vault:
   - If the user names a vault, use it.
   - If exactly one vault exists, use it.
   - If multiple vaults exist and the user did not name one, ask which vault to use.
3. Read the selected vault's root `AGENTS.md` if it exists.
4. Read any vault-local files referenced by that `AGENTS.md` before doing work.
5. Follow vault-local instructions first. Use this skill's reference files only as defaults.
6. Route the task:
   - navigation, search, discovery -> `./reference/navigating-vaults.md`
   - regular note creation or editing -> `./reference/note-writing.md`
   - MoC creation or editing -> `./reference/moc-writing.md`

## Instruction Precedence

- The selected vault's root `AGENTS.md` overrides this skill.
- Files referenced by that vault `AGENTS.md` also override this skill.
- `./reference/*.md` contains default conventions to use only when the vault does not define a more specific rule.

## Vault Basics

A notes vault is a normal folder on disk that contains markdown files. Notes typically use frontmatter plus wiki links such as `[[page-name]]` to create a navigable graph.

Typical vault contents:
- `*.md` notes
- `.obsidian/` configuration for Obsidian-based vaults
- folders for structure
- `AGENTS.md` for vault-specific operating rules

Do not modify `.obsidian/` unless the user explicitly asks.

## References

- Vault discovery and setup: `./reference/managing-vaults.md`
- Vault navigation defaults: `./reference/navigating-vaults.md`
- Regular note defaults: `./reference/note-writing.md`
- MoC defaults: `./reference/moc-writing.md`
- Default note template: `./reference/note-template.md`
- Default MoC template: `./reference/moc-template.md`
