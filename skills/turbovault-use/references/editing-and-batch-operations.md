# Editing and Batch Operations

## Targeted edits

`edit_note` uses SEARCH/REPLACE blocks:

```text
<<<<<<< SEARCH
Exact old text with enough context to be unique
=======
Replacement text
>>>>>>> REPLACE
```

Rules:

- Read the note first and copy exact text into SEARCH.
- Include enough surrounding context for uniqueness.
- Use the complete delimiters, including `REPLACE` on the closing line.
- End the `edits` string exactly at the `>>>>>>> REPLACE` line — no trailing XML-style closing tag. A stray `</edits>` is parsed as more block content and fails with `Parse error: Incomplete SEARCH/REPLACE block (state: InReplace). Expected >>>>>>> REPLACE`.
- No wrapper tags around the block (`<edits>`, `<search>`, `<replace>`) and no quote-escaping of the delimiters — the parser reads them as content and fails with `Parse error: No SEARCH/REPLACE blocks found`.
- After a parse error, do not retry the same shape: rebuild the call correctly, or fall back to `write_note` with the full content in overwrite mode.
- Do not assume a partial match or regex interpretation.
- For a large insert, use the next heading as the SEARCH anchor and place the new section before it — the following heading stays stable while content above the insertion point changes, and short heading anchors are far less fuzzy-prone than long bullet lines with quotes or em dashes.
- After the patch, read the section back and check that no blank line sits before the inserted bullet; a SEARCH/REPLACE anchored before a heading otherwise leaves a gap.
- Catalog lines may use non-ASCII separators (Unicode em dash); match on stable prefixes (e.g. up to the `|` in `- [[path|alias]]`) or rewrite whole sections, verify after the write, and never assume ASCII ` - ` separators in SEARCH blocks.
- Through `tool_call`, `edit_note` takes `{path, edits}`; a SEARCH/REPLACE block passed under a wrong argument name returns "missing required argument(s): edits" — retry with `edits`, do not rebuild the content.

Complex YAML, tables, brackets, backticks, and multiline lists can make targeted replacement fragile. If parsing or matching fails, read the complete note, modify it, and use `write_note` with explicit overwrite mode.

Files that document these delimiters themselves (this reference, recipes with example fences) trip `read_file`'s merge-conflict heuristic: an "unresolved block" report there is a false positive when the markers sit inside example fences and `git status` shows no real conflict.

## Patch whitespace traps

The `patch` tool on vault notes has three recurring whitespace failure modes:

- **Title duplication:** patching a note that already has an H1 can produce a double title. Read the note first and match the title line together with its blank-line separator.
- **Concatenated lines:** a `new_string` without a trailing newline glues the replacement to the next line (`[[+Agents]][[area/x]]`). Always end inserted text with an explicit trailing newline and re-read the file after every patch.
- **Section-name mismatch:** an `old_string` written as `## Related` does not match a file with `## See Also`. Verify the actual header first (`read_file`/`search_files`) — seen variants: `## See Also`, `## Related`, `## Related Pages`, `## Verwandte Seiten` — and read the "Did you mean one of these sections?" hint in the tool response.

## Partial reads

`read_note` accepts `path` plus at most one selector — `head_lines`, `tail_lines`, `heading_equals`, `heading_level`, `last_sections`. Combining two selectors is a validation error. A partial read returns `truncated`, `total_lines`, and `returned_lines`/`sections` metadata but **no `hash`**, so it cannot supply `expected_hash`; use a full read or an `edit_note` dry run for that. Use a selector to locate or verify one section instead of pulling a multi-KB note whole.

## Dry-run and hash-guarded apply

`edit_note` can preview before it writes: `dry_run: true` applies nothing and returns `blocks_applied`/`total_blocks`, `old_hash`/`new_hash`, and a `diff_preview`; the file stays byte-identical. Apply with `dry_run: false` plus `expected_hash: <old_hash from the preview>`, so the write is guarded against a file that changed in between. After the write, confirm `blocks_applied` equals `total_blocks`, then read the target back.

## Write preconditions and blind overwrites

For writes to existing notes, read the current note and pass its current `expected_hash` when the tool supports it. `edit_note` can use the `old_hash` returned by its dry run. Do not send the removed `force` argument. Never use `expected_hash: "blind"` unless the user explicitly authorizes an intentional blind overwrite.

## Append and prepend modes

`mode: prepend` keeps the frontmatter block first (the note still starts with `---`) and puts the new content at the top of the body — the right mode for newest-first logs. `mode: append` adds to the end. Use either only when the new content unambiguously belongs there. Do not append tasks or content blindly when placement affects semantics or section structure.

## Write-file chunk assembly

Assembling a note from multiple `read_file` chunks by concatenation glues content when a chunk's trailing newline is missing (`## See Also\n- foo+- [[+Agents]]`). After any multi-chunk `write_file`, read the file back and scan for `+[[`, `+##`, `+-` artifacts; prefer reading the source in one `read_file(offset/limit)` call, and for large files append chunks via `patch` instead of overwriting with `write_file`.

## Index.md duplicates after patch

`patch` on an Index.md can leave both the old and the new line in place. Prefer `write_file` for Index.md; when patching, read the file first and target a unique occurrence.

## Batch operations and transaction guarantees

Check the active write backend before planning a batch. With the `direct` backend, `batch_execute` runs sequentially and fails fast; operations completed before a later failure remain applied. It is not a transaction. Only describe a batch as all-or-nothing when the configured backend's documented contract guarantees it. Use Direct batches only when partial completion is recoverable or operations are independent; otherwise use bounded passes, verify each pass, and preserve a recovery path.

Typical cases, when partial completion is acceptable or a transaction is guaranteed:

- ingest that creates several connected notes;
- coordinated note and MoC updates;
- a structural rename requiring several link corrections;
- repeated frontmatter updates whose recovery plan is explicit.

If all operations must succeed together, do not use a Direct-backend batch; use only a backend whose transaction guarantee has been verified.

Build every operation explicitly. Do not rely on provider defaults for path, mode, or merge behavior.

`batch_execute` accepts `CreateNote | WriteNote | EditNote | DeleteNote | MoveNote | UpdateLinks | UpdateFrontmatter | ManageTags | CreateFromTemplate`, so a frontmatter stamp, a body edit, and a tag change can ride in one call. One constraint: **no two operations in one batch may touch the same path** — the batch is refused before anything runs (`intra-batch path collision`), so a frontmatter stamp plus a body rewrite of the same note needs two calls. Verify from the response's `records[]` (per-operation `success`/`error`/`affected_files`) and `changes[]`, not from the top-level `success` alone. `WriteNote` is a full overwrite, not an append: read append-only files (index, log) first and batch their merged content; `CreateNote` behaves the same way.

A large single-note rebuild (callout + new section + source list + MoC entry) belongs in ONE `edit_note` call with multiple SEARCH/REPLACE blocks: a multi-block call is fail-fast and **all-or-nothing** on a match failure — the error names only the first failing block and nothing is applied, so interdependent changes never land half-done. Check the response counts afterwards.

Independent section refreshes (one data note updated in several separate places) flip the trade-off: issue one block per `edit_note` call, chaining `expected_hash` from each response's `new_hash`, so every landed block survives a later failure and one stale SEARCH text costs only its own section. On `Could not find search text (tried 4 strategies)` the SEARCH text no longer matches the file byte-for-byte (drafted from an earlier read, or paraphrased) — rebuild it from a fresh `read_note` output instead of iterating on the draft; splitting into per-call blocks also reveals which block mismatched, since the multi-block error names only the first failure.

## Verification

A successful write response is not sufficient for external-state claims:

1. Read each changed target.
2. Confirm the intended content and frontmatter.
3. Check graph effects where links changed.
4. For a batch, verify every operation and determine whether partial state remains; do not assume completed operations were rolled back.
5. For `edit_note`, `blocks_applied` must equal `total_blocks` in the response. The response never says whether a block matched exactly or fuzzily (only hashes and counts come back), so treat every SEARCH that is not byte-identical to a complete line as potentially fuzzy-matched: re-read the touched region and confirm no orphaned tail remains.
6. Fuzzy matching can damage adjacent tokens (a date value can gain a stray digit) — re-read the frontmatter character-exact and parse date values, `topics:`, and lists as YAML after any non-exact edit; do not trust the success response.
7. When a block failed to match (`Could not find search text (tried 4 strategies)`), re-read with the same tool the parser uses (`read_note` — a filesystem read can normalize differently) and rebuild the SEARCH text byte-for-byte from that output before re-issuing; whitespace, typographic quotes/dashes, and invisible characters are the usual mismatch causes.
