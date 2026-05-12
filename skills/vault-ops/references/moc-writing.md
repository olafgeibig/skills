## Scope

Use this file for Maps of Content. For regular notes, use `./reference/note-writing.md`.

## Maps of Content (MoCs)

MoCs are navigation notes that emphasize relationships between notes through curated link lists with brief descriptions.

Use `./reference/moc-template.md` as the default MoC structure.

If the selected vault's root `AGENTS.md` or files referenced by it define different MoC conventions, follow the vault-local rules instead.

## Naming

- Unlike regular notes, MoCs must use a plain topic label as the title and H1.
- Prefix MoC filenames with a '+' sign and H1 titles to make them visually distinct in navigation and backlinks.
- Examples: `+AI.md` with `# AI`, `+Personal Agents.md` with `# Personal Agents`, `INDEX.md` with `# INDEX`

## Structure And Content

- Provide start-here orientation.
- Curate links with one-line descriptions.
- Group links by theme.
- Use wiki links or markdown links. Avoid plugin-specific dependencies.

## Nesting

- MoCs can be nested.
- If a topic becomes too broad, create sub-MoCs and link them from the parent MoC.
- Keep the parent MoC as the entry point and push detailed navigation into nested MoCs.

## Root MoC

- There is a vault root MoC named `[[Index]]` with `type: moc`.
- Top-level MoCs should ultimately link to `[[Index]]` through `topics`, explicit links, or both.
- `topics` must be a YAML list/array of quoted wiki-link strings. See `./reference/note-writing.md`.

## Maintenance

- Update continuously.
- Start from MoCs for exploration and update links as needed.
- Do not restructure the vault without approval.
