# Relocate Ingested Content Between Domain Wikis

When a source was ingested into the wrong domain wiki, move the files and fix all references rather than re-ingesting from scratch.

## Trigger

- The user says "that should have gone into `<other-wiki>`" after an ingest
- Follow-up reveals the source fits a different wiki's abstract better
- The raw source was ingested into wiki A, but its entity/concept pages belong in wiki B

## Workflow

**① Move the files** — `mcp_turbovault_move_note` for the raw source and each derived page:

```
mcp_turbovault_move_note(from="wiki/<source>/raw/articles/<file>.md", to="wiki/<target>/raw/articles/<file>.md")
mcp_turbovault_move_note(from="wiki/<source>/entities/<file>.md", to="wiki/<target>/entities/<file>.md")
mcp_turbovault_move_note(from="wiki/<source>/concepts/<file>.md", to="wiki/<target>/concepts/<file>.md")
```

**② Fix wikilinks in the moved files** — `move_note` does NOT update them: same-wiki links use the canonical full vault path `[[wiki/<target>/<type>/<page>]]` (never relative `[[<type>/<page>]]`); cross-wiki links keep their full path `[[wiki/<other>/<type>/<page>]]`; source links point at `[[wiki/<target>/raw/articles/...]]` once raw and derived pages share a wiki. Adjust raw tags to the target wiki's taxonomy (read its `SCHEMA.md`).

**③ Update the source wiki:** revert relationship-only additions on entity pages pointing at the moved content (rewrite substantively changed pages); remove the moved entries from index sections and decrement the page count; remove the ingest log entry or add a correction entry "moved to `wiki/<target>/`".

**④ Update the target wiki:** add entries to the correct index sections, alphabetically; increment the page count; bump "Last updated"; append a standard ingest log entry.

**⑤ Verify:** moved pages load via `read_note`; `get_backlinks` shows appropriate backlinks; source index count decreased and target count increased.

## Pitfalls

| Pitfall | Prevention |
|---|---|
| `move_note` leaves stale wikilinks | Read and fix links after every move |
| Page counts drift in either index | Track +1/−1 per moved file |
| Tag taxonomy violation in the target wiki | Check the target `SCHEMA.md` first |
| Source log still lists the ingest | Rewrite the log (or add the correction entry) |
