# Maps of Content (MoCs)

MoCs are navigation notes that emphasize relationships between notes through curated link lists with brief descriptions. Use `./assets/moc-template.md` as the default MoC structure. If the selected vault's root `AGENTS.md` or files referenced by it define different MoC conventions, follow the vault-local rules instead.

## Naming

- Unlike regular notes, MoCs must use a plain topic label as the title.
- Prefix MoC filenames with a '+' sign to make them visually distinct in navigation and backlinks.
- Examples: `+AI.md` with `# AI`, `+Personal Agents.md` with `# Personal Agents`

## Structure And Content

- Provide start-here orientation.
- Curate links with meaningful descriptions that are like an abstract.
- Group links by theme.

## Root MoC
An MoC must integrate into the vault graph, see `./references/vault-graph.md`

- There is a vault root MoC `+Index` with `type: moc`.
- Top-level MoCs should ultimately link to `[[+Index]]` through `topics`, explicit links, or both.

## Nesting

- MoCs can be nested.
- If a topic becomes too broad, create sub-MoCs and link them from the parent MoC.
- Keep the parent MoC as the entry point and push detailed navigation into nested MoCs.

## Required linking for sub-MoCs

When you introduce a sub-MoC:
- The parent MoC must explicitly link to the sub-MoC in its curated link list.
- The sub-MoC must link back to the parent MoC via `topics` and an explicit inline wikilink.

Rationale: nested MoCs are only useful if they are discoverable through the graph.

## Maintenance

- Update continuously.
- Start from MoCs for exploration and update links as needed.
- Do not restructure the vault without approval.
