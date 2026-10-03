# Refactoring Workflows

Staged, user-directed structural refactors — both workflows below change many files, so run them as explicit work with verification, never as a quick patch.

## Promote a Sub-MoC to a Top-Level Project

Use when a sub-MoC nested under a parent project accumulates enough notes to warrant its own directory, tag, and INDEX entry. Promote when: the sub-project holds 3+ notes; the parent `project/*` tag is too generic to filter them; the parent MoC becomes a dump container mixing unrelated topics; task filters like `path includes projects/<parent>` catch unrelated notes; or the topic is an active project with ongoing obligations.

**Procedure:**

1. **Create the target directory and move notes** — one `move_note` per file; move the MoC first, then its child notes.
2. **Update tags** — on every note, replace `project/<parent>` with `project/<dir>` via `update_frontmatter` with `merge=true` (`merge=false` rewrites all frontmatter — avoid); the tags array is replaced wholesale, so pass the complete tag list that must remain, not only the changed tag.
3. **Fix wikilinks (only when renaming)** — `move_note` does NOT update wikilinks: run `get_backlinks` on the old MoC path BEFORE moving, then update body `[[links]]` (SEARCH/REPLACE), frontmatter `topics`, and INDEX entries.
4. **Update the project INDEX** — lift the sub-MoC to its own `##` entry with a one-or-two-sentence routing description; shorten the parent's entry; bump the INDEX `updated:` date.
5. **Clean up the parent MoC** — drop the promoted sub-project from the parent's core-notes list; point to it from a "Related Projects" / "See Also" section.
6. **(Optional) create a task note** — `projects/<dir>/Tasks.md` (or `Aufgaben.md` for German-language vaults): a `tasks` query block filtered by `path includes projects/<dir>`.

**Pitfalls:**

- `move_note` leaves broken `[[links]]` behind → `get_backlinks` before moving, then systematic SEARCH/REPLACE.
- `topics` is not a real wikilink — `get_backlinks` won't find notes by it → keep real body `[[wikilinks]]` + a `Topics:` footer.
- `update_frontmatter` merge behavior can clear fields → `merge=true` for targeted updates.
- Stale INDEX `updated:` → set it manually after structural changes.

## Rename a Note Type

Use when a vault-local note type is renamed (e.g. `resource-collection` → `bookmarks`) and the change must land consistently across templates, frontmatter, governance docs, MoCs, project notes, and concept notes. Broad type renames are risky — treat them as explicit user-directed work.

**Orientation:** read the vault's `AGENTS.md`; if any target path is under `wiki/`, load `vault-wiki` and follow its orientation/logging rules; identify the old and new type names, and whether filenames or templates change too.

**Discovery — metadata plus full-text:**

- Frontmatter SQL: `SELECT path, type FROM files WHERE type = '<old-type>' ORDER BY path LIMIT 100`
- Full-text search for the old slug, its title-case label, and its plural label — prose and templates often carry the old concept name.
- File-name search for old template/support files.

**Update targets:** `AGENTS.md` note-type table; `system/templates/<type>.md`; notes whose `type:` uses the old value; MoC headings/sections with old labels; project concept notes; skill references that still mention the old type. For a template rename, create and verify the new template before removing the old file by the appropriate safe method.

**Raw/wiki exception:** raw sources under `wiki/<domain>/raw/` are immutable by default — preserve them unless the user explicitly asks for the exception. Then load `vault-wiki`, read the wiki's `SCHEMA.md`, `<name>-wiki.md`, and `log.md` as needed, apply the correction, and append a log entry explaining the intentional raw-source update.

**Verification — all checks before reporting done:**

1. `SELECT path, type FROM files WHERE type = '<old-type>'` returns zero rows.
2. `SELECT path, type FROM files WHERE type = '<new-type>'` shows the new type where expected.
3. Full-text search for old terms returns zero active hits — or only explicitly reported historical exceptions.
4. The new template exists and the old template name is gone.
5. Read back one representative updated note and the governance doc.

**Reporting:** old/new type note counts before and after; renamed or deleted template paths; remaining old-term hits with reason; whether the `vault-wiki` log was updated for wiki changes.

## Load the Tool Skill Before Planning

Before authoring a refactor plan, list every tool the plan will use (MCP tools, `edit_note`, batch writes) and load the matching tool skill — read its refactor recipe and quirks sections. Record in the plan header which tool quirks the plan accounts for. A plan built on assumed tool behavior breaks at the first tool call: `move_note` does not update wikilinks (see `turbovault-use`), and the half-migrated state costs a plan rebuild plus recovery from backup.
