# Sync Management

Vault sync runs via `ob sync` wrapped in a systemd timer/service (`ob-sync-all`). The AGENTS.md directive is: sync is automatic, never sync manually.

## Diagnostics

```bash
# Service + timer status
systemctl status --user ob-sync-all.service
systemctl status --user ob-sync-all.timer

# Recent sync logs
journalctl --user -u ob-sync-all.service --since "1 hour ago" --no-pager

# Last sync result
journalctl --user -u ob-sync-all.service --since "24 hours ago" --no-pager | grep -E "Fully synced|Connection successful|ERROR"
```

## When Sync Is Stuck

Symptom: `Active: active (running)` for hours at "Connecting..." — the timer fires every 3min (`OnUnitActiveSec=3min`) but cannot start a new instance while the service is still "running".

```bash
# 1. Hard-kill the stuck ob sync process
kill -9 $(pgrep -f 'ob sync')

# 2. Reset systemd state
systemctl --user reset-failed ob-sync-all.service
systemctl --user stop ob-sync-all.service

# 3. Start fresh
systemctl --user start ob-sync-all.service

# 4. Verify — should reach "Fully synced" within seconds
journalctl --user -u ob-sync-all.service --since "30 seconds ago" --no-pager | tail -10
```

## Prevention

The wrapper script at `~/.local/bin/ob-sync-all-vaults` wraps the `ob sync` call with `timeout 120` so a hung connection kills itself after 2 minutes. If the timeout fires, `Restart=on-failure` in the service file triggers a clean retry after 10s.

Check that the timeout is in place:
```bash
grep timeout ~/.local/bin/ob-sync-all-vaults
# Should show: timeout 120 $OB sync --path "$vault_path"
```

## Architecture

- **Timer:** `~/.config/systemd/user/ob-sync-all.timer` — fires every 3 minutes
- **Service:** `~/.config/systemd/user/ob-sync-all.service` — `Type=simple`, `Restart=on-failure`
- **Script:** `~/.local/bin/ob-sync-all-vaults` — discovers vaults from `ob sync-list-local`, runs `ob sync --path` per vault with lockfile dedup
- **Lockfiles:** `/tmp/ob-sync-locks/<vault_name>.lock`
