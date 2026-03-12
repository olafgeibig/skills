# Configuration

Source: README section `Configuration`.

## Full Example

```json
{
  "embedding": {
    "apiKey": "${JINA_API_KEY}",
    "model": "jina-embeddings-v5-text-small",
    "baseURL": "https://api.jina.ai/v1",
    "dimensions": 1024,
    "taskQuery": "retrieval.query",
    "taskPassage": "retrieval.passage",
    "normalized": true
  },
  "dbPath": "~/.openclaw/memory/lancedb-pro",
  "autoCapture": true,
  "autoRecall": true,
  "retrieval": {
    "mode": "hybrid",
    "vectorWeight": 0.7,
    "bm25Weight": 0.3,
    "minScore": 0.3,
    "rerank": "cross-encoder",
    "rerankApiKey": "${JINA_API_KEY}",
    "rerankModel": "jina-reranker-v3",
    "rerankEndpoint": "https://api.jina.ai/v1/rerank",
    "rerankProvider": "jina",
    "candidatePoolSize": 20,
    "recencyHalfLifeDays": 14,
    "recencyWeight": 0.1,
    "filterNoise": true,
    "lengthNormAnchor": 500,
    "hardMinScore": 0.35,
    "timeDecayHalfLifeDays": 60,
    "reinforcementFactor": 0.5,
    "maxHalfLifeMultiplier": 3
  },
  "enableManagementTools": false,
  "scopes": {
    "default": "global",
    "definitions": {
      "global": { "description": "Shared knowledge" },
      "agent:discord-bot": { "description": "Discord bot private" }
    },
    "agentAccess": {
      "discord-bot": ["global", "agent:discord-bot"]
    }
  },
  "sessionMemory": {
    "enabled": false,
    "messageCount": 15
  },
  "smartExtraction": true,
  "llm": {
    "apiKey": "${OPENAI_API_KEY}",
    "model": "gpt-4o-mini",
    "baseURL": "https://api.openai.com/v1"
  },
  "extractMinMessages": 2,
  "extractMaxChars": 8000
}
```

## Default Notes

- `autoCapture`: enabled by default
- `autoRecall`: disabled by schema default; many users enable it
- `embedding.chunking`: enabled by default
- `sessionMemory.enabled`: disabled by default

## Embedding Providers

- Jina: `jina-embeddings-v5-text-small`, `https://api.jina.ai/v1`, 1024 dims
- OpenAI: `text-embedding-3-small`, `https://api.openai.com/v1`, 1536 dims
- Gemini: `gemini-embedding-001`, `https://generativelanguage.googleapis.com/v1beta/openai/`, 3072 dims
- Ollama: `nomic-embed-text`, `http://localhost:11434/v1`

## Rerank Providers

- `jina`: `https://api.jina.ai/v1/rerank`, model `jina-reranker-v3`
- `siliconflow`: `https://api.siliconflow.com/v1/rerank`, model `BAAI/bge-reranker-v2-m3`
- `voyage`: `https://api.voyageai.com/v1/rerank`, model `rerank-2.5`
- `pinecone`: `https://api.pinecone.io/rerank`, model `bge-reranker-v2-m3`

## Smart Extraction (v1.1.0)

Important fields:

- `smartExtraction` (default `true`)
- `llm.apiKey`, `llm.model`, `llm.baseURL`
- `extractMinMessages` (default `2`)
- `extractMaxChars` (default `8000`)

Minimal config:

```json
{
  "embedding": { "apiKey": "${OPENAI_API_KEY}", "model": "text-embedding-3-small" },
  "smartExtraction": true
}
```

## Lifecycle Configuration (Decay + Tier)

Key groups:

- `decay.*`: Weibull/frequency/intrinsic weighting
- `tier.*`: promote/demote thresholds between `peripheral`, `working`, `core`

Example:

```json
{
  "decay": { "recencyHalfLifeDays": 21, "betaCore": 0.7, "betaPeripheral": 1.5 },
  "tier": { "coreAccessThreshold": 8, "peripheralAgeDays": 45 }
}
```

## Access Reinforcement

Under `retrieval`:

- `reinforcementFactor` (`0` to disable, default `0.5`)
- `maxHalfLifeMultiplier` (default `3`)

Reinforcement applies to `source: "manual"` only.
