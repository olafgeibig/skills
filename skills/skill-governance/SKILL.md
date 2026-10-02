---
name: skill-governance
description: "Use when creating or maintaining reusable skills."
metadata:
  version: "0.11.0"
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

The Bosch-specific application of these rules lives in `bosch-skills`. Profile- or environment-specific rules belong in a **profile-local skill** under `$HERMES_HOME/skills/`. A profile `AGENTS.md` is not an option — Hermes never loads `$HERMES_HOME/AGENTS.md` (see "Who Maintains What"). This skill is the shared core.

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

## Who Maintains What (verified boundaries)

- **`$HERMES_HOME/skills/`** — the profile-local zone. Skills here are discovered unconditionally, and it is the **only** zone an autonomous curator may write to — and only for skills carrying `created_by: "agent"`. The background curator is refused on pinned skills, anything under `skills.external_dirs`, bundled, hub-installed, and user-owned (un-managed) skills.
- **`skills.external_dirs`, owned repositories** — canonical, git-versioned, maintainer-only. Neither the curator nor an autonomous pass writes here; every change goes through the review gate below.
- **`skills.external_dirs`, third-party repositories** — never written at all.
- **`curator.consolidate` ships OFF** (`DEFAULT_CONSOLIDATE = False` in `agent/curator.py`). The curator archives and prunes; it does not rewrite skill content. Content consolidation is the agent's job under these rules — never leave something behind expecting a background pass to tidy it.

### Where a profile-local rule actually gets injected

Hermes builds its context files from the **working-directory tree** (git root → cwd) only: `AGENTS.md` / `AGENTS.override.md`, `CLAUDE.md` (cwd), `.cursorrules`, `SOUL.md`. `$HERMES_HOME/AGENTS.md` is never read. Consequences:

- Standing rules that must apply in *every* session belong in a profile-local skill, because that zone is always discovered.
- An `AGENTS.md` works where the agent actually works inside that tree — a vault or project `AGENTS.md` is legitimate and load-bearing. A "profile `AGENTS.md`" is not a destination that exists.
- An in-tree `AGENTS.md` is simultaneously injected context and ordinary content of that tree — indexed alongside everything else and possibly an orphan note with no inbound links. Keep it scoped to rules — the whole file is injected into every session working in that tree.

## Decision Matrix: Where an Improvement Goes

When self-improvement (or a user-directed patch) has a learning to capture, classify it by **generality** and **ownership**:

| The learning is… | And the skill is… | Route it to… |
|---|---|---|
| **Generic** (true for any user of the skill) | Own | **The skill itself** (this is the only "shared" tier — the git-versioned skill IS the shared artifact) |
| **Generic** | Third-party | **Never the skill** → an explicitly maintained profile-local adaptation or sidecar |
| **Project-specific** (reusable within one project, not across) | Own | **A project skill** (`project-*`) mirroring the project's own folder — same name, same scope; including lessons that only make sense with that project's context |
| **Agent-/environment-specific** (this profile, this machine, this setup) | Any | **A profile-local skill** in a real directory at `$HERMES_HOME/skills/own/<name>/` (standalone) or `$HERMES_HOME/skills/adaptations/<source>-adaptation/`; declared `metadata.scope: standalone` or `metadata.adapted_from` |
| **A rule discovered while working** (pitfall, correction, new technique) | Any | Classified and routed in the session it arises: generic → the owning skill (review gate); project-only → the **project skill**; profile/environment → **profile-local skill**. Never a diary entry — see Capture Discipline |
| **Project fact** (architecture, current state, system brief) | Any | **Project repository content** — never a skill |
| **A new skill that narrows, specializes, or extends one existing skill** | Own or third-party | **The owning skill (owned only) or a `<source>-adaptation`** — never a standalone sibling; see the routing gate below |

### The simplification that matters

There is **no separate "shared improvements" tier**. The only generic home for an owned skill is the skill itself. Profile-specific and environment-specific learnings go to a profile-local skill under `$HERMES_HOME/skills/`. This keeps the model to two ownership classes and explicit route targets.

### Where a profile-local skill lives

The own skills of a profile live in the `own/` directory, and the directory decides the category — the loader derives it from the path, so `own/<name>/SKILL.md` is category `own` with nothing to declare. Standing user preferences, environment quirks, and tool knowledge about one setup all land here.

- **Real directories, never symlinks.** The discovery walk uses `rglob("SKILL.md")` and does not descend into symlinked directories: a symlinked skill directory is invisible to `skills_list` and to the Telegram command scan while `skill_view` still loads it — the most confusing "missing skill" there is.
- **Create with `category="own"`.** `skill_manage(action="create", category="own")` writes to `own/<name>/`; without a category it writes to the profile root. Do **not** additionally point `skills.create_dir` at `own/` — the two combine into `own/own/<name>`.
- **An adaptation stays in `adaptations/`.** `own/` is for standalone profile-local skills; a delta against a third-party source belongs in `adaptations/<source>-adaptation/`, which is what the audit script looks for.
- **Declare it anyway.** `metadata.hermes.category: own` plus `metadata.scope: standalone` keeps the frontmatter honest for humans and audits; only the path decides discovery.
- **Description budget: 60 characters.** `skill_manage(action="create")` refuses longer descriptions, because the skill index truncates them to 57 chars plus an ellipsis and the routing signal is destroyed. A long description is a routing defect — the detail belongs in the body.
- **Frontmatter dialect.** `metadata.version` and `metadata.author` (the strict agentskills validator rejects top-level `version`/`author`, and flow-style lists such as `tags: [a, b]`); `platforms:` stays top-level because Hermes gates on it even though the strict spec does not know the field.

### The project route: one skill per project

A project skill is the route that is easiest to get wrong, because "project" is not a scope you can feel — either the project has an anchor or it does not.

- **One skill per project, named after the project folder.** `project-<folder>` mirrors the project's canonical folder (vault project folder, work tree) one-to-one. No project skill without a project to anchor it; no actively used project without a skill.
- **Confirm the naming bundle before the first write.** Before creating a project skill, confirm in one message: the skill name (`project-<folder>`), the project folder, and the naming elements derived from the same root (folder path, display name, note prefix, tag, MoC filename, language). The values are downstream-coupled — correcting the root after the write means rewriting every file that mirrored it, so bundle the checks; never create first and correct later.
- **No note inventory.** The project's MoC is the single source for what exists and what is open. A skill that lists notes, tasks, or contacts duplicates the MoC and drifts from the first rename.
- **What the skill does carry:** location and naming conventions, the load triggers, the stable situation (who/what, and which open decision shapes the work), the working rules for that project, and the methodology developed inside it.
- **Methods discovered inside a project stay inside that project skill** as `references/` or `scripts/` until a second, independent consumer exists — see Promotion From Sidecars.
- **A method is not generic because it is method-shaped.** A source ladder, checklist, or analysis script written while working one project is that project's procedure, not a shared capability.

## Routing Gate Before Creating a Skill

The matrix above routes a **learning**; a new skill needs the same decision *before* it exists, because the default write goes to the wrong place. `skill_manage(action="create")` creates in the profile-local skills directory unless `skills.create_dir` points elsewhere — creating a skill is therefore not a routing decision, it is the absence of one.

1. **Search for an overlapping skill** across the profile-local directory, every `skills.external_dirs` root, and the curator archive. Compare topics and trigger phrases, not only names:
   ```bash
   python3 skills/skill-library-maintenance/scripts/audit-skill-declarations.py --strict
   hermes curator list-archived
   ```
   Include the archive because `.archive/` is skipped by discovery: an archived skill is invisible to `skills_list` and `skill_view`, and `skill_manage(action="create")` refuses only a name that exists in the **active** tree. Nothing restores automatically — curator transitions only run forward (active → stale → archived) and `hermes curator restore <name>` is the sole way back — so a capability that "used to exist" is recovered, never re-created. A consolidated umbrella names its archived members in `umbrella_of`; mechanics in `skill-library-maintenance` ‣ Archived Skills.
2. **If the new skill narrows, specializes, or extends an existing skill**, exactly two outcomes are allowed:
   - **Generic rule → the owning skill.** Write the delta into the owning skill (owned repositories only, never a third-party source tree).
   - **Local delta → an adaptation.** `<source-skill>-adaptation` with `metadata.adapted_from`, `metadata.scope: profile-local`, `metadata.hermes.category: adaptations`, and the source listed in `related_skills`.
3. **A standalone profile-local sibling is prohibited** when it quietly duplicates or narrows an existing skill. If the skill genuinely stands alone, say so explicitly: `metadata.scope: standalone` plus `metadata.hermes.related_skills` naming the skills it borders. Undeclared skills are indistinguishable from unnamed adaptations — that is what makes the gap invisible.

- **An existing skill that needs a new name or scope is renamed or archived — never silently replaced by a parallel new skill.** Rename in place while its content stays useful (default); archive only when the content is fully superseded or migrated. A rename is create + delete plus the 5-location sweep — canonical repository, installed copy, sibling `related_skills` entries, bundles, lock files — and a check that the old name no longer resolves; mechanics in `skill-library-maintenance`.

### Self-declaration is not a precondition

The prohibitions that apply to adaptations apply to any profile-local skill that *functions* as a local delta or improvement bundle, whether or not it claims the label. "Do not create generic catch-all improvement bundles" and "no nested Git repository for an individual adaptation" bind the artifact, not the declaration — otherwise every rule can be escaped by choosing a different name.

### A generic rule must not live only in an adaptation

An adaptation that accumulates generic rules leaks: the owning skill never learns them and other profiles never receive them. When a finding turns out to be generic (true for any user of the source skill), promote it into the source skill in the same session and leave only the local delta behind. See `references/profile-adaptations.md`.

## Review Gate Before Writing to a Canonical Skill

A **substantive generic change** to an owned canonical skill is proposed before it is written. The repository is the shared artifact; the review is the point, not a formality after the fact.

Write the proposal as a delta, not a summary:

1. **Target** — skill and file, plus the current section the rule lands in or replaces.
2. **Rule text** — verbatim, imperative plus one clause of why.
3. **Generality** — why this is true for any user of the skill, not only for this profile or project.
4. **Dedupe evidence** — the search showing the rule is not already in the target (see Capture Discipline).
5. **Retirement** — what is removed or replaced, and where the rule is retired from after promotion.

Wait for approval, then write, validate (`./skills/skill-builder/scripts/skills-ref.sh validate ./skills/<name>` from the repository root), bump the version, and commit.

**Direct, no proposal needed:** fixing a broken command or path, a typo, frontmatter or metadata repair, a version bump, or deleting content that was already agreed. When in doubt, propose — an unwanted proposal costs one message; an unwanted repository write costs a review cycle and a revert.

## Capture Discipline — No Staging Areas

The failure this rule exists for: a profile-local skill that grows one dated `new-pitfalls-<date>-batch.md` file per session beside its own SKILL.md and ends up with ~1 MB of unclassified sediment, in which the same lesson appears many times and almost nothing is generic. It happened because the skill declared itself a staging area and released the agent from consolidating.

- **Classify and route in the session where the finding arises.** No staging file, batch diary, or "collect now, sort later" pile. A pile has no owner, outlives its context, and is never reviewed.
- **Search before writing.** Before adding a rule to any skill, search the target for the same rule — its imperative verb plus domain nouns, with `search_files`. A rule stated twice is a defect, not redundancy insurance. The observed cost of skipping this step: ~22 restatements of rules that were already in the target.
- **Write the rule, not the incident.** Dates, booking or ticket IDs, handles, and session narration are not knowledge. If a finding only makes sense together with its story, it is project content → the project skill.
- **One home per rule.** After promotion, delete the source statement; a rule living in two places drifts.
- **Keep the shape.** `SKILL.md` carries always-on rules, depth goes to `references/`. Respect the repository budget (~500 lines) and the runtime budget (~24k chars — the whole body is loaded for the rest of the session). Route content out rather than growing the file.

## Promotion From Sidecars

A sidecar is not a mandatory staging area for improvements to owned skills. Use one only when direct editing is prohibited, the finding is profile-specific, or the owning repository has explicitly chosen a review queue.

Before promoting an existing sidecar entry into a stable skill:

- classify ownership and scope using the decision matrix;
- abstract away personal names, local paths, session dates, one-off tool details, and project facts;
- check whether the target skill already contains the durable rule;
- obtain explicit maintainer approval when the sidecar or repository requires it;
- migrate the rule once, then retire the duplicate sidecar entry.

**Promotion needs a second, independent occurrence.** A method, checklist, or script developed for one project is not evidence of a generic capability — it is evidence of one use. Promote it into an owned canonical skill when a *second, independent* consumer appears (another project, another domain, another profile), not on the first occurrence: a rule promoted on a guess lands in the shared artifact and has to be maintained there forever. Until then it lives in the project skill that uses it.

For an owned skill, a newly discovered generic rule goes through the review gate above: propose the delta, obtain approval, then write it. "The user authorized the change" is satisfied by approving that specific delta — not by a general mandate to keep a repository tidy.

For the normative profile-local storage layout, naming, delta rules, and promotion signals, load `references/profile-adaptations.md`.

## Hard Rules for Any Skill Write

- **Read-before-write (ENFORCED):** before patching or editing an existing `SKILL.md`, load it with `skill_view(name)`. Before overwriting an existing supporting file, load it with `skill_view(name, file_path=...)`. Content quoted earlier in a transcript does **not** count — a fresh load is required.
- Use `skill_manage` for existing skills: it resolves skills across the profile and `skills.external_dirs`, then patches the file in place with native validation, ledger, cache invalidation, and security hooks.
- Before creating a skill, classify its ownership and determine its canonical repository. `skill_manage(action="create")` writes only to the profile-local skills directory or the single configured `skills.create_dir`; it cannot select among several external repositories per call.
- Use `skill_manage(action="create")` only when its resolved creation directory is the intended canonical root. Otherwise create the new files explicitly in the canonical repository with filesystem tools, then validate them, load the skill, verify `_source_path`, and remove or rename any local shadow.
- Use `skill_manage(action="write_file")` for supporting files of an existing skill. Use targeted `skill_manage(action="patch")` or `patch` edits instead of full rewrites.
- See `references/skill-manage-external-directories.md` for the verified behavior, trade-offs, and decision table.
- **Reference steps must be literally executable.** Write each workflow step as the exact call the agent should make; never nest a tool call inside another tool call's argument (`write(content=fetch(url))`). A pseudo-code fragment in a reference gets copied and fails at runtime — split nested operations into sequential steps.
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
- Do not mix agent-specific/environment quirks into a shared generic skill; keep them in a profile-local skill under `$HERMES_HOME/skills/`.
- Do not create a staging area, batch diary, or dated pitfall file — not in a skill, not in `references/`. Classify in the session, or lose the finding.
- Do not route anything to a profile `AGENTS.md`: Hermes never loads `$HERMES_HOME/AGENTS.md`. Use a profile-local skill.
- Do not write a rule into a canonical repository skill without the review gate, and do not assume the curator will consolidate the result — consolidation ships off and the curator never touches `skills.external_dirs`.
- Do not promote from a sidecar without explicit maintainer approval and full abstraction.
- Do not skip the version bump after an edit.
- Do not treat `skill_manage(action="create")` as a routing decision — it writes to the profile-local directory by default, which is where unnamed adaptations accumulate.
- Do not rely on a name convention to keep the rules honest: an undeclared improvement bundle escapes every adaptation rule. The prohibitions bind the artifact, not the label.
- Do not leave a generic rule in a profile-local adaptation because that is where it was discovered — promote it to the owning skill in the same session.
- Do not create a project skill without a project to anchor it, and do not inventory notes in one — the MoC is the source of truth, and a note list in a skill drifts from the first rename.
- Do not promote a project-born method into an owned canonical skill on its first occurrence — one consumer is not a signal, a second independent one is.
- Do not answer a request for a capability that "used to exist" by creating a new skill — run `hermes curator list-archived` first; archived skills are invisible to discovery, and nothing restores them automatically.

## Verification

- Class confirmed: own vs third-party.
- Route confirmed: the improvement's generality and ownership map to exactly one target in the decision matrix.
- Read-before-write honored (fresh `skill_view` before any edit).
- Version bumped to match change magnitude.
- New skill: the overlap search ran, and the outcome is one of the three declared forms — a delta in the owning skill, a `<source>-adaptation`, or an explicit `metadata.scope: standalone`.
- Canonical write: the delta proposal (target, rule text, generality, dedupe evidence, retirement) was approved before the write.
- Capture: the rule was searched against the target first, and no staging, batch, or diary file was created.
- Route: a project-only finding landed in the project skill, not in a generic one.
- Project route: the skill mirrors exactly one project folder by name, carries no note inventory, and any method it holds has not been promoted on its first occurrence.
- Saved file re-read and consistent with intent.

## Generic-scope and self-improvement rule

This skill must remain generic across all skill domains.

Do not fold project-specific conventions, one-off repository rules, local terminology, or session-derived specifics into this skill as if they were universal.

Route such content to the correct place instead:
- the relevant project skill or project repository content for project-specific material
- a profile-local skill under `$HERMES_HOME/skills/` for agent- or environment-specific quirks (never `$HERMES_HOME/AGENTS.md`, which Hermes does not load)

When improving this skill:
- keep only reusable cross-domain governance here
- move domain-specific examples into the owning domain skill (`bosch-skills` for Bosch, or the relevant project skill)
- prefer adding or refining rules that generalize instead of embedding session-derived specifics into the core
