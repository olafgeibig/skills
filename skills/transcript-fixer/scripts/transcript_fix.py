#!/usr/bin/env python3
"""Project-local deterministic transcript correction helper.

No AI calls. No global database. Source of truth is .transcript-fixer/config.yaml
and TSV correction files in the current project.
"""
from __future__ import annotations

import argparse
import csv
import difflib
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


CONFIG_DIR = ".transcript-fixer"
CONFIG_FILE = "config.yaml"
CANONICAL_CONFIG_PATH = Path(CONFIG_DIR) / CONFIG_FILE
DEFAULT_CORRECTIONS = ".transcript-fixer/corrections.tsv"


@dataclass
class Glossary:
    path: str
    domain: str = "project"
    format: str = "markdown-bold-terms"


@dataclass
class CorrectionFile:
    path: str
    domain: str = "project"


@dataclass
class Config:
    root: Path
    project: str = "project"
    glossaries: list[Glossary] | None = None
    corrections: list[CorrectionFile] | None = None
    suffix: str = "_corrected"
    diff: bool = True
    keep_original: bool = True

    def __post_init__(self) -> None:
        self.glossaries = self.glossaries or []
        self.corrections = self.corrections or [CorrectionFile(DEFAULT_CORRECTIONS, "project")]


def find_project_root(start: Path | None = None) -> Path | None:
    cur = (start or Path.cwd()).resolve()

    # Canonical location: current working directory contains .transcript-fixer/config.yaml.
    # We keep the upward walk only as a compatibility fallback for nested working dirs.
    canonical = cur / CANONICAL_CONFIG_PATH
    if canonical.exists():
        return cur

    for candidate in cur.parents:
        if (candidate / CANONICAL_CONFIG_PATH).exists():
            return candidate
    return None


def parse_scalar(value: str) -> str | bool:
    value = value.strip().strip('"').strip("'")
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    return value


def load_config(root: Path) -> Config:
    path = root / CONFIG_DIR / CONFIG_FILE
    text = path.read_text(encoding="utf-8")
    cfg = Config(root=root)

    section: str | None = None
    current: dict[str, str] | None = None

    def finish_item() -> None:
        nonlocal current, section
        if not current:
            return
        if section == "glossaries":
            cfg.glossaries.append(Glossary(
                path=current.get("path", ""),
                domain=current.get("domain", "project"),
                format=current.get("format", "markdown-bold-terms"),
            ))
        elif section == "corrections":
            cfg.corrections.append(CorrectionFile(
                path=current.get("path", DEFAULT_CORRECTIONS),
                domain=current.get("domain", "project"),
            ))
        current = None

    cfg.glossaries = []
    cfg.corrections = []

    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        stripped = line.strip()
        if not line.startswith(" ") and stripped.endswith(":"):
            finish_item()
            section = stripped[:-1]
            continue
        if not line.startswith(" ") and ":" in stripped:
            finish_item()
            key, val = stripped.split(":", 1)
            if key == "project":
                cfg.project = str(parse_scalar(val))
            continue
        if stripped.startswith("- "):
            finish_item()
            current = {}
            rest = stripped[2:].strip()
            if rest and ":" in rest:
                key, val = rest.split(":", 1)
                current[key.strip()] = str(parse_scalar(val))
            continue
        if current is not None and ":" in stripped:
            key, val = stripped.split(":", 1)
            current[key.strip()] = str(parse_scalar(val))
            continue
        if section == "output" and ":" in stripped:
            key, val = stripped.split(":", 1)
            parsed = parse_scalar(val)
            if key.strip() == "suffix":
                cfg.suffix = str(parsed)
            elif key.strip() == "diff":
                cfg.diff = bool(parsed)
            elif key.strip() == "keep_original":
                cfg.keep_original = bool(parsed)

    finish_item()
    if not cfg.corrections:
        cfg.corrections = [CorrectionFile(DEFAULT_CORRECTIONS, "project")]
    return cfg


def resolve_path(root: Path, value: str) -> Path:
    p = Path(value).expanduser()
    return p if p.is_absolute() else root / p


def init_project(args: argparse.Namespace) -> None:
    root = Path.cwd().resolve()
    d = root / CONFIG_DIR
    d.mkdir(parents=True, exist_ok=True)
    config = d / CONFIG_FILE
    corrections = root / DEFAULT_CORRECTIONS
    if not config.exists():
        project = args.project or root.name
        config.write_text(f"""project: {project}

glossaries:
  # Add project glossaries here. Relative paths are resolved from project root.
  # - path: csl/context/drivalia-glossary.md
  #   domain: project
  #   format: markdown-bold-terms

corrections:
  - path: .transcript-fixer/corrections.tsv
    domain: project

output:
  suffix: _corrected
  diff: true
  keep_original: true

ai:
  mode: native-agent
""", encoding="utf-8")
    if not corrections.exists():
        corrections.write_text("from\tto\tdomain\tnotes\n", encoding="utf-8")
    print(f"initialized {d}")
    print(f"config: {config}")
    print(f"corrections: {corrections}")


def require_config() -> Config:
    root = find_project_root()
    if not root:
        raise SystemExit("No .transcript-fixer/config.yaml found. Run: transcript_fix.py init")
    return load_config(root)


def read_corrections(cfg: Config) -> list[tuple[str, str, str, str]]:
    rows: list[tuple[str, str, str, str]] = []
    for cf in cfg.corrections:
        path = resolve_path(cfg.root, cf.path)
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                frm = (row.get("from") or "").strip()
                to = (row.get("to") or "").strip()
                domain = (row.get("domain") or cf.domain or "project").strip()
                notes = (row.get("notes") or "").strip()
                if frm and to:
                    rows.append((frm, to, domain, notes))
    rows.sort(key=lambda r: len(r[0]), reverse=True)
    return rows


def safe_replace(text: str, frm: str, to: str) -> tuple[str, int]:
    # Phrase-like replacements are literal. Single token replacements use word boundaries.
    if re.fullmatch(r"[A-Za-z0-9_.+-]+", frm):
        pattern = re.compile(rf"(?<!\w){re.escape(frm)}(?!\w)")
        return pattern.subn(to, text)
    return text.replace(frm, to), text.count(frm)


def apply_corrections(args: argparse.Namespace) -> None:
    cfg = require_config()
    input_path = Path(args.input).expanduser()
    if not input_path.is_absolute():
        input_path = Path.cwd() / input_path
    if not input_path.exists():
        raise SystemExit(f"Input not found: {input_path}")
    text = input_path.read_text(encoding="utf-8")
    original = text
    applied: list[tuple[str, str, int]] = []
    for frm, to, _domain, _notes in read_corrections(cfg):
        text, n = safe_replace(text, frm, to)
        if n:
            applied.append((frm, to, n))
    out = Path(args.output).expanduser() if args.output else input_path.with_name(f"{input_path.stem}{cfg.suffix}{input_path.suffix}")
    if not out.is_absolute():
        out = Path.cwd() / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"wrote: {out}")
    print(f"applied corrections: {sum(n for _, _, n in applied)}")
    for frm, to, n in applied:
        print(f"  {n}x {frm!r} -> {to!r}")
    if cfg.diff and original != text:
        diff_path = out.with_suffix(out.suffix + ".diff")
        diff = difflib.unified_diff(
            original.splitlines(keepends=True),
            text.splitlines(keepends=True),
            fromfile=str(input_path),
            tofile=str(out),
        )
        diff_path.write_text("".join(diff), encoding="utf-8")
        print(f"diff: {diff_path}")


def add_correction(args: argparse.Namespace) -> None:
    cfg = require_config()
    target = resolve_path(cfg.root, cfg.corrections[0].path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text("from\tto\tdomain\tnotes\n", encoding="utf-8")
    with target.open("a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow([args.from_text, args.to_text, args.domain, args.notes or ""])
    print(f"added to {target}: {args.from_text!r} -> {args.to_text!r}")


def extract_terms_from_markdown(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    terms: set[str] = set()
    for m in re.finditer(r"(?:^-\s*)?\*\*([^*\n]+?)\*\*", text, flags=re.M):
        term = m.group(1).strip()
        if 2 <= len(term) <= 100:
            terms.add(term)
            pm = re.search(r"\(([^)]+)\)\s*$", term)
            if pm and 2 <= len(pm.group(1).strip()) <= 30:
                terms.add(pm.group(1).strip())
    return sorted(terms, key=str.lower)


def list_config(args: argparse.Namespace) -> None:
    cfg = require_config()
    print(f"project root: {cfg.root}")
    print(f"project: {cfg.project}")
    print("glossaries:")
    for g in cfg.glossaries:
        p = resolve_path(cfg.root, g.path)
        print(f"  - {g.domain}: {p} ({'exists' if p.exists() else 'missing'})")
    print("corrections:")
    rows = read_corrections(cfg)
    for cf in cfg.corrections:
        p = resolve_path(cfg.root, cf.path)
        print(f"  - {cf.domain}: {p} ({'exists' if p.exists() else 'missing'})")
    print(f"correction rows: {len(rows)}")
    if args.verbose:
        for frm, to, domain, notes in rows:
            print(f"  {domain}: {frm!r} -> {to!r} {notes}")


def print_terms(args: argparse.Namespace) -> None:
    cfg = require_config()
    for g in cfg.glossaries:
        path = resolve_path(cfg.root, g.path)
        if not path.exists():
            print(f"# missing: {path}")
            continue
        print(f"# {g.domain}: {path}")
        for term in extract_terms_from_markdown(path):
            print(term)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Project-local deterministic transcript fixer helper")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="create .transcript-fixer config and corrections TSV")
    p.add_argument("--project", default="")
    p.set_defaults(func=init_project)

    p = sub.add_parser("list", help="show config and corrections")
    p.add_argument("--verbose", "-v", action="store_true")
    p.set_defaults(func=list_config)

    p = sub.add_parser("add", help="add a confirmed correction to the first configured TSV")
    p.add_argument("from_text")
    p.add_argument("to_text")
    p.add_argument("--domain", default="project")
    p.add_argument("--notes", default="")
    p.set_defaults(func=add_correction)

    p = sub.add_parser("apply", help="apply deterministic corrections to a transcript")
    p.add_argument("input")
    p.add_argument("--output", "-o", default="")
    p.set_defaults(func=apply_corrections)

    p = sub.add_parser("terms", help="print terms extracted from configured glossaries")
    p.set_defaults(func=print_terms)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
