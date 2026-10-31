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

## External Writes Via Sync

Other Obsidian clients edit the same tree; sync delivers their renames and link rewrites to the local vault within minutes. Treat the vault as concurrently written for the whole session.

- **Re-resolve a note's path before patching it.** A SEARCH/REPLACE or patch failure on a note written earlier in the same session usually means the file was renamed on disk, not that the patch text is wrong — `ls` the directory, retry on the current name. Never rewrite the whole note to force the write; that clobbers the external edits.
- **After a noticed rename, repair links by exact string replacement** across the referencing notes (`grep -rn "<old name>" <vault>`), then verify every affected note with `get_links`. The external renamer rewrites links in files it knows — notes created mid-session can be left pointing at dead names.
- **Only rename yourself when every link moves with you** and `get_links` verifies afterwards; an inconsistent name with live links beats a clean name with broken ones.

### Attribution: who changed a vault file

When files change in a way nobody asked for, establish the source before touching anything — the user expects an evidenced attribution chain (source, mechanism, evidence), not a plausible story:

1. `mcp__turbovault__audit_log` — TurboVault writes appear with path, timestamp, tool, session. No entry for the file/time proves the change did NOT come through TurboVault.
2. `journalctl --user --since "<t1>" --until "<t2>" | grep -iE "sync"` (or the unit-scoped form above) — a sync tick at the change's minute means an external client wrote it and sync delivered it.
3. `find <vault> -newermt "<timestamp>" -type f` (exclude `.obsidian/`, `.git/`) — the blast radius. Several files with the same second are one external batch: a rename sweep plus its link rewrites.

Report the chain and the changed files; do not roll anything back without asking.
