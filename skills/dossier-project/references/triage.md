# Triage

What is this thing, and where does it go? One decision per arriving object, one decision per note that turned out to be the wrong class.

## When to Load

- Something landed in `inbox/` or arrived in a chat: a scanned letter, a transcript, a quick fact
- A note exists and you suspect it is the wrong class
- A case turns out to be bigger than a case, or an event turns out to belong elsewhere

## Part 1 — an arriving object

Two questions, in this order. The first decides whether the note belongs to the world out there or
to your work on it; only then does the second pick the class. The groups are exclusive — something
that arrived is never an extract, and something you derived never becomes an event.

```
1) Did it arrive, or did I make it?

   arrived — a file came and was converted        → raw/,      type: document
   arrived — an app transcript                    → raw/,      type: transcript
   arrived — the note IS the document             → artifacts/, type: artifact
             (sent, received or produced: a letter, a contract, a filled form)
   arrived — nothing to show for it               → events/,   type: event
             only if it carries content; a one-line happening belongs in `## Stand`
   made — from exactly one raw note               → resources/, type: extract
   made — from many external sources, no raw note → resources/, type: research
   made — my own conclusion across several notes  → analyses/,  type: analysis

2) Neither arrived nor made — it is a fact or a matter:

   a value other notes will cite                  → masterdata/   (the user owns it)
   can I close it?                                → cases/,   type: case
   does it never end?                             → dossiers/, type: dossier
```

## Which of the two is a document?

Ask where the text comes from.

| The text is… | Class | Consequence |
|---|---|---|
| the markdown a converter made from an arrived file | `document` | folder `raw/`, body verbatim; optional provenance follows `SKILL.md` → Ownership |
| the document itself — typed, quoted, drafted, agreed | `artifact` | folder `artifacts/`, frozen, no provenance fields |

Direction does not decide it. A letter that arrives, a contract both sides signed, a questionnaire you drafted, a decision quoted word for word — all `artifact`. What separates them from `document` is only whether a converted file stands behind the text.

**Nothing is decided yet? Leave it in `inbox/`.** That is a valid state, not a failure: the folder exists so an unclassified file has somewhere to lie without becoming the wrong class. Triage can wait for the session that knows what the thing is.

**The three brakes**, all from the class table in `SKILL.md`:

- An `event` needs content. A half-sentence is not a file; it is a sentence in the `## Stand` of the case or the dossier.
- No event without a case. Something too small for a case is a `## Stand` sentence, not an event — and a small matter that keeps recurring becomes its own case, which then closes.
- A value is not knowledge. If the answer is one number other notes will cite, it is `masterdata/`, even when it came out of an `extract`.

## Part 2 — a quick fact from the user

"Note that the hearing is on 12 March." No file. Ask which of these it is:

| Shape | Target |
|---|---|
| a value others will cite (date, number, reference) | `masterdata/`, values replaced in place |
| the current state of a case or the subject | the `## Stand` of that case or dossier |
| something that happened and left no document | an `event` — if it carries content |
| a task | `## Aufgaben` of the case or the dossier |

## Part 3 — a note that is the wrong class

Reclassifying is a move plus a property change, and it breaks links. Order:

1. **Decide the new class and its parent.** Which case or dossier will list it, and in which generated section will it then appear?
2. **Change `type:` and the headings in the same visit.** A note that says `type: event` and still carries `## Kurzfassung` is worse than the original problem.
3. **Move it** with `move_note`, then set `cases:` / `dossier:` / `sources:`.
4. **Repair both link kinds** — path-qualified links break on the move, bare-name links break on a rename. Raw-text sweep on the old path and the old name; never SQL, because the links table drops unresolvable targets.
5. **Rebuild and audit**: `check.py --rebuild` then `--audit`.

## The four promotions

| From | To | When | What has to change |
|---|---|---|---|
| `event` | `case` | the happening keeps recurring and needs its own history | new case note; the event gets `cases:[[new]]`; the old parent keeps the outcome in `## Stand` |
| `case` | `dossier` | the matter does not end after all — it is a subject | the note becomes a dossier (`type:`, sections); **its children must be re-pointed** — an `event` that said `cases: [[X]]` is not a child of a dossier, so move it to the new case that continues the work, or set `dossier: [[X]]` where the class allows it |
| `extract` | `analysis` | the note stopped reporting the source and started arguing | new `analysis` note; the extract stays as evidence, or is dropped if it only held the argument |
| `document` | nothing | a document is never promoted | it is evidence; derive an `extract` beside it |

A promotion is not a rename of the class. It creates the target class and decides what happens to the old note; the old note either stays as its own evidence or is retired deliberately.

## Pitfalls

- Two notes for one arrival: the `document` and an `event` saying "it arrived". One thing, one note — the document carries the date and appears in the chronology itself.
- An `event` created so the chronology looks complete. The chronology is milestones, chosen by hand; an event is detail, and detail belongs in a case.
- A `research` that is really an `extract` with a URL in `source:`. Many URLs and no raw note is research; one source with page references is an extract.
- Reclassifying without the rebuild: the parent still lists the note under its old type, and the audit will not notice a wrong row — it only notices a missing one.
