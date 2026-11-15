---
name: dossier-project
description: "Use when running a dossier-project: dossiers and cases."
version: "0.4.3"
author: Olaf Geibig
license: MIT
metadata:
  source: https://github.com/olafgeibig/skills
  scope: standalone
  hermes:
    tags:
      - projects
      - knowledge-work
      - dossier
    related_skills:
      - hermes-projects
      - vault-ops
      - turbovault-use
---

# Dossier Project

A project kind for real-world affairs administered over years: care, health, contracts, estates, an authority's file, a house. The centre is neither a deliverable nor code — it is the **dossier**: the subject that never ends, held current while the cases that touch it open and close.

Two things make the kind. **One case is one note**, so no directory wraps a single file. **Evidence and knowledge are separate levels**, so no session has to read an eighty-page valuation report to answer a question it already answered last month.

Project setup, manual and Projektform are `hermes-projects`; writing notes and frontmatter mechanics are `vault-ops`; TurboVault calls are `turbovault-use`. This skill owns the classes, their care rules, the routing and the check.

**Projekttyp `dossier-project`, Containertyp `vault`.** The type sits in a vault as `projects/<x>/` and is governed inside that subtree only — it never owns a vault of its own. The project's `AGENTS.md` declares the same pair, and a mismatch is a defect (`hermes-projects` audits it).

## When to Use

- Set up a dossier-project, or adopt an existing project onto this kind
- Classify, create or care for a note inside one
- Open, work on, block or close a case
- Decide where a fact belongs: `masterdata/`, the project manual, `conventions.md`, a `## Stand`
- Something arrived — a scanned letter, a transcript, a quick fact — and needs a place

Not for deliverable authoring (`authoring-vault`) or for projects whose subject is code or a body of notes (`hermes-projects`).

## The model: two axes

The classes sit on two axes. They are not one flat list, or `type:` becomes a bucket.

```
granularity   dossier ─→ case ─→ event / artifact
derivation    arrived document ─→ raw ─→ resources → analyses
                    └────────────┴── join the granularity axis via cases:/dossier:
```

**The reading rule that makes the second axis worth having:** `resources/` and `analyses/` are the working surface — read there first. `raw/` is the evidence — open it when a claim must be checked. No summary is trustworthy without the full text beside it; no full text has to be read twice.

**The division the model rests on:** a document becomes a note (`document`, `transcript`, `artifact`); a happening that leaves no document becomes an `event`. One real-world thing, one note. A letter is never recorded twice — once as the document and once as "it arrived".

**`document` or `artifact`?** Ask where the text comes from. A file arrived and a converter produced the markdown: `document`, and it may carry `source:` and, when that source is a path, `sha256:`. The note *is* the document, whichever direction it went — sent, received or produced: `artifact`.

## Folders and the types allowed in them

| Folder | allowed `type:` | Holds | Date prefix |
|---|---|---|---|
| `inbox/` | **none** — markdown without frontmatter | pipeline output and quick fact notes, unclassified | no |
| `raw/` | `document`, `transcript` | full text of an arrived document, or of a recording | **yes** |
| `resources/` | `extract`, `research` | distillation of one source · research result with URLs | no |
| `analyses/` | `analysis` | synthesised knowledge across every other level | **yes** |
| `dossiers/` | `dossier` | the subject | no |
| `cases/` | `case` | the bounded matter | no |
| `events/` | `event` | a happening without a document | **yes** |
| `artifacts/` | `artifact` | a document held as evidence — sent, received or produced | **yes** |
| `masterdata/` | `masterdata` | a free-form collection of values on one subject, the user's | no |
| root or `utility/` | `utility` | task hub, project chronology, other tools | no |

Three notes live at the project root: the router `+<X>.md` (`moc`), the task hub `<X> Aufgaben.md` (`utility`, one `tasks` block scoped to the project path) and the chronology (`utility`, milestones across all cases). Everything else lives in a class folder. The task hub owns the block — a router rendering the same query again is the same five lines maintained twice.

**Date prefix only where the folder is a chronology.** A case lasts, a dossier never ends, an extraction is maintained — none is ordered by the day it was written. `analyses/` earns a prefix because the same subject may be analysed again and the earlier analysis stays.

## The classes

| `type:` | Test question | Care |
|---|---|---|
| `dossier` | does this ever end? | `## Stand` replaced in place; the rest is curated routing |
| `case` | can I close this? | `## Stand` replaced; `status: open \| blocked \| closed` |
| `event` | is it worth its own file? | written once, never edited |
| `artifact` | is it a document in its own right? | frozen; a correction is a new artifact |
| `document` | did it arrive? | the body is the conversion, verbatim; a deadline runs from delivery, so the delivery date belongs to the case |
| `transcript` | was it spoken? | as `document`; no original file ever exists |
| `extract` | is it one source, distilled? | replaced in place when the source changes |
| `research` | many sources, no `raw` note? | appended; URLs under `Quellen:` |
| `analysis` | is it my conclusion? | `status: draft \| final`; final is frozen |
| `masterdata` | do I look this up? | **the user's** free-form collection: values replaced in place, no history, no tasks |
| `utility` | is it a tool? | as needed |

**The recording rule — the brake on note inflation.** An `event` earns a file only when it carries content: what was agreed, what was answered, what follows. A half-sentence belongs in the `## Stand` of the case or the dossier. And there is no event without a case: something too small for a case is not an event, it is a sentence in the dossier's `## Stand`.

**Every knowledge note opens with `## Kurzfassung`.** The head is the cheap version, the rest is detail — the same arrangement as `## Stand`. Whoever reads only the head has most of the value and none of the forty thousand words.

## The two hubs

A case is one note in `cases/`, named after the matter, no date prefix, no directory, no `+`:

```
## Stand        curated: distilled, replaced in place
## Ereignisse   generated: date · class · link · one clause, newest first
## Aufgaben     curated: tasks with a stable ID and action tag
```

A dossier is the subject, and it reads like a map of that subject:

```
## Stand        curated: distilled, replaced in place
## Wissen       curated: the extracts, research and analyses worth reading
## Dokumente    curated: the important documents and artifacts, with a reason
## Fälle        generated: the cases that name this dossier
## Aufgaben     curated: only what has no case of its own
```

`## Wissen` and `## Dokumente` are selections — which extraction answers the question, which document to open first. A generated list would be complete and useless. The agent proposes an entry, the user confirms it, and no rebuild ever writes into those two.

**There is no history on a dossier.** What was done lives in the case, what changed lives in `## Stand`, the milestones live in the chronology. A `## Verlauf` or `## Erledigt (Historie)` is the fourth telling of the same thing and the first to go stale.

Every class has a template in `assets/`. Read the one for the class you create — the placeholder text says what belongs there *and what does not*.

## Ownership and the one truth

| Link | Written on | Read by |
|---|---|---|
| child → case | `cases: ["[[…]]"]`, a list | the case's `## Ereignisse` |
| case → dossier | `dossier: '[[…]]'` | the dossier's `## Fälle` |
| derived note → evidence | `sources: ["[[…]]"]` on `extract`/`analysis` | the `Quellen:` footer |
| final analysis → the evidence it used | `sources:` includes the frozen `raw` version instead of its mutable extract, plus other evidence | a revised extract does not invalidate the reference |
| any note → MoC | `topics: ["[[+Router]]"]` | vault navigation |

- `cases:` is a list because an artifact may serve two cases. It cannot be `topics:` — that property holds MoC links only, and a case is not a MoC.
- **`source:` and `sources:` are different fields.** `source:` is the external origin — a relative file path or a URL, never a wikilink. `sources:` names evidence by wikilink; an analysis without a raw note can name its actual external URLs there. It never holds a file path.
- **`source:` is optional, per document, regardless of shape.** It names where an original is — a path or a URL — and the original may sit on another machine. An unreachable path is recorded, not deleted or repaired; nothing local has to exist. Record `sha256:` when it is known; an unavailable checksum is not a defect.
- **Master data belong to the user.** The agent reads and cites them, creates a note on instruction, and never rewrites a value. Tasks and histories do not belong there either — they go to `## Aufgaben` of a case or a dossier.
- **No mirrored footers.** A link lives in its property, once. Every note is read many times, and a footer repeating `topics:` / `cases:` / `dossier:` costs tokens on every read without adding a graph edge — TurboVault indexes frontmatter wikilinks. The one footer that earns its place is `Quellen:`: it is where a reader looks for the evidence, and for `research` it is the only place the URLs exist. (This deliberately deviates from the hybrid-navigation rule in `vault-ops`.)
- **Generated is not curated.** `## Ereignisse`, `## Fälle` and the `Quellen:` footers are rebuilt from properties. `## Stand`, `## Wissen`, `## Dokumente`, `## Aufgaben` and the chronology are never written by the rebuild.
- **A generated section must say so.** Its first line is `<!-- GENERIERT — nicht von Hand bearbeiten. -->`, and everything under it is a row. Without the marker the author is unknown and nothing is proposed; a line that is not a row makes the section refused, not rewritten — that is how hand-written content survives a rebuild.

## Creating a note

Four steps; the template carries the rest.

1. Pick the class from the table above — uncertain? `references/triage.md`.
2. Copy that class's template from `assets/` into its folder, named by that folder's rule.
3. Set `cases:` / `dossier:` / `sources:` — the parent must be able to find it, and the check reports an orphan.
4. Run `check.py --rebuild <project>`: it **proposes** the parent's generated rows and writes nothing. Read the diff, then write the section with `turbovault edit_note` once the user approves it.

## Where a fact belongs

No session decides this again:

```
values others cite            → masterdata/     cite it, never copy it; the user owns the value
pointers known before reading → AGENTS.md       with a reason ("open before …")
rules that no longer fit      → conventions.md
current state in prose        → ## Stand       values cited by link
```

**The test:** a fact belongs in the project manual if an error happens before anyone could look it up. Everything else is a lookup, and lookups live where lookups live.

## What stays German

The schema is English; the human surface is not. Headings, note titles, slugs and all body prose follow the vault's language policy.

| Class | Required headings |
|---|---|
| case | `## Stand` · `## Ereignisse` · `## Aufgaben` |
| dossier | `## Stand` · `## Wissen` · `## Dokumente` · `## Fälle` · `## Aufgaben` |
| extract | `## Kurzfassung` · `## Fakten` |
| research | `## Kurzfassung` · `## Befunde` |
| analysis | `## Kurzfassung` · `## Analyse` · `## Ergebnis` |
| document, transcript | none — the body is the conversion |
| masterdata, utility | none |

The `Quellen:` footer mirrors `sources:` — the one footer the kind keeps, because a reader looks for the evidence there. Which sections the rebuild proposes is in *Ownership*, not in this table.

## Workflows

| Need | Reference |
|---|---|
| Something arrived, or an existing note turned out to be another class | `references/triage.md` |
| Rebuild what is generated, audit what is missing | `references/validate.md` |
| A case is resolved, abandoned or superseded | `references/close-case.md` |
| Set up a new project of this kind | `references/init-project.md` |
| Adopt an existing project onto this kind | `references/migrate-existing-project.md` |

## Pitfalls

- Never migrate a project's existing notes as part of setting the kind up. Adoption is decided project by project and note by note with the user: a concept rollout is not a bulk refactor, and provenance the old notes never had is recorded as missing, not invented.
- Never two notes for one thing: the document and its arrival, the value and its copy, the case and its summary.
- Never write a value into two places. `## Stand` cites the master data note; it does not repeat the number.
- Never build a section that is both generated and curated. If a list needs judgement, it is not rebuilt — `references/validate.md` says which is which.
- Never record what was done; record what changed. Done-lists are the first thing to rot.
- Never edit a `document`, `transcript` or `artifact` to correct it. New note, or a `## Stand` that says what is wrong with it.
- Never let a case close with an open task nobody decided about, and never let `blocked` become a label without a reason.
- Never invent a folder. A folder appears with its first note; an empty class folder is a defect, not preparation.
- Never rename a class folder or a `type:` value in one project only. The folder belongs to the type, vault-wide.

## Verification

Run `check.py` from this skill's `scripts/` directory with the project path as its argument — `--report`, `--audit`, `--rebuild`. `--report` and `--audit` must be clean or reviewed.

After touching `check.py` or any template, run `python3 scripts/selftest.py`: it instantiates the note templates and exercises the parser, the marker rule and the preview without dependencies.

**The script never writes.** `--rebuild` prints a diff of every generated section that would change and stops; the write happens through TurboVault (`edit_note`) after the user approves exactly those bytes. A generated section holding anything that is not a row is refused, never proposed for overwriting — hand-written content in `## Ereignisse` or `## Fälle` is a defect to move, not to delete. A proposal must be reviewable on its own: a new section shows where it is inserted and its full content, a changed section shows the exact bytes.

- Every note's folder allows its `type:`, and its required headings are present.
- No two notes in the vault share a basename — compared case-insensitively: Obsidian resolves `[[…]]` case-insensitively on a case-insensitive filesystem, so `cases/Grundbuchberichtigung` and `wiki/…/grundbuchberichtigung` are one name for the resolver even when a string-exact name check passes.
- Every generated section agrees with its children's `cases:` / `dossier:` / `sources:`.
- `Quellen:` lists exactly what `sources:` names.
- `masterdata/` contains no tasks and no history.
- `source:` and `sha256:` are recorded when known; an original need not be reachable locally.
- The vault-wide broken-link count is unchanged after a move.

## References

- `references/triage.md` — what an arriving thing is, and how an existing note is reclassified.
- `references/validate.md` — generated vs curated, the three validation layers, when to rebuild.
- `references/close-case.md` — the pre-flight and the three ways a case ends.
- `references/init-project.md` — setting up a dossier-project.
- `references/migrate-existing-project.md` — adopting an existing project onto this kind.