---
name: hermes-projects
description: "Use when structuring a project that Hermes works in."
version: "2.1.1"
author: Olaf Geibig
license: MIT
metadata:
  source: https://github.com/olafgeibig/skills
  hermes:
    category: personal
    tags:
      - projects
      - structure
      - agents-md
      - working-vault
      - machines
    related_skills:
      - vault-ops
      - turbovault-use
      - authoring-project
      - csl-vault
---

# Hermes Projects

How a project that Hermes works in is structured: where its content lives, what type it is, which container holds it, where the operating manual lives, and how output is published. Three questions decide everything, in this order.

1. **Projektform — where does the content live?** `workdir` (a directory outside every vault), `vault` (`projects/<x>/` in a vault), or `hybrid` (both).
2. **Projekttyp — how is it built and cared for?** Every type is governed by its own skill; the single exception is `flat`.
3. **Containertyp — what holds the project?** `vault` (it sits in a vault), `workdir` (its container is a workdir), `standalone` (it *is* a vault at its own root).

## When to Use

- Choose a project form, project type, or container type.
- Create or audit a project manual, or adopt a new type in an existing project.
- Resolve project paths or decide how its vault and publication target relate to the workdir.

## Projektform

| Form | Project directory | Notes | Own vault |
|---|---|---|---|
| **`workdir`** | the workdir | none | possible |
| **`vault`** | `projects/<x>/` in the vault | *are* the project | — |
| **`hybrid`** | the workdir | `projects/<x>/`, a knowledge source or a publication target, often both | possible |

A **hybrid** project that has a vault of its own has two variants: the vault sits **beside** the workdir, or **inside** it. The second is what this skill used to call a *working vault*; that word described the placement, not a third form. Such a vault lives in a **subdirectory** of the workdir, never at its root: two contexts need two `AGENTS.md`, one for how the work is done and one for what is known.

**The chain is stated on both sides, never assumed.** The project's `AGENTS.md` names the vault, its Projekttyp and Containertyp and the Projektskill that governs it, and says that work inside the vault begins by loading that skill and reading the vault's own `AGENTS.md`. The skill states the same from its side and makes the vault-local file the manual inside the vault — its rules override the skill's defaults, and the skill overrides generic vault conventions. A project manual that names a working vault without that line is incomplete, and a kind-skill that does not require the vault-local `AGENTS.md` is equally incomplete: an agent that reads only the project manual will otherwise work in the vault on the wrong rules, and one that loads only the skill will miss the project's layout, language and publication target.

A project's own vault is **unregistered by default**. Registration is a per-profile decision; without it there are no TurboVault hashes, audit, rollback or drift check, so its own version control is the safety net — or state before the first large write that none exists. **When a task needs those guarantees, say that the vault is unregistered and, after the user's approval, register it** in the active profile's TurboVault config — do not silently work on without an audit trail, and do not register without asking. Never register a work project's vault in a private profile.

Projektform is a decision, not an accident. Write it into the project's `AGENTS.md` together with the Projekttyp and — where a vault is involved — the vault's Containertyp, because everything else follows from them: where the manual lives, which paths are needed, whether publishing exists at all, and how far the Projektskill's authority reaches.

## The operating manual lives where the work happens

- **With a workdir (`workdir`, `hybrid`):** its `AGENTS.md` is the manual. `AGENTS.md` loads from the working directory, and Codex or Claude Code working in that repo read it there. The vault side, if it exists, is a **router**: purpose, how to find the workdir, and what the notes are for.
- **The router is optional, but discovery decides.** Keep it only when an agent that has just the vault must be able to find the workdir. Otherwise drop it: the MoC carries one line instead — `Projektverzeichnis: das Workdir, sein AGENTS.md ist das Betriebshandbuch; diese Notizen sind seine Wissensquelle` — and the manual names the vault notes worth reading. Two files describing the same project drift apart.
- **`vault` form:** the vault project directory *is* the project directory, so its `AGENTS.md` is the manual.

Both use the same five sections — `Purpose`, `Setup`, `Important resources`, `Rules`, `Extending the rules` — from `assets/project-AGENTS.md.example`. The five sections are semantic: their headings follow the vault's language and the wording of sibling project manuals (`Zweck`, `Wichtige Ressourcen`, `Regeln`, `Regeln erweitern` where the vault is German). Read one or two sibling `AGENTS.md` files first and match their idiom — heading language, `Projektverzeichnis:`/`Projekttyp:` line format — instead of introducing a new one. Around 30–40 lines: the file is read on every entry, so everything longer belongs in `conventions.md` or in the Projektskill.

**One manual, plus `conventions.md` when it earns its place.** `AGENTS.md` is the contract; `conventions.md` takes every rule that does not fit a page. Create it with the first rule that overflows and link it from `AGENTS.md` in the same change — the link is what makes the file editable: an agent told to extend the rules opens the file it was pointed at instead of growing the manual. Shape it from `assets/project-conventions.md.example` — in a vault it is a note (frontmatter, `topics`, MoC entry in the same change), in a workdir a plain markdown file. Never scaffold an empty file or leave a dangling link.

## Resolve the current machine

Use the active profile’s setup guidance or the machine inventory linked by the project manual. If the inventory is keyed by hostname, look up `hostname` there and use the corresponding stable logical name. If no mapping exists, ask; do not guess from a username, known path, or another machine’s entry. Keep hostnames and machine roles in that inventory, never in a shared skill.

## Paths have one authoritative home

- Declare the workdir's absolute path per machine **exactly once**. Default: the workdir's manual, which travels with the repository. If a vault router is required for vault-only discovery, the router carries that path instead and the manual does not duplicate it.
- The **workdir's manual** names the vault by **name** and resolves the path with `list_vaults` or the TurboVault config. A vault path differs per machine; a vault name does not.
- Never make an agent guess a checkout. If the workdir is absent on the current machine, write `not present`; if vault-only discovery matters, keep the router rather than relying on a path the agent cannot see.

## Publication

Declare the publication target per project; the Projektform alone does not determine it. An `authoring-project`'s vault commonly publishes into the associated notes project. A `cs-project` (Projekttyp, Projektform `hybrid`) publishes according to its own skill; its embedded `csl/` vault follows the lifecycle `analysis → compiled → docs` and may target `docs/` in the same vault or an external repository. A `vault` project may publish into itself; a project without a declared target does not publish.

- Explicit request only — no request, no publication.
- One deliverable maps one-to-one to one target artifact — a note, page, report, or declared bundle.
- Render into the destination's conventions. Never copy a file, never sync two vaults.
- Read the target back, then record the publication on the deliverable.
- The procedure belongs to the Projektskill of the project's type; the project's `AGENTS.md` names the destination.

## Rules that always hold

- **Never mirror.** One artefact, one home per role; a note names the path and says what it is.
- **No vault guarantees outside a registered vault.** Hashes, audit, rollback and the drift check cover a *registered* vault only. In a workdir: read before writing, write only when the task asks, and name its own version control as the safety net — or state plainly that nothing is versioned.
- **One fact, one place.** Project facts in the project's files, method in a skill, installation facts in the profile’s setup guidance or its project documentation. A skill never restates a project fact; it links.
- **Facts versus method.** The Projektskill that governs the type carries the method; the project's files carry locations, rules and the state of the work. There is no per-project skill: a project's specifics live in its `AGENTS.md` and the `conventions.md` beside it, which every environment can read.
- **A concept note carries the complete concept; another audience gets its own file.** Rewrite a spec or design note so it stands alone as the full current concept — never leave a chain of amendments appended over time. Operational instructions aimed at a different reader (a runbook brief for other agents, per-machine steps) are a separate note beside it, linked from the spec: one file serving two audiences buries the procedure under the rationale.

## Writing these files safely

- **Name only artifacts that exist.** List the directory and check every file the manual names — the `Projektverzeichnis` line, `conventions.md`, the workdir, named skills — before writing it. MoC boilerplate drifts and hands down phantom claims: a `conventions.md` that was never created, a workdir declared as the project directory when the notes are the project. The manual is read as authority, so a phantom name sends every later session hunting a file that is not there; when the claim came from the MoC or another note, correct that source line in the same change and say so in the report.
- **Resolve “here” before choosing the manual.** For a request to create or update the project-root `AGENTS.md`, target the workdir root, not the root of the vault inside it; inspect the directory context and existing manuals first. Preserve an adequate vault manual unless its own changes were requested, because the two files govern different contexts.
- **State mandatory skills explicitly.** In the project manual's `Setup`, add a `Mandatory skills` subsection naming `hermes-projects` and, when the project has a vault of its own, its Projektskill plus the requirement to read its local `AGENTS.md`. A passing mention of the vault kind does not tell the next agent what to load.

- **A vault-side `AGENTS.md` or `conventions.md` goes through TurboVault.** It is audited and rollback-able but *not* approval-gated, while the same filename outside the vault is a protected file. Treat every vault-side edit as a change to agent behaviour: read the section back and quote what changed.
- **A workdir `AGENTS.md` is protected.** Read its full current content first — an overwrite from a stale copy is refused — then expect an approval prompt. A timed-out prompt means nothing was written: report it and hand over the intended content, never retry through another tool.
- **One `AGENTS.md` per context, not per project.** A hybrid project can legitimately have a workdir manual, the manual of its own vault, and a vault router. Two in the *same* directory are the defect, and that is why a project's own vault goes into a subdirectory.

## Indexing originals and the conversions of a project's own vault

When asked for a work-tree document index connecting originals outside the vault to converted source notes inside it:

1. Resolve the requested root and inventory both directories before writing. Read the existing resource MoC for descriptions; do not assume every original already has a conversion.
2. Create the requested root-level navigation file, link to the resource MoC, and use one table row per original: **Original | Conversion | Description**. Keep the MoC authoritative for source descriptions rather than adding independent analysis to this bridge.
3. Match files using their actual directory entries. Unicode normalization may help compare names, but build each link from the target's exact filename; composed and decomposed accents can differ between originals and conversions. Use relative Markdown links across the vault boundary, percent-encoding path characters with `urllib.parse.quote(path, safe='/')` so spaces, parentheses, ampersands and combining marks survive Markdown parsing.
4. Mark unmatched originals explicitly as having no conversion found; do not invent conversion links or silently convert documents during an indexing task. Label descriptions inferred only from filenames as such.
5. Verify the generated artifact: extract and URL-decode its local link destinations, resolve them relative to the index file, and check each target exists. Compare the table's original-document rows against the actual directory inventory, not a second hand-maintained expected list; otherwise both lists can omit the same file. Report missing conversions separately from broken links.

Keep this file a navigation bridge, not a second resource MoC; leave originals and source notes unchanged unless their modification was requested.

## Projekttyp (notes projects)

**Rule 1 — a type is what has a skill.** This skill does not enumerate the types, because a list is a second place to edit: an active type has a maintained skill; a retired skill may remain discoverable solely to identify historical references. Every type is governed by its own **Projektskill**, which carries the folders, the `type:` vocabulary, the templates, the care rules and the validation; the project's `AGENTS.md` keeps facts and deviations only. The single exception is **`flat`**, described below. A manual naming a type this skill does not know is not a defect; a manual naming a type with no skill behind it is.

**`flat`** — plain notes: a MoC and notes, no classes, no generated sections, no check. It is the state a project starts in and may legitimately stay in. It needs no skill because there is nothing to encode beyond this paragraph; the moment a project needs classes, a template or a check, the type changes and a skill takes over.

**Rule 2 — the Projektskill declares its Containertyp**, and the project manual declares the one in use; a mismatch is a defect. The Containertyp also fixes how far the skill reaches: a `vault` project is governed inside `projects/<x>/` only, while a vault that sits in a workdir — and a `standalone` one — is governed as a whole. Both sides are stated, never assumed: the skill names the type it governs, the manual names the skill. One page per form and per type: `references/project-forms-and-types.md`.

**Adopting a type on a project that predates it:** inventory the existing notes' `type:` values first (`SELECT path, type FROM files WHERE path LIKE 'projects/<x>/%'`), declare the type in the manual, and record the legacy deviation — flat layout, pre-type `type:` values — in its `Rules`. Migrating or retyping the existing notes is a separate assignment that waits for the user's go. Follow the target type’s adoption procedure for the approved scope; writing the manual alone never restructures existing notes.

**When a project deserves its own vault** — exactly three reasons: an access or device boundary (work versus private), a publication or deployment target that needs its own home, or shared custody with its own sync history. Rule volume is not a reason; new document types call for a new kind, not a new vault.

## Renaming a skill

For a requested rename, follow `skill-governance`; do not rename a released package in place as part of project maintenance. Inventory affected project and vault manuals, templates, and other consumers before proposing a coordinated update. After publication verify discovery under the new name and check that no live declaration still depends on the old one.

## Auditing an existing project manual

Asked whether a project's `AGENTS.md` still matches these conventions, the deliverable is the audit plus a proposed patch — check first, rewrite only after approval. Read the manual, the `conventions.md` beside it, and every note that points at the manual, then work the list in order:

1. **Five sections, in order, about a page.** A missing `Project directory: …` line is the most common gap: nothing else states which file *is* the manual.
2. **Projektform stated literally** (`Projektform: hybrid`) together with the Projekttyp and — where a vault is involved — its Containertyp: consistent with the file tree and the rest of the file, and matching what the type's skill declares. If the form claim itself is wrong, rewrite rather than patch around it.
3. **Instance data not restated.** Reference the authoritative machine inventory; name only the logical machines relevant to the project. A manual that calls one machine "the work laptop" is a second place to edit.
4. **Every cross-reference resolves.** The longest-lived defect is a note claiming "the table of installations lives in `AGENTS.md`" while the manual has no such table: each file reads correctly alone, so only a grep finds it. Grep the project for `AGENTS.md`, `conventions`, and the MoC link, and test every claim against the file's actual content.
5. **`conventions.md` is a real link, not a code span**, from the `Extending the rules` section — the agent told to extend the rules must be able to follow it.
6. **Important resources carry a reason** (`open before …`) and a stated selection rule. The MoC is the index; a second complete list is the defect.
7. **Rules state the publication position** even when it is "nothing publishes", and name the `wiki/` ownership boundary where the vault has one.

Report as a numbered list with `file:line` and, for each, the exact replacement; distinguish what is wrong from what is merely terse. Apply after approval — through TurboVault for a vault-side file — and read each edit back. A validator warning on a correct `[text](https://…)` link is a false positive: say so instead of rewriting it.

## Setting up a new project

1. Answer the three questions and write Projektform, Projekttyp and — where a vault is involved — the Containertyp down.
2. `vault` form: create `projects/<x>/` with its `+<X>` MoC and its entry in the vault index.
3. `workdir` and `hybrid`: create the workdir, `git init` and commit — or state that it is unversioned.
4. Write `AGENTS.md` from the template, on the side where the work happens. For `hybrid`, add a vault router only when vault-only discovery requires it. Create `conventions.md` from `assets/project-conventions.md.example` with the first rule that overflows the page, and link it in the same change.
5. Declare per-machine checkout paths in their one authoritative home; in the workdir name the vault by name, never by path.
6. If the project has a vault of its own: install it in a subdirectory, declare its Containertyp, name the Projektskill that governs it, and add the chain sentence — load that skill and read the vault's `AGENTS.md` before the first write inside it.
7. Only then start working. The files exist before the first write, not after.

## What this skill does not own

| Question | Skill |
|---|---|
| Note types, MoCs, INDEX, frontmatter, refactoring, tasks | `vault-ops` |
| Writing into a vault, audit, drift | `turbovault-use` |
| The `authoring-project` type (analysis → deliverable) | `authoring-project` |
| The `cs-project` type (repository plus embedded `csl/` vault) | `cs-project` governs the project; `csl-vault` governs only the embedded vault |
