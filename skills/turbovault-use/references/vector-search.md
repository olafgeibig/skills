# Vector Search (`vector_search` plugin)

Semantic retrieval on top of the lexical tools: dense vectors (Model2Vec static embeddings)
fused with BM25 by Reciprocal Rank Fusion. It answers "which note is *about* this", including
wording a note never uses — and it is an **opt-in, compiled-in plugin**, never a runtime
install: a binary built without the `vector-search` Cargo feature has no dependency, no tool
and no code path for it. Treat it as absent in any session where `vector_search_status` is not
in the tool list rather than concluding the vault or the server is broken.

## Check what the binary can do before believing a note

Three probes, cheapest first:

```bash
turbovault --version
turbovault --help | grep -- --plugins          # flag exists → the feature set includes plugins
strings "$(command -v turbovault)" | grep -c vector_search   # >0 → plugin compiled into this binary
```

`cargo install turbovault` alone is stdio-only without the plugin; the published release
archives carry every feature. A note or README claiming vector search "is available" describes
the project, not the installed binary.

## Enable it

1. Name the plugin — a full-featured binary behaves like a bare one until then:

   ```bash
   --plugins vector_search        # env: TURBOVAULT_PLUGINS
   ```

2. Three tools appear namespaced: `vector_search_search` (`query`, `limit` ≤ 100, `hybrid`
   default true), `vector_search_reindex`, `vector_search_status`.
3. In Hermes the server is started from `mcp_servers.turbovault.args`. Add the flag with
   `hermes config set mcp_servers.turbovault.args '[...]'` (the tool refuses this file
   directly). The running session keeps its old tool list: verify with
   `hermes mcp test turbovault`, and the tools become callable only after the MCP
   server/session restarts.

## Model: a local directory, never a download

The engine is built `local-only`, so it cannot reach the network even if a model id is passed.
`model_path` must point at a directory on disk holding a Model2Vec/Potion model:

```
<model-dir>/
  tokenizer.json
  model.safetensors
  config.json
```

`model_path` has no default and the crate cannot download one. Fetch the three files straight
from the Hub (`https://huggingface.co/<id>/resolve/main/<file>`) and use an absolute path; the
directory needs no Python tooling at run time.

Any [Model2Vec](https://huggingface.co/models?library=model2vec) model qualifies — the format
is a static-embedding distillation of a sentence-transformer, so the loader is identical.
Dimensions come from each model's own `config.json` (`hidden_dim`); the plugin README's flat
"256-dim" is wrong for part of the family, so read the config rather than repeating the doc.

| Model | Dim | Weights | Dir | German |
|---|---|---|---|---|
| `minishlab/potion-base-2M` | 64 | 7.6 MB | 16 MB | no |
| `minishlab/potion-base-4M` | 128 | 15 MB | 31 MB | no |
| `minishlab/potion-base-8M` | 256 | 30 MB | 30 MB | no |
| `minishlab/potion-base-32M` | 512 | 129 MB | 260 MB | no |
| `minishlab/potion-retrieval-32M` | 512 | 129 MB | 260 MB | no (retrieval-tuned) |
| `minishlab/potion-multilingual-128M` | 256 | 512 MB | 1.05 GB | yes (101 languages) |
| `minishlab/potion-science-8M` / `-32M` | 256 | — | — | science corpora |

Two cheap checks before promising a model works: `curl -s https://huggingface.co/api/models/<id>`
for the file list (a repo shipping `embeddings.safetensors` or a bare torch checkpoint instead
of `model.safetensors` needs conversion; the loader also accepts the sentence-transformers
layout with a `0_StaticEmbedding/` subfolder), and
`curl -sL https://huggingface.co/<id>/raw/main/config.json` for the dimension.

Any Model2Vec-compatible model works, including one distilled from a German sentence
Transformer with the `model2vec` Python package (`pip install model2vec[distillation]`); a
distilled 8–32M table keeps the RAM of the small Potion models while fixing the language gap.
Embeddings are static lookup-table means, so encoding is CPU-cheap, needs no model server and
a GPU is irrelevant. Report "not configured" as a configuration gap with the missing
`model_path`, never as a broken feature.

## Configure it

Write `<vault>/.turbovault/plugins/vector_search/config.json` — omitted fields keep defaults:

```json
{"model_path": "/abs/path/to/potion-multilingual-128M",
 "chunk_max_chars": 800, "chunk_overlap_chars": 100, "lexical_weight": 0.4}
```

| Field | Default | Meaning |
|---|---|---|
| `chunk_max_chars` / `chunk_overlap_chars` | 800 / 100 | Chunking of long notes |
| `lexical_weight` | 0.4 | BM25 share in the RRF fusion |
| `rrf_k` | 60 | Reciprocal Rank Fusion constant |
| `search_overfetch_factor` | 5 | Candidates pulled per side before fusing |
| `min_similarity` | 0.2 | Minimum cosine similarity for a dense hit |
| `ann_max_nb_connection` / `ann_ef_construction` / `ann_ef_search` | 16 / 200 / 64 | HNSW degree, build quality, query recall |

`vector_search_status` resolves and returns this configuration without loading the model —
call it first when diagnosing, instead of reading the JSON and guessing which defaults apply.

## Measured on a Pi 5 (4 cores, 8 GB), 999 notes / 20,759 chunks

| | potion-base-8M | potion-multilingual-128M |
|---|---|---|
| Process RSS after first search | 232 MB | 1,236 MB |
| Index dir (one JSON per note) | 75 MB | 75 MB |
| Full `reindex` | — | 22 s |
| Warm query (hybrid / dense) | 8–19 ms | 8–15 ms |
| First search after process start | ~21 s | ~21 s |

The first search in a process rebuilds the engine from the JSON snapshots; after that queries
are single-digit milliseconds.

Quality check that matters for a German vault: with `hybrid: false` on `potion-base-8M` every
German query returned scores flat at ~0.70 in unrelated notes — the dense side is noise, and
hybrid results are then just BM25 plus noise. `potion-multilingual-128M` spreads scores over
~0.30–0.66 and returns topically related notes, though exact-wording queries are still served
better by the core `search`.

## Shrink a multilingual model: prune the vocabulary

The 512 MB of `potion-multilingual-128M` is almost entirely vocabulary — 500,353 Unigram
tokens x 256 dims x 4 bytes — and a German+English vault touches only ~29k of them.
`scripts/prune-model2vec-vocab.py` keeps every token the corpus uses, pads to a target with the
highest-scoring Latin-script tokens and slices the embedding table. Pure Python (tokenizers,
safetensors, numpy — no torch):

```bash
python3 -m venv m2v && m2v/bin/pip install tokenizers safetensors numpy
m2v/bin/python scripts/prune-model2vec-vocab.py \
  --source ~/.local/share/turbovault-models/potion-multilingual-128M \
  --out ~/.local/share/turbovault-models/potion-multilingual-45k \
  --target 45000 --corpus '~/vaults/akademeia/**/*.md'
```

Measured on that vault (999 notes / 20,759 chunks):

| | multilingual-128M | pruned to 45k |
|---|---|---|
| model directory | 513 MB | 47 MB |
| process RSS (start / after first search) | 1,164 / 1,225 MB | 211 / 273 MB |
| full `reindex` | 22.2 s | 21.6 s |
| German query results | reference | same paths, same dense scores |

Embedding drift: cosine 1.0000 between original and pruned over Latin-script sentences (rare
German compounds and made-up words included), 0.93 for a rare English word whose subword piece
fell out of the target, ~0 for Cyrillic/CJK, which become `[UNK]`. Re-prune with a higher
`--target` if the vault starts holding notes in other scripts. Switching `model_path` requires
`vector_search_reindex` because the token ids change.

## Index

- Persisted under `.turbovault/plugins/vector_search/` — one JSON file per note plus `meta.json`
  (model, dims, chunk-id high-water mark). It lives inside the vault but never appears as
  notes, because TurboVault always excludes its own `.turbovault/` from the note tools.
- Incremental and chunk-hash based: an unchanged note short-circuits before chunking, an
  unchanged chunk reuses its stored vector. Re-embedding a long note after a paragraph edit is
  cheap by design.
- `vector_search_reindex` drops every chunk and the reconcile cursor and rebuilds — the call
  after changing the model, or when the snapshot is no longer trusted.
- Because the state directory is outside the note tools, writing `config.json` there is a
  legitimate **filesystem** write (`write_file`/`terminal`), not a bypass of the guarded write
  path. This is the one exception to "all vault writes go through TurboVault": `.turbovault/`
  is server state, not notes. The audit trail, plugin storage and the vector index all sit there.

## Tools

| Tool | Arguments | Behaviour |
|---|---|---|
| `vector_search_search` | `query`, `limit` (10, max 100), `hybrid` (true) | Reconciles first, then searches; `hybrid: false` for dense-only |
| `vector_search_reindex` | — | Full re-embed after dropping every chunk and the cursor |
| `vector_search_status` | — | Model, dimensions, indexed note/chunk counts, resolved config |

## Pitfalls

- **One engine per process, bound to the vault that was active when it was first built.** A
  later vault switch returns `unavailable` instead of silently searching another vault's index.
  `is_default: true` in the config does not decide it either: the per-project cache
  (`~/.cache/turbovault/projects/<hash>`) restores its own active vault, so a probe with a
  temporary `--config` can silently index the real vault. In a multi-vault setup the fix is
  process/vault ordering, not a retry.
- **Storage keys max out at 200 bytes.** A note whose vault-relative path is ~185+ bytes makes
  `vector_search_reindex` fail outright with `storage key is <n> bytes; the maximum is 200`,
  and the incremental reconcile only skips it with a WARN. Shorten long clipping titles before
  the first reindex (rename through `move_note`, check `get_links` for inbound links first).
- **`reindex` drops every snapshot before it re-walks**, so an abort leaves a partial index.
  Finish it with another `reindex`, or let the next search reconcile incrementally.
- Non-UTF-8 files (macOS `._name.md`) are skipped; a 1,000-note vault indexes 999.
- Scores are RRF values (`weight / (k + rank)`, max ≈ 0.0164 with `rrf_k` 60), not cosine
  similarities — do not read them as confidence. One hit per note (best chunk) is returned.
- Deletions become skipped tombstones in the HNSW graph, with a rebuild once they pass a quarter
  of it; below 4096 vectors search is an exact linear scan, so absence of an HNSW graph on a
  small vault is not a defect.
- It does not replace `search` (Tantivy BM25) or `find_similar` (TF-IDF). Describe it as the
  dense side fused on top, and keep the lexical tools in the recommendation.

## See also

- `references/upgrading.md`, `references/vault-configuration.md` — server config and plugin
  enablement outside Hermes
- `references/audit-and-drift.md` — what TurboVault did *not* record
