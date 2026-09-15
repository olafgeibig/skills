# Concept Vault

This directory is one self-contained concept vault. Apply the simple-vault skill. Replace these setup placeholders before adoption; merge with existing instructions rather than overwrite them.

## Scope

- Concept: {{title}}
- Goal: {{purpose and intended outcome}}
- Out of scope: {{boundaries}}
- Documentation language: English

## Structure

INDEX.md is the main MoC and holds the quoted project version. Optional +Topic.md files organize aspects. Working notes live in notes/, conclusions in derived/, publication candidates in concept/, and originals in resources/. Create directories only when used. No area/project hierarchy or mandatory plugins.

Each content note has description, type, updated, and topics. Types: resource, research, analysis, idea, derived, concept, moc. Non-root notes link to parent MoCs in both frontmatter and a matching Topics footer; those MoCs link back. Root has topics: [] and no self-link. Use portable relative paths and unambiguous wikilinks.

Based on body links identify inputs. Review bottom-up using checked and reviewed_for; never mass-bump markers. Keep updated unchanged for review-only confirmation. Invalidate downstream review markers when inputs change, even within the same version. Concept status is draft or ready, separate from publication.

## Publication

- Target vault: {{vault name, or not configured}}
- Target location convention: {{destination folder or mapping, or not configured}}
- Origin locator: {{repository/web locator or Obsidian vault name, or unavailable}}

Publish only on explicit request. Each local concept maps to one target through a Deliverable link and publication record. Read target before updates, reconcile target-side edits, and read back after publication. Do not publish when the destination is not configured. Plain wikilinks are not cross-vault links.

## History

Use existing version control when available. Do not initialize Git or commit without instruction. Frontmatter versions alone do not preserve historical content.
