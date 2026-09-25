---
name: skill-governance
description: "Use when creating or maintaining reusable skills."
metadata:
  version: "0.5.0"
  source: https://github.com/olafgeibig/skills
  hermes:
    tags:
      - skills
      - governance
      - self-improvement
    related_skills:
      - bosch-skills
      - skill-builder
---

# Skill Governance

This skill is the **generic, ownership-agnostic** rule set for creating, maintaining, and self-improving Hermes skills. It applies to the maintainer's own personal, Bosch, and project skills and tells an improving agent where a new learning must go.

The key stance is **scope discipline**: every improvement is routed either into the skill itself (only if generic and the skill is yours), into a project skill, or into an agent-specific improvement sidecar. Third-party skills are never edited directly.

The Bosch-specific application of these rules lives in `bosch-skills`. Profile- or environment-specific rules belong in the profile's `AGENTS.md` or an explicitly maintained profile-local sidecar. This skill is the shared core.

## When to Use

- "create a new skill"
- "update / patch / improve this skill"
- "a learning happened — where do I put it?"
- "self-improvement wants to edit a skill"
- "fix skill metadata" / "bump skill version"
- "is this skill mine or third-party, and may I edit it?"

## The Two Skill Ownership Classes

Every skill belongs to exactly one class. The class decides whether the skill itself may be edited autonomously.

1. **Own skills** — the maintainer's personal, Bosch, and project skills, kept in their own git repositories. The maintainer wants the agent to keep developing these, but only within these rules and the intended scope of each repository.
2. **Third-party skills** — checked out from another author's git repository and mounted as their own `external_dirs` entry. The maintainer does **not** want the skill itself touched: any change is overwritten on the next `git pull`. These are **never edited directly** — improvements go only to an agent-specific improvement sidecar.

## Decision Matrix: Where an Improvement Goes

When self-improvement (or a user-directed patch) has a learning to capture, classify it by **generality** and **ownership**:

| The learning is… | And the skill is… | Route it to… |
|---|---|---|
| **Generic** (true for any user of the skill) | Own | **The skill itself** (this is the only "shared" tier — the git-versioned skill IS the shared artifact) |
| **Generic** | Third-party | **Never the skill** → an explicitly maintained profile-local adaptation or sidecar |
| **Project-specific** (reusable within one project, not across) | Own | **A project skill** (name starts with `project-`) or project content |
| **Agent-/environment-specific** (this profile, this machine, this setup) | Any | **Profile `AGENTS.md`** or an explicitly maintained profile-local sidecar |
| **Project fact** (architecture, current state, system brief) | Any | **Project repository content** — never a skill |
| **A new skill that narrows, specializes, or extends one existing skill** | Own or third-party | **The owning skill (owned only) or a `<source>-adaptation`** — never a standalone sibling; see the routing gate below |

### The simplification that matters

There is **no separate "shared improvements" tier**. The only generic home for an owned skill is the skill itself. Profile-specific and environment-specific learnings go to profile `AGENTS.md` or an explicitly maintained profile-local sidecar. This keeps the model to two ownership classes and explicit route targets.

## Routing Gate Before Creating a Skill

The matrix above routes a **learning**; a new skill needs the same decision *before* it exists, because the default write goes to the wrong place. `skill_manage(action="create")` creates in the profile-local skills directory unless `skills.create_dir` points elsewhere — creating a skill is therefore not a routing decision, it is the absence of one.

1. **Search for an overlapping skill** across the profile-local directory and every `skills.external_dirs` root. Compare topics and trigger phrases, not only names:
   ```bash
   python3 skills/skill-library-maintenance/scripts/audit-skill-declarations.py --strict
   ```
2. **If the new skill narrows, specializes, or extends an existing skill**, exactly two outcomes are allowed:
   - **Generic rule → the owning skill.** Write the delta into the owning skill (owned repositories only, never a third-party source tree).
   - **Local delta → an adaptation.** `<source-skill>-adaptation` with `metadata.adapted_from`, `metadata.scope: profile-local`, `metadata.hermes.category: adaptations`, and the source listed in `related_skills`.
3. **A standalone profile-local sibling is prohibited** when it quietly duplicates or narrows an existing skill. If the skill genuinely stands alone, say so explicitly: `metadata.scope: standalone` plus `metadata.hermes.related_skills` naming the skills it borders. Undeclared skills are indistinguishable from unnamed adaptations — that is what makes the gap invisible.

### Self-declaration is not a precondition

The prohibitions that apply to adaptations apply to any profile-local skill that *functions* as a local delta or improvement bundle, whether or not it claims the label. "Do not create generic catch-all improvement bundles" and "no nested Git repository for an individual adaptation" bind the artifact, not the declaration — otherwise every rule can be escaped by choosing a different name.

### A generic rule must not live only in an adaptation

An adaptation that accumulates generic rules leaks: the owning skill never learns them and other profiles never receive them. When a finding turns out to be generic (true for any user of the source skill), promote it into the source skill in the same session and leave only the local delta behind. See `references/profile-adaptations.md`.

## Promotion From Sidecars

A sidecar is not a mandatory staging area for improvements to owned skills. Use one only when direct editing is prohibited, the finding is profile-specific, or the owning repository has explicitly chosen a review queue.

Before promoting an existing sidecar entry into a stable skill:

- classify ownership and scope using the decision matrix;
- abstract away personal names, local paths, session dates, one-off tool details, and project facts;
- check whether the target skill already contains the durable rule;
- obtain explicit maintainer approval when the sidecar or repository requires it;
- migrate the rule once, then retire the duplicate sidecar entry.

For an owned skill, a newly discovered generic rule may be written directly to the skill when the user has authorized the change and the repository workflow permits it.

For the normative profile-local storage layout, naming, delta rules, and promotion signals, load `references/profile-adaptations.md`.

## Hard Rules for Any Skill Write

- **Read-before-write (ENFORCED):** before patching or editing an existing `SKILL.md`, load it with `skill_view(name)`. Before overwriting an existing supporting file, load it with `skill_view(name, file_path=...)`. Content quoted earlier in a transcript does **not** count — a fresh load is required.
- Use `skill_manage` for existing skills: it resolves skills across the profile and `skills.external_dirs`, then patches the file in place with native validation, ledger, cache invalidation, and security hooks.
- Before creating a skill, classify its ownership and determine its canonical repository. `skill_manage(action="create")` writes only to the profile-local skills directory or the single configured `skills.create_dir`; it cannot select among several external repositories per call.
- Use `skill_manage(action="create")` only when its resolved creation directory is the intended canonical root. Otherwise create the new files explicitly in the canonical repository with filesystem tools, then validate them, load the skill, verify `_source_path`, and remove or rename any local shadow.
- Use `skill_manage(action="write_file")` for supporting files of an existing skill. Use targeted `skill_manage(action="patch")` or `patch` edits instead of full rewrites.
- See `references/skill-manage-external-directories.md` for the verified behavior, trade-offs, and decision table.
- Verify the saved file by re-reading the frontmatter.
- **Never edit a third-party skill's `SKILL.md`** under any classification — route to the sidecar instead.

## Frontmatter Baseline

Required where the repo convention uses them:

- `name` — lowercase-hyphenated, noun phrase preferred
- `description` — one or two trigger-focused sentences, ends with a period
- `metadata.version` — semantic versioning; bump when the skill itself or its supporting behavior changes
- `metadata.author` — intended human owner when attribution is maintained
- `metadata.source` — the owning git repository URL when one exists
- scope-appropriate `metadata.hermes.tags` and `metadata.hermes.related_skills`

Version rules (semantic):
- **patch** — typo, wording, metadata-only, small clarifications
- **minor** — substantive additive guidance, new sections, new references
- **major** — breaking change in scope, workflow, or expected behavior

Never leave the version unchanged after editing.

## Pitfalls

- Do not route a generic rule only into one domain skill — put it in the generic core so every skill inherits it.
- Do not edit a third-party skill directly just because you loaded it; being in play does not make it editable.
- Do not store project facts in skills — they belong in the project repository content.
- Do not mix agent-specific/environment quirks into a shared generic skill; keep them in profile `AGENTS.md` or an explicitly maintained profile-local sidecar.
- Do not promote from a sidecar without explicit maintainer approval and full abstraction.
- Do not skip the version bump after an edit.
- Do not treat `skill_manage(action="create")` as a routing decision — it writes to the profile-local directory by default, which is where unnamed adaptations accumulate.
- Do not rely on a name convention to keep the rules honest: an undeclared improvement bundle escapes every adaptation rule. The prohibitions bind the artifact, not the label.
- Do not leave a generic rule in a profile-local adaptation because that is where it was discovered — promote it to the owning skill in the same session.

## Verification

- Class confirmed: own vs third-party.
- Route confirmed: the improvement's generality and ownership map to exactly one target in the decision matrix.
- Read-before-write honored (fresh `skill_view` before any edit).
- Version bumped to match change magnitude.
- New skill: the overlap search ran, and the outcome is one of the three declared forms — a delta in the owning skill, a `<source>-adaptation`, or an explicit `metadata.scope: standalone`.
- Saved file re-read and consistent with intent.

## Generic-scope and self-improvement rule

This skill must remain generic across all skill domains.

Do not fold project-specific conventions, one-off repository rules, local terminology, or session-derived specifics into this skill as if they were universal.

Route such content to the correct place instead:
- the relevant project skill or project repository content for project-specific material
- profile `AGENTS.md` or an explicitly maintained profile-local sidecar for agent- or environment-specific quirks

When improving this skill:
- keep only reusable cross-domain governance here
- move domain-specific examples into the owning domain skill (`bosch-skills` for Bosch, or the relevant project skill)
- prefer adding or refining rules that generalize instead of embedding session-derived specifics into the core
