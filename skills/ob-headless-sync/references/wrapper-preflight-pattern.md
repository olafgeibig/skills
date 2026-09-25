# Wrapper Pre-Flight: The "Skip-if-Fresh, Kill-if-Stale" Pattern

The `ob-sync-all-vaults` wrapper implements a reusable pre-flight pattern for any periodic background task that may hang (network calls, file syncs, external API requests). This document extracts the pattern so it can be applied to other wrappers.

## Why the pattern is needed

Cron (and systemd-timer) is **fire-and-forget**: when the scheduler triggers a job, it does not know whether the previous job is still running. For tasks that may take longer than the schedule interval, you get one of two failure modes:

1. **Pile-up:** each trigger starts a new invocation. After 10 triggers, 10 hung processes are running, contending for locks, hammering the server, eating CPU.
2. **State corruption:** the second invocation sees the first's locks / temp files / partial state and either errors out, silently corrupts data, or does the work twice.

The classic Unix solution is a lockfile (PID in `/var/lock/foo`), but that requires the second invocation to **read** the lockfile and **decide** what to do. The naive implementation is "skip if lock exists" — but a crashed first invocation leaves a stale lock that blocks all future invocations forever.

The improved pattern: **check both liveness AND age.**

## The pattern

Three layers, in order of execution at the start of every wrapper invocation:

```
1. Try to acquire the lock (mkdir /path/to/lock.d/)  ← atomic on tmpfs
2. If acquire failed:
     a. Read PID from the existing lock
     b. Is the process alive? (kill -0 $pid)
        No  → stale lock, remove it, try acquire again
        Yes → check the lock's mtime (stat -c %Y lock.d/pid)
              age < THRESHOLD  → exit 0 (another fresh invocation is running)
              age >= THRESHOLD → kill the prior, remove lock, try acquire again
3. If we hold the lock:
     set trap "rm -rf lock.d" EXIT INT TERM
     ... do the work ...
```

## Concrete example (from `ob-sync-all-vaults`)

```bash
LOCKDIR=/run/user/1000/ob-sync-locks
WRAPPER_LOCK="$LOCKDIR/wrapper.lock"
THRESHOLD_SEC=180

acquire_wrapper_lock() {
    if mkdir "$WRAPPER_LOCK" 2>/dev/null; then
        echo $$ > "$WRAPPER_LOCK/pid"
        return 0
    fi
    return 1
}

handle_prior_wrapper() {
    if [[ ! -f "$WRAPPER_LOCK/pid" ]]; then
        return 0   # no prior wrapper, proceed
    fi
    local prior_pid prior_age_sec
    prior_pid=$(cat "$WRAPPER_LOCK/pid" 2>/dev/null || true)
    if [[ -z "${prior_pid:-}" ]] || ! kill -0 "$prior_pid" 2>/dev/null; then
        rm -rf "$WRAPPER_LOCK"   # stale lock, clear and proceed
        return 0
    fi
    prior_age_sec=$(( $(date +%s) - $(stat -c %Y "$WRAPPER_LOCK/pid") ))
    if (( prior_age_sec < THRESHOLD_SEC )); then
        log "prior wrapper PID $prior_pid is ${prior_age_sec}s old (< ${THRESHOLD_SEC}s), skipping"
        return 2
    fi
    log "prior wrapper PID $prior_pid is ${prior_age_sec}s old (> ${THRESHOLD_SEC}s), killing it"
    kill -9 "$prior_pid" 2>/dev/null || true
    sleep 0.2
    rm -rf "$WRAPPER_LOCK"
    return 0
}

# Main flow
if ! acquire_wrapper_lock; then
    handle_prior_wrapper
    rc=$?
    if (( rc == 2 )); then
        exit 0   # skip — another fresh wrapper is doing the work
    fi
    if ! acquire_wrapper_lock; then
        log "could not acquire wrapper lock after cleanup; aborting"
        exit 1
    fi
fi
trap 'rm -rf "$WRAPPER_LOCK"' EXIT INT TERM
```

## Threshold selection

The `THRESHOLD_SEC` value should be:
- **Larger than** the longest expected normal runtime (otherwise you'll kill healthy runs)
- **Smaller than** the cron/timer interval (otherwise the next tick won't fire and won't know to kill)

For `ob sync` with a 120s internal timeout and 30-min cron: `THRESHOLD_SEC=180` (120s max + 50% buffer, well under 1800s cron interval).

For a different workload, run a few healthy invocations with `time` to find the typical p99, then add a 50–100% buffer.

## Where to put the lock

- **`/run/user/<uid>/<app>-locks/`** — systemd-managed tmpfs, auto-cleaned on reboot. Best for user-level wrappers. This is what `ob-sync-all-vaults` uses.
- **`/var/lock/<app>.lock`** — traditional location, persistent across reboots. Good for system-level services, but requires cleanup script on boot or accept that stale locks can persist.
- **`~/.cache/<app>-locks/`** — fallback if neither of the above is writable.

**Avoid `/tmp/`** — on most distros, `/tmp` is cleaned on boot but also on timer (e.g. systemd-tmpfiles after 10 days). Your wrapper might find a stale lock that someone else (a deleted user) put there.

## Why `mkdir` for the lock, not `flock` or `touch`

- `flock` (BSD file lock): requires an open file descriptor, which you can't easily pass to a cron-triggered process. `flock` is great for **daemon** processes that want to coordinate with each other; it's the wrong tool for **cron wrappers** that are each short-lived and independent.
- `touch` + check for existence: races. Two wrappers can `touch` the file before either reads it.
- `mkdir`: atomic on tmpfs (and on every Linux filesystem since the 90s). If two wrappers race to `mkdir`, exactly one succeeds. Then write the PID into the new directory, and your age-check works on the directory's contents.

## Self-immunity in pkill

If your wrapper also kills other hung children (like `cleanup_zombies` does for `node ob sync`), you must be careful not to kill your own descendants. The naive `pkill -f '<command>'` matches the wrapper's own command line too.

The robust approach (from the `cleanup_zombies` function in the wrapper):
```bash
# Only consider processes whose argv starts with the exact path of the hung binary
# AND whose argv includes " sync" as the next word
# (so we don't kill `ob sync-list-local` or unrelated `ob` invocations)
ob_pids=$(ps -e -o pid=,comm=,args= 2>/dev/null \
          | awk -v ob="$OB" '$2 == "node" && index($3, ob) == 1 && $4 == "sync" { print $1 }' \
          | grep -v "^${$}\$" || true)
if [[ -n "$ob_pids" ]]; then
    kill -9 $ob_pids 2>/dev/null || true
fi
```

The combination of:
1. `comm == "node"` (so we don't match other node processes)
2. `index($3, ob) == 1` (so we don't match the wrapper's own path, which contains `$OB`)
3. `$4 == "sync"` (so we don't match `ob sync-list-local` or `ob help sync`)
4. `grep -v "^$$$"` (defense in depth — exclude our own PID)

...gives you a kill that only hits the right processes, never the wrapper.

## Testing the pattern

Three tests, all should pass:

1. **No prior:** run wrapper directly. Should acquire lock, do work, release.
2. **Prior is young and alive:** spawn a "fake" prior that holds the lock for 60s, then in another terminal run the wrapper. Should log `skipping` and exit 0.
3. **Prior is old and alive:** spawn a "fake" prior that holds the lock, then `touch -d "300 seconds ago" lock.d/pid`, then in another terminal run the wrapper. Should log `killing it` and proceed.

For the test, a "fake" prior can be:
```bash
mkdir /run/user/$(id -u)/test-locks/wrapper.lock
echo $$ > /run/user/$(id -u)/test-locks/wrapper.lock/pid
sleep 60
rm -rf /run/user/$(id -u)/test-locks/wrapper.lock
```
Spawn it via `terminal(background=true)`, give it a known PID, then run the real wrapper from a separate terminal call.

## When NOT to use this pattern

- **Single-fire daemons** — they should use `flock` instead, since they hold the lock for their entire lifetime.
- **Truly fire-and-forget tasks** that are idempotent and cheap (e.g. `echo $(date) >> /tmp/log`). Pile-up is harmless.
- **Coordinated multi-writer queues** — use a real queue (Redis, RabbitMQ, file-based job runner like `at` or `taskd`).
- **Tasks where the work is in the database, not the process** — if two cron ticks both succeed at writing the same data, you don't need a wrapper-level lock at all; the database handles concurrency.

For the `ob sync` use case, the pattern is a clear win: the work is slow (up to 120s), can hang, and pile-up wastes server resources.
