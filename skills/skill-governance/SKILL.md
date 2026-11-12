---
name: skill-governance
description: "Use when the skill concept decides a change."
metadata:
  version: "1.0.0"
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

The Bosch-specific application of these rules lives in `bosch-skills`. Profile- or environment-specific rules belong in a **profile-local skill** under `$HERMES_HOME/skills/`. This skill is the shared core.

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

### Taking a third-party skill over as a maintained fork

The sidecar is not the only outcome for the second class. When the maintainer wants the skill itself kept and maintained, it is **forked into the canonical owned repository**, where it becomes an own skill: the source client's execution layer is rewritten for this runtime, upstream is reached only through a separate read-only reference checkout (never a `git remote` of the canonical repository), and a provenance file records the upstream URL, the sync revision, and a per-file class — `verbatim` (byte-identical, listed with its hash, safe to copy over wholesale), `rewritten` (port the upstream diff, never copy), `pending rewrite` (still upstream text, treat as `rewritten`). The class table is what turns a later sync into a per-file decision instead of a remembered one, so a class claim must be true of the file it labels. Layout and sync procedure live in the fork's own provenance file beside the skill.

## Who Maintains What (verified boundaries)

- **`$HERMES_HOME/skills/`** — the profile-local zone. Skills here are discovered unconditionally, and it is the **only** zone an autonomous curator may write to — and only for skills carrying `created_by: "agent"`. The background curator is refused on pinned skills, anything under `skills.external_dirs`, bundled, hub-installed, and user-owned (un-managed) skills.
- **`skills.external_dirs`, owned repositories** — canonical, git-versioned. The curator walk is refused here, and the **background review fork is not** — but a released skill is locked, so the fork cannot patch it either: the lock and the file-write guard refuse the write. With locks in place this zone is effectively writer-free for agents; before any write, read the lock state rather than assuming the fork can reach the file. Route substantive changes through the development phase, and attribute unexpected changes here to the ledger before blaming a session.
- **`skills.external_dirs`, third-party repositories** — never written at all.
- **`curator.consolidate` ships OFF** (`DEFAULT_CONSOLIDATE = False` in `agent/curator.py`). The curator archives and prunes; it does not rewrite skill content. Content consolidation is the agent's job under these rules — never leave something behind expecting a background pass to tidy it.

### Where a standing rule lives

Standing rules that must apply in every session belong in a profile-local skill, because that zone is always discovered. An in-tree `AGENTS.md` (vault or project) is legitimate where the agent works inside that tree — keep it scoped to rules, because the whole file is injected.

- **Instance identity and role live in `$HERMES_HOME/SOUL.md`.** Which machine a profile runs on, and what role it plays in a multi-instance workflow (contributor, maintainer), is identity: declare it in the profile's `SOUL.md`, a prompt source every session loads and scoped to that profile by construction. Keep procedure in skills and volatile assignments (model pins, quotas) in the jobs or config that hold them — a second declarative copy of a role or a pin drifts from the first.

- **Instructions for other agent instances live in a standing reference section, not in a per-session brief or a templated order.** The instance's identity supplies its machine, role and paths at read time; an order template carrying them as variables duplicates the identity layer and drifts from it. The operator's message shrinks to "follow section X of reference Y" — and survives any number of future installations without being rewritten.

### Released Skills Are Locked

Released owned skills stay locked. A lock guards content: the agent cannot patch the package through
`skill_manage`, and the file-write guard refuses the same targets. It does **not** pin a Git revision,
and it does not stop the user from deliberately updating the checkout.

- **A change opens a development phase in a complete profile-local working copy.** The user opens
  the skill, the whole package is copied (not just `SKILL.md`), and the phase records its canonical
  baseline, its target and its one development owner. It ends with a verified publication or an
  explicit abandonment. Procedure: `skill-library-maintenance` →
  `skill-library-maintenance/references/skill-development-lifecycle.md`.
- **A same-name local package is allowed only as that working copy.** It is temporary — not an
  adaptation, not a second canonical source, and never an accidental shadow. Directory and
  frontmatter name stay unchanged, and it leaves active discovery after publication is verified.
- **A background review that meets a locked skill has nothing to do there.** That is a normal state,
  not a reason to open an adaptation or a development phase: classify the finding and route it. The
  lock is not an obstacle to work around, and no helper, alternate API or relocated command may
  perform the write it refuses.

## Decision Matrix: Where an Improvement Goes

When self-improvement (or a user-directed patch) has a learning to capture, classify it by **generality** and **ownership**:

| The learning is… | And the skill is… | Route it to… |
|---|---|---|
| **Generic** (true for any user of the skill) | Own | **The skill itself** (this is the only "shared" tier — the git-versioned skill IS the shared artifact) |
| **Generic** | Third-party | **Never the skill** → an explicitly maintained profile-local adaptation or sidecar |
| **Project-specific** (reusable within one project, not across) | Own | **A project skill** (`project-*`) mirroring the project's own folder — same name, same scope; including lessons that only make sense with that project's context |
| **Agent-/environment-specific** (this profile, this machine, this setup) | Any | **A profile-local skill** in a real directory at `$HERMES_HOME/skills/own/<name>/` (standalone) or `$HERMES_HOME/skills/adaptations/<source>-adaptation/`; declared `metadata.scope: standalone` or `metadata.adapted_from` |
| **A rule discovered while working** (pitfall, correction, new technique) | Any | Classified and routed in the session it arises: generic → the owning skill, at its development checkpoint (`skill-library-maintenance`); project-only → the **project skill**; profile/environment → **profile-local skill**. Never a diary entry — see Capture Discipline |
| **Project fact** (architecture, current state, system brief) | Any | **Project repository content** — never a skill |
| **A design draft or concept document** (proposal, analysis, trade-off study) | Any | **Project repository content** — the project directory, even when its subject is a skill or the shared skill machinery; a rule enters a skill only when extracted and approved |
| **A new skill that narrows, specializes, or extends one existing skill** | Own or third-party | **The owning skill (owned only) or a `<source>-adaptation`** — never a standalone sibling; see the routing gate below |

### The simplification that matters

There is **no separate "shared improvements" tier**. The only generic home for an owned skill is the skill itself. Profile-specific and environment-specific learnings go to a profile-local skill under `$HERMES_HOME/skills/`. This keeps the model to two ownership classes and explicit route targets.

### Where a profile-local skill lives

The own skills of a profile live in the `own/` directory, and the directory decides the category — the loader derives it from the path, so `own/<name>/SKILL.md` is category `own` with nothing to declare. Standing user preferences, environment quirks, and tool knowledge about one setup all land here.

- **Real directories, never symlinks.** The discovery walk uses `rglob("SKILL.md")` and does not descend into symlinked directories: a symlinked skill directory is invisible to `skills_list` and to the Telegram command scan while `skill_view` still loads it — the most confusing "missing skill" there is.
- **Create with `category="own"`.** `skill_manage(action="create", category="own")` writes to `own/<name>/`; without a category it writes to the profile root. Do **not** additionally point `skills.create_dir` at `own/` — the two combine into `own/own/<name>`.
- **An adaptation stays in `adaptations/`.** `own/` is for standalone profile-local skills; a delta against a third-party source belongs in `adaptations/<source>-adaptation/`, which is what the audit script looks for.
- **Declare it anyway.** `metadata.hermes.category: own` plus `metadata.scope: standalone` keeps the frontmatter honest for humans and audits; only the path decides discovery.
- **Description budget: 57 characters.** One trigger sentence. Hermes `create` refuses only above 60; past that the index shows 57 characters plus an ellipsis. Author to 57 so the trigger stays whole. Detail belongs in the body.
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

An adaptation that accumulates generic rules leaks: the owning skill never learns them and other profiles never receive them. When a finding turns out to be generic (true for any user of the source skill), route it into that skill's development phase and leave only the local delta behind. Generic rules have one released canonical home; their review and publication happen at the development checkpoint, not as a mandatory immediate write into a locked source. See `references/profile-adaptations.md`.

## Review Gate Before Writing to a Canonical Skill

A **substantive generic change** to an owned canonical skill is proposed before it is written. The repository is the shared artifact; the review is the point, not a formality after the fact.

Write the proposal as a delta, not a summary:

1. **Target** — skill and file, plus the current section the rule lands in or replaces.
2. **Rule text** — verbatim, imperative plus one clause of why.
3. **Generality** — why this is true for any user of the skill, not only for this profile or project.
4. **Dedupe evidence** — the search showing the rule is not already in the target (see Capture Discipline).
5. **Retirement** — what is removed or replaced, and where the rule is retired from after promotion.

Wait for approval, then write, validate (`./skills/skill-builder/scripts/skills-ref.sh validate ./skills/<name>` from the repository root), bump the version, and commit.

### No autonomous write path

There is no configured pipeline that publishes skill content without a review. Every canonical write
is a foreground change with an explicit authorization for the reviewed bytes; a record of a past run,
a merged commit, or an earlier approval is never permission for a different change. A standing
contributor/maintainer process that integrates unreviewed work on its own schedule is not part of
this model — its implementation is archived, and nothing should be reactivated on the assumption
that it still owns a write path.

An agent that finds a generic rule while working does **not** write it into the released skill. It
routes the rule into that skill's development phase and publishes at the checkpoint described under
*Released Skills Are Locked*.

**Direct, no proposal needed:** fixing a broken command or path, a typo, frontmatter or metadata repair, a version bump, or deleting content that was already agreed. When in doubt, propose — an unwanted proposal costs one message; an unwanted repository write costs a review cycle and a revert.

## Capture Discipline — No Staging Areas

The failure this rule exists for: a profile-local skill that grows one dated `new-pitfalls-<date>-batch.md` file per session beside its own SKILL.md and ends up with ~1 MB of unclassified sediment, in which the same lesson appears many times and almost nothing is generic. It happened because the skill declared itself a staging area and released the agent from consolidating.

- **Classify and route in the session where the finding arises.** No staging file, batch diary, or "collect now, sort later" pile. A pile has no owner, outlives its context, and is never reviewed.
- **Search before writing.** Before adding a rule to any skill, search the target for the same rule — its imperative verb plus domain nouns, with `search_files`. A rule stated twice is a defect, not redundancy insurance. The observed cost of skipping this step: ~22 restatements of rules that were already in the target. Repeat the search before each later write in the same series: the background review turn (see *Who Maintains What*) runs after every assistant turn and can patch or create the target mid-session, so a search made once certifies a file that no longer exists — a series that dedupes only at its start lands the same rule next to the review's copy.
- **Write the rule, not the incident.** Dates, booking or ticket IDs, handles, and session narration are not knowledge. If a finding only makes sense together with its story, it is project content → the project skill.
- **One home per rule.** After promotion, delete the source statement; a rule living in two places drifts. A cross-reference only counts as a home when it resolves — verify the named file carries the content before writing "see X for details"; a pointer at a missing section sends the next agent hunting.
- **A review lesson that names an instance is routed at write time, not at consolidation time.** The writing session classifies before it writes: vault paths, host names, provider quotas, machine tables and one-off workarounds are setup knowledge → the profile-local adaptation (`~/.hermes/skills/adaptations/`, `adapted_from` declared) or the project files; only generic, durable procedure may enter a shared-repository skill. There is no automatic scan behind you to catch what slipped through — the routing decision belongs to the instance that knows the context.
- **Adaptations are profile-scoped — never pool them across profiles.** On a machine that runs several profiles (work vs private), the adaptation lives in that profile's `$HERMES_HOME`: attribute a pending write by its ledger `evidence.session_id` and route the lesson to the *writing* profile's adaptation. A profile boundary is a trust boundary — pooled adaptations leak one profile's setup knowledge into another's sessions.
- **Keep the shape.** `SKILL.md` carries always-on rules, depth goes to `references/`. Respect the repository budget (~500 lines) and the runtime budget (~24k chars — the whole body is loaded for the rest of the session). Route content out rather than growing the file.

## Volatile Data Has a Note, Not a Skill

Prices, caps, model lists, quota snapshots, and dated probe results are volatile instance state: a **dated note in the user's knowledge base** holds them, with a fetch-time stamp and a refresh command — never a skill body, `references/`, or memory. The skill keeps the procedure, how to read the data, and a pointer to the note. Why: a list in a skill hardens into a stale claim later sessions trust as current.

- **A skill is bound by its own placement rule** — when it states where a data kind lives, its own `references/` obey it too; a convenience copy beside the note drifts from the source of truth.
- **Re-date the note instead of appending a second one**; re-fetch rather than re-citing an older snapshot.
- **Point generically in a shared skill.** "A dated note in the user's knowledge base" travels; a vault name, note path, or local script path is an instance pointer and lives in that setup's profile-local skill — unless every consumer of the skill resolves the same path (one vault synced across the user's installations), in which case the concrete pointer may travel. The generic form is for pointers that resolve differently per consumer.

## Promotion From Sidecars

A sidecar is not a mandatory staging area for improvements to owned skills. Use one only when direct editing is prohibited, the finding is profile-specific, or the owning repository has explicitly chosen a review queue.

Before promoting an existing sidecar entry into a stable skill:

- classify ownership and scope using the decision matrix;
- abstract away personal names, local paths, session dates, one-off tool details, and project facts;
- check whether the target skill already contains the durable rule;
- obtain explicit maintainer approval when the sidecar or repository requires it;
- migrate the rule once, then retire the duplicate sidecar entry.

**Promotion needs a second, independent occurrence.** A method, checklist, or script developed for one project is not evidence of a generic capability — it is evidence of one use. Promote it into an owned canonical skill when a *second, independent* consumer appears (another project, another domain, another profile), not on the first occurrence: a rule promoted on a guess lands in the shared artifact and has to be maintained there forever. Until then it lives in the project skill that uses it.

For an owned skill, a newly discovered generic rule goes through that skill's development phase: it is
refined in the working copy, reviewed as a package, and published on authorization. "The user
authorized the change" is satisfied by approving that reviewed package — not by a general mandate to
keep a repository tidy.

**Consent has four distinct layers.** Lock state (may this content be edited at all), adoption (does
the Curator manage this package's lifecycle), pinning (does it survive lifecycle transitions and
deletion), and write approval (may this specific change land) are separate permissions; holding one
implies none of the others. A substantive change is approved as a coherent reviewed package or plan —
individual micro-edits inside that authorization do not need a second interview, but a later content
change or a wider scope does.

For the normative profile-local storage layout, naming, delta rules, and promotion signals, load `references/profile-adaptations.md`.

## Hard Rules for Any Skill Write

- **Read-before-write (ENFORCED):** before patching or editing an existing `SKILL.md`, load it with `skill_view(name)`. Before overwriting an existing supporting file, load it with `skill_view(name, file_path=...)`. Content quoted earlier in a transcript does **not** count — a fresh load is required.
- Use `skill_manage` for existing skills: it resolves skills across the profile and `skills.external_dirs`, then patches the file in place with native validation, ledger, cache invalidation, and security hooks. While a same-name local working copy is active, the bare name resolves to **that** copy — do not treat it as targeting the released package.
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
- Do not name a new mechanism after an existing Hermes subsystem (the Skill Curator, its ledger, its CLI): a word collision causes real mis-attributions in reports and commits before anyone notices the mistake — pick a distinct word family for your own machinery, and apply it in code, docs and commit messages alike.
- The user's word family is canonical; a spec's or an earlier draft's coined synonyms are not. When he names the vocabulary for a concept (roles, actions), that is the naming authority — adopt it across code, CLI, config keys, docs, scheduled jobs and concept documents alike and retire the coined alternatives everywhere: two vocabularies for one concept split every future grep and mislead every reader. Prefer the established name at design time over a fresh coinage: renaming a concept the operator has already configured costs a config edit on every machine and profile he runs. A vocabulary rename is mechanical: inventory every surface first (identifiers, CLI strings, config keys, docs, job names and prompts, vault notes), preserve terms that are intentionally distinct domain vocabulary (a Git state word is not a role name), sweep, then rerun the suite. The sweep surface is the whole configured library plus the user's concept documents, not the change's path allowlist — a rename that ships inside one package's allowlist leaves sibling skills in the same repository stale — and the inventory must match derived word forms (the verb behind a renamed noun, its -ing form), which noun-only patterns miss and which leave headings and prose describing the retired concept. An already-landed change archive may stay stale only on the user's explicit choice. Post-rename breakage means the sweep missed a surface, not that the vocabulary was wrong.
- Do not put a version in an artifact directory name (`<tool>-v2`-style store, cache or config paths). The directory outlives any single version — the version belongs in metadata or content — and a versioned path forks every config that points at it and forces a migration at each bump. A file that IS one release artifact may carry a version; a path other artifacts reference must not.
- Do not couple shared machinery's writes to one knowledge-base write API (a vault handle, a note-write protocol) when a plain file at a configured path does the same job: the coupling hardcodes deployment data into the tool and turns every relocation into a code change. The tool writes and verifies plain files; the deployment config names the destination.
- Do not park a design draft in a skill's `references/` because its topic is that skill's territory — placement follows the artefact's role (a draft is project content until a rule is extracted and approved), not its subject.
- Do not keep a dated price, cap, or model table in a skill or its `references/` — the dated note holds the numbers, the skill holds the procedure and the pointer.
- Do not mix agent-specific/environment quirks into a shared generic skill; keep them in a profile-local skill under `$HERMES_HOME/skills/`.
- Do not create a staging area, batch diary, or dated pitfall file — not in a skill, not in `references/`. Classify in the session, or lose the finding.
- Do not write a rule into a canonical repository skill outside its development phase — there is no autonomous integration path, and no assumption that a background pass will consolidate the result: consolidation ships off and the curator's maintenance walk never touches `skills.external_dirs`.
- Do not treat a locked skill as an obstacle: a refused write is the intended state. Bulk-unlocking siblings, editing `.usage.json` or the ledger, relocating the command or hiding the write in a helper are all bypasses, not solutions.
- Do not promote from a sidecar without explicit maintainer approval and full abstraction.
- Do not skip the version bump after an edit.
- Do not treat `skill_manage(action="create")` as a routing decision — it writes to the profile-local directory by default, which is where unnamed adaptations accumulate.
- Do not rely on a name convention to keep the rules honest: an undeclared improvement bundle escapes every adaptation rule. The prohibitions bind the artifact, not the label.
- Do not leave a generic rule in a profile-local adaptation because that is where it was discovered — promote it to the owning skill in the same session.
- Do not create a project skill without a project to anchor it, and do not inventory notes in one — the MoC is the source of truth, and a note list in a skill drifts from the first rename.
- Do not promote a project-born method into an owned canonical skill on its first occurrence — one consumer is not a signal, a second independent one is.
- Do not answer a request for a capability that "used to exist" by creating a new skill — run `hermes curator list-archived` first; archived skills are invisible to discovery, and nothing restores them automatically.
- Do not design a skill-storage or ownership layout on assumed curator semantics — probe each verb (lock, adopt, pin, archive) on a disposable profile with the real CLI and read the state back first; the verbs differ by target location, and one blanket assumption misroutes the architecture.

## Verification

- Class confirmed: own vs third-party.
- Route confirmed: the improvement's generality and ownership map to exactly one target in the decision matrix.
- Read-before-write honored (fresh `skill_view` before any edit).
- Version bumped to match change magnitude.
- New skill: the overlap search ran, and the outcome is one of the three declared forms — a delta in the owning skill, a `<source>-adaptation`, or an explicit `metadata.scope: standalone`.
- Canonical write: the reviewed package was authorized before the write, and the released skill is locked again afterwards. No integration pipeline, recorded run or prior approval stands in for that authorization.
- Capture: the rule was searched against the target first, and no staging, batch, or diary file was created.
- Data placement: volatile reference data went to a dated note with a refresh command; the skill carries procedure and a generic pointer only.
- Route: a project-only finding landed in the project skill, not in a generic one.
- Project route: the skill mirrors exactly one project folder by name, carries no note inventory, and any method it holds has not been promoted on its first occurrence.
- Saved file re-read and consistent with intent.

## Generic-scope and self-improvement rule

This skill must remain generic across all skill domains.

Do not fold project-specific conventions, one-off repository rules, local terminology, or session-derived specifics into this skill as if they were universal.

Route such content to the correct place instead:
- the relevant project skill or project repository content for project-specific material
- a profile-local skill under `$HERMES_HOME/skills/` for agent- or environment-specific quirks

When improving this skill:
- keep only reusable cross-domain governance here
- move domain-specific examples into the owning domain skill (`bosch-skills` for Bosch, or the relevant project skill)
- prefer adding or refining rules that generalize instead of embedding session-derived specifics into the core
