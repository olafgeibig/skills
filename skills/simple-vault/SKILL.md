---
name: simple-vault
description: "Use when working in single-concept Obsidian mini-vaults."
metadata:
  version: "0.1.2"
  author: Olaf Geibig
  source: https://github.com/olafgeibig/skills
  hermes:
    category: personal
    tags:
      - obsidian
      - vault
      - concepts
      - research
      - mocs
    related_skills:
      - turbovault-use
---

# Simple Vault

Operate one concept project as a small, self-contained Obsidian vault. Use this standalone model instead of importing the area/project hierarchy from `vault-ops` or compliance machinery from `csl-vault`. No mandatory plugins, manifests, evidence IDs, or independent per-note versions.

## Before working

- Read applicable `AGENTS.md` files; local rules override defaults. Read `VAULT.md` when relevant.
- Establish the concept directory as the vault root, not the enclosing repository or publication vault.
- Follow project documentation language; default to English, not the chat language.
- Filesystem tools suffice. When using TurboVault, load `turbovault-use` and verify the selected vault and scope. Registration is not required for an Obsidian mini-vault.
- Do not restructure existing material, initialize Git, commit, or publish without a request. Preserve unrelated work.
- For new notes load `references/note-templates.md`; for initialization load `templates/vault-agents.md`.

## Layout

```text
concept-root/
├── AGENTS.md
├── INDEX.md
├── +Topic.md          # optional thematic MoCs
├── notes/             # resource, research, analysis, idea
├── derived/           # reusable conclusions
├── concept/           # publication candidates
└── resources/         # originals and attachments
```

Create directories only when used. No area/project wrappers, per-type folders, or mandatory per-directory MoCs.

## Navigation and Obsidian compatibility

- `INDEX.md` is the main MoC: purpose, scope, working version, current state, and curated links with short descriptions. Distinguish active and deferred material when useful.
- Start with INDEX as the only parent. Add `+Topic` MoCs for aspects that benefit from them; each has a parent that explicitly links back to it.
- Every content note must be reachable from INDEX through curated MoC links. MoCs organize, not synthesize.
- Every non-root note has at least one MoC in `topics` as quoted wikilink strings, mirrored exactly in a body `Topics:` footer after a horizontal rule. The root uses `topics: []` and no footer or self-link.
- Use unique basenames where possible; disambiguate collisions with vault-relative wikilink targets and optional aliases. Use relative attachment links and preserve case. No machine-specific absolute internal paths.
- Keep semantic/dependency links in the body, not duplicated in frontmatter. Only MoC membership requires dual representation.
- No Dataview or other plugin requirement. Do not overwrite `.obsidian` settings or require a preconfigured `.obsidian` directory. Content must remain understandable without the publication vault.

## Note types

| type | Role |
| --- | --- |
| resource | What one external source says; provenance plus summary/excerpts |
| research | What is known about a focused question across sources; findings and gaps |
| analysis | Evaluation, comparison, interpretation, feasibility, trade-offs |
| idea | Proposals, brainstorming, discussion outcomes, unverified hypotheses |
| derived | Reusable conclusion synthesized from working notes |
| concept | Coherent, independently readable publication candidate |
| moc | Curated navigation |

Atomic means a bounded subject, not one sentence. Split for independent reuse. Prefer one authoritative source per resource note; put collections in research or MoCs. An original meeting record can be a resource; extracted proposals are ideas.

Normally working notes → derived → concept. Create distinct artifacts linked by `Based on:`, not repeated renaming of one file. Concepts may directly use analyses or resources; omit redundant derived notes. Cite sources next to claims where a general dependency list is ambiguous. Separate source statements, interpretations, assumptions, and open questions.

## Metadata and links

Required: `description`, `type`, `updated`, `topics`. Descriptions explain content rather than echo titles. Obtain actual local dates with a tool; use `YYYY-MM-DD`.

- `updated`: last substantive content change, not a review-only metadata update.
- `created` and `tags`: optional; no area/project tags required.
- Root INDEX: quoted SemVer `version`, the shared working/release target; start at `"0.1.0"` unless directed otherwise.
- Content notes: `checked` and `reviewed_for` are absent until reviewed; both are required to claim review for a target version. `checked` is the actual review date; `reviewed_for` is the quoted project version, not an independent note version.
- Concept notes: `status: draft` or `status: ready`. Ready means scoped, supported, understandable alone, and explicit about assumptions and limitations; not necessarily perfect or published.
- `Based on:` body links identify actual inputs and drive impact assessment. Do not hide material dependencies solely in prose.
- `Deliverable:` body link identifies a real published target; omit until it exists.

## Resource provenance and refresh

Require `source_uri`: authoritative HTTPS URL, KB URI, or portable file path relative to the resource note. Optional `source_version` records a source-provided revision; optional `snapshot` locates a local copy relative to the note. Include a clickable source link in the body too.

1. Read the existing note and retrieve/read its actual source via an authorized backend. A locator is not authorization to transmit content or access other systems.
2. Compare claims, revision, and any snapshot. Follow confidentiality rules for copies.
3. Update summary, source revision, and snapshot where appropriate. Preserve substantive history using existing Git or project conventions; do not silently overwrite originals when history matters.
4. Advance `checked` only after a genuine check. Changed content also advances `updated` and invalidates affected downstream reviews.
5. If unchanged and valid for the target version, update only `checked` and `reviewed_for`.
6. Inaccessible, removed, or partially retrieved sources are limitations: report them, do not advance successful-review markers for checks not completed, invent revisions, or silently substitute sources.

## Bottom-up version refresh

Project versions label iterations; they do not archive history. Existing Git supplies history. Without version control or snapshots, state that old releases cannot be reconstructed from frontmatter alone.

1. Establish the target version and iteration reason in INDEX. Default: minor for substantive additions, patch for corrections, major for incompatible changes to the agreed approach. Preserve explicitly requested versions.
2. Traverse the target concept's `Based on:` inputs recursively, including material inline dependencies. Repair missing explicit input links. Determine the relevant dependency set; unused/deferred ideas need not block publication.
3. Review resources, then dependent research/analysis/ideas, then derived conclusions, then concepts. Follow dependency order rather than folders. Resolve dependency cycles by separating assumptions from conclusions or report the ambiguity; never certify circular reasoning.
4. Assess each note. Check ideas for relevance and assumptions, not truth as established facts. For unchanged-but-valid notes advance only `checked` and `reviewed_for`; changed notes also advance `updated`.
5. When any input changes, remove `reviewed_for` from affected downstream notes and set affected concepts to draft. Preserve the last actual `checked` date. Revalidate bottom-up before restoring markers. Apply this even within the same version or day.
6. Never bulk-bump review markers without individual checks. Matching dates/versions alone do not prove freshness; inspect actual changes and available history.
7. Mark a concept ready only after relevant dependencies are reviewed or unresolved limitations are explicitly accepted. Summarize changed, rechecked-unchanged, deferred, and blocked material in INDEX.

## Publication

- Publish only on explicit request to a destination defined in local AGENTS.md. Work may be the target, but do not hardcode a vault name or machine path in this generic skill.
- Maintain one local concept ↔ one target note. Multiple local concepts may have separate targets; never silently map several to one target or create a new target per release.
- The mini-vault is the authoring source. Update the existing target; no automatic two-way sync.
- Read the target before updating and compare against the last published content/revision when available. If target-side edits cannot safely be distinguished, stop for reconciliation rather than overwrite.
- Render a self-contained target following destination conventions. Translate local-only links into valid target links, explanations, or external locators. Preserve citations and limitations; do not leak unresolved mini-vault wikilinks.
- Cross-vault links require properly encoded Obsidian URIs or actual repository/web locators, not plain wikilinks. Add a reciprocal origin locator if authorized and usable; disclose missing portable locators.
- Read back the exact target after writing. Only then update `Deliverable:` plus a body publication record with version and actual publication date. Later local edits do not change that historical publication record.

## Verify before completion

- Validate YAML, allowed types, quoted version strings, descriptions, and actual date values.
- Check local note/attachment targets and reachability of every content note from INDEX.
- Check non-root MoC membership in both directions and matching frontmatter/footer topics.
- Exclude instructions, templates, raw resources, and `.obsidian` settings from content metadata requirements.
- Verify review order; distinguish changed, reviewed, deferred, and blocked work honestly.
- Check publication mapping and read-back when requested.
- If an actual Obsidian rendering test is unavailable, report static compatibility checks only; never claim visual testing occurred.
