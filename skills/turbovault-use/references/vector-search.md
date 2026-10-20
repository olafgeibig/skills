# TurboVault vector search plugin (`vector_search`)

Optional hybrid index over the active vault: dense vectors (Model2Vec static embeddings)
fused with BM25 by Reciprocal Rank Fusion. Separate from the core `search` (Tantivy) and
from `find_similar` (TF-IDF): it answers "which note is *about* this", including wording the
note never uses, and it is off by default.

## Enable it

1. The binary must be built with the `vector-search` feature. Release archives and the
   Docker image carry every feature; a `cargo` build needs `--features vector-search`.
2. Name the plugin — a full-featured binary behaves like a bare one until then:
   `--plugins vector_search` or `TURBOVAULT_PLUGINS=vector_search`.
3. Three tools appear: `vector_search_search` (`query`, `limit` ≤ 100, `hybrid` default true),
   `vector_search_reindex`, `vector_search_status`.
4. In Hermes the server is started from `mcp_servers.turbovault.args`. Add the flag with
   `hermes config set mcp_servers.turbovault.args '[...]'` (the tool refuses this file directly).
   The running session keeps its old tool list: verify with `hermes mcp test turbovault`, and
   the tools become callable only after the MCP server/session restarts.

## Configure the model

Write `<vault>/.turbovault/plugins/vector_search/config.json` — omitted fields keep defaults:

```json
{"model_path": "/home/olaf/.local/share/turbovault-models/potion-multilingual-128M",
 "chunk_max_chars": 800, "chunk_overlap_chars": 100, "lexical_weight": 0.4}
```

Defaults: `chunk_max_chars` 800, `chunk_overlap_chars` 100, `rrf_k` 60, `lexical_weight` 0.4,
`search_overfetch_factor` 5, `min_similarity` 0.2, `ann_max_nb_connection` 16,
`ann_ef_construction` 200, `ann_ef_search` 64.

`model_path` has no default and the crate cannot download one (built `local-only`): point it at
a local directory containing `tokenizer.json`, `model.safetensors` and `config.json`. Fetch those
files straight from the Hub (`https://huggingface.co/<id>/resolve/main/<file>`); the directory
needs no Python tooling at run time.

| Model | Dims | Weights | Dir | German |
|---|---|---|---|---|
| `minishlab/potion-base-2M` | 64 | 7.6 MB | 16 MB | no |
| `minishlab/potion-base-4M` | 128 | 15 MB | 31 MB | no |
| `minishlab/potion-base-8M` | 256 | 30 MB | 30 MB | no |
| `minishlab/potion-base-32M` | 512 | 129 MB | 260 MB | no |
| `minishlab/potion-retrieval-32M` | 512 | 129 MB | 260 MB | no (retrieval-tuned) |
| `minishlab/potion-multilingual-128M` | 256 | 512 MB | 1.05 GB | yes (101 languages) |

Any Model2Vec-compatible model works, including one distilled from a German sentence
Transformer with the `model2vec` Python package (`pip install model2vec[distillation]`); a
distilled 8–32M table keeps the RAM of the small Potion models while fixing the language gap.

Measured on a Pi 5 (4 cores, 8 GB), 999 notes / 20,759 chunks:

| | potion-base-8M | potion-multilingual-128M |
|---|---|---|
| Process RSS after first search | 232 MB | 1,236 MB |
| Index dir (one JSON per note) | 75 MB | 75 MB |
| Full `reindex` | — | 22 s |
| Warm query (hybrid / dense) | 8–19 ms | 8–15 ms |
| First search after process start | ~21 s | ~21 s |

Embedding is CPU-only (tokenize + lookup + mean-pool, no transformer pass), so a GPU is
irrelevant. The first search in a process rebuilds the engine from the JSON snapshots; after
that queries are single-digit milliseconds.

Quality check that matters for a German vault: with `hybrid: false` on `potion-base-8M` every
German query returned scores flat at ~0.70 in unrelated notes — the dense side is noise, and
hybrid results are then just BM25 plus noise. `potion-multilingual-128M` spreads scores over
~0.30–0.66 and returns topically related notes, though exact-wording queries are still served
better by the core `search`.

## Pitfalls

- **One engine per process, bound to the vault that was active at first build.** A later vault
  switch returns `unavailable`. `is_default: true` in the config does not decide it either: the
  per-project cache (`~/.cache/turbovault/projects/<hash>`) restores its own active vault, so a
  probe with a temporary `--config` can silently index the real vault.
- **Storage keys max out at 200 bytes.** A note whose vault-relative path is ~185+ bytes makes
  `vector_search_reindex` fail outright with `storage key is <n> bytes; the maximum is 200`, and
  the incremental reconcile only skips it with a WARN. Shorten long clipping titles before the
  first reindex (rename through `move_note`, check `get_links` for inbound links first).
- **`reindex` drops every snapshot before it re-walks**, so an abort leaves a partial index.
  Finish it with another `reindex`, or let the next search reconcile incrementally.
- Non-UTF-8 files (macOS `._name.md`) are skipped; a 1,000-note vault indexes 999.
- Scores are RRF values (`weight / (k + rank)`, max ≈ 0.0164 with `rrf_k` 60), not cosine
  similarities — do not read them as confidence. One hit per note (best chunk) is returned.
- Persistence is one JSON file per note plus `meta.json` (model, dims, chunk-id high-water mark)
  under `.turbovault/plugins/vector_search/`; changing the model re-embeds everything.
- The plugin's snapshot directory lives inside the vault. On a Git-backed vault it is inside
  `.turbovault/`, which TurboVault always protects; otherwise keep it out of sync/backup noise.
