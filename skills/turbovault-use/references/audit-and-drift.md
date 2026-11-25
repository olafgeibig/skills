# Audit Trail, Rollback, Destructive Gates, and External Drift

Single reference for what TurboVault records, how rollback works, how destructive-operation confirmation behaves across TurboVault 4.x, and how to detect or recover edits made outside TurboVault.

## 1. What the Direct audit trail covers

On `write_backend: direct`, every mutation through TurboVault's write chokepoint appends to `<vault>/.turbovault/audit/operations.jsonl` with content-addressed pre-change snapshots in `<vault>/.turbovault/audit/snapshots/<sha256>`.

- **Recorded operations:** `CREATE`, `UPDATE`, `DELETE`, `MOVE`, `ROLLBACK`.
- **Two `MOVE` patterns on Direct (verified on 4.0.2):**
  - Plain `move_note` (default `update_backlinks: false`) writes a single `MOVE` entry carrying `new_path`. `rollback_note` does **not** support `MOVE` (`Move rollback not yet supported`) — repair by moving the note back via `move_note`.
  - `move_note(update_backlinks: true)` writes a `DELETE` (old path) plus a `CREATE` (new path) (plus `UPDATE` entries for rewritten referrers) — undo by rolling back both halves (and any rewritten referrers) and verifying both paths.
- **Rollback semantics (`rollback_preview`, `rollback_note`):**
  - `CREATE` → deletes the created file; `UPDATE` → restores pre-change bytes; `DELETE` → recreates the file and missing parent directories; `ROLLBACK` → restores what the rollback replaced.
  - Refuses if the file changed after the audited operation unless `force: true` is passed. Every rollback is itself audited.
  - `diff_notes(left: path, operation_id: id)` inspects the before/after diff of an audited change.
- **Hash chain & retention:** `audit_log(summary: true)` reports `operations_by_type`, `total_snapshot_size_bytes`, `oldest_entry`, and `chain`. `chain.broken_at: null` means no corruption, but `chain.unchained > 0` indicates entries without `prev_hash` (not tamper-evident). Default retention keeps all snapshots (~5–10 KB per operation).
- **Multi-process on one host:** Processes sharing the same vault serialize on the audit file lock and see each other's writes. Across machines they do not.
- **Git-backed vaults (`write_backend: git`):** Commit history is the audit record; `audit_log` and `rollback_note` are unavailable there.

### What the audit trail cannot see

- Any edit made outside TurboVault: Obsidian's editor, sync clients, `git`/`git pull`, other machines, or direct filesystem writes (`write_file`, `patch`, `terminal`). Those changes produce **no snapshot**; the next TurboVault write sees the modified file as its "before" state.
- Verified authorship: `context` (`tool`, `request_id`, `session_id`) is advisory metadata, not an authentication boundary.
- History older than `oldest_entry` in `audit_log(summary: true)`.

## 2. Destructive-operation confirmation (elicitation) and `--no-confirm-destructive`

**Elicitation is never an authorization boundary.** TurboVault prompts via MCP form elicitation (`confirm: boolean`) **only when the connected client advertises `elicitation.form` capability**; a client or CLI bridge that does not advertise `elicitation.form` is **never asked at all** and executes immediately. Always obtain explicit user authorization for destructive operations independently of client elicitation.

Gated paths when the client advertises `elicitation.form`:

- **TurboVault 4.0.x:** 3 paths — `delete_note`, destination-replacing `move_note` (`dest_expected_hash != "absent"` with existing destination), and forced `rollback_note`.
- **TurboVault 4.1.0+:** 5 paths — adds `add_vault` and `batch_execute` calls containing `DeleteNote` or a destination-replacing `MoveNote` (`dest_expected_hash != "absent"` with existing destination). Note that an overwriting `WriteNote` inside `batch_execute` is **not** elicitation-gated.
- `--no-confirm-destructive` (CLI `args` flag; read at server spawn — changing it requires restarting the owning MCP service) turns elicitation off for all gated calls.

### Client behavior & deciding whether to disable the gate

- **Interactive clients advertising `elicitation.form`** (including current Hermes interactive surfaces) prompt the user for `requestedSchema` fields; Hermes's `ElicitationHandler` fails closed (declines) in headless sessions *only when it advertises the capability*. Clients that omit `elicitation.form` (e.g. headless scripts or simple bridges) are not prompted at all. Older clients that advertise `elicitation.form` without filling `requestedSchema` fail every gated call permanently (`Couldn't confirm with the user ...`).
- Keep elicitation **enabled by default**. Enable `--no-confirm-destructive` in `args` (never in `env` — see `references/troubleshooting.md` §2) only as an explicit user decision when unattended destructive calls are authorized or a client cannot answer form elicitations.
- **Before turning `--no-confirm-destructive` on for an existing vault**, verify recovery with three read-only calls and report the exact numbers:
  1. `audit_log(summary: true)` — note `oldest_entry`, operation counts, snapshot size, and `chain`.
  2. `audit_log(operation: "DELETE", limit: 100)` — confirm entries carry `before_snapshot_id`.
  3. `rollback_preview(operation_id: <existing DELETE>)` — confirm `would_create: true`, `rollback_to_hash`, and `warnings: []`.
- State the limits plainly: external edits have no snapshot, `MOVE` entries cannot be rolled back automatically, and coverage starts at `oldest_entry`.

### Working discipline for destructive operations

- Obtain explicit user authorization first; read the target and `get_links`, pass `force: false` by default on Direct `delete_note`, and prefer archiving when content still has value.
- Before a destructive `batch_execute` (including overwriting `WriteNote`s), list every affected path and obtain explicit confirmation.
- Report the audit `id` from `audit_log` (on Direct — `delete_note` does not return it) or the Git commit reference in the handoff.
- Verify deletions via `read_note` or `get_notes_info`, and verify rollbacks by confirming the restored hash equals `rollback_to_hash`.

## 3. Detecting external edits (drift check & watchdog)

Because the Direct audit trail cannot see external edits, this skill bundles two scripts:

| Script | Purpose |
|---|---|
| `scripts/vault-drift-check.py` | Hash one vault (respecting `--exclude` like TurboVault's `excluded_paths`) and classify changes since the last run as `audited` or `external`. Opt-in `--store` atomically hashes and writes post-baseline changed bytes to `objects/<sha256>`. |
| `scripts/vault-drift-all.py` | Iterate vaults in a TurboVault YAML config (requires PyYAML; respects each vault's `excluded_paths`; optional `--vault <name>` filter and opt-in `--store`). Silent when clean (watchdog mode). |

```bash
# Single vault, including historical audit-vs-disk divergence (hash-only)
python3 scripts/vault-drift-check.py --vault ~/Documents/Vault --exclude private --full

# Configured vaults, hash-only watchdog (add --store only when opting into content copies)
python3 scripts/vault-drift-all.py ~/.turbovault/config.yaml
```

- **Privacy & opt-in content storage:** `vault-drift-all.py` defaults to hash-only tracking and forwards each vault's `excluded_paths` via `--exclude`. Both scripts skip symlinks and non-regular files (enforced on the opened descriptor via `O_NOFOLLOW` + `fstat`), so symlinks into excluded folders or outside the vault are never hashed or copied. Pass `--store` only for vaults where copying post-baseline changed note contents into the local state directory is explicitly authorized; use `--vault <name>` to scope to specific vaults.
- **State location (outside the vault):** `$TURBOVAULT_DRIFT_STATE`, else `$HERMES_HOME/state/vault-drift`, else `$XDG_STATE_HOME/turbovault-drift`, else `~/.local/state/turbovault-drift`, keyed as `<vault-dirname>-<sha256(resolved_path)[:8]>/` so vaults sharing a directory name never collide.
- **Exit codes (`vault-drift-check.py`):** `0` clean, `2` external drift, `1` error (including snapshot `--store` failures, which keep the affected manifest entry open for retry on the next run). With `--quiet`, drift exits `0` while errors still exit `1`. (`vault-drift-all.py` exits `1` whenever PyYAML is missing, YAML parsing fails, or any vault check/path fails.)
- **First run is a baseline, not a backup:** The baseline run writes hashes to `manifest.json` only and stores **no file contents** (`--store` copies only files changed in subsequent windows, hashing the exact written bytes atomically so filename and SHA-256 always match). Temporarily unreadable files retain their prior manifest state instead of being reported as deleted and later re-created. Treat the watchdog as a change-detection and post-baseline versioning aid, not a full backup or authoritative audit proof.
- **Pitfalls handled by the scripts:** handle `MOVE` entries (source deletion + `new_path` audited write), keep the maximum timestamp per hash (so an external revert to an older audited hash is not misclassified as drift), skip cloud-placeholder unreadable files (`EDEADLK`/`EBUSY`) and alert only once, and report *content divergence* without inventing a culprit.

### Installing the cron watchdog

Cron jobs only run scripts under `<profile>/scripts/`, so `templates/vault-drift-shim.py` locates the skill's `scripts/vault-drift-all.py` at runtime and pins `CONFIG`, `HERMES_HOME`, and `STATE_ROOT`:

1. Locate the skill's `scripts/` directory. If installed via `skills.external_dirs`, set `TURBOVAULT_DRIFT_SKILL_SCRIPTS` in the shim or cron environment.
2. Copy `templates/vault-drift-shim.py` to `<profile>/scripts/vault-drift-all.py`, and set `CONFIG` to the exact `--config` YAML that profile's TurboVault server uses and `HERMES_HOME` to the profile root (`~/.hermes` for the default profile, `~/.hermes/profiles/<name>` for named profiles).
3. Run the shim once by hand to write the baseline manifest (must exit `0`).
4. Register a `no_agent: true` cron job running the shim, then trigger once manually and confirm silent success.
5. Repeat per profile so each profile maintains its own baseline.

## 4. Restoring an unaudited edit

1. **Diff against TurboVault's last snapshot:**
   ```bash
   diff -u "<vault>/.turbovault/audit/snapshots/<before_snapshot_id>" "<vault>/<path>"
   ```
2. **Restore from drift object store (when `--store` was enabled):** Verify the stored object's SHA-256 matches its filename first (`shasum -a 256 "<state>/objects/<sha256>"` or `sha256sum`), then read the target note via `read_note` for its current `expected_hash` and write the verified content back through `write_note(mode: "overwrite", expected_hash: ...)` so the restore is hash-guarded and audited. Never `cp` an unverified object straight over a vault note.
3. **Older than audit and drift state:** rely on OS/external backups (e.g. Time Machine local snapshots on macOS), not the vault tools.

## 5. Never sync `.turbovault/` via Git

Do **not** commit `<vault>/.turbovault/` into a synced Git repository to bridge machines:

- `operations.jsonl` is an append-only hash chain (`prev_hash`); concurrent appends on two machines merge into a broken chain.
- File locks serialize processes on one filesystem only.
- Routine `git checkout`/`reset` overwrites the recovery evidence itself.

Keep `.turbovault/` gitignored. For cross-machine history, either keep `write_backend: direct` with periodic Git auto-commits (retaining local `audit_log` + `rollback_note`), or explicitly authorize `write_backend: git` on a vault that has **no** second sync layer (`references/vault-configuration.md`).
