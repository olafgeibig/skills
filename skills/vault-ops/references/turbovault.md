# TurboVault — Obsidian Vault MCP Server

**Status: Installed on durin** — `~/.local/bin/turbovault` (ARM64 binary), configured as MCP server in `~/.hermes/config.yaml`. Tools not yet integrated into vault-ops workflow (next step).
**Version:** v1.5.0 (2026-05-01)
**Language:** Rust (MIT)

## What It Does

TurboVault is a dual-purpose toolkit: a Rust SDK for Obsidian-flavored Markdown (.ofm), and a ready-to-use MCP server with 47+ specialized tools.

**Key capability for vault-ops:** `move_note` and `rename_note` automatically update all backlinks — no manual regex patching needed. This is the missing piece that vault-ops currently does manually.

## Installation (ARM64 / Raspberry Pi)

Pre-built binaries available — no Rust toolchain needed.

```bash
# Download binary
curl -fsSL -o /tmp/turbovault.tar.gz \
  "https://github.com/Epistates/turbovault/releases/download/v1.5.0/turbovault-aarch64-unknown-linux-gnu.tar.gz"
tar xzf /tmp/turbovault.tar.gz -C /tmp

# Install
mkdir -p ~/.local/bin
cp /tmp/turbovault-aarch64-unknown-linux-gnu ~/.local/bin/turbovault
chmod +x ~/.local/bin/turbovault
```

Binary is ~10 MB. Uses glibc (Debian ARM64 confirmed working).

## Hermes MCP Configuration

Add to `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  turbovault:
    command: "/home/olaf/.local/bin/turbovault"
    args: ["--vault", "/home/olaf/vaults/akademeia", "--profile", "production"]
```

Requires: `pip install mcp --break-system-packages` (Debian PEP 668)

After restart, tools appear as `mcp_turbovault_*` (47 tools).

## Key Tools (Selection)

- `move_note` / `rename_note` — auto-updates all backlinks
- `batch_move` / `batch_delete` — atomic all-or-nothing operations
- `search` — full-text search with BM25 (Tantivy), <100ms on 10k notes
- `quick_health_check` / `full_health_analysis` — broken links, orphans, hubs
- `get_broken_links` / `get_orphans` — vault integrity
- `get_hub_notes` / `recommend_related` — knowledge graph navigation
- `edit_note` — hash-based conflict detection (optimistic concurrency)
- Multi-vault support (add/remove/switch at runtime)

## Performance (M1 Mac, 10k notes)

- File read: <10ms
- Search: <50ms
- Vault init: ~500ms
- Memory: ~80MB

## vs. `ob sync`

| Task | `ob` (Obsidian headless) | TurboVault |
|------|--------------------------|------------|
| Sync vault | ✅ `ob sync` | ❌ not a sync tool |
| Move/rename with link fix | ❌ | ✅ native |
| Search | ❌ | ✅ BM25 full-text |
| Health checks | ❌ | ✅ broken links, orphans |
| MCP-native | ❌ | ✅ 47 tools |
