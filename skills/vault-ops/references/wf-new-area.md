When creating a new area:

1. Create the area directory: `mkdir -p <vault-path>/area/<name>` (nicht nötig wenn mit TurboVault — `write_note` erstellt dirs automatisch)
2. Create a MoC with `+` prefix: `<name>/+<Name>.md`
3. Add the area to the vault's `AGENTS.md` Area Map with its scope and language
4. Add bi-directional links in `INDEX.md` and the new MoC

Follow instructions in `./references/moc-writing.md` when creating the MoC

**Pitfall:** The AGENTS.md Area Map is the canonical list of areas. An area directory without a AGENTS.md entry is orphaned; an AGENTS.md entry without a directory is misleading. Keep them in sync.
