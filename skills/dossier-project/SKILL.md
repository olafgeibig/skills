---
name: dossier-project
description: "Use when running a dossier-project: dossiers and cases."
version: "0.5.5"
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

**`document` or `artifact`?** Ask who authored the text. Correspondence and other arrived documents — a letter, an email thread, a court document, sent or received — are `document` in `raw/`, whatever shape the original has: a file that reached the vault (a converted PDF, an `.eml` export) carries `source:` as a path and `sha256:`; text pasted from an original that lives elsewhere (a cloud doc, a mailbox) carries `source:` as prose naming that place and no checksum. `artifact` is a work product the project itself produced and holds as evidence — never a message anyone sent. A `document` may carry `document_type:` (letter, email, judgment, …).

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
| `artifacts/` | `artifact` | a work product the project produced, held as evidence | **yes** |
| `masterdata/` | `masterdata` | a free-form collection of values on one subject, the user's | no |
| root or `utility/` | `utility` | task hub, project chronology, other tools | no |

Three notes live at the project root: the router `+<X>.md` (`moc`), the task hub `Aufgaben <X>.md` (`utility`, one `tasks` block scoped to the project path) and the chronology `Chronologie <X>.md` (`utility`, milestones across all cases). Hub names read head-first in the project's language — `Aufgaben Dieter.md`, never `Dieter Aufgaben.md` — while the router keeps its `+<X>.md` shape. Everything else lives in a class folder. The task hub owns the block — a router rendering the same query again is the same five lines maintained twice.

**The router is a map of the dossiers, not of the cases.** It carries one line per dossier — name plus what it holds — plus the two hub notes and one sentence saying where the cases live. A case table in the router duplicates what the dossier's `## Fälle` already generates and is maintained twice — the first list to rot.

**Date prefix only where the folder is a chronology.** A case lasts, a dossier never ends, an extraction is maintained — none is ordered by the day it was written. `analyses/` earns a prefix because the same subject may be analysed again and the earlier analysis stays.

## The classes

| `type:` | Test question | Care |
|---|---|---|
| `dossier` | does this ever end? | `## Stand` replaced in place; the rest is curated routing |
| `case` | can I close this? | `## Stand` replaced; `status: open \| blocked \| closed` |
| `event` | did it leave a paper of its own? | written once, never edited; a one-line happening belongs in `## Stand`, not in `events/` |
| `artifact` | did the project produce it? | frozen; a correction is a new artifact |
| `document` | did it arrive? | the body is the conversion, verbatim — a thread keeps its quoted history, trimmed to the newest message it loses the substance; a deadline runs from delivery, so the delivery date belongs to the case |
| `transcript` | was it spoken? | as `document`; no original file ever exists |
| `extract` | is it one source, distilled? | replaced in place when the source changes |
| `research` | many sources, no `raw` note? | appended; opens with its Prüftiefe — checked at which primary texts, what explicitly not; URLs under `Quellen:` |
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

`## Ereignisse` lists what happened: `event`, `artifact`, `document`, `transcript`. An `extract`, `research` or `analysis` that names the case is working knowledge, not an event — it is cited in `## Stand` and belongs in the dossier's `## Wissen`.

A dossier is the subject, and it reads like a map of that subject:

```
## Stand        curated: distilled, replaced in place
## Wissen       curated: the extracts, research and analyses worth reading
## Dokumente    curated: the important documents and artifacts, with a reason
## Fälle        generated: the cases that name this dossier — link, status, what it is
## Aufgaben     none: which case holds the next step
```

`## Fälle` is a three-column table: `| Fall | Status | Worum es geht |`. The link comes from the case name, the status from its `status:`, the third column from its `description:` — so the dossier answers "what is running here, and what is it about" without opening a single case.

`## Wissen` and `## Dokumente` are selections — which extraction answers the question, which document to open first. A generated list would be complete and useless. The agent proposes an entry, the user confirms it, and no rebuild ever writes into those two.

**A dossier carries no tasks.** A task is the decision to act, and a decision to act has a matter; a matter is a case. So `## Aufgaben` in a dossier names which case holds the next step — a pointer, never a checkbox. If work appears and no case holds it, the work is the case, and it gets opened. A dossier is a map; maps do not carry the walking.

**There is no history on a dossier.** What was done lives in the case, what changed lives in `## Stand`, the milestones live in the chronology. A `## Verlauf` or `## Erledigt (Historie)` is the fourth telling of the same thing and the first to go stale.

Every class has a template in `assets/`. Read the one for the class you create — the placeholder text says what belongs there *and what does not*.

## Ownership and the one truth

| Link | Written on | Read by |
|---|---|---|
| child → case | `cases: ["[[…]]"]`, a list | the case's `## Ereignisse` |
| case → dossier | `dossier: '[[…]]'` | the dossier's `## Fälle` |
| Derived note → evidence | `sources: ["[[…]]"]` on `extract`/`analysis` | the `Quellen:` footer |
| mail → the document it carried | `attachment: ["[[…]]"]`, a list | whoever needs the enclosure; the checksums in `source:`/`sha256:` of both notes prove identity |
| final analysis → the evidence it used | `sources:` includes the frozen `raw` version instead of its mutable extract, plus other evidence | a revised extract does not invalidate the reference |
| any note → MoC | `topics: ["[[+Router]]"]` | vault navigation |

- `cases:` is a list because an artifact may serve two cases. It cannot be `topics:` — that property holds MoC links only, and a case is not a MoC.
- **`source:` and `sources:` are different fields.** `source:` is the external origin — a relative file path or a URL, never a wikilink. `sources:` names evidence by wikilink; an analysis without a raw note can name its actual external URLs there. It never holds a file path.
- **`source:` is optional, per document, regardless of shape.** It names where an original is — a path, a URL, or prose naming a place only the user can reach (a cloud doc, a mailbox) — and the original may sit on another machine. An unreachable path is recorded, not deleted or repaired; nothing local has to exist. Record `sha256:` when it is known; an unavailable checksum is not a defect. A path is recorded **relative to the original storage root**, never absolute: a work tree synced between machines sits at a different absolute path on each, and an absolute one is wrong on every machine but one. Each machine's location is one line in the manual's setup section.
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
5. Shrink what the new row now tells. If the parent's `## Stand` narrates what the note records, replace the narration with the link and its consequence in the same pass — the row carries the happening, and a Stand that keeps telling it is a second copy waiting to contradict the first.

## Where a fact belongs

No session decides this again:

```
values others cite            → masterdata/     cite it, never copy it; the user owns the value
pointers known before reading → AGENTS.md       with a reason ("open before …")
rules that no longer fit      → conventions.md
base facts held on hand       → conventions.md  persons, property, standing constraints — no lookup
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
| Correspondence without mailbox access — one note per thread, `.eml` exports · the channel a German authority receives on | `references/correspondence.md` |
| Adopt an existing project onto this kind | `references/migrate-existing-project.md` |

## Writing to an authority

What the agent drafts for the user to send: a request, a Nachfrage, a notice. The recurring shape, in the project's language:

1. **One page, essentials first.** The opening names the matter and the request; the facts follow in dated order, each tied to its evidence. Cut everything the authority does not need to act — side stories, speculative clauses, reassurances about other channels ("I am sending a fax as well because I am not sure this arrives"). A letter states facts and one request.
2. **State the reply channel, with fallback.** The closing says where the answer goes: the electronic mailbox where one exists, else the sender's postal address written out in full. Authorities answer by post even when the request arrived electronically — the address in the letter is what makes that work. Never leave the reply path implicit; it is a standing user expectation.
3. **Every norm citation verified** at the source before it enters the letter (see the pitfalls in `SKILL.md`).
4. **Send on the channel the authority receives on.** Which German authority receives how — no published e-mail for case matters, Justizbehörden over the Justizpostfach, file numbers marked “unbekannt” — is in `references/correspondence.md`.
5. **After dispatch:** date and channel go to the case's `## Stand`, the milestone to the chronology, and the follow-up — checking for the answer, on a fixed rhythm — to the task.

## Pitfalls

- Never migrate a project's existing notes as part of setting the kind up. Adoption is decided project by project and note by note with the user: a concept rollout is not a bulk refactor, and provenance the old notes never had is recorded as missing, not invented.
- Never two notes for one thing: the document and its arrival, the value and its copy, the case and its summary.
- Never one note per e-mail or per export: a thread export quotes every earlier message, so a second note copies the whole history again. One note per thread, grown in place, named after its first message.
- Never write a value into two places. `## Stand` cites the master data note; it does not repeat the number.
- Never build a section that is both generated and curated. If a list needs judgement, it is not rebuilt — `references/validate.md` says which is which.
- Never record what was done; record what changed. Done-lists are the first thing to rot.
- Never answer a project question in chat only. A question about law, procedure or a deadline comes back with the next letter from the authority; the conclusion belongs in the case's `## Stand` and its derivation in a `research` note with URLs.
- Never carry a document-existence claim (Eingangsbestätigung, Bescheid, Nachweis) — or a claim about how and when something was submitted — from curated prose into a letter or a new note without opening the evidence. A sentence in a `## Stand` is not proof: check `raw/` or the original storage root, and when nothing is there the user's account settles it. Curated prose can repeat a claim no evidence ever supported, and a letter to the authority is where an invented receipt does the damage.
- Never judge note existence by a content grep, and never read `????-??-??` in `## Ereignisse` as a missing note. A note's body need not contain its own title, so grepping for the title reports an existing note as absent and invites a duplicate — and that date is simply what every generated row from a folder without date prefix (`resources/`, `masterdata/`) carries. Match by basename (`search_files` target=files, `find -iname`) before concluding anything is a ghost.
- Never cite a law, paragraph or deadline from memory into a letter, a task or a `## Stand`. Law names and numbering change — a paragraph cited under its former law's name misleads exactly the reader who checks. Verify name and number in the current consolidated text at the source (for German federal law: gesetze-im-internet), and let the `research` note record where and when.
- Never correct a false claim at one site only. The same fact lives in the case's `## Stand`, the dossier, the task hub and the chronology; search every occurrence and fix all before reporting the correction done.
- Never put a task in a dossier: a task is a decision to act, and a decision to act deserves a case. `## Aufgaben` there is a pointer to the case that holds it — a checkbox means a case is missing.
- Never edit a `document`, `transcript`, `artifact` or `event` to correct it. New note, or a `## Stand` that says what is wrong with it, names the corrected note and states that it stands unchanged but is superseded.
- Never let a case close with an open task nobody decided about, and never let `blocked` become a label without a reason.
- Never invent a folder. A folder appears with its first note; an empty class folder is a defect, not preparation.
- Never rename a class folder or a `type:` value in one project only. The folder belongs to the type, vault-wide.
- Never swap the generated-section scan in `check.py` for a TurboVault query. A query only fetches rows into the agent's context — the section is still written through `edit_note` — while adding a dependency on a running server that the selftest's unregistered fixture vaults do not have, and list-valued `cases:` cannot be queried at all (equality silently returns nothing). The filesystem scan is the mechanism, not a shortcut awaiting an upgrade.

## Verification

Run `check.py` from this skill's `scripts/` directory with the project path as its argument — `--report`, `--audit`, `--rebuild`. `--report` and `--audit` must be clean or reviewed.

After touching `check.py` or any template, run `python3 scripts/selftest.py`: it instantiates the note templates and exercises the parser, the marker rule and the preview without dependencies.

When the row format or the row selection of a generated section changes — a new row shape, or which note classes it lists — migrate the existing notes through TurboVault right after the script change and before anything else. A format change makes the rebuild refuse the old rows (it never overwrites content it did not write); a selection change makes it propose their removal — and until the migration lands, the notes lag the script. Pin the changed shape or selection with a selftest case in the same change, and afterwards normalize whitespace-only rebuild leftovers in one pass: a proposal that always carries noise gets skimmed, and the real change hides in it.

**The script never writes.** `--rebuild` prints a diff of every generated section that would change and stops; the write happens through TurboVault (`edit_note`) after the user approves exactly those bytes. A generated section holding anything that is not a row is refused, never proposed for overwriting — hand-written content in `## Ereignisse` or `## Fälle` is a defect to move, not to delete. A proposal must be reviewable on its own: a new section shows where it is inserted and its full content, a changed section shows the exact bytes.

- Every note's folder allows its `type:`, and its required headings are present.
- No two notes in the vault share a basename — compared case-insensitively: Obsidian resolves `[[…]]` case-insensitively on a case-insensitive filesystem, so `cases/Grundbuchberichtigung` and `wiki/…/grundbuchberichtigung` are one name for the resolver even when a string-exact name check passes.
- Every generated section agrees with its children's `cases:` / `dossier:` / `sources:`.
- `Quellen:` lists exactly what `sources:` names.
- `masterdata/` contains no tasks and no history.
- `source:` and `sha256:` are recorded when known; an original need not be reachable locally.
- The vault-wide broken-link count is unchanged after a move.
- A clean `--report` is not link health: it proves classes, folders and generated sections. Link resolution is its own gate — `graph_report(kind="broken_links")` plus the raw-text sweep for old basenames.

## References

- `references/triage.md` — what an arriving thing is, and how an existing note is reclassified.
- `references/validate.md` — generated vs curated, the three validation layers, when to rebuild.
- `references/close-case.md` — the pre-flight and the three ways a case ends.
- `references/init-project.md` — setting up a dossier-project.
- `references/migrate-existing-project.md` — adopting an existing project onto this kind.
- `references/correspondence.md` — mail and letters without mailbox access: one note per thread, `.eml` provenance, attachments by checksum; the channel a German authority receives letters on.