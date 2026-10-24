# Audit Trail, Rollback and the Destructive-Operation Gate

TurboVault refuses deletions and replacements until the client confirms them. Granting the agent standing destructive rights is a user decision, and the honest way to support it is to check the recovery guarantee first, then state exactly which part of it is real.

## Before asking for the gate to be turned off

Run these three checks against the vault that will be affected, in this order. They are read-only and take seconds.

1. `audit_log(summary: true)` — `operations_by_type`, `total_snapshot_size_bytes`, `oldest_entry`, `chain`. Coverage starts at `oldest_entry`; anything older is unrecoverable, so say so instead of implying full history.
2. `audit_log(operation: "DELETE", limit: 100)` — every entry must carry a `before_snapshot_id`. An entry without one has no content to restore and cannot be rolled back.
3. `rollback_preview(operation_id: <an existing DELETE>)` — expect `would_create: true`, a `rollback_to_hash`, and `warnings: []`. This proves the restore path without touching a file; a preview never writes.

Report the numbers, not an assurance: operations of each type, snapshot storage, the date coverage begins, and the limits below. "The audit log has everything" is false in four specific ways.

## What the trail records (Direct backend)

One entry per changed path, under `<vault>/.turbovault/audit/`: operation type, path, timestamp, `before_hash`, `after_hash`, `before_snapshot_id`, and a `context` naming the tool, `request_id` and `session_id`.

| Operation | Rollback action |
|---|---|
| `CREATE` | deletes the file it created |
| `UPDATE` | restores the pre-change bytes from the snapshot |
| `DELETE` | recreates the file, including missing parent directories |
| `ROLLBACK` | restores what the rollback itself replaced, when it recorded that |

- A rollback is refused when the path changed since the audited operation, because it would discard the later edit; `force` overrides that and discards it deliberately.
- A rollback is itself audited, so a mistaken rollback can be rolled back.
- `diff_notes(operation_id: …)` shows the before/after content of a recorded operation.

## What it does not cover

- **Only writes that went through TurboVault.** Edits made in Obsidian, by a sync client, by `git`, or through `write_file`/`terminal` leave no snapshot. The stored "before" is the state TurboVault last saw, which may already be behind the file on disk.
- **`MOVE` is not a recorded type on Direct.** A move appears as `DELETE` (old path) + `CREATE` (new path), and the engine refuses a single undo (`Move rollback not yet supported`). Repair a bad move by rolling back both halves, then verify by path — the old file reappears while the moved copy stays, so one call is never the whole repair.
- **The hash chain has holes that are not corruption.** `chain.broken_at: null` means nothing is inconsistent, but `chain.unchained > 0` counts entries written without a `prev_hash`. Those are not tamper-evident; do not describe the whole trail as tamper-proof.
- **Retention defaults to keeping everything**, so snapshot storage grows with every write (single-digit KB per operation is typical). Check `total_snapshot_size_bytes` before claiming unlimited history, and re-check it periodically on a busy vault.
- **Git-backed vaults have no such trail** — the commit history is the record, and these tools are unavailable there.
- On Direct, `delete_note` runs with `force: true` by default, so inbound links do not block a deletion. Check `get_links` yourself before deleting; the snapshot protects the content, not the graph.

## Turning the gate off

`--no-confirm-destructive` / `TURBOVAULT_NO_CONFIRM_DESTRUCTIVE=1` is a server-wide flag, not a per-vault setting. Prefer the environment-variable form on the MCP server entry so the `args` list stays untouched (see `hermes-agent` → `references/native-mcp.md`). The value is read when the MCP subprocess spawns: the running session keeps the old behaviour until Hermes restarts, so a tool call that still refuses after the config write is expected, not a failed write — confirm with the config reader, not by calling the tool.

Ask before flipping it. The user granting destructive rights is not the same as the user accepting that moves cannot be undone or that Obsidian edits have no snapshot; state both.

## Working discipline once it is off

- Read the note and its backlinks first; a delete that strands inbound links is still a repair job afterwards.
- Prefer `archive/` over deletion whenever the content has reference value — retirement is reversible, deletion is only recoverable through the trail.
- Report the audit `id` of every destructive operation in the reply, so it can be undone individually later.
- After a delete, confirm absence with `read_note` or `get_notes_info`; after a rollback, read the restored note and confirm its hash equals `rollback_to_hash`.
