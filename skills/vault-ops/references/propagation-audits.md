# Propagation Audits

Changing a canonical value or status is rarely done at the point of change. Copies, restated values, and status echoes live in other notes, tables, and task lists. This reference defines the search-first propagation discipline: change once, audit everywhere, patch in one pass.

## Trigger

Run a propagation audit when:

- a value that exists in more than one place changes — a time, date, price, weight, dimension, address, limit, or ID;
- a status moves (open → done, "to book" → "booked") and lists, tasks, or tables may still show the old state;
- a note is renamed or moved and plain-text references may survive outside the link graph — the mechanical side is covered by the `turbovault-use` skill (`renames-and-refactors.md`); this reference covers the content side.

Not triggered for literal edits with no restated copies (one file, exact text) — execute those directly.

## Inventory first

Before the first patch:

1. Collect search keys: the old value in its common spellings and fragments, the entity's ID or name, the old status string, and the titles of affected notes. Include variant typography (em dash vs hyphen, spaced vs unspaced separators).
2. Search the whole vault for every key — TurboVault `search`/`advanced_search` plus any MoC, index, or overview that enumerates the affected notes.
3. Classify every hit before touching it:
   - **canonical** — the one place that holds the authoritative value; it gets the actual new value;
   - **restated** — a restatement of the value in tables, checklists, dashboards; each needs the new value;
   - **echo** — incidental prose mentions; update when leaving them would make the note wrong;
   - **unrelated** — same string, different referent; never touch.
4. Build ONE consolidated change list from the classified hits.

**Restated values hide in prose.** Inline numbers in sentences (a sleep window restating a flight time, per-day budget lines) are easily missed by file-level scanning; search for the raw numbers and fragments too, not just the formatted versions.

## Specificity

Similar-but-distinct entries must not be merged: two carriers, two bookings, two flights with similar names or numbers. Each propagated value follows its own entity — confirm which referent a hit belongs to before including it, and do not let a fallback or alternative entity's value leak into the propagated one.

The canonical home can move between sessions. Do not patch from memory of where the value used to live; search is the source of truth. If the expected canonical spot is gone, find where it went before patching anything else.

## Patch and verify

- Apply all changes for one value in one pass (an atomic batch where possible) so the vault never rests half-propagated.
- Show the consolidated diff when the hits span multiple files or when any hit needs interpretation; obvious 1:1 substitutions can be patched directly, then reported per file.
- Re-run the original searches afterwards: the old value must return zero hits except deliberate historical mentions.
- Status changes have one extra check: no line may show the old status next to the new one, and a completed item must not remain in an open-items list — phantom rows like this are the classic propagation defect. Conversely, a genuinely unresolved state keeps its open marker; do not "fix" a truthful open status to done.
- Report what changed where, and list anything left unresolved instead of silently closing it.

### Refactor residuum sweep (two calls)

After a rename, deletion, or content refactor, sweep the affected area with two `search_files` calls: `output_mode="files_only"` lists which files still match the old pattern, then `output_mode="count"` shows occurrences per file. Classify every remaining hit:

- **live reference** — active task or current content: fix in place;
- **documentation** — history, "previously was X", an explicit deprecation note: leave it;
- **residuum** — no current link, no documentation value: delete it, then verify the MoC no longer points at it.

Many mentions in one file suggest a live reference; one or two spread across files suggest documentation. The sweep covers the content layer — the re-run check asserts the original keys return zero hits; this sweep extends to the refactor's residue (old names, anchors, superseded content) and classifies what remains.

## Related

- `./references/wf-interpretive-edits.md` — audit → diff → confirm → write for interpretive requests.
- The `turbovault-use` skill — search mechanics; rename and link corrections (`renames-and-refactors.md`).
