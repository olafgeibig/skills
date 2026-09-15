#!/usr/bin/env python3
"""Read-only maintainability audit for an Agent Skills library."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import TypedDict

SKIPPED_DIRECTORIES = {".git", ".venv", "node_modules"}
REFERENCE_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_/-])(?:\./)?(?:references|scripts|assets|templates)/[A-Za-z0-9_./-]+"
)


class SkillResult(TypedDict):
    name: str
    path: str
    lines: int
    words: int
    description_chars: int
    errors: list[str]
    warnings: list[str]


def find_skill_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("SKILL.md")
        if not SKIPPED_DIRECTORIES.intersection(path.parts)
    )


def unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def frontmatter_value(frontmatter: str, key: str) -> str:
    lines = frontmatter.splitlines()
    prefix = f"{key}:"
    for index, line in enumerate(lines):
        if not line.startswith(prefix):
            continue
        value = line[len(prefix):].strip()
        if value not in {"|", "|-", ">", ">-"}:
            return unquote(value)
        continuation = []
        for next_line in lines[index + 1:]:
            if next_line and not next_line[0].isspace():
                break
            if next_line.strip():
                continuation.append(next_line.strip())
        return " ".join(continuation)
    return ""


def referenced_files(content: str) -> list[str]:
    return sorted(
        {
            match.group(0).rstrip(".,;:)")
            for match in REFERENCE_PATTERN.finditer(content)
            if not match.group(0).endswith("/")
        }
    )


def inspect_skill(root: Path, path: Path) -> SkillResult:
    content = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n([\s\S]*?)\n---\n?", content)
    frontmatter = match.group(1) if match else ""
    name = frontmatter_value(frontmatter, "name")
    description = frontmatter_value(frontmatter, "description")
    lines = len(content.splitlines())
    words = len(content.split())
    missing_references = [
        target
        for target in referenced_files(content)
        if not (path.parent / target).exists()
    ]
    errors: list[str] = []
    warnings: list[str] = []

    if not name:
        errors.append("missing name")
    if not description:
        errors.append("missing description")
    if name and name != path.parent.name:
        errors.append("name/directory mismatch")
    if len(description) > 1024:
        errors.append("description exceeds 1024 characters")
    if lines > 500:
        errors.append("SKILL.md exceeds 500 lines")
    if len(description) > 57:
        warnings.append("description exceeds Hermes 57-character routing target")
    if 350 < lines <= 500:
        warnings.append("main file requires an explicit size justification")
    elif 250 < lines <= 350:
        warnings.append("review main file for thematic extraction")
    elif 200 < lines <= 250:
        warnings.append("main file exceeds preferred range")
    if missing_references:
        errors.append(f"missing references: {', '.join(missing_references)}")

    return {
        "name": name or path.parent.name,
        "path": str(path.relative_to(root)),
        "lines": lines,
        "words": words,
        "description_chars": len(description),
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    results = [inspect_skill(root, path) for path in find_skill_files(root)]
    summary = {
        "root": str(root),
        "skills": len(results),
        "errors": sum(len(item["errors"]) for item in results),
        "warnings": sum(len(item["warnings"]) for item in results),
    }

    if args.json:
        print(json.dumps({"summary": summary, "results": results}, indent=2))
    else:
        print("skill\tlines\twords\tdescription\tresult")
        for item in results:
            messages = [
                *(f"ERROR: {message}" for message in item["errors"]),
                *(f"WARN: {message}" for message in item["warnings"]),
            ]
            print(
                f"{item['name']}\t{item['lines']}\t{item['words']}\t"
                f"{item['description_chars']}\t{'; '.join(messages) or 'ok'}"
            )
        print(
            f"\n{summary['skills']} skills, {summary['errors']} errors, "
            f"{summary['warnings']} warnings"
        )

    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
