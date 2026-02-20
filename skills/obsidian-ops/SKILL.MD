---
name: notesmd
description: Work with Obsidian vaults (plain Markdown notes) and automate via notesmd-cli.
homepage: https://help.obsidian.md
metadata: {"clawdbot":{"emoji":"💎","requires":{"bins":["notesmd-cli"]},"install":[{"id":"brew","kind":"brew","formula":"yakitrak/yakitrak/notesmd-cli","bins":["notesmd-cli"],"label":"Install notesmd-cli (brew)"}]}}
---

# Notesmd

Obsidian vault = a normal folder on disk. If running `notesmd-cli` returns an error, you need to ind the vaults as described in `references/vaults.md` and set a default vault with `notesmd-cli set-default <vault name>`

Vault structure (typical)
- Notes: `*.md` (plain text Markdown; edit with any editor)
- Config: `.obsidian/` (workspace + plugin settings; usually don’t touch from scripts)
- Canvases: `*.canvas` (JSON)
- Attachments: whatever folder you chose in Obsidian settings (images/PDFs/etc.)
- AGENTS.md: instructions how to work with the vault - MUST READ (if exists in vault root)

## notesmd-cli quick start

Pick a default vault (once):
- `notesmd-cli set-default "<vault-folder-name>"`
- `notesmd-cli print-default` / `notesmd-cli print-default --path-only`

Search
- `notesmd-cli search "query"` (note names)
- `notesmd-cli search-content "query"` (inside notes; shows snippets + lines)

Create
- `notesmd-cli create "Folder/New note" --content "..." --open`
- Requires Obsidian URI handler (`obsidian://…`) working (Obsidian installed).
- Avoid creating notes under “hidden” dot-folders (e.g. `.something/...`) via URI; Obsidian may refuse.

Move/rename (safe refactor)
- `notesmd-cli move "old/path/note" "new/path/note"`
- Updates `[[wikilinks]]` and common Markdown links across the vault (this is the main win vs `mv`).

Delete
- `notesmd-cli delete "path/note"`

Prefer direct edits when appropriate: open the `.md` file and change it; Obsidian will pick it up.