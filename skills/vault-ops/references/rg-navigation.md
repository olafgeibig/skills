# Ripgrep navigation

Use this when TurboVault MCP tools are not available. This workflow emulates MoC-based graph navigation using ripgrep + filesystem reads.

## 1) Navigate via MoCs (best-effort graph traversal)

Goal: follow the vault’s intended navigation path (MoCs -> notes) before running broad keyword search.

1) Find the entry MoC.
- Default entry point is `+Index.md` (or a vault-local equivalent defined in the vault root `AGENTS.md`).
- If you do not know the vault root, ask the user or consult `~/.vault-ops.json`.

2) Read the MoC.
- Open `+Index.md` and inspect its curated link lists.

3) Extract wikilinks from the MoC.
- Use ripgrep to list candidate targets from `[[...]]` links.
- Prefer links that point to other MoCs (`[[+Something]]`) first.

4) Handle nested MoCs explicitly.
- Treat MoCs as a hierarchy: a MoC can link to sub-MoCs (also +*.md).
- Expand MoC -> sub-MoC links before expanding MoC -> regular note links.
- If a MoC is too broad, expect navigation to continue via sub-MoCs; do not stop at the parent MoC.

5) Resolve link targets to files.
- If the link is `[[Name]]`, search for a file whose basename matches `Name` (common case).
- If multiple candidates exist, disambiguate using frontmatter `description` and/or `type`.
- If no file matches, the link may point to a heading or an unresolved note; search for a heading `# Name`.

6) Continue traversal.
- Repeat: open sub-MoCs, extract links, then drill into the most relevant notes.

## 2) Frontmatter navigation using `description` (rg-friendly index)

This is the key fallback when graph traversal is ambiguous: the `description:` frontmatter is treated as a navigation label (retrieval-oriented), not a content summary.

1) Build a shortlist via descriptions.
- Grep for `^description:` across the vault (optionally scoped to a subtree like `projects/` or `area/`).
- If the user provides keywords, filter descriptions by those keywords first.

2) Disambiguate candidates.
- Prefer candidates with the right `type:` (note vs moc) and correct `topics:`.
- Prefer more recently updated notes if multiple descriptions match equally well.

3) Navigate to the selected note.
- Read the note, then follow its `Topics:` inline links back to MoCs to continue exploration.

## 3) Keyword search (last resort / confirmation)

Use full-text search when:
- you cannot find the right MoC path,
- you suspect the vault is missing MoC coverage,
- or you want to confirm you did not miss anything.

Guidelines:
- Start with 2–5 distinctive keywords.
- Prefer adding a term over making the regex complex.
- After finding a candidate note, locate its MoC(s) by searching for its `Topics:` section and/or `topics:` frontmatter, then continue via MoCs.

## 4) Safety notes (rg-only mode)

- Avoid large-scale rename/move operations in rg-only mode; you cannot safely keep wikilinks consistent.
- Prefer reading first, propose changes second, and keep edits small and localized.
