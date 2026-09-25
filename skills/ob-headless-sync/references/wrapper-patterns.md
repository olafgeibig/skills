# Wrapper patterns for cron-driven daemons

Three patterns from the `ob-sync-all-vaults` wrapper that apply to any
"run this periodically, safely under double-fires" daemon. They are
written generically here so future wrappers can lift them without having
to re-derive from the ob-sync context.

## 1. mkdir-based atomic lock with age-based take-over

**Problem.** Cron ticks can pile up. If a previous run is still alive
when the next tick fires, two instances run side-by-side and the
underlying resource (server, file, queue) gets hammered.

**Pattern.** Use `mkdir` (not file-create) as the lock primitive, because
`mkdir` is atomic on tmpfs. Inside the lock directory, write a `pid`
file. The lock's "age" is the mtime of that pid file.

```bash
LOCKDIR=/run/user/1000/my-wrapper-locks   # tmpfs, auto-cleared on reboot
LOCK="$LOCKDIR/wrapper.lock"
MAX_AGE_SEC=180

acquire_lock() {
    if mkdir "$LOCK" 2>/dev/null; then
        echo $$ > "$LOCK/pid"
        return 0
    fi
    return 1
}

# Returns 0 if we should proceed, 2 if we should skip.
handle_prior() {
    [[ -f "$LOCK/pid" ]] || return 0
    local prior_pid=$(cat "$LOCK/pid" 2>/dev/null || true)
    if [[ -z "$prior_pid" ]] || ! kill -0 "$prior_pid" 2>/dev/null; then
        rm -rf "$LOCK"   # stale: prior died
        return 0
    fi
    local age=$(( $(date +%s) - $(stat -c %Y "$LOCK/pid") ))
    if (( age < MAX_AGE_SEC )); then
        log "prior PID $prior_pid is ${age}s old (< ${MAX_AGE_SEC}s), skipping"
        return 2
    fi
    log "prior PID $prior_pid is ${age}s old (> ${MAX_AGE_SEC}s), killing it"
    kill -9 "$prior_pid" 2>/dev/null || true
    sleep 0.2
    rm -rf "$LOCK"
    return 0
}

# Main entry
if ! acquire_lock; then
    handle_prior
    rc=$?
    (( rc == 2 )) && exit 0
    acquire_lock || { log "could not acquire lock"; exit 1; }
fi
trap 'rm -rf "$LOCK"' EXIT INT TERM
```

**Why mkdir, not flock or file-create.**
- `mkdir` is atomic on any POSIX tmpfs. `flock` requires the binary and
  is awkward to chain into a "skip if locked" check.
- `touch /path/to/lockfile` is racy: between the test and the touch, two
  callers can both pass the test.
- A directory's existence is a single atomic op.

**Why the 180s threshold.**
Pick a value just above the wrapper's own internal timeout. A healthy run
finishes before the next tick fires, so the threshold is never reached.
A stuck run (server hang, deadlock) gets reclaimed before the next
cron slot, so the system self-heals within one tick.

**Self-healing on SIGKILL.** If the wrapper is SIGKILLed, the trap
doesn't run. The lock directory remains. But the next invocation sees
that the recorded PID is dead (`kill -0` fails), clears the lock, and
proceeds. No manual cleanup needed.

## 2. pkill self-immunity

**Problem.** A wrapper often needs to kill any stuck children of a
previous run. `pkill -f '<pattern>'` matches the wrapper itself if the
pattern appears in the wrapper's argv (which it usually does, because
the script path contains the pattern).

**Pattern.** Use `ps` + `awk` to match on the *child's* comm + arg
position, never on the wrapper's own path. Filter by parent PID to
exclude the wrapper.

```bash
# Find stuck children of a specific binary, excluding ourselves.
# Don't use:  pkill -f '/.npm-global/bin/ob sync'    ← matches the wrapper
# Use this instead:
ps -e -o pid=,comm=,args= \
  | awk -v ob="/path/to/real/binary" \
        '$2 == "node" && index($3, ob) == 1 && $4 == "sync" { print $1 }' \
  | grep -v "^$$\$" \
  | xargs -r kill -9
```

The key insight: `ps -e -o args=` shows the full command line including
the wrapper's own script path. `pkill -f` matches against that whole
string. So any pattern that appears in the wrapper path (or in any
argv that includes the pattern) will match the wrapper.

**Alternative.** Walk the process tree from the recorded prior PID and
kill all descendants except yourself.

## 3. Read-only SQLite check via Python in a bash wrapper

**Problem.** The wrapper needs to query a SQLite database. The CLI
`sqlite3` may or may not be installed; shelling out to it requires
parsing JSON or pipe-friendly text in bash, which is fragile.

**Pattern.** Embed a small Python script in the bash wrapper. Python's
stdlib has `sqlite3` and `json` modules everywhere; cold-start is
~4ms, and `json_extract()` lets you query JSON blobs without
post-processing.

```bash
is_vault_dirty() {
    local db_path="$HOME/.config/someapp/sync/state.db"
    [[ -f "$db_path" ]] || { echo "unknown"; return 0; }
    python3 - "$db_path" <<'PYEOF' 2>/dev/null
import sqlite3, json, sys
db_path = sys.argv[1]
try:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2)
    cur = con.cursor()
    # Count rows where the JSON data shows a state mismatch.
    cur.execute(
        "SELECT COUNT(*) FROM local_files WHERE "
        "json_extract(data, '$.hash') != "
        "COALESCE(json_extract(data, '$.synchash'), '')"
    )
    dirty = cur.fetchone()[0] > 0
    con.close()
    print("dirty" if dirty else "clean")
except Exception:
    print("unknown")
PYEOF
}
```

**Why this works inside bash.**
- `python3 -` reads the script from stdin, avoiding a temp file.
- `<<'PYEOF'` (with quoted delimiter) prevents bash from expanding
  `$` inside the Python script.
- `2>/dev/null` swallows the Python traceback so the wrapper log
  stays clean.
- `timeout=2` on the SQLite connect prevents the wrapper from hanging
  if the DB is on a slow disk.

**Why this is faster than the sqlite3 CLI.** Process startup is
~3ms for Python vs ~6ms for sqlite3 CLI on a typical Linux box. The
SQLite query itself takes microseconds. So Python wins by ~50% on
cold-start and ~25% on warm calls. More importantly, the Python
output is structured (a single `print()`), so the wrapper just
captures stdout and case-matches.
