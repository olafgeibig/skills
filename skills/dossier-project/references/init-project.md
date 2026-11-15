# Setting Up a Dossier-Project

The rare path: a new project of this kind. Ends with a manual, a router, a task hub and an index entry — and **no class folders**.

## When to Load

- The user asks to set up a project for a real-world subject
- An existing project is adopted onto this kind — `references/migrate-existing-project.md` runs the migration, note by note with the user (`SKILL.md` → Pitfalls), never a bulk refactor

## Preconditions

- Shape: **notes only (B)** in this reference. A hybrid project (C) needs its manual in the work tree, which `hermes-projects` decides — that path is deliberately not covered here yet.
- `source:` on a `document` is optional and independent of the shape: it names where an original is, also when that copy sits on another machine.
- The vault is registered in TurboVault and its `AGENTS.md` is read. The vault rules override this skill.
- `projects/INDEX.md` and the thematic area's sub-index are open — the new project needs an entry in both directions.

## Steps

1. **Create the directory** `projects/<x>/`. Name it after the subject, in the project's language.
2. **Write the manual** from `assets/project-AGENTS.md`. It states the shape, the project directory, `Projekttyp: dossier-project`, the language, and the load line that makes this skill apply. Keep the five sections; deviations from the kind go under *Regeln*, and nothing else does.
3. **Create the router** `+<X>.md`, `type: moc`. Sections: persons (if any), the active cases table, dossiers, master data, a pointer to the task hub. It routes; it does not inventory — an inventory is what the check and the folder tree are for.
4. **Create the task hub** `Aufgaben <X>.md` from `assets/template-task-hub.md`, `type: utility`, with one `tasks` block scoped to `path includes projects/<x>`. This is the only place that block exists; the router links it.
5. **Create the chronology** if the project will have more than one case: `Chronologie <X>.md`, `type: utility`. One line per milestone, hand-written, newest first. Do not pre-fill it.
6. **Index both ways**: an entry in `projects/INDEX.md` with a routing abstract, and a reciprocal pointer from the thematic area. Both search paths must land.
7. **Stop.** No `dossiers/`, no `cases/`, no `raw/`. Each folder appears with its first note (`SKILL.md` → Folders).

## No empty folders

An empty class folder is a defect, not preparation: it tells the next session a class exists where nothing has ever been filed, and it makes the tree lie about what the project contains. The folder set is a rule in the skill, not an act at setup.

## Verification

- `check.py --report projects/<x>` passes with no notes — a project with zero notes is valid.
- `check.py --audit` reports the missing material, not a missing structure: expect "no task hub" to be gone, everything else empty.
- The router links the task hub and the chronology. No footer mirrors the properties (`SKILL.md` → *Ownership*); only `Quellen:` exists, and only on `extract`/`analysis`.
- `projects/INDEX.md` names the project and the area points back.
- The manual names only files that exist — no `conventions.md` link before the file is there.

## Pitfalls

- Scaffolding the ten folders "so the structure is ready". That is the one thing this skill forbids at setup.
- Copying a sibling project's manual. It carries that project's facts; the asset carries the shape.
- Creating a task hub and leaving the same `tasks` block in the router. One query, one home.
- Writing a chronology line for the setup itself. The chronology starts with the first real milestone.
