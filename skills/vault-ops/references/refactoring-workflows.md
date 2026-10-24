# Refactoring Workflows

User-directed structural refactors and note retirement. Scope the affected files before writing; run multi-file structural changes as explicit work with verification, never as a quick patch.

## Promote a Sub-MoC to a Top-Level Project

Use when a sub-MoC nested under a parent project accumulates enough notes to warrant its own directory, tag, and INDEX entry. Promote when: the sub-project holds 3+ notes; the parent `project/*` tag is too generic to filter them; the parent MoC becomes a dump container mixing unrelated topics; task filters like `path includes projects/<parent>` catch unrelated notes; or the topic is an active project with ongoing obligations.

**Procedure:**

1. **Create the target directory and move notes** — one `move_note` per file; move the MoC first, then its child notes.
2. **Update tags** — on every note, replace `project/<parent>` with `project/<dir>` via `update_frontmatter` with `merge=true` (`merge=false` rewrites all frontmatter — avoid); the tags array is replaced wholesale, so pass the complete tag list that must remain, not only the changed tag.
3. **Fix wikilinks (only when renaming)** — pass `update_backlinks: true` on every `move_note`: on Direct it defaults to false, and with it set, inbound wikilinks and Markdown links are rewritten (inspect `link_sources_updated`). Coverage is not complete — reference-style links, canvas cards, aliases and frontmatter `topics` still need SEARCH/REPLACE, as do INDEX entries. Compare `get_links` before and after the move instead of assuming either state.
4. **Update the project INDEX** — lift the sub-MoC to its own `##` entry with a one-or-two-sentence routing description; shorten the parent's entry; bump the INDEX `updated:` date.
5. **Clean up the parent MoC** — drop the promoted sub-project from the parent's core-notes list; point to it from a "Related Projects" / "See Also" section.
6. **(Optional) create a task note** — `projects/<dir>/Tasks.md` (or `Aufgaben.md` for German-language vaults): a `tasks` query block filtered by `path includes projects/<dir>`.

**Pitfalls:**

- `move_note` without `update_backlinks: true` strands every inbound link, and even with it `topics:`, aliases and canvas cards do not follow → `get_links` before and after, then targeted SEARCH/REPLACE.
- `topics` is not a real wikilink — `get_links` won't find notes by it → keep real body `[[wikilinks]]` + a `Topics:` footer.
- `update_frontmatter` merge behavior can clear fields → `merge=true` for targeted updates.
- Stale INDEX `updated:` → set it manually after structural changes.

## Move Notes Between Areas

Use when the boundary between two areas shifts: notes, bookmark files or zettels sit under an area whose scope no longer covers them. Move them — do not copy, and do not leave a second file behind under a near-identical name.

**Procedure:**

1. **Inventory both areas from the filesystem.** `ls area/<from>/*.md` plus a per-file frontmatter dump gives the real set; reconcile any SQL-derived list against it before building the work list, and note files with no frontmatter at all.
2. **Check the destination for a name collision.** List `area/<to>/` for the same topic before choosing the target name. Two near-identical filenames in one directory (`agent-tool-bookmarks.md` beside `agent-tools-bookmarks.md`) is a defect you create yourself: rename the moved file by its distinguishing scope, or merge its entries verbatim into the existing file and retire the source.
3. **Move with explicit backlink rewriting** — one `move_note(from=…, to=…, update_backlinks: true)` per file. On Direct the flag defaults to false, so omitting it strands every inbound link. Read `link_sources_updated` as the list of files to spot-check.
4. **Rewrite each moved note's own metadata** — `tags`: swap `area/<from>` for `area/<to>`, keeping descriptive tags; frontmatter `topics`: `[[+NewMoC]]`; body `Topics:` footer: the same MoC link, added if the note had no footer. Skipping this leaves the note tagged to the old area and invisible to the new MoC.
5. **Fix links between moved notes.** Moving the referenced file first rewrites inbound links to it, including links inside notes that move later. Finish with a grep for the old path across the vault.
6. **Update both MoCs in opposite directions** — drop the entries from the source MoC, add one line each to the target MoC in that MoC's language, bump `updated:` on both. Do not mirror the moved notes in the source MoC — not even as a short "these moved to X" list, which is the same duplicate with a friendlier heading and drifts the moment one of them moves again. A single routing line naming the target area's MoC is the whole entry, plus the stale description fix in step 7.
7. **Re-scope the area descriptions.** When the area's purpose changed, rewrite the sub-index abstract (`area/INDEX.md`) and the MoC's `description:` plus orientation paragraph to state the new boundary and where the moved class of note now lives. The MoC `description:` is the routing filter — leave it stale and the next note lands in the wrong area.
8. **Verify** — `grep -rn 'area/<from>/<name>' --include='*.md' .` returns nothing; `get_links(direction=incoming)` on a moved note lists the target MoC; `query_frontmatter_sql` shows `area/<to>` in `tags` and `[[+<NewMoC>]]` in `topics`; `ls area/<from>` holds only what stayed.

**Pitfalls:**

- A note without frontmatter is invisible to every metadata query yet still sits in the file listing. Give it frontmatter while moving it, otherwise it arrives in the target area unregistered.
- An area can legitimately end up with one or two notes after a re-scope. Rewrite its MoC around what remains plus a pointer to the target area; do not delete the MoC and do not pad it with notes from elsewhere.
- Moving is also the moment to fix metadata the old area tolerated: `topics` holding plain tags instead of MoC wikilinks, missing body `Topics:` footers, stale `updated:`.

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

## Retire an Obsolete Note

Use when the user asks whether a note is obsolete and authorizes deletion if it is. This is conditional authorization for that note, not permission to redesign the surrounding documentation.

1. **Resolve the target before mutation.** Read the candidate note and enclosing MoC. If “this note” could refer to multiple recent notes, ask for the intended path before deleting; do not choose an unrelated older note solely because its topic matches the proposed replacement.
2. **Test complete supersession.** Separate the note's problem, proposed mechanism, and independent requirements. Check the replacement against current primary documentation. For tool-access notes, distinguish schema discovery/context cost from authorization and work isolation: on-demand schemas do not by themselves enforce read/write permissions. Preserve or update a note with surviving independent value instead of deleting it as wholly obsolete. For a collection or bookmark file, compare **entry by entry**, not by topic: the replacement can be newer, larger and better maintained while still missing entries the old file carried, and a topic-level match silently loses them. Carry each missing entry into the replacement verbatim — same field set, same wording, same `Date:` — then count entries on both sides before retiring the source.
3. **Inventory incoming references.** Use backlinks plus text search for the filename, wikilink target, and title; metadata and prose mentions may not appear in the backlink graph. Read actual referring passages before deciding which edits are necessary.
4. **Keep the change bounded.** Remove or replace dead MoC/list links and directly invalidated recommendations. Do not turn a link cleanup into a rewrite of sibling architectures. If a related note needs substantive redesign, report it as separate work. When changing a recommendation, also check its configuration example and verdict for contradictions; do not claim a read-only boundary while leaving write tools in the example, or infer a security boundary from tool labels alone.
5. **Apply the decision.** If the note is completely superseded and the user already authorized deletion on that condition, delete the exact resolved path using TurboVault's confirmation and hash guards. Otherwise report the surviving value and propose the narrower update. When the client cannot answer that confirmation, the delete is refused with `Couldn't confirm with the user …` and nothing changes: do not retry the identical call, and do not delete through `terminal`/`rm`. Retire it by moving it into `archive/` instead — `status: archived` in the frontmatter, tags reduced to `archived`, `description:` and the H1 marked as retired with a link to the replacement — and tell the user the deletion is still pending plus what would enable it (see `turbovault-use` → `references/audit-and-rollback.md`).
6. **Verify the result.** Read back the deleted path and expect absence; search for remaining references, and read back every edited referring note. A title search returning zero is not enough to establish that links were cleaned up. Report the deleted path, the reason for retirement, and any intentionally retained material.

## Load the Tool Skill Before Planning

Before authoring a refactor plan, list every tool the plan will use (MCP tools, `edit_note`, batch writes) and load the matching tool skill — read its refactor recipe and quirks sections. Record in the plan header which tool quirks the plan accounts for. A plan built on assumed tool behavior breaks at the first tool call: `move_note` rewrites inbound links only when `update_backlinks: true` is passed (default false on Direct) and never touches `topics:`, aliases or canvas cards (see `turbovault-use`), so a half-migrated state costs a plan rebuild plus recovery from backup.
