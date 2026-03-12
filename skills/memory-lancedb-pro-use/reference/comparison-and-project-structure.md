# Comparison and Project Structure

Source: README sections `Compared to Built-in memory-lancedb` and `Architecture` / `File Reference`.

## Compared to built-in `memory-lancedb`

memory-lancedb-pro extends the built-in plugin with:

- BM25 full-text search and hybrid vector+BM25 fusion
- Cross-encoder reranking (Jina/custom endpoint)
- Recency boost, time decay, length normalization, MMR diversity
- Multi-scope isolation and adaptive retrieval/noise filtering
- Management CLI and session memory support
- Smart extraction, lifecycle decay, and legacy-upgrade workflow (v1.1.0)

## High-level architecture

- `index.ts`: plugin registration, config parsing, lifecycle hooks
- `src/store.ts`: LanceDB storage, FTS, CRUD, stats
- `src/embedder.ts`: embedding abstraction and provider compatibility
- `src/retriever.ts`: hybrid scoring, rerank, filtering pipeline
- `src/scopes.ts`: scope definitions and access control
- `src/tools.ts`: agent tool registration
- `cli.ts`: `openclaw memory-pro` command implementation
- `src/migrate.ts`: migration from built-in memory-lancedb

v1.1.0 additions:

- `src/smart-extractor.ts`, `src/memory-categories.ts`
- `src/decay-engine.ts`, `src/tier-manager.ts`
- `src/memory-upgrader.ts`, `src/llm-client.ts`
- `src/extraction-prompts.ts`, `src/smart-metadata.ts`

## Retrieval pipeline summary

1. Query embedding + BM25 retrieval.
2. Fusion and rerank.
3. Decay-aware scoring and length normalization.
4. Threshold filtering and diversity control.
5. Return top memories for agent injection/use.
