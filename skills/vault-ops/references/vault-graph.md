## Vault Graph
The vault graph is a way to navigate the vault. MoCs

The graph starts at the `+Index.md` root MoC. It links to all area and project root MoCs and they link back to the root MoC. MoCs can have sub-MoCs. The description propert of a note or MoC should always be like a short abstract, enough that an agent querying the frontmatter can decide if the note contains interesting information or links.

## Rules

- All notes and MoCs must integrate into the vault graph, except files in directories `inbox`, `wiki` and `system`
- The `description` field in the frontmatter functions as a retrieval filter, not a content summary. Optimize it for search discoverability and progressive disclosure.
- A note should be linked to and from at lease one MoC (topic). 
- Two related notes there should always be bi-directionally linked.

## Topological Linking

`topics` in the frontmatter MUST be an array/list because a note can belong to multiple topics. To keep Obsidian property editing reliable, represent each topic as a quoted string that contains the wiki-link.

- Correct: `topics: ["[[AI]]", "[[Personal Agents]]"]`
- Also acceptable:

  ```yaml
  topics:
    - "[[AI]]"
    - "[[Personal Agents]]"
  ```

- Incorrect:
  - `topics: [[AI]]`
  - `topics: [AI]`
  - `topics: ["AI"]`
