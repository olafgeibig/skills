# Archiving and Removal

## Archiving a Single Page

When content is fully superseded or the domain scope changes:

1. Create `_archive/` directory in the domain wiki if it doesn't exist
   (via `mcp_turbovault_write_note` with a placeholder)
2. Move the page to `_archive/` with its original path:
   `mcp_turbovault_move_note(from="wiki/<target>/entities/old-page.md", to="wiki/<target>/_archive/entities/old-page.md")`
3. Remove the page from the domain wiki's `index.md`
4. Update any pages that linked to it — replace wikilink with plain text + "(archived)"
5. Log the archive action in the domain wiki's `log.md`

## Removing an Entire Domain Wiki

When the user says "delete wiki X" or "remove wiki Y":

1. **List all files in the wiki directory** via terminal or search:
   `mcp_turbovault_search(query="wiki/X/")` to find all pages
2. **Delete all files** — use the terminal tool:
   `rm -rf /path/to/vault/wiki/X/`
   (This is faster than individual TurboVault deletes for an entire directory.)
3. **Remove the entry** from the root `wiki/index.md` (the hub):
   Read the hub, delete the `## wiki-name` section, write back.
4. **Log the deletion** — write a short note to the wiki's `log.md` before
   deleting it, OR if already deleted, note it in the hub changes.
5. **No INDEX.md updates needed** — the root INDEX.md links to `wiki/index.md`,
   which now reflects the change.

**Pitfall — check for cross-references first:** Before deleting, search for
`[[wiki/<wiki-name>/` across the vault to find pages in other wikis that link
to content in the wiki being deleted. Report these to the user and offer to
update or remove the links.

**Pitfall — don't use TurboVault delete for bulk removal:** `delete_note`
requires confirmation per file and is slow for 10+ files. Terminal `rm -rf`
is the right tool for removing an entire wiki directory.
