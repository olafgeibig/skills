# Search and Graph Operations

## Choose the right search

- `search` is full-text search and also carries the 3.x `advanced_search` filters (`tags`, `frontmatter_filters`, `exclude_paths`, `related_to`).
- `find_similar` finds conceptually similar content.
- `search` with `frontmatter_filters` filters metadata fields.
- `query_frontmatter_sql` supports structured reports.
- `get_notes_info` retrieves selected frontmatter fields for one or more notes.

Do not send `field:value` expressions such as `type: analysis` to full-text search. Use frontmatter search or SQL.

Full-text and semantic searches can cover the entire active vault. Constrain results with path filters where supported or verify every result path before using it.

## Vector Search plugin

The optional `vector_search` plugin is separate from the built-in TF-IDF `find_similar`; its tools use the `vector_search_` prefix. It requires a local Potion/Model2Vec-compatible model directory; TurboVault does not download the model. The plugin maintains a local index and has one engine per server process, bound to the vault active when first built. Switching the active vault afterwards can make its tools return `unavailable`. Do not assume it supports a dynamic multi-vault process.

`vector_search_reindex` drops and rebuilds the plugin index; it does not rewrite notes, but it can be expensive. Use it only when changing models or intentionally recovering an untrusted index.

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

## Bare-name vs path wikilinks

Obsidian resolves `[[other-note]]` (bare name) fine, but TurboVault graph tools may not see the edge: `get_links`/`get_links(direction="outgoing")` can miss a bare link where the path form `[[area/dir/note|Alias]]` is seen. Use the path form wherever the edge must count (MoC ↔ note, cross-area references); frontmatter `topics:` never creates an edge (YAML string — expected, not a bug). Detection: after creating or linking a note, run `get_links(direction="outgoing")` on the source — if the target is absent, convert to path form and re-check.

**Index lag:** after a mass conversion, per-note queries update at once while aggregate counters (`vault_health()` totals) still show old values — verify per note, not by aggregate.

**Mass conversion recipe:** (1) dry-run inventory classifying bare links as same-dir / unique-basename / ambiguous / unresolved; (2) back up; (3) apply with the same resolution logic, skipping fenced code blocks and frontmatter; (4) cleanup (strip stray `.md` suffixes, restore frontmatter from the backup); (5) verify per note. Conversion only makes edges graph-visible — it does not lower broken-link counts. Work the link classes in order: (1) bare→path, (2) missing `wiki/` prefix in wiki files, (3) case mismatch, (4) relative path without folder prefix, (5) dead frontmatter `topics` targets — rewrite to the correct bare name, not a path, (6) genuine missing targets and doc placeholders — leave them and report. **Parser trap:** in tables `\|` is a correct escaped pipe — a naive split at the first `|` reports the link as broken; split on `\\?\|` and strip the trailing `\`.

## Verification

After search:

- confirm candidate paths fall inside the intended scope;
- read selected notes before drawing conclusions;
- distinguish indexed text from frontmatter and graph relationships;
- report truncation or result limits rather than implying complete coverage.
