## Writing notes
Notes contain the actual content. They must follow a template defined in AGENTS.md

## Template

Use `./assets/note-template.md` as the default note structure.

If the selected vault's root `AGENTS.md`, `README.md` or files referenced by it define a different note structure, follow the vault-local rules instead.

Do not omit required sections or invent new structural layouts unless the vault-local instructions allow it.

**Template missing? Derive from siblings.** A vault `AGENTS.md` may cite a template that was never written to disk — that is normal, not exceptional. When no template file exists for a note type (and the project skill's `references/` has no derived shape yet), read 2–3 sibling notes with the same `doc:` value (or the same directory-sublocation) and derive the de-facto structure — the union of frontmatter fields, H1 shape, lead paragraph, footer, and standing section headings — then apply it. Never invent a layout from scratch. Do not recreate the missing template file mid-task. Document the derived shape in the project skill's `references/` so the next agent doesn't have to re-derive it.

Before adding a markdown construct the vault has not used yet (callout, table, admonition), search the vault for existing instances (e.g. `grep -rn '> [!' --include=*.md .`) and adopt the vault's own placement — not the Obsidian default.

## Description Methodology

The `description` field in the frontmatter functions as a retrieval filter, not a content summary. Optimize it for search discoverability and progressive disclosure.

## Language Policy Adherence

The vault's AGENTS.md defines a language per area (e.g., `agents` → EN, `gesundheit` → DE). **Write notes in the area's language, not the conversation language.** If you're conversing in German but writing a note for an English area (agents, swe, ai, devops, cybersecurity, tools), write in English. The area language overrides the conversation language.

**Pitfall:** A zettel written in German for an English-language area will need to be rewritten — the area's language policy is authoritative regardless of how the user asked for the note.

## Consolidation Style — Fact Mirror, Not Audit Trail

A note is a **fact mirror**: it states the current knowledge, each fact once. It is not an audit trail — no iteration history, no superseded statements, no rejected-findings tables, no decision-recommendation menus, no inline ✅/⚠️/❌ as evaluation — status only where the facts justify it. Verification checklists and correction history belong in pitfall captures or skill references, not in the note body.

**When the user signals a note is confusing or bloated** ("extrem verwirrend" / "zu viel" / "kompakter" — extremely confusing / overloaded / more compact), that is authority for a radical restructuring, not incremental patching — the trigger compounds when the note has grown past ~5 KB:

1. Back up the file first (copy it to a scratch path as a rollback option).
2. Inventory the user's explicit requirements, and what moves out of the note (general pitfalls → a skill).
3. Rewrite the note in one `write_file` with the new minimal structure — not a chain of patches.
4. Report the reduction (size / lines / sections before → after).

## Note Footer Format

Notes end with a footer block after a `---` separator (3 dashes on their own line, blank line after) — plain labels, never heading markup (`## Siehe auch` is a common mistake):

```markdown
---

Topics:
- [[+ParentMoC]]

Related:
- [[related-note]] — description
```

`Topics:` matches the `topics:` frontmatter (bidirectional consistency; always at least one). `Related:` is optional — include it when related notes exist (`— description` suffixes optional but recommended).

## Importing Legacy Notes

When the user copies notes from an external vault into the active vault, they arrive without frontmatter, with legacy task formats, and unlinked from the graph. Follow this procedure:

1. **Discover all imported files — don't rely on search alone.** Keyword searches like `query: "<search-term>"` may miss notes without any content that matches your search terms. Verify all notes in the target directory using `query_frontmatter_sql`:
   ```sql
   SELECT path FROM files WHERE path LIKE 'projects/<project>%' AND (tags IS NULL OR type IS NULL)
   ```
   Files returned by this query (missing `tags` or `type`) are the unprocessed imports — notes that were copied in but have no `tags`, `type`, `description`, or `topics`; they're invisible to the graph until frontmatter is added.
2. **Read & assess each note.** Topic and scope; content clarity (note ambiguities to ask about); legacy task formats (`#tag` in tasks, `@completed(ISO-date)`, plain `✅ date`); type fit (atomic fact → `type: zettel`, structured link list → `type: bookmarks`).
3. **Clarify before editing.** Ask about unclear terms/abbreviations/typos, tasks possibly completed since export, and naming/scope decisions. Do not auto-interpret ambiguous content — user confirmation prevents rework.
4. **Add frontmatter** per vault `AGENTS.md`: `description` (~150 chars, no period), `type`, `created`, `tags` matching the directory, and `topics` as `"[[+<MoC>]]"`.
5. **Convert legacy task formats:** inline `#topic` tag → `🆔 <topic-id>`; `@completed(...)` → `✅ YYYY-MM-DD`; a plain `✅ YYYY-MM-DD` stays valid.
6. **Add the body footer** — `---` separator plus a `Topics:` wikilink to the parent MoC (see Note Footer Format above).
7. **Update the project MoC** — add an entry for each new note under the MoC's core-notes section.
8. **Verify zero unprocessed files** — re-run the discovery SQL; every file must have `type IS NOT NULL` and `tags IS NOT NULL`, otherwise return to step 2.

**Pitfall:** In a session where the user copies 3 notes, a keyword search may find those 3 — but there could be 6 more that happen not to contain the search term. Always verify via SQL with the directory path filter.

## Topological Linking

The note must integrate into the vault graph, see `./references/vault-graph.md`

In addition to the structured `topics` array in the frontmatter, the body or footer of the note must contain an explicit inline wiki-link to the same MoC or topics. The frontmatter enables querying; the inline link establishes the graph edge required for traversal.

## Bookmark Back-Linking

After creating a zettel for a tool, concept, or entity, check for existing bookmark notes in the same area that match the topic. If a match exists, add a backlink entry (`See also: [[zettel-name]]`) to that bookmark note. This keeps bookmarks current and creates a bidirectional graph edge between the zettel (deep knowledge) and the bookmark note (curated overview).

**Example:** A zettel about a tool in an area may get a backlink from that area's matching tools bookmark note when the bookmark note is the user's curated overview and the zettel is the deeper note.

**When to skip:** The bookmark note already covers the topic with sufficient depth directly, the zettel is only tangentially related, or adding the backlink would be a noisy side effect unrelated to the user's request.

## Request Triage

- A request like "where do I already have notes about X" → no new file; read and answer (prefer TurboVault search over `ls` / `grep -rli`).
- A bare URL list or "add this to <note>" → an entry in an existing `*-bookmarks.md`, not a new note.
- Unresolvable designation in the request: pick the most plausible referent **from the source**, disclose the interpretation in the answer ("X — I read that as the repo from your link"), and create the note; don't block with a question, don't silently guess.

## Source-to-Note Rules

- External source → `type: zettel` with `source:` in the frontmatter, never `article`; a bookmarks entry is no substitute for a zettel.
- Frontmatter dates come from the `date` command, never from session context — a rebuilt context can be days old.
- From ~10–15 KB an entity note gets unwieldy (several main sections spanning the thing + ecosystem + prices) → split the research part into its own note (e.g. `<thing>-runtime.md`, `<topic>-tools.md`) and offer the split; one entity note per thing, several links → one MoC edit.
