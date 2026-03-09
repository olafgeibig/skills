---
name: vault-ops
description: "Use this skill when working with vaults of makdown notes like Obsidian vaults: searching, creating, moving, or deleting notes. Triggers: vault, obsidian, note, markdown note"
metadata:
  version: "0.1.0"
  source: https://github.com/olafgeibig/skills
---

## Vault Ops

Vault Ops is an opinionated approach for managing a vault of notes. It assumes certain concepts like MOCs and using topic links.

## Contents of a vault

A notes vault is a normal folder on disk that contains markdown files with an extended syntax. A typical note is basically a markdown file that has a yaml section at the top with document properties. Notes can be linked by using a wiki-link notation [[page-name]]. Effectively this is building a knowledge-graph consisting of notes.

Typical vault structure:
- Notes: `*.md` (plain text Markdown; edit with any editor)
- Config: `.obsidian/` (workspace + plugin settings; usually don’t touch from scripts)
- Folders: to structure the vault
- AGENTS.md: instructions how to work with the vault - MUST READ (if exists in vault root)

Read the config file `<your-workspce-dir>/.vault-ops.json` to know the vaults and their properties. If the file does not exist, follow the instructions in `<skill-dir>/references/managing-vaults.md`.

## Working with a vault

If there is more than one vault, the user must name the vault in the request. If the user didn't name it, you assume the default vault. First read the AGENTS.md. It explains the setup of the vault and the specifics how to use it. It often also contains a README.md that explains the context of the vault, contains definitions and a glossary.

When navigating the vault, follow the instructions in `<skill-dir>/references/navigating-vaults.md`.

## Working with notes
When writing, editing or updating notes, follow the instructions in `<skill-dir>/references/note-writing.md`.
