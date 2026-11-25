# Vector Search (`vector_search` plugin)

Complete reference and setup guide for TurboVault's opt-in `vector_search` plugin: dense Model2Vec static embeddings fused with BM25 via Reciprocal Rank Fusion (RRF).

This plugin is **compiled-in and off by default**. A binary built without `--features vector-search` has no code path for it, and even a full release binary keeps it disabled until `--plugins vector_search` is passed. It is separate from the built-in TF-IDF `find_similar` tool and does not replace `search` (Tantivy BM25). Treat it as absent whenever `vector_search_status` is not in `tools/list`.

## 1. Check binary capability first

```bash
turbovault --version
turbovault --help | grep -- --plugins
strings "$(command -v turbovault)" | grep -c vector_search
```

`--help` and embedded strings are capability hints only — not proof of activation or a loaded model. Bare `cargo install turbovault` omits the plugin; published release archives include it.

## 2. Choose and fetch a local model

The engine is built `local-only` and cannot download models at runtime. `model_path` has no default and must point to an absolute local directory containing at least `tokenizer.json`, `model.safetensors`, and `config.json` (or a `0_StaticEmbedding/` subfolder). Dimensions come from the model's `config.json` (`hidden_dim`), not README assumptions.

| Model | Dim | Weights | Dir | Languages |
|---|---|---|---|---|
| `minishlab/potion-base-8M` | 256 | 30 MB | 30 MB | English |
| `minishlab/potion-base-32M` | 512 | 129 MB | 260 MB | English |
| `minishlab/potion-retrieval-32M` | 512 | 129 MB | 260 MB | English (retrieval-tuned) |
| `minishlab/potion-multilingual-128M` | 256 | 512 MB | 1.05 GB | 101 languages (incl. German) |

Any Model2Vec-compatible model works (including custom distillations via `pip install model2vec[distillation]`). Encoding is CPU-cheap lookup-table pooling; no GPU or external model server is required.

Verify file layout and `hidden_dim` before downloading (`curl -s https://huggingface.co/api/models/<id>` and `config.json`), then fetch the model files locally:

```bash
MODEL=minishlab/potion-multilingual-128M
DEST=~/.local/share/turbovault-models/potion-multilingual-128M
mkdir -p "$DEST"
for f in config.json model.safetensors tokenizer.json tokenizer_config.json \
         special_tokens_map.json modules.json vocab.txt; do
  curl -fsSL "https://huggingface.co/$MODEL/resolve/main/$f" -o "$DEST/$f"
done
```

### Optional: shrink a multilingual model by vocabulary pruning

When RSS is the binding constraint on a bilingual/Latin-script vault, prune before the first index build using `scripts/prune-model2vec-vocab.py` (pure Python: `tokenizers`, `safetensors`, `numpy`; no PyTorch):

```bash
python3 -m venv m2v && m2v/bin/pip install tokenizers safetensors numpy
m2v/bin/python scripts/prune-model2vec-vocab.py \
  --source ~/.local/share/turbovault-models/potion-multilingual-128M \
  --out ~/.local/share/turbovault-models/potion-multilingual-45k \
  --target 45000 --corpus '~/vaults/<name>/**/*.md'
```

- Pruning removes token entries (not notes) and can drop non-Latin scripts or unseen future query terms. Include representative texts and queries in every target language, and compare against lexical/unpruned baselines.
- Switching `model_path` or tokenizer requires `vector_search_reindex` even if `hidden_dim` is unchanged, because token IDs and embedding spaces differ.

## 3. Configure per vault and wire into Hermes

Write `<vault>/.turbovault/plugins/vector_search/config.json` via filesystem tools (`write_file` — `.turbovault/` is server state outside TurboVault's note tools):

```json
{
  "model_path": "/abs/path/to/model-dir",
  "chunk_max_chars": 800,
  "chunk_overlap_chars": 100,
  "lexical_weight": 0.4
}
```

Use an absolute path in `model_path` (do not rely on `~` expansion). Optional tuning defaults: `chunk_max_chars` (800), `chunk_overlap_chars` (100), `lexical_weight` (0.4), `rrf_k` (60), `search_overfetch_factor` (5), `min_similarity` (0.2), `ann_max_nb_connection` (16), `ann_ef_construction` (200), `ann_ef_search` (64).

Enable the plugin in Hermes `mcp_servers.turbovault.args` alongside the baseline flags (`references/wf-turbovault-config.md` §2):

```bash
hermes config set mcp_servers.turbovault.args \
  '["-p","production","--config","/abs/path/to/turbovault.yaml","--plugins","vector_search"]'
hermes config get mcp_servers.turbovault
```

Diff running process args (`ps -eo pid,ppid,etime,args | grep '[t]urbovault'`) before reloading the owning connection (`references/wf-upgrading.md` §6), because a reload replaces the entire `args` list and affects only the reloaded service.

## 4. Tools and index behavior

| Tool | Arguments | Behavior |
|---|---|---|
| `vector_search_status` | — | Resolves and reports config (`model_path`, `dims`, note/chunk counts) **without** loading the model. Call this first when diagnosing. |
| `vector_search_search` | `query`, `limit` (default 10, max 100), `hybrid` (default `true`) | Reconciles incrementally, then runs hybrid RRF (or dense-only with `hybrid: false`). Returns one best-chunk hit per note. |
| `vector_search_reindex` | — | Drops all snapshots and cursor, then re-embeds every note. Use only after model changes or an untrusted index. |

- Index state lives under `<vault>/.turbovault/plugins/vector_search/` (one JSON snapshot per note plus `meta.json`).
- Incremental indexing hashes notes and chunks: unchanged notes short-circuit, unchanged chunks reuse stored vectors.

## 5. Verification, bounded single-vault pilot, and transferred setups

Verify enablement in three steps:

1. `vector_search_status` → `configured: true`, expected `model_path` and `dims`. (`configured: false` is a missing-config gap, not a broken server.)
2. `vector_search_search(query: "<vault-language query>", limit: 5)` → confirm at least one relevant hit has `dense_rank` set with `lexical_rank: null` (proves the dense side contributes).
3. After a normal note write, confirm `vector_search_status` reflects the updated count incrementally.

When evaluating a pilot or adapting a model/setup from another machine:

- Confirm the destination machine's memory budget, exact MCP process, and single target vault before downloading or editing config. Leave other profiles untouched.
- Budget one loaded model per process that actually initializes an engine (`vector_search_status` alone does not load the model; sharing files on disk does not imply shared RAM). Treat source-machine RSS and query quality as estimates, never local guarantees.
- Measure baseline RSS, cold-search / post-reindex RSS, indexing time, and lexical vs. hybrid quality on representative queries in every vault language; keep all corpus text local. Do not report config or status success as a completed retrieval evaluation.

## 6. Pitfalls & rollback

- **One engine per server process, bound to whichever vault was active on first build:** Switching `active_vault` afterwards returns `unavailable`. Do not enable `--plugins vector_search` on dynamic multi-vault servers. Because project-cache recovery can override `is_default`, isolate `XDG_CACHE_HOME` during probes (`references/vault-configuration.md` §2).
- **200-byte storage key limit:** Vault-relative paths longer than ~185 bytes make `vector_search_reindex` fail (`storage key is <n> bytes; the maximum is 200`), while incremental reconcile skips them with a warning. Shorten overly long filenames via `move_note` before reindexing.
- **Aborted `reindex` leaves a partial index:** Recover by re-running `vector_search_reindex` or letting the next search reconcile incrementally.
- **Non-UTF-8 files (e.g. macOS `._*`) are skipped** during indexing.
- **Scores are RRF values** (`weight / (k + rank)`, max ≈ 0.0164 at `rrf_k = 60`), not cosine similarities; below 4,096 vectors search uses exact linear scan (no HNSW graph is expected).
- **Rollback:** Remove `--plugins vector_search` from `args` and reload. The three tools disappear while `config.json` and the persisted index remain untouched on disk; `search` and `find_similar` are unaffected.
