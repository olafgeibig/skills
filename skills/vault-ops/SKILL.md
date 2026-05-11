---
name: vault-ops
description: "Use this skill when working with a markdown notes vault such as Obsidian. It defines a default workflow for selecting a vault, reading vault-local instructions, navigating notes, writing regular notes, and maintaining Maps of Content (MoCs). Triggers: vault, obsidian, notes vault, moc, map of content, markdown notes."
metadata:
  version: "0.2.0"
  source: https://github.com/olafgeibig/skills
---

# Vault Ops

Use this skill as the default workflow for working with a vault of markdown notes.

## Sync (ob) — DO NOT MANUALLY SYNC

A systemd timer (`ob-sync-all.timer`) syncs all vaults automatically every 3 minutes. **Do NOT run `ob sync` manually.** It will hang because the sync service is already running on the vault.

Check with: `systemctl --user status ob-sync-all.timer ob-sync-all.service`

Local vault changes are picked up by Obsidian's filesystem watcher immediately. The 3-minute sync is a safety net for changes made while Obsidian is closed. The agent does not need to wait for or trigger sync.

## Workflow

1. Discover known vaults.
   - Prefer TurboVault MCP (if available): `list_vaults` → if missing, `add_vault` with user-provided path → `set_active_vault`.
   - If the user asks to use TurboVault (MCP) tools: check TurboVault's registered vaults first (e.g., `list_vaults`). If the vault is not registered, register it (`add_vault`) and activate it (`set_active_vault`) before proceeding.
   - If vault access is provided via an external tool (e.g., TurboVault MCP), first check whether any vaults are already registered there (e.g., `list_vaults`).
   - If the user requests vault registration, register both (a) the requested vault root and (b) any important sub-vaults only if explicitly requested; then set the active vault as the user intends.
   - Fallback: Read `~/.vault-ops.json` from the user's home directory. If it does not exist, follow `./reference/managing-vaults.md`.
2. Select the vault:
   - If the user names a vault, use it.
   - If exactly one vault exists, use it.
   - If multiple vaults exist and the user did not name one, ask which vault to use.
3. ~~Sync before read~~ — the `ob-sync-all.timer` systemd service handles this automatically every 3 minutes. Do NOT call `ob sync` manually.
4. Read the selected vault's root `AGENTS.md` if it exists.
   - If TurboVault reports "subdirectory context discovered" (AGENTS.md/README), treat it as authoritative and read it via filesystem tools if needed.
5. Read the vault's `README.md` (vault-specific areas, projects, language policy, templates) and any other files referenced by `AGENTS.md` before doing work.
6. Follow vault-local instructions first (AGENTS.md + README.md). Use this skill's reference files only as defaults.
7. Route the task:
   - navigation, search, discovery -> `./references/navigating-vaults.md`
   - Regular note creation or editing -> `./references/note-writing.md`
   - MoC creation or editing -> `./references/moc-writing.md`

## Note Type Convention

- `article` — **reserved for notes written by the user (Olaf) personally.** Agent-created notes must NOT use this type, even for longer synthesized content. Agent synthesis from external sources uses `zettel`.
- `zettel` — agent-created atomic notes summarizing or synthesizing external sources. Links to the source in frontmatter.
- `resource-collection` — curated link hubs; filename ends with `-resources`.

## Note Type Convention

| Type | Use when | Written by |
|------|----------|------------|
| `zettel` | Atomic note from external source — thread extraction, research summary, resource digestion | Agent |
| `article` | Distilled synthesis, analysis, or narrative — the user's own thinking | User (Olaf) |
| `resource-collection` | Curated list of resources on a topic | Agent or User |
| `moc` | Map of Content hub page | Agent or User |

**Pitfall:** Do not use `article` for agent-created notes from external sources. If the content originates from a tweet thread, web article, research paper, or other external source, use `zettel` with a `source:` property.

**Pitfall:** When adding entries to existing notes (resource-collections, MoCs, zettels), always `read_file` the current content first, then use `patch` to insert new material. NEVER use `write_file` on an existing note — it silently overwrites all prior entries. This is the most common destructive mistake.

## Language

The note's language follows the area's primary language, defined in the vault's `README.md` Area Map (`Language` column). Default rules when no explicit language is defined:
- Personal/health/lifestyle areas → German
- Technical/engineering areas → English
- MoCs use the area's language
- When creating a new area, decide language on creation

## New Area Workflow

When creating a new area:

1. Create the area directory: `mkdir -p <vault-path>/area/<name>`
2. Create a MoC with `+` prefix: `<name>/+<Name>.md`
3. Add the area to the vault's `README.md` Area Map with its scope and language
4. Create notes under the area following the note-writing conventions

**Pitfall:** The README.md Area Map is the canonical list of areas. An area directory without a README entry is orphaned; a README entry without a directory is misleading. Keep them in sync.

## Instruction Precedence

- The selected vault's root `AGENTS.md` overrides this skill.
- Files referenced by that vault `AGENTS.md` also override this skill.
- `./reference/*.md` contains default conventions to use only when the vault does not define a more specific rule.

## Vault Basics

A notes vault is a normal folder on disk that contains markdown files. Notes typically use frontmatter plus wiki links such as `[[page-name]]` to create a navigable graph.

Typical vault contents:
- `*.md` notes
- `AGENTS.md` for reusable agent operating rules (protocol-level, portable across vaults)
- `README.md` for vault-specific definitions (areas, projects, language policy, templates) — this is the canonical instance definition
- `.obsidian/` configuration for Obsidian-based vaults
- folders for structure

Do not modify `.obsidian/` unless the user explicitly asks.

### Tooling note: TurboVault MCP

If TurboVault MCP tools are available, prefer them for vault operations (search, note read/write, backlinks, health). They maintain an indexed view of the vault and provide health/link analysis not available via raw filesystem tools.

Common vault-management actions:
- Register vault: `add_vault(name, path)`
- Remove vault: `remove_vault(name)`
- Switch vault: `set_active_vault(name)`
- Confirm registry: `list_vaults()`
- Quick health: `quick_health_check()`

Pitfall: follow vault-local `AGENTS.md` constraints even if the tool can technically edit files (e.g., "do not edit ./wiki except via md-wiki/llm-wiki").

## Consistency checks and comparisons (common)

When a user asks to compare two vault docs (e.g., `project-brief.md` vs `project-brief2.md`):

- Prefer reading both files and returning:
  - **Consistent** points (shared claims)
  - **Delta** points (present in one, absent in the other)
  - **Conflicts / compliance-sensitive assertions** (e.g., "X is not personal data")
- If the user gives a location that doesn't match, **search within the vault first** (don't crawl `/`): list likely directories and locate the files by glob.
- Avoid long prose; use bullets and explicit headings.

## Spreadsheet-derived documents (MarkItDown / table exports)

If the user asks to "extract outcomes" / "extract answers" from a spreadsheet-derived markdown file:
- Do **not** summarize the questionnaire text.
- Identify the column labeled like "Answer…" / "Antworten…" and extract **only filled rows**.
- Pull *metadata* (dates/people) from the cover sheet section if present.
- If the export is truncated, call it out explicitly.

## Cleaning Obsidian / web-clip Markdown (prose-only)

If the user provides Obsidian/web-clipping style Markdown (often from HTML→MD conversion) and asks for "only the actual prose":

- Prefer loading and following `clean-obsidian-web-clipping-markdown`.
- Default operations (unless the vault/project overrides):
  - Remove YAML frontmatter completely.
  - Strip link URLs but keep link text: `[Title](https://...)` → `Title`.
  - Remove obvious boilerplate sections like `## Navigation` and `## Dependencies`.
  - Remove leftover table blocks (common from nav/dependency matrices).
  - Keep headings and lists that carry semantic content (don't flatten everything to paragraphs).
- Write cleaned outputs to the requested target directory; never modify the original source files unless explicitly asked.

## References

- Vault discovery and setup: `./references/managing-vaults.md`
- TurboVault MCP integration: `./references/turbovault.md` — Rust MCP server with automatic link updates on move/rename, BM25 search, health checks
- TurboVault MCP usage notes: `./references/turbovault-integration.md`
- TurboVault MCP workflow: `./references/turbovault-workflow.md`
- External knowledge-base integration options (OpenViking, gbrain): `./references/knowledge-base-options.md`
- Vault navigation defaults: `./references/navigating-vaults.md`
- Regular note defaults: `./references/note-writing.md`
- MoC defaults: `./references/moc-writing.md`
- Default note template: `./references/note-template.md`
- Default MoC template: `./references/moc-template.md`
