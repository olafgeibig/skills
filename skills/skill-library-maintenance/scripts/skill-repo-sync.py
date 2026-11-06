#!/usr/bin/env python3
# skill-repo-sync — v2 "Stage & Curate" stage layer.
#
# SCRIPT_VERSION: 2.0.0
# Part of the skill-library-maintenance skill (shared repo). Install with
# scripts/install-skill-repo-sync.py; verify with `--selfcheck`.
#
# The staging layer runs on every installation. It bundles pending skill work
# into ONE commit on the installation's transport branch `machine/<name>` and
# pushes that branch only. It never writes `main`; consolidation onto main is
# the nightly curator's job (skill-repo-consolidate.py / agent cron on the
# consolidation host).
#
# Modes
#   --stage           (default) bundle ledger+worktree changes into one commit on
#                     machine/<name>, push; safe to re-run (idempotent by content)
#   --sync-from-main  session-start refresh: fetch; when origin/machine/<name> has
#                     been consumed by the curator (== origin/main, or origin/main
#                     is an ancestor) and the worktree is clean, reset the local
#                     branch to origin/main
#   --selfcheck       verify the local install (state, machine, branch policy, wrapper)
#   --version         print SCRIPT_VERSION
#   --dry-run         no state, index, commit, fetch, or push writes
#   --verbose         also report no-op runs
#   --machine NAME    override the machine name from the state file
#
# Exit codes: 0 ok/no-op · 12 other error · 13 not installed
#
# Design rules (spec: vault note draft-skill-repo-sync, "Stage & Curate"):
#   * the transport branch is `machine/<name>` — anything on main is refused
#   * the mutation ledger picks/attributes paths; the v1 before/after hash chain
#     is gone (it deadlocked against a moving HEAD: foreign commits retroactively
#     invalidated old entries and froze cursor + push for the whole repo)
#   * one bundled commit per stage run; this layer never uses force
#   * no provider/network calls beyond git itself
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_VERSION = "2.0.0"
STATE_NAME = "skill-repo-sync.json"
CURSOR_KEY = "ledger_cursor"  # index of the last ledger line staged into a commit

# Lines that must never enter a shared (generic) skill: instance pointers.
# Both home layouts are covered — Linux (`/home/<user>`) and macOS (`/Users/<user>`).
# A `~/` path is only an instance pointer outside the portable runtime directories
# every installation has: `~/.local`, `~/.cache`, `~/.config` and `~/.hermes`.
# Kept from v1: the consolidation layer reuses this list for its preflight.
INSTANCE_PATTERNS = (
    (r"/(?:home|Users)/[A-Za-z0-9_.-]+", "absolute home path"),
    (r"(?<![\w/])~/(?!~|\.(?:local|cache|config|hermes)\b)(?!\.hermes/skills)", "tilde path"),
    (r"\b(durin|boromir|BE18-C-0001G)\b", "machine name"),
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

    A hook runs unattended: a credential prompt or an interactive SSH key question would stall
    the tool round until the hook timeout. BatchMode + no terminal prompt turn those into a
    fast, reportable failure on Linux and macOS alike.
    """
    env = dict(os.environ)
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    env.setdefault("GIT_SSH_COMMAND", "ssh -oBatchMode=yes -oConnectTimeout=10")
    env.setdefault("GIT_ASKPASS", "/bin/true")
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                          check=check, timeout=120, env=env)


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
    for number, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON in mutation ledger {p} line {number}") from exc
        if isinstance(entry, dict):
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


def dirty_paths(repo: Path) -> tuple[set[str], set[str]]:
    """(modified paths, untracked paths) relative to the repo root."""
    modified = set(git(repo, "ls-files", "--modified", "--exclude-standard").stdout.splitlines())
    untracked = set(git(repo, "ls-files", "--others", "--exclude-standard").stdout.splitlines())
    return modified, untracked


def branch_policy(repo: Path, machine: str) -> tuple[bool, str]:
    branch = git(repo, "branch", "--show-current").stdout.strip()
    upstream = git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    upstream_name = upstream.stdout.strip() if upstream.returncode == 0 else "<none>"
    expected = f"machine/{machine}"
    if branch != expected:
        return False, (f"expected transport branch {expected}; found {branch or '<detached>'} — "
                       f"checkout {expected} first (the stage layer never writes 'main')")
    if upstream_name != f"origin/{expected}":
        return False, f"expected upstream origin/{expected}; found {upstream_name}"
    return True, ""


def git_path(repo: Path, name: str) -> Path:
    result = git(repo, "rev-parse", "--git-path", name)
    path = Path(result.stdout.strip())
    return path if path.is_absolute() else (repo / path)


def repository_preflight(repo: Path, machine: str) -> tuple[bool, str]:
    allowed, reason = branch_policy(repo, machine)
    if not allowed:
        return False, reason
    if git(repo, "diff", "--cached", "--quiet").returncode != 0:
        return False, "pre-existing staged changes; the stage layer refuses to run with a dirty index"
    for marker in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply"):
        if git_path(repo, marker).exists():
            return False, f"Git operation already in progress ({marker})"
    return True, ""


# --- stage ----------------------------------------------------------------------------------------

def stage(repo: Path, machine: str, dry_run: bool, verbose: bool) -> tuple[int, list[str]]:
    """Bundle ledger + worktree changes into one commit on machine/<name>, then push."""
    notes: list[str] = []
    state = load_state()
    allowed, reason = repository_preflight(repo, machine)
    if not allowed:
        return 12, [f"machine/{machine}: {reason}"]

    entries = read_ledger()
    cursor = int(state.get(CURSOR_KEY) or 0)
    if cursor < 0 or cursor > len(entries):
        # Self-healing, not fatal: the cursor is a performance shortcut, content comes
        # from the worktree anyway. Treat an out-of-bounds cursor as "see all pending".
        cursor = max(0, min(cursor, len(entries)))
        notes.append(f"machine/{machine}: ledger cursor out of bounds; re-detected from content")

    ledger_paths: set[str] = set()
    ledger_ids: list[str] = []
    for entry in entries[cursor:]:
        for p in entry_paths(entry):
            try:
                rel = str(p.expanduser().resolve().relative_to(repo.resolve()))
            except (ValueError, OSError):
                continue
            ledger_paths.add(rel)
        if entry.get("id"):
            ledger_ids.append(str(entry["id"]))

    modified, untracked = dirty_paths(repo)
    manual_paths = sorted((modified | untracked) - ledger_paths)
    paths = sorted(ledger_paths | modified | untracked)

    if not paths:
        if verbose:
            notes.append(f"machine/{machine}: nothing to stage")
        return 0, notes

    if dry_run:
        notes.append(f"[dry-run] would stage {len(paths)} path(s) into one commit on machine/{machine}")
        if manual_paths:
            shown = ", ".join(manual_paths[:10]) + (f" … +{len(manual_paths) - 10}" if len(manual_paths) > 10 else "")
            notes.append(f"  manual (no ledger entry): {shown}")
        return 0, notes

    staged = git(repo, "add", "--", *paths)
    if staged.returncode != 0:
        return 12, [f"machine/{machine}: git add failed: {staged.stderr.strip()[:200]}"]
    if not git(repo, "diff", "--cached", "--name-only").stdout.strip():
        # Content is already committed (a previous run's push failed and was retried):
        # nothing new to build, retry the push only. The cursor advances on push success.
        notes.append(f"machine/{machine}: nothing new to commit; retrying push of existing commits")
        return push_stage(repo, machine, notes, state=state, verbose=verbose)

    if git(repo, "diff", "--cached", "--check").returncode != 0:
        return 12, [f"machine/{machine}: staged whitespace check failed"]

    stamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    message_lines = [f"stage: skill updates on {machine} ({stamp})", ""]
    if ledger_ids:
        message_lines.append("Ledger-Entries: " + ", ".join(ledger_ids))
    if manual_paths:
        shown = ", ".join(manual_paths[:20]) + (f"\n… +{len(manual_paths) - 20} more manual paths"
                                                if len(manual_paths) > 20 else "")
        message_lines.append("Manual additions (no ledger entry): " + shown)
    message_lines.append("Consolidating this content into main is the curator's job; "
                         "this commit only secures the work.")

    commit = git(repo, "commit", "-q", "-m", "\n".join(message_lines), "--", *paths)
    if commit.returncode != 0:
        return 12, [f"machine/{machine}: git commit failed: {(commit.stderr or commit.stdout).strip()[:200]}"]
    notes.append(f"machine/{machine}: staged {len(paths)} path(s) "
                 f"({len(ledger_ids)} ledger entries, {len(manual_paths)} manual)")

    return push_stage(repo, machine, notes, state=state, verbose=verbose)


def push_stage(repo: Path, machine: str, notes: list[str], state: dict,
               verbose: bool) -> tuple[int, list[str]]:
    push = git(repo, "push", "origin", f"HEAD:refs/heads/machine/{machine}")
    if push.returncode != 0:
        notes.append(f"machine/{machine}: push failed — commit retained for retry: "
                     f"{(push.stderr or push.stdout).strip()[:300]}")
        # The cursor deliberately stays: the next stage run re-detects the same content,
        # finds nothing new to add, and retries the push.
        return 12, notes
    notes.append(f"machine/{machine}: pushed")
    state[CURSOR_KEY] = len(read_ledger())
    state["last_stage_run"] = datetime.now(tz=timezone.utc).isoformat()
    save_state(state)
    return 0, notes


# --- refresh --------------------------------------------------------------------------------------

def sync_from_main(repo: Path, machine: str, dry_run: bool, verbose: bool) -> tuple[int, list[str]]:
    """Session-start refresh: fetch; when the branch was consumed by the curator, reset to origin/main."""
    notes: list[str] = []
    allowed, reason = branch_policy(repo, machine)
    if not allowed:
        return 12, [f"machine/{machine}: {reason}"]

    fetch = git(repo, "fetch", "origin", "--quiet")
    if fetch.returncode != 0:
        return 12, [f"machine/{machine}: fetch failed: {(fetch.stderr or fetch.stdout).strip()[:300]}"]

    origin_branch = git(repo, "rev-parse", "--verify", "--quiet",
                        f"refs/remotes/origin/machine/{machine}").stdout.strip()
    if not origin_branch:
        return 12, [f"machine/{machine}: origin branch missing on remote"]

    if git(repo, "status", "--porcelain").stdout.strip():
        if verbose:
            notes.append(f"machine/{machine}: local changes present — sync skipped "
                         "(content rides the next stage run)")
        return 0, notes

    origin_main = git(repo, "rev-parse", "--verify", "refs/remotes/origin/main").stdout.strip()
    local_branch = git(repo, "rev-parse", "HEAD").stdout.strip()

    # Consumed = the remote transport branch carries nothing main lacks.
    origin_branch_is_ancestor_of_main = git(repo, "merge-base", "--is-ancestor",
                                            origin_branch, origin_main).returncode == 0
    if not origin_branch_is_ancestor_of_main:
        if verbose:
            notes.append("machine/{0}: branch holds unconsolidated work — no reset".format(machine))
        return 0, notes

    if origin_main == local_branch:
        if verbose:
            notes.append(f"machine/{machine}: already at origin/main")
        return 0, notes

    if dry_run:
        notes.append(f"[dry-run] would reset local machine/{machine} to origin/main ({origin_main[:12]})")
        return 0, notes

    reset = git(repo, "reset", "--hard", origin_main)
    if reset.returncode != 0:
        return 12, [f"machine/{machine}: reset failed: {reset.stderr.strip()[:300]}"]
    notes.append(f"machine/{machine}: consumed by the curator — reset to origin/main ({origin_main[:12]})")
    return 0, notes


# --- selfcheck ------------------------------------------------------------------------------------

def selfcheck(verbose: bool, machine_override: str | None) -> tuple[int, list[str]]:
    notes: list[str] = []
    state = load_state()
    if not state:
        return 13, [f"not installed: {state_path()} missing"]
    notes.append(f"script version: {SCRIPT_VERSION} (state recorded {state.get('version', '?')})")
    machine = (machine_override or "").strip() or str(state.get("machine") or "").strip()
    if not machine:
        return 12, ["no machine name in state — reinstall with install-skill-repo-sync.py --machine <name>"]
    notes.append(f"machine: {machine}")
    ok = True
    for repo in repos_from_state():
        remote = has_remote(repo)
        allowed, br_reason = branch_policy(repo, machine)
        head = git(repo, "rev-parse", "--short", "HEAD").stdout.strip()
        notes.append(f"repo {repo}: remote={'yes' if remote else 'NO'} head={head}")
        if not remote:
            ok = False
        if not allowed:
            notes.append(f"WARN branch policy: {br_reason}")
            ok = False
    cursor, total = int(state.get(CURSOR_KEY) or 0), len(read_ledger())
    notes.append(f"ledger: {total} entries, stage cursor at {cursor}, {max(0, total - cursor)} pending")
    return (0 if ok else 12), notes


def main() -> int:
    ap = argparse.ArgumentParser(description="stage-layer sync for the shared skill repo (v2)")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--stage", action="store_true",
                      help="bundle pending work into one commit on machine/<name> and push (default)")
    mode.add_argument("--sync-from-main", action="store_true",
                      help="fetch; reset to origin/main when the curator consumed the branch")
    mode.add_argument("--selfcheck", action="store_true", help="verify the install")
    mode.add_argument("--version", action="store_true", help="print the script version")
    ap.add_argument("--machine", default=None, help="machine name override (default: from state file)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--hook", action="store_true",
                    help="hook mode: silent on success, failures on stderr (keeps hook stdout clean)")
    args = ap.parse_args()

    if args.version:
        print(f"skill-repo-sync {SCRIPT_VERSION}")
        return 0

    try:
        if args.selfcheck:
            code, notes = selfcheck(args.verbose, args.machine)
        else:
            if not load_state() or not repos_from_state():
                print(f"skill-repo-sync: not installed ({state_path()} missing) — run install-skill-repo-sync.py")
                return 13
            state = load_state()
            machine = (args.machine or "").strip() or str(state.get("machine") or "").strip()
            if not machine:
                print("skill-repo-sync: no machine name in state — reinstall with "
                      "install-skill-repo-sync.py --machine <name>")
                return 12
            code, notes = 0, []
            for repo in repos_from_state():
                if args.sync_from_main:
                    repo_code, repo_notes = sync_from_main(repo, machine, args.dry_run, args.verbose)
                else:
                    repo_code, repo_notes = stage(repo, machine, args.dry_run, args.verbose)
                notes += repo_notes
                code = max(code, repo_code)
            if len(notes) < len(repos_from_state()) and not any(n for n in notes) and args.verbose:
                notes = ["nothing to do"]
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        code, notes = 12, [f"skill-repo-sync: {type(exc).__name__}: {exc}"]
    for line in ([] if args.hook and code == 0 and not args.verbose else notes):
        print(line, file=sys.stderr if args.hook else sys.stdout)
    return code


if __name__ == "__main__":
    sys.exit(main())
