# Workflow: Task Overview Dashboard note (Obsidian Tasks)

Create (or update) a single dashboard note that contains multiple `tasks` query blocks.

## Why this exists

Hermes cannot resolve ```tasks``` blocks itself — they render inside Obsidian.
So the correct pattern is:
- Hermes writes the dashboard note with the queries
- Obsidian Tasks plugin resolves and renders them

## Patterns

### 1) Due today + overdue

Obsidian Tasks supports “due on/before/after” filters.

Example:

```tasks
not done
(due before 2026-06-03) OR (due on 2026-06-02)
sort by due
```

Notes:
- The “overdue” part is `due before <tomorrow>`.
- The “due today” part is `due on <today>`.
- Use explicit dates to avoid timezone ambiguity.

### 2) Due in the next N days, grouped by path buckets

Example for “next 3 days” (exclude today):

```tasks
not done
due after 2026-06-02
due before 2026-06-06
path includes BitC-
sort by due
```

Repeat blocks for each bucket (e.g. `DFT`, `area/`).

### 3) Remaining open tasks

Example:

```tasks
not done
path does not include BitC-
path does not include DFT
path does not include area/
sort by priority
sort by due
```

## Pitfalls

- `path includes` matches substrings in the full vault-relative path. Choose patterns that are stable (e.g. `area/`), and prefer project folder prefixes.
- If you need to scope to a folder, use an unambiguous prefix (e.g. `projects/BitC-` instead of just `BitC-`) when available.

## Verification

Open the dashboard note in Obsidian and confirm the Tasks blocks render:
- correct counts
- correct grouping
- correct due windows
