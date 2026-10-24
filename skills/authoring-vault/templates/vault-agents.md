# Authoring Vault

This directory is one self-contained working vault of kind `authoring`: analysis and deliverables, whose outputs publish into a notes vault. Apply the `authoring-vault` skill. Replace these setup placeholders before adoption; merge with existing instructions rather than overwrite them.

## Scope

- Project: {{title}}
- Goal: {{purpose and intended outcome}}
- Out of scope: {{boundaries}}
- Documentation language: English

## Structure

INDEX.md is the main MoC and holds the quoted project version. Optional +Topic.md files organize aspects. Working research and analysis live in notes/, reusable conclusions in distilled/, audience- and format-specific outputs in deliverables/, originals in resources/, and project context, publication instructions, topical templates, and optional deliverable briefs in system/. Create directories only when used. No area/project hierarchy or mandatory plugins.

AGENTS.md should point agents to essential context and publication instructions. Support instructions, templates, and briefs are not content notes by default; factual context maintained as a content note needs appropriate metadata, provenance, and input links.

Each content note has description, type, updated, and topics. Types: resource, research, analysis, idea, distilled, deliverable, moc. Non-root notes link to parent MoCs in both frontmatter and a matching Topics footer; those MoCs link back. Root has topics: [] and no self-link. Use portable relative paths and unambiguous wikilinks.

Based on body links identify inputs. Review relevant dependencies bottom-up using checked and reviewed_for; never mass-bump markers. Keep updated unchanged for review-only confirmation. When an input changes, invalidate affected downstream review markers and set affected deliverables to draft, preserving the last checked date. Check coverage against the agreed scope and each deliverable brief; readiness is not approval or publication.

Grounding roles can complement one another and are not mandatory sequential stages. Distill relevant findings when that adds reusable value, then compose self-contained deliverables by assembling or rewriting supported material. Keep actual inputs in Based on links; ordinary Markdown is not live transclusion.

## Publication

- Target vault: {{vault name, or not configured}}
- Target location convention: {{destination folder or mapping, or not configured}}
- Origin locator: {{repository/web locator or Obsidian vault name, or unavailable}}

Publish only on explicit request and when authorized. Each local deliverable maps one-to-one to its own target through a Deliverable link and publication record; multiple deliverables may reuse inputs but have independent target histories. A brief may state an intended target, but it is not a verified publication. Read the target before updating, reconcile target-side edits, and read back after publication before recording it. Do not publish when the destination is not configured. Plain wikilinks are not cross-vault links.

## History

Use existing version control when available. Do not initialize Git or commit without instruction. Frontmatter versions alone do not preserve historical content.
