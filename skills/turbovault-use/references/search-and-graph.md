# Search and Graph Operations

## Choose the right search

- `search` and the query portion of `advanced_search` are full-text search.
- `semantic_search` finds conceptually similar content.
- `search_by_frontmatter` filters one metadata field.
- `query_frontmatter_sql` supports structured reports.
- `get_metadata_value` retrieves one field from one note.

Do not send `field:value` expressions such as `type: analysis` to full-text search. Use frontmatter search or SQL.

Full-text and semantic searches can cover the entire active vault. Constrain results with path filters where supported or verify every result path before using it.

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
| Notes linking to a target | `get_backlinks` |
| Links leaving a note | `get_forward_links` |
| Nearby graph context | `get_related_notes` |
| Broken targets | `get_broken_links` |
| Notes with inbound but no outbound links | `get_dead_end_notes` |
| Disconnected groups | `get_isolated_clusters` |
| Circular chains | `detect_cycles` |
| Central notes | `get_hub_notes`, `get_centrality_ranking` |
| Similarity suggestions | `find_similar_notes`, `recommend_related`, `suggest_links` |

Start routine navigation with forward links, backlinks, or one-hop related notes. Use centrality, cluster, cycle, and similarity operations for audits or explicit analysis. Cost-bearing inference tools should not replace deterministic graph traversal.

## Verification

After search:

- confirm candidate paths fall inside the intended scope;
- read selected notes before drawing conclusions;
- distinguish indexed text from frontmatter and graph relationships;
- report truncation or result limits rather than implying complete coverage.
