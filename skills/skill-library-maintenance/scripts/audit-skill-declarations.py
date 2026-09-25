#!/usr/bin/env python3
"""Audit skill-name collisions and local routing declarations.

Two failures this reports:

1. **Name collision** — the same frontmatter `name:` reachable from more than one
   root. Hermes' loader fails closed on those, so the skill is unusable under its
   bare name:

       skill_view(name) -> "Ambiguous skill name '...': 2 skills match across your
                           local skills dir and external_dirs. Refusing to guess"

2. **Undeclared local skill** — a skill that does not say what it is: neither
   `metadata.adapted_from` (a delta for a named source skill) nor
   `metadata.scope: standalone`. An undeclared skill that overlaps an external
   skill is an *unnamed adaptation*: it splits a rule set across two locations
   while the owning skill stays unaware.

Check 2 is scoped by provenance so it stays actionable:

- **agent-created** (`.usage.json` -> `created_by: agent`) — the agent decided to
  create this skill, so the agent owes the declaration. Reported in full.
- **unattributed** (no provenance marker) — predates the marker or was created in
  the foreground. Declare on next edit; only overlap candidates are listed.
- **managed** (`.bundled_manifest`, `.hub/lock.json`) — upstream packages, not
  local decisions. Skipped and counted, so the exclusion stays visible.

The overlap column is a **candidate list for human review**, not a verdict —
token similarity over name plus description.

Usage:
    python3 audit-skill-declarations.py
    python3 audit-skill-declarations.py --strict    # unnamed adaptation is fatal
    python3 audit-skill-declarations.py --all --json
    python3 audit-skill-declarations.py --root ~/some/skills:label

Exit codes: 0 clean, 1 collision, 1 with --strict when an agent-created skill is
undeclared and overlaps an external skill, 2 no roots.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

SKIP_DIRS = {
    ".archive",
    ".hub",
    ".curator_backups",
    ".git",
    ".locks",
    ".attic",
    "__pycache__",
}

STOPWORDS = {
    "a", "an", "and", "as", "at", "by", "for", "from", "in", "into", "is", "it",
    "its", "of", "on", "or", "that", "the", "this", "to", "use", "using", "when",
    "with", "your", "der", "die", "das", "und", "fuer", "für", "mit", "oder",
    "von", "zu",
}


# --------------------------------------------------------------------------- #
# roots and provenance
# --------------------------------------------------------------------------- #
def profile_home() -> str:
    return os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")


def external_dirs_from_config() -> list[str]:
    """Read skills.external_dirs from the active profile's config.yaml.

    Deliberately a line scanner: no YAML dependency, and only this one list is
    needed. The list ends at the first line that is not an item indented deeper
    than the `external_dirs:` key, so sibling keys (`disabled:` and friends) are
    not swallowed.
    """
    config = os.path.join(profile_home(), "config.yaml")
    try:
        with open(config, encoding="utf-8", errors="replace") as handle:
            lines = handle.read().splitlines()
    except OSError:
        return []

    dirs: list[str] = []
    inside_skills = False
    skills_indent = 0
    key_indent = None
    for line in lines:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if inside_skills and indent <= skills_indent:
            inside_skills = False
            key_indent = None
        if not stripped or stripped.startswith("#"):
            continue
        if re.match(r"^skills:\s*$", stripped):
            inside_skills = True
            skills_indent = indent
            key_indent = None
            continue
        if not inside_skills:
            continue
        if key_indent is None:
            match = re.match(r"^external_dirs:\s*(.*)$", stripped)
            if not match:
                continue
            key_indent = indent
            inline = match.group(1).strip()
            if inline and inline != "[]":
                for part in re.findall(r"[^\s,\[\]]+", inline):
                    dirs.append(os.path.expanduser(part.strip("\"'")))
            continue
        if indent <= key_indent:
            key_indent = None  # left the list, e.g. `disabled:`
            continue
        item = re.match(r"^-\s*(.+)$", stripped)
        if item:
            dirs.append(os.path.expanduser(item.group(1).strip().strip("\"'")))
    return [d for d in dirs if d]


def default_roots() -> list[tuple[str, str]]:
    roots = [("local", os.path.join(profile_home(), "skills"))]
    for path in external_dirs_from_config():
        label = "ext:" + (os.path.basename(os.path.dirname(path.rstrip("/"))) or path)
        roots.append((label, path))
    return roots


def parse_roots(raw_roots) -> list[tuple[str, str]]:
    roots = []
    for raw in raw_roots:
        path, _, label = raw.partition(":")
        path = os.path.expanduser(path)
        roots.append((label or os.path.basename(path.rstrip("/")) or path, path))
    return roots


def managed_names(local_root: str) -> set[str]:
    """Skills Hermes manages itself: bundled manifest plus hub/tap installs."""
    names: set[str] = set()
    try:
        with open(
            os.path.join(local_root, ".bundled_manifest"),
            encoding="utf-8",
            errors="replace",
        ) as handle:
            for line in handle:
                line = line.strip()
                if line:
                    names.add(line.split(":", 1)[0])
    except OSError:
        pass
    try:
        with open(
            os.path.join(local_root, ".hub", "lock.json"),
            encoding="utf-8",
            errors="replace",
        ) as handle:
            names.update(json.load(handle).get("installed", {}).keys())
    except (OSError, ValueError):
        pass
    return names


def provenance(local_root: str) -> dict[str, str | None]:
    """Map skill name -> created_by value from the profile's .usage.json."""
    try:
        with open(
            os.path.join(local_root, ".usage.json"), encoding="utf-8", errors="replace"
        ) as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return {
        name: (entry or {}).get("created_by")
        for name, entry in data.items()
        if isinstance(entry, dict)
    }


# --------------------------------------------------------------------------- #
# scanning
# --------------------------------------------------------------------------- #
def skill_dirs(root: str):
    """Yield every directory that directly contains SKILL.md; never descend into one.

    os.path.isfile() follows symlinks, so a symlinked skill directory is
    recognised and treated as a leaf. A plain os.walk(followlinks=False) skips
    symlinked skill dirs entirely and silently undercounts collisions.
    """
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")
        ]
        if "SKILL.md" in filenames:
            yield dirpath
            dirnames[:] = []  # a skill directory is a leaf


def read_frontmatter(skill_dir: str) -> str:
    path = os.path.join(skill_dir, "SKILL.md")
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            text = handle.read(8000)
    except OSError:
        return ""
    match = re.match(r"^---\s*\n(.*?)\n---\s*(\n|$)", text, re.S)
    return match.group(1) if match else ""


def scalar(frontmatter: str, key: str):
    """First `key: value` scalar anywhere in the frontmatter (heuristic)."""
    match = re.search(rf"^\s*{re.escape(key)}:\s*(.+?)\s*$", frontmatter, re.M)
    if not match:
        return None
    value = match.group(1).strip()
    if value in ("|", ">", "|-", ">-"):
        return None  # block scalar: none of the audited keys need it
    return value.strip("\"'")


def list_items(frontmatter: str, key: str) -> list[str]:
    lines = frontmatter.splitlines()
    items: list[str] = []
    for index, line in enumerate(lines):
        if not re.match(rf"^\s*{re.escape(key)}:\s*$", line):
            continue
        key_indent = len(line) - len(line.lstrip())
        for follower in lines[index + 1 :]:
            if not follower.strip():
                continue
            if len(follower) - len(follower.lstrip()) <= key_indent:
                break
            item = re.match(r"^-\s*(.+)$", follower.strip())
            if item:
                items.append(item.group(1).strip().strip("\"'"))
    return items


def tokens(*parts: str) -> set[str]:
    words: set[str] = set()
    for part in parts:
        if not part:
            continue
        for word in re.split(r"[^0-9a-zA-ZäöüßÄÖÜ+]+", part.lower()):
            if len(word) < 3 or word in STOPWORDS:
                continue
            words.add(word)
    return words


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def collect(roots) -> tuple[dict, list[str]]:
    index: dict[str, list[dict]] = {}
    missing: list[str] = []
    for label, root in roots:
        if not os.path.isdir(root):
            missing.append(f"{label} {root}")
            continue
        for skill_dir in skill_dirs(root):
            frontmatter = read_frontmatter(skill_dir)
            name = scalar(frontmatter, "name") or os.path.basename(skill_dir)
            index.setdefault(name, []).append(
                {
                    "root": label,
                    "dir": skill_dir,
                    "name": name,
                    "description": scalar(frontmatter, "description") or "",
                    "adapted_from": scalar(frontmatter, "adapted_from"),
                    "scope": scalar(frontmatter, "scope"),
                    "related_skills": list_items(frontmatter, "related_skills"),
                    "symlink": os.path.islink(skill_dir),
                    "real": os.path.realpath(skill_dir),
                }
            )
    return index, missing


# --------------------------------------------------------------------------- #
# report
# --------------------------------------------------------------------------- #
def status_of(entry: dict) -> str:
    if entry["adapted_from"]:
        return "adaptation"
    if (entry["scope"] or "").strip().lower() == "standalone":
        return "standalone"
    return "UNDECLARED"


def build_report(index, threshold: float, managed: set[str], created_by: dict,
                 include_managed: bool) -> dict:
    collisions = {name: hits for name, hits in index.items() if len(hits) > 1}
    local_hits = [
        entry for hits in index.values() for entry in hits if entry["root"] == "local"
    ]
    external = [
        entry for hits in index.values() for entry in hits if entry["root"] != "local"
    ]

    agent, unattributed = [], []
    skipped_managed = 0
    for entry in sorted(local_hits, key=lambda item: item["name"]):
        manage = entry["name"] in managed
        if manage and not include_managed:
            skipped_managed += 1
            continue

        own_tokens = tokens(entry["name"], entry["description"])
        candidates = []
        for other in external:
            if other["name"] == entry["name"]:
                continue
            score = jaccard(own_tokens, tokens(other["name"], other["description"]))
            name_score = jaccard(
                set(entry["name"].split("-")), set(other["name"].split("-"))
            )
            if score >= threshold or name_score >= 0.5:
                candidates.append(
                    {"skill": other["name"], "root": other["root"], "score": round(score, 3)}
                )
        candidates.sort(key=lambda item: -item["score"])

        record = {
            "name": entry["name"],
            "dir": entry["dir"],
            "status": status_of(entry),
            "adapted_from": entry["adapted_from"],
            "scope": entry["scope"],
            "related_skills": entry["related_skills"],
            "candidates": candidates[:3],
            "managed": manage,
        }
        if created_by.get(entry["name"]) == "agent":
            agent.append(record)
        else:
            unattributed.append(record)

    return {
        "collisions": collisions,
        "agent_created": agent,
        "unattributed": unattributed,
        "skipped_managed": skipped_managed,
        "threshold": threshold,
    }


def _detail(record: dict) -> str:
    detail = ""
    if record["adapted_from"]:
        detail = f" adapted_from={record['adapted_from']}"
    elif record["scope"]:
        detail = f" scope={record['scope']}"
    if record["candidates"]:
        detail += "  candidates: " + ", ".join(
            f"{c['skill']} ({c['score']})" for c in record["candidates"]
        )
    return detail


def print_report(report: dict, roots, missing) -> None:
    for line in missing:
        print(f"  ! missing root: {line}", file=sys.stderr)
    print(f"roots={len(roots)}  local={roots[0][1] if roots else '?'}")
    for label, root in roots[1:]:
        print(f"          {label}: {root}")

    collisions = report["collisions"]
    print(f"\nCOLLISIONS: {len(collisions)}")
    for name, hits in sorted(collisions.items()):
        print(f"\n[{name}]  skill_view({name!r}) refuses this")
        for entry in hits:
            link = f" -> {entry['real']}" if entry["symlink"] else ""
            print(f"   {entry['root']:18} {entry['dir']}{link}")

    agent = report["agent_created"]
    agent_gaps = [r for r in agent if r["status"] == "UNDECLARED"]
    agent_risky = [r for r in agent_gaps if r["candidates"]]
    print(
        f"\nAGENT-CREATED (created_by: agent) — declaration required: "
        f"{len(agent)} checked, {len(agent_gaps)} undeclared, "
        f"{len(agent_risky)} with an overlap candidate"
    )
    for record in agent:
        marker = "ok  " if record["status"] != "UNDECLARED" else "GAP "
        print(f"  {marker}{record['name']:42}{_detail(record)}")

    unattributed = report["unattributed"]
    unattributed_gaps = [r for r in unattributed if r["status"] == "UNDECLARED"]
    print(
        f"\nUNATTRIBUTED LOCAL (no provenance marker) — declare on next edit: "
        f"{len(unattributed)} skills, {len(unattributed_gaps)} undeclared"
    )
    for record in unattributed_gaps:
        if record["candidates"]:
            print(f"  ?   {record['name']:42}{_detail(record)}")
    print(
        f"  ({len(unattributed_gaps) - sum(1 for r in unattributed_gaps if r['candidates'])}"
        " further undeclared without an overlap candidate)"
    )
    print(f"\nHermes-managed skipped: {report['skipped_managed']}")

    if agent_risky:
        print(
            "\nUndeclared = neither `metadata.adapted_from` nor `metadata.scope: standalone`.\n"
            "A candidate hit means it may be an unnamed adaptation: route the delta into the\n"
            "owning skill, or rename it `<source>-adaptation` with the declaration.\n"
            "A non-standard scope value (e.g. `scope: olaf-personal`) is still undeclared."
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit skill-name collisions and local routing declarations."
    )
    parser.add_argument(
        "--root",
        action="append",
        default=None,
        metavar="PATH[:LABEL]",
        help="override the discovered roots (repeatable)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 when an agent-created skill is undeclared and overlaps an external skill",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="also check Hermes-managed (bundled, hub-installed) skills",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--threshold", type=float, default=0.10, help="overlap threshold (default 0.10)"
    )
    args = parser.parse_args()

    roots = parse_roots(args.root) if args.root else default_roots()
    if not roots:
        print("no roots to scan", file=sys.stderr)
        return 2

    local_root = roots[0][1] if roots and roots[0][0] == "local" else None
    index, missing = collect(roots)
    managed = managed_names(local_root) if local_root else set()
    created_by = provenance(local_root) if local_root else {}
    report = build_report(index, args.threshold, managed, created_by, args.all)

    if args.json:
        print(json.dumps(report, indent=1))
    else:
        print_report(report, roots, missing)

    if report["collisions"]:
        return 1
    if args.strict and any(
        r["status"] == "UNDECLARED" and r["candidates"] for r in report["agent_created"]
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
