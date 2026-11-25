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

Security & integrity guarantees:
- Symlinks (directories or files) and non-regular files (FIFOs, devices) are
  never followed, hashed, or copied; files are opened with O_NOFOLLOW and
  verified via fstat(S_ISREG) on the opened file descriptor.
- Respects `--exclude` (repeatable) with the same path-component / prefix
  matching as TurboVault's `excluded_paths`.
- With `--store` (opt-in, off by default), post-baseline changed bytes are
  stream-hashed while written to a temp file and atomically renamed to
  `<state>/objects/<sha256>`. If snapshotting fails, the script exits 1,
  reports the error to stderr, and holds the manifest entry back so the next
  run retries once the object store is writable again.
- Temporarily unreadable files keep their prior manifest state instead of
  being misclassified as externally deleted and later re-created.

Exit codes: 0 clean, 2 external changes found, 1 error (including snapshot
store failures). With `--quiet` nothing is printed unless there is something
to report, drift exits 0, and errors still exit 1.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import tempfile
import time
import unicodedata
from datetime import datetime
from pathlib import Path

NOTE_SUFFIXES = {".md", ".canvas", ".base"}
SKIP_DIRS = {
    ".obsidian",
    ".git",
    ".turbovault",
    ".trash",
    ".smart-env",
    ".enzyme",
    "node_modules",
    ".DS_Store",
}


class _NonRegularOrSymlink(Exception):
    """Raised when a path or any intermediate component is a symlink or non-regular file."""


def _open_regular_nofollow(vault: Path, rel_parts: tuple[str, ...]) -> tuple[int, os.stat_result]:
    """Open `vault / rel_parts` component-by-component via dir_fd + O_NOFOLLOW.

    Each intermediate directory is opened relative to its already-opened parent
    descriptor with O_DIRECTORY | O_NOFOLLOW, and the leaf with O_NOFOLLOW,
    eliminating parent-directory symlink swap TOCTOU windows. Returns
    `(fd, fstat_result)`. Raises `_NonRegularOrSymlink` if any component is a
    symlink or non-regular target; raises `OSError` for permission/IO failures.
    """
    if not rel_parts or any(p in ("", ".", "..") or "/" in p for p in rel_parts):
        raise _NonRegularOrSymlink(f"invalid relative path parts: {rel_parts!r}")

    o_nofollow = getattr(os, "O_NOFOLLOW", 0)
    o_directory = getattr(os, "O_DIRECTORY", 0)
    o_cloexec = getattr(os, "O_CLOEXEC", 0)
    eloop_errnos = {getattr(os, "ELOOP", -1), 40, 62}
    dir_reject_errnos = eloop_errnos | {getattr(os, "ENOTDIR", -1), 20}

    cur_fd = os.open(vault, os.O_RDONLY | o_directory | o_cloexec)
    try:
        for part in rel_parts[:-1]:
            try:
                next_fd = os.open(
                    part, os.O_RDONLY | o_directory | o_nofollow | o_cloexec, dir_fd=cur_fd
                )
            except OSError as exc:
                if exc.errno in dir_reject_errnos:
                    raise _NonRegularOrSymlink(
                        f"symlink or non-directory component: {part}"
                    ) from exc
                raise
            os.close(cur_fd)
            cur_fd = next_fd

        leaf = rel_parts[-1]
        try:
            fd = os.open(leaf, os.O_RDONLY | o_nofollow | o_cloexec, dir_fd=cur_fd)
        except OSError as exc:
            if exc.errno in eloop_errnos:
                raise _NonRegularOrSymlink(f"symlink leaf: {leaf}") from exc
            raise
    finally:
        os.close(cur_fd)

    try:
        fst = os.fstat(fd)
        if not stat.S_ISREG(fst.st_mode):
            os.close(fd)
            raise _NonRegularOrSymlink(f"opened descriptor is not a regular file: {rel_parts}")
        return fd, fst
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        raise


def _sha256_fd(fd: int) -> str:
    h = hashlib.sha256()
    with os.fdopen(fd, "rb", closefd=True) as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _fold_component(name: str) -> str:
    """Fold a path component at least as strictly as TurboVault's protected_component.

    Normalizes Unicode to NFC, strips trailing dots/spaces (Windows), and case-folds
    so `excluded_paths: [private]` matches `Private`, `PRIVATE`, `private.`, and NFD/NFC forms.
    """
    return unicodedata.normalize("NFC", name).rstrip(". ").casefold()


def _is_excluded(
    rel_parts: tuple[str, ...],
    skip_components: set[str],
    skip_prefixes: set[str],
) -> bool:
    folded_parts = tuple(_fold_component(part) for part in rel_parts)
    if any(part in skip_components for part in folded_parts):
        return True
    if skip_prefixes:
        rel_posix = "/".join(folded_parts)
        for pref in skip_prefixes:
            if rel_posix == pref or rel_posix.startswith(pref + "/"):
                return True
    return False


def _prepare_excludes(excludes: list[str] | None) -> tuple[set[str], set[str]]:
    skip_components = {_fold_component(d) for d in SKIP_DIRS}
    skip_prefixes: set[str] = set()
    for raw in excludes or []:
        norm = raw.strip().strip("/")
        if not norm:
            continue
        if "/" in norm:
            folded_pref = "/".join(
                _fold_component(p) for p in norm.split("/") if p
            )
            if folded_pref:
                skip_prefixes.add(folded_pref)
        else:
            folded = _fold_component(norm)
            if folded:
                skip_components.add(folded)
    return skip_components, skip_prefixes


def _under_unreadable_dir(rel: str, unreadable_dirs: set[str]) -> bool:
    if "" in unreadable_dirs:
        return True
    return any(rel == d or rel.startswith(d + "/") for d in unreadable_dirs)


def scan_vault(
    vault: Path,
    excludes: list[str] | None = None,
) -> tuple[dict[str, dict], list[str], set[str]]:
    skip_components, skip_prefixes = _prepare_excludes(excludes)
    out: dict[str, dict] = {}
    unreadable: list[str] = []
    unreadable_dirs: set[str] = set()

    def _on_walk_error(exc: OSError) -> None:
        fname = exc.filename
        if not fname:
            return
        try:
            p = Path(fname)
            rel_path = p.relative_to(vault)
        except ValueError:
            return
        rel_parts = () if rel_path == Path(".") else rel_path.parts
        if rel_parts and _is_excluded(rel_parts, skip_components, skip_prefixes):
            return
        if os.path.lexists(p):
            rel_dir = "" if not rel_parts else "/".join(rel_parts)
            unreadable_dirs.add(rel_dir)
            unreadable.append(f"{rel_dir}/" if rel_dir else "./")

    for root, dirs, files in os.walk(vault, followlinks=False, onerror=_on_walk_error):
        rel_root = Path(root).relative_to(vault)
        base_parts = () if rel_root == Path(".") else rel_root.parts
        kept_dirs: list[str] = []
        for d in dirs:
            d_path = Path(root) / d
            if d_path.is_symlink():
                continue
            if _is_excluded(base_parts + (d,), skip_components, skip_prefixes):
                continue
            kept_dirs.append(d)
        dirs[:] = kept_dirs

        for name in files:
            p = Path(root) / name
            if p.suffix.lower() not in NOTE_SUFFIXES:
                continue
            rel_parts = base_parts + (name,)
            if _is_excluded(rel_parts, skip_components, skip_prefixes):
                continue
            rel = "/".join(rel_parts)
            try:
                fd, fst = _open_regular_nofollow(vault, rel_parts)
                digest = _sha256_fd(fd)
            except _NonRegularOrSymlink:
                # Never follow symlinks or non-regular files (matches TurboVault confinement)
                continue
            except FileNotFoundError:
                # Vanished mid-walk: truly absent, not unreadable
                continue
            except OSError:
                # Permission denied or OneDrive placeholder (EDEADLK/EBUSY): present but unreadable
                if os.path.lexists(p):
                    unreadable.append(rel)
                continue
            out[rel] = {
                "hash": digest,
                "mtime": int(fst.st_mtime),
                "size": fst.st_size,
            }
    return out, unreadable, unreadable_dirs


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
            if ts and (
                info["__meta__"]["newest"] is None or ts > info["__meta__"]["newest"]
            ):
                info["__meta__"]["newest"] = ts
            path = entry.get("path")
            if not path:
                continue
            rec = paths.setdefault(
                path,
                {"last": None, "write_hashes": {}, "delete_ts": []},
            )
            rec["last"] = entry
            op = entry.get("operation")
            stamp = _epoch(ts)
            if op in ("CREATE", "UPDATE", "ROLLBACK") and entry.get("after_hash"):
                prev_ts = rec["write_hashes"].get(entry["after_hash"], 0.0)
                rec["write_hashes"][entry["after_hash"]] = max(prev_ts, stamp or 0.0)
            elif op == "DELETE":
                rec["delete_ts"].append(stamp or 0.0)
            elif op == "MOVE":
                rec["delete_ts"].append(stamp or 0.0)
                dest = entry.get("new_path")
                dest_hash = entry.get("after_hash") or entry.get("before_hash")
                if dest:
                    dest_rec = paths.setdefault(
                        dest,
                        {"last": None, "write_hashes": {}, "delete_ts": []},
                    )
                    dest_rec["last"] = {
                        "operation": "CREATE",
                        "path": dest,
                        "after_hash": dest_hash,
                        "timestamp": ts,
                    }
                    if dest_hash:
                        prev_ts = dest_rec["write_hashes"].get(dest_hash, 0.0)
                        dest_rec["write_hashes"][dest_hash] = max(
                            prev_ts, stamp or 0.0
                        )
    return info


def load_manifest(path: Path) -> dict:
    if not path.exists():
        return {
            "generated": None,
            "generated_epoch": None,
            "files": {},
            "unreadable": [],
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {
            "generated": None,
            "generated_epoch": None,
            "files": {},
            "unreadable": [],
        }
    data.setdefault("files", {})
    data.setdefault("unreadable", [])
    data.setdefault("generated_epoch", None)
    return data


def write_manifest(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def store_object(objects: Path, vault: Path, rel: str) -> tuple[str, str]:
    """Open `vault / rel` without following symlinks, stream-hash to temp file, atomically rename.

    Returns:
      ("stored", actual_sha256)  - new object written
      ("exists", actual_sha256)  - identical content-addressed object already present
      ("skipped", reason)        - target became symlink/non-regular file
      ("error", error_message)   - IO/permission failure writing the snapshot
    """
    rel_parts = tuple(Path(rel).parts)
    try:
        fd, _ = _open_regular_nofollow(vault, rel_parts)
    except _NonRegularOrSymlink as exc:
        return "skipped", str(exc)
    except OSError as exc:
        return "error", f"cannot open source {rel}: {exc}"

    tmp_path: Path | None = None
    try:
        objects.mkdir(parents=True, exist_ok=True)
        h = hashlib.sha256()
        with os.fdopen(fd, "rb", closefd=True) as rfh, tempfile.NamedTemporaryFile(
            dir=objects, prefix=".obj-", suffix=".tmp", delete=False
        ) as wfh:
            fd = -1  # owned by rfh now
            tmp_path = Path(wfh.name)
            for chunk in iter(lambda: rfh.read(1 << 20), b""):
                h.update(chunk)
                wfh.write(chunk)
            wfh.flush()
            os.fsync(wfh.fileno())
        actual_digest = h.hexdigest()
        dest = objects / actual_digest
        if dest.exists():
            tmp_path.unlink(missing_ok=True)
            return "exists", actual_digest
        os.replace(tmp_path, dest)
        tmp_path = None
        return "stored", actual_digest
    except OSError as exc:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        return "error", f"cannot write snapshot for {rel}: {exc}"


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
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--vault", required=True, help="vault root")
    ap.add_argument("--state", help="exact state dir for this vault")
    ap.add_argument(
        "--state-root",
        help="parent dir for per-vault state (default: $TURBOVAULT_DRIFT_STATE,"
        " $HERMES_HOME/state/vault-drift, $XDG_STATE_HOME/turbovault-drift)",
    )
    ap.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="directory/component or relative path prefix to skip (repeatable; matches TurboVault excluded_paths)",
    )
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument(
        "--quiet",
        action="store_true",
        help="print only when there is something to report; drift exits 0, errors exit 1",
    )
    ap.add_argument(
        "--store",
        action="store_true",
        help="copy post-baseline changed content into the content-addressed object store (opt-in)",
    )
    ap.add_argument(
        "--full",
        action="store_true",
        help="also print the whole audit-vs-disk picture (historical drift)",
    )
    ap.add_argument(
        "--name", help="display name for reports (default: the directory name)"
    )
    ap.add_argument(
        "--limit", type=int, default=20, help="paths printed per category"
    )
    args = ap.parse_args()

    vault = Path(args.vault).expanduser().resolve()
    if not vault.is_dir():
        print(f"not a directory: {vault}", file=sys.stderr)
        return 1

    # Two vaults can share a directory name (e.g. …/project-a/vault and …/project-b/vault),
    # so the default state dir is keyed by the resolved path, not the basename.
    path_key = hashlib.sha256(str(vault).encode()).hexdigest()[:8]
    if args.state:
        state = Path(args.state).expanduser()
    else:
        root = (
            Path(args.state_root).expanduser()
            if args.state_root
            else default_state_root()
        )
        state = root / f"{vault.name}-{path_key}"
    state.mkdir(parents=True, exist_ok=True)
    manifest_path = state / "manifest.json"
    previous = load_manifest(manifest_path)
    prev_files: dict[str, dict] = previous["files"]
    prev_unreadable = set(previous["unreadable"])
    window_start = previous.get("generated_epoch")
    objects = state / "objects"

    disk, unreadable, unreadable_dirs = scan_vault(vault, excludes=args.exclude)
    unreadable_set = set(unreadable)
    audit = read_audit(vault)
    audited_paths: dict[str, dict] = audit["paths"]

    def audited_write(rel: str, digest: str) -> bool:
        rec = audited_paths.get(rel)
        if not rec or digest not in rec["write_hashes"]:
            return False
        if window_start is None:
            return True
        return rec["write_hashes"][digest] >= window_start - 1

    def is_audited_delete(rel: str) -> bool:
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
    store_errors: list[dict[str, str]] = []
    retry_paths: set[str] = set()
    stored = 0
    baseline = window_start is None

    if not baseline:
        for rel, info in list(disk.items()):
            prev = prev_files.get(rel)
            if prev is not None and prev.get("hash") == info["hash"]:
                continue
            digest = info["hash"]
            if args.store:
                status, detail = store_object(objects, vault, rel)
                if status == "stored":
                    digest = detail
                    info["hash"] = detail
                    stored += 1
                elif status == "exists":
                    digest = detail
                    info["hash"] = detail
                elif status == "skipped":
                    # File turned into symlink/non-regular mid-run: exclude it
                    disk.pop(rel, None)
                    continue
                else:
                    store_errors.append({"path": rel, "error": detail})
                    retry_paths.add(rel)
            (audited if audited_write(rel, digest) else external).append(rel)

        for rel in prev_files:
            if rel in disk or rel in unreadable_set or _under_unreadable_dir(rel, unreadable_dirs):
                continue
            (audited_delete if is_audited_delete(rel) else external_delete).append(rel)

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
    skip_components, skip_prefixes = _prepare_excludes(args.exclude)
    for rel, rec in audited_paths.items():
        if (
            rel in disk
            or rel in unreadable_set
            or _under_unreadable_dir(rel, unreadable_dirs)
            or rec["last"] is None
        ):
            continue
        if _is_excluded(Path(rel).parts, skip_components, skip_prefixes):
            continue
        if rec["last"].get("operation") not in ("DELETE", "MOVE"):
            missing_despite_audit.append(rel)

    new_unreadable = sorted(unreadable_set - prev_unreadable)

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
        "store_errors": store_errors,
        "state_dir": str(state),
    }
    dirty = bool(external or external_delete)

    # Build next manifest:
    # - Keep prior state for temporarily unreadable files (no false delete/create)
    # - Hold back entries whose --store snapshot failed so the next run retries them
    next_files: dict[str, dict] = {}
    for rel, info in disk.items():
        if rel in retry_paths:
            if rel in prev_files:
                next_files[rel] = prev_files[rel]
            continue
        next_files[rel] = {
            "hash": info["hash"],
            "mtime": info["mtime"],
            "size": info["size"],
        }
    for rel, prev_info in prev_files.items():
        if rel in next_files:
            continue
        if rel in unreadable_set or _under_unreadable_dir(rel, unreadable_dirs):
            next_files[rel] = prev_info

    now = time.time()
    write_manifest(
        manifest_path,
        {
            "generated": report["checked_at"],
            "generated_epoch": now,
            "vault": str(vault),
            "unreadable": sorted(unreadable),
            "files": next_files,
        },
    )

    for err in store_errors:
        print(f"store error ({err['path']}): {err['error']}", file=sys.stderr)

    window_label = previous.get("generated") or "first run"
    changed_total = (
        len(external) + len(audited) + len(external_delete) + len(audited_delete)
    )

    if args.json:
        print(json.dumps(report, indent=1))
        if store_errors:
            return 1
        return 2 if dirty else 0

    if args.quiet:
        if dirty:
            print(
                f"## {report['name']} — {len(external) + len(external_delete)} change(s) outside the audit log"
            )
            print(
                f"since {window_label} · {len(audited) + len(audited_delete)} audited change(s) in the same window"
            )
            for rel in report["window"]["external"][: args.limit]:
                print(f"  ~ {rel}")
            for rel in report["window"]["external_delete"][: args.limit]:
                print(f"  - {rel} (deleted, no audit delete)")
            rest = len(external) + len(external_delete) - args.limit
            if rest > 0:
                print(f"  … {rest} more")
            if args.store:
                print(f"prior versions: {state}/objects")
        if new_unreadable:
            print(
                f"## {report['name']} — {len(new_unreadable)} newly unreadable file(s), skipped"
            )
            for rel in new_unreadable[: args.limit]:
                print(f"  ! {rel}")
        if dirty or new_unreadable:
            print()
        return 1 if store_errors else 0

    print(f"vault:    {vault}")
    print(
        f"files:    {len(disk)}   audit entries: {audit['__meta__']['entries']}   "
        f"audit newest: {audit['__meta__']['newest']}"
    )
    print(f"window:   {window_label} -> {report['checked_at']}")
    print()
    if baseline:
        print(
            "BASELINE RUN — no previous manifest, so nothing is compared against it yet."
        )
        print(
            f"  notes whose disk state differs from what TurboVault last wrote: {len(diverging)}"
        )
        print(f"  notes TurboVault has never written: {len(never_audited)}")
        if args.store:
            print("  (no objects stored on the baseline run)")
        if unreadable:
            print(f"  unreadable, skipped: {len(unreadable)}")
        print()
        print("RESULT: baseline written — the next run reports changes only")
        return 0

    print(
        f"changed since last run: {changed_total} "
        f"({len(audited)} audited, {len(audited_delete)} audited deletes, "
        f"{len(external)} external, {len(external_delete)} external deletes)"
    )
    for label, items in (
        ("~ external", report["window"]["external"]),
        ("- external delete", report["window"]["external_delete"]),
        ("✓ audited", report["window"]["audited"]),
        ("✓ audited delete", report["window"]["audited_delete"]),
    ):
        for rel in items[: args.limit]:
            print(f"  {label:<18} {rel}")
        if len(items) > args.limit:
            print(f"  {label:<18} … {len(items) - args.limit} more")
    if args.store:
        print(f"objects stored this run: {stored}")
    if store_errors:
        print(f"snapshot store errors: {len(store_errors)} (held open for retry)")
    if unreadable:
        print(f"unreadable, skipped: {len(unreadable)}")
    print()

    if args.full:
        print("HISTORICAL DRIFT (audit vs disk right now)")
        print(f"  differs from TurboVault's last write: {len(diverging)}")
        for rel in report["historical"]["diverging"][: args.limit]:
            print(f"    ~ {rel}")
        print(
            f"  audited as present but missing on disk: {len(missing_despite_audit)}"
        )
        for rel in report["historical"]["missing_despite_audit"][: args.limit]:
            print(f"    - {rel}")
        print(f"  never written through TurboVault: {len(never_audited)} of {len(disk)}")
        print()

    if store_errors:
        print("RESULT: ERROR — snapshot storage failed")
        return 1
    print(
        "RESULT:",
        "ATTENTION — changes outside the audit log" if dirty else "in sync",
    )
    return 2 if dirty else 0


if __name__ == "__main__":
    sys.exit(main())
