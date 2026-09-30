---
name: ob-headless-sync
description: Obsidian Headless Sync — wrapper management, dirty-check gating, cron@1min scheduler, and recovery for the ob sync service on headless machines. Includes the `ob sync-list-local` parser pitfalls and the reusable wrapper patterns (mkdir atomic lock, pkill self-immunity, embedded Python+SQLite check).
metadata:
  version: "0.7.4"
  source: https://github.com/olafgeibig/skills
  origin: durin-2026-04-18
  updated: "2026-07-08"
---

# Obsidian Headless Sync — Wrapper & Cron Management
The Obsidian Headless Sync runs every minute via a user crontab. The wrapper does a 4ms SQLite dirty-check before invoking `ob sync`, so ticks that hit a clean vault are no-ops. The agent does NOT need to trigger syncs manually — cron handles everything with a 60s ceiling for both iPad edits and Hermes-assisted note edits.

## Architecture (decided 2026-07-08)

**Why this is the way it is** — a single intentional design after we tried
several alternatives and hit the limits of each:

1. **The problem:** Obsidian-Sync on durin kept hanging every few days
   because the upstream `ob sync` Node client has a known WebSocket race
   condition (Issue #1 in `references/upstream-bugs.md`). A second stuck
   process appears inside the timer-driven service. Wrapper-based mitigations
   can hide the symptom but cannot fix the upstream bug.
2. **What we tried and rejected:**
   - **Syncthing instead of Obsidian-Sync.** Rejected as too much
     architecture-migration for a problem we could solve locally.
   - **systemd-timer at 3-min interval.** Works most days but the user's
     session with the agent then waits 3 min for a sync to land — too slow
     when actively editing notes with the agent.
   - **Manual sync only.** Loses iPad-edits when the user is not actively
     editing.
   - **Smart dual-mode (high frequency during agent sessions, low frequency
     idle).** The agent cannot reliably detect "session active" and even if
     it could, the user wants to focus on working, not toggling sync modes.
   - **Agent-trigger on every write.** Fragile — agent forgets the call
     often enough that iPad-side content stays stale, and it costs an extra
     tool-call per write.
   - **inotify file-watcher daemon.** Rejected as too much code for the
     payoff (sub-second latency not required).
3. **What we chose:** **cron @ 1 minute + SQLite dirty-check inside wrapper**
   + wrapper-level pre-flight to prevent parallel syncs.
   - Cron @ 1 min: max 60s sync latency for any change, whether from iPad,
     from Hermes agent edits, or from anywhere else.
   - 4ms SQLite dirty-check per tick: most ticks are no-ops, no `ob sync`
     is invoked, no server load, no zombie risk.
   - Wrapper pre-flight: skips while a recent sync is alive, takes over if
     a sync is stuck for >180s. Safe under double-fires.
   - Manual override: `OB_SYNC_FORCE=1 ob-sync-all-vaults` to bypass the
     dirty-check when the user explicitly wants a sync right now.

**The result** (in operation since 2026-07-08): a single line in crontab,
a single bash script, a 4ms check. No timer service, no inotify daemon,
no agent-side hook. Latency ≈ 60s ceiling. Idempotent under all observed
fail modes (server-hang, double-fire, stale-lock, partial-success DB
state).

## User preference — short, action-oriented answers (2026-07-08)

When this skill fires, the user wants:
- One clear recommendation, not three options
- The reasoning in 1–2 sentences, then execute
- Do NOT keep exploring after a decision is made ("warum machen wir das eigentlich selber mit so einem Timer und nicht einfach als Cronjob" = stop surveying, start doing)
- Skip Syncthing and other architectural rewrites by default — user said "ist mir jetzt zu kompliziert"
- When the user asks a "why don't we use X" question mid-implementation, treat it as a hint that the current approach is wrong. Stop, answer briefly, and switch to the user's suggestion. Do not defensively justify the current approach.
- When offering cron / timer / hook alternatives, default to the simplest one. The user has explicitly said they don't want smart-mode toggles or per-write hooks — they want one cron line, one wrapper, no magic.
- When adding a new trigger mechanism, ask "is this strictly simpler than cron@1min + dirty-check?" before proposing anything more complex. If not, do not propose it.

## Quick Diagnostic

```bash
# 1. Is ob reachable?
which ob || echo "ob not in PATH — use: ~/.npm-global/bin/ob"

# 2. Timer / cron status
systemctl --user list-timers --all --no-pager | grep ob-sync
# or, if migrated to cron:
crontab -l | grep ob-sync

# 3. Recent service logs
journalctl --user -u ob-sync-all.service -n 20 --no-pager
```

## Skip-the-sync check: SQLite dirty-state query (v0.5, 2026-07-08)

`ob sync-status` only reports config — it does NOT tell you if a sync is needed. The dirty-state lives in the SQLite DB that the ob client writes to. Querying it is ~100ms and avoids triggering a server roundtrip when nothing has changed.

**DB path:** `~/.config/obsidian-headless/sync/<vault_id>/state.db` — discover the vault_id with `ob sync-list-local`.

**Note:** the CLI `sqlite3` is NOT installed on durin. Use Python:

```python
import sqlite3, json
db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
def load(t):
    return {p: json.loads(d) for p, d in db.execute(f"SELECT path,data FROM {t}")}
local, server, pending = load("local_files"), load("server_files"), load("pending_files")
common = set(local) & set(server)

# Vault is dirty if ANY of these:
#  1. local-only files (not yet pushed)
#  2. server-only files (not yet pulled)
#  3. local.hash != local.synchash (edited since last sync)
#  4. local.synchash != server.hash (server moved on, we have stale view)
#  5. pending.count > 0
is_dirty = (
    len(set(local) - set(server)) > 0
    or len(set(server) - set(local)) > 0
    or any(local[p]["hash"] != local[p]["synchash"] for p in common)
    or any(local[p]["synchash"] != server[p]["hash"] for p in common)
    or len(pending) > 0
)
```

A full inspection script lives at `references/scripts/check-dirty.py` in this skill. Run it before each sync to skip the 120s server roundtrip when nothing has changed. **Important caveat:** if the wrapper's last sync was killed mid-way (Issue #1 hang), the DB is stale. A fresh sync is required before the DB can be trusted again — the check is only valid after at least one successful sync has completed.

## Agent trigger after vault writes (v0.6, 2026-07-08) — *superseded by cron@1min (v0.7)*

> **Status 2026-07-08:** This section documents an idea that was initially
> considered (agent calls wrapper after each write). It was superseded because
> the agent is unreliable at remembering to call it, and the alternative — cron
> @ 1 minute with the 4ms dirty-check — gives the same UX (max 60s sync latency)
> for zero cognitive cost. Kept here for context.

Cron @1min covers everything: iPad-edits picked up within 60s, agent edits
picked up within 60s, no special "agent hooks" needed, no skill-section
required for the agent to read first.

**Decision (2026-07-08):** User chose cron @ 1 min over inotify/agent-hook
because:

- Implementation is one character change (`*/5` → `*`)
- 4ms dirty-check on each tick means almost all ticks are no-ops
- The "after-write" agent hook idea was abandoned as too fragile (agent
  forgets to call it, requires the skill to be loaded, costs a tool-call
  per write)
- 60s latency is acceptable for both iPad and active-session edits

## The `ob` Binary

- **Full path:** `/home/olaf/.npm-global/bin/ob`
- **PATH may not include it** in subshell/agent contexts — always use the full path in scripts
- **Manual sync test:** (only for diagnostics — never invoke manually as part of normal workflow)
  ```bash
  /home/olaf/.npm-global/bin/ob sync --path /home/olaf/vaults/akademeia
  ```

## Known Issue: Timer Dies After Service Kill/Timeout

**Symptom:** Timer shows `inactive (dead)` even though it is `enabled` and has `Persistent=true`.

**Trigger:** If the service (`ob-sync-all.service`) is killed with SIGKILL after a timeout (e.g. from `systemctl stop`), the User Manager daemon can lose track of the timer's next-execution state. `systemctl status` shows `Trigger: n/a` and the `NEXT` column shows an old/distant timestamp or `-`.

**Fix — run all three commands:**
```bash
XDG_RUNTIME_DIR=/run/user/1000 systemctl --user daemon-reload
XDG_RUNTIME_DIR=/run/user/1000 systemctl --user reset-failed
XDG_RUNTIME_DIR=/run/user/1000 systemctl --user start ob-sync-all.timer
```

Then verify:
```bash
systemctl --user list-timers --all --no-pager | grep ob-sync
# Should show: Active: active (running) and a near-future NEXT time
```

**Do NOT just `systemctl --user restart ob-sync-all.timer`** — the daemon-reload and reset-failed are required to clear the stale state.

## Companion Issue: The `ob` Node Process Stuck in "Connecting..."

**Symptom:** Service status shows `deactivating (final-sigterm)` indefinitely. The `node` child of the `ob sync` wrapper has been alive for **days** in a `Connecting...` state (visible in `journalctl`). `list-timers` shows the last successful sync was N days ago, even though the timer itself looks active.

**Root cause:** The `ob sync` Node process hung during initial WebSocket connect — the 120s `timeout` wrapper sent SIGTERM, but the Node process **ignored the signal** and stayed in `Connecting...` indefinitely. Because the service stays in the "active" state, the timer thinks it's fine; but no sync is actually completing.

**Why the standard 3-command fix is insufficient:** `daemon-reload` + `reset-failed` + `start ob-sync-all.timer` only resets the **timer's** state — they do **not** kill the stuck Node process that's holding the service hostage. The service stays in `deactivating (final-sigterm)` because the parent bash is waiting for the child Node to exit, and the child Node is in uninterruptible sleep on a network syscall.

**Fix — kill the stuck process BEFORE the standard sequence:**
```bash
# 1. Find ALL stuck processes — there will be 4:
#    - 2 bash wrappers (ob-sync-all-vaults, parent + child)
#    - 1 `timeout 120` parent
#    - 1 `node` doing `ob sync` (the actual hung process)
ps -ef | grep -E "ob.sync|ob-sync" | grep -v grep

# 2. SIGKILL all 4 in one command
kill -9 <BASH_PID1> <BASH_PID2> <TIMEOUT_PID> <NODE_PID>

# 3. Standard 3-command sequence — but WITHOUT sudo, see Pitfall below
XDG_RUNTIME_DIR=/run/user/1000 systemctl --user daemon-reload
XDG_RUNTIME_DIR=/run/user/1000 systemctl --user reset-failed
XDG_RUNTIME_DIR=/run/user/1000 systemctl --user start ob-sync-all.timer
```

**Skip the `timeout 10 systemctl ... stop` and `start ob-sync-all.service` smoke-test** — they're unnecessary once the stuck PIDs are dead, and they can themselves hang on a freshly-restarted systemd user instance. Verify recovery via the timer's `Trigger:` field instead:

```bash
systemctl --user status ob-sync-all.timer --no-pager | grep Trigger
# Expected: "Trigger: <future time within ~3min>"
```

Then verify with `list-timers` (should show fresh `NEXT` within ~3min) and `journalctl -n 5` (should show new "All vaults synced" lines).

**The "Warning: ... can still be activated by ob-sync-all.timer" message** after `stop` is normal and expected — the service will be re-triggered by the timer on the next interval. Don't try to disable the timer; just kill the stuck process and restart.

**Diagnostic tell:** If `journalctl -u ob-sync-all.service` ends with "Connecting..." followed by no "Disconnected" / "Fully synced" line, and the corresponding `node` process has been alive for >1 hour, the process is stuck and the standard 3-command fix will not work.

**Historical trigger:** 2026-06-18 — the ob sync was stuck since 2026-06-14, a 4-day outage caused by a hung Node process. The fix (kill -9 + daemon-reload + reset-failed + start) restored sync within seconds.

## Two-tier pre-flight + dirty check in the wrapper (v0.6, 2026-07-08)

The wrapper at `~/.local/bin/ob-sync-all-vaults` has THREE gates, all implemented with `mkdir` and a SQLite query (atomic on tmpfs, self-healing on process death):

1. **Wrapper-level lock** — `~/.config/.../ob-sync-locks/wrapper.lock/` with `pid` file inside. The wrapper checks it on every invocation:
   - If a prior wrapper is alive AND its pid file is <180s old → **skip** (don't pile up parallel syncs)
   - If a prior wrapper is alive AND its pid file is >180s old → **kill it** and take over (recover from a stuck prior run)
   - If a prior wrapper's pid file exists but the process is dead → clear the stale lock and proceed
2. **Per-vault dirty-check** — Before invoking `ob sync` for a vault, query `~/.config/obsidian-headless/sync/<vault_id>/state.db`:
   - Local files where `hash != synchash` (edited since last sync) → dirty
   - Pending files queue non-empty → dirty
   - Server has many more files than local → dirty (something to pull)
   - All checks pass → log "clean, skipping", no `ob sync` invoked (4ms total)
3. **Per-vault lock** — `~/.config/.../ob-sync-locks/<vault_name>.lock` with the subshell PID. Same logic per-vault.

The 180s threshold is the user's choice: it's longer than the wrapper's own 120s internal timeout, so a healthy sync never gets killed. It's short enough that a true hang (Issue #1) doesn't waste a full timer cycle.

When upgrading the wrapper, archive the old version as `ob-sync-all-vaults.old.YYYYMMDD` for rollback — the user has done this multiple times and uses the archive to compare behavior after regression reports.

## Cron vs systemd-timer (decision, 2026-07-08)

User asked: why not just use cron instead of systemd-timer? The wrapper's two-tier pre-flight makes cron **strictly equivalent** to the timer for this use case — both fire every N minutes, both call the wrapper, and the wrapper handles the "prior still running" case either way.

**Cron is preferred** going forward because:
- The systemd timer's "Trigger: n/a" failure mode (companion issue above) doesn't exist
- Cron doesn't need the user-bus + `XDG_RUNTIME_DIR` dance
- Cron survives reboots and user-session changes without `daemon-reload`
- One file (`crontab -l`) is easier to inspect than three (`.service` + `.timer` + `/etc/systemd`)

**Active cron line (set 2026-07-08, updated to 1-min interval):**
```
PATH=/home/olaf/.local/bin:/usr/local/bin:/usr/bin:/bin
* * * * * /home/olaf/.local/bin/ob-sync-all-vaults >> /home/olaf/.local/share/ob-sync-cron.log 2>&1
```

Set `PATH` so the wrapper finds `timeout` (used inside the per-vault subshell). The wrapper has a 4ms SQLite dirty-check before triggering `ob sync`, so most 1-min ticks are no-ops. Capture stdout to a log file because cron doesn't forward output anywhere by default.

**Why 1 minute, not 3 or 5:** User chose 1 min to keep latency low for both active-session edits and iPad push-pulls. The 4ms dirty-check makes this cheap — most ticks are 4ms no-ops, only dirty ticks pay the 1-5s `ob sync` roundtrip.

## Files

| File | Purpose |
|------|---------|
| `/home/olaf/.local/bin/ob-sync-all-vaults` | Wrapper script — three layers of defense (v0.6, 2026-07-08): (1) wrapper-level pre-flight with age-based lock stealing, (2) per-vault dirty-check via state.db (4ms), (3) per-vault 120s `timeout` cap and stale-lock cleanup. Archive of older versions kept as `ob-sync-all-vaults.old.YYYYMMDD` for rollback (e.g. `ob-sync-all-vaults.old.20260708`). |
| `/home/olaf/.config/systemd/user/ob-sync-all.timer` | Masked 2026-07-08 (`/dev/null` symlink). Legacy; cron replaces it. |
| `/home/olaf/.config/systemd/user/ob-sync-all.service` | Legacy; matches the masked timer. |
| `~/.config/obsidian-headless/sync/<vault_id>/state.db` | The ob client's sync state — SQLite, the wrapper queries it for the dirty check before `ob sync` runs. |
| `~/.local/share/ob-sync-cron.log` | Cron stdout capture — wrapper output, append-only. |

## References

- `references/upstream-bugs.md` — Known GitHub issues in `obsidianmd/obsidian-headless`. Issue #1 (WebSocket microtask race, open) is the root cause of most hangs; Issue #4 (stale `.sync.lock`) is the lock-directory workaround origin.
- `references/scripts/check-dirty.py` — Standalone Python script that runs the dirty-state SQLite query for one or all vaults. Returns exit 0 (clean) or 1 (dirty), so it composes with shell logic.
- `references/sync-status-check.md` — 7-line Status-Snapshot-Recipe for "check the sync" type queries. Use this recipe instead of dumping the full diagnostic.
- `references/sync-list-local-format.md` — The exact 4-line-block format `ob sync-list-local` emits, common parsing pitfalls, and a reference parser. Always read this before writing any code that consumes `ob sync-list-local` output; the format is NOT the `Vault: <name> (<id>)` that some third-party examples show.
- `references/wrapper-patterns.md` — Three reusable patterns lifted from this wrapper, written generically so other cron-driven daemons can adopt them: (1) `mkdir`-based atomic lock with age-based take-over, (2) `pkill -f` self-immunity workaround, (3) embedded Python+SQLite dirty-check inside a bash wrapper.

## Service / Timer Commands

```bash
# Full restart (daemon-reload included)
XDG_RUNTIME_DIR=/run/user/1000 systemctl --user daemon-reload
XDG_RUNTIME_DIR=/run/user/1000 systemctl --user reset-failed
XDG_RUNTIME_DIR=/run/user/1000 systemctl --user start ob-sync-all.timer

# Check status
XDG_RUNTIME_DIR=/run/user/1000 systemctl --user status ob-sync-all.timer --no-pager
XDG_RUNTIME_DIR=/run/user/1000 systemctl --user status ob-sync-all.service --no-pager

# Stop completely
XDG_RUNTIME_DIR=/run/user/1000 systemctl --user stop ob-sync-all.timer ob-sync-all.service

# View logs
journalctl --user -u ob-sync-all.service -n 50 --no-pager
```

## Pitfalls

- **Do NOT prefix `systemctl --user` with `sudo`.** Three failure modes observed 2026-06-27:
  - `sudo systemctl --user daemon-reload` → `Failed to connect to bus: No medium found` (root has no `XDG_RUNTIME_DIR`)
  - `sudo XDG_RUNTIME_DIR=/run/user/1000 systemctl --user daemon-reload` → `Failed to connect to bus: Operation not permitted` (root can't open your user bus socket)
  - `sudo -E systemctl --user daemon-reload` → silently inherits broken env, same root-bus failure

  The fix is to run **as the owning user** (no sudo) with `XDG_RUNTIME_DIR` set explicitly. Confirmed working sequence on 2026-06-27:
  ```bash
  XDG_RUNTIME_DIR=/run/user/1000 systemctl --user daemon-reload
  XDG_RUNTIME_DIR=/run/user/1000 systemctl --user reset-failed ob-sync-all.timer ob-sync-all.service
  XDG_RUNTIME_DIR=/run/user/1000 systemctl --user start ob-sync-all.timer
  ```

- **Set `XDG_RUNTIME_DIR` explicitly** even without sudo, when running from a non-login shell (cron, agent tool, tmux pane without user session). Otherwise systemd may report a misleading bus error.

- **`pkill -f "ob sync"` alone is not enough** when the timer is also wedged — User Manager loses timer state and needs the daemon-reload + reset-failed + start sequence, not just the kill.

- **`.sync.lock` is a directory, not a file.** After killing stuck sync processes, check `/home/olaf/vaults/akademeia/.obsidian/` — if a `.sync.lock` directory remains (empty, owned by olaf), it is stale debris from killed zombies. Remove with `rmdir`, not `rm -f`. Stale `.sync.lock` causes `ob sync` to refuse with `Another sync instance is already running for this vault` even though no process is actually running. Symptom-first diagnostic: if `ps -ef | grep "ob sync"` shows nothing but `ob sync` still says "Another sync instance...", it is the stale lock directory. Fix: `rmdir /home/olaf/vaults/akademeia/.obsidian/.sync.lock`.

- **`pkill -f '/.npm-global/bin/ob sync'` matches too broadly** (v0.5 pitfall). It will match the wrapper bash itself if the path appears in its argv, causing self-kill. Use `ps -e -o pid=,comm=,args= | awk '$2=="node" && $3 ~ ob && $4=="sync"'` for precise matching, or filter by parent PID. See `references/wrapper-patterns.md` for the generic pattern.

- **`ob sync-list-local` does NOT emit `Vault: <name> (<id>)`** (v0.7 pitfall). Third-party examples and the `ob` docs sometimes show that format; the actual output is a 4-line block with the 32-hex vault-id on its own line, followed by `    Path: <path>` and `    Host: <server>`. A parser that matches `Vault:` will silently produce an empty vault list and exit cleanly with "no vaults discovered". See `references/sync-list-local-format.md` for the exact format and a working parser.

- **Three stuck-process variants exist.** Variant A (documented above): the `timeout 120` parent sends SIGTERM but the child Node ignores it and stays in `Connecting...` for days. Variant B: the wrapper script was re-invoked **without** a `timeout` parent at all, so the Node process has no kill signal and only dies when killed manually. Variant D (v0.5): the wrapper is robust, but Issue #1 makes `ob sync` itself hang server-side — the wrapper's 120s timeout fires, returns exit 124, and the wrapper's trap cleans up cleanly. The symptom "Node alive for >3 min with no progress" is now NORMAL during a server-hang, not a stuck wrapper.

- **Server-side slowness looks like client-side stuck but isn't.** Symptom: `ob sync` connects to the server successfully, then logs `Connecting...` and nothing else for the full 120s timeout, then `Received signal to shut down... Disconnected from server` — with NO `Detecting changes...` or `Fully synced` line. This is **not** a hung Node process (Node is responsive and gets cleanly killed). It means the server is taking longer than 120s to respond, usually because another client device has pushed a large changeset. Fix recipe **does not apply** — the timer will recover on its own once the server catches up. Don't kill the process, don't reset-failed, just wait for the next timer tick (3 min) and try again. If stuck for >30 min, the server may genuinely be down — check Obsidian status page.

- **Dirty-check can show stale "dirty" after a partial sync (v0.6).** Observed 2026-07-08: after a successful "Fully synced" round-trip, the SQLite query still reports 32 files as `hash != synchash` because `ob sync` did not update those rows in the DB (likely a quirk of how the ob client tracks files whose server-side hash already matches). The wrapper logs "dirty, syncing" again on the next tick, the sync runs through cleanly in ~3 s, but the DB rows stay "dirty". Workaround: this is benign — the next sync is a no-op server-side, just useless local work. **Don't trust the dirty check as proof that something real needs syncing;** it's an optimization, not a contract. If the sync keeps getting triggered and you're worried about server load, run `references/scripts/check-dirty.py` to inspect what specifically is marked dirty.

- **File visible on disk + in DB but not in Obsidian's file pane = Obsidian lazy-load, not a sync bug (v0.7, 2026-07-15).** User reported "I edited a note on a sibling agent 5 min ago and don't see it in Obsidian". Diagnostic showed: file present in `~/vaults/akademeia/`, present in `state.db` with matching `hash`/`synchash`, `Fully synced` in cron log within 60s of creation. Obsidian's file-watcher only refreshes panes for directories you've navigated to recently; an `area/familie/` edit while you were working elsewhere doesn't propagate to the file pane. Fix is in Obsidian, not the sync: Ctrl/Cmd+P → type the note name → Enter, or click into the target folder in the file pane. **Rule of thumb:** before debugging sync, check Obsidian's command palette for the file. If it's there, sync is fine; if it's not, then debug sync.

- **Sibling-agent edits on other devices reach durin within 60s, not immediately (v0.7, 2026-07-15).** Cron @ 1 min is the sync floor for all clients. If a sibling agent on BE18-C-0001G or iPad creates/updates a note, expect a 0–60s lag before it lands on durin's local filesystem. Do NOT promise "instant" sync to the user — it's 1-min tick granularity at best. If they say "I don't see the file" within that window, it's expected; if after 60s, check the file-pane pitfall above first.

- **Sibling-agent on iPad: file mtime in `state.db` shows `device='iPad'`, file lives in `.obsidian/*.json` drift** (v0.7, 2026-07-15). The `.obsidian/appearance.json`, `core-plugins.json`, `graph.json` etc. drift entries in `server_files` (vs `local_files`) come from iPad and `boromir` devices syncing Obsidian config that's intentionally not synced to disk. This is normal and benign — `ob sync` doesn't try to materialize them. Don't flag these as "missing files" during dirty-check inspection.


## Timer vs Service — Key Distinction

- `ob-sync-all.timer` — the **scheduler** (fires every 3 min) — LEGACY, see Cron section
- `ob-sync-all.service` — the **worker** (runs `ob sync`)
- A timer in `inactive (dead)` state means **no syncs are being triggered**
- A service that fails/times-out does NOT automatically restart the timer
- A service in `deactivating (final-sigterm)` state usually means a child process is stuck — see "Companion Issue" above
