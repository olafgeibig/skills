Vault Ops

vault-ops is an opinionated workflow for working with a markdown notes vault (e.g. Obsidian) as a navigable notes-graph.

Core idea:
- Use MoCs (Maps of Content) as curated navigation notes (index pages) that form the spine of the graph.
- Use consistent frontmatter (description/type/updated/tags/topics) so notes are machine-queryable and can be traversed reliably.
- Enforce topological linking: every note belongs to one or more MoCs via frontmatter topics and an explicit inline wikilink, so the graph remains connected for both search and navigation.

How it adapts:
- The selected vault’s root AGENTS.md is authoritative and can override this skill’s defaults (structure, templates, tags, language).
- If TurboVault is available, prefer its MCP tools for safe reads/edits and vault health checks; otherwise fall back to ripgrep and filesystem operations.