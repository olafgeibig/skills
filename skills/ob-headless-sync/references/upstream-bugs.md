# Upstream Bugs in `obsidianmd/obsidian-headless`

These are the GitHub issues in the official `obsidianmd/obsidian-headless` repository that explain why `ob sync` hangs intermittently. The local wrapper has workarounds for the secondary issues, but the primary hang root cause (Issue #1) has no local fix.

## Issue #1: WebSocket microtask race (PRIMARY HANG)

**Status:** Open as of 2026-07-08. Affects all current versions.

**Symptom:** `ob sync` connects to the server successfully, then logs `Connecting...` and nothing else for the full 120s internal timeout, then `Received signal to shut down... Disconnected from server` — with no `Detecting changes...` or `Fully synced` line. The Node process is responsive to signals (cleanly killed by `timeout 120`); the hang is in a network read that never completes.

**Root cause** (from the Wireshark POC in the issue thread): when the server sends a WebSocket packet containing BOTH a text frame and a binary frame, the client's `pull()` function is waiting on a `dataPromise` that is only resolved by the text frame. The binary frame arrives first (in the same TCP packet), the client reads the packet, sees text + binary, and:
- processes the text frame (resolves the promise)
- but the binary frame was already consumed by the packet-read syscall, so it's not delivered to the data callback

Net effect: the binary frame is silently dropped, the client expects more data, the server has nothing more to send in that round, and the pull hangs for the rest of the connection lifetime.

**Why this is hard to fix locally:** it requires changes to the WebSocket library or the pull() function's frame-handling order. No client-side workaround is reliable. (We tried shortening the timeout, lengthening the timeout, killing and retrying — none changes the probability of the race firing.)

**What we do instead:** accept intermittent loss. The wrapper's 30-min cron cadence means at most one failed sync per 30 min window; the next sync has a fresh socket and may avoid the race.

**Maintainer note from the issue thread:** the maintainer acknowledged the bug but has not produced a fix in the time since reporting (months, per the Wireshark attachment timestamp).

## Issue #4: Stale `.sync.lock` directory (SECONDARY)

**Status:** Closed without a real fix (workaround documented in the issue thread).

**Symptom:** After `ob sync` is killed with SIGKILL or crashes, the directory `/path/to/vault/.obsidian/.sync.lock/` is left behind, empty, owned by the user. Subsequent `ob sync` invocations fail with `Another sync instance is already running for this vault` even though no process is actually running.

**Root cause:** `ob` uses `mkdir`-based locking (not `flock`). On normal exit, the lock directory is removed. On abnormal exit (SIGKILL, OOM kill, hard crash), it is not. The lock is never given an expiry timestamp or a heartbeat, so it lives forever until manually removed.

**Workaround** (implemented in the local wrapper):
```bash
rmdir "$vault_path/.obsidian/.sync.lock" 2>/dev/null || true
```
`rmdir` is safe — it only removes empty directories, so it never touches a real lock.

## Issue #382: Server-side overload (related but separate)

**Status:** Open, low maintainer engagement.

**Symptom:** Sync occasionally hangs for many minutes (much longer than the 120s internal timeout) on one or more devices, then recovers. Suspected server bottleneck at Obsidian's sync infrastructure.

**Local observation (2026-07-08):** we saw the 120s timeout fire repeatedly with `Connecting...` and no `Detecting changes` — this matched Issue #382's profile. The server eventually caught up and a later sync succeeded.

**Workaround:** wait. The cron + pre-flight setup retries on the next tick.

## Searching for new issues

When investigating a new symptom, search the upstream repo with:
- `is:issue` filter for "hang", "stuck", "sync", "websocket"
- the `obsidianmd/obsidian-headless` repo (note: hyphenated, not "obsidian-headless")
- the linked `obsidianmd/obsidian-cli` repo for CLI-specific issues

## What we cannot fix upstream-side

- The WebSocket frame-handling order in `pull()`
- The `mkdir`-based locking (would require a major refactor)
- Server-side sync throughput

All three are upstream-only.

## Issue (local-observed, not yet reported upstream): Stale `hash != synchash` after Fully Synced

**Status:** Locally observed 2026-07-08, not yet reported. Reproducible: run `ob sync` until it logs `Fully synced` / `Disconnected from server`, then query state.db.

**Symptom:** After a successful "Fully synced" round-trip, the SQLite query still reports ~32 files in the akademeia vault as `hash != synchash`. Inspecting one of these shows:
- `local.hash == server.hash` (identical, no real divergence)
- `local.mtime != server.mtime` (different modification timestamps)
- `local.synchash` is empty string for these files (never updated)

**Root cause (suspected):** The `ob sync` client skips updating the local `synchash` field for files where the local hash already matches the server hash — the assumption being "nothing changed, no need to record a new synctime". This is logically correct for "is anything dirty?" purposes but breaks any external dirty-check that relies on `synchash` being set after every sync.

**Workaround in the wrapper (v0.6):** the dirty-check treats these stale rows as "dirty" anyway, so the wrapper will re-invoke `ob sync` on the next cron tick. The next sync is a no-op server-side (server sees nothing changed), completes in 2–3 s, and the DB still shows the same stale rows. Net effect: harmless, ~3 s of useless work per cron tick on vaults that are in this state. This is acceptable; the alternative (filtering on the broken `synchash` field) would risk missing real changes.

**Why not reported upstream yet:** it would only matter to people using external dirty-checks (like our wrapper). Most users just see "synced, no error" and never look at the DB. If this becomes a maintenance burden (e.g. cron ticks start triggering server rate-limits), it becomes worth reporting. For now: documented locally as a known quirk.

## Issue (local-observed): `ob sync-list-local` output format is unusual

**Status:** Local-observed behavior, likely a stable upstream contract (not a bug per se, but a footgun).

**Symptom:** `ob sync-list-local` output looks like this:
```
Configured vaults:
  1674fc8b6c8697a98ed64a597a8499ac
    Path: /home/olaf/vaults/akademeia
    Host: sync-51.obsidian.md
```

The vault-id sits on its own line, NOT inside `Vault: <name> (<id>)` as one might guess from CLI conventions. A parser matching `^Vault: +(.+) \(([a-f0-9]+)\)$` matches nothing and silently produces "no vaults".

**Workaround:** parse the four-line block format with two regexes:
- `^[[:space:]]+([a-f0-9]{32})[[:space:]]*$` for the id line (32 hex chars, leading whitespace, optional trailing whitespace)
- `^[[:space:]]+Path:[[:space:]]+(.+)$` for the path line (leading whitespace, "Path:", path)

**Should this be fixed upstream?** Probably not — the format is internally consistent. The real lesson is "use `ob sync-list-local` with the actual format, don't guess".
