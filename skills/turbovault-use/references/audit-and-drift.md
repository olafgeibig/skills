# Audit Trail and Edits From Outside TurboVault

Use when the question is "what changed, and did TurboVault see it?" — auditing a vault change, restoring something nobody recorded, or deciding whether an edit can be trusted because it has a snapshot behind it.

## What the audit trail covers

Every mutation that goes through TurboVault's own write path is recorded, because the direct substrate writes the entry at the single write chokepoint (a new write path inherits the trail without opting in).

- **Location:** `<vault>/.turbovault/audit/operations.jsonl`, one JSON object per line, newest last. Snapshots next to it in `audit/snapshots/<sha256>`.
- **Fields:** `id`, `timestamp` (UTC), `operation`, `path`, `before_hash`/`before_snapshot_id`, `after_hash`/`after_snapshot_id`, `prev_hash`, optional `context` (tool, request_id, session_id) and `metadata`.
- **Operations:** `CREATE`, `UPDATE`, `DELETE`, `ROLLBACK`. A **move is not an operation of its own** — on the direct backend it appears as `DELETE` of the source path plus `CREATE` of the destination, so a wrong move is undone by two rollbacks, not one.
- **Snapshots are content-addressed and kept by default.** Retention by count/age exists in `turbovault-core` but the default keeps everything: budget roughly 5–10 KB per operation.
- **Rollback** (`rollback_preview`, `rollback_note`) restores `before_snapshot_id`, recreates missing parent directories, refuses when the note changed since that operation, and records itself (so a rollback can be rolled back). Rolling back a `DELETE` recreates the file.
- **Not available on Git-backed vaults** — there the commit history is the audit trail.
- **Same machine, several processes:** all TurboVault instances appending to one vault share this file and serialize on its file lock, so two Hermes profiles on one host do see each other's writes. Across machines they do not.

## What it cannot see

Anything that does not write through TurboVault:

- Obsidian's own editor, a sync client, `git`/`git pull`, other machines, and any agent that used `write_file`, `patch`, `edit_note` on a stale handle, or `terminal` instead of the MCP note tools.
- Authorship. `context` is advisory (the crate README says so explicitly): nothing verifies it, and an external change carries none.
- Anything older than the log. Check `audit_log(summary: true)` for `oldest_entry` before promising a restore.

A change made outside TurboVault has **no snapshot**, so `rollback_note` cannot help. That gap is what the drift check fills.

## Drift check

Two scripts ship with this skill:

| Script | Purpose |
|---|---|
| `scripts/vault-drift-check.py` | One vault: hash the notes, classify the window since the last run against the audit log |
| `scripts/vault-drift-all.py` | Every vault in a TurboVault config file, printing only the ones with drift |

```bash
# one vault, full picture (historical drift included)
python3 scripts/vault-drift-check.py --vault ~/Documents/Vault --full

# every vault in a config, watchdog mode (silent when clean, exit 0)
python3 scripts/vault-drift-all.py ~/.turbovault/config.yaml
```

**State** lives outside the vault: `$TURBOVAULT_DRIFT_STATE`, else `$HERMES_HOME/state/vault-drift`, else `$XDG_STATE_HOME/turbovault-drift`, else `~/.local/state/turbovault-drift`, in `<vault-dirname>-<sha256(path)[:8]>/` — the path hash is required because two vaults can share a directory name (`…/dft-csl/csl`, `…/drivalia-csl/csl`). Contains `manifest.json` (path → hash, mtime, size) and `objects/<sha256>` with the content of every changed note when `--store` is set.

**Classification.** Only the window since the previous run is reported, so historical divergence does not alert daily:

- `audited` — the new content hash equals an `after_hash` from the audit log recorded in the same window. TurboVault made this change. Silent.
- `external` — no such entry. Somebody else changed it; the tip is copied into `objects/` so a version exists.

`--full` prints the whole audit-vs-disk picture instead: notes that differ from TurboVault's last write, notes audited as present but missing, and how many notes have no audit entry at all (usually the vast majority — a vault edited mainly in Obsidian).

**Exit codes:** `0` clean, `2` external changes, `1` error. `--quiet` prints only when there is something to report and exits 0 either way — that is the cron/watchdog mode.

### Wiring it as a watchdog

Cron only accepts scripts under the profile's `scripts/` directory, so a shim lives there and executes the skill copy. `templates/vault-drift-shim.py` is that shim: it discovers the skill's `scripts/` directory at runtime (`$TURBOVAULT_DRIFT_SKILL_SCRIPTS` first, then `$HERMES_HOME/skills/**/turbovault-use/scripts`, then `~/work/skills/**`, so a moved repository fails loudly instead of reporting "clean"), pins the TurboVault config and the drift state root, and exits non-zero when either is missing.

**Installation procedure, per profile or instance:**

1. **Locate the skill's scripts** — `$HERMES_HOME/skills/**/turbovault-use/scripts` or the repo checkout. `TURBOVAULT_DRIFT_SKILL_SCRIPTS` is the escape hatch when the layout is unusual.
2. **Copy the template** to `$HERMES_HOME/scripts/vault-drift-all.py` (create the directory) and edit its `CONFIG` line to the config file *this* installation starts the server with — `~/.turbovault/config.yaml` is only the default; many setups pass `--config ~/.turbovault/<name>.yaml` in the MCP args or `env`.
3. **Run it once by hand.** The first run is a baseline: it writes `manifest.json` and states what already diverges. It must exit 0. A missing-script or missing-config error means the shim is wrong, not the skill.
4. **Create the cron job** — `no_agent: true`, any schedule, `deliver` to the chat that should hear about drift. The job's entire output is the script's stdout.
5. **Fire it once manually** — expect silence. A silent run is the only accepted success; an error names the broken path.
6. **Repeat per profile.** State is per `$HERMES_HOME`, so each profile keeps its own baseline. Two profiles on one host each see the other's TurboVault writes as *audited* (shared audit log) but keep separate drift state — expected, not a defect.

Pin `--state-root` in the shim (the template does), otherwise a scheduled run without `HERMES_HOME` silently starts a second baseline.

## Restoring something the audit never saw

1. **Compare against the last audited version** — every audit entry carries the hash of what TurboVault last wrote, and the snapshot is still on disk:

   ```bash
   diff -u "<vault>/.turbovault/audit/snapshots/<before_snapshot_id>" "<vault>/<path>"
   ```

   That answers "what changed" even for an external edit, and gives a manual rollback source.
2. **From the drift object store** — if a run saw the change, the content sits in `objects/<sha256>`: `cp <state>/objects/<sha> <vault>/<path>`, or paste it through `write_note` so the restore itself is audited.
3. **Older than the log** — macOS Time Machine local snapshots (`tmutil listlocalsnapshots /`) cover the last hours; mounting them needs `sudo`. On other platforms this is the backup system's job, not the vault's.

## Pitfalls

- **A revert to an already-audited hash** looks unaudited if the log's hash → timestamp map keeps the first write. Keep the maximum timestamp per hash, or an external revert to an older audited state reports as drift.
- **Cloud storage refuses reads.** OneDrive/iCloud placeholders can return `EDEADLK`/`EBUSY` on a non-warming read. Skip the file, report it once (compare with the previous run's unreadable list) and never treat it as drift, or every run alerts on the same placeholder.
- **A directory name is not an identity.** Two vaults can share one; key state by the resolved path.
- **The first run is a baseline**, not a report. It writes the manifest and states what already diverges; only the second run compares.
- **Content, not provenance.** Hash comparison says "not written by TurboVault", never "written by Obsidian" or "by that other agent". Do not narrate a culprit.

## If the vault moves to Git-backed writes

Do **not** solve the cross-machine gap by committing `.turbovault/` into a synced repository:

- `operations.jsonl` is append-only with a per-writer hash chain (`prev_hash`); two machines appending produce divergent files that merge into a broken chain — git cannot re-chain entries it did not write.
- The file lock serializes processes on one filesystem only, so ordering and atomicity disappear across machines.
- A routine `git checkout`, `reset`, or a bad merge then rewrites or drops the very evidence a restore would use.
- Snapshots are content-addressed and merge cleanly; the log is the part that does not.

Prefer TurboVault's own `write_backend: git`: every write (and every batch) becomes one commit, authorship is real, `git revert` is the rollback, `audit_log` is documented as unavailable there, and drift collapses into `git status --porcelain` plus `git log @{u}..HEAD`. The write-safety rules for that backend are in `references/editing-and-batch-operations.md`.

**Two Git options, not one.** Switching `write_backend: git` *replaces* the audit trail with commits. Keeping `direct` and adding a Git auto-commit layer on top (obsidian-git, or a cron `git add -A && git commit`) is the cheaper move when the goal is cross-machine history rather than per-write commits: the local audit log and `rollback_note` keep working, every writer's change lands in a commit at the interval, and `.turbovault/` stays gitignored. The cost is that an edit stays invisible to other hosts until commit *and* push — the same window a sync client has, except visible through `git status` and `git log @{u}..HEAD`. Choose the backend switch when per-write commits and real authorship must be the primary record, and only on a vault that sits outside every other sync layer: one sync mechanism per vault, never two.
