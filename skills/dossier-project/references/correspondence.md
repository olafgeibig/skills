# Correspondence

Draft correspondence, verify delivery requirements, and file letters or mail exports as evidence.

## When to Load

- Mail has to be recorded and the agent has no mailbox access
- A pasted mail text sits in the vault and should become a proper document
- A thread grows and the question is: a new note, or the old one extended
- Drafting or revising a letter, verifying a delivery channel, or requesting official records

## The shape

One note **per thread**, in `raw/`, `type: document`, `document_type: email`. The `.eml` export is a file that arrived, so it carries `source:` and `sha256:` like any converted PDF — no placeholder, no `artifacts/` detour, no printing to PDF.

The export is usually the newest message with the whole history quoted inside its plain-text part. That is one document, not fifteen: the quoted history is the same bytes, and filing it twice is the defect the class model forbids.

| Question | Answer |
|---|---|
| one note per message? | no — the export quotes every earlier message already |
| one note per export? | no — that copies the whole history on every exchange |
| new note or extend? | extend in place only if the newer export preserves the previously recorded messages |
| where does the growth go? | never into a new row — into the case's `## Stand` as a milestone |

## Filename

Date prefix = the **first** message of the thread, not the newest. The thread grows; the name must not. `updated:` carries how current it is, `created:` when the note was made. Renaming on every exchange rewrites every inbound link for no gain.

## Provenance

- every export is its own file in the original storage, dated — never overwrite an older export
- `source:` and `sha256:` name the **newest** export; the older files stay as evidence of earlier states
- `sha256` of the file, plus `sha256` of each attachment, is what makes the record checkable
- If the new export omits earlier messages or attachments, do not overwrite the only accessible evidence. Retain both originals and the existing note until the gap is resolved. A final analysis cites the thread and records the exact original export used (relative path and SHA-256); a later update of the thread must not change that citation.

## The body

Never splice by hand. The body is always the output of `scripts/eml_to_md.py` on the newest export:

```
python3 scripts/eml_to_md.py documents/20261118-Thread.eml > body.md
```

The script writes the body to stdout and the statistics to stderr: file checksum, estimated message count, and named MIME parts with type and, where actual payload bytes are available, size and checksum. Do not infer attachment identity where the checksum is unavailable. It normalises the surface only — `mailto:`/`tel:`/link annotations, whitespace and header layout — and separates quoted messages with `---`. Verify the conversion against the source, especially standalone links and quoted boundaries.

Angle brackets around an address or `Message-ID` are removed; the identifier itself stays (`<person@example.org>` → `person@example.org`).

Regenerating the whole body each time is what makes "extend by the new messages" safe: no hand-splicing, nothing duplicated, nothing dropped.

## Fields

| Field | Value |
|---|---|
| `document_type:` | `email`, `letter`, `note`, `transcript`, `decision` — the genre, orthogonal to the class and the folder |
| `attachment:` | a **list** of wikilinks to the `raw` notes of the documents the thread carried |

The attachment link is not decoration: the script prints the attached file's checksum, and when it equals the `sha256` of an existing `raw` note, the mail and the document are proven to be the same file. Write the field only when the attachment is in the vault.

## Without an export

Text the user pasted into the chat has no file behind it yet. Then:

- Use `raw/`, `type: document`, `document_type: email`; record `source:` as prose naming the mailbox or other location, with no checksum until known.
- Once a complete export exists, verify it against the pasted text and update provenance on the same thread note (`source:` as relative path, `sha256:` of that export).

An unsent draft does not prove dispatch. If the draft itself is retained as a distinct work product, label it as such. Record sent correspondence as `document` in `raw/`, irrespective of whether the source is an export or pasted text.

## Draft and record dispatch

1. Open with the matter and requested action; tie factual claims to evidence and verify any legal citations against current primary sources. Include only the detail the recipient needs.
2. If a request may incur additional fees, check the contract before stating what it covers. If scope or price is unclear, ask the user whether the draft should request clarification or an estimate; do not assert coverage or add a reservation on their behalf.
3. Name a reply channel that the user can receive and the procedure allows. Treat the user's revised draft as the new base; change substance only on instruction.
4. After confirmed dispatch, record date and channel in the case, mark the milestone in the chronology, and record any agreed follow-up in the case task. Distinguish proof of dispatch from proof of receipt.

## Sending to an authority: the channel

Check the recipient's official instructions for the specific procedure before drafting. Verify the exact addressee, accepted channel, any form/signature requirements and whether that channel meets the applicable filing rules. Do not infer acceptance from a published general contact address or from a recipient appearing in a portal directory. Check how the actual portal handles a missing file number; never invent one or mark an existing matter as new. Send on the agreed, verified channel only. Keep any dispatch or receipt confirmation as its own evidence; do not equate a sent copy or an upload with proven receipt.

## Getting documents out of an authority

Name the specific records and the requested form of access. Verify the applicable route (e.g. procedural file access, information access, or a register request), eligibility, available delivery modes, deadlines, fees and proof of representation from the current official sources for that procedure and jurisdiction. Do not assume an entitlement to dispatch, fee exemption or a universal deadline. Record the primary sources and date checked in the `research` note.

## Copies from a register, and the appointment

For a register document, identify the register keeper and reference from the available evidence and verify the official order procedure and required form. Distinguish what the project holds (e.g. a scan) from what it depicts (e.g. a document bearing a certification mark); verify what the receiving body accepts rather than inferring legal status from the file or image.

When the only route left is the counter in person, treat the visit as a small project of its own:

- Verify the counter serves walk-ins at all before planning travel — „Terminkunden only“ is the common rule, and the next free slot can be weeks out.
- Prepare against the authority's published Bringliste, not the booking confirmation: confirmations list less than the service page, and the recurring missing item is proof of representation — the Vollmacht, or the Erbnachweis when the user acts as the heir. Arriving without it wastes the appointment.
- One call to confirm the file is laid ready saves the journey.
- The preparation note is the paper the user carries: appointment details, per-item bring status, the list of copies to order at the counter, the questions to ask.

## Pitfalls

- One note per export: the second export's note repeats every message the first one held, and the two drift apart.
- Renaming the thread note to the newest message date, then again on the next exchange.
- Splicing the new message onto the stored body by hand — the quoted history shifts, and duplicates follow.
- Filing the attached PDF as if it came separately: it is `attachment:` on the thread, and its checksum is the proof.
- Printing a mail to PDF so that "a file exists". Export the `.eml`.
- Letting every exchange into the case as its own `## Ereignisse` row. The thread has one row, at its start; what moved goes to `## Stand`.
- Reading a reply by its position in the file. A reply written inside the quoted block of an earlier message interleaves quote and answer in the plain text; identify each message by its own header lines (`From:`, `Date:`, the quoted `Von:`/`From:` boundary), never by order — and note the interleaving in the `description:`, or a reader who trusts top-down chronology misattributes the answer.
- Assuming the export carries every enclosure the thread ever had. An `.eml` export usually holds the attachments of the newest message only, so an offer, an Auftrag or a Bescheid sent three replies up is quoted in the history but exists nowhere in the vault — the thread is complete as text and incomplete as evidence. Check `eml_to_md.py`'s attachment list against what the thread's own text announces; when the matter turns on an earlier enclosure, record the gap and get the file from the user before anything cites its terms.
