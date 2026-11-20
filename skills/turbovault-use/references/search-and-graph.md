# Search and Graph Operations

## Choose the right search

- `search` is full-text search and also carries the 3.x `advanced_search` filters (`tags`, `frontmatter_filters`, `exclude_paths`, `related_to`).
- `find_similar` finds conceptually similar content.
- `search` with `frontmatter_filters` filters metadata fields.
- `query_frontmatter_sql` supports structured reports.
- `get_notes_info` retrieves selected frontmatter fields for one or more notes; with `include_tags` its `tags` is an object (`frontmatter_tags`, `inline_tags`, `all_tags`).
- Obsidian Bases (`query_base`), canvases (`read_canvas`/`write_canvas`), and periodic notes (`get_periodic_note`) exist on 4.0; use them only when the vault actually has `.base`/`.canvas` files or daily-note settings.

For broad discovery, pass `response_format: concise` to `search` (compact rows: `path`, `title`, `snippet`, `score`, `tags`, `backlink_count`, without `preview`, `outgoing_links`, `word_count`) or to `explain_vault`/`get_vault_context`.

Do not send `field:value` expressions such as `type: analysis` to full-text search. Use frontmatter search or SQL.

**Retrieval is not enumeration.** When the answer must be complete — every note of a type, a naming survey, a rollout view — use `query_frontmatter_sql` (`SELECT path FROM files WHERE …`) and reconcile the row count against a known total (e.g. `get_vault_context` type counts) before claiming coverage. With `search` + `frontmatter_filters`, omit `query` entirely for filter-only listing: a `"*"` query beside the filters returns a small arbitrary subset instead of every match.

Full-text and semantic searches can cover the entire active vault. Constrain results with path filters where supported or verify every result path before using it.

List results page at 50 by default (`limit`/`offset` and `meta.pagination.next_offset`); a vault-wide count needs the loop, not the first page.

## Vector Search plugin

The optional `vector_search` plugin is separate from the built-in TF-IDF `find_similar`; its tools use the `vector_search_` prefix. It requires a local Potion/Model2Vec-compatible model directory; TurboVault does not download the model. The plugin maintains a local index and has one engine per server process, bound to the vault active when first built. Switching the active vault afterwards can make its tools return `unavailable`. Do not assume it supports a dynamic multi-vault process.

`vector_search_reindex` drops and rebuilds the plugin index; it does not rewrite notes, but it can be expensive. Use it only when changing models or intentionally recovering an untrusted index.

## Tasks

`query_tasks` parses markdown checkboxes across the vault — the only tool that reads Tasks-plugin emoji (📅 due, ⏳ scheduled, 🛫 start, ✅ done, 🔺⏫🔼🔽⏬ priority) and Dataview fields (`[due:: 2026-10-20]`). Filters: `status` (`todo`, `done`, `in_progress`, `cancelled`, `other`), `due_before`/`due_after`, `scheduled_before`/`scheduled_after`, `tag`, `path`, `priority` (`highest`, `high`, `medium`, `normal`, `low`, `lowest`), `text`. Each result carries `path`, `line`, `status`, `status_char`, `text`, `priority`, `due`/`scheduled`/`done`, `tags`; results sort by due date, then priority, then note and line.

The parser reads the checkbox character only: `[ ]` → `todo`, `[x]`/`[X]` → `done`, `[/]` → `in_progress`, `[-]` → `cancelled`. A `[?]` checkbox is not parsed at all — those tasks stay invisible to `query_tasks` and need the regex fallback in `vault-ops` task management. Do not rebuild any of this with regex over `search` output.

## SQL limits

TurboVault's frontmatter query interface is not unrestricted SQLite. Prefer simple queries and inspect the available schema first.

Reliable pattern:

```sql
SELECT path, type, description
FROM files
WHERE type = 'moc'
ORDER BY path
LIMIT 50
```

Do not assume multi-table `json_each()` joins or `LIKE` against array-valued metadata will work. Prefer dedicated graph and metadata tools.

**Optional columns are NULL on notes that lack the key, and NULL breaks `LIKE`.** The `files` table spans every note in the vault, so a frontmatter key only some notes carry (a custom field mid-rollout) yields `value: operator doesn't exist: Null LIKE Str(...)` and aborts the whole query. Wrap the column: `WHERE coalesce(scope, '') LIKE '%x%'` (same for `lower()`). `WHERE <col> IS NOT NULL` works and lists exactly the notes that already carry an optional key — useful as a rollout/progress view.

**`LIKE` is not supported on list-valued columns** in 4.0.2 (`List(...) LIKE Str(...)`). `coalesce` does not convert lists to strings. Use `search(frontmatter_filters=[{key, value}])` to find substring candidates; then inspect the actual frontmatter list and verify exact membership. For complete results, page and reconcile against the intended scope; enumerate notes and inspect metadata directly if the search cap prevents coverage.

**In 4.0.2, a `CASE` alias can be silently ignored in `ORDER BY`.** `SELECT path, status, (CASE status WHEN 'blocked' THEN 2 WHEN 'open' THEN 1 ELSE 0 END) AS w FROM files … ORDER BY w DESC, updated DESC` returns rows ordered by `updated DESC` alone — the alias contributes nothing, no error is raised, and the result looks plausible. Repeat the expression in `ORDER BY` (verified: the same query with the `CASE` written out sorts the blocked row to the top), and when a ranking matters, run the query once without the secondary key to confirm the first key is doing the work.

## Graph tools

| Goal | Tool |
|---|---|
| Notes linking to a target | `get_links` |
| Links leaving a note | `get_links(direction="outgoing")` |
| Nearby graph context | `get_related_notes` |
| Broken targets | `graph_report(kind="broken_links")` |
| Notes with inbound but no outbound links | `graph_report(kind="dead_ends")` |
| Disconnected groups | `graph_report(kind="isolated_clusters")` |
| Circular chains | `graph_report(kind="cycles")` |
| Central notes | `graph_report(kind="hubs")`, `graph_report(kind="centrality")` |
| Similarity suggestions | `find_similar`, `search(related_to=...)`, `suggest_links` |

Start routine navigation with forward links, backlinks, or one-hop related notes. Use centrality, cluster, cycle, and similarity operations for audits or explicit analysis. Cost-bearing inference tools should not replace deterministic graph traversal.

**The link table does not record which field a link came from.** `links.link_type` holds only `WikiLink`, `MarkdownLink` and `HeadingRef` — never `sources`, `cases` or `dossier` — so a typed expansion ("follow only `sources:`", "only this case's children") cannot be expressed as one query. List-valued frontmatter wikilinks *do* create edges, though: a note naming another only under `cases:` or `sources:` shows up in that target's `get_links`. Reverse expansion by field therefore works as `get_links(direction="incoming")` plus reading each candidate's frontmatter; forward expansion by field is read the note, then traverse or read its targets. A hub-heavy vault flattens hop distance — `get_related_notes` over two hops returns the whole project through the dossier and MoC notes — so treat hop count as navigation, never as a relevance signal.

## Bare-name vs path wikilinks

Obsidian resolves `[[other-note]]` (bare name) fine, but TurboVault graph tools may not see the edge: `get_links`/`get_links(direction="outgoing")` can miss a bare link where the path form `[[area/dir/note|Alias]]` is seen. Use the path form wherever the edge must count (MoC ↔ note, cross-area references); a resolvable wikilink in a `topics:` list can create an edge (verified for both bare and path links on 4.0.2); a plain string does not. Detection: after creating or linking a note, run `get_links(direction="outgoing")` on the source — if the target is absent, convert to path form and re-check.

**Unicode-equivalent filenames:** if a visible target exists but its edge is missing or reported broken, compare the actual filename's Unicode code points before changing the source filename. macOS filenames may use decomposed characters (NFD) while a typed wikilink uses composed characters (NFC); visually identical strings can fail graph resolution. Obtain the exact vault-relative filename from discovery (or a read-only filesystem listing when needed), preserve its Unicode spelling in a path-form wikilink, and edit only that link through TurboVault. Re-read the note, confirm the target appears in `get_links(direction="outgoing")`, and re-run `graph_report(kind="broken_links")`; do not rename a source document merely to fix a navigation edge.

**Index lag:** after a mass conversion, per-note queries update at once while aggregate counters (`vault_health()` totals) still show old values — verify per note, not by aggregate.

**Mass conversion recipe:** (1) dry-run inventory classifying bare links as same-dir / unique-basename / ambiguous / unresolved; (2) back up; (3) apply with the same resolution logic, skipping fenced code blocks and frontmatter; (4) cleanup (strip stray `.md` suffixes, restore frontmatter from the backup); (5) verify per note. Conversion only makes edges graph-visible — it does not lower broken-link counts. Work the link classes in order: (1) bare→path, (2) missing `wiki/` prefix in wiki files, (3) case mismatch, (4) relative path without folder prefix, (5) dead frontmatter `topics` targets — rewrite to the correct bare name, not a path, (6) genuine missing targets and doc placeholders — leave them and report. **Parser trap:** in tables `\|` is a correct escaped pipe — a naive split at the first `|` reports the link as broken; split on `\\?\|` and strip the trailing `\`.

## Overview and validation

`explain_vault` answers "what is in this vault and how is it wired" in one call (counts, folders, hubs, structure) — cheaper than assembling it from health and graph calls, and `response_format: concise` trims it further. `vault_health(depth="full")` stays the scored view; `validate_vault` is the content check (frontmatter that does not parse, pre-1.9 `tags`/`aliases`/`cssclasses`, broken links) and belongs before a bulk pass and after a server upgrade.

## Verification

After search:

- confirm candidate paths fall inside the intended scope;
- read selected notes before drawing conclusions;
- distinguish indexed text from frontmatter and graph relationships;
- report truncation or result limits rather than implying complete coverage.
