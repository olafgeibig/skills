#!/usr/bin/env python3
"""Normalize SKILL.md frontmatter to this library's Hermes variant.

Repairs declaration defects while the skill still loads in Hermes:

  * `version:` / `author:` -> top level (promoted out of `metadata:` when nested).
    The authoring linter expects them there in every root; `skills-ref` reports
    them as an accepted portability finding, not a defect.
  * flow-style lists (`tags: [a, b]`) -> block lists
  * `--category` given                -> `metadata.hermes.category` (never added on its own)
  * `--scope` given                   -> `metadata.scope` (never added on its own)

The BODY IS NEVER TOUCHED: frontmatter and body are split before parsing, the
original body string is re-attached after the dump, and the result is verified
byte-identical.

Usage:
    normalize-skill-frontmatter.py <skill-dir-or-SKILL.md> [more...] \\
        [--category own] [--scope standalone] [--bump patch|minor|major|none] \\
        [--backup-dir DIR] [--dry-run]

Nothing is added unless you ask for it: without `--category`/`--scope` both
declarations stay exactly as they are, and their absence is not a failure. Pass
`--category own --scope standalone` only for a profile-local package.
"""
from __future__ import annotations

import argparse
import pathlib
import shutil
import sys

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML required: python3 -m pip install pyyaml")


def split_skill_md(text: str):
    """Return (frontmatter_dict, frontmatter_raw, body). The body is untouched."""
    if not text.startswith("---\n"):
        raise ValueError("file does not start with a frontmatter block")
    end = text.index("\n---\n", 3)
    raw = text[4:end]
    body = text[end + 5:]
    return (yaml.safe_load(raw) or {}), raw, body


def bump(version, kind: str) -> str:
    if kind == "none":
        return version or "0.1.0"
    parts = str(version or "0.0.0").split(".")
    while len(parts) < 3:
        parts.append("0")
    idx = {"major": 0, "minor": 1, "patch": 2}[kind]
    parts[idx] = str(int(parts[idx]) + 1)
    for i in range(idx + 1, 3):
        parts[i] = "0"
    return ".".join(parts[:3])


def normalize(path: pathlib.Path, category: str, scope: str, kind: str):
    text = path.read_text()
    fm, _raw, body = split_skill_md(text)

    meta = dict(fm.get("metadata") or {})
    top = dict(fm)
    top.pop("metadata", None)
    for key in ("version", "author"):   # library standard: top level, never nested
        if key in meta:
            top[key] = meta.pop(key)
    hermes = dict(meta.get("hermes") or {})
    if category:
        hermes["category"] = category
    if hermes or "hermes" in meta:
        meta["hermes"] = hermes
    if scope:
        meta["scope"] = scope
    top["version"] = bump(top.get("version"), kind)

    order = ("name", "description", "version", "author",
             "license", "compatibility", "allowed-tools")
    out = {}
    for key in order:                   # canonical order first
        if key in top:
            out[key] = top.pop(key)
    for key, value in top.items():      # then any remaining original keys
        out[key] = value
    out["metadata"] = meta

    new_fm = yaml.safe_dump(out, allow_unicode=True, sort_keys=False,
                            default_flow_style=False, width=10000)
    return "---\n" + new_fm + "---\n" + body, body, out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("targets", nargs="+")
    ap.add_argument("--category", default="", help="set metadata.hermes.category; empty leaves it untouched")
    ap.add_argument("--scope", default="", help="set metadata.scope; empty leaves it untouched")
    ap.add_argument("--bump", default="patch", choices=["patch", "minor", "major", "none"])
    ap.add_argument("--backup-dir", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    failures = 0
    for target in args.targets:
        p = pathlib.Path(target)
        if p.is_dir():
            p = p / "SKILL.md"
        if not p.is_file():
            print(f"  !! not found: {p}")
            failures += 1
            continue
        try:
            new_text, body, out = normalize(p, args.category, args.scope, args.bump)
        except Exception as exc:                       # noqa: BLE001
            print(f"  !! {p}: {exc}")
            failures += 1
            continue

        print(f"  {p.parent.name:<32} version={out['version']} "
              f"category={(out['metadata'].get('hermes') or {}).get('category')}")
        if args.dry_run:
            print(new_text[: new_text.index('\n---\n', 3) + 5])
            continue

        if args.backup_dir:
            bdir = pathlib.Path(args.backup_dir)
            bdir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, bdir / f"{p.parent.name}.SKILL.md.bak")
        p.write_text(new_text)

        check_fm, _r, check_body = split_skill_md(p.read_text())
        ok_body = check_body == body
        ok_meta = (not args.category) or (
            check_fm.get("metadata", {}).get("hermes", {}).get("category") is not None
        )
        meta_keys = set((check_fm.get("metadata") or {}).keys())
        ok_top = "version" in check_fm and not meta_keys & {"version", "author"}
        print(f"      body_identical={ok_body} category_declared={ok_meta} top_level_version={ok_top}")
        if not (ok_body and ok_meta and ok_top):
            failures += 1

    if not args.dry_run:
        print("\n  Validate with the Hermes authoring linter and the library audit;")
        print("  skills-ref is a portability check whose frontmatter finding is expected.")
        print("  Then confirm discovery: hermes skills list  (expected entries present).")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
