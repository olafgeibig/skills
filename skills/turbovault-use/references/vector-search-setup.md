# Setting up `vector_search` on a Hermes installation

End-to-end recipe for a machine where the plugin is not yet running: binary check → model → per-vault config → Hermes MCP wiring → verification. The reference facts (config keys, tool surface, index layout, pitfalls) live in `references/vector-search.md`; this file is the order of operations.

Placeholders: `<vault>` = absolute path of a registered vault, `<model-dir>` = absolute directory holding the model files, `<binary>` = absolute path of the `turbovault` executable.

## 0. Decide the model before downloading anything

Two questions, in this order: **which languages** does the vault hold, and **how much RAM** may the server hold permanently.

| Vault content | Model | Dim | Weights | Disk | Expected RSS |
|---|---|---|---|---|---|
| English only | `minishlab/potion-base-8M` | 256 | 30 MB | 30 MB | ~230 MB |
| Mostly English, some German | `minishlab/potion-base-32M` | 512 | 129 MB | 260 MB | ~400 MB |
| Bilingual (German + English) | `minishlab/potion-multilingual-128M` | 256 | 512 MB | 1.05 GB | ~1.2 GB |
| Bilingual, RAM-constrained | pruned `multilingual-128M` (step 3) | 256 | ~45 MB | ~47 MB | ~270 MB |

`hidden_dim` is per model — read it from the model's own `config.json` instead of assuming (2M = 64, 4M = 128, 8M = 256, 32M and retrieval-32M = 512, multilingual-128M = 256).

A multilingual model is not optional politeness: on an English-trained model a German query returns dense scores flat around 0.70 across unrelated notes, and hybrid search then degrades to BM25 plus noise. If the vault is German, take a multilingual model or prune one.

## 1. Check what the binary can do

```bash
<binary> --version
<binary> --help | grep -- --plugins              # flag present → plugin support compiled in
strings <binary> | grep -c vector_search         # > 0 → the plugin itself is in this binary
```

A `cargo install` build is stdio-only without the feature; release archives carry everything. If the plugin is not compiled in, no configuration will produce the tools — replace the binary.

## 2. Fetch the model files

No download at runtime: the engine is built `local-only` and only reads a directory. Fetch the repository files except `onnx/` and `README.md`:

```bash
MODEL=minishlab/potion-multilingual-128M
DEST=~/.local/share/turbovault-models/potion-multilingual-128M
mkdir -p "$DEST"
for f in config.json model.safetensors tokenizer.json tokenizer_config.json \
         special_tokens_map.json modules.json vocab.txt; do
  curl -fsSL "https://huggingface.co/$MODEL/resolve/main/$f" -o "$DEST/$f"
done
ls -l "$DEST"
```

Checks worth doing in the same pass: `curl -s https://huggingface.co/api/models/<id>` for the real file list (a repo that ships `embeddings.safetensors` or a bare torch checkpoint needs conversion), and `curl -sL https://huggingface.co/<id>/raw/main/config.json` for `hidden_dim`. Note the directory path absolutely — `model_path` accepts no `~` expansion you can rely on.

## 3. Optional — prune the vocabulary

A multilingual model is almost entirely vocabulary (500,353 Unigram tokens × 256 dims × 4 bytes), while a two-language vault touches a few tens of thousands of them. `scripts/prune-model2vec-vocab.py` keeps every token the corpus uses and slices the embedding table:

```bash
python3 -m venv /tmp/m2v && /tmp/m2v/bin/pip install tokenizers safetensors numpy
/tmp/m2v/bin/python <skill-dir>/scripts/prune-model2vec-vocab.py \
  --source ~/.local/share/turbovault-models/potion-multilingual-128M \
  --out ~/.local/share/turbovault-models/potion-multilingual-45k \
  --target 45000 --corpus '<vault>/**/*.md'
```

Measured on a 1,000-note bilingual vault: model 513 MB → 47 MB, RSS 1,164/1,225 MB → 211/273 MB, reindex 22.2 s → 21.6 s, German query results identical paths and dense scores. Only Latin-script corpora survive pruning intact — Cyrillic/CJK tokens become `[UNK]`; re-prune with a higher `--target` if the vault later collects other scripts.

## 4. Configure the plugin per vault

```bash
mkdir -p <vault>/.turbovault/plugins/vector_search
cat > <vault>/.turbovault/plugins/vector_search/config.json <<'EOF'
{
  "model_path": "<model-dir>",
  "chunk_max_chars": 800,
  "chunk_overlap_chars": 100,
  "lexical_weight": 0.4
}
EOF
```

Only `model_path` has no default. This is a plain **filesystem** write, not a vault write: `.turbovault/` is server state — the one legitimate exception to "everything goes through TurboVault".

Check the write with `vector_search_status` (step 6) — it resolves the file and reports the effective config without loading the model.

## 5. Wire it into Hermes and reload

The MCP server is a spawned child process; the plugin flag belongs in its `args`:

```bash
hermes config set mcp_servers.turbovault.args \
  '["--profile","production","--config","/home/<user>/.turbovault/config.yaml","--plugins","vector_search"]'
hermes config get mcp_servers.turbovault      # read the whole list back
```

Then reload in a session with **`/reload-mcp`** (gateway, TUI, desktop). New session or `/new` does **not** help — the connection is cached per registry scope and a fresh session adopts the live one. The command asks for confirmation because it resets the provider prompt cache.

Before reloading, diff the running process against the config: a reload applies the **entire** `args` list, so any flag that exists only on the running process (an experiment, a debug switch, a confirm-gate setting the config does not carry) silently disappears.

```bash
ps -eo pid,ppid,etime,args | grep '[t]urbovault'    # expect a young child with the full new args
```

If the installation keeps more than one host alive (gateway plus dashboard), only the reloading host replaces its child — the other keeps the old flags until it restarts.

## 6. Verify in three steps

1. **Config resolution:** `vector_search_status` → `configured: true`, the exact `model_path`, its `dims`, and the indexed note/chunk counts. `configured: false` names the missing `model_path`; that is a configuration gap, not a broken feature.
2. **Dense side actually works:** `vector_search_search` with a query in the vault's own language and `limit` 5. Read `dense_rank` and `lexical_rank` per hit — a hit with `dense_rank` set and `lexical_rank: null` proves the vector side contributed. Flat, unrelated top hits mean the model does not cover the language.
3. **Counts move:** after a real write, `vector_search_status` reflects the new note; the index reconciles incrementally per note and per chunk.

The first search after a process start takes ~20 s on a Pi-class machine (the engine rebuilds from the JSON snapshots); warm queries are single-digit to low-double-digit milliseconds. Do not read that first latency as a defect.

Full reindex only when it is needed — after a model change (token ids change), after the snapshot is distrusted, or for the first build on a large vault: `vector_search_reindex` drops every chunk and the cursor before it re-walks, so an abort leaves a partial index that the next `reindex` or an incremental reconcile has to finish.

## 7. Expectations on small hardware

Pi 5 (4 cores, 8 GB), 1,000 notes / ~21,000 chunks: reindex 22 s, warm hybrid query 8–19 ms, RSS 232 MB (`base-8M`) or ~1.2 GB (`multilingual-128M`), 211/273 MB pruned. Embedding is CPU-only (tokenize + lookup + mean-pool), so a GPU changes nothing. On a 4 GB box take `base-8M` or the pruned multilingual model — the full multilingual model's RSS is the difference between a server that stays up and one that gets OOM-killed.

## 8. Failure modes seen in practice

- **Tools missing after a restart:** the `--plugins vector_search` flag was dropped from `args` while the process was still running with it. Check `ps` against the config block — an intact index with no tools is always this.
- **`configured: false`:** no `<vault>/.turbovault/plugins/vector_search/config.json`, or its `model_path` points at a missing directory. The index cannot substitute for it.
- **`unavailable` on every call:** one engine per process, bound to the vault that was active when it was first built; an active-vault switch does not follow. Reorder vault selection, do not retry.
- **`storage key is <n> bytes; the maximum is 200`:** a long note path breaks `vector_search_reindex`; shorten titles before the first build (rename through `move_note`, check `get_links` first).
- **A 1,001-note vault indexes 1,000:** a non-UTF-8 file (macOS `._name.md`) is skipped by design.

## 9. Rollback

Remove `--plugins vector_search` from `args` and `/reload-mcp`: the three tools disappear, the index and `config.json` stay on disk untouched. Re-adding the flag brings the index back without a re-embed. Nothing about the vault depends on the plugin — `search` (BM25) and `find_similar` (TF-IDF) keep working throughout.
