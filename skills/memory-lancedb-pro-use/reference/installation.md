# Installation

Source: README section `Installation`.

## Path A - New to OpenClaw (recommended)

1) Clone plugin into workspace:

```bash
cd /path/to/your/openclaw/workspace
git clone https://github.com/CortexReach/memory-lancedb-pro.git plugins/memory-lancedb-pro
cd plugins/memory-lancedb-pro
npm install
```

2) Add plugin path and slot in `openclaw.json`:

```json
{
  "plugins": {
    "load": { "paths": ["plugins/memory-lancedb-pro"] },
    "entries": {
      "memory-lancedb-pro": {
        "enabled": true,
        "config": {
          "embedding": {
            "apiKey": "${JINA_API_KEY}",
            "model": "jina-embeddings-v5-text-small",
            "baseURL": "https://api.jina.ai/v1",
            "dimensions": 1024,
            "taskQuery": "retrieval.query",
            "taskPassage": "retrieval.passage",
            "normalized": true
          }
        }
      }
    },
    "slots": { "memory": "memory-lancedb-pro" }
  }
}
```

3) Validate, restart, and verify:

```bash
openclaw config validate
openclaw gateway restart
openclaw plugins info memory-lancedb-pro
openclaw hooks list --json
openclaw memory-pro stats
```

## Path B - Existing OpenClaw deployment

- Keep existing agents/channels/models unchanged.
- Use an absolute plugin path:

```json
{ "plugins": { "load": { "paths": ["/absolute/path/to/memory-lancedb-pro"] } } }
```

- Bind slot: `plugins.slots.memory = "memory-lancedb-pro"`
- Verify:

```bash
openclaw plugins info memory-lancedb-pro
openclaw memory-pro stats
```

## Path C - Upgrade from pre-v1.1.0 memory-lancedb-pro

Command boundaries:

- `upgrade`: old `memory-lancedb-pro` data
- `migrate`: built-in `memory-lancedb` only
- `reembed`: embedding rebuild after model change

Safe sequence:

```bash
openclaw memory-pro export --scope global --output memories-backup.json
openclaw memory-pro upgrade --dry-run
openclaw memory-pro upgrade
openclaw memory-pro stats
openclaw memory-pro search "known keyword" --scope global --limit 5
```

## Post-install checklist

```bash
openclaw config validate
openclaw gateway restart
openclaw plugins info memory-lancedb-pro
openclaw hooks list --json
openclaw memory-pro stats
openclaw memory-pro list --scope global --limit 5
```

Then confirm:

- exact-ID search returns expected hit
- natural-language search returns expected hit
- `memory_store` then `memory_recall` round trip works
- `/new` session behavior works if `sessionMemory.enabled=true`

## AI-safe checks

```bash
openclaw config get agents.defaults.workspace
openclaw config get plugins.load.paths
openclaw config get plugins.slots.memory
openclaw config get plugins.entries.memory-lancedb-pro
```

Notes:

- Prefer absolute `plugins.load.paths` in production.
- Ensure env vars are visible to the gateway process.
- Restart gateway after any plugin config change.
