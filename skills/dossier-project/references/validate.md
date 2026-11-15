# Validate and Rebuild

What is generated, what is curated, and what the check can and cannot see.

## When to Load

- After creating, moving, reclassifying or deleting a note
- Before closing a case or handing the project over
- When two notes disagree, or a list looks short

## Generated versus curated

**The test:** a section is generated only when its content follows completely from properties. As soon as a selection is needed, it is curated and nothing writes it but a human-reviewed edit.

| Section | On | Generated from |
|---|---|---|
| `## Ereignisse` | case | all notes whose `cases:` names this case, sorted newest first |
| `## Fälle` | dossier | all `case` notes whose `dossier:` names this dossier |
| `Quellen:` footer | extract, analysis | the note's own `sources:` |

| Section | On | Why not generated |
|---|---|---|
| `## Stand` | case, dossier | prose about the current state |
| `## Wissen` | dossier | which extraction matters is a judgement |
| `## Dokumente` | dossier | which document to open first is a judgement |
| `## Aufgaben` | case, dossier | tasks are decisions |
| chronology | project root | "milestone" is a selection, not a filter |
| `## Kurzfassung` | every knowledge note | the author's condensation |

`--rebuild` proposes the first table and nothing else — it writes nothing at all. It never touches the second — a rebuild that overwrites a curated section destroys the review that produced it.

## The three layers, and who owns each

| Layer | Question | Owner |
|---|---|---|
| links | does every link resolve? | TurboVault — `graph_report(kind="broken_links")`, `get_links` |
| shape | right type in the right folder, required headings, valid `status:`, unique basenames | `check.py --report` |
| completeness | is something **missing**? | `check.py --audit` |

The split matters. TurboVault already catches a link that no longer resolves; it cannot catch a link that was never written, a case no dossier names, or a fact that went stale. And a broken link is not a missing note — do not answer an audit finding with a link-repair sweep.

## How to run it

Run the script from this skill's `scripts/` directory (or by its full path) and pass the project
directory — absolute, or relative to the current working directory:

```bash
python3 check.py --report  <vault>/projects/<x>
python3 check.py --audit   <vault>/projects/<x>
python3 check.py --rebuild <vault>/projects/<x>     # proposes, writes nothing
```

`--rebuild` prints a unified diff of every generated section that would change and stops. It never
writes: the write goes through TurboVault (`edit_note`) after the user approves exactly those bytes,
so the approval covers what was shown. Only after the reviewed edits are applied should a second run
report `nothing to change`.

**A generated section is refused, not overwritten, when it holds anything that is not a row** —
prose, a code block, a hand-written line. `--report` names the section; move the content to `## Stand`
or to its own note, then rebuild. `Quellen:` is refused when it contains handwritten or ambiguous
content, and a final analysis is never proposed for alteration. Review each diff: a handwritten line
that exactly resembles a generated row cannot be distinguished by syntax alone.

`--report` exits non-zero on a hard finding: a folder that does not allow the `type:`; a missing
required heading; an invalid `status:`; a generated section that is stale or holds hand-written
content; a duplicate basename anywhere in the vault; `## Aufgaben` inside `masterdata/` or a
`## Erledigt`/`## Verlauf` on a dossier or master data note; a `Quellen:` footer that disagrees
with `sources:`, including an extra entry; a chronology note whose filename carries no `YYYYMMDD`
prefix. Neither an unavailable original nor a missing checksum is a hard finding.

`--audit` never fails the run — it lists what a human has to decide:

| Finding | What to do |
|---|---|
| a `case` with no `dossier:` | decide the dossier, or make one |
| a child with neither `cases:` nor `dossier:` | an orphan: file it, or delete it if it was never meant to stay |
| a `blocked` case | confirm `## Stand` names the blocker — the script cannot read meaning |
| a `dossier` with empty `## Wissen`/`## Dokumente` while material exists | propose the entries; the user confirms |
| no task hub at the project root | create it from `assets/template-task-hub.md` |
| no note carries a kind type | the project is not on the model yet |

## When to rebuild

- after creating a note that names a parent
- after moving or reclassifying a note
- after closing a case (its last rows land in the chronology, not in the list)
- after a bulk edit of `cases:`/`dossier:`/`sources:`

Not after editing `## Stand` or a curated section: nothing generated depends on prose, so a rebuild proves nothing and rewrites rows the user may be mid-way through reviewing.

## The rebuild is a render, not a second ledger

Each row is one line: date, class, link, and the child's `description:` as the clause. The child states the fact; the parent shows it. If a row needs a sentence that is not the child's description, the child's description is wrong — not the generator.

The date is parsed from the child's filename prefix only: a child whose folder carries no prefix (`resources/`, `cases/`, `masterdata/`) renders `????-??-??`. That is the render, not a defect in the note — never patch a date into a generated block. If the undated row matters, the question is whether the child belongs in `## Ereignisse` at all, and that question goes to the user.

## Pitfalls

- Adding a row by hand. It will be gone after the next rebuild, or it will survive and contradict one.
- Sorting `## Wissen` by date. It is curated: order it by what a reader needs first, not by when it was written.
- Treating a clean `--report` as a correct project. It proves shape; only `--audit` and a human look at the content prove meaning.
- Rebuilding before the links are repaired. A rebuild reads bare-name links; a note that is not yet visible to the index may drop out of the list.
- Writing a proposal with different padding than shown. The proposed bytes include the blank lines an empty section keeps — a write that trims them leaves every later `--rebuild` proposing whitespace noise. Re-run `--rebuild` after writing and expect `nothing to change`: that run is the idempotence check on the write, not a formality.
