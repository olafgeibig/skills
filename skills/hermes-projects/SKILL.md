---
name: hermes-projects
description: "Use when structuring a project that Hermes works in."
metadata:
  version: "1.0.0"
  author: Olaf Geibig
  source: https://github.com/olafgeibig/skills
  scope: standalone
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
      - authoring-vault
      - csl-vault
---

# Hermes Projects

How a project that Hermes works in is structured: what its project directory is, whether it has a notes project, where the operating manual lives, and how output is published. Three questions decide everything, in this order.

1. **Does it have a work tree** — a directory outside any vault, where the work is done?
2. **Does it have a notes project** — `projects/<x>/` in a vault?
3. **Does it have a working vault** — a second, self-contained vault inside the work tree?

## The three shapes

| Shape | Project directory | Notes | Working vault |
|---|---|---|---|
| **A — worktree only** | the work tree | none | possible |
| **B — notes only** | `projects/<x>/` in the vault | *are* the project | — |
| **C — hybrid** | the work tree | `projects/<x>/`, a knowledge base or a publication target, often both | possible |

A **working vault** is a vault inside the work tree that is not a notes vault: it holds the analysis and the deliverables, and its kind names the skill that governs it — `knowledge-base` (hand-written, no publication, no skill), `authoring` → `authoring-vault`, `csl` → `csl-vault`. It lives in a **subdirectory** of the work tree, never at its root: two contexts need two `AGENTS.md`, one for how the work is done and one for what is known.

Shape is a decision, not an accident. Write it into the project's `AGENTS.md` (`Shape: …`), because everything else follows from it — where the manual lives, which paths are needed, whether publishing exists at all.

## The operating manual lives where the work happens

- **With a work tree (A, C):** its `AGENTS.md` is the manual. `AGENTS.md` loads from the working directory, and Codex or Claude Code working in that repo read it there. The vault side, if it exists, is a **router**: purpose, the work tree's location per machine, and what the notes are for.
- **Notes only (B):** the vault project directory *is* the project directory, so its `AGENTS.md` is the manual.

Both use the same five sections — `Purpose`, `Setup`, `Important resources`, `Rules`, `Extending the rules` — from `assets/project-AGENTS.md.example`. Around 30–40 lines: the file is read on every entry, so everything longer belongs in `conventions.md` or in the project skill.

**Every project has two files, not one.** `AGENTS.md` is the contract and links `conventions.md` at its end; `conventions.md` takes every rule that does not fit a page. The link is what makes the file editable: an agent told to extend the rules opens the file it was pointed at, instead of growing the manual. Shape it from `assets/project-conventions.md.example` — in a vault it is a note (frontmatter, `topics`, body `Topics:` footer, MoC entry in the same change), in a work tree a plain markdown file. Create it with the first rule that overflows; do not scaffold an empty one, and never leave the link dangling.

## Machines

Paths are declared per machine under a stable logical name. A hostname changes when hardware is replaced; the logical name does not.

| Machine | Hostname | What it is |
|---|---|---|
| `bosch` | `BE18-C-0001G` | work laptop; its successor keeps the logical name, only this row changes |
| `durin` | *fill on first use* | home-lab server (Raspberry Pi 5), runs an agent and the backup NAS |
| `boromir` | *fill on first use* | private MacBook, the local ML box |

This table lives here on purpose. It is instance data and belongs in a personal skill, not in a shared one — and it is the one place to edit when the setup changes, instead of every project's `AGENTS.md`.

Resolution: run `hostname`, find the row, use its logical name. Unknown hostname → ask which machine this is, add the row, then continue. Never derive a machine name from `whoami`, from a path, or from an OS hostname, and never reuse another machine's path. Write `not present` explicitly for a machine without a work tree — it stops the next agent from inventing a plausible path.

## Paths go one way

- The **vault router** names the work tree's absolute path per machine. Nothing else can discover a checkout location.
- The **work tree's manual** names the vault by **name** and resolves the path with `list_vaults` or the TurboVault config. A vault path differs per machine; a vault name does not.

## Publication

A working vault publishes into the notes project; shape B publishes into itself; shape A does not publish at all.

- Explicit request only — no request, no publication.
- One deliverable maps one-to-one to one published note.
- Render into the destination's conventions. Never copy a file, never sync two vaults.
- Read the target back, then record the publication on the deliverable.
- The procedure belongs to the working vault's skill; the project's `AGENTS.md` names the destination.

## Rules that always hold

- **Never mirror.** One artefact, one home per role; a note names the path and says what it is.
- **No vault guarantees outside the vault.** Hashes, audit, rollback and the drift check cover a *registered* vault only. In a work tree: read before writing, write only when the task asks, and name its own version control as the safety net — or state plainly that nothing is versioned.
- **One fact, one place.** Project facts in the project's files, method in a skill, instance data in the table above. A skill never restates a project fact; it links.
- **Facts versus method.** A `project-<x>` skill carries the method and loads by trigger; the files carry locations, rules and the state of the work.

## Writing these files safely

- **A vault-side `AGENTS.md` or `conventions.md` goes through TurboVault.** It is audited and rollback-able but *not* approval-gated, while the same filename outside the vault is a protected file. Treat every vault-side edit as a change to agent behaviour: read the section back and quote what changed.
- **A work-tree `AGENTS.md` is protected.** Read its full current content first — an overwrite from a stale copy is refused — then expect an approval prompt. A timed-out prompt means nothing was written: report it and hand over the intended content, never retry through another tool.
- **Two `AGENTS.md` files in one project** (work tree and working vault) are correct. Two in the *same* directory are the defect, and that is why a working vault goes into a subdirectory.

## Renaming a genus or a kind

A rename touches more than the skill: the vault root `AGENTS.md`, every project `AGENTS.md`, the skill's own frontmatter and template, and any note naming the term. Patch the skill contents first, then `git mv` the directory (the frontmatter `name:` must equal the directory name), grep every skill root and vault for the old name, and verify discovery with the skills list — trust the listing, not the rename.

## Setting up a new project

1. Answer the three questions and write the shape down.
2. Shape B: create `projects/<x>/` with its `+<X>` MoC and its entry in the vault index.
3. Shape A/C: create the work tree, `git init` and commit — or state that it is unversioned.
4. Write `AGENTS.md` from the template, on the side where the work happens; add the router on the vault side for C. The last section links `conventions.md` — create that file from `assets/project-conventions.md.example` with the first rule that overflows the page.
5. Add the per-machine path line; in the work tree name the vault by name, never by path.
6. If a working vault exists: install it in a subdirectory, declare its kind, name the skill that governs it.
7. Only then start working. The files exist before the first write, not after.

## What this skill does not own

| Question | Skill |
|---|---|
| Note types, MoCs, INDEX, frontmatter, refactoring, tasks | `vault-ops` |
| Writing into a vault, audit, drift | `turbovault-use` |
| Authoring a working vault (analysis → deliverable) | `authoring-vault` |
| Bosch security lifecycle vault (`csl` kind) | `csl-vault` |
| One project's method, triggers, pitfalls | `project-<x>` |
