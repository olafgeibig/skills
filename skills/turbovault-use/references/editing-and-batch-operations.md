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

## Dry-run and hash-guarded apply

`edit_note` can preview before it writes: `dry_run: true` applies nothing and returns `blocks_applied`/`total_blocks`, `old_hash`/`new_hash`, and a `diff_preview`; the file stays byte-identical. Apply with `dry_run: false` plus `expected_hash: <old_hash from the preview>`, so the write is guarded against a file that changed in between. After the write, confirm `blocks_applied` equals `total_blocks`, then read the target back.

## Appending content

Use append mode only when the new content unambiguously belongs at the end. Do not append tasks or content blindly when placement affects semantics or section structure.

## Write-file chunk assembly

Assembling a note from multiple `read_file` chunks by concatenation glues content when a chunk's trailing newline is missing (`## See Also\n- foo+- [[+Agents]]`). After any multi-chunk `write_file`, read the file back and scan for `+[[`, `+##`, `+-` artifacts; prefer reading the source in one `read_file(offset/limit)` call, and for large files append chunks via `patch` instead of overwriting with `write_file`.

## Index.md duplicates after patch

`patch` on an Index.md can leave both the old and the new line in place. Prefer `write_file` for Index.md; when patching, read the file first and target a unique occurrence.

## Atomic batches

Use `batch_execute` when creating or updating multiple files and partial completion would leave the vault inconsistent.

Typical cases:

- ingest that creates several connected notes;
- coordinated note and MoC updates;
- a structural rename requiring several link corrections;
- repeated frontmatter updates that must succeed together.

Build every operation explicitly. Do not rely on provider defaults for path, mode, or merge behavior.

`batch_execute` accepts only `CreateNote | CreateFile | WriteNote | WriteFile | DeleteNote | DeleteFile | MoveNote | MoveFile | UpdateLinks` — it does not accept `UpdateFrontmatter`. Run a frontmatter update (e.g. a SHA stamp) as a separate `update_frontmatter` call instead, in parallel with the batch when it touches a different file. `WriteNote` is a full overwrite, not an append: read append-only files (index, log) first and batch their merged content; `CreateNote` behaves the same way.

A large rebuild (callout + new section + source list + MoC entry) belongs in ONE `edit_note` call with multiple SEARCH/REPLACE blocks — atomic and faster than sequential calls; check the response counts afterwards.

## Verification

A successful write response is not sufficient for external-state claims:

1. Read each changed target.
2. Confirm the intended content and frontmatter.
3. Check graph effects where links changed.
4. For a batch, verify that every operation landed and no partial state remains.
5. For `edit_note`, `blocks_applied` must equal `total_blocks` in the response; a fuzzy-matched block is not a success.
6. After any response that reports a block as fuzzy-matched, re-read the frontmatter character-exact: fuzzy matching can damage adjacent tokens (a date value can gain a stray digit). Parse date values, `topics:`, and lists as YAML after every such write — do not trust the success response.
7. After a fuzzy-matched block, re-read with the same tool the parser uses (`read_note` — a filesystem read can normalize differently) and rebuild the SEARCH text byte-for-byte from that output before re-issuing; whitespace, typographic quotes/dashes, and invisible characters are the usual mismatch causes.
