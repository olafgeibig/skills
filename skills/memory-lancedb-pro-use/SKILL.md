---
name: memory-lancedb-pro-use
description: "Use this skill when installing, configuring, operating, or troubleshooting the memory-lancedb-pro plugin for OpenClaw. It covers hybrid retrieval (vector + BM25), cross-encoder reranking, smart extraction, multi-scope isolation, lifecycle controls, and the memory-pro CLI workflow. Triggers: memory-lancedb-pro, OpenClaw memory plugin, memory-pro CLI, hybrid retrieval, BM25, reranker, session memory."
license: MIT
compatibility: Requires OpenClaw with plugin slots support, Node.js 22+, and an embedding provider API key
metadata:
  source: https://github.com/CortexReach/memory-lancedb-pro
  version: "1.1.0-beta.8"
---

# Memory LanceDB Pro Helper

memory-lancedb-pro is a production-focused long-term memory plugin for OpenClaw. It adds persistent memory with hybrid retrieval (vector + BM25), optional cross-encoder rerank, smart LLM extraction, lifecycle decay and tiering, multi-scope isolation, and an operations CLI.

## What It Does

1. Stores memories in LanceDB with vector + FTS support.
2. Retrieves with hybrid scoring, reranking, and filtering.
3. Auto-captures memories from conversation turns.
4. Auto-recalls relevant memory before agent responses.
5. Isolates memory by scope (`global`, `agent:*`, `project:*`, `user:*`, `custom:*`).
6. Provides `openclaw memory-pro` commands for operations and migration.

## Quick Start

### Install plugin

```bash
npm i memory-lancedb-pro@beta
```

### Bind memory slot in `openclaw.json`

```json
{
  "plugins": {
    "slots": {
      "memory": "memory-lancedb-pro"
    }
  }
}
```

### Validate and restart

```bash
openclaw config validate
openclaw gateway restart
openclaw logs --follow --plain | rg "memory-lancedb-pro"
```

## Usage Overview

- Use auto-capture + smart extraction for low-friction memory building.
- Use auto-recall for memory injection before replies.
- Use scopes to prevent cross-agent/user memory leakage.
- Use CLI for audit and maintenance (`list`, `search`, `stats`, `export`, `import`, `upgrade`, `migrate`).

## Detailed References

- Installation guide (README Installation section): `./reference/installation.md`
- Configuration guide (README Configuration section): `./reference/configuration.md`
- Advanced topics (README Advanced Topics section): `./reference/advanced.md`
- Comparison and project structure from README: `./reference/comparison-and-project-structure.md`

README documentation links are mirrored locally here:

- OpenClaw integration playbook: `./reference/openclaw-integration-playbook.md`
- OpenClaw integration playbook (zh-CN): `./reference/openclaw-integration-playbook.zh-CN.md`
- Memory architecture analysis: `./reference/memory_architecture_analysis.md`
- Long-context chunking: `./reference/long-context-chunking.md`
- Changelog v1.1.0: `./reference/CHANGELOG-v1.1.0.md`

## Core CLI Commands

```bash
openclaw memory-pro list --scope global --limit 20
openclaw memory-pro search "query" --scope global --limit 10
openclaw memory-pro stats --scope global
openclaw memory-pro export --scope global --output memories.json
openclaw memory-pro import memories.json --scope global --dry-run
openclaw memory-pro upgrade --dry-run
openclaw memory-pro migrate check --source /path/to/memory-lancedb
```

## Operational Guardrails

- Run `openclaw config validate` before restart.
- Keep API keys in environment variables, not in tracked files.
- Use `upgrade` only for legacy `memory-lancedb-pro` data.
- Use `migrate` only when moving from built-in `memory-lancedb`.
