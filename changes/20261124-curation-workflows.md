---
change_id: 20261124-curation-workflows
date: 2026-11-24
branch: edit/governance-workflows
status: reviewed
affected_skills:
  - skill-governance (3.0.0 -> 3.1.0)
  - skill-builder (2.0.0 -> 2.0.1)
---

# Change: Add Curation Workflow Conventions, `wf-*` Naming & Bulk-Lock Helper

## Goal Statement

Make the curation lifecycle in `skill-governance` concrete and traceable across sessions by establishing branch and change-doc conventions (`edit/<slug>`, `improve/<slug>`, `./changes/YYYYMMDD-<slug>.md`), marking procedural workflow references with the `wf-` prefix, making review explicitly iterative with change-doc synchronization, adding sync/lock checks to publication, and providing a user-only bulk lock/unlock helper script for repo-wide Git operations.

## Summary

- **`wf-*` prefix convention:** All six procedural workflow references in `skill-governance/references/` are renamed with the `wf-` prefix (`wf-develop-skill.md`, `wf-review-skill.md`, `wf-publish-skill.md`, `wf-close-development.md`, `wf-update-library.md`, `wf-audit-library.md`), cleanly separating actionable workflows from policy/reference material (`ownership-and-scope.md`, `skill-manage-external-directories.md`). Cross-references in `skill-builder` and `audit-skill-declarations.py` were updated accordingly.
- **Branch & change-doc traceability (`wf-develop-skill.md`):**
  - Targeted edits use `edit/<slug>`; burn-in / self-improvement phases use `improve/<slug>`.
  - Every change opens a change doc at `./changes/YYYYMMDD-<slug>.md` with Goal Statement, Summary, and abstract Conceptual Deltas. No separate `kind` field or second document type is needed because the branch prefix in frontmatter already distinguishes targeted edits from self-improvement phases.
- **Iterative review with change-doc sync (`wf-review-skill.md`):** Review inspects complete packages, `git diff`, and the change doc together, applies stricter scrutiny for project/instance leakage on `improve/*` branches, and explicitly loops (edit → update change doc → re-lint/re-audit → re-review) until approved.
- **Sync check & re-lock output at publish (`wf-publish-skill.md`):** Publication first checks `origin/main` sync state (running `wf-update-library.md` if behind), stages the change doc alongside the skill files, and ends by outputting copy-paste `hermes curator lock <skill>` commands (one per skill, or `bulk-lock.py lock` if bulk-unlocked).
- **Clean update / conflict handling (`wf-update-library.md`) & user-only `bulk-lock.py`:** `wf-update-library.md` distinguishes clean fast-forward from divergence/conflicts. Added `scripts/bulk-lock.py` (`lock` / `unlock`, `--dry-run`, `--profile`), strictly a user-invoked shell helper for repo-wide Git operations or conflict resolution — never called by the agent.

## Conceptual Deltas (Input for Concept Documentation Update)

### 1. Workflow vs. Policy Reference Naming (`wf-*`)

- Procedural step-by-step workflows in `skill-governance/references/` use the `wf-` prefix (matching `vault-ops`), while declarative reference material stays unprefixed.

### 2. Unified Change-Doc Traceability (`./changes/`)

- Every non-trivial canonical skill change or burn-in phase is tracked in `./changes/YYYYMMDD-<slug>.md` in the skills repository.
- Structure: YAML frontmatter (`change_id`, `date`, `branch`, `status`, `affected_skills`), **Goal Statement**, **Summary**, and **Conceptual Deltas** (abstract input for updating concept documentation without reading raw diffs).
- The branch naming convention (`edit/<slug>` vs. `improve/<slug>`) encodes whether the change is a deliberate edit or a self-improvement burn-in phase. No separate `improvements/` folder or `kind:` frontmatter field is introduced.

### 3. Iterative Review & `improve/*` Leakage Gate

- `wf-review-skill.md` is an iterative loop rather than a one-shot gate: every user-discussed revision updates both the skill and its change doc and re-runs validation/linting.
- On `improve/*` branches, review explicitly audits for project- or instance-specific leakage introduced by `/refine` runs.

### 4. Publication Sync & Re-Locking

- `wf-publish-skill.md` commits reviewed changes locally first, then runs `git fetch origin` and checks `HEAD...origin/main`. If `origin/main` has moved ahead, it stops for an explicit user integration decision and re-review (keeping `wf-update-library.md` strictly for clean consuming checkouts).
- At close/publish, re-locking separates two steps: first `bulk-lock.py restore <skills-dir> -p <profile>` if bulk-unlocked (restoring sibling locks from the mid-phase snapshot), then individual `hermes -p <profile> curator lock <skill>` commands for the target skill(s) unlocked at phase start (unless kept unlocked for burn-in), followed by `hermes -p <profile> curator status` verification.

### 5. State-Preserving User-Only Lock Helper (`scripts/bulk-lock.py`)

- Default for repo-root Git operations remains letting the user run Git commands directly without changing locks.
- When the user deliberately wants the agent to perform repo-wide Git/conflict resolution, `scripts/bulk-lock.py unlock <skills-dir>` queries `hermes curator status`, unlocks **only** the skills in that directory that were actually locked, and records them in a state file. `scripts/bulk-lock.py restore <skills-dir>` re-locks only that recorded subset (preserving burn-in unlocked skills) and clears the state file. `bulk-lock.py lock` remains available for explicit full-directory locking. The agent must never invoke `bulk-lock.py unlock`.

### 6. Review Fixes (P1/P2 & Consistency Cleanup)

- **In-place abandon path (`wf-close-development.md`):** Added an explicit published + abandoned workflow for existing canonical skills edited in place: inventories staged, unstaged, and untracked files separately; preserves staged (`git diff --cached --binary HEAD`) and working-tree (`git diff --binary`) patches separately plus untracked files if requested (so staged changes reverted in the working tree are not lost); restores both index and working tree via `git restore --source=HEAD --staged --worktree -- <exact paths>`; verifies source and restores locks.
- **Explicit profile & state-binding in `bulk-lock.py`:** `unlock` and `restore` require `-p/--profile` explicitly (avoiding drift across mutable active-profile defaults) and pass it to every `hermes -p <profile> curator ...` call; snapshots bind both `effective_profile` and resolved `skills_dir`, and `restore` refuses with exit code 2 (without touching locks or deleting the snapshot) if either mismatches.
- **Local create root check (`wf-develop-skill.md`):** Branch B now checks `hermes config get skills.create_dir` before creating a brand-new local skill and falls back to explicit filesystem `write_file` under `$HERMES_HOME/skills/local/<name>/` if `skills.create_dir` points elsewhere.
- Updated stale `skill-builder` step-number references (`step 5` → `step 4`, `step 8` → `step 7`) in `wf-develop-skill.md` and `wf-audit-library.md`.
- Removed remaining `working copy`, `open-development-phases`, and `own/` wording leftovers across `skill-governance` references/tests and `skill-builder` references (`hermes-frontmatter.md`, `profile-skill.md`).
