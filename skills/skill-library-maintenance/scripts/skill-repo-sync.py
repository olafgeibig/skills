#!/usr/bin/env python3
# skill-repo-sync — publish background-review skill writes and keep shared skill repos current.
#
# SCRIPT_VERSION: 1.0.2
# Part of the skill-library-maintenance skill (shared repo). Install with
# scripts/install-skill-repo-sync.py; verify with `--selfcheck`.
#
# Modes
#   --safety      (default) verify ledger changes, commit, fetch origin, rebase if needed, push
#   --pull-only   session-start refresh: git pull --ff-only for every shared repo (main only)
#   --audit       report only, never writes: review-driven commits since the last audit + defect scan
#   --selfcheck   verify the local install (state file, repos, branch policy, wrapper, ledger cursor)
#   --version     print SCRIPT_VERSION
#   --dry-run     read-only preview: no state, index, report, commit, fetch, or push writes
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
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_VERSION = "1.0.2"
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
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON in mutation ledger {p}") from exc
        if not isinstance(entry, dict):
            raise ValueError(f"non-object entry in mutation ledger {p}")
        entries.append(entry)
    return entries


def entry_paths(entry: dict) -> list[Path]:
    """Absolute paths a ledger entry touched (after + before manifests)."""
    paths: list[Path] = []
    for key in ("after", "before"):
        for item in entry.get(key) or []:
            if isinstance(item, dict) and item.get("path"):
                paths.append(Path(str(item["path"])))
    return paths


def manifest_hash(entry: dict, side: str, absolute_path: Path) -> str | None:
    for item in entry.get(side) or []:
        if isinstance(item, dict) and item.get("path") == str(absolute_path):
            value = item.get("sha256")
            return str(value) if value else None
    return None


def git_bytes(repo: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    env = dict(os.environ)
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    env.setdefault("GIT_SSH_COMMAND", "ssh -oBatchMode=yes -oConnectTimeout=10")
    env.setdefault("GIT_ASKPASS", "/bin/true")
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                          check=False, timeout=120, env=env)


def blob_hash_at_head(repo: Path, relative_path: str) -> str | None:
    object_name = f"HEAD:{relative_path}"
    result = git_bytes(repo, "show", object_name)
    if result.returncode != 0:
        return None
    return hashlib.sha256(result.stdout).hexdigest()


def worktree_hash(repo: Path, relative_path: str) -> str | None:
    path = repo / relative_path
    if not path.exists():
        return None
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_path(repo: Path, name: str) -> Path:
    result = git(repo, "rev-parse", "--git-path", name)
    path = Path(result.stdout.strip())
    return path if path.is_absolute() else (repo / path)


def branch_policy(repo: Path) -> tuple[bool, str]:
    branch = git(repo, "branch", "--show-current")
    upstream = git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    actual_branch = branch.stdout.strip()
    actual_upstream = upstream.stdout.strip() if upstream.returncode == 0 else "<none>"
    if actual_branch != "main" or actual_upstream != "origin/main":
        return False, (f"expected branch main tracking origin/main; found "
                       f"{actual_branch or '<detached>'} tracking {actual_upstream}")
    return True, ""


def repository_preflight(repo: Path) -> tuple[bool, str]:
    allowed, reason = branch_policy(repo)
    if not allowed:
        return False, reason
    staged = git(repo, "diff", "--cached", "--quiet")
    if staged.returncode != 0:
        return False, "pre-existing staged changes; publisher refuses to commit with a dirty index"
    for marker in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply"):
        if git_path(repo, marker).exists():
            return False, f"Git operation already in progress ({marker})"
    return True, ""


def verify_file_chain(
    repo: Path, relative_path: str, events: list[dict], run_index: dict[int, int], committed_ids: set[str]
) -> tuple[str, str, int | None]:
    """Authorize one worktree file only when ledger hashes exactly describe its changes."""
    absolute_path = repo / relative_path
    path_events = [
        entry for entry in events
        if absolute_path in entry_paths(entry)
    ]
    if not path_events:
        return "held", "no matching ledger manifest", None

    head_hash = blob_hash_at_head(repo, relative_path)
    current_hash = worktree_hash(repo, relative_path)
    published_prefix = [
        index for index, entry in enumerate(path_events)
        if str(entry.get("id", "")) in committed_ids
        or manifest_hash(entry, "after", absolute_path) == head_hash
    ]
    start = max(published_prefix) + 1 if published_prefix else 0
    if start == len(path_events):
        if current_hash == head_hash:
            return "published", "already present at HEAD", None
        return "held", "worktree differs from the ledger-published HEAD content", None

    expected = head_hash
    pending = path_events[start:]
    for entry in pending:
        before_hash = manifest_hash(entry, "before", absolute_path)
        after_hash = manifest_hash(entry, "after", absolute_path)
        if before_hash != expected:
            return "held", "ledger before-hash does not match HEAD or the preceding ledger entry", None
        expected = after_hash
    if expected != current_hash:
        return "held", "worktree hash does not match the final ledger after-hash", None

    run_ids = {run_index[id(entry)] for entry in pending}
    if len(run_ids) != 1:
        return "held", "multiple review runs changed this file; intermediate snapshots are unavailable", None
    return "pending", "ledger hash chain verified", next(iter(run_ids))


def committed_ledger_ids(repo: Path) -> set[str]:
    history = git(repo, "log", "--format=%B%x00")
    if history.returncode != 0:
        return set()
    ids: set[str] = set()
    for message in history.stdout.split("\x00"):
        for line in message.splitlines():
            if line.startswith("Ledger-Entries:"):
                ids.update(value.strip() for value in line.partition(":")[2].split(",") if value.strip())
    return ids


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
    if cursor < 0 or cursor > len(entries):
        return 12, [f"{repo.name}: invalid ledger cursor {cursor} for {len(entries)} entries"]
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

    allowed, reason = repository_preflight(repo)
    if not allowed:
        return 12, [f"{repo.name}: {reason}"]

    runs = group_runs([entry for entry, _ in in_repo])
    run_index = {id(entry): index for index, run in enumerate(runs) for entry in run}
    committed_ids = committed_ledger_ids(repo)
    file_events: dict[str, list[dict]] = {}
    for entry, paths in in_repo:
        for relative_path in paths:
            file_events.setdefault(relative_path, []).append(entry)

    candidate_by_run: dict[int, list[str]] = {}
    held_by_run: dict[int, list[dict]] = {}
    for relative_path, events in file_events.items():
        status, detail, owner = verify_file_chain(repo, relative_path, events, run_index, committed_ids)
        if status == "published":
            continue
        if status == "held":
            run_id = run_index[id(events[-1])]
            held_by_run.setdefault(run_id, []).append({
                "file": relative_path,
                "kind": "ledger-integrity",
                "detail": detail,
                "line": "",
            })
            continue
        assert owner is not None
        candidate_by_run.setdefault(owner, []).append(relative_path)

    all_candidates = set(file_events)
    changed_paths = set(git(repo, "diff", "--name-only").stdout.splitlines())
    untracked_paths = set(git(repo, "ls-files", "--others", "--exclude-standard").stdout.splitlines())
    unexpected = (changed_paths | untracked_paths) - all_candidates
    if unexpected:
        return 12, [f"{repo.name}: unrelated worktree changes prevent publishing: {sorted(unexpected)}"]

    held: list[dict] = []
    for run_id, run in enumerate(runs):
        files = sorted(set(candidate_by_run.get(run_id, [])))
        run_held = held_by_run.get(run_id, [])
        if files and not run_held:
            findings = gate(repo, files)
            if findings:
                run_held.extend(findings)
        if run_held:
            held.extend(run_held)
            notes.append(f"gate: held review run {run_id + 1}; {len(run_held)} finding(s)")
            for finding in run_held:
                notes.append(f"  ! {finding['kind']} in {finding['file']}: {finding['detail']}")
            continue
        if not files:
            continue

        skills = sorted({str(entry.get("skill", "?")) for entry in run})
        stamp = str(run[0].get("ts", ""))[:19]
        message = ("review: publish skill updates (" + ", ".join(skills) + ")\n\n"
                   f"Review-Run: {stamp}\n"
                   f"Skills: {', '.join(skills)}\n"
                   "Source: background-review mutations recorded in the skill ledger.\n"
                   "Revert with: git revert <this commit>")
        ledger_ids = sorted(str(entry["id"]) for entry in run if entry.get("id"))
        if ledger_ids:
            message += "\nLedger-Entries: " + ", ".join(ledger_ids)
        if dry_run:
            notes.append(f"[dry-run] would commit {len(files)} file(s): {', '.join(skills)}")
            continue
        staged = git(repo, "add", "--", *files)
        if staged.returncode != 0:
            notes.append(f"error: git add failed for {files}: {staged.stderr.strip()[:200]}")
            return 12, notes
        checked = git(repo, "diff", "--cached", "--check", "--", *files)
        if checked.returncode != 0:
            notes.append(f"error: staged whitespace check failed: {checked.stderr.strip()[:200]}")
            return 12, notes
        commit = git(repo, "commit", "--only", "-q", "-m", message, "--", *files)
        if commit.returncode != 0:
            notes.append("error: git commit failed: " + (commit.stderr or commit.stdout).strip()[:200])
            return 12, notes
        notes.append(f"committed {len(files)} file(s) ({', '.join(skills)})")

    if dry_run:
        return (10 if held else 0), notes
    if held:
        report = {"at": datetime.now(tz=timezone.utc).isoformat(), "repo": str(repo), "findings": held}
        git_path(repo, "hermes-skill-sync-report.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8")
        notes.append("held ledger entries remain pending; pull/push skipped until they are resolved")
        return 10, notes

    # Do not update remote refs while unrelated user changes remain in the checkout.
    if git(repo, "status", "--porcelain").stdout.strip():
        notes.append(f"{repo.name}: worktree is not clean after publishing; pull/push skipped")
        return 12, notes

    fetch = git(repo, "fetch", "origin", "--quiet")
    if fetch.returncode != 0:
        notes.append(f"{repo.name}: fetch failed: {(fetch.stderr or fetch.stdout).strip()[:300]}")
        return 12, notes

    remote_is_ancestor = git(repo, "merge-base", "--is-ancestor", "origin/main", "HEAD")
    if remote_is_ancestor.returncode != 0:
        rebase = git(repo, "rebase", "origin/main")
        if rebase.returncode != 0:
            rebase_active = git_path(repo, "rebase-merge").exists() or git_path(repo, "rebase-apply").exists()
            if rebase_active:
                aborted = git(repo, "rebase", "--abort")
                marker = git_path(repo, "hermes-skill-sync-conflict.json")
                marker.write_text(json.dumps({
                    "at": datetime.now(tz=timezone.utc).isoformat(),
                    "repo": str(repo),
                    "note": "rebase conflict aborted; resolve in a session, both lessons must land",
                    "stderr": (rebase.stderr or rebase.stdout).strip()[:1000],
                    "abort_error": aborted.stderr.strip()[:500],
                }, indent=2), encoding="utf-8")
                notes.append(f"conflict: rebase aborted; marker written to {marker}")
                return 11, notes
            notes.append(f"{repo.name}: rebase failed without an active conflict: {(rebase.stderr or rebase.stdout).strip()[:300]}")
            return 12, notes

    push = git(repo, "push", "--quiet")
    if push.returncode != 0:
        notes.append(f"{repo.name}: push failed; local commit retained for retry: {(push.stderr or push.stdout).strip()[:300]}")
        return 12, notes

    notes.append("pushed")
    marker = git_path(repo, "hermes-skill-sync-conflict.json")
    if marker.exists():
        marker.unlink()
        notes.append("cleared resolved conflict marker after successful push")
    return 0, notes


def pull_only(verbose: bool) -> tuple[int, list[str]]:
    notes: list[str] = []
    state = load_state()
    if not state:
        return 13, [f"not installed: {state_path()} missing"]
    failed = False
    for repo in repos_from_state():
        if not has_remote(repo):
            notes.append(f"{repo.name}: configured repository has no remote")
            failed = True
            continue
        allowed, reason = branch_policy(repo)
        if not allowed:
            notes.append(f"{repo.name}: {reason}")
            failed = True
            continue
        if git(repo, "status", "--porcelain").stdout.strip():
            notes.append(f"{repo.name}: local changes present — pull skipped")
            failed = True
            continue
        r = git(repo, "pull", "--ff-only", "--quiet")
        if r.returncode != 0:
            notes.append(f"{repo.name}: pull failed — left untouched: {(r.stderr or r.stdout).strip()[:300]}")
            failed = True
        elif verbose:
            notes.append(f"{repo.name}: up to date")
    return (12 if failed else 0), notes


def audit(verbose: bool) -> tuple[int, list[str]]:
    """Report-only: review commits since the last audit + a whole-repo defect scan."""
    notes: list[str] = []
    for repo in repos_from_state():
        marker = git_path(repo, AUDIT_MARKER)
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
        allowed, reason = branch_policy(repo)
        if not allowed:
            notes.append(f"WARN branch policy: {reason}")
            ok = False
    cursor, total = int(state.get(CURSOR_KEY) or 0), len(read_ledger())
    notes.append(f"ledger: {total} entries, cursor at {cursor}, {max(0, total - cursor)} pending")
    if cursor < 0 or cursor > total:
        notes.append("WARN cursor outside ledger bounds — repair state before publishing")
        ok = False
    wrapper = Path(str(state.get("wrapper", ""))).expanduser()
    if wrapper.is_file():
        text = wrapper.read_text(encoding="utf-8", errors="replace")
        target = ""
        interpreter = ""
        for line in text.splitlines():
            if line.startswith("exec "):
                try:
                    parts = shlex.split(line)
                except ValueError:
                    parts = []
                if len(parts) >= 3:
                    interpreter, target = parts[1], parts[2]
                break
        if target and Path(target).is_file() and interpreter and Path(interpreter).is_file():
            notes.append(f"wrapper: {wrapper} -> {interpreter} {target} (ok)")
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
    try:
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
            repos = repos_from_state()
            if not repos:
                return 13
            for repo in repos:
                repo_code, repo_notes = publish(repo, args.dry_run, args.verbose)
                notes += repo_notes
                code = max(code, repo_code)
            # A dry-run, gate finding, or operational failure never acknowledges ledger entries.
            if code == 0 and not args.dry_run:
                state = load_state()
                state[CURSOR_KEY] = len(read_ledger())
                state["last_run"] = datetime.now(tz=timezone.utc).isoformat()
                save_state(state)
            if not notes and args.verbose:
                notes = ["nothing to publish"]
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        code, notes = 12, [f"skill-repo-sync: {type(exc).__name__}: {exc}"]
    for line in ([] if args.hook and code == 0 and not args.verbose else notes):
        print(line, file=sys.stderr if args.hook else sys.stdout)
    return code


if __name__ == "__main__":
    sys.exit(main())
