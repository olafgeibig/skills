# Task Management

## Syntax

Obsidian Tasks uses emoji-based metadata inline in markdown checklists.

### Status Model

```markdown
- [ ] I am a task that is not yet done
- [x] I am a task that has been done
- [-] A dropped/cancelled task
- [?] A question/blocked task
- [/] A Half Done/In-progress task
```

### Task Properties

```markdown
- [ ] Submit tax documents 📅 2026-05-15 ⏫ 🔁 every year
```

| Emoji | Meaning | Format |
|-------|---------|--------|
| 📅 | Due date | `📅 YYYY-MM-DD` |
| ✅ | Done date | `✅ YYYY-MM-DD` |
| 🔺 | Highest priority | `🔺` |
| ⏫ | High priority | `⏫` |
| 🔼 | Medium priority | `🔼` |
| 🔽 | Low priority | `🔽` |
| ⏬ | Lowest priority | `⏬` |
| 🔁 | Recurrence | `🔁 every day/week/month/year` |
| 🛫 | Start date | `🛫 YYYY-MM-DD` |
| ⏳ | Scheduled date | `⏳ YYYY-MM-DD` |
| 🆔 | Task ID | `🆔 abc123` |
| ⛔ | Depends on | `⛔ abc123` or `⛔ abc,def` |

### Dependencies (Tasks 6.1.0+)

Tasks can have Finish-to-Start dependencies. A task with `🆔` gets an ID, another references it with `⛔`:

```markdown
- [ ] Write first draft 🆔 draft-1
- [ ] Test with users ⛔ draft-1
```

**Query filters for dependencies:** `is blocking`, `is not blocking`, `is blocked`, `is not blocked`, `has id`, `no id`, `has depends on`, `no depends on`

### Query Blocks

Tasks can be aggregated with fenced code blocks (resolved by Obsidian at render time):

```markdown
\`\`\`tasks
not done
path includes projects/personal
group by filename
\`\`\`
```

Hermes does **not** resolve query blocks. For programmatic search use TurboVault search tools (`mcp_turbovault_search`, `mcp_turbovault_advanced_search`).

---

## Hermes Operations

### Find Tasks

**Pattern search via `rg`** (for checkbox status — Tantivy strips these characters at index time):

```bash
# Get vault path dynamically
mcp_turbovault_get_vault_context()  # → active_vault.path = /home/olaf/vaults/akademeia

# Open tasks (- [ ])
rg --no-heading -e '- \[ \]' <vault-path> --glob '!wiki/**' --glob '!system/**'

# Completed tasks (- [x])
rg --no-heading -e '- \[x\]' <vault-path> --glob '!wiki/**'

# All tasks (any status)
rg --no-heading -e '- \[[ x\-?/]\]' <vault-path>

# Not-done tasks (open + in-progress + question)
rg --no-heading -e '- \[[ ?/]\]' <vault-path>
```

**Keyword search** (for known task topics via Tantivy):

```bash
mcp_turbovault_search(query="Hundesteuer")
mcp_turbovault_advanced_search(query="2026-05", exclude_paths=["wiki/"])
```

### Create a Task

Append to the end of the relevant note using `mcp_turbovault_write_note` with `mode="append"`:

```bash
mcp_turbovault_write_note(
    path="path/to/note.md",
    content="- [ ] New task 📅 YYYY-MM-DD ⏫",
    mode="append"
)
```

Where exactly the task goes depends on context — there is no required section. The task belongs in the note it is thematically related to.

### Complete a Task

Replace `- [ ]` with `- [x]` and add the completion date using `mcp_turbovault_edit_note`:

```bash
# SEARCH must match the exact task line — copy from file, never retype
mcp_turbovault_edit_note(
    path="path/to/note.md",
    edits="""<<<<<<< SEARCH
- [ ] Task description 📅 YYYY-MM-DD
=======
- [x] Task description 📅 YYYY-MM-DD ✅ YYYY-MM-DD
>>>>>>> REPLACE"""
)
```

### Update Due Date

```bash
mcp_turbovault_edit_note(
    path="path/to/note.md",
    edits="""<<<<<<< SEARCH
📅 YYYY-MM-DD
=======
📅 YYYY-MM-NEW
>>>>>>> REPLACE"""
)
```

**Note:** This replaces only the first occurrence. If a note has multiple tasks with the same date, include enough context in the SEARCH block (e.g. the full task line `- [ ] Task name 📅 ...`) to match the specific task.

---

## Notes

- **Emoji in `mcp_turbovault_edit_note`:** Emojis are characters like any other. Never retype — copy the exact string from the file (`mcp_turbovault_read_note` before editing). SEARCH matches the first occurrence only — include enough surrounding text to target the right task.
- **Query blocks are Obsidian-only:** Hermes cannot resolve ```tasks``` blocks. For live queries use `rg` (pattern search for checkbox status) or TurboVault search (keywords).
- **Recurrence is plugin-only:** Hermes can set `🔁 every week`, but the recurrence logic runs only inside Obsidian.
- **Restart required:** New tasks won't appear in query blocks until Obsidian is restarted (plugin caches vault index at startup).
- **No `tasks/` folder needed:** The plugin scans the entire vault. Tasks belong in their context note.
- **Prefer `mcp_turbovault_write_note(path, ..., mode="append")`** over `edit_note` for adding new tasks — simpler and avoids SEARCH/REPLACE complexity.
