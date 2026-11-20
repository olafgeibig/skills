# Editing and Batch Operations

## Hermes payloads

Pass `tool_call.calls` as a real array of `{name, arguments}` objects, not JSON nested in a string. Serialize `content` and `edits` once as ordinary JSON strings; preserve literal quotes, backslashes, and Unicode in the note. A malformed envelope or wrong key is rejected before MCP runs; correct the structure and reissue the same tool. If a write is too large for the client, split it at section boundaries, sequence the writes with fresh hashes, and append any footer last.

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

- Read the note first and copy exact text into SEARCH. When the note was already written earlier in this session, re-read it before building SEARCH — text from a pre-write read skips lines that changed in between, fuzzy-matches into the gap, and splices adjacent lines together.
- Include enough surrounding context for uniqueness.
- Use the complete delimiters, including `REPLACE` on the closing line. **Each block needs its own opening `<<<<<<< SEARCH` and closing `>>>>>>> REPLACE`** — two edits written as one block with two `=======` dividers is a parse error (`block contains 3 `=======` divider lines`), not two blocks.
- End the `edits` string exactly at the `>>>>>>> REPLACE` line — no trailing XML-style closing tag. A stray `</edits>` is parsed as more block content and fails with `Parse error: Incomplete SEARCH/REPLACE block (state: InReplace). Expected >>>>>>> REPLACE`.
- No wrapper tags around the block (`<edits>`, `<search>`, `<replace>`) and no quote-escaping of the delimiters — the parser reads them as content and fails with `Parse error: No SEARCH/REPLACE blocks found`.
- On a parse error, fix the payload and retry `edit_note`; none of the blocks apply. On an apply error, read back and reconcile before retrying (see Verification).
- Do not assume a partial match or regex interpretation.
- For a large insert, use the next heading as the SEARCH anchor and place the new section before it — the following heading stays stable while content above the insertion point changes, and short heading anchors are far less fuzzy-prone than long bullet lines with quotes or em dashes.
- After the patch, read the section back and check that no blank line sits before the inserted bullet; a SEARCH/REPLACE anchored before a heading otherwise leaves a gap.
- For catalog lines with typographic separators (e.g. em dashes), copy the full line exactly from `read_note`; do not use a prefix as the SEARCH block.
- Through `tool_call`, `edit_note` takes `{path, edits}`; a SEARCH/REPLACE block passed under a wrong argument name returns "missing required argument(s): edits" — retry with `edits`, do not rebuild the content.

Complex YAML, tables, brackets, backticks, and multiline lists can make targeted replacement fragile. If parsing or matching fails, read the complete note, modify it, and use `write_note` with explicit overwrite mode.

Files that document these delimiters themselves (this reference, recipes with example fences) trip `read_file`'s merge-conflict heuristic: an "unresolved block" report there is a false positive when the markers sit inside example fences and `git status` shows no real conflict.

## Note write path

Use `edit_note` for localized changes, or `write_note` with the current hash and explicit mode for a full rewrite. For index or catalog entries, anchor on unique complete lines and read back the edited section to catch duplicates or joined lines. Use the note tools for both operations; filesystem writes are reserved for non-note artifacts.

## Partial reads

`read_note` takes `path` and either one line selector (`head_lines` or `tail_lines`) or section selectors (`heading_equals`, `heading_level`, `last_sections`). In 4.0.2 the section selectors can be combined, e.g. `heading_level: 2`, `heading_equals: "Match"`, `last_sections: 1`; check the live schema before combining. `heading_equals` is case-sensitive: on no match, inspect the actual H1–H6 headings and retry with their exact text, or read the full note. A partial read has **no `hash`**; use a full read or an `edit_note` dry run for `expected_hash`.

## Dry-run and hash-guarded apply

`edit_note` can preview before it writes: `dry_run: true` applies nothing and returns `blocks_applied`/`total_blocks`, `old_hash`/`new_hash`, and a `diff_preview`; the file stays byte-identical. Apply with `dry_run: false` plus `expected_hash: <old_hash from the preview>`, so the write is guarded against a file that changed in between. After the write, confirm `blocks_applied` equals `total_blocks`, then follow the read-back checks below. A fuzzy warning requires reading the whole touched region.

## Write preconditions and blind overwrites

For writes to existing notes, read the current note and pass its current `expected_hash` when the tool supports it — that hash is the only protection against clobbering a change made between your read and your write; without it the write is blind. A `dry_run` preview returns the current `old_hash`, so for `edit_note` the preview can stand in for the separate read. Do not send the removed `force` argument. Never use `expected_hash: "blind"` unless the user explicitly authorizes an intentional blind overwrite.

## Append and prepend modes

`mode: prepend` keeps the frontmatter block first (the note still starts with `---`) and puts the new content at the top of the body — the right mode for newest-first logs. `mode: append` adds to the end. Use either only when the new content unambiguously belongs there. Do not append tasks or content blindly when placement affects semantics or section structure.

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

A large single-note rebuild (callout + new section + source list + MoC entry) belongs in ONE `edit_note` call with multiple SEARCH/REPLACE blocks, so interdependent changes land together: the call fails fast and names only the first failing block. Do not read a failed multi-block call as an unchanged note — treat it per Verification step 7 (read back, reconcile, repair with single-block edits). Check the response counts afterwards.

Independent section refreshes (one data note updated in several separate places) flip the trade-off: issue one block per `edit_note` call, chaining `expected_hash` from each response's `new_hash`, so every landed block survives a later failure and one stale SEARCH text costs only its own section. On `Could not find search text (tried 4 strategies)` the SEARCH text no longer matches the file byte-for-byte (drafted from an earlier read, or paraphrased) — rebuild it from a fresh `read_note` output instead of iterating on the draft; splitting into per-call blocks also reveals which block mismatched, since the multi-block error names only the first failure.

## Verification

A successful write response is not sufficient for external-state claims:

1. Read each changed target.
2. Confirm the intended content and frontmatter.
3. Check graph effects where links changed.
4. For a batch, verify every operation and determine whether partial state remains; do not assume completed operations were rolled back.
5. For `edit_note`, `blocks_applied` must equal `total_blocks` in the response. The response flags fuzzy blocks in a `warnings` array (`Block N used fuzzy (Levenshtein) matching`); no warning on complete-line SEARCH blocks means an exact match. Any fuzzy warning is mandatory: re-read the whole touched region and confirm no orphaned tail, glued line, or rewritten neighbor remains. Without that signal (older servers), treat every SEARCH that is not byte-identical to a complete line as potentially fuzzy-matched.
6. Fuzzy matching can damage adjacent tokens (a date value can gain a stray digit) — re-read the frontmatter character-exact and parse date values, `topics:`, and lists as YAML after any non-exact edit; do not trust the success response.
7. When a block failed to match (`Could not find search text (tried 4 strategies)`), the call is **not** all-or-nothing: the note can come back changed although the response reports a failure — a line named in the failing block's SEARCH region has been observed gone from the note. Re-read the whole note with the same tool the parser uses (`read_note` — a filesystem read can normalize differently), check every block's SEARCH region for missing content, reconcile against the intended state, and rebuild the SEARCH text byte-for-byte from that output; repair with single-block calls instead of resending the whole multi-block payload. Whitespace, typographic quotes/dashes, and invisible characters are the usual mismatch causes.
