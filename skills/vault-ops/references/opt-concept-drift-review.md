# Concept Drift Review

Use when a user asks whether a concept/design note still matches the current Vault Ops skill, or asks to align concept notes with the live skill.

## Purpose

Concept notes often drift after the skill changes. Review them against the loaded skill and the vault-local rules, then patch the concept so it describes the current operating model rather than historical assumptions.

## Required Inputs

- Current `vault-ops` `SKILL.md`
- Relevant Vault Ops references, especially:
  - `references/vault-graph.md`
  - `references/vault-navigation.md`
  - `references/bookmarks-writing.md`
  - `references/note-writing.md`
- The selected vault's `AGENTS.md`
- If a `wiki/` path is involved, load `md-wiki` and follow its orientation/logging rules
- The concept/design note(s) being reviewed

## Drift Checks

Check for these common stale patterns:

1. **Scope drift**
   - Current rule: Vault Ops manages non-wiki vault work by default.
   - `wiki/` is maintained by `md-wiki`; Vault Ops edits it only when the user explicitly asks and `md-wiki` is loaded.

2. **Note-type drift**
   - Current resource-list type is `bookmarks`, not `resource-collection`.
   - Bookmarks are curated lists of external resources and use `type: bookmarks`.

3. **Precedence drift**
   - Current rule: the vault's root `AGENTS.md` overrides the skill.
   - Files referenced by `AGENTS.md` also override the skill.
   - `VAULT.md` provides deeper context/glossary; do not describe it as a blanket highest-precedence policy layer unless the vault explicitly says so.

4. **Hybrid linking drift**
   - Current convention is frontmatter `topics` plus body `Topics:` links after a horizontal rule.
   - Avoid old `## MoCs` body-section wording unless the specific vault still defines it.
   - Explain that `topics` is metadata, not a parsed graph edge; body wikilinks create backlinks.

5. **SQL drift**
   - Do not recommend `files, json_each(topics)` or arbitrary multi-table SQL as a working pattern.
   - Prefer graph tools (`get_forward_links`, `get_backlinks`, `get_related_notes`) and simple SQL over `files`, `links`, and `tags`.

6. **INDEX drift**
   - Current root path is `INDEX.md` → `area/INDEX.md`, `projects/INDEX.md`, `wiki/index.md`.
   - Root `INDEX.md` links to sub-INDEX files, not every individual MoC.

7. **Self-improvement drift**
   - Stable skill core should not accumulate session-specific lessons.
   - Lessons go first into `references/opt-*.md` or `references/opt-pitfalls.md` and are promoted only after explicit user approval.

## Update Workflow

1. Read the concept note and identify stale claims.
2. Rewrite the note to match the current rules above.
3. Keep project concepts concise but explicit about boundaries and caveats.
4. If also updating a wiki page/raw article under `wiki/`, load `md-wiki`, orient to the target wiki, and append a log entry.
5. Verify by searching for stale phrases such as:
   - `resource-collection`
   - `Resource Collections`
   - `## MoCs`
   - `Precedence: Skill defaults`
   - `files, json_each(topics)` when presented as recommended workflow
   - claims that Vault Ops powers all wiki operations

## Reporting

Report:

- files changed
- stale concepts removed or corrected
- verification searches performed
- any remaining historical/raw-source exceptions
