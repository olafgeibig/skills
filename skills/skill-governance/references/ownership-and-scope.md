# Ownership and Scope

Load this when a routing question needs more than the decision matrix: a third-party skill might be
maintained as a fork, a standing rule needs a home, a profile-local or project skill is being
placed, or a rule seems ready to leave the scope where it was found.

## Taking a third-party skill over as a maintained fork

When the maintainer wants a third-party skill itself kept and maintained, it is **forked into the
canonical owned repository**, where it becomes an own skill: the source client's execution layer is
rewritten for this runtime, upstream is reached only through a separate read-only reference checkout
(never a `git remote` of the canonical repository), and a provenance file records the upstream URL,
the sync revision, and a per-file class — `verbatim` (byte-identical, listed with its hash, safe to
copy over wholesale), `rewritten` (port the upstream diff, never copy), `pending rewrite` (still
upstream text, treat as `rewritten`). The class table is what turns a later sync into a per-file
decision instead of a remembered one, so a class claim must be true of the file it labels. Layout and
sync procedure live in the fork's own provenance file beside the skill.

The fork is a separate, explicitly authorized request. Ordinary learning never starts one: until it
is asked for, a third-party source stays read-only and its improvements are reported.

## Where a standing rule lives

Standing rules that must apply in every session belong in a profile-local skill, because that zone is
always discovered. An in-tree `AGENTS.md` (vault or project) is legitimate where the agent works inside
that tree — keep it scoped to rules, because the whole file is injected.

- **Instance identity and role live in `$HERMES_HOME/SOUL.md`.** Which machine a profile runs on, and
  what role it plays in a multi-instance workflow (contributor, maintainer), is identity: declare it
  in the profile's `SOUL.md`, a prompt source every session loads and scoped to that profile by
  construction. Keep procedure in skills and volatile assignments (model pins, quotas) in the jobs or
  config that hold them — a second declarative copy of a role or a pin drifts from the first.
- **Instructions for other agent instances live in a standing reference section, not in a per-session
  brief or a templated order.** The instance's identity supplies its machine, role and paths at read
  time; an order template carrying them as variables duplicates the identity layer and drifts from it.
  The operator's message shrinks to "follow section X of reference Y" — and survives any number of
  future installations without being rewritten.

## Where a profile-local skill lives

The own skills of a profile live in the `own/` directory, and the directory decides the category — the
loader derives it from the path, so `own/<name>/SKILL.md` is category `own` with nothing to declare.
Standing user preferences, environment quirks and tool knowledge about one setup all land here.

- **Real directories, never symlinks.** The discovery walk uses `rglob("SKILL.md")` and does not
  descend into symlinked directories: a symlinked skill directory is invisible to `skills_list` and to
  the Telegram command scan while `skill_view` still loads it — the most confusing "missing skill"
  there is.
- **Create with `category="own"`.** `skill_manage(action="create", category="own")` writes to
  `own/<name>/`; without a category it writes to the profile root. Do **not** additionally point
  `skills.create_dir` at `own/` — the two combine into `own/own/<name>`.
- **Declare it anyway.** `metadata.hermes.category: own` plus `metadata.scope: standalone` keeps the
  frontmatter honest for humans and audits; only the path decides discovery.

**Legacy `adaptations/` path.** `$HERMES_HOME/skills/adaptations/<source>-adaptation/` is a historical
layout, not an active convention: nothing new is created there and a lock is never evaded by
re-creating a package under that path. Existing `metadata.adapted_from` records are read diagnostically
by the declaration audit — readability, not permission to create another skill. A local delta that is
still needed belongs in the owning skill's development phase, not in a new adaptation.

## The project route: one skill per project

A project skill is the route that is easiest to get wrong, because "project" is not a scope you can
feel — either the project has an anchor or it does not.

- **One skill per project, named after the project folder.** `project-<folder>` mirrors the project's
  canonical folder (vault project folder, work tree) one-to-one. No project skill without a project to
  anchor it; no actively used project without a skill.
- **Confirm the naming bundle before the first write.** Before creating a project skill, confirm in one
  message: the skill name (`project-<folder>`), the project folder, and the naming elements derived
  from the same root (folder path, display name, note prefix, tag, MoC filename, language). The values
  are downstream-coupled — correcting the root after the write means rewriting every file that mirrored
  it, so bundle the checks; never create first and correct later.
- **No note inventory.** The project's MoC is the single source for what exists and what is open. A
  skill that lists notes, tasks or contacts duplicates the MoC and drifts from the first rename.
- **What the skill does carry:** location and naming conventions, the load triggers, the stable
  situation (who/what, and which open decision shapes the work), the working rules for that project,
  and the methodology developed inside it.
- **Methods discovered inside a project stay inside that project skill** as `references/` or
  `scripts/` until a second, independent consumer exists.
- **A method is not generic because it is method-shaped.** A source ladder, checklist or analysis
  script written while working one project is that project's procedure, not a shared capability.

## Promotion needs a second, independent occurrence

A method, checklist or script developed for one project is not evidence of a generic capability — it
is evidence of one use. Promote it into an owned canonical skill when a **second, independent**
consumer appears (another project, another domain, another profile), not on the first occurrence: a
rule promoted on a guess lands in the shared artifact and has to be maintained there forever. Until
then it lives in the project skill that uses it. Promotion itself is not a continuous process: the
delta enters the owning skill's development phase and is published with that phase's reviewed bytes,
not written straight into a locked source.

## Pitfalls retained here

- Do not name a new mechanism after an existing Hermes subsystem (the Skill Curator, its ledger, its
  CLI): a word collision causes real mis-attributions in reports and commits before anyone notices.
- The user's word family is canonical; a spec's or an earlier draft's coined synonyms are not. When he
  names the vocabulary for a concept, adopt it across code, CLI, config keys, docs, jobs and concept
  documents and retire the alternatives everywhere. A vocabulary rename is mechanical: inventory every
  surface first (identifiers, CLI strings, config keys, docs, job names and prompts, vault notes),
  preserve terms that are intentionally distinct domain vocabulary, sweep, then rerun the suite. The
  sweep surface is the whole configured library plus the user's concept documents, not the change's
  path allowlist, and the inventory must match derived word forms (the verb behind a renamed noun, its
  -ing form). Post-rename breakage means the sweep missed a surface, not that the vocabulary was wrong.
- Do not put a version in an artifact directory name (`<tool>-v2`-style store, cache or config paths).
  The directory outlives any single version — the version belongs in metadata or content — and a
  versioned path forks every config that points at it and forces a migration at each bump. A file that
  IS one release artifact may carry a version; a path other artifacts reference must not.
- Do not couple shared machinery's writes to one knowledge-base write API (a vault handle, a
  note-write protocol) when a plain file at a configured path does the same job: the coupling hardcodes
  deployment data into the tool and turns every relocation into a code change. The tool writes and
  verifies plain files; the deployment config names the destination.
- Do not design a skill-storage or ownership layout on assumed curator semantics — probe each verb
  (lock, adopt, pin, archive) on a disposable profile with the real CLI and read the state back first;
  the verbs differ by target location, and one blanket assumption misroutes the architecture.

## Verification

- Fork request is explicit; the provenance file exists and its per-file class claims are true.
- Standing rule placed in an always-discovered zone; identity kept in `SOUL.md`, not duplicated.
- Profile-local skill is a real directory under `own/`, declares `metadata.scope: standalone`, and no
  new package was created under the legacy `adaptations/` path.
- Project skill mirrors exactly one project folder, carries no note inventory, and any method it holds
  has not been promoted on its first occurrence.
