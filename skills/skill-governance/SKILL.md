---
name: skill-governance
description: "Use when the skill concept decides a change."
version: "2.0.0"
author: Olaf Geibig
license: MIT
metadata:
  source: https://github.com/olafgeibig/skills
  hermes:
    tags:
      - skills
      - governance
      - self-improvement
    related_skills:
      - skill-builder
      - skill-library-maintenance
---

# Skill Governance

Where does this knowledge belong, and may the agent write there? Routing, skill kinds and permission — not how a package is written (`skill-builder`), not the development procedure (`skill-library-maintenance`).

The four kinds: **canonical** (owned, git-versioned repository), **profile-local** (one profile's own skill under `$HERMES_HOME/skills/`), **project** (`project-<folder>`), **third-party** (read-only).

## When to Use

"Where do I put this learning?", "create a new skill", "is this even a new skill?", "may I edit this skill?", "self-improvement wants to write — now, or only report?"

## The Two Ownership Classes

1. **Own skills** — personal, project and domain skills in their own git repositories: developed under these rules and the intended scope of each repository.
2. **Third-party skills** — another author's checkout, mounted as an `external_dirs` entry. **Never edited**; a change is overwritten on the next pull. Improvements are **reported**, not written — no sidecar, adaptation or variant name. A maintained fork is a separate, explicitly authorized request (`references/ownership-and-scope.md`), not a learning escape.

## Who Maintains What

- **`$HERMES_HOME/skills/`** — profile-local, discovered unconditionally; the only zone the curator's own stale/archive lifecycle applies to, and only for agent-created packages. Content writes are wider: the background review and `/refine` reach any **unlocked** skill in any root, so a lock — not a directory — is what stops them.
- **Owned repositories under `skills.external_dirs`** — canonical, git-versioned; a released skill is locked, so no agent path writes it and change goes through a development phase.
- **Third-party repositories** — never written. **Consolidation ships off:** the curator archives and prunes, never rewrites content; do not leave a finding for a background pass.

## Released Skills Are Locked

A lock guards content — `skill_manage` cannot patch the package and the file-write guard refuses the same targets — but it neither pins a Git revision nor stops the user updating the checkout. **Released means locked:** a locked owned skill changes only through a **complete working copy** (whole package, same name, recorded baseline, one owner): `skill-library-maintenance` → workflow selector. A project skill outside the release boundary is ordinary authoring, edited where it lives. A skill that is or will be released stays inside the lifecycle even while its phase is open: the unlock opens the **working copy**, not the canonical package, and during a phase only `publish-skill.md` writes that package.

- **Unlocking is the user's action.** The agent states the exact skill name and waits; `hermes curator unlock <name>` is the user's command — no wrapper, relocated command or lock-record edit.
- **A same-name local package is legitimate only as that working copy** — temporary, never a second canonical source or accidental shadow; it leaves discovery once publication is verified.
- **A refused write is the intended state** — no helper, alternate API or relocated command may perform the write the lock refuses.

## Decision Matrix: Where an Improvement Goes

Classify by **generality** and **ownership**; route to exactly one target.

| The learning is… | And the skill is… | Route it to… |
|---|---|---|
| **Generic** (true for any user of the skill) | Own | **The skill itself**, through its development phase |
| **Generic** | Third-party | **Report, do not write** — state the proposed change; never the source tree |
| **Project-specific** | Own | **A project skill** (`project-<folder>`) holding that project's context |
| **Agent-/environment-specific** | Any | **A profile-local skill** in a real directory under `$HERMES_HOME/skills/` |
| **A project fact or a design draft** | Any | **Project repository content** — never a skill; a rule enters a skill only when extracted and approved |
| **A narrowing or extension of an existing skill** | Own / third-party | **The owning skill** (owned only) — a delta inside it, never a parallel sibling; a third-party source is only reported |

A rule discovered while working is routed in the session it arises (see Capture Discipline): generic → the owning skill at its development checkpoint, project-only → the project skill, profile/environment → a profile-local skill. When no phase is open and the target is a released skill, report the finding and propose opening one (`skill-library-maintenance` → `develop-skill.md`); never park it in another skill, memory or a diary. A new original skill is created only for an explicitly intended method with its own owner — not because a review is expected to write something. **`Nothing to save` is a valid outcome.**

## Routing Gate Before Creating a Skill

`skill_manage(action="create")` writes to the profile-local directory, or the single configured `skills.create_dir`; creating a skill is not a routing decision.

1. **Search for an overlapping skill** across the profile-local tree, every `skills.external_dirs` root and the curator archive (`audit-skill-declarations.py --strict`, `hermes curator list-archived`). `.archive/` is skipped by discovery, so a capability that "used to exist" is restored, never re-created; mechanics in `skill-library-maintenance` → `audit-library.md`.
2. **A skill that narrows, specializes or extends an existing one** becomes a delta in the owning skill (owned only) or a report (third-party); never a standalone sibling.
3. **A genuinely standalone skill declares itself**: `metadata.scope: standalone` plus `metadata.hermes.related_skills` naming the skills it borders.

**Self-declaration is not a precondition:** the prohibitions bind what an artifact does, not what it calls itself. A skill needing a new name or scope is renamed or archived as its own decision, never silently replaced by a parallel new skill.

## Review Gate Before Writing to a Canonical Skill

A substantive generic change is reviewed before it is written — as the **package** review of its development phase, not a per-sentence proposal: write in the working copy, review the complete package (`skill-library-maintenance` → `review-skill.md`), publish the reviewed bytes on explicit authorization (`publish-skill.md`).

- **No autonomous write path.** No pipeline, recorded run, merged commit or earlier approval is permission for a different change; a rule found during ordinary work is routed into the owning skill's development phase, not patched into the released package. With no phase open, that is a report and a proposal to open one.
- **No direct-canonical exception for small patches.** A typo or a broken command is a short phase, not an exception.

## Capture Discipline — No Staging Areas

- **Classify and route in the session where the finding arises.** No staging file, batch diary or "collect now, sort later" pile: a pile has no owner, outlives its context and is never reviewed.
- **Search before writing, and keep one home per rule.** A rule stated twice is a defect, not redundancy insurance; search the target for the imperative verb plus domain nouns, repeat before each later write in a series, and verify that a "see X" pointer resolves to a file that carries the content.
- **Write the rule, not the incident.** Dates, IDs, handles and session narration are not knowledge; a finding that only makes sense with its story is project content → the project skill.
- **Profile boundaries are trust boundaries.** Setup knowledge goes to the writing profile's own profile-local skill or its project files, never pooled across profiles or into a shared skill.
- **Keep the shape.** `SKILL.md` carries always-on rules, depth goes to `references/`; respect the runtime budget.

## Volatile Data Has a Note, Not a Skill

Prices, caps, model lists, quota snapshots and dated probe results are volatile instance state: a dated note in the user's knowledge base holds them, with a fetch timestamp and a refresh command — never a skill body, `references/` or memory. The skill keeps the procedure, how to read the data and a pointer to the note; a list inside a skill hardens into a stale claim later sessions trust.

- **A skill is bound by its own placement rule.** When it states where a data kind lives, its own `references/` obey that rule too; a convenience copy beside the note drifts from the source of truth.
- **Re-date the note instead of appending a second one**; re-fetch rather than re-citing an older snapshot.
- **Point generically in a shared skill** — unless every consumer resolves the same path (one vault synced across the user's installations), in which case the concrete pointer may travel. The generic form is for pointers that resolve differently per consumer.

## Rules That Live Elsewhere

- **Frontmatter and version rules** — `skill-builder` step 5 and `skill-builder` → `hermes-frontmatter.md`; **hard write rules** — `skill-builder` step 7.
- **Development, review, publication, close, update** — `skill-library-maintenance` workflow selector.
- **Conditional ownership, fork and project-scope detail, promotion signal** (a second, independent occurrence) — `references/ownership-and-scope.md`.
- **Suggestion, applied write, release publication and the four consent layers** — `references/self-improvement-boundaries.md`; **external directories** — `references/skill-manage-external-directories.md`.

**Never edit a third-party skill's `SKILL.md`** under any classification; report the change instead.

## Pitfalls

- Do not edit a third-party skill just because you loaded it; being in play does not make it editable.
- Do not store project facts, dated prices or environment quirks in a skill or its `references/`, and do not create a staging area, batch diary or dated pitfall file.
- Do not invent a substitute skill, memory entry or diary when no writable target is in scope: report the useful proposed change instead.
- Do not treat a locked skill as an obstacle: bulk-unlocking, editing `.usage.json` or the ledger, relocating the command or hiding the write in a helper are bypasses, not solutions.
- Do not treat `skill_manage(action="create")` as a routing decision, create a project skill without a project, or promote a project-born method on its first occurrence.
- Do not answer a request for a capability that "used to exist" by creating a new skill.

## Verification

- Class confirmed (own/third-party), writable target named, exactly one route from the matrix; a write happens in a working copy of an owned skill, or not at all; no third-party tree touched.
- Frontmatter, version and write rules checked in `skill-builder`; the phase opened and closed per `skill-library-maintenance`; no staging file exists; volatile data lives in a dated note.

## Generic Scope

Stay generic across all skill domains: no project conventions, local terminology or session specifics as universal rules. Domain applications live in the owning domain skill; profile specifics in a profile-local skill.
