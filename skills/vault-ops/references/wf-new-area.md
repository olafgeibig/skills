When creating a new area:

1. Create the area directory: `mkdir -p <vault-path>/area/<name>` (not necessary with TurboVault — `write_note` creates directories automatically)
2. Create a MoC with `+` prefix: `<name>/+<Name>.md`
3. Add bi-directional links in `<vault-path>/area/INDEX.md` and the new MoC

Follow instructions in `./references/moc-writing.md` when creating the MoC

For a marginal topic without its own area: do not create a new area — put the note in the nearest existing area and state the delimitation explicitly (what belongs here, what deliberately in the neighbouring area).
When scope grows, prefer a sub-MoC (`area/<area>/+<Topic>.md`, type `moc`, `topics:` → parent MoC) over a new area; register it in the parent MoC only — `area/INDEX.md` lists only area MoCs (the `+Name.md` files on area level), never sub-MoCs.
Register the area: `area/INDEX.md` is the area map (not AGENTS.md) — add a section with an abstract = purpose + language + delimitation; bump `updated:`.
