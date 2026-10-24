#!/usr/bin/env python3
"""Detect vault changes that TurboVault's audit log does not cover.

TurboVault records an audit entry for every write that goes through its own
write path. Edits made by Obsidian, a sync client, another agent instance or a
shell never appear there. This script keeps a hash manifest of the vault
(outside the vault) and, on each run, classifies what changed since the last
run against the audit log:

  audited     the new content hash equals an audit entry's after_hash recorded
              in the same window, so TurboVault made this change
  external    no such entry — the change came from somewhere else

It reports only the window (changes since the previous run), so a note that
already diverged months ago does not alert on every run. `--full` additionally
prints the whole audit-vs-disk picture, which is where historical drift shows
up.

With --store (default in the all-vaults wrapper), every new content hash is also
copied to <state>/objects/<sha256>, giving a version history for edits
TurboVault never saw.

Exit codes: 0 clean, 2 external changes found, 1 error. With --quiet nothing is
printed unless there is something to report, and drift still exits 0
(watchdog mode).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

NOTE_SUFFIXES = {".md", ".canvas", ".base"}
SKIP_DIRS = {
    ".obsidian", ".git", ".turbovault", ".trash", ".smart-env", ".enzyme",
    "node_modules", ".DS_Store",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def scan_vault(vault: Path) -> tuple[dict[str, dict], list[str]]:
    out: dict[str, dict] = {}
    unreadable: list[str] = []
    for root, dirs, files in os.walk(vault):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            p = Path(root) / name
            if p.suffix.lower() not in NOTE_SUFFIXES:
                continue
            try:
                st = p.stat()
                digest = sha256_file(p)
            except OSError:
                # OneDrive placeholders can refuse a read with EDEADLK, and a
                # sync client can remove a file mid-walk.
                unreadable.append(p.relative_to(vault).as_posix())
                continue
            out[p.relative_to(vault).as_posix()] = {
                "hash": digest,
                "mtime": int(st.st_mtime),
                "size": st.st_size,
            }
    return out, unreadable


def _epoch(ts: str) -> float | None:
    try:
        return datetime.fromisoformat(ts).timestamp()
    except (TypeError, ValueError):
        return None


def read_audit(vault: Path) -> dict[str, dict]:
    """Aggregate the audit log per path: entry count, write hashes, delete times."""
    log = vault / ".turbovault" / "audit" / "operations.jsonl"
    info: dict[str, dict] = {"__meta__": {"entries": 0, "newest": None}, "paths": {}}
    if not log.exists():
        return info
    paths: dict[str, dict] = info["paths"]
    with log.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            info["__meta__"]["entries"] += 1
            ts = entry.get("timestamp")
            if ts and (info["__meta__"]["newest"] is None or ts > info["__meta__"]["newest"]):
                info["__meta__"]["newest"] = ts
            path = entry.get("path")
            if not path:
                continue
            rec = paths.setdefault(path, {
                "last": None, "write_hashes": {}, "delete_ts": [],
            })
            rec["last"] = entry
            op = entry.get("operation")
            stamp = _epoch(ts)
            if op in ("CREATE", "UPDATE", "ROLLBACK") and entry.get("after_hash"):
                prev_ts = rec["write_hashes"].get(entry["after_hash"], 0.0)
                rec["write_hashes"][entry["after_hash"]] = max(prev_ts, stamp or 0.0)
            if op == "DELETE":
                rec["delete_ts"].append(stamp or 0.0)
    return info


def load_manifest(path: Path) -> dict:
    if not path.exists():
        return {"generated": None, "generated_epoch": None, "files": {}, "unreadable": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"generated": None, "generated_epoch": None, "files": {}, "unreadable": []}
    data.setdefault("files", {})
    data.setdefault("unreadable", [])
    data.setdefault("generated_epoch", None)
    return data


def write_manifest(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def store_object(objects: Path, vault: Path, rel: str, digest: str) -> bool:
    dest = objects / digest
    if dest.exists():
        return False
    objects.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(vault / rel, dest)
    except OSError:
        return False
    return True


def default_state_root() -> Path:
    """Where drift state lives, without assuming a Hermes profile."""
    env = os.environ.get("TURBOVAULT_DRIFT_STATE")
    if env:
        return Path(env).expanduser()
    hermes_home = os.environ.get("HERMES_HOME")
    if hermes_home:
        return Path(hermes_home) / "state" / "vault-drift"
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg:
        return Path(xdg) / "turbovault-drift"
    return Path.home() / ".local" / "state" / "turbovault-drift"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault", required=True, help="vault root")
    ap.add_argument("--state", help="exact state dir for this vault")
    ap.add_argument("--state-root",
                    help="parent dir for per-vault state (default: $TURBOVAULT_DRIFT_STATE,"
                         " $HERMES_HOME/state/vault-drift, $XDG_STATE_HOME/turbovault-drift)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--quiet", action="store_true",
                    help="print only when there is something to report; drift exits 0")
    ap.add_argument("--store", action="store_true", help="copy changed content into the object store")
    ap.add_argument("--full", action="store_true",
                    help="also print the whole audit-vs-disk picture (historical drift)")
    ap.add_argument("--name", help="display name for reports (default: the directory name)")
    ap.add_argument("--limit", type=int, default=20, help="paths printed per category")
    args = ap.parse_args()

    vault = Path(args.vault).expanduser().resolve()
    if not vault.is_dir():
        print(f"not a directory: {vault}", file=sys.stderr)
        return 1

    # Two vaults can share a directory name (…/dft-csl/csl and …/drivalia-csl/csl),
    # so the default state dir is keyed by the resolved path, not the basename.
    path_key = hashlib.sha256(str(vault).encode()).hexdigest()[:8]
    if args.state:
        state = Path(args.state).expanduser()
    else:
        root = Path(args.state_root).expanduser() if args.state_root else default_state_root()
        state = root / f"{vault.name}-{path_key}"
    state.mkdir(parents=True, exist_ok=True)
    manifest_path = state / "manifest.json"
    previous = load_manifest(manifest_path)
    prev_files: dict[str, dict] = previous["files"]
    prev_unreadable = set(previous["unreadable"])
    window_start = previous.get("generated_epoch")
    objects = state / "objects"

    disk, unreadable = scan_vault(vault)
    audit = read_audit(vault)
    audited_paths: dict[str, dict] = audit["paths"]

    def audited_write(rel: str, digest: str) -> bool:
        rec = audited_paths.get(rel)
        if not rec or digest not in rec["write_hashes"]:
            return False
        if window_start is None:
            return True
        return rec["write_hashes"][digest] >= window_start - 1

    def audited_delete(rel: str) -> bool:
        rec = audited_paths.get(rel)
        if not rec or not rec["delete_ts"]:
            return False
        if window_start is None:
            return True
        return max(rec["delete_ts"]) >= window_start - 1

    # ---- window: what changed since the previous run -----------------------
    external: list[str] = []
    audited: list[str] = []
    external_delete: list[str] = []
    audited_delete: list[str] = []
    stored = 0
    baseline = window_start is None

    if not baseline:
        for rel, info in disk.items():
            prev = prev_files.get(rel)
            if prev is not None and prev.get("hash") == info["hash"]:
                continue
            (audited if audited_write(rel, info["hash"]) else external).append(rel)
            if args.store and store_object(objects, vault, rel, info["hash"]):
                stored += 1
        for rel in prev_files:
            if rel in disk:
                continue
            (audited_delete if audited_delete(rel) else external_delete).append(rel)

    # ---- historical picture (only with --full, or on the baseline run) -----
    never_audited = [rel for rel in disk if rel not in audited_paths]
    diverging: list[str] = []
    for rel, info in disk.items():
        rec = audited_paths.get(rel)
        if rec is None or rec["last"] is None:
            continue
        if rec["last"].get("after_hash") == info["hash"]:
            continue
        diverging.append(rel)
    missing_despite_audit: list[str] = []
    for rel, rec in audited_paths.items():
        if rel in disk or rec["last"] is None:
            continue
        if rec["last"].get("operation") != "DELETE":
            missing_despite_audit.append(rel)

    new_unreadable = sorted(set(unreadable) - prev_unreadable)

    report = {
        "vault": str(vault),
        "name": args.name or vault.name,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime()),
        "window_start": previous.get("generated"),
        "baseline": baseline,
        "files": len(disk),
        "audit_entries": audit["__meta__"]["entries"],
        "audit_newest": audit["__meta__"]["newest"],
        "window": {
            "external": sorted(external),
            "external_delete": sorted(external_delete),
            "audited": sorted(audited),
            "audited_delete": sorted(audited_delete),
        },
        "historical": {
            "never_audited": len(never_audited),
            "diverging": sorted(diverging),
            "missing_despite_audit": sorted(missing_despite_audit),
        },
        "unreadable": sorted(unreadable),
        "new_unreadable": new_unreadable,
        "objects_stored": stored,
        "state_dir": str(state),
    }
    dirty = bool(external or external_delete)

    now = time.time()
    write_manifest(manifest_path, {
        "generated": report["checked_at"],
        "generated_epoch": now,
        "vault": str(vault),
        "unreadable": sorted(unreadable),
        "files": {rel: {"hash": i["hash"], "mtime": i["mtime"], "size": i["size"]}
                  for rel, i in disk.items()},
    })

    window_label = previous.get("generated") or "first run"
    changed_total = len(external) + len(audited) + len(external_delete) + len(audited_delete)

    if args.json:
        print(json.dumps(report, indent=1))
        return 2 if dirty else 0

    if args.quiet:
        if not dirty and not new_unreadable:
            return 0
        if dirty:
            print(f"## {report['name']} — {len(external) + len(external_delete)} change(s) outside the audit log")
            print(f"since {window_label} · {len(audited) + len(audited_delete)} audited change(s) in the same window")
            for rel in report["window"]["external"][: args.limit]:
                print(f"  ~ {rel}")
            for rel in report["window"]["external_delete"][: args.limit]:
                print(f"  - {rel} (deleted, no audit delete)")
            rest = len(external) + len(external_delete) - args.limit
            if rest > 0:
                print(f"  … {rest} more")
            print(f"prior versions: {state}/objects")
        if new_unreadable:
            print(f"## {report['name']} — {len(new_unreadable)} newly unreadable file(s), skipped")
            for rel in new_unreadable[: args.limit]:
                print(f"  ! {rel}")
        print()
        return 0

    print(f"vault:    {vault}")
    print(f"files:    {len(disk)}   audit entries: {audit['__meta__']['entries']}   "
          f"audit newest: {audit['__meta__']['newest']}")
    print(f"window:   {window_label} -> {report['checked_at']}")
    print()
    if baseline:
        print("BASELINE RUN — no previous manifest, so nothing is compared against it yet.")
        print(f"  notes whose disk state differs from what TurboVault last wrote: {len(diverging)}")
        print(f"  notes TurboVault has never written: {len(never_audited)}")
        if args.store:
            print("  (no objects stored on the baseline run)")
        if unreadable:
            print(f"  unreadable, skipped: {len(unreadable)}")
        print()
        print("RESULT: baseline written — the next run reports changes only")
        return 0

    print(f"changed since last run: {changed_total} "
          f"({len(audited)} audited, {len(audited_delete)} audited deletes, "
          f"{len(external)} external, {len(external_delete)} external deletes)")
    for label, items in (("~ external", report["window"]["external"]),
                         ("- external delete", report["window"]["external_delete"]),
                         ("✓ audited", report["window"]["audited"]),
                         ("✓ audited delete", report["window"]["audited_delete"])):
        for rel in items[: args.limit]:
            print(f"  {label:<18} {rel}")
        if len(items) > args.limit:
            print(f"  {label:<18} … {len(items) - args.limit} more")
    if args.store:
        print(f"objects stored this run: {stored}")
    if unreadable:
        print(f"unreadable, skipped: {len(unreadable)}")
    print()

    if args.full:
        print("HISTORICAL DRIFT (audit vs disk right now)")
        print(f"  differs from TurboVault's last write: {len(diverging)}")
        for rel in report["historical"]["diverging"][: args.limit]:
            print(f"    ~ {rel}")
        print(f"  audited as present but missing on disk: {len(missing_despite_audit)}")
        for rel in report["historical"]["missing_despite_audit"][: args.limit]:
            print(f"    - {rel}")
        print(f"  never written through TurboVault: {len(never_audited)} of {len(disk)}")
        print()

    print("RESULT:", "ATTENTION — changes outside the audit log" if dirty else "in sync")
    return 2 if dirty else 0


if __name__ == "__main__":
    sys.exit(main())
