# Workflow: Promote a Sub-MoC to a Top-Level Project

When a sub-MoC (nested under a parent project like `+Personal`) accumulates enough notes that it warrants its own directory, tag, and INDEX entry, promote it to a standalone top-level project.

## Assessment — When to Promote

| Signal | Threshold |
|--------|-----------|
| Note count | 3+ notes in the sub-project |
| Tag clarity | `project/personal` is too generic to filter these notes |
| Parent MoC health | Parent becomes a "dump container" mixing unrelated topics |
| Task filtering | `path includes projects/personal` catches unrelated notes |
| Growth trajectory | Topic is an active project with legal/financial/ongoing obligations |

## Procedure

### 1. Create Target Directory & Move Notes

```bash
# Determine the new directory name (kebab-case, English or German as appropriate)
# Old: projects/personal/SubProject.md
# New: projects/sub-project/SubProject.md
```

Use `mcp_turbovault_move_note` for each file. TurboVault auto-creates intermediate directories.

**Order:** Move the MoC first, then its child notes. This ensures the target directory exists for subsequent moves.

```python
# Pattern (one call per note):
mcp_turbovault_move_note(
    from="projects/parent/OldNote.md",
    to="projects/new-project/OldNote.md"
)
```

### 2. Update Tags

All notes must get the new `project/<dir>` tag. The old `project/<parent>` tag must be replaced.

Use `mcp_turbovault_update_frontmatter` with `merge=true` to change only the tags without touching content:

```python
mcp_turbovault_update_frontmatter(
    path="projects/new-project/Note.md",
    frontmatter={"tags": ["project/new-project"]},
    merge=True
)
```

**Pitfall:** `merge=true` merges the provided fields into the existing frontmatter. If you want to *replace* the tags array entirely (removing the old tag), pass only the new tag. `merge=false` replaces the entire frontmatter — only use that when you intend to rewrite all frontmatter fields.

### 3. Fix Wikilinks (Critical — Only if Renaming)

**`mcp_turbovault_move_note` does NOT update wikilinks.** If the MoC is being renamed (e.g. `+Erbe WHV` → `+WHV`), every note that has `[[+Erbe WHV]]` in its body or frontmatter will have a broken link.

**Fix sequence:**
1. Use `mcp_turbovault_get_backlinks(path="projects/old-path/+OldName.md")` to find all referencing notes BEFORE moving
2. After the move, update all references:
   - **Body wikilinks:** Use `mcp_turbovault_edit_note` with SEARCH/REPLACE to change `[[+OldName]]` → `[[+NewName]]`
   - **Frontmatter `topics`:** Use `mcp_turbovault_update_frontmatter` with `merge=true` to update the topics array
   - **INDEX entries:** Update the path and display name

**For frontmatter `topics` specifically:**
```python
mcp_turbovault_update_frontmatter(
    path="projects/new-project/Note.md",
    frontmatter={"topics": ["[[+NewMoC]]"]},
    merge=True
)
```

**Pitfall:** `topics` in frontmatter is a YAML string array, NOT a real wikilink. `get_backlinks("+NewMoC.md")` will NOT find notes via their `topics` field. You MUST also have real `[[wikilinks]]` in the body for graph traversal. The `## MoCs` body section is where backlink discovery works.

### 4. Update the Project INDEX

**Before** (sub-MoC listed as a bullet under parent):
```markdown
## [[projects/parent/+Parent|+Parent]] — Parent Project
Description.
- [[projects/parent/+Sub]] — Sub description
```

**After** (lifted to own top-level entry):
```markdown
## [[projects/sub-project/+Sub|+Sub]] — Meaningful Short Title
Routing description — one or two sentences explaining scope, so agents
can decide whether to file new notes here.

## [[projects/parent/+Parent|+Parent]] — Parent Project
Parent description (now shorter, no longer listing the sub-project).
```

**Rules for the INDEX entry:**
- Use `##` heading with `[[path/+MoC|+DisplayName]]` link format
- First sentence: high-level scope
- Second sentence (optional): concrete examples of content
- Language: follow the vault's language policy for the project
- Update the `updated` date in the INDEX frontmatter

### 5. Clean Up the Parent MoC

Update the parent MoC (`+Parent.md`) to no longer list the promoted sub-project under "Core Notes." Instead, add a "Related Projects" or "See Also" section with links.

**Before:**
```markdown
## Core Notes
- [[+Sub]] — Description
```

**After:**
```markdown
## Related Projects
- [[projects/sub-project/+Sub|+Sub]] — Brief pointer
```

### 6. (Optional) Create a Task Note

Each top-level project benefits from a dedicated tasks-query note. This gives the user a single-page dashboard of all open tasks filtered by project directory.

Create `projects/<project>/Aufgaben.md` (or `Tasks.md` for English-language projects):

```markdown
---
description: All open tasks for <project> — sorted by priority
type: zettel
tags:
  - project/<dir>
topics:
  - "[[+ProjectMoC]]"
---

# Aufgaben — <Project>

```tasks
not done
path includes projects/<dir>
sort by priority
```

---

Topics:
- [[+ProjectMoC]]
```

The `path includes projects/<dir>` filter ensures the tasks query only picks up tasks from notes in this project's directory.

## Pitfalls Summary

| Pitfall | Consequence | Prevention |
|---------|-------------|------------|
| `move_note` doesn't update wikilinks | Broken `[[links]]` everywhere | Use `get_backlinks` before moving, then systematic SEARCH/REPLACE |
| `update_frontmatter` merge behavior | Accidentally clears frontmatter | Use `merge=true` for targeted updates |
| `topics` is not a real wikilink | `get_backlinks` won't find notes by topics | Always have body `[[wikilinks]]` + `## MoCs` section |
| Renaming a MoC but not updating references | Broken links persist across the vault | Check all files that referenced the old name |
| Forgetting to update INDEX `updated` field | Staleness tracking breaks | Manually set `updated: YYYY-MM-DD` after structural changes |
