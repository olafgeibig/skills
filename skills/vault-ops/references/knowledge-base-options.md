# External Knowledge-Base Integration Options

When the vault grows large and grep/wiki-links no longer suffice for search, or
when the user asks about augmenting the vault with semantic search / agent memory.

## OpenViking

**Status: Running** (http://127.0.0.1:1933)

| Capability | Supported? | Notes |
|---|---|---|
| Semantic search | ✅ | `viking_search` tool |
| Vault auto-sync | ❌ | **No file-watcher.** Must manually `viking_add_resource` to re-index. No watch mode, no inotify integration. |
| Persistent agent memory | ✅ | `viking_remember` |
| Web resource indexing | ✅ | `viking_add_resource` for URLs |

**Verdict:** Good for code repos and persistent facts, bad for a living vault that
changes daily. The lack of watch/auto-sync means the index drifts from reality
unless you build a cron job that re-indexes periodically.

## gbrain (Garry Tan)

**Status: Not installed — planning phase**

Repository: https://github.com/garrytan/gbrain (~14k stars, MIT)

### What it is
A personal knowledge brain for OpenClaw/Hermes agents. Production deployment holds
17,888 pages, 4,383 people, 723 companies across 21 cron jobs.

### Architecture
- **Canonical source:** Markdown + git (compatible with Obsidian vaults)
- **Backend:** Postgres + pgvector (local PGLite or Supabase)
- **Search:** Hybrid — HNSW cosine vector + tsvector keyword + graph-boosted, fused via RRF
- **Automation:** "Dream cycle" (9-phase nightly maintenance), conversation synthesis, auto-enrichment
- **Entity tracking:** Typed knowledge graph (founded, works_at, attended, ...)
- **MCP server:** 30+ tools, OAuth 2.1, thin-client mode

### Infrastructure Requirements (non-trivial!)
- **Bun** runtime (not Node/npm)
- **PostgreSQL** with **pgvector** extension
- Optional: Supabase account for managed DB

### Install Path
```
git clone + bun install + bun link
gbrain init
gbrain import ~/vaults/akademeia/
```

MCP mode (agent-driven): `gbrain serve` → add to config.yaml as MCP server.

### Key Differences vs vault-ops + md-wiki

| Dimension | vault-ops + md-wiki | gbrain |
|---|---|---|
| Complexity | Minimal (markdown + git) | High (DB, vector index, job queue, OAuth) |
| Search | grep/wiki-links | Hybrid vector+keyword+graph |
| Entity tracking | Manual | Automatic with typed relations |
| Automation | Agent-driven (skills) | Dream cycle + cron jobs |
| People/companies | Manual notes | Auto-enrichment by mention frequency |
| Setup time | 0 (already running) | ~30 min agent-driven, + PostgreSQL setup |

### When to Consider gbrain
- Vault exceeds ~1000 notes and grep/wiki-link search breaks down
- Entity tracking (people, companies, projects) becomes a manual burden
- You want the agent to automatically surface "what you know about X" without explicit queries

### When to Stay with vault-ops
- Vault is manageable with current tools
- You value simplicity and debuggability (plain markdown, no database)
- Infrastructure overhead of PostgreSQL + Bun is not justified yet
