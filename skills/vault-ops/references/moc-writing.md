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
- Register each new note in the thematically fitting section of the target MoC: bookmarks under `## Bookmarks`, zettels under their own section (e.g. `## Zettel`), not under concepts.
- Write the description line in the MoC body's language (technical areas English, personal German — not the user's language), bump `updated:`, and set a reciprocal `Topics:` link in the zettel.

## Root MoC
An MoC must integrate into the vault graph, see `./references/vault-graph.md`

- There is a vault root MoC `INDEX.md` with `type: moc`.
- Top-level MoCs should ultimately link to `[[INDEX]]` through `topics`, explicit links, or both.

## Nesting

- MoCs can be nested.
- If a topic becomes too broad, create sub-MoCs and link them from the parent MoC.
- Keep the parent MoC as the entry point and push detailed navigation into nested MoCs.

## Required linking for sub-MoCs

When you introduce a sub-MoC:
- The parent MoC must explicitly link to the sub-MoC in its curated link list.
- The sub-MoC must link back to the parent MoC via `topics` and an explicit inline wikilink.
- The parent MoC registration is the only registration — `area/INDEX.md` lists only area MoCs, never sub-MoCs.

Rationale: nested MoCs are only useful if they are discoverable through the graph.

### Curate an Instance-Specific Sub-MoC

Use for a profile, machine, deployment, or other bounded instance within an existing project.

1. Read the parent MoC, a sibling sub-MoC if available, and the proposed member notes. Search filenames/titles plus body references for the instance identifiers; inspect linked candidates before including them, because a generic dependency or evaluation is not automatically instance-specific documentation.
2. Keep the member list scoped to notes whose primary subject is the instance. Link existing canonical notes rather than copying their facts into the MoC. Do not pad a small, accurate index with generic background material.
3. Describe each member's purpose and evidence status. Distinguish an older overview from the latest recorded operational snapshot; say “latest recorded” rather than “live” unless the underlying runtime was actually checked. A navigation change must not silently endorse stale configuration claims or expand into an unsolicited configuration audit.
4. Create the sub-MoC and register it in the parent. Add the new MoC to each member's frontmatter `topics` and matching body `Topics:` footer, preserving existing parents unless reparenting was requested. Do not add a sub-MoC to the top-level project/area index when no new project/area directory was created.
5. Read back the created MoC and every edited note. Check its outgoing links against the intended parent and members, and incoming links against the parent registration and member footers; then validate the new note. Report validation at its actual scope, not as a clean bill for the whole vault.

## Maintenance

- Update continuously.
- Start from MoCs for exploration and update links as needed.
- Do not restructure the vault without approval.
- Verify that edges resolve, not that link text is present: a bare link (e.g. `[[INDEX]]`) resolves in the graph (`is_valid: true`) but is not listed by forward-link queries.

## Post-Refactor Consistency Checks

After a multi-note restructuring (split, merge, rename, move), verify the MoC against disk — a quick health check catches note counts and broken links, but not MoC-level residue:

- **Duplicates and phantom entries:** parse each `##` section's wikilinks; flag any note listed twice (often under two different category headings) and any link whose `.md` file is missing on disk; compare each category's count against the expected post-refactor size.
- **Body concatenation:** a file-size anomaly — the MoC body repeats 2-3× mid-file, with the same H1 heading appearing again after the `Topics:` footer. Each copy has identical links, so wikilink counting misses it; detect via a size check first (`wc -l` / `ls -la` far above expected), then confirm by reading the tail.
- **Recovery:** read the full file, keep the canonical single copy (usually the LAST copy — appended duplicates are more recent), write it back with overwrite mode, then verify exactly one H1 and one `Topics:` footer.
