Vault Ops

Concept (refactor towards TurboVault)

vault-ops used to be a workflow that primarily operated on a markdown notes vault (e.g. Obsidian) via ripgrep and standard filesystem file tools.

Now vault-ops is being reoriented around TurboVault (an MCP server): TurboVault is installed, the MCP tools are available, and the agent can use them to work in the vault both more safely and more powerfully.

Why TurboVault:
- Safer edits: notes can be moved/renamed with less risk of breaking vault consistency.
- Advanced navigation and search:
  - Traversing the notes graph (links/backlinks)
  - SQL queries over frontmatter
  - Fast keyword search (BM25) and additional analysis tools

Graph navigation as the core principle
- MoCs (Maps of Content) are curated navigation nodes (index pages), typically as +*.md.
- Notes attach to one or more MoCs via frontmatter (topics) and explicit wikilinks.
- The goal is a connected, traversable graph: entry via +Index, from there via MoCs to notes and back.

First concrete task (rework navigation)
1) Search the vault via graph traversal along MoCs and linked notes.
2) Search frontmatter (e.g. via SQL / metadata queries).
3) Search notes by keywords (BM25 / full-text).

Note
- Vault-local rules in the selected vault’s AGENTS.md are authoritative and may override these defaults.
- TurboVault MCP is required for vault-ops. If it is not available, instruct the user to enable/configure the TurboVault MCP server.