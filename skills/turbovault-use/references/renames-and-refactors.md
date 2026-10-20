# Renames and Structural Refactors

Use this procedure for moves, renames, and changes that affect multiple links or navigation structures.

## Before changing

1. Read the vault `AGENTS.md`.
2. Inventory the target note, inbound links, outbound links, aliases, and heading anchors.
3. Search for both basename and path-qualified references.
4. Define scope and rollback before multi-file changes.

## Move or rename

Use `move_note` rather than a raw filesystem move when TurboVault is available. Do not assume the tool updated every reference.

`move_note` by default does **not** update wikilinks in other notes — its warning ("Links pointing to the old path were not updated and may now be broken") is literal. Pass `update_backlinks: true` and it rewrites inbound wikilinks (bare `[[name]]` and path forms alike) and reports every changed source in `link_sources_updated`; without the flag the move succeeds and silently leaves the links pointing at the dead path. Default pattern for a rename: `move_note(from, to, update_backlinks: true)` → verify `link_sources_updated` covers every expected source → `grep -rn "<old-basename>"` over the vault for prose mentions and source-list entries the rewrite cannot see. Use a manual pattern when the move must also change content, or when building a bulk link map first:

- **A — single note whose content also changes:** `read_note` old path → `write_note` new path with links updated → `delete_note` old path (pass `confirm_path`). Write before delete, always.
- **B — link rewrite (file already moved):** one `UpdateLinks` op per source note in `batch_execute` (the current server exposes no standalone `update_links` call). Works even when the old note no longer exists.
- **C — bulk (20+):** read all old notes in parallel → build the link map → `batch_execute` with one `WriteNote` per new path → separate `batch_execute` with one `DeleteNote` per old path → verify with `graph_report(kind="broken_links")`. Never `delete_note` before the content is written at the new path.

After the move:

1. Search for the old basename and old path with an explicit `grep -rn "<old-name>"` over the vault.
   That finds prose mentions and source-list entries `graph_report(kind="broken_links")` does not see — it checks wikilinks
   only, so a complete-looking broken-links result is not completeness.
2. Check backlinks and broken links.
3. Update path-qualified wikilinks that remain.
4. Review display aliases and surrounding prose for stale terminology.
5. Update heading anchors and every `#anchor` reference when headings changed.
6. Update relevant INDEX and MoC entries.

For several coordinated files, an all-or-nothing batch needs a Git-backed vault; on the Direct backend a batch is sequential and not a transaction, so use bounded passes and verify after each pass.

## Delete

`delete_note` requires `confirm_path`, the same vault-relative path again, so a delete cannot be issued by accident. Check `get_links(path)` first. On a plain-folder (Direct) vault `force` defaults to true: the delete goes through and the inbound links stay where they are (`link_sources_updated: []`), so they break. On a Git-backed vault the delete is refused while other notes link to it unless `on_backlinks: "rewrite-stale-callout"` or `force: true` is given. Verify afterwards with `graph_report(kind="broken_links")`, not by assumption.

## Fallback without TurboVault

If TurboVault is unavailable and the user still authorizes the change:

1. use repository-aware filesystem moves;
2. search explicitly for plain and path-qualified wikilinks;
3. patch every affected reference;
4. verify no old target remains and no new broken link was introduced.

Do not stop after the filesystem move.

## Verification

- New target exists and old target does not.
- `link_sources_updated` lists every expected source note — an empty result with `update_backlinks` omitted means the inbound wikilinks were left stale.
- Inbound and outbound links resolve.
- No old basename, path, or heading anchor remains unintentionally.
- Relevant INDEX and MoC navigation is current.
- No unrelated content was reformatted or moved.
