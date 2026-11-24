#!/usr/bin/env python3
"""User-only helper to lock, unlock, or restore locks in an external skills dir.

Usage (run by the user in their own shell — never invoked by the agent):
    python3 bulk-lock.py unlock  /path/to/skills-dir [--dry-run]
    python3 bulk-lock.py restore /path/to/skills-dir [--dry-run]
    python3 bulk-lock.py lock    /path/to/skills-dir [--dry-run]

- `unlock` reads currently locked skills from `hermes curator status`, unlocks
  only the ones in <skills-dir> that are currently locked, and records them in a
  state file so `restore` re-locks ONLY those skills (preserving any skills that
  were already intentionally unlocked for burn-in).
- `restore` re-locks the skills recorded by the previous `unlock` and removes
  the state file once all succeed.
- `lock` explicitly locks every discovered skill in <skills-dir> (e.g. initial
  lock setup on a new checkout).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path


SKIP_DIRS = {".git", ".archive", ".hub", ".locks", ".attic", "__pycache__"}


def discover_skills(root: Path) -> list[tuple[str, Path]]:
    skills: list[tuple[str, Path]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        if "SKILL.md" not in filenames:
            continue
        skill_dir = Path(dirpath)
        name = read_skill_name(skill_dir / "SKILL.md") or skill_dir.name
        skills.append((name, skill_dir))
        dirnames[:] = []  # do not descend inside a skill package
    return sorted(skills, key=lambda item: item[0])


def read_skill_name(skill_md: Path) -> str | None:
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    match = re.search(r"^\s*name:\s*['\"]?([^'\"\n#]+)['\"]?", parts[1], re.MULTILINE)
    return match.group(1).strip() if match else None


def parse_locked_skills(status_output: str) -> set[str]:
    """Extract locked skill names from `hermes curator status` stdout."""
    for line in status_output.splitlines():
        match = re.match(r"^\s*locked\s*\(\d+\):\s*(.+?)(?:\s{2,}\(.*\))?\s*$", line)
        if not match:
            continue
        raw = match.group(1).strip()
        if not raw or raw.lower() == "none":
            return set()
        return {item.strip() for item in raw.split(",") if item.strip()}
    return set()


def get_locked_skills(profile: str | None) -> set[str]:
    cmd = ["hermes"]
    if profile:
        cmd += ["-p", profile]
    cmd += ["curator", "status"]
    result = subprocess.run(cmd, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "curator status failed")
    return parse_locked_skills(result.stdout)


def default_state_file(root: Path, profile: str | None) -> Path:
    key = f"{profile or 'default'}::{root}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
    base = Path.home() / ".hermes" / "cache" / "bulk-lock"
    return base / f"{digest}.json"


def run_curator(action: str, names: list[str], profile: str | None, dry_run: bool) -> int:
    base_cmd = ["hermes"]
    if profile:
        base_cmd += ["-p", profile]
    base_cmd += ["curator", action]

    failures = 0
    for name in names:
        cmd = [*base_cmd, name]
        if dry_run:
            print(" ".join(cmd))
            continue
        result = subprocess.run(cmd, text=True, capture_output=True)
        status = "ok" if result.returncode == 0 else f"FAIL ({result.returncode})"
        detail = (result.stdout or result.stderr or "").strip().splitlines()
        msg = detail[-1] if detail else ""
        print(f"  {status:10} {name:35} {msg}")
        if result.returncode != 0:
            failures += 1
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Lock, unlock, or restore locks in an external skills directory (user-only)."
    )
    parser.add_argument("action", choices=["lock", "unlock", "restore"], help="curator action")
    parser.add_argument("skills_dir", type=Path, help="path to external skills directory")
    parser.add_argument("-p", "--profile", default=None, help="optional Hermes profile name")
    parser.add_argument(
        "--state-file",
        type=Path,
        default=None,
        help="path to record previously locked skills (used by unlock/restore)",
    )
    parser.add_argument("--dry-run", action="store_true", help="print commands without running")
    args = parser.parse_args(argv)

    root = args.skills_dir.expanduser().resolve()
    if not root.is_dir():
        print(f"error: directory not found: {root}", file=sys.stderr)
        return 2

    state_file = (
        args.state_file.expanduser().resolve()
        if args.state_file
        else default_state_file(root, args.profile)
    )

    if args.action == "restore":
        if not state_file.is_file():
            print(f"error: no saved lock state at {state_file}", file=sys.stderr)
            return 2
        payload = json.loads(state_file.read_text(encoding="utf-8"))
        names = sorted(payload.get("previously_locked", []))
        if not names:
            print("No previously locked skills recorded; nothing to restore.")
            if not args.dry_run:
                state_file.unlink(missing_ok=True)
            return 0
        failures = run_curator("lock", names, args.profile, args.dry_run)
        if failures == 0 and not args.dry_run:
            state_file.unlink(missing_ok=True)
            print(f"Restored {len(names)} lock(s) and cleared {state_file}.")
        return 1 if failures else 0

    skills = discover_skills(root)
    if not skills:
        print(f"no skills found under {root}", file=sys.stderr)
        return 1
    discovered = [name for name, _ in skills]

    if args.action == "lock":
        failures = run_curator("lock", discovered, args.profile, args.dry_run)
        return 1 if failures else 0

    # action == "unlock": unlock only currently locked skills and record them
    if state_file.is_file():
        print(
            f"error: existing state file {state_file} — run `restore` first so prior lock state is not overwritten.",
            file=sys.stderr,
        )
        return 2
    try:
        currently_locked = get_locked_skills(args.profile)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    to_unlock = [name for name in discovered if name in currently_locked]
    skipped = [name for name in discovered if name not in currently_locked]
    if not to_unlock:
        print("No discovered skills are currently locked; nothing to unlock.")
        return 0

    if not args.dry_run:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(
            json.dumps(
                {
                    "skills_dir": str(root),
                    "profile": args.profile,
                    "previously_locked": to_unlock,
                    "already_unlocked": skipped,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    else:
        print(f"# would save {len(to_unlock)} previously locked skill(s) to {state_file}")
        if skipped:
            print(f"# already unlocked (preserved): {', '.join(skipped)}")

    failures = run_curator("unlock", to_unlock, args.profile, args.dry_run)
    if not args.dry_run:
        print(f"Saved prior lock state ({len(to_unlock)} skill(s)) to {state_file}.")
        if skipped:
            print(f"Preserved {len(skipped)} already-unlocked skill(s): {', '.join(skipped)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
