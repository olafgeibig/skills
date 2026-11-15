# Correspondence without a mailbox

How letters and e-mails are filed when the agent cannot read the mailbox — only what the user exports.

## When to Load

- Mail has to be recorded and the agent has no mailbox access
- A pasted mail text sits in the vault and should become a proper document
- A thread grows and the question is: a new note, or the old one extended
- A letter has to go out to an authority and the channel is unclear

## The shape

One note **per thread**, in `raw/`, `type: document`, `document_type: email`. The `.eml` export is a file that arrived, so it carries `source:` and `sha256:` like any converted PDF — no placeholder, no `artifacts/` detour, no printing to PDF.

The export is usually the newest message with the whole history quoted inside its plain-text part. That is one document, not fifteen: the quoted history is the same bytes, and filing it twice is the defect the class model forbids.

| Question | Answer |
|---|---|
| one note per message? | no — the export quotes every earlier message already |
| one note per export? | no — that copies the whole history on every exchange |
| new note or extend? | extend in place; the export supersedes itself |
| where does the growth go? | never into a new row — into the case's `## Stand` as a milestone |

## Filename

Date prefix = the **first** message of the thread, not the newest. The thread grows; the name must not. `updated:` carries how current it is, `created:` when the note was made. Renaming on every exchange rewrites every inbound link for no gain.

## Provenance

- every export is its own file in the original storage, dated — never overwrite an older export
- `source:` and `sha256:` name the **newest** export; the older files stay as evidence of earlier states
- `sha256` of the file, plus `sha256` of each attachment, is what makes the record checkable

## The body

Never splice by hand. The body is always the output of `scripts/eml_to_md.py` on the newest export:

```
python3 scripts/eml_to_md.py documents/20261118-Thread.eml > body.md
```

The script writes the body to stdout and the statistics to stderr: file checksum, message count, and every attachment with type, size and checksum. It normalises the surface only — `mailto:`/`tel:`/link annotations, trailing whitespace, runs of blank lines, one blank line after each quoted header field — and separates quoted messages with `---`. Message text is never shortened or reordered.

One rule earns its own line: **angle brackets around an address are removed, the address stays** (`<olaf@pobox.com>` → `olaf@pobox.com`). Obsidian reads them as mail autolinks, and every one lands in the broken-link report as a phantom note. Same for the `Message-ID`.

Regenerating the whole body each time is what makes "extend by the new messages" safe: no hand-splicing, nothing duplicated, nothing dropped.

## Fields

| Field | Value |
|---|---|
| `document_type:` | `email`, `letter`, `note`, `transcript`, `decision` — the genre, orthogonal to the class and the folder |
| `attachment:` | a **list** of wikilinks to the `raw` notes of the documents the thread carried |

The attachment link is not decoration: the script prints the attached file's checksum, and when it equals the `sha256` of an existing `raw` note, the mail and the document are proven to be the same file. Write the field only when the attachment is in the vault.

## Without an export

Text the user pasted into the chat has no file behind it yet. Then:

- `artifacts/`, `type: artifact`, `document_type: email`, `source: "<System> — <Titel> (nicht verlinkt)"`, no `retrieved:`
- once the export exists: `source:` → path, `sha256:` → checksum, `type: document`, move to `raw/`
- the open candidates are `grep -rl "nicht verlinkt"`

A draft the agent writes is the opposite case and stays an `artifact` with no `source:` at all — there is no other instance. A sent mail has one: the copy in the mailbox, hence `raw/` once exported.

## Sending to an authority: the channel

Decide the channel before drafting — German authorities rarely publish an e-mail address for case matters, and hunting for one wastes the session the letter was meant to save.

| Recipient | Channel | Watch out |
|---|---|---|
| Justizbehörden — Amtsgericht, Grundbuchamt, Nachlassgericht, Staatsanwaltschaft | EGVP, the user's Justizpostfach | a department may only be findable under its parent court's name; a Grundbuchamt is a department of its Amtsgericht |
| everyone else — authorities, companies, landlords | post, or the e-mail published for the matter | a fax only when the user asks for one |

- The portal's Aktenzeichen field: mark it **unbekannt** for an ongoing matter the user has no file number for. **Neu** opens a new matter and files the letter beside the running procedure instead of into it. Never invent a file number.
- One confirmed channel is enough. Stacking fax or registered post on an electronic channel happens on request — a letter hedging its own delivery reads as noise at the authority as well.

## Pitfalls

- One note per export: the second export's note repeats every message the first one held, and the two drift apart.
- Renaming the thread note to the newest message date, then again on the next exchange.
- Splicing the new message onto the stored body by hand — the quoted history shifts, and duplicates follow.
- Filing the attached PDF as if it came separately: it is `attachment:` on the thread, and its checksum is the proof.
- Printing a mail to PDF so that "a file exists". Export the `.eml`.
- Letting every exchange into the case as its own `## Ereignisse` row. The thread has one row, at its start; what moved goes to `## Stand`.
