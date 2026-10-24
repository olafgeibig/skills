#!/usr/bin/env python3
"""Locate `project-*` skill directories for a Hermes profile.

The convention it implements: every skill directory named `project-*`, in any
skill root the profile sees (its own `skills/` plus every `skills.external_dirs`
entry), is a project skill. The **skill name** is the discriminator — not the
root — so a machine that holds both work and private projects needs no further
hint: you ask for the project, and the root follows.

Usage:
    find-project-skill-dirs.py                 # list every project skill
    find-project-skill-dirs.py fsj             # match projects/fsj
    find-project-skill-dirs.py project-fsj     # same, full skill name
    find-project-skill-dirs.py fsj --json
    find-project-skill-dirs.py --profile robert
    find-project-skill-dirs.py --root ~/some/skills   # override discovery

Exit codes: 0 = found (one match, or a listing), 1 = no match, 2 = ambiguous.
Ambiguous is a real state, not an error to paper over: the same project folder
name in a work and a private vault maps to two skills, and the caller has to
pick by looking at which vault the note lives in.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

MAX_DEPTH = 4
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__"}


def hermes_home(profile: str | None) -> Path:
    """An explicit --profile wins over the ambient HERMES_HOME of this session."""
    base = Path(os.environ.get("HERMES_BASE_HOME", Path.home() / ".hermes"))
    if profile:
        return base.expanduser() / "profiles" / profile
    if os.environ.get("HERMES_HOME"):
        return Path(os.environ["HERMES_HOME"]).expanduser()
    return base.expanduser()


def external_dirs(home: Path) -> list[Path]:
    """Read `skills.external_dirs` through the supported reader, not by parsing YAML."""
    env = dict(os.environ, HERMES_HOME=str(home))
    try:
        out = subprocess.run(
            ["hermes", "config", "get", "skills.external_dirs"],
            env=env, capture_output=True, text=True, timeout=60, check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    dirs: list[Path] = []
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("- "):
            value = line[2:].strip().strip("'\"")
            if value:
                dirs.append(Path(os.path.expandvars(value)).expanduser())
    return dirs


def skill_roots(home: Path) -> list[Path]:
    roots = [home / "skills"] + external_dirs(home)
    seen: set[str] = set()
    unique: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        real = str(root.resolve())
        if real not in seen:
            seen.add(real)
            unique.append(root)
    return unique


def project_skills(roots: list[Path]):
    """Yield (name, path, root) for every directory named project-* holding a SKILL.md."""
    for root in roots:
        base_depth = len(root.parts)
        for current, dirnames, _files in os.walk(root):
            here = Path(current)
            if len(here.parts) - base_depth >= MAX_DEPTH:
                dirnames[:] = []
                continue
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            for name in list(dirnames):
                if name.startswith("project-") and (here / name / "SKILL.md").is_file():
                    yield name, here / name, root


def main() -> int:
    parser = argparse.ArgumentParser(description="Locate project-* skill directories.")
    parser.add_argument("project", nargs="?", help="vault folder stem (fsj) or skill name (project-fsj)")
    parser.add_argument("--profile", help="profile name; wins over the session's HERMES_HOME")
    parser.add_argument("--root", action="append", default=[], help="skill root to scan instead of discovery (repeatable)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    home = hermes_home(args.profile)
    roots = [Path(os.path.expandvars(r)).expanduser() for r in args.root] or skill_roots(home)

    found = list(project_skills(roots))
    if args.project:
        wanted = args.project if args.project.startswith("project-") else f"project-{args.project}"
        found = [item for item in found if item[0] == wanted]

    ambiguous = bool(args.project) and len(found) > 1
    code = 0 if found else 1
    if ambiguous:
        code = 2

    if args.json:
        print(json.dumps({
            "hermes_home": str(home),
            "roots": [str(r) for r in roots],
            "matches": [{"name": n, "path": str(p), "root": str(r)} for n, p, r in found],
            "ambiguous": ambiguous,
        }, indent=2))
    else:
        if not roots:
            print("no skill roots found", file=sys.stderr)
        elif not found:
            print(f"no project skill for {args.project!r}" if args.project else "no project-* skills", file=sys.stderr)
        else:
            if ambiguous:
                print(f"ambiguous: {len(found)} skills named {found[0][0]} — pick by the vault the note lives in", file=sys.stderr)
            for name, path, root in found:
                print(path)
    return code


if __name__ == "__main__":
    sys.exit(main())
