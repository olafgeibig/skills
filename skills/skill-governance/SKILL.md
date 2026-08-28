---
name: skill-governance
description: "Use this skill whenever creating, maintaining, or self-improving ANY skill, and especially before an agent patches a skill in an external_dirs repository. It defines the two skill ownership classes (own vs third-party), the decision matrix for routing generic / project-specific / agent-specific improvements, and the mandatory read-before-write and promotion-freeze rules. Triggers: skill governance, skill maintenance, self-improvement, improve a skill, patch a skill, update a skill, skill scope, skill ownership."
metadata:
  version: "0.1.0"
  source: https://github.com/olafgeibig/skills
  hermes:
    tags:
      - skills
      - governance
      - self-improvement
    related_skills:
      - bosch-skills
      - vault-improvements
      - skill-builder
---

# Skill Governance

This skill is the **generic, ownership-agnostic** rule set for creating, maintaining, and self-improving Hermes skills. It applies to the maintainer's own skills (personal and Bosch) and tells an improving agent where a new learning must go.

The key stance is **scope discipline**: every improvement is routed either into the skill itself (only if generic and the skill is yours), into a project skill, or into an agent-specific improvement sidecar. Third-party skills are never edited directly.

The Bosch-specific application of these rules lives in `bosch-skills`; the agent-specific improvement container pattern lives in `vault-improvements`. This skill is the shared core.

## When to Use

- "create a new skill"
- "update / patch / improve this skill"
- "a learning happened — where do I put it?"
- "self-improvement wants to edit a skill"
- "fix skill metadata" / "bump skill version"
- "is this skill mine or third-party, and may I edit it?"

## The Two Skill Ownership Classes

Every skill belongs to exactly one class. The class decides whether the skill itself may be edited autonomously.

1. **Own skills** — the maintainer's personal and Bosch skills, kept in their own git repositories (e.g. `personal/skills`, `bosch-skills`). The maintainer wants the agent to keep developing these, but only within these rules (generic changes only).
2. **Third-party skills** — checked out from another author's git repository and mounted as their own `external_dirs` entry. The maintainer does **not** want the skill itself touched: any change is overwritten on the next `git pull`. These are **never edited directly** — improvements go only to an agent-specific improvement sidecar.

## Decision Matrix: Where an Improvement Goes

When self-improvement (or a user-directed patch) has a learning to capture, classify it by **generality** and **ownership**:

| The learning is… | And the skill is… | Route it to… |
|---|---|---|
| **Generic** (true for any user of the skill) | Own | **The skill itself** (this is the only "shared" tier — the git-versioned skill IS the shared artifact) |
| **Generic** | Third-party | **Never the skill** → agent improvement sidecar |
| **Project-specific** (reusable within one project, not across) | Own | **A project skill** (name starts with `project-`) or project content |
| **Agent-/environment-specific** (this profile, this machine, this setup) | Any | **Agent improvement sidecar** (e.g. `vault-improvements`) |
| **Project fact** (architecture, current state, system brief) | Any | **Project repository content** — never a skill |

### The simplification that matters

There is **no separate "shared improvements" tier**. The only generic home is the skill itself. Agent-specific and environment-specific learnings go to the profile-local improvement sidecar. This keeps the model to two skill classes and three route targets — nothing more.

## Promotion Freeze (Stable Core)

- The versioned stable skill must **not** be edited directly just because of a single new learning.
- New learnings, known pitfalls, and discovered workflows go **first** to the improvement sidecar.
- Before anything is promoted from a sidecar into the stable skill, it must be **abstracted**:
  - no personal names
  - no local paths
  - no session dates
  - no one-off tool or environment details
  - no project-specific facts in a generic skill
- **Promotion happens only after explicit maintainer approval.** The agent must never promote unilaterally.

## Hard Rules for Any Skill Write

- **Read-before-write (ENFORCED):** before patching or editing an existing `SKILL.md`, load it with `skill_view(name)`. Before overwriting an existing supporting file, load it with `skill_view(name, file_path=...)`. Content quoted earlier in a transcript does **not** count — a fresh load is required.
- Create new skills and add new supporting files through `skill_manage`; use `skill_manage(action="write_file")` for supporting files.
- Use `patch` for targeted edits to existing skill files.
- Verify the saved file by re-reading the frontmatter.
- **Never edit a third-party skill's `SKILL.md`** under any classification — route to the sidecar instead.

## Frontmatter Baseline

Required where the repo convention uses them:

- `name` — lowercase-hyphenated, noun phrase preferred
- `description` — one or two trigger-focused sentences, ends with a period
- `version` — semantic versioning; bump on every meaningful change
- `metadata.source` — the owning git repository URL
- skope-appropriate `metadata.hermes.tags` and `metadata.hermes.related_skills`

Version rules (semantic):
- **patch** — typo, wording, metadata-only, small clarifications
- **minor** — substantive additive guidance, new sections, new references
- **major** — breaking change in scope, workflow, or expected behavior

Never leave the version unchanged after editing.

## Pitfalls

- Do not route a generic rule only into one domain skill — put it in the generic core so every skill inherits it.
- Do not edit a third-party skill directly just because you loaded it; being in play does not make it editable.
- Do not store project facts in skills — they belong in the project repository content.
- Do not mix agent-specific/environment quirks into a shared generic skill; keep them in the sidecar.
- Do not promote from a sidecar without explicit maintainer approval and full abstraction.
- Do not skip the version bump after an edit.

## Verification

- Class confirmed: own vs third-party.
- Route confirmed: the improvement's generality and ownership map to exactly one target in the decision matrix.
- Read-before-write honored (fresh `skill_view` before any edit).
- Version bumped to match change magnitude.
- Saved file re-read and consistent with intent.

## Generic-scope and self-improvement rule

This skill must remain generic across all skill domains.

Do not fold project-specific conventions, one-off repository rules, local terminology, or session-derived specifics into this skill as if they were universal.

Route such content to the correct place instead:
- the relevant project skill or project repository content for project-specific material
- the agent improvement sidecar (e.g. `vault-improvements`) for agent- or environment-specific quirks

When improving this skill:
- keep only reusable cross-domain governance here
- move domain-specific examples into the owning domain skill (`bosch-skills` for Bosch, or the relevant project skill)
- prefer adding or refining rules that generalize instead of embedding session-derived specifics into the core
