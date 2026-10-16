#!/usr/bin/env python3
# skill-repo-sync — publish background-review skill writes and keep shared skill repos current.
#
# SCRIPT_VERSION: 1.0.0
# Part of the skill-library-maintenance skill (shared repo). Install with
# scripts/install-skill-repo-sync.py; verify with `--selfcheck`.
#
# Modes
#   --safety      (default) publish: commit ledger-recorded skill changes, pull --rebase, push
#   --pull-only   session-start refresh: git pull --ff-only for every shared repo (silent on success)
#   --audit       report only, never writes: review-driven commits since the last audit + defect scan
#   --selfcheck   verify the local install (state file, repos, wrapper, hooks, ledger cursor)
#   --version     print SCRIPT_VERSION
#   --dry-run     do everything except commit/push
#   --verbose     also report no-op runs
#
# Exit codes: 0 ok/no-op · 10 gate findings (nothing committed for the flagged files)
#             11 rebase conflict (aborted, note written) · 12 other error · 13 not installed
#
# Design rules that must not be broken (see references/shared-repo-sync.md):
#   * commits only paths the mutation ledger names — hand-written work in progress is never swept in
#   * one commit per review run, so `git revert <sha>` is surgical
#   * a conflict is aborted, never resolved by choosing a side
#   * no provider/network calls beyond git itself
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_VERSION = "1.0.1"
STATE_NAME = "skill-repo-sync.json"
GROUP_GAP_SECONDS = 120          # entries closer than this belong to one review run
AUDIT_MARKER = "hermes-skill-sync-audit"
CURSOR_KEY = "ledger_cursor"     # index of the last processed ledger line

# Lines that must never enter a shared (generic) skill: instance pointers.
# Both home layouts are covered — Linux (`/home/<user>`) and macOS (`/Users/<user>`).
INSTANCE_PATTERNS = (
    (r"/(?:home|Users)/[A-Za-z0-9_.-]+", "absolute home path"),
    (r"(?<![\w/])~/(?!\.hermes/skills)", "tilde path"),
    (r"\bakademeia\b", "vault name"),
    (r"\b(durin|boromir)\b", "machine name"),
    (r"\bBosch\b", "employer name"),
    (r"\b20\d{2}-\d{2}-\d{2}\b", "date"),
    (r"\b20\d{3}_\d{6}_[0-9a-f]{6}\b", "session id"),
)
LINK_RE = re.compile(r"\]\(([^)#]+?)(?:#[^)]*)?\)")
REF_RE = re.compile(r"`?(references/[A-Za-z0-9_.-]+\.md)`?")


def hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes")).expanduser()


def state_path() -> Path:
    return hermes_home() / STATE_NAME


def load_state() -> dict:
    try:
        return json.loads(state_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state: dict) -> None:
    p = state_path()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, p)


def git(repo: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess:
    """Run git without ever blocking on a prompt.

    A hook runs unattended: a credential prompt or an interactive SSH key question would stall the
    tool round until the hook timeout. BatchMode + no terminal prompt turn those into a fast,
    reportable failure on Linux and macOS alike.
    """
    env = dict(os.environ)
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    env.setdefault("GIT_SSH_COMMAND", "ssh -oBatchMode=yes -oConnectTimeout=10")
    env.setdefault("GIT_ASKPASS", "/bin/true")
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                          check=check, timeout=120, env=env)


def repo_root(path: Path) -> Path | None:
    r = git(path if path.is_dir() else path.parent, "rev-parse", "--show-toplevel")
    return Path(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None


def has_remote(repo: Path) -> bool:
    r = git(repo, "remote")
    return r.returncode == 0 and bool(r.stdout.split())


def repos_from_state() -> list[Path]:
    out: list[Path] = []
    for entry in load_state().get("repos", []):
        p = Path(entry.get("path", "")).expanduser()
        if p.is_dir():
            out.append(p)
    return out


def ledger_path() -> Path:
    return hermes_home() / "skills" / ".curator_ledger.jsonl"


def read_ledger() -> list[dict]:
    p = ledger_path()
    if not p.is_file():
        return []
    entries = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def entry_paths(entry: dict) -> list[Path]:
    """Absolute paths a ledger entry touched (after + before manifests)."""
    paths: list[Path] = []
    for key in ("after", "before"):
        for item in entry.get(key) or []:
            if isinstance(item, dict) and item.get("path"):
                paths.append(Path(str(item["path"])))
    return paths


def group_runs(entries: list[dict]) -> list[list[dict]]:
    """Group ledger entries into review runs (contiguous writes within GROUP_GAP_SECONDS)."""
    runs: list[list[dict]] = []
    for entry in sorted(entries, key=lambda e: str(e.get("ts", ""))):
        if runs:
            last_ts = parse_ts(str(runs[-1][-1].get("ts", "")))
            this_ts = parse_ts(str(entry.get("ts", "")))
            if last_ts and this_ts and (this_ts - last_ts) <= GROUP_GAP_SECONDS:
                runs[-1].append(entry)
                continue
        runs.append([entry])
    return runs


def parse_ts(value: str) -> float | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


# --- gate -----------------------------------------------------------------------------------------
def added_lines(repo: Path, paths: list[str]) -> list[tuple[str, str]]:
    """(file, text) for every line the working tree adds relative to HEAD, scoped to *paths*."""
    r = git(repo, "diff", "-U0", "--no-color", "--", *paths)
    if r.returncode != 0:
        return []
    out: list[tuple[str, str]] = []
    current = ""
    for line in r.stdout.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith("+") and not line.startswith("+++"):
            out.append((current, line[1:]))
    return out


def normalize(text: str) -> str:
    return re.sub(r"[\s`*_.,;:()\[\]\"']+", " ", text).strip().lower()


def repo_line_index(repo: Path, skip: set[str]) -> dict[str, set[str]]:
    """normalized line -> files, for every markdown file in the repo (excluding *skip*)."""
    index: dict[str, set[str]] = {}
    for md in repo.rglob("*.md"):
        rel = str(md.relative_to(repo))
        if rel in skip or "/.git/" in str(md):
            continue
        try:
            for line in md.read_text(encoding="utf-8", errors="replace").splitlines():
                norm = normalize(line)
                if len(norm) >= 40:
                    index.setdefault(norm, set()).add(rel)
        except OSError:
            continue
    return index


def gate(repo: Path, files: list[str]) -> list[dict]:
    """Defect checks on added lines: instance pointers, dangling references, duplicate rules."""
    findings: list[dict] = []
    index = repo_line_index(repo, skip=set(files))
    for file, text in added_lines(repo, files):
        if not text.strip():
            continue
        for pattern, label in INSTANCE_PATTERNS:
            if re.search(pattern, text):
                findings.append({"file": file, "kind": "instance-pointer", "detail": label,
                                 "line": text.strip()[:160]})
        for target in LINK_RE.findall(text) + REF_RE.findall(text):
            target = target.strip()
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            base = (repo / file).parent if file else repo
            if not (base / target).exists() and not (repo / target).exists():
                findings.append({"file": file, "kind": "dangling-reference", "detail": target,
                                 "line": text.strip()[:160]})
        norm = normalize(text)
        if len(norm) >= 40:
            for other in index.get(norm, set()):
                if other != file:
                    findings.append({"file": file, "kind": "duplicate-rule", "detail": other,
                                     "line": text.strip()[:160]})
    # de-duplicate identical findings (a line can hit several patterns)
    seen, unique = set(), []
    for f in findings:
        key = (f["file"], f["kind"], f["detail"], f["line"])
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return unique


# --- publishing -----------------------------------------------------------------------------------
def publish(repo: Path, dry_run: bool, verbose: bool) -> tuple[int, list[str]]:
    """Commit pending ledger paths, rebase onto origin, push. Returns (exit_code, messages)."""
    notes: list[str] = []
    state = load_state()
    entries = read_ledger()
    cursor = int(state.get(CURSOR_KEY) or 0)
    pending = entries[cursor:]

    # Which pending paths belong to this repo?
    in_repo: list[tuple[dict, list[str]]] = []
    for entry in pending:
        rel = []
        for path in entry_paths(entry):
            root = repo_root(path)
            if root == repo:
                try:
                    rel.append(str(path.relative_to(repo)))
                except ValueError:
                    continue
        if rel:
            in_repo.append((entry, sorted(set(rel))))

    if not in_repo:
        return 0, notes

    # One commit per review run; flagged files are held back.
    held: list[dict] = []
    for run in group_runs([e for e, _ in in_repo]):
        file_map = {id(e): rel for e, rel in in_repo}
        files = sorted({f for e in run for f in file_map[id(e)]})
        findings = gate(repo, files)
        if findings:
            bad = {f["file"] for f in findings}
            held.extend(findings)
            files = [f for f in files if f not in bad]
            notes.append(f"gate: {len(findings)} finding(s); held back {sorted(bad)}")
        # Only paths that actually differ from HEAD can be committed; everything else is a no-op.
        dirty = [f for f in files if git(repo, "status", "--porcelain", "--", f).stdout.strip()]
        if not dirty:
            continue
        # Name the commit after the skills whose files really changed — not after every entry the
        # run touched, or the message claims changes the commit does not contain.
        skills = sorted({str(e.get("skill", "?")) for e in run
                         if any(f in dirty for f in file_map[id(e)])})
        if not skills:
            continue
        files = dirty
        stamp = str(run[0].get("ts", ""))[:19]
        message = ("review: publish skill updates (" + ", ".join(skills) + ")\n\n"
                   f"Review-Run: {stamp}\n"
                   f"Skills: {', '.join(skills)}\n"
                   "Source: background-review mutations recorded in the skill ledger.\n"
                   "Revert with: git revert <this commit>")
        if dry_run:
            notes.append(f"[dry-run] would commit {len(files)} file(s): {', '.join(skills)}")
            continue
        if git(repo, "add", "--", *files).returncode != 0:
            notes.append(f"error: git add failed for {files}")
            return 12, notes
        commit = git(repo, "commit", "-q", "-m", message)
        if commit.returncode != 0:
            notes.append("error: git commit failed: " + (commit.stderr or commit.stdout).strip()[:200])
            return 12, notes
        notes.append(f"committed {len(files)} file(s) ({', '.join(skills)})")

    if held:
        report = {"at": datetime.now(tz=timezone.utc).isoformat(), "repo": str(repo), "findings": held}
        (repo / ".git" / "hermes-skill-sync-report.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8")
        return 10, notes

    if dry_run:
        return 0, notes

    # Integrate: rebase onto origin, never resolve by choosing a side.
    if git(repo, "pull", "--rebase", "--quiet").returncode != 0:
        git(repo, "rebase", "--abort")
        conflict = {"at": datetime.now(tz=timezone.utc).isoformat(), "repo": str(repo),
                    "note": "rebase aborted; resolve in a session, both lessons must land"}
        (repo / ".git" / "hermes-skill-sync-conflict.json").write_text(
            json.dumps(conflict, indent=2), encoding="utf-8")
        notes.append("conflict: rebase aborted, note written to .git/hermes-skill-sync-conflict.json")
        return 11, notes

    push = git(repo, "push", "--quiet")
    if push.returncode != 0:
        git(repo, "pull", "--rebase", "--quiet")
        push = git(repo, "push", "--quiet")
        if push.returncode != 0:
            notes.append("error: push failed: " + (push.stderr or "").strip()[:200])
            return 12, notes
    notes.append("pushed")
    return 0, notes


def pull_only(verbose: bool) -> tuple[int, list[str]]:
    notes: list[str] = []
    for repo in repos_from_state():
        if not has_remote(repo):
            continue
        if git(repo, "status", "--porcelain").stdout.strip():
            if verbose:
                notes.append(f"{repo.name}: local changes present — pull skipped")
            continue
        r = git(repo, "pull", "--ff-only", "--quiet")
        if r.returncode != 0:
            notes.append(f"{repo.name}: pull not fast-forwardable — left untouched")
        elif verbose:
            notes.append(f"{repo.name}: up to date")
    return 0, notes


def audit(verbose: bool) -> tuple[int, list[str]]:
    """Report-only: review commits since the last audit + a whole-repo defect scan."""
    notes: list[str] = []
    for repo in repos_from_state():
        marker = repo / ".git" / AUDIT_MARKER
        since = marker.read_text(encoding="utf-8").strip() if marker.is_file() else ""
        rng = f"{since}..HEAD" if since else "-30"
        fmt = "--pretty=%h|%ad|%s"
        args = ["log", fmt, "--date=short"] + ([rng] if since else [f"--since={rng} days ago"])
        log = git(repo, *args)
        commits = [l for l in log.stdout.splitlines() if "review: publish skill updates" in l]
        scan = gate(repo, [])
        if commits or scan:
            notes.append(f"{repo.name}: {len(commits)} review commit(s) since last audit")
            for line in commits[:20]:
                notes.append("  " + line)
            for f in scan[:20]:
                notes.append(f"  ! {f['kind']} in {f['file']}: {f['detail']} — {f['line'][:80]}")
        elif verbose:
            notes.append(f"{repo.name}: nothing to audit")
    return 0, notes


def selfcheck(verbose: bool) -> tuple[int, list[str]]:
    notes: list[str] = []
    state = load_state()
    if not state:
        return 13, [f"not installed: {state_path()} missing"]
    notes.append(f"script version: {SCRIPT_VERSION} (state recorded {state.get('version', '?')})")
    ok = True
    for repo in repos_from_state():
        remote = has_remote(repo)
        notes.append(f"repo {repo}: remote={'yes' if remote else 'NO'} "
                     f"head={git(repo,'rev-parse','--short','HEAD').stdout.strip()}")
        ok = ok and remote
    cursor, total = int(state.get(CURSOR_KEY) or 0), len(read_ledger())
    notes.append(f"ledger: {total} entries, cursor at {cursor}, {max(0, total - cursor)} pending")
    if cursor > total:
        notes.append("WARN cursor beyond ledger — reset it")
    wrapper = Path(str(state.get("wrapper", ""))).expanduser()
    if wrapper.is_file():
        text = wrapper.read_text(encoding="utf-8", errors="replace")
        target = ""
        for line in text.splitlines():
            if line.startswith("exec "):
                parts = line.split('"')
                target = parts[1] if len(parts) > 1 else line.split()[-1]
                break
        if target and Path(target).is_file():
            notes.append(f"wrapper: {wrapper} -> {target} (ok)")
        else:
            notes.append(f"WARN wrapper target missing or unparsable: {target or text[:60]!r}")
            ok = False
    else:
        notes.append(f"WARN wrapper missing: {wrapper}")
        ok = False
    return (0 if ok else 12), notes


def main() -> int:
    ap = argparse.ArgumentParser(description="publish review-driven skill writes; keep shared skill repos in sync")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--safety", action="store_true", help="commit + rebase + push (default)")
    mode.add_argument("--pull-only", action="store_true", help="fast-forward refresh only")
    mode.add_argument("--audit", action="store_true", help="report only")
    mode.add_argument("--selfcheck", action="store_true", help="verify the install")
    mode.add_argument("--version", action="store_true", help="print the script version")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--hook", action="store_true",
                    help="hook mode: silent on success, failures on stderr (keeps hook stdout clean for `hermes hooks doctor`)")
    args = ap.parse_args()

    if args.version:
        print(f"skill-repo-sync {SCRIPT_VERSION}")
        return 0
    if args.selfcheck:
        code, notes = selfcheck(args.verbose)
    elif args.audit:
        code, notes = audit(args.verbose)
    elif args.pull_only:
        code, notes = pull_only(args.verbose)
    else:
        if not load_state():
            print(f"skill-repo-sync: not installed ({state_path()} missing) — run install-skill-repo-sync.py")
            return 13
        code, notes = 0, []
        touched = False
        for repo in repos_from_state():
            repo_code, repo_notes = publish(repo, args.dry_run, args.verbose)
            notes += repo_notes
            touched = touched or bool(repo_notes)
            code = max(code, repo_code)
        # advance the cursor only when every repo published cleanly
        if code in (0, 10):
            state = load_state()
            state[CURSOR_KEY] = len(read_ledger())
            state["last_run"] = datetime.now(tz=timezone.utc).isoformat()
            save_state(state)
        if not notes and args.verbose:
            notes = ["nothing to publish"]
    for line in ([] if args.hook and code == 0 and not args.verbose else notes):
        print(line, file=sys.stderr if args.hook else sys.stdout)
    return code


if __name__ == "__main__":
    sys.exit(main())
