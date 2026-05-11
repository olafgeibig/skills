## Scope

Use this file for regular notes. For Maps of Content, use `./reference/moc-writing.md` instead.

## Title as Claim

The filename and primary heading (`#`) must be formulated as a specific, opinionated claim. Do not use topical or categorical labels. The title must make the core argument clear before opening the file.

## Template

Use `./reference/note-template.md` as the default note structure.

If the selected vault's root `AGENTS.md` or files referenced by it define a different note structure, follow the vault-local rules instead.

Do not omit required sections or invent new structural layouts unless the vault-local instructions allow it.

## Description Methodology

The `description` field in the frontmatter functions as a retrieval filter, not a content summary. Optimize it for search discoverability and progressive disclosure.

## Topological Linking

The note must integrate into the vault graph.

- `topics` in the frontmatter MUST be an array/list because a note can belong to multiple topics.
- To keep Obsidian property editing reliable, represent each topic as a quoted string that contains the wiki-link.
  - Correct: `topics: ["[[HR]]", "[[BOSCH APPS]]"]`
  - Also acceptable:

    ```yaml
    topics:
      - "[[HR]]"
      - "[[BOSCH APPS]]"
    ```

  - Incorrect:
    - `topics: [[HR]]`
    - `topics: [HR]`
    - `topics: ["HR"]`

In addition to the structured `topics` array in the frontmatter, the body or footer of the note must contain an explicit inline wiki-link to the same MoC or topics. The frontmatter enables querying; the inline link establishes the graph edge required for traversal.
