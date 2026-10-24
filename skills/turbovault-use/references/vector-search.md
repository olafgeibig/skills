# Vector Search (`vector_search` plugin)

Semantic retrieval on top of the lexical tools. It is an **opt-in, compiled-in plugin**, never a runtime install: a binary built without the `vector-search` Cargo feature has no dependency, no tool and no code path for it. Treat it as absent in any session where `vector_search_status` is not in the tool list rather than concluding the vault or the server is broken.

## Check what the binary can do before believing a note

Three probes, cheapest first:

```bash
turbovault --version
turbovault --help | grep -- --plugins          # flag exists → the feature set includes plugins
strings "$(command -v turbovault)" | grep -c vector_search   # >0 → plugin compiled into this binary
```

`cargo install turbovault` alone is stdio-only without the plugin; the published release archives carry every feature. A note or README claiming vector search "is available" describes the project, not the installed binary.

## Enable

Add the plugin to the server invocation — either on the command line or in the client's MCP block:

```bash
--plugins vector_search        # env: TURBOVAULT_PLUGINS
```

Nothing is enabled by default, so a binary built with every plugin behaves like one built with none until a plugin is named. After a restart the three tools appear namespaced: `vector_search_search`, `vector_search_reindex`, `vector_search_status`.

## Model: local directory, never a download

The engine is built `local-only`, so it cannot reach the network even if a model id is passed. `model_path` must point at a directory on disk holding a Model2Vec/Potion model:

```
<model-dir>/
  tokenizer.json
  model.safetensors
  config.json
```

Any model in the [Model2Vec library](https://huggingface.co/models?library=model2vec) qualifies: the format is a static-embedding distillation of a sentence-transformer, so the loader is identical. Dimensions come from each model's own `config.json` (`hidden_dim`) — the plugin README's flat "256-dim" is wrong for part of the family, so read the config rather than repeating the doc:

| Model | Dim | Notes |
|---|---|---|
| `minishlab/potion-base-2M` | 64 | smallest / fastest |
| `minishlab/potion-base-4M` | 128 | |
| `minishlab/potion-base-8M` | 256 | documented default, best size/quality balance |
| `minishlab/potion-retrieval-32M` | 512 | retrieval-tuned, larger |
| `minishlab/potion-multilingual-128M` | 256 | multilingual vaults |
| `minishlab/potion-science-8M` / `potion-science-32M` | 256 | science corpora |

Fetch the repository files, keep the three together, and use an absolute path. Two cheap checks before promising a model works: `curl -s https://huggingface.co/api/models/<id>` for the file list (a repo shipping `embeddings.safetensors` or a bare torch checkpoint instead of `model.safetensors` needs conversion; the loader also accepts the sentence-transformers layout with a `0_StaticEmbedding/` subfolder), and `curl -sL https://huggingface.co/<id>/raw/main/config.json` for the dimension. Changing the model changes the dimension and therefore requires `vector_search_reindex`. Embeddings are static lookup-table means, so encoding is CPU-cheap and needs no model server. Report "not configured" as a configuration gap with the missing `model_path`, never as a broken feature.

## Config file

`<vault>/.turbovault/plugins/vector_search/config.json` — per vault, inside the vault, next to the index. Omitted keys keep their defaults; an empty `model_path` means "not configured" rather than an error at startup.

| Key | Default | Effect |
|---|---|---|
| `model_path` | — | Absolute path to the model directory |
| `chunk_max_chars` | 800 | Chunk size before embedding |
| `chunk_overlap_chars` | 100 | Trailing context carried into the next chunk |
| `lexical_weight` | 0.4 | BM25 share of the fusion; dense gets `1 − weight` |
| `rrf_k` | 60 | Reciprocal Rank Fusion constant |
| `search_overfetch_factor` | 5 | Candidates pulled per side before fusing |
| `min_similarity` | 0.2 | Minimum cosine similarity for a dense hit |
| `ann_max_nb_connection` / `ann_ef_construction` / `ann_ef_search` | 16 / 200 / 64 | HNSW degree, build quality, query recall |

`vector_search_status` resolves and returns this configuration without loading the model — call it first when diagnosing, instead of reading the JSON and guessing which defaults apply.

## Index

- Persisted under `.turbovault/plugins/vector_search/` — one JSON file per note plus a metadata key for the chunk-id high-water mark. It lives inside the vault but never appears as notes, because TurboVault always excludes its own `.turbovault/` from the note tools.
- Incremental and chunk-hash based: an unchanged note short-circuits before chunking, an unchanged chunk reuses its stored vector. Re-embedding a long note after a paragraph edit is cheap by design.
- `vector_search_reindex` drops every chunk and the reconcile cursor and rebuilds — the call after changing the model, or when the snapshot is no longer trusted.
- Because the state directory is outside the note tools, writing `config.json` there is a legitimate **filesystem** write (`write_file`/`terminal`), not a bypass of the guarded write path. This is the one exception to "all vault writes go through TurboVault": `.turbovault/` is server state, not notes. The audit trail, plugin storage and the vector index all sit there.

## Tools

| Tool | Arguments | Behaviour |
|---|---|---|
| `vector_search_search` | `query`, `limit` (10, max 100), `hybrid` (true) | Reconciles first, then searches; `hybrid: false` for dense-only |
| `vector_search_reindex` | — | Full re-embed after dropping every chunk and the cursor |
| `vector_search_status` | — | Model, dimensions, indexed note/chunk counts, resolved config |

## Limits that change the recommendation

- **One engine per process, bound to the vault that was active when it was first built.** After an active-vault switch every call returns an `unavailable` error instead of silently searching another vault's index. In a multi-vault setup with a default vault that is not the intended one, state this before promising semantic search — the fix is process/vault ordering, not a retry.
- Deletions become skipped tombstones in the HNSW graph, with a rebuild once they pass a quarter of it; below 4096 vectors search is an exact linear scan, so absence of an HNSW graph on a small vault is not a defect.
- It does not replace `search` (Tantivy BM25) or `find_similar` (TF-IDF). Describe it as the dense side fused on top, and keep the lexical tools in the recommendation.
