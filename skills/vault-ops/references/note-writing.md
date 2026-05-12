## Writing notes
Notes contain the actiual content. They must follow a template defined in AGENTS.md

## Template

Use `./assets/note-template.md` as the default note structure.

If the selected vault's root `AGENTS.md`, `README.md` or files referenced by it define a different note structure, follow the vault-local rules instead.

Do not omit required sections or invent new structural layouts unless the vault-local instructions allow it.

## Description Methodology

The `description` field in the frontmatter functions as a retrieval filter, not a content summary. Optimize it for search discoverability and progressive disclosure.

## Topological Linking

The note must integrate into the vault graph, see `./references/vault-graph.md`

In addition to the structured `topics` array in the frontmatter, the body or footer of the note must contain an explicit inline wiki-link to the same MoC or topics. The frontmatter enables querying; the inline link establishes the graph edge required for traversal.
