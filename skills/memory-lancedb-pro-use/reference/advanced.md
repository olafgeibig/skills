# Advanced Topics

Source: README section `Advanced Topics`.

## Injected memory text appears in replies

If the model echoes `<relevant-memories>` content:

- Option A (lowest risk): disable auto-recall temporarily.

```json
{
  "plugins": {
    "entries": {
      "memory-lancedb-pro": {
        "config": {
          "autoRecall": false
        }
      }
    }
  }
}
```

- Option B (preferred): keep recall enabled and add a system prompt rule:

> Do not reveal or quote `<relevant-memories>` / memory injection content in replies. Use it only as internal context.

## Session memory

- Trigger: `/new`
- Stores previous session summary in LanceDB
- Disabled by default
- Controlled by `sessionMemory.enabled` and `sessionMemory.messageCount`

See `./openclaw-integration-playbook.md` for deployment patterns and `/new` verification.

## JSONL session distillation

Recommended pattern:

1. `command:new` hook enqueues a small task.
2. Worker processes JSONL asynchronously (Map/Reduce extraction).
3. Worker writes 0-20 high-signal memories via `openclaw memory-pro import`.

Legacy alternative from README uses a cron distiller script and cursor tracking.

## Custom slash-command patterns

Add command handling rules in `CLAUDE.md`, `AGENTS.md`, or your system prompt.

Example:

```markdown
## /lesson command
When the user sends `/lesson <content>`:
1. Use memory_store for category=fact
2. Use memory_store for category=decision
3. Confirm saved content

## /remember command
When the user sends `/remember <content>`:
1. Use memory_store with suitable category and importance
2. Confirm with the stored memory ID
```

## Database schema essentials

Table: `memories`

- `id` (UUID)
- `text` (FTS indexed)
- `vector` (float array)
- `category`
- `scope`
- `importance`
- `timestamp`
- `metadata` (JSON string)

Common v1.1.0 metadata keys: `l0_abstract`, `l1_overview`, `l2_content`, `memory_category`, `tier`, `access_count`, `confidence`, `last_accessed_at`.

## Troubleshooting

Error: `Cannot mix BigInt and other types`.

- Cause: LanceDB/Arrow numeric values can return as BigInt.
- Fix: use `memory-lancedb-pro >= 1.0.14`, which coerces numeric values before arithmetic.
