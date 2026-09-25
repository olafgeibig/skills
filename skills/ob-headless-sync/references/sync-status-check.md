# Sync Status Check Workflow

Recipe for answering "check the sync" / "ist der Sync in Ordnung" / "läuft das" type questions in 7 lines instead of 30+ lines of full diagnostic dump.

## When to use this workflow

User signals (any of these):
- "check the sync"
- "sync status"
- "läuft der sync"
- "ist alles in Ordnung"
- "läuft das noch"
- "sync health"

## The 7-line snapshot

```bash
# 1. Crontab aktiv?
crontab -l | grep -v '^#' | grep -v '^$'

# 2. Cron service status
systemctl is-active cron

# 3. Letzte 5-8 Zeilen vom Cron-Log
tail -8 /home/olaf/.local/share/ob-sync-cron.log

# 4. Laufende ob-sync Prozesse (sollte nichts sein)
pgrep -af 'ob sync\|ob-sync-all' || echo "no running sync"

# 5. Lock-Dir (sollte leer sein nach sync)
ls /run/user/1000/ob-sync-locks/

# 6. Aktuelle Zeit / nächster 1-Min-Slot
date

# 7. DB dirty-status (4ms Check)
python3 /tmp/check-dirty.py  # or inline: see pitfall-cache below
```

## Status interpretation

**Green (alle 7 Checks OK):**

```
Crontab: ✅ `* * * * * /home/olaf/.local/bin/ob-sync-all-vaults >> ...`
Cron service: ✅ active
Log tail: ✅ "akademeia: ok" und "Fully synced"
Running processes: ✅ none
Lock-Dir: ✅ empty
Time: now
DB dirty: ✅ 32 false-positive rows (known ob-client quirk)
```

→ Antwort: "Sync ist in Ordnung. Letzte [N] Minuten: [count] erfolgreiche Syncs. False-Positive-Dirty-Einträge sind das bekannte ob-Client-Quirk."

**Yellow (Wrapper hat gekillt, aber Cron läuft):**

```
Log tail: ⚠️ "killed stuck ob sync processes: <PIDs>"
```

→ Antwort: "Cron hat einen hängengebliebenen Sync gekillt (Issue #1 Symptom). Server war überlastet. Aktuell wieder grün."

**Red (Cron aus, oder service dead):**

```
Crontab: ⚠️ leer
Cron service: ⚠️ inactive
```

→ Antwort: Diagnose + Recovery-Recipe (siehe `ob-headless-sync/SKILL.md` Pitfall "Timer Dies After Service Kill").

## Pitfall-Cache

Statt `python3 /tmp/check-dirty.py` jedes Mal neu zu schreiben, hier das inline-Snippet das du in jeden Check einfügen kannst:

```python
import sqlite3, json
vault_id = "1674fc8b6c8697a98ed64a597a8499ac"  # academicheia — anpassen für andere vaults
db = f"/home/olaf/.config/obsidian-headless/sync/{vault_id}/state.db"
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=2)
cur = con.cursor()

# 1) Local edits since last sync
cur.execute(
    "SELECT COUNT(*) FROM local_files WHERE "
    "json_extract(data, '$.hash') != COALESCE(json_extract(data, '$.synchash'), '')"
)
local_dirty = cur.fetchone()[0]

# 2) Pending
cur.execute("SELECT COUNT(*) FROM pending_files")
pending = cur.fetchone()[0]

# 3) Server-only drift
cur.execute("SELECT COUNT(*) FROM server_files WHERE COALESCE(json_extract(data, '$.deleted'), 0) = 0")
server_count = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM local_files")
local_count = cur.fetchone()[0]

con.close()

status = (
    "dirty" if (local_dirty > 0 or pending > 0 or server_count > local_count + 50)
    else "clean"
)
print(f"local_dirty={local_dirty} pending={pending} server={server_count} local={local_count} → {status}")
```

**Wenn `local_dirty > 0` aber `pending == 0` und Server-Count stabil:** Das ist das **bekannte False-Positive** — ob-Client aktualisiert DB-Rows nicht für Files die Server-seitig bereits den korrekten Hash haben. Sync läuft trotzdem sauber durch, nächster Tick zeigt dasselbe. **Kein Handlungsbedarf.**

Wenn `local_dirty` UND `pending > 0`: Echte Sync-Arbeit ausstehend, Cron @ 1 min wird es beim nächsten Tick erledigen.

## Detection Heuristic

Bei User-Anfrage „check X":

1. **Wenn X = ein runnable Service:** 7-Snapshot-Recipe für `ob-headless-sync`, ähnliche Recipes für andere Services.
2. **Wenn X = ein skill-load:** `skill_view` Output (3-5 Zeilen).
3. **Wenn X = ein vault-state:** Read-Only MCP-Call + 3 Zeilen Summary.

**Anti-Pattern:** Direkt mit Voll-Diagnose antworten ohne Snapshot. User-Aufwand 30+ Sek für Status-Lesen ist nicht akzeptabel.

## Pitfall-Quelle

Pitfall 27 (`ob-headless-sync`): Sync-Status-Check Workflow — siehe `vault-improvements/references/new-pitfalls-2026-07-16-batch.md` §2.

## Worked example (Session 2026-07-15 + 2026-07-16)

User bat zweimal „check the sync" / „ist der in Ordnung?". Beide Male lieferte der Agent eine 30+-Zeilen-Diagnose mit Crontab, Log-Tail, allen Server-Files-Listen, file-mtimes, etc. Lesson: User wollte nur eine Ampel, kein Daten-Briefing.

Korrekte Antwort wäre gewesen:

> "Sync läuft. Cron @ 1 min aktiv, letzte Sync vor 3 min, Fully synced, keine laufenden Prozesse, Lock-Dir leer. 32 false-positive Dirty-Einträge in der DB (ob-Client-Quirk, harmless)."

→ 4 Zeilen statt 30+. User kann sofort „OK, danke" antworten.

## Verwandte Patterns

- **Honcho-Doctor-Check:** Ähnlicher Snapshot-Style für `hermes doctor` — siehe `vault-improvements` Pitfall 25 für den Background.
- **Systemd-Timer-Status:** `systemctl --user status X.timer --no-pager | head -10` ist bereits ein eingebauter Snapshot-Style.