# Editing, Frontmatter, Templates, and Structural Mutations

Covers every mutating note operation in TurboVault 4.x: localized edits, full writes, frontmatter/tags, templates, moves, deletes, and batches. For read/query tools see `references/search-and-graph.md`; for audit, rollback, and destructive confirmation gates see `references/audit-and-drift.md`.

## Partial reads and hash preconditions

- `read_note` accepts either one line selector (`head_lines` or `tail_lines`) or combinable section selectors (`heading_level`, `heading_equals`, `last_sections`). `heading_equals` is case-sensitive.
- Partial reads return **no `hash`**. To obtain `expected_hash` for an existing note, use a full `read_note` or `edit_note(dry_run: true)` (which returns `old_hash`, `new_hash`, `blocks_applied`, and `diff_preview` without writing).
- Pass `expected_hash` on every overwrite, edit, frontmatter update, move, or delete of an existing note so concurrent changes are never clobbered. On `write_note`, `expected_hash: "absent"` enforces create-only; never pass `"blind"` without explicit user authorization.
- **On the first `expected_hash` mismatch, reconcile before retrying:** re-read the note via `read_note` and compare your prior read, the current disk content, and your intended edit. Only proceed with the fresh hash if the content is unchanged or after re-deriving a conflict-free edit against the new version — blindly swapping in the fresh hash and replaying an overwrite or stale edit destroys the concurrent change that triggered the guard.

## Localized edits (`edit_note`)

`edit_note` applies one or more SEARCH/REPLACE blocks:

```text
<<<<<<< SEARCH
exact existing lines with enough surrounding context to be unique
=======
replacement lines
>>>>>>> REPLACE
```

- **Anchor on whole lines copied from a fresh `read_note`.** After an earlier write in the same session, re-read before drafting SEARCH blocks; stale text triggers fuzzy matching and can splice adjacent lines.
- **Keep delimiters clean and verify against stray markers.** Every block needs its own `<<<<<<< SEARCH`, `=======`, and `>>>>>>> REPLACE` on dedicated lines, with no wrapper tags and no trailing text after the closing marker. If the edited text itself contains a `=======` line, use 8 or more marker characters (`<<<<<<<< SEARCH` / `========` / `>>>>>>>> REPLACE`) on all three lines. A stray `=======` inside a REPLACE half lands verbatim (e.g. `=======### Next Heading`) and silently breaks heading counts — after large multi-block edits, check for stray `^=======` lines if heading counts drop while byte size grows.
- **Multi-match refusal:** `edit_note` rejects a SEARCH block that matches more than once and asks for more context.
- **Insertions:** Anchor on the following heading and place the new section before it; read back to confirm clean blank-line spacing.
- **Multi-block vs. single-block strategy:** Put interdependent changes in one note into a single multi-block `edit_note` call; for independent section refreshes, send one block per call chaining `expected_hash` from each `new_hash` so one mismatch does not block unrelated sections.
- **Error recovery:** On a parse error, nothing applies — fix the payload and retry. On a match failure (`Could not find search text`), **do not assume the note is untouched**: re-read the full note via `read_note`, reconcile against intended content, and repair with single-block edits.
- **Fallback for fragile syntax:** When complex YAML, tables, or nested code fences make SEARCH/REPLACE brittle, read the full note and use `write_note(mode: "overwrite", expected_hash: ...)`.

## Full writes (`write_note`)

- Modes: `overwrite` (default, creates missing parent directories), `append`, and `prepend`.
- `append` and `prepend` operate inside the body (preserving frontmatter first on `prepend`) and require an existing note. On a missing path they fail with a misleading `Concurrent access conflict: File does not exist` — create the note with `overwrite` first.
- Use `append`/`prepend` only when placement at the exact end or top of the body is semantically right.
- If a write payload exceeds client call-size limits, split it at section boundaries and sequence writes with fresh `expected_hash` values instead of switching away from TurboVault.

## Frontmatter, tags, and templates

- **`update_frontmatter`:** Merges keys by default (`merge: true`); `merge: false` replaces the whole frontmatter block. Passing an empty object is a silent no-op (`success: true`) — always pass at least one key and read back. A `write_note` whose content already carries frontmatter needs no second stamp.
- **`manage_tags`:** Accepts `operation: "add"` or `"remove"` and a non-empty `tags` array (without `#`). It modifies frontmatter `tags` only and leaves inline `#tags` untouched. Listing tags uses `get_notes_info(include_tags: true)`.
- **`list_templates` / `create_from_template`:** Returns TurboVault's built-in templates (`task`, `doc`, `research`, etc.) — **not** markdown template files stored inside the vault. `create_from_template` takes `fields` as a JSON object string, records the template in frontmatter, and defaults `expected_hash` to `"absent"`. For vault-local template files, read the template and write the note with `write_note`.
- Treat templates as schemas, never literal placeholders: preserve existing real descriptions, dates, and navigation links during normalization, and never bulk-stamp dummy values solely to eliminate nulls.

## Moves, renames, and structural refactors

1. Read the vault's `AGENTS.md` and inventory inbound links (`get_links`), outbound links (`get_links(direction: "outgoing")`), aliases, and heading anchors before moving.
2. **Backend defaults differ critically:**
   - **Direct backend (default):** `move_note` defaults to `update_backlinks: false`. Always pass `update_backlinks: true` to rewrite inbound links, then inspect `link_sources_updated`. Rewriting is sequential, not atomic — verify wikilinks, inline Markdown links, and any canvas/reference links explicitly.
   - **Git backend:** `move_note` rewrites inbound wikilinks, Markdown links, and canvas references atomically by default (`update_backlinks: true`).
3. `move_note` defaults `dest_expected_hash` to `"absent"`, refusing to overwrite an existing destination unless a hash or `"blind"` is supplied.
4. For attachments or binary files, use `move_file` (advanced).
5. **Manual / bulk patterns:**
   - *Move + content rewrite:* `read_note` old → `write_note` new (with `expected_hash: "absent"`) → `delete_note` old (`confirm_path`). Always write before delete.
   - *Re-point links after a move:* `batch_execute` with `UpdateLinks` operations (`file`, `old_target`, `new_target`, `expected_hash`). Note that `UpdateLinks` is literal text replacement, not full OFM parsing.
   - *Bulk moves (20+):* read old notes in parallel → write new paths in bounded batches → delete old paths in a separate pass → sweep for leftover references.
6. **Post-move sweep:** `graph_report(kind: "broken_links")` checks parsed links only, not plain-text mentions or unlinked prose. Sweep raw text for old basenames, paths, and changed `#heading` anchors, and update navigation notes / MoCs.

## Deleting notes (`delete_note`)

- Obtain explicit user authorization before deleting, regardless of client elicitation support. Always inspect `get_links` first, and prefer archiving over deletion when content retains reference value.
- `delete_note` requires `confirm_path` equal to `path`.
- **Pass `force: false` by default on Direct:** On Direct, `force` defaults to `true` — an omitted `force` silently deletes even referenced notes and strands inbound links (`link_sources_updated: []`). Pass `force: false` explicitly so TurboVault refuses while backlinks exist, and use `on_backlinks: "rewrite-stale-callout"` or `force: true` only after explicit review/authorization. On Git, `force` already defaults to `false`.
- **Audit / commit reference:** `delete_note` does **not** return an audit `id` in its response. On Direct, look up the recorded entry via `audit_log(path: "<path>", operation: "DELETE", limit: 5)` and report its `id`; on Git, record the commit reference. Verify absence with `read_note` or `get_notes_info`.

## Batch operations (`batch_execute`)

Supported operations: `CreateNote`, `WriteNote`, `EditNote`, `DeleteNote`, `MoveNote`, `UpdateLinks`, `UpdateFrontmatter`, `ManageTags`, `CreateFromTemplate`.

- **Transaction guarantee depends on backend and failure stage:**
  - **Direct backend:** Precondition and validation failures checked up front (such as an `expected_hash` mismatch or intra-batch path collision) reject before writing. Failures **during execution** run sequentially and fail fast, leaving earlier operations applied — including partial states inside a multi-file Direct `move_note(update_backlinks: true)`. Use Direct batches only for independent or cleanly recoverable changes, and verify every target from `records[]` and `changes[]` (never top-level `success` alone).
  - **Git backend:** One all-or-nothing commit.
- **No intra-batch path collision:** Two operations in the same batch cannot target the same path; the batch is refused before execution. Combine frontmatter + body edits into one `WriteNote`/`EditNote`, or split into two sequential calls.
- **`WriteNote` / `CreateNote` are full overwrites** (no `append`/`prepend` mode in batches). Read append-only notes first and pass merged content.
- **`DeleteNote` in batches** defaults `on_backlinks` to `"refuse"` (unlike standalone Direct `delete_note`); pass `"rewrite-stale-callout"` or `"force"` explicitly when needed.

## Mutation-specific verification checks

In addition to the standard post-write read-back in `SKILL.md`:

- **`edit_note` fuzzy warnings:** Any `warnings` entry reporting fuzzy (Levenshtein) matching requires reading the entire touched region and validating frontmatter YAML (dates, lists, links), because fuzzy matches can leave line tails or corrupt adjacent tokens.
- **Direct-backend batches:** Inspect every item in `records[]` and `changes[]` (never top-level `success` alone) and resolve or report any partial state explicitly.
