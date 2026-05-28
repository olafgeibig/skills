## Vault Health

Use this reference to run consistency checks on a markdown notes vault: find broken links, orphaned notes, duplicates, stale content, and graph structure issues. All tools listed are TurboVault MCP calls.

### What Gets Checked — And What Doesn't

The vault has multiple subsystems with **different rules**. A broken link in `area/` is a real problem; the same pattern in `sources` is expected. This reference accounts for that.

**Default exclusion zones** (can be overridden in AGENTS.md):

| Directory | Reason for exclusion | Exception |
|---|---|---|
| `wiki/` | Per-design isolated subgraphs; SCHEMA.md uses placeholder `[[wikilinks]]` | Check that each wiki domain has an index.md |
| `sources/` | Raw articles from web; `[[@handle]]` links are external refs, not broken links | **Check incoming links**: sources with zero incoming links are candidates for archiving |
| `system/` | `[[moc]]`, `[[note]]` are substitution placeholders, not real links | None |
| `inbox/` | Fresh captures, not yet connected — temporary only | If older than 30 days: suggest integration into the main graph |

### Problem Categorization

Each finding is assigned to a category:

| Symbol | Meaning | Action |
|---|---|---|
| 🔴 **Actual Problem** | Broken Link in `area/` or `projects/` | Fix immediately |
| 🟡 **Expected / System-inherent** | SCHEMA.md `[[wikilinks]]`, Clipping `[[@handle]]` | Document, ignore |
| ⚪ **Context-dependent** | Source with no incoming links, orphan in `sources/` | Review, then decide |

### Three-Tier Approach

The health tools are organised in three escalation levels.

### Tier 1 — Quick Check (Session Pulse)

Run at session start or as a periodic cron job. Fast, low-overhead overview.

1. `mcp_turbovault_full_health_analysis()` → 0–100 score + aggregate counts
2. If score **≥ 80**: "Vault is healthy — X Broken Links, Y Orphans (see Exclusion Zones)" — no further action
3. If score **< 80**: present a short summary and offer to escalate to Tier 2

**Pitfall:** The health score counts *all* broken links and orphans, including those in exclusion zones. A score of 75 can be perfectly normal when many wiki domains or clippings exist. Use the score as a **trend indicator**, not an absolute quality metric.

### Tier 2 — Cleanup Routine (On-Demand)

Systematically address issues found by the quick check.

Before starting: define which directories to include/exclude for this pass. Default: focus on `area/` and `projects/`.

#### Broken Links

`mcp_turbovault_get_broken_links()` — lists every broken `[[wikilink]]` with:
- `source_file` — the note containing the link
- `target` — the missing target name
- `line` — line number in source
- `suggestions` — alternative target names TurboVault could match

**Filter by directory** — entries in `sources/`, `wiki/`, `system/templates/` are typically 🟡 expected:
- `sources/Clippings/[[@handle]]` → external Twitter/X references, don't fix
- `wiki/*/SCHEMA.md:[[wikilinks]]` → template placeholders, don't fix
- Remaining 🔴: Broken links in `area/` and `projects/` → fix

**Fix each:**
1. Read the source note at the relevant line
2. If `suggestions` exist, pick the best match and update the link
3. If no suggestion, either create the missing note or remove the link
4. For batch review: `mcp_turbovault_export_broken_links()`

#### Dead-End Notes

`mcp_turbovault_get_dead_end_notes()` — notes with incoming links but **no outgoing links**. Likely incomplete.

- **🔴** in `area/` or `projects/`: add relevant outgoing `[[wikilinks]]` or a "See also" section
- **🟡** `wiki/*/raw/articles/*`: leaf notes, expected dead-ends (referenced by index and concept notes)
- **⚪** other: depends on note type

#### Source Orphan Check

Sources in `sources/` are only valuable if they have incoming links from the main graph.

1. `mcp_turbovault_get_broken_links()` — filter by `sources/`
2. For each source without incoming links: check if it has a placeholder `[[wikilink]]` (`Unknown`, `@handle`, ...)
3. Result: list of sources **with no connection** to the vault graph → suggest archiving or linking

#### Duplicates

`mcp_turbovault_find_duplicates(threshold: 0.8)` — near-exact copies via SimHash + TF-IDF.

- Compare candidates with `mcp_turbovault_compare_notes()`
- Merge content, delete one, or add explicit cross-links
- Typical case: notes accidentally copied across directories (e.g. `area/food/` + `area/essen/`)

#### Stale Notes

`mcp_turbovault_find_stale_notes(threshold_days: 180)` — notes not recently updated.

- Review each; update content or move to `archive/`
- Skip `wiki/` (articles are reference material, not personal notes)
- Skip `sources/` (raw content, shouldn't be edited)

#### Optional: Full Quality Report

`mcp_turbovault_vault_quality_report()` — per-note quality scores across readability, structure, completeness, and staleness dimensions. Useful for a systematic improvement pass on low-scoring notes.

### Tier 3 — Graph Analysis (Architecture)

Use when evaluating the vault's overall structure and navigation design.

| Goal | Tool | Exclusion Hint |
|---|---|---|
| Are the right notes acting as hubs? | `get_hub_notes(top_n: 10)` | Compare against expected hubs (+Index, area-MoCs) |
| Which notes bridge knowledge domains? | `get_centrality_ranking()` (betweenness) | High betweenness in `wiki/` = normal (siloed domains) |
| Are there disconnected subgraphs? | `get_isolated_clusters()` | ⚠️ **Every** `wiki/*/` domain is an isolated cluster by design. Only check clusters outside `wiki/`. |
| Are there circular reference chains? | `detect_cycles()` | Rare, always 🔴 |
| All metrics in one call | `full_health_analysis()` | Use as entry point, then drill down |

**For isolated clusters:** check each subgraph.
- 🟡 Wiki domains (`wiki/ai/`, `wiki/camp/`, …) are intentionally self-contained — no action needed.
- 🔴 Clusters in `area/` or `projects/` that lack a parent MoC link should be connected.
- ⚪ If a non-wiki cluster has its own index.md and is clearly a standalone topic, discuss with the user.

**For cycles:** read the chain, remove or redirect the weakest link.

### Quick Reference Card

| Check | Command | Effort |
|---|---|---|
| Pulse | `full_health_analysis()` | ~0ms |
| Broken Links | `get_broken_links()` → fix in `area/`+`projects/` | ~5-30min |
| Dead Ends | `get_dead_end_notes()` → supplement | ~5-15min |
| Source Orphans | `get_broken_links()` filtered + `get_backlinks()` | ~2min |
| Duplicates | `find_duplicates(0.8)` → merge/delete | ~5-10min |
| Stale (180d) | `find_stale_notes(180)` → review | ~5-15min |
| Graph | `get_isolated_clusters()` + `get_hub_notes()` | ~5min |
