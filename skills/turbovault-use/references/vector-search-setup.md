# Setting up `vector_search` on a Hermes installation

End-to-end recipe for a machine where the plugin is not yet running: binary check → model → per-vault config → Hermes MCP wiring → verification. The reference facts (config keys and defaults, model table with dims/weights/disk, tool surface, index layout, measured costs, pitfalls) live in `references/vector-search.md`; this file is only the order of operations.

Placeholders: `<vault>` = absolute path of a registered vault, `<model-dir>` = absolute directory holding the model files, `<binary>` = absolute path of the `turbovault` executable.

## 0. Decide the model before downloading anything

Two questions, in this order: **which languages** does the vault hold, and **how much RAM** may the server hold permanently.

| Vault content | Model |
|---|---|
| English only | `minishlab/potion-base-8M` |
| Bilingual (German + English) | `minishlab/potion-multilingual-128M` |
| Bilingual, RAM-constrained | pruned `multilingual-128M` (step 3) |

Check model dimensions and disk size in `references/vector-search.md`. Use a model that covers the required query languages, and measure process memory and retrieval quality in a bounded pilot before committing to it.

## 1. Check what the binary can do

`<binary> --help | grep -- --plugins` and `strings <binary> | grep -c vector_search` — probes, thresholds and the `cargo install` caveat: `references/vector-search.md` § Check what the binary can do before believing a note. If the plugin is not compiled in, no configuration will produce the tools — replace the binary.

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

Note the directory path absolutely — `model_path` accepts no `~` expansion you can rely on. The file-list and `hidden_dim` checks to run in the same pass are in `references/vector-search.md` § Model.

## 3. Optional — prune the vocabulary

Worth it when a multilingual model's RSS is the binding constraint. The command, the mechanism, the corpus caveats and the measured before/after live in `references/vector-search.md` § Shrink a multilingual model: prune the vocabulary — run it with `--corpus '<vault>/**/*.md'` **before** the first index build. Pruning afterwards costs a full `vector_search_reindex`, because switching `model_path` changes the token ids.

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

Only `model_path` has no default; the full field list with defaults is in `references/vector-search.md` § Configure it. This is a plain **filesystem** write, not a vault write: `.turbovault/` is server state — the one legitimate exception to "everything goes through TurboVault". Check the write with `vector_search_status` (step 6) — it resolves the file and reports the effective config without loading the model.

## 5. Wire it into Hermes and reload

The MCP server is a spawned child process; the plugin flag belongs in its `args` alongside the existing baseline flags (`references/wf-turbovault-config.md` §2):

```bash
hermes config set mcp_servers.turbovault.args \
  '["-p","production","--config","/home/<user>/.turbovault/config.yaml","--no-confirm-destructive","--plugins","vector_search"]'
hermes config get mcp_servers.turbovault      # read the whole block back (verify args and XDG_CACHE_HOME)
```

Reload the owning MCP connection as described in `references/upgrading.md` §7. A new chat can reuse the old connection; verify the plugin tools on the intended surface.

Diff the running process against the config block before reloading (`ps -eo pid,ppid,etime,args | grep '[t]urbovault'`): a reload applies the **entire** `args` list, and only the reloading host replaces its child. Both traps — dropped process-only flags, and a second host keeping the old flags — belong to the generic rule in `hermes-provider-setup` § Config reload: what picks up a change; read it there rather than re-deriving it here.

## 6. Verify in three steps

1. **Config resolution:** `vector_search_status` → `configured: true`, the exact `model_path`, its `dims`, and the indexed note/chunk counts. `configured: false` names the missing `model_path`; that is a configuration gap, not a broken feature.
2. **Dense side actually works:** `vector_search_search` with a query in the vault's own language and `limit` 5. Read `dense_rank` and `lexical_rank` per hit — a hit with `dense_rank` set and `lexical_rank: null` proves the vector side contributed. Flat, unrelated top hits mean the model does not cover the language.
3. **Counts move:** after a real write, `vector_search_status` reflects the new note; the index reconciles incrementally per note and per chunk.

Measure cold and warm queries separately: the first search can rebuild the engine from the snapshots. Full reindex only after a model change, a distrusted snapshot, or the first build on a large vault — the abort/partial-index behaviour is in `references/vector-search.md` § Index.

## 7. Failure modes seen in practice

- **Tools missing after a restart:** compare the live process with the configured `args` and check plugin compilation and tool visibility before treating the index as broken.
- Everything else (`configured: false`, `unavailable` on every call, the 200-byte storage key, skipped non-UTF-8 files, RRF scores misread as confidence): `references/vector-search.md` § Pitfalls.

## 8. Rollback

Remove `--plugins vector_search` from `args` and reload the owning connection as in step 5: the three tools disappear, the index and `config.json` stay on disk untouched. Re-adding the flag brings the index back without a re-embed. Nothing about the vault depends on the plugin — `search` (BM25) and `find_similar` (TF-IDF) keep working throughout.
