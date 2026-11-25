# Audit Trail, Rollback and the Destructive-Operation Gate

TurboVault 4.0.2 gates three tools through client elicitation — `delete_note`, a `move_note` that replaces its destination, and a forced `rollback_note` — and whether that gate protects anything depends entirely on the client (§When the gate cannot work). Granting the agent standing destructive rights is a user decision, and the honest way to support it is to check the recovery guarantee first, then state exactly which part of it is real.

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

- **Only writes that went through TurboVault.** Edits made in Obsidian, by a sync client, by `git`, or through `write_file`/`terminal` leave no snapshot. The stored "before" is the state TurboVault last saw, which may already be behind the file on disk. A note created that way has no `CREATE` entry at all, so the trail cannot say when it appeared: the first entry you find for it is whatever TurboVault did to it next.
- **`MOVE` is not a recorded type on Direct.** A move appears as `DELETE` (old path) + `CREATE` (new path), and the engine refuses a single undo (`Move rollback not yet supported`). Repair a bad move by rolling back both halves, then verify by path — the old file reappears while the moved copy stays, so one call is never the whole repair.
- **The hash chain has holes that are not corruption.** `chain.broken_at: null` means nothing is inconsistent, but `chain.unchained > 0` counts entries written without a `prev_hash`. Those are not tamper-evident; do not describe the whole trail as tamper-proof.
- **Retention defaults to keeping everything**, so snapshot storage grows with every write (single-digit KB per operation is typical). Check `total_snapshot_size_bytes` before claiming unlimited history, and re-check it periodically on a busy vault.
- **Git-backed vaults have no such trail** — the commit history is the record, and these tools are unavailable there.
- On Direct, `delete_note` runs with `force: true` by default, so inbound links do not block a deletion. Check `get_links` yourself before deleting; the snapshot protects the content, not the graph.

## When the gate cannot work

Elicitation asks the client to return content that matches the server's `requestedSchema`. A client that answers `accept` with an empty object never satisfies a schema that declares a required field, so every gated call fails — permanently, and not as a version or configuration problem. That is the case for Hermes: it builds `ElicitResult(action="accept", content={})` and never fills the schema, which is why `delete_note` there reports `Couldn't confirm with the user (… required field 'confirm' is missing)` and changes nothing.

Two things follow, and they decide the setting rather than the workaround:

- **The gate covers one of two equivalent entry points.** `batch_execute` asks nothing, and its `DeleteNote` carries no `confirm_path` — the same deletion, one call away, without the question. A gate that a caller skips by choosing another tool is not a boundary.
- **Repairing the client alone would make it worse.** A shim that answers the schema would leave the batch path silent, so the one moment a human is asked would be missing exactly when many notes disappear at once.

So either make the gate uniform — the same restate-the-target parameter (`confirm_path`) on every delete path, including the batch, which is client-independent and needs no dialog — or turn it off deliberately (§Turning the gate off) and lean on `confirm_path`, `expected_hash` and the trail. Until the server offers the uniform form, the flag is the honest setting, not merely the convenient one.

## Turning the gate off

`--no-confirm-destructive` is a server-wide flag belonging in the MCP server entry's **`args`** list — never in `env` as `TURBOVAULT_NO_CONFIRM_DESTRUCTIVE` (non-string `env` values fail spawn validation and park the server; see `references/troubleshooting.md` §A failed spawn is parked, not retried). Because Hermes leaves MCP elicitation `requestedSchema` fields empty, `references/wf-turbovault-config.md` treats `--no-confirm-destructive` as the baseline Hermes workaround once the user understands the limits above.

Because the flag is read when the MCP subprocess spawns, a running session keeps the old behavior until the owning service restarts; verify via the `registered N tool(s)` log line before testing calls. Outside an authorized config setup/audit, ask before flipping `--no-confirm-destructive`, and state clearly that moves cannot be undone in one step and external edits have no snapshot.

## Working discipline once it is off

- Read the note and its backlinks first; a delete that strands inbound links is still a repair job afterwards.
- Prefer `archive/` over deletion whenever the content has reference value — retirement is reversible, deletion is only recoverable through the trail.
- Report the audit `id` of every destructive operation in the reply, so it can be undone individually later.
- Before a batch that deletes, list the affected paths in plain text and send that list first: a batch is the one destructive path with no question at all.
- A `DELETE` that came from `batch_execute` is restorable like any other: the entry carries `context.tool: batch_execute` and a `before_snapshot_id`, and `rollback_preview` answers `would_create: true` with no warnings. Prove it by preview before promising the undo.
- After a delete, confirm absence with `read_note` or `get_notes_info`; after a rollback, read the restored note and confirm its hash equals `rollback_to_hash`.
