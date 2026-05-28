---
name: ob-headless-sync
description: Obsidian Headless Sync — systemd timer monitoring, diagnostics, and recovery for the ob sync service on headless machines
metadata:
  version: "0.1.0"
  source: durin-2026-04-18
---

# Obsidian Headless Sync — Timer & Service Management
The Obsidian Headless Sync is running in a fixed interval every three minutes, controlled by a system service. The agent MUST not do the sync manually. This is important to avoid conflicts. 

## Quick Diagnostic

```bash
# 1. Is ob reachable?
which ob || echo "ob not in PATH — use: ~/.npm-global/bin/ob"

# 2. Timer status
systemctl --user list-timers --all --no-pager | grep ob-sync

# 3. Recent service logs
journalctl --user -u ob-sync-all.service -n 20 --no-pager
```

## The `ob` Binary

- **Full path:** `/home/olaf/.npm-global/bin/ob`
- **PATH may not include it** in subshell/agent contexts — always use the full path in scripts
- **Manual sync test:**
  ```bash
  ~/.npm-global/bin/ob sync --path /home/olaf/vaults/akademeia
  ```

## Known Issue: Timer Dies After Service Kill/Timeout

**Symptom:** Timer shows `inactive (dead)` even though it is `enabled` and has `Persistent=true`.

**Trigger:** If the service (`ob-sync-all.service`) is killed with SIGKILL after a timeout (e.g. from `systemctl stop`), the User Manager daemon can lose track of the timer's next-execution state. `systemctl status` shows `Trigger: n/a` and the `NEXT` column shows an old/distant timestamp or `-`.

**Fix — run all three commands:**
```bash
systemctl --user daemon-reload
systemctl --user reset-failed
systemctl --user start ob-sync-all.timer
```

Then verify:
```bash
systemctl --user list-timers --all --no-pager | grep ob-sync
# Should show: Active: active (running) and a near-future NEXT time
```

**Do NOT just `systemctl --user restart ob-sync-all.timer`** — the daemon-reload and reset-failed are required to clear the stale state.

## Files

| File | Purpose |
|------|---------|
| `~.local/bin/ob-sync-all-vaults` | Wrapper script — discovers vaults via `ob sync-list-local` and syncs each |
| `~/.config/systemd/user/ob-sync-all.timer` | Fires every 3min (`OnUnitActiveSec=3min`), `Persistent=true` |
| `~/.config/systemd/user/ob-sync-all.service` | Runs the wrapper script; `Restart=on-failure` |

## Service / Timer Commands

```bash
# Full restart (daemon-reload included)
systemctl --user daemon-reload && systemctl --user reset-failed
systemctl --user start ob-sync-all.timer

# Check status
systemctl --user status ob-sync-all.timer --no-pager
systemctl --user status ob-sync-all.service --no-pager

# Stop completely
systemctl --user stop ob-sync-all.timer ob-sync-all.service

# View logs
journalctl --user -u ob-sync-all.service -n 50 --no-pager
```

## Timer vs Service — Key Distinction

- `ob-sync-all.timer` — the **scheduler** (fires every 3 min)
- `ob-sync-all.service` — the **worker** (runs `ob sync`)
- A timer in `inactive (dead)` state means **no syncs are being triggered**
- A service that fails/times-out does NOT automatically restart the timer
