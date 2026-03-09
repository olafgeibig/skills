## Title as Claim

The filename and primary heading (#) must be formulated as a specific, opinionated claim. Do not use topical or categorical labels. The title must enable traversal as reasoning, meaning the core argument is evident without opening the file.

## Template Enforcement

Every new note must strictly adhere to the structural template defined for its specific category or type. Do not omit required sections or invent new structural layouts. The skill templates are good practices, but can be overridden by definitions in the AGENTS.md `<skill-dir>/references/note-template.md` 

## Description Methodology

The description field in the frontmatter functions exclusively as a retrieval filter, not a content summary. It operates as lossy compression to help agents determine relevance before loading the full file content. Optimize the vocabulary for search discoverability and progressive disclosure.

## Topological Linking

The note must integrate into the associative heterarchy.

- `topics` in the frontmatter MUST be an array/list, because a note can belong to multiple topics.
- To keep Obsidian property editing reliable, represent each topic as a *quoted string* that contains the wiki-link.
  - Correct:
    - `topics: ["[[HR]]", "[[BOSCH APPS]]"]`
  - Also acceptable (block list):
    - `topics:`
    - `  - "[[HR]]"`
    - `  - "[[BOSCH APPS]]"`
  - Incorrect:
    - `topics: [[HR]]` (not an array)
    - `topics: [HR]` (missing wiki-link syntax)
    - `topics: ["HR"]` (missing wiki-link syntax)

In addition to the structured `topics` array in the frontmatter, the body or footer of the note must contain an explicit inline wiki-link to the same MoC(s). The frontmatter enables querying; the inline link establishes the semantic graph edge required for multi-hop traversal.
