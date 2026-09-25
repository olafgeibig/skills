#!/usr/bin/env python3
"""Check whether any local Obsidian vault has pending sync work.

Reads the ob client's SQLite state DB for each locally configured vault
and reports whether there's anything dirty to push or pull. Run this
before a sync to skip the 120s server roundtrip when nothing has changed.

Exit codes:
  0 — all vaults clean, no sync needed
  1 — at least one vault is dirty, sync recommended
  2 — usage error or DB unreadable

Usage:
  check-dirty.py                 # check all configured vaults
  check-dirty.py <vault_path>    # check one vault by path
  check-dirty.py --json          # machine-readable output

`ob sync-list-local` output format (as of obsidian-headless 2025-2026):
    Configured vaults:
      <32-hex-vault-id>          ← 2 leading spaces, 32 hex chars
        Path: <path>              ← 4 leading spaces
        Host: <server-host>       ← 4 leading spaces, ignored
The 32-hex ID is the directory name under
~/.config/obsidian-headless/sync/ and the suffix of state.db.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

OB = "/home/olaf/.npm-global/bin/ob"
SYNC_BASE = Path.home() / ".config" / "obsidian-headless" / "sync"
HEX32 = re.compile(r"^[a-f0-9]{32}$")
PATH_LINE = re.compile(r"^\s+Path:\s+(.+)$")


def list_vaults() -> list[tuple[str, str]]:
    """Return [(vault_id, vault_path), ...] from `ob sync-list-local`.

    Output is a 4-line block per vault:
        <vault-id>     ← 32 hex chars
          Path: <path>
          Host: <host>
    A single leading 2-space indent marks the vault-id line; Path/Host
    lines have 4 leading spaces. Anything else (header line, blank
    line) closes the current block.
    """
    try:
        out = subprocess.run(
            [OB, "sync-list-local"], capture_output=True, text=True, check=True
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"ob sync-list-local failed: {exc}", file=sys.stderr)
        sys.exit(2)

    pairs: list[tuple[str, str]] = []
    pending_id: str | None = None
    for line in out.splitlines():
        stripped = line.lstrip()
        # Vault-id line: 32 hex chars, possibly with leading spaces.
        if pending_id is None and HEX32.match(stripped) and len(line) - len(stripped) >= 2:
            pending_id = stripped
            continue
        if pending_id is not None:
            m = PATH_LINE.match(line)
            if m:
                pairs.append((pending_id, m.group(1).strip()))
                pending_id = None
                continue
            # Anything else (Host:, blank, EOF) closes the current block.
            if stripped:  # non-blank, non-Path line: abort this block
                pending_id = None
    return pairs


def check_vault(vault_id: str, vault_path: str) -> dict:
    """Return dirty state for one vault. Vault-level: is_dirty + reason list."""
    db_path = SYNC_BASE / vault_id / "state.db"
    reasons: list[str] = []
    if not db_path.exists():
        return {
            "vault": vault_path,
            "vault_id": vault_id,
            "is_dirty": True,  # no state at all → first sync needed
            "reasons": ["no state.db — first sync needed"],
            "counts": {"local": 0, "server": 0, "pending": 0},
        }

    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        local = _load(con, "local_files")
        server = _load(con, "server_files")
        pending = _load(con, "pending_files")
    finally:
        con.close()

    local_set, server_set = set(local), set(server)
    common = local_set & server_set

    if local_set - server_set:
        reasons.append(f"{len(local_set - server_set)} local-only files")
    if server_set - local_set:
        reasons.append(f"{len(server_set - local_set)} server-only files")

    locally_edited = 0
    server_diverged = 0
    for p in common:
        if local[p].get("hash") != local[p].get("synchash"):
            locally_edited += 1
        if local[p].get("synchash") != server[p].get("hash"):
            server_diverged += 1

    if locally_edited:
        reasons.append(f"{locally_edited} files locally edited since last sync")
    if server_diverged:
        reasons.append(f"{server_diverged} files server-side diverged")
    if pending:
        reasons.append(f"{len(pending)} files pending")

    return {
        "vault": vault_path,
        "vault_id": vault_id,
        "is_dirty": bool(reasons),
        "reasons": reasons,
        "counts": {
            "local": len(local),
            "server": len(server),
            "pending": len(pending),
            "locally_edited": locally_edited,
            "server_diverged": server_diverged,
        },
    }


def _load(con: sqlite3.Connection, table: str) -> dict[str, dict]:
    cur = con.execute(f"SELECT path, data FROM {table}")
    result: dict[str, dict] = {}
    for path, data in cur.fetchall():
        try:
            result[path] = json.loads(data)
        except json.JSONDecodeError:
            pass
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vault", nargs="?", help="single vault path to check")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    if args.vault:
        # Single-vault mode: scan SYNC_BASE for the matching path in the DB
        for db_path in SYNC_BASE.glob("*/state.db"):
            try:
                con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
                cur = con.execute(
                    "SELECT 1 FROM local_files WHERE json_extract(data, '$.path') = ? LIMIT 1",
                    (args.vault,),
                )
                found = cur.fetchone() is not None
                con.close()
                if found:
                    results = [check_vault(db_path.parent.name, args.vault)]
                    break
            except sqlite3.Error:
                continue
        else:
            print(f"vault not found in any state.db: {args.vault}", file=sys.stderr)
            return 2
    else:
        results = [check_vault(vid, vp) for vid, vp in list_vaults()]

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            status = "DIRTY" if r["is_dirty"] else "CLEAN"
            line = f"[{status}] {r['vault']}"
            if r["is_dirty"]:
                line += " — " + "; ".join(r["reasons"])
            print(line)

    return 1 if any(r["is_dirty"] for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
