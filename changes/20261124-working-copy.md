---
change_id: 20261124-working-copy
date: 2026-11-24
branch: bosch/working-copy
status: draft
affected_skills:
  - skill-governance (2.1.0 -> 3.0.0)
  - skill-builder (1.0.0 -> 2.0.0)
  - skill-library-maintenance (retired; merged into skill-governance)
  - hermes-projects (2.1.0 -> 2.1.1)
  - hermes-provider-setup (0.13.6 -> 0.13.7)
  - dossier-project (0.6.0 -> 0.6.1)
  - smart-document-converter (1.1.0 -> 1.1.1)
---

# Change: Simplify Skill Governance & Replace Working-Copy Editing Model

## Goal Statement

Simplify how canonical skills are maintained by replacing the local working-copy ceremony for existing skills with direct in-place editing after user unlock (and Git branching for larger changes), consolidating overlapping governance/maintenance skills into a clean two-skill architecture (`skill-governance` + `skill-builder`), and establishing four unambiguous skill categories.

## Summary

- **No local working copies for existing canonical skills:** Existing canonical skills are unlocked by the user and edited directly in the canonical Git repository (on a branch for larger or multi-skill changes). Local development phases (`baseline: none`) remain valid only for brand-new skills before first publication.
- **Burn-in / self-improvement happens in place:** When a new or heavily refactored canonical skill should learn from real usage (`/refine`), it stays **unlocked** in its canonical repository until stable — never copied into `$HERMES_HOME/skills/` as a shadow.
- **Two-skill split (progressive disclosure):** `skill-library-maintenance` is retired and merged into `skill-governance` (`3.0.0`). `skill-builder` (`2.0.0`) is narrowed strictly to authoring, structure, frontmatter, versioning, and validation.
- **Four skill categories:** `canonical`, `local` (under `$HERMES_HOME/skills/local/`, replacing `own/`), `third-party`, and `hermes` (bundled/Marketplace).
- **Decoupled from project concepts:** Project-specific concepts (`AGENTS.md`, `conventions.md`, `dossier-project`, `authoring-project`, legacy `project-*` skills) are removed from skill governance and reduced to a single boundary statement: project specifics belong in project files, not skills.
- **Simplified permission model + unlock UX:** Lock state is the gate — no separate self-improvement gate machinery. Whenever locked skill(s) must be edited, the agent must output a ready-to-copy-paste block with one `hermes curator unlock <skill>` command per skill and wait.

## Conceptual Deltas (Input for Concept Documentation Update)

### 1. Editing & Lifecycle Model for Canonical Skills

- **Replaced:** The mandatory "one temporary complete working copy in `$HERMES_HOME/skills/`" model for modifying existing canonical skills is retired. Copying packages back and forth and tracking per-skill local overrides proved too complex, especially for multi-skill refactors.
- **New rule (existing skills):**
  - User unlocks target skill(s) via `hermes curator unlock <name>` (one command per skill).
  - Agent edits directly in place in the canonical repository.
  - For larger or multi-skill changes, work happens on a Git branch in the canonical repository rather than `main`.
  - Complete package(s) are reviewed against the Git baseline, committed/merged on explicit authorization, and re-locked.
- **New rule (brand-new skills):**
  - Still start in a profile-local development phase under `$HERMES_HOME/skills/local/<name>/` (`baseline: none`), or directly on a branch in the canonical repository if preferred.
  - Same-name local overrides in declaration audits are now legitimate *only* during the brief publication/close window of a brand-new skill, never for editing an existing one.
- **New rule (burn-in / self-improvement):**
  - If a newly published or heavily refactored canonical skill should temporarily participate in self-improvement (`/refine`), it simply remains **unlocked** in its canonical repository until stable, then gets locked. No local shadow or adaptation copy is created.

### 2. Skill Architecture & Responsibility Split

- **Retired:** `skill-library-maintenance` is removed as a standalone skill; its workflow references (`develop-skill.md`, `review-skill.md`, `publish-skill.md`, `close-development.md`, `update-library.md`, `audit-library.md`), scripts (`audit-skill-library.py`, `audit-skill-declarations.py`), and tests move into `skill-governance`.
- **`skill-governance` (`3.0.0`):** Single owner of skill categories, locking/unlocking, routing, lifecycle workflows, checkout updates, and library audits.
- **`skill-builder` (`2.0.0`):** Single owner of package authoring — format, progressive disclosure, frontmatter (Hermes variant), semantic versioning, safe editing, and structural validation. Governance and lifecycle rules were stripped from `skill-builder` and replaced with pointers to `skill-governance`.

### 3. Taxonomy: Four Skill Categories

The previous three-kind/two-ownership-class split is replaced by four explicit categories:

1. **`canonical`** — User-curated skills in external owned Git repositories (`skills.external_dirs`). Locked by default; self-improvement off unless explicitly unlocked by the user; strict Git versioning and review.
2. **`local`** — Profile-local skills under `$HERMES_HOME/skills/local/` (replaces `own/`). Default destination for agent-created skills (via self-improvement or user request) and brand-new skills before promotion. Self-improvement active by default.
3. **`third-party`** — External Git/`skills.sh` checkouts (`skills.external_dirs`), shared across profiles. Read-only and locked; never edited by the agent (improvements are reported in chat only).
4. **`hermes`** — Profile-local bundled and Marketplace-installed skills, managed by Hermes as intended without user interference.

### 4. Simplified Self-Improvement & Unlock Mechanics

- **Removed:** `self-improvement-boundaries.md` and the multi-layer gate/policy text around self-improvement approval queues.
- **New rule:** The Curator lock is the binary gate. Unlocked = editable (including `/refine`); locked = read-only (report proposed change only).
- **Mandatory unlock command UX:** Whenever an edit requires unlocking one or more skills, the agent must generate a ready-to-copy-paste block with one `hermes curator unlock <skill>` command per skill (the CLI accepts only one skill per call) and wait for confirmation.

### 5. Removal of Project-Domain Coupling & Legacy Adaptation Metadata

- Removed all references to specific project types (`dossier-project`, `authoring-project`), legacy `project-*` skill patterns, and `conventions.md` mechanics from `skill-governance`.
- Retained only the clean boundary: project-specific content lives in the project's own files (e.g. `AGENTS.md`), and volatile instance data lives in dated notes — neither belongs in a skill.
- **Removed legacy adaptation metadata (`metadata.scope: standalone` and `metadata.adapted_from`):** Both fields existed solely to distinguish standalone skills from the retired `adaptations/` model. Removed from `skill-governance`, `skill-builder`, `normalize-skill-frontmatter.py` (`--scope` dropped), and `audit-skill-declarations.py` (now audits collisions, temporary local overrides, and overlap candidates directly without requiring a `scope: standalone` declaration). Also stripped `metadata.scope: standalone` from all remaining canonical skills (`hermes-projects`, `hermes-provider-setup`, `dossier-project`, `smart-document-converter`).

## Notes for Follow-up (Out of Scope Here)

- Existing profile-local skills currently sitting in `$HERMES_HOME/skills/own/` on individual profiles have not been moved to `local/` yet; that is a per-profile cleanup.
- Vault concept documentation (e.g. `projects/hermes-agent/skills/skill-library-maintenance.md` and `+Skills.md`) still reflects the previous working-copy model and can be updated using this change doc as input.
- Lock state on `skill-governance`, `skill-builder`, `hermes-projects`, `hermes-provider-setup`, `dossier-project`, and `smart-document-converter` should be restored after commit/merge (unless kept unlocked intentionally for burn-in).
