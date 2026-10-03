# Bookmarks Bridge (Wiki ↔ Area Layer)

**→ Trigger:** After ingesting a source into a domain wiki, the user says "add the link to <topic> bookmarks" or "add this to my X bookmarks".

Find the existing `area/<topic>/<topic>-bookmarks.md` and add the wiki source as a curated entry that cross-links back to the wiki layer. It does NOT mean: create a new bookmarks file, add to a `wiki/...` bookmarks file (wrong layer — wiki is agent-curated, area is user-curated), or add an entry without a cross-link.

## Workflow

1. **Find the target file:** search `area/` for an existing `area/<topic>/<topic>-bookmarks.md` matching the topic. Don't create a new one when a match exists; ask the user when none matches.
2. **Confirm the entry schema** by reading the file — one bullet per property:
   ```
   ### {title}
   - description: {one sentence to one paragraph}
   - Link: {primary URL}
   - Repo: {GitHub URL if applicable}
   - Date: {YYYY-MM-DD added}
   ```
   Extra properties (License, Platform, Use case, ...) are used as-needed. Add a new `## {Category}` section when the resource starts a new category.
3. **Cross-link back to the wiki layer (the bridge):**
   ```
   - Wiki source: [[wiki/<wiki>/raw/articles/<ingest-slug>]]
   - Wiki entity: [[wiki/<wiki>/entities/<entity-slug>]]
   ```
4. **Bump frontmatter `updated:`** to today's date; leave `created`, `tags`, `topics`, `description` unchanged.
5. **Additive only** — never reformat existing entries; they are user-curated.

**Layer check:** "bookmarks" → search `area/`, not `wiki/`; "concept"/"entity" → wiki layer.

## Promotion (Area → Wiki) Is Manual

A bookmark entry is not an auto-ingest candidate. Promoting an entry to a wiki note is a two-step, user-gated process: the user reviews the entry and decides it is worth a note; only then is it ingested via the wiki workflow. Never ingest from a bookmarks file unprompted.
