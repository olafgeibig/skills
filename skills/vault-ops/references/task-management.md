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

### Dependencies

Tasks can have Finish-to-Start dependencies. A task with `🆔` gets an ID.

**Legacy syntax (⛔):**

```markdown
- [ ] Write first draft 🆔 draft-1
- [ ] Test with users ⛔ draft-1
```

**Modern syntax (`depends on:`) — Tasks 6.0+:**

Multiline `depends on:` is preferred for readability, especially with multiple dependencies:

```markdown
- [ ] Write first draft 🆔 draft-1
- [ ] Review draft 🆔 draft-review
- [ ] Publish article 🆔 publish-article
  depends on: draft-1
  depends on: draft-review
```

The `depends on:` lines are indented with **two spaces**. Each line specifies one dependency. The parent task's `🆔` must be unique in the vault.

**Pitfall — circular dependencies:** Tasks checks for cycles at render time and shows blocked tasks. Avoid `A → B → A` chains.

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
mcp_turbovault_get_vault_context()  # → active_vault.path = <vault-path>

# Open tasks (- [ ])
rg --no-heading -e '- \[ \]' <vault-path> --glob '!wiki/**' --glob '!system/**'

# Completed tasks (- [x])
rg --no-heading -e '- \[x\]' <vault-path> --glob '!wiki/**'

# All tasks (any status)
rg --no-heading -e '- \[[ x\-?/]\]' <vault-path>

# Not-done tasks (open + in-progress + question) — vault-ops scope
rg --no-heading -e '- \[[ ?/]\]' <vault-path> --glob '!wiki/**' --glob '!system/**'
```

**Keyword search** (for known task topics via Tantivy):

```bash
mcp_turbovault_search(query="<task-topic>")
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

**CRITICAL RULE — Do NOT append tasks to MoCs:** Never append tasks to a Map of Content (MoC) or project-level MoC as a general collection. Tasks must be written inline directly next to the specific content inside the note they belong to, maintaining the rich context of the work.

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
- **Pitfall (No MoC/Central Task Lists):** Never append tasks to a Map of Content (MoC) or collect them in central lists. Tasks must always be written inline, directly next to the specific content in the note they belong to, to preserve context.
- **Prefer `mcp_turbovault_write_note(path, ..., mode="append")`** over `edit_note` for adding new tasks — simpler and avoids SEARCH/REPLACE complexity.
- **Pitfall — Delimiter Format:** `mcp_turbovault_edit_note` requires the git-diff style delimiters: `<<<<<<< SEARCH` (opening), `=======` (separator), `>>>>>>> REPLACE` (closing). Plain `SEARCH`/`REPLACE` without angle brackets will fail with "Parse error: No SEARCH/REPLACE blocks found in input." This is the #1 failure cause.

---

## Workflows

### Review all open tasks across the vault

Use this when asked to "show all tasks" or "review all todos".

1. **Get vault path**: `mcp_turbovault_get_vault_context()` → use `active_vault.path`
2. **Search for non-done tasks** with standard exclusions:
   ```bash
   rg --no-heading -n -e '- \[[ ?/]\]' <vault-path> --glob '!wiki/**' --glob '!system/**'
   ```
   *Use `-n` to get line numbers for later editing.*
3. **Categorize results** by directory:
   - `projects/<name>/` → active tasks. Note priority (⏫, 🔼), due dates (📅), and task IDs (🆔).
   - `archive/` → potentially stale. Read the note's frontmatter — if `status: archived`, flag tasks as likely obsolete.
   - `area/`, `inbox/`, `sources/` → standard context tasks.
   - `wiki/` → excluded by glob (vault-ops is read-only for wiki per AGENTS.md). If the user asks about wiki tasks, mention separately.
4. **Read context for archive notes** — a task under an archived note may be a stale instruction, not an active todo.
5. **Present structured overview** grouped by note, with priorities and due dates. Use a consistent format so the user can quickly scan.
