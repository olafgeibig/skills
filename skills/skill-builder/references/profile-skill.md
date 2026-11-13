# Writing a Profile Skill

A profile skill holds what is true of one installation: the machine, its profile, the paths that only
resolve there, the roles its skill directories play, and its own operating settings. This reference
covers what belongs in it, what does not, and how to create one.

## When to load

The deliverable is a profile-local skill — standing preferences, environment quirks, tool knowledge
about one setup, or the installation facts a generic skill deliberately does not name.

## What belongs

- **Host and profile facts.** Which machine and profile the skill serves, its role in a multi-instance
  setup, the operating system or runtime constraints that change how a procedure is run, and the names
  of services it depends on. Identity (machine, role) belongs in the profile's `SOUL.md`; the skill
  points there instead of duplicating it.
- **Paths that resolve only here.** The location of the installation's notes, the working directories
  a workflow uses, the skill roots this profile actually configures — stated as the concrete path, with
  a note that another installation will differ.
- **Roles of the external skill directories.** Which configured root is canonical for which family of
  skills, which root is a read-only third-party checkout, which is a project shelf. A generic skill
  cannot know this mapping; the profile skill can.
- **Installation settings, described not assumed.** Whether automatic background review and the
  write-approval gate are on or off for this installation, and what that means for how learning lands
  (edits apply at once, the phase review is the check). State the fact for this profile and its
  consequence; do not encode it as a rule for every installation.
- **Pointers to the installation's notes.** The open-development-phases table that records baselines
  and owners, and any dated note holding volatile data, named by their real location.
- **Local overrides of generic conventions**, where the generic skill says the concrete value varies
  per consumer.

## What does not belong

- **Generic procedure.** A method that holds for any user of the skill belongs in the canonical skill,
  not in a copy here. A profile skill that restates the generic procedure drifts from it.
- **Volatile data.** Prices, quotas, model lists and dated probe results live in a dated note in the
  user's knowledge base, with a fetch timestamp and a refresh command; the skill keeps the pointer.
- **Project facts.** Architecture, current state and system briefs belong in the project's repository
  content, never in a profile skill.
- **A second copy of another skill's rules.** Reference the owning skill; do not restate it.

## Frontmatter

The same Hermes variant as every other package in the library: top-level `version`, `author`,
`license`; `metadata.scope: standalone` because it is not a delta on another skill;
`metadata.hermes.category: own`; a description of at most 57 characters.

```yaml
---
name: example-profile-setup
description: "Use for this profile's environment facts."
version: "1.0.0"
author: Example Author
license: MIT
metadata:
  scope: standalone
  hermes:
    category: own
    tags:
      - environment
---
```

Field detail: `references/hermes-frontmatter.md`.

## Workflow

1. **Confirm it is profile-specific.** If the content would be true for any user of an existing skill,
   it belongs there instead; route it per `skill-governance`. If it is project content or volatile data,
   it belongs in that home. A profile skill is for what is genuinely installation-bound.
2. **Check for an overlap.** Run the routing gate in `skill-governance`: search the profile-local tree,
   every external root and the curator archive before creating a second skill with the same territory.
3. **Create the package** with `skill_manage(action="create", category="own")`, which writes to
   `own/<name>/`. Use a real directory — a symlinked skill directory is not discovered — and do not
   point `skills.create_dir` at `own/` as well.
4. **Write only the installation-specific content**, with the generic procedure referenced rather than
   copied. Keep the main file short; detail goes to `references/`.
5. **Validate:** the authoring linter (see `references/hermes-frontmatter.md`), then confirm the skill
   appears in `hermes skills list` and resolves with `skill_view`.

## Verification

- The skill states installation facts, not generic procedure; nothing in it duplicates a canonical
  skill's rule.
- Paths, directory roles and settings are concrete for this profile, and volatile data is a pointer to
  a dated note.
- Frontmatter follows the Hermes variant and declares `metadata.scope: standalone`.
- The skill is a real directory under `own/`, appears in discovery, and no second package claims the
  same territory.
