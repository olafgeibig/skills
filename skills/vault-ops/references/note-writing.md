## Writing notes
Notes contain the actual content. They must follow a template defined in AGENTS.md

## Template

Use `./assets/note-template.md` as the default note structure.

If the selected vault's root `AGENTS.md`, `README.md` or files referenced by it define a different note structure, follow the vault-local rules instead.

Do not omit required sections or invent new structural layouts unless the vault-local instructions allow it.

## Description Methodology

The `description` field in the frontmatter functions as a retrieval filter, not a content summary. Optimize it for search discoverability and progressive disclosure.

## Language Policy Adherence

The vault's AGENTS.md defines a language per area (e.g., `agents` → EN, `gesundheit` → DE). **Write notes in the area's language, not the conversation language.** If you're conversing in German but writing a note for an English area (agents, swe, ai, devops, cybersecurity, tools), write in English. The area language overrides the conversation language.

**Pitfall:** A zettel written in German for an English-language area will need to be rewritten — the area's language policy is authoritative regardless of how the user asked for the note.

## Verification After Import

When the user copies notes from an external vault into the active vault:

1. **Don't rely on search alone** — keyword searches like `query: "WHV"` may miss notes without any content that matches your search terms.
2. **Verify all notes in the target directory have frontmatter** using `query_frontmatter_sql`:
   ```sql
   SELECT path FROM files WHERE path LIKE 'projects/<project>%' AND (tags IS NULL OR type IS NULL)
   ```
   This catches notes that were copied in but have no `tags`, `type`, `description`, or `topics` — they're invisible to the graph until frontmatter is added.

**Pitfall:** In a session where the user copies 3 notes, a keyword search may find those 3 — but there could be 6 more that happen not to contain the search term. Always verify via SQL with the directory path filter.

## Topological Linking

The note must integrate into the vault graph, see `./references/vault-graph.md`

In addition to the structured `topics` array in the frontmatter, the body or footer of the note must contain an explicit inline wiki-link to the same MoC or topics. The frontmatter enables querying; the inline link establishes the graph edge required for traversal.

## Bookmark Back-Linking

After creating a zettel for a tool, concept, or entity, check for existing bookmark notes in the same area that match the topic. If a match exists, add a backlink entry (`See also: [[zettel-name]]`) to that bookmark note. This keeps bookmarks current and creates a bidirectional graph edge between the zettel (deep knowledge) and the bookmark note (curated overview).

**Example:** A zettel about a tool in an area may get a backlink from that area's matching tools bookmark note when the bookmark note is the user's curated overview and the zettel is the deeper note.

**When to skip:** The bookmark note already covers the topic with sufficient depth directly, the zettel is only tangentially related, or adding the backlink would be a noisy side effect unrelated to the user's request.
