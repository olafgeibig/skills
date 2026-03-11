---
name: lossless-claw-skill
description: "Use this skill when installing, configuring, tuning, or troubleshooting the lossless-claw plugin in OpenClaw. It covers context engine setup, LCM compaction tuning, agent memory tools (`lcm_grep`, `lcm_describe`, `lcm_expand_query`), database operations, TUI maintenance workflows, and optional FTS5 runtime enablement. Triggers: lossless-claw, LCM, OpenClaw context engine, summary DAG, lcm-tui, lcm_expand_query."
license: Apache-2.0
compatibility: Requires OpenClaw with plugin slots support, Node.js 22+, and an LLM provider configured for summarization
metadata:
  source: https://github.com/olafgeibig/skills
  version: "0.1.0"
---

# Lossless Claw Helper

Lossless Context Management plugin for OpenClaw, based on the LCM paper. It replaces OpenClaw's built-in sliding-window compaction with a DAG-based summarization system that preserves every message while keeping active context within model token limits.

## What It Does

When a conversation grows beyond the model's context window, OpenClaw normally truncates older messages. LCM instead:

1. Persists every message in a SQLite database, organized by conversation.
2. Summarizes older message chunks using the configured LLM.
3. Condenses summaries into higher-level nodes, forming a DAG.
4. Assembles each turn from summaries plus recent raw messages.
5. Exposes retrieval tools so agents can search and recall details from compacted history.

Nothing is lost: raw messages remain in the database, summaries link to source material, and agents can drill into compacted history.

## Quick Start

### Prerequisites

- OpenClaw with plugin context engine support
- Node.js 22+
- An LLM provider configured in OpenClaw for summarization

### Install the plugin

```bash
openclaw plugins install @martian-engineering/lossless-claw
```

If running from a local OpenClaw checkout:

```bash
pnpm openclaw plugins install @martian-engineering/lossless-claw
```

For local plugin development, link your working copy:

```bash
openclaw plugins install --link /path/to/lossless-claw
```

### Configure OpenClaw

In most cases, installer setup is enough. If manual configuration is needed, set the context engine slot:

```json
{
  "plugins": {
    "slots": {
      "contextEngine": "lossless-claw"
    }
  }
}
```

Restart OpenClaw after configuration changes.

## Usage Overview

- Use `lcm_grep` to search compacted history.
- Use `lcm_describe` to inspect a specific summary or stored large file.
- Use `lcm_expand_query` for deep recall when summaries omit required detail.
- Use `lcm-tui` to inspect DAG/context state and run maintenance operations.

## Detailed References

- Configuration guide (including environment variables): `./reference/configuration.md`
- Architecture and internals: `./reference/architecture.md`
- Agent tools reference and patterns: `./reference/agent-tools.md`
- TUI reference and maintenance workflows: `./reference/tui.md`
- Optional FTS5 runtime enablement: `./reference/fts5.md`
