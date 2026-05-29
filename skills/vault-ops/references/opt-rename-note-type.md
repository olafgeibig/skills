# Rename a Note Type Across a Vault

Use when a vault-local note type is renamed (for example `resource-collection` → `bookmarks`) and the change must be applied consistently across templates, frontmatter, governance docs, MoCs, project notes, and concept notes.

## Scope

This workflow covers bulk note-type refactors in an active TurboVault vault. It is intentionally staged as an `opt-*` workflow because broad type renames can be risky and should usually be explicit user-directed work.

## Required Orientation

1. Load `vault-ops` and read the selected vault's `AGENTS.md`.
2. If any target path is under `wiki/`, load `vault-wiki` and follow its orientation/logging rules.
3. Identify the old type name and new type name.
4. Identify whether filenames/templates should also change.

## Discovery

Use both metadata and full-text discovery:

- SQL for frontmatter type:
  ```sql
  SELECT path, type FROM files WHERE type = '<old-type>' ORDER BY path LIMIT 100
  ```
- Full-text search for prose/template references:
  - old type slug: `<old-type>`
  - title-case label: `Resource Collection`, etc.
  - plural label: `Resource Collections`, etc.
- File-name search for old template/support filenames where available.

Do not assume a frontmatter-only update is enough; governance docs and MoC prose often carry the old concept name.

## Update Targets

Patch or rewrite all active targets that intentionally describe the current model:

- `AGENTS.md` note type table
- `system/templates/<type>.md`
- notes whose `type:` frontmatter uses the old value
- MoC headings/sections that use old labels
- project concept/design notes describing note types
- skill references if the skill itself still mentions the old type

When renaming a template file, prefer an actual file rename/move if using filesystem tools; if using TurboVault, create the new template note, verify it, then remove the old file by the appropriate safe method.

## Raw/Wiki Exception

Raw sources under `wiki/<domain>/raw/` are immutable by default. Preserve historical raw sources unless the user explicitly asks to adapt the raw source itself. If the user explicitly asks for that exception:

1. Load `vault-wiki`.
2. Read the target wiki's `SCHEMA.md`, `index.md`, and `log.md` as needed.
3. Apply the explicit raw-source correction.
4. Append a log entry explaining that the raw source was intentionally updated to align the concept with the current skill.

## Verification

Run all of these checks before reporting completion:

1. Old type no longer appears as active frontmatter:
   ```sql
   SELECT path, type FROM files WHERE type = '<old-type>' ORDER BY path LIMIT 100
   ```
   Expected: zero rows.

2. New type appears where expected:
   ```sql
   SELECT path, type FROM files WHERE type = '<new-type>' ORDER BY path LIMIT 100
   ```

3. Full-text search for old terms returns zero active hits, or only explicitly reported historical exceptions.

4. New template exists and old template name no longer exists.

5. Read back at least one representative updated note and the governance doc (`AGENTS.md` or equivalent).

## Reporting

Report concise counts and exceptions:

- number of notes with old frontmatter type before/after
- number of notes with new type after
- renamed/deleted template paths
- remaining old-term hits, if any, with reason
- whether `vault-wiki` log was updated for wiki changes
