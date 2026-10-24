---
name: authoring-vault
description: "Use when authoring deliverables in a working vault: notes → distilled → publication."
metadata:
  version: "2.0.0"
  author: Olaf Geibig
  source: https://github.com/olafgeibig/skills
  hermes:
    category: personal
    tags:
      - obsidian
      - vault
      - analysis
      - deliverables
      - research
      - mocs
    related_skills:
      - turbovault-use
---

# Authoring Vault

Operate one small, self-contained **working vault** of kind `authoring`: the vault a project's work is done in, whose outputs are published into a notes vault. Use this standalone model instead of importing the area/project hierarchy from `vault-ops` or the compliance machinery from `csl-vault`. No mandatory plugins, manifests, evidence IDs, or independent per-note versions.

A working vault without a publication target is just a hand-written knowledge base and needs none of this. This skill is the `authoring` kind, not the whole genus: a `csl` working vault is governed by `csl-vault`.

## Before working

- Read applicable `AGENTS.md` files; local rules override defaults. Read `VAULT.md` when relevant.
- Establish the project directory as the vault root, not the enclosing repository or a destination vault.
- Follow project documentation language; default to English, not the chat language.
- Filesystem tools suffice. When using TurboVault, load `turbovault-use` and verify the selected vault and scope. Registration is not required for an Obsidian mini-vault.
- Do not restructure existing material, initialize Git, commit, or publish without a request. Preserve unrelated work.
- For new notes load `references/note-templates.md`; for initialization load `templates/vault-agents.md`.
- For multi-step knowledge work, coverage decisions, composition choices, or refreshes, load `references/knowledge-workflow.md`.
- Treat template body headings as defaults: preserve the user's requested section names, order, and brevity while applying the required metadata and navigation, because a valid note must also match the requested reading structure.

## Capture an existing discussion as a note

1. Read INDEX and the relevant existing notes before adding a Zettel; update the authoritative note when the subject already exists rather than creating a duplicate.
2. Carry forward the purpose and sequence already stated in the conversation. Record genuinely undecided boundaries separately; an unexplained project acronym does not make the user's stated goal unknown. Keep analysis, distilled findings, and later deliverables distinct when the user requested that sequence.
3. For a request to save completed research, write a focused `research` note from the available findings and actual source locators, then link it from INDEX and update the iteration reason/version. Preserve the research's original as-of date and attribution; saving or reformatting findings is not a fresh source check. Re-fetch sources only when a refresh is requested or a material claim needs verification, and disclose missing evidence instead of treating an earlier assistant assertion as a checked source.
4. When asked for a project-context note, keep the AGENTS summary to short sentences about the subject, current phase, and intended next phase; place essential facts, limitations, and links to detailed research in the context note. Add the requested read-before-work instruction to AGENTS and a curated link from INDEX. Preserve the user-specified filename even when documentation uses another language; translating the basename breaks the requested artifact and its incoming links.

## Formal migration of an existing vault

When asked to align an existing vault with an updated skill without changing its substance:

1. Read local rules, INDEX, context, and affected notes; compare their current roles with this skill. Identify obsolete folder/type names, stale links, and support files carrying content-only metadata. Preserve compatible structure rather than rebuilding the vault.
2. Rename or reclassify only what needs alignment. Map legacy types by actual role rather than replacing every occurrence mechanically. Keep instructions and templates discoverable from AGENTS or INDEX without adding content-note metadata or Topics footers; retain content-note provenance and navigation for factual context notes.
3. Update incoming links and local operating instructions together with any rename. Preserve substantive text, source as-of dates, `updated`, project version, review markers, and publication history unless the requested migration explicitly requires changing them. A formal migration is not a fresh evidence review or authorization to republish.
4. Read back affected targets and validate YAML, allowed types, links, and navigation across the migration scope. Search for obsolete paths/types, distinguishing intentional historical mentions from live references. Report exactly what changed and what was checked; validating a few touched files does not establish whole-vault conformance.

## Layout

```text
project-root/
├── AGENTS.md
├── INDEX.md
├── +Topic.md          # optional thematic MoCs
├── notes/             # working research, analysis, and ideas
├── distilled/         # reusable conclusions drawn from analysis
├── deliverables/      # audience- and format-specific outputs
├── resources/         # originals and attachments
└── system/            # project context, publication instructions, local templates, optional briefs
```

Create directories only when used. No area/project wrappers, per-type folders, or mandatory per-directory MoCs.

## Navigation and Obsidian compatibility

- `INDEX.md` is the main MoC: purpose, scope, working version, current state, and curated links with short descriptions. Distinguish active and deferred material when useful.
- Start with INDEX as the only parent. Add `+Topic` MoCs for aspects that benefit from them; each has a parent that explicitly links back to it.
- Every content note must be reachable from INDEX through curated MoC links. MoCs organize, not synthesize.
- Every non-root content note has at least one MoC in `topics` as quoted wikilink strings, mirrored exactly in a body `Topics:` footer after a horizontal rule. The root uses `topics: []` and no footer or self-link. Instructions, templates, and other support files are exempt unless deliberately maintained as content notes.
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
| distilled | Reusable conclusion synthesized from research and analysis |
| deliverable | Self-contained output tailored to an audience and target format |
| moc | Curated navigation |

Atomic means a bounded subject, not one sentence. Split for independent reuse. Prefer one authoritative source per resource note; put collections in research or MoCs. An original meeting record can be a resource; extracted proposals are ideas.

Grounding is the work of establishing relevant knowledge. `resource` represents a concrete source, `research` reports findings across sources, `analysis` evaluates or interprets, and `idea` records proposals or assumptions. These roles can complement one another; they are not mandatory sequential steps.

Normally, working research and analysis lead to distilled knowledge, then deliverables. Distillation turns relevant grounding into concise, reusable conclusions with scope, qualifications, unresolved limits, and actual input links. A deliverable may assemble distilled material or rewrite it for its audience and format. It may use analysis or resources directly when a separate distilled note adds no value. Create distinct artifacts linked by `Based on:`, not repeated renaming of one file. Cite sources next to claims where a general dependency list is ambiguous. Separate source statements, interpretations, assumptions, and open questions.

## Knowledge workflow

Define the subject, boundaries, intended outputs, and known unknowns before assessing coverage. Check coverage against that scope and each deliverable brief; record material omissions rather than claiming exhaustive knowledge of an open-ended subject. The phases can iterate when a gap requires more grounding.

- **Grounding:** develop source-backed findings, evaluations, or clearly marked proposals; retain reasoning, provenance, assumptions, and unresolved points at useful detail.
- **Distillation:** synthesize relevant grounding into bounded, reusable conclusions without losing qualifications; link actual inputs.
- **Composition:** create a self-contained audience- and format-specific output. Assemble distilled sections or rewrite their substance; keep actual dependencies in `Based on:`. Copied text is authored output, not live transclusion, and does not update automatically.
- **Review:** review the relevant dependency chain bottom-up. Readiness must be justified by scope, support, and accepted limitations; it is not approval or publication.
- **Publication:** publish only an authorized ready output to its specific target. Read back the target before recording a verified link and publication history.
- **Refresh:** when an input changes, invalidate affected downstream review claims and return affected deliverables to draft. Preserve the last actual `checked` date and revalidate affected material bottom-up.

Use `system/` for project-specific operating instructions, topical templates, compact context, publication instructions, and optional deliverable briefs. Keep AGENTS concise and link to the support files agents need. Instructions, templates, and briefs are not content notes by default. A context note that makes factual claims follows content-note provenance and dependency rules; it frames the goal, subject, phase, boundaries, and pointers without replacing detailed evidence or becoming independent proof of claims derived from its inputs. A brief describes the intended result, audience, scope, content, structure, coverage, composition mode, intended target, acceptance criteria, and open decisions.

## Metadata and links

Required: `description`, `type`, `updated`, `topics`. Descriptions explain content rather than echo titles. Obtain actual local dates with a tool; use `YYYY-MM-DD`.

- `updated`: last substantive content change, not a review-only metadata update.
- `created` and `tags`: optional; no area/project tags required.
- Root INDEX: quoted SemVer `version`, the shared working/release target; start at `"0.1.0"` unless directed otherwise.
- Content notes: `checked` and `reviewed_for` are absent until reviewed; both are required to claim review for a target version. `checked` is the actual review date; `reviewed_for` is the quoted project version, not an independent note version.
- Deliverable notes: `status: draft` or `status: ready`. Ready means scoped, supported by its inputs, understandable alone, and explicit about assumptions and limitations; not necessarily perfect or published.
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
2. Traverse the target deliverable's `Based on:` inputs recursively, including material inline dependencies. Repair missing explicit input links. Determine the relevant dependency set; unused/deferred ideas need not block publication.
3. Review resources, then dependent research/analysis/ideas, then distilled conclusions, then deliverables. Follow dependency order rather than folders. Resolve dependency cycles by separating assumptions from conclusions or report the ambiguity; never certify circular reasoning.
4. Assess each note. Check ideas for relevance and assumptions, not truth as established facts. For unchanged-but-valid notes advance only `checked` and `reviewed_for`; changed notes also advance `updated`.
5. When any input changes, remove `reviewed_for` from affected downstream notes and set affected deliverables to draft. Preserve the last actual `checked` date. Revalidate bottom-up before restoring markers. Apply this even within the same version or day.
6. Never bulk-bump review markers without individual checks. Matching dates/versions alone do not prove freshness; inspect actual changes and available history.
7. Mark a deliverable ready only after relevant dependencies are reviewed or unresolved limitations are explicitly accepted. Summarize changed, rechecked-unchanged, deferred, and blocked material in INDEX.

## Publication

- Publish only on explicit request to a destination defined in local AGENTS.md. Work may be the target, but do not hardcode a vault name or machine path in this generic skill.
- A brief may name an intended target before publication. An intended target is not a verified `Deliverable:` link or publication record; add those only after authorized publication succeeds and the exact target is read back.
- Map each local deliverable one-to-one to a target artifact. When asked to publish distilled findings, create the output under `deliverables/` with `type: deliverable`, link its actual inputs through `Based on:`, and add it to INDEX; keep distilled conclusions as reusable inputs rather than attaching publication metadata to them. Preserve approved content unless adaptation is needed for the audience or format. A target can be a page, report, deck, or vault/package; for a multi-file target, define its root `INDEX.md` or complete bundle as the mapped artifact. Multiple deliverables may reuse the same inputs, but do not map several deliverables to one target or create a new target per release.
- The source vault is the authoring source. Update the existing target; no automatic two-way sync.
- Read the target before updating and compare against the last published content/revision when available. If target-side edits cannot safely be distinguished, stop for reconciliation rather than overwrite.
- Render a self-contained target following destination conventions. Translate local-only links into valid target links, explanations, or external locators. Preserve citations and limitations; do not leak unresolved mini-vault wikilinks.
- Cross-vault links require properly encoded Obsidian URIs or actual repository/web locators, not plain wikilinks. Add a reciprocal origin locator if authorized and usable; disclose missing portable locators.
- Read back the exact target after writing. Only then update `Deliverable:` plus a body publication record with version and actual publication date. Read the project version from INDEX before building publication comments or records; keep that version distinct from the destination's revision number, because they identify different histories. Later local edits do not change that historical publication record.

## Verify before completion

- Validate YAML, allowed types, quoted version strings, descriptions, and actual date values.
- Check local note/attachment targets and reachability of every content note from INDEX. Inspect list indentation as well as link existence: insert a new sibling after an existing parent's entire nested child block, not between the parent and its children, because valid links can still imply the wrong hierarchy. Verify requested filenames and AGENTS read-before-work links explicitly; after a rename, update incoming links together and check that no stale target remains.
- Check non-root MoC membership in both directions and matching frontmatter/footer topics.
- Exclude instructions, templates, raw resources, and `.obsidian` settings from content metadata requirements.
- Verify review order and coverage against the agreed subject scope and output briefs; distinguish changed, reviewed, deferred, omitted, and blocked work honestly. Keep publication records on deliverable notes, not distilled inputs.
- Confirm support-file roles are clear, factual context has traceable inputs, and every deliverable's intended target is distinguished from verified publication.
- Check publication mapping and read-back when requested.
- If an actual Obsidian rendering test is unavailable, report static compatibility checks only; never claim visual testing occurred.
