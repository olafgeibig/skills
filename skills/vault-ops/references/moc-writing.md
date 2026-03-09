## Maps of Content (MoCs)
Definition: Higher‑order navigation notes that emphasize relationships between notes; curated link lists with brief descriptions.

- Template: `<skill-dir>/references/moc-template.md`

### Naming (MoCs are not claims)
- Unlike regular notes, MoCs must use a plain topic label as the title/H1 (no claim/proposition titles).
- Use ALL CAPS for MoC filenames and H1 titles to make them visually distinct in navigation and backlinks.
  - Examples: `HR.md` with `# HR`, `BOSCH APPS.md` with `# BOSCH APPS`, `INDEX.md` with `# INDEX`.

### Structure & content
- Provide "Start here" orientation.
- Curate links with one‑liners; group by theme.
- Use wiki/markdown links; avoid plugin dependencies.

### Nesting
- MoCs can be nested. If a topic becomes too broad/complex, create sub‑MoCs and link them from the parent MoC.
- Keep the parent MoC as the entry point; push detailed navigation into the nested MoCs.

### Root MoC
- There is a vault root MoC named [[Index]] (type: moc).
- Top‑level MoCs should ultimately link up to [[Index]] (via `topics` and/or explicit links), so the vault has a single navigable entry point.
- `topics` MUST be a YAML list/array of *quoted wiki-link strings* (see `<skill-dir>/references/note-writing.md`).

### Maintenance
- Update continuously; no formal approval states.
- Start from MoCs for exploration; update links.
- Don’t restructure without approval.
