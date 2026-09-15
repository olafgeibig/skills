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
- Do not assume a partial match or regex interpretation.

Complex YAML, tables, brackets, backticks, and multiline lists can make targeted replacement fragile. If parsing or matching fails, read the complete note, modify it, and use `write_note` with explicit overwrite mode.

## Appending content

Use append mode only when the new content unambiguously belongs at the end. Do not append tasks or content blindly when placement affects semantics or section structure.

## Atomic batches

Use `batch_execute` when creating or updating multiple files and partial completion would leave the vault inconsistent.

Typical cases:

- ingest that creates several connected notes;
- coordinated note and MoC updates;
- a structural rename requiring several link corrections;
- repeated frontmatter updates that must succeed together.

Build every operation explicitly. Do not rely on provider defaults for path, mode, or merge behavior.

## Verification

A successful write response is not sufficient for external-state claims:

1. Read each changed target.
2. Confirm the intended content and frontmatter.
3. Check graph effects where links changed.
4. For a batch, verify that every operation landed and no partial state remains.
