#!/usr/bin/env python3
# skill-repo-sync — v3 "Stage & Integrate" contributor engine (staging, refresh, integration).
#
# SCRIPT_VERSION: 3.0.0
# Part of the skill-library-maintenance skill (shared repo). Install with
# scripts/install-skill-repo-sync.py; verify with `--selfcheck`.
#
# The contributor engine runs on every installation. It bundles pending skill work
# into ONE commit on the installation's transport branch `machine/<name>`, refreshes
# that branch by merge ancestry, and integrates exactly the reviewed commit. Stage
# secures the work locally; the pre-integration run owns the push — what lands on
# a transport branch is always pre-integrated. It never writes `main`; integration
# onto main is the maintainer's job (skill-repo-maintain.py / agent cron on the
# integration host).
#
# Modes
#   --stage           (default) bundle ledger+worktree changes into one commit on
#                     machine/<name> — local only, the push is held for the
#                     pre-integration run; safe to re-run (idempotent by content).
#                     Only the transport branch is a sweep target: a `refactor/*`
#                     branch is excluded untouched, `main` is refused (exit 12,
#                     clean or dirty). A missing never-tracked ledger path is
#                     recorded as skipped and does not block valid work; a
#                     whitespace/commit failure undoes only this run's index
#                     entries, so fixing the cause and rerunning succeeds. The
#                     short staging operation runs under the contributor lock.
#   --sync-from-main  session-start refresh by ancestry: fetch; fast-forward when
#                     HEAD is an ancestor of integrated main and the worktree is
#                     clean; do nothing when main is an ancestor of HEAD; on
#                     divergence report "pre-integration merge required" and
#                     change no file or index. Never reset, rebase or autostash.
#   --screen-history SHA  mechanical screen of the ENTIRE unpublished range
#                     `SHA ^ <remote source tip>`: forbidden file names and
#                     suspected credential patterns, reported as path/category
#                     only (never the matched value). Exit 10 on findings.
#   --record-history-review SHA --history-review FILE
#                     persist the agent's semantic profile-scope review, bound to
#                     the exact full SHA and its exact commit set (digest over the
#                     review fields). Required before --push-reviewed.
#   --push-reviewed SHA   under the contributor lock: re-run the history screen,
#                     require the matching history review, require SHA to be HEAD
#                     or an ancestor of HEAD, push `<SHA>:refs/heads/machine/<name>`
#                     (NOT the branch name), verify the remote ref with ls-remote
#                     and record `last_pushed_tip` as metadata only. A commit made
#                     after the review (T2) stays local and unpublished.
#   --lock / --unlock hold/release the contributor lock across a deliberate
#                     pre-integration merge; never hold it for a whole session.
#   --selfcheck       verify the local install (state, machine, branch policy, wrapper,
#                     contributor lock, last integrated tip)
#   --version         print SCRIPT_VERSION
#   --dry-run         no state, index, commit, fetch, push or lock-file writes
#   --verbose         also report no-op runs
#   --machine NAME    override the machine name from the state file
#
# Exit codes: 0 ok/no-op · 10 history-screen findings · 12 policy refusal or error · 13 not installed
#
# Design rules (design record: "Stage & Integrate", decisions D1/D2):
#   * the transport branch is `machine/<name>` — anything on main is refused
#   * the mutation ledger picks/attributes paths; the v1 before/after hash chain
#     is gone (it deadlocked against a moving HEAD: foreign commits retroactively
#     invalidated old entries and froze cursor + push for the whole repo)
#   * one bundled commit per stage run; this layer never uses force
#   * stage never pushes (push-gate): the commit stays local until the
#     pre-integration run cleans and pushes it
#   * refresh and integration use merge ancestry only; there is no reset, rebase,
#     autostash or "last_pushed_tip means consumed" shortcut anywhere
#   * staging, refresh and the pre-integration push/merge share one contributor
#     lock at the contributor repo's Git common dir (separate from the maintainer lock)
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
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

SCRIPT_VERSION = "3.0.0"
STATE_NAME = "skill-repo-sync.json"
CURSOR_KEY = "ledger_cursor"  # index of the last ledger line staged into a commit
# Deliberate development branches are never sweep targets: a refactor worktree holds
# unfinished tracked edits by design, and the sweep must not turn them into transport work.
REFACTOR_BRANCH_PREFIX = "refactor/"

# Lines that must never enter a shared (generic) skill: instance pointers.
# Both home layouts are covered — Linux (`/home/<user>`) and macOS (`/Users/<user>`).
# A `~/` path is only an instance pointer outside the portable runtime directories every
# installation has: `~/.local`, `~/.cache`, `~/.config` and `~/.hermes` resolve everywhere.
_HERE = Path(__file__).resolve().parent
_CORE_MODULE = None


def workflow_core():
    """Import the shared v3 core beside this engine (no CLI, no import side effects).

    The contributor lock and the history-exposure screen live in the shared core so the
    maintainer and the contributor cannot drift into two different definitions.
    """
    global _CORE_MODULE
    if _CORE_MODULE is None:
        candidates = [_HERE / "skill_repo_workflow.py"]
        override = os.environ.get("SKILL_REPO_WORKFLOW_CORE", "").strip()
        if override:
            candidates.append(Path(override).expanduser())
        path = next((candidate for candidate in candidates if candidate.is_file()), None)
        if path is None:
            raise RuntimeError("shared workflow core not found beside the engine "
                               "(skill_repo_workflow.py)")
        spec = spec_from_file_location("skill_repo_workflow_core", path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load the shared workflow core at {path}")
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        core_version = getattr(module, "CORE_VERSION", "<missing>")
        if core_version != SCRIPT_VERSION:
            raise RuntimeError(
                f"mixed installation: engine SCRIPT_VERSION {SCRIPT_VERSION} does not match "
                f"core CORE_VERSION {core_version}; reinstall the engine/core pair together"
            )
        _CORE_MODULE = module
    return _CORE_MODULE


def _release_contributor_lock(repo: Path, token: str, notes: list[str] | None = None) -> None:
    """Release our own lock; a release failure is reported but never masks the result."""
    try:
        workflow_core().release_contributor_lock(repo, token)
    except (OSError, RuntimeError) as exc:
        message = f"contributor lock release failed: {exc}"
        if notes is None:
            print(f"skill-repo-sync: {message}", file=sys.stderr)
        else:
            notes.append(message)


INSTANCE_PATTERNS = (
    (r"/(?:home|Users)/[A-Za-z0-9_.-]+", "absolute home path"),
    (r"(?<![\w/])~/(?!\.(?:local|cache|config|hermes)\b)(?!\.hermes/skills)", "tilde path"),
    (r"\bakademeia\b", "vault name"),
    (r"\b(durin|boromir)\b", "machine name"),
    (r"\bBosch\b", "employer name"),
    (r"\b20\d{2}-\d{2}-\d{2}\b", "date"),
    (r"\b20\d{3}_\d{6}_[0-9a-f]{6}\b", "session id"),
)
LINK_RE = re.compile(r"\]\(([^)#]+?)(?:#[^)]*)?\)")
REF_RE = re.compile(r"`?(references/[A-Za-z0-9_.-]+\.md)`?")


def _norm_line(line: str) -> str:
    s = re.sub(r"\s+", " ", line.strip().lower())
    return s.rstrip(".:").replace("*", "").replace("`", "")


def added_pairs_from_diff(diff_text: str) -> list[tuple[str, str]]:
    """(file, added line) pairs from a unified diff — the stage scan's input (v2.1)."""
    out: list[tuple[str, str]] = []
    current = ""
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith("+") and not line.startswith("+++ b/"):
            out.append((current, line[1:]))
    return out


def pre_integration_scan(repo: Path, added: list[tuple[str, str]]) -> list[dict]:
    """Vorbereitung fuer die Konsolidierung: welche Additionen brauchen Augen?
    Instanz-Pointer (Veto) und Duplikat-Kandidaten (Zeile >= 8 Woerter existiert
    sinngemaess schon in origin/main:<file> oder im Branch-Verlauf/HEAD). Der Scan ist
    das SICHERHEITSNETZ (Marker), nicht der Router — markieren statt verwerfen."""
    findings: list[dict] = []
    seen: dict[str, set[str]] = {}
    for f, text in added:
        if not text.strip():
            continue
        for pattern, label in INSTANCE_PATTERNS:
            if re.search(pattern, text):
                findings.append({"file": f, "kind": "instance-pointer", "detail": label,
                                 "line": text.strip()[:160]})
        if len(text.split()) < 8:
            continue
        if f not in seen:
            lines: set[str] = set()
            for rev in ("origin/main", "HEAD"):
                out = git(repo, "show", f"{rev}:{f}")
                if out.returncode == 0:
                    lines |= {_norm_line(l) for l in out.stdout.splitlines() if l.strip()}
            seen[f] = lines
        if _norm_line(text) in seen[f]:
            findings.append({"file": f, "kind": "duplicate-candidate",
                             "detail": "line already in origin/main or HEAD",
                             "line": text.strip()[:160]})
    return findings


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
    """(modified paths, untracked paths) relative to the repo root — NUL-separated, exact bytes."""
    modified = _nul_paths(git(repo, "ls-files", "-z", "--modified", "--exclude-standard").stdout)
    untracked = _nul_paths(git(repo, "ls-files", "-z", "--others", "--exclude-standard").stdout)
    return modified, untracked


def _nul_paths(out: str) -> set[str]:
    """Path set from a NUL-separated git listing (no shell, no quoting, no newline splitting)."""
    return {p for p in out.split("\0") if p}


def tracked_paths(repo: Path) -> set[str]:
    """Every path currently in the index — a deleted tracked file is still listed by Git."""
    return _nul_paths(git(repo, "ls-files", "-z").stdout)


def staged_paths(repo: Path) -> set[str]:
    return _nul_paths(git(repo, "diff", "--cached", "--name-only", "-z").stdout)


def rollback_staged(repo: Path, paths: list[str]) -> None:
    """Undo only the index entries this invocation added; worktree bytes are never touched.

    The stage layer refuses a pre-existing dirty index, so every entry it is about to undo
    belongs to this run. Path-scoped `restore --staged -- <paths>` restores those index
    entries from HEAD without editing worktree content, keeping the failure retryable.
    """
    if paths:
        git(repo, "restore", "--staged", "--", *paths)


def branch_name(repo: Path) -> str:
    return git(repo, "branch", "--show-current").stdout.strip()


def is_refactor_branch(branch: str) -> bool:
    return branch == "refactor" or branch.startswith(REFACTOR_BRANCH_PREFIX)


def main_branch_refusal(machine: str, operation: str) -> tuple[int, list[str]]:
    activity = "staging" if operation == "stage" else operation
    return 12, [f"machine/{machine}: branch policy refuses main — expected machine/{machine}; "
                f"{operation} never touches main (a clean main is not healthy transport {activity}, "
                f"a dirty one is a decision)"]


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

def write_stage_report(findings: list[dict], skipped: list[dict]) -> None:
    """Report what this successful staging attempt scanned and which ledger paths it skipped."""
    report = {"at": datetime.now(tz=timezone.utc).isoformat(),
              "needs_pre_integration": len(findings),
              "findings": findings,
              "skipped_ledger_paths": skipped}
    (state_path().parent / "stage-report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")


def previous_stage_findings() -> list[dict]:
    """Findings of the last report, kept when an attempt secures no new content."""
    report_file = state_path().parent / "stage-report.json"
    if not report_file.is_file():
        return []
    try:
        return list(json.loads(report_file.read_text(encoding="utf-8")).get("findings") or [])
    except (OSError, json.JSONDecodeError, AttributeError):
        return []


def stage(repo: Path, machine: str, dry_run: bool, verbose: bool) -> tuple[int, list[str]]:
    """Bundle ledger + worktree changes into one commit on machine/<name>.
    Stage secures the work locally; the pre-integration run owns the push.

    Only a registered transport checkout is a sweep target: a deliberate `refactor/*` branch is
    excluded without touching it, and `main` is refused as a branch-policy violation even when
    clean (a clean main is the maintainer's state, never healthy transport staging).

    The commit is a short contributor operation and runs under the contributor lock; a
    pre-integration merge/push holding that lock refuses staging before any index, worktree
    or state write.
    """
    notes: list[str] = []
    state = load_state()
    branch = branch_name(repo)
    if is_refactor_branch(branch):
        notes.append(f"machine/{machine}: {branch} is a refactor branch: excluded from sweep — "
                     f"stage only secures machine/{machine} (no branch checkout performed)")
        return 0, notes
    if branch == "main":
        return main_branch_refusal(machine, "stage")
    allowed, reason = repository_preflight(repo, machine)
    if not allowed:
        return 12, [f"machine/{machine}: {reason}"]

    # Snapshot the ledger ONCE: the cursor may only acknowledge entries observed for this attempt,
    # so a row another writer appends during the commit stays pending for the next sweep.
    entries = read_ledger()
    snapshot_len = len(entries)
    cursor = int(state.get(CURSOR_KEY) or 0)
    if cursor < 0 or cursor > snapshot_len:
        # Self-healing, not fatal: the cursor is a performance shortcut, content comes
        # from the worktree anyway. Treat an out-of-bounds cursor as "see all pending".
        cursor = max(0, min(cursor, snapshot_len))
        notes.append(f"machine/{machine}: ledger cursor out of bounds; re-detected from content")

    tracked = tracked_paths(repo)
    ledger_paths: set[str] = set()
    ledger_ids: list[str] = []
    skipped_by_path: dict[str, dict] = {}
    for entry in entries[cursor:]:
        for p in entry_paths(entry):
            try:
                rel = str(p.expanduser().resolve().relative_to(repo.resolve()))
            except (ValueError, OSError):
                continue
            # A missing path is only stale when Git never tracked it; a tracked deletion is
            # real work and stays in the staging set.
            if p.expanduser().exists() or rel in tracked:
                ledger_paths.add(rel)
            else:
                skipped_by_path.setdefault(rel, {
                    "path": rel,
                    "entry": str(entry.get("id") or ""),
                    "reason": "missing and never tracked — stale ledger path skipped",
                })
        if entry.get("id"):
            ledger_ids.append(str(entry["id"]))
    skipped = sorted(skipped_by_path.values(), key=lambda s: s["path"])

    modified, untracked = dirty_paths(repo)
    manual_paths = sorted((modified | untracked) - ledger_paths)
    paths = sorted(ledger_paths | modified | untracked)

    if not paths:
        if not skipped:
            if verbose:
                notes.append(f"machine/{machine}: nothing to stage")
            return 0, notes
        if dry_run:
            notes.append(f"[dry-run] would record {len(skipped)} stale ledger path(s) as skipped "
                         f"and advance the cursor to {snapshot_len}")
            return 0, notes
    elif dry_run:
        notes.append(f"[dry-run] would stage {len(paths)} path(s) into one commit on machine/{machine}")
        if manual_paths:
            shown = ", ".join(manual_paths[:10]) + (f" … +{len(manual_paths) - 10}" if len(manual_paths) > 10 else "")
            notes.append(f"  manual (no ledger entry): {shown}")
        for item in skipped:
            notes.append(f"[dry-run] would skip stale ledger path: {item['path']}")
        return 0, notes

    # Short staging operation: one owner-token lock at the contributor repo's Git common dir.
    # It is never held for a chat session, and a held pre-integration lock refuses here
    # before anything is written.
    try:
        token = workflow_core().acquire_contributor_lock(repo)
    except (OSError, RuntimeError) as exc:
        return 12, [f"machine/{machine}: {exc}"]
    try:
        return _stage_apply(repo, machine, paths, skipped, ledger_ids, manual_paths,
                            snapshot_len, state, notes)
    finally:
        _release_contributor_lock(repo, token, notes)


def _stage_apply(
    repo: Path,
    machine: str,
    paths: list[str],
    skipped: list[dict],
    ledger_ids: list[str],
    manual_paths: list[str],
    snapshot_len: int,
    state: dict,
    notes: list[str],
) -> tuple[int, list[str]]:
    """The index/commit/state part of staging; the caller holds the contributor lock."""
    if not paths:
        # Explicit recorded skipping: a stale entry must not block the cursor forever. This
        # attempt secures no new content, so an existing report's findings stay authoritative
        # for the already-committed content it describes.
        write_stage_report(previous_stage_findings(), skipped)
        state[CURSOR_KEY] = snapshot_len
        state["last_stage_run"] = datetime.now(tz=timezone.utc).isoformat()
        save_state(state)
        notes.append(f"machine/{machine}: skipped {len(skipped)} stale ledger path(s); "
                     f"nothing to stage — cursor advanced to {snapshot_len}")
        return 0, notes

    staged = git(repo, "add", "--", *paths)
    if staged.returncode != 0:
        rollback_staged(repo, paths)
        return 12, [f"machine/{machine}: git add failed: {staged.stderr.strip()[:200]} "
                    f"(index restored, worktree bytes untouched)"]
    if not staged_paths(repo):
        # Content is already committed (e.g. a manual commit got there first):
        # nothing new to build. Stage never pushes, so there is no push to retry.
        notes.append(f"machine/{machine}: nothing new to commit — content already secured locally")
        if skipped:
            write_stage_report(previous_stage_findings(), skipped)
        state[CURSOR_KEY] = snapshot_len
        state["last_stage_run"] = datetime.now(tz=timezone.utc).isoformat()
        save_state(state)
        return 0, notes

    if git(repo, "diff", "--cached", "--check").returncode != 0:
        rollback_staged(repo, paths)
        return 12, [f"machine/{machine}: staged whitespace check failed — index restored to HEAD, "
                    f"worktree bytes untouched; fix the whitespace and rerun"]

    # v2.1 staging pre-integration scan (R3): every staged addition against origin/main/HEAD —
    # instance pointers and duplicate candidates. Safety net: mark, never route.
    findings = pre_integration_scan(repo, added_pairs_from_diff(git(repo, "diff", "--cached").stdout))

    stamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    message_lines = [f"stage: skill updates on {machine} ({stamp})", ""]
    if ledger_ids:
        message_lines.append("Ledger-Entries: " + ", ".join(ledger_ids))
    if manual_paths:
        shown = ", ".join(manual_paths[:20]) + (f"\n… +{len(manual_paths) - 20} more manual paths"
                                                if len(manual_paths) > 20 else "")
        message_lines.append("Manual additions (no ledger entry): " + shown)
    if skipped:
        shown = ", ".join(item["path"] for item in skipped[:20])
        message_lines.append("Skipped stale ledger paths: " + shown
                             + (f" … +{len(skipped) - 20} more" if len(skipped) > 20 else ""))
    message_lines.append("Consolidating this content into main is the maintainer's job; "
                         "this commit only secures the work.")
    if findings:
        message_lines.append(f"Needs-pre-integration: {len(findings)}")

    commit = git(repo, "commit", "-q", "-m", "\n".join(message_lines), "--", *paths)
    if commit.returncode != 0:
        rollback_staged(repo, paths)
        return 12, [f"machine/{machine}: git commit failed: {(commit.stderr or commit.stdout).strip()[:200]} "
                    f"(index restored, worktree bytes untouched)"]
    notes.append(f"machine/{machine}: staged {len(paths)} path(s) "
                 f"({len(ledger_ids)} ledger entries, {len(manual_paths)} manual) — "
                 f"holding push for the pre-integration run")
    write_stage_report(findings, skipped)
    # Push-gate: stage never pushes. The cursor advances through the snapshot read before
    # staging — the pre-integration run owns the push; no reset is ever a recovery path.
    state[CURSOR_KEY] = snapshot_len
    state["last_stage_run"] = datetime.now(tz=timezone.utc).isoformat()
    save_state(state)
    return 0, notes


# --- refresh --------------------------------------------------------------------------------------

def sync_from_main(repo: Path, machine: str, dry_run: bool, verbose: bool) -> tuple[int, list[str]]:
    """Session-start refresh by ancestry: fast-forward, no-op, or defer to pre-integration.

    * HEAD is an ancestor of integrated main and the worktree is clean -> ``git merge --ff-only``.
    * integrated main is an ancestor of HEAD -> nothing to integrate (no echo merge commit).
    * the two sides diverged -> report "pre-integration merge required" and change nothing.

    This path never resets, rebases or autostashes contributor work, and never uses
    `last_pushed_tip` counts to decide that rewritten history is safe. A dirty worktree is
    never integrated; a merge/rebase already in progress is refused. Divergence exits 12 so
    the session hook actually reports it — it is a deliberate deferral, not an LLM wake-up.
    Non-dry refresh holds the contributor lock across preflight, fetch and merge;
    every main checkout refuses before any mutation, even when clean.
    """
    notes: list[str] = []
    if branch_name(repo) == "main":
        return main_branch_refusal(machine, "refresh")
    if dry_run:
        return _sync_from_main_apply(repo, machine, dry_run, verbose, notes)
    try:
        token = workflow_core().acquire_contributor_lock(repo)
    except (OSError, RuntimeError) as exc:
        return 12, [f"machine/{machine}: {exc}"]
    try:
        code, notes = _sync_from_main_apply(repo, machine, dry_run, verbose, notes)
        return code, notes
    finally:
        _release_contributor_lock(repo, token, notes)


def _sync_from_main_apply(repo: Path, machine: str, dry_run: bool, verbose: bool,
                          notes: list[str]) -> tuple[int, list[str]]:
    """Preflight and refresh under the contributor lock, or read-only cached dry-run."""
    # v2.1 session-start warning (R3): the local cleanup trigger for the last stage scan.
    report_path = state_path().parent / "stage-report.json"
    if report_path.is_file():
        try:
            rep = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            rep = {}
        if rep.get("needs_pre_integration"):
            notes.append(f"skills: {rep['needs_pre_integration']} addition(s) need pre-integration — "
                         "see stage-report.json (fix before staging again)")
    branch = git(repo, "branch", "--show-current").stdout.strip()
    if branch == "main":
        return main_branch_refusal(machine, "refresh")
    allowed, reason = branch_policy(repo, machine)
    if not allowed:
        return 12, [f"machine/{machine}: {reason}"]
    for marker in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply"):
        if git_path(repo, marker).exists():
            return 12, [f"machine/{machine}: Git operation already in progress ({marker}) — "
                        f"finish or abort it before refreshing"]

    if dry_run:
        origin_main = git(repo, "rev-parse", "--verify", "--quiet",
                          "refs/remotes/origin/main").stdout.strip()
        notes.append(f"[dry-run] evaluating ancestry against cached origin/main "
                     f"({origin_main[:12] or '(absent)'}) — no fetch")
    else:
        fetch = git(repo, "fetch", "origin", "--quiet")
        if fetch.returncode != 0:
            return 12, [f"machine/{machine}: fetch failed: "
                        f"{(fetch.stderr or fetch.stdout).strip()[:300]}"]
        origin_main = git(repo, "rev-parse", "--verify", "--quiet",
                          "refs/remotes/origin/main").stdout.strip()
    if not origin_main:
        return 12, [f"machine/{machine}: origin/main missing on remote — cannot decide ancestry"]
    head = git(repo, "rev-parse", "HEAD").stdout.strip()

    if head == origin_main:
        if verbose:
            notes.append(f"machine/{machine}: already at origin/main")
        return 0, notes

    if git(repo, "merge-base", "--is-ancestor", head, origin_main).returncode == 0:
        # Consumed by integrated main. Only integrating is fast-forward; local bytes are
        # never touched, so a dirty checkout defers the refresh instead of losing work.
        if git(repo, "status", "--porcelain").stdout.strip():
            if verbose:
                notes.append(f"machine/{machine}: local changes present — sync skipped "
                             "(content rides the next stage run)")
            return 0, notes
        if dry_run:
            notes.append(f"[dry-run] would fast-forward machine/{machine} to origin/main "
                         f"({origin_main[:12]})")
            return 0, notes
        merge = git(repo, "merge", "--ff-only", "--quiet", "origin/main")
        if merge.returncode != 0:
            return 12, [f"machine/{machine}: fast-forward failed: "
                        f"{(merge.stderr or merge.stdout).strip()[:300]} (nothing was reset)"]
        notes.append(f"machine/{machine}: fast-forwarded to integrated main ({origin_main[:12]}) — "
                     "no reset, no rebase")
        return 0, notes

    if git(repo, "merge-base", "--is-ancestor", origin_main, "HEAD").returncode == 0:
        if verbose:
            notes.append(f"machine/{machine}: origin/main is an ancestor of HEAD — nothing to integrate")
        return 0, notes

    return 12, [f"machine/{machine}: pre-integration merge required — local work and integrated "
                f"main ({origin_main[:12]}) diverged; nothing was reset. Merge deliberately "
                f"(git merge --no-ff origin/main), review, then push the reviewed tip "
                f"with --push-reviewed <sha>"]


# --- contributor integration: exact reviewed tip + history exposure gate ------------------------------

FULL_SHA_RE = re.compile(r"\A[0-9a-f]{40}(?:[0-9a-f]{24})?\Z")
HISTORY_REVIEWS_KEY = "history_reviews"
PRODUCER_LOCKS_KEY = "contributor_locks"
HISTORY_REVIEW_KEYS = frozenset({"schema", "tip", "scope", "summary", "commits"})
HISTORY_REVIEW_ROW_KEYS = frozenset({"sha", "classification", "reason"})


def source_ref(machine: str) -> str:
    return f"refs/heads/machine/{machine}"


def _utc_stamp() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _full_sha(value: str, label: str) -> str:
    value = (value or "").strip()
    if not FULL_SHA_RE.match(value):
        raise RuntimeError(f"{label} must be a full commit SHA, got {value!r}")
    return value


def _ls_remote(repo: Path, ref: str) -> str | None:
    """Checked read of one remote ref: exactly one line, the exact ref, a full SHA."""
    result = git(repo, "ls-remote", "--refs", "origin", ref)
    if result.returncode != 0:
        raise RuntimeError(f"git ls-remote failed for {ref}: "
                           f"{(result.stderr or result.stdout).strip()[:300]}")
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        return None
    if len(lines) != 1:
        raise RuntimeError(f"git ls-remote returned {len(lines)} rows for {ref}; refusing to guess")
    fields = lines[0].split()
    if len(fields) < 2 or fields[1] != ref:
        raise RuntimeError(f"git ls-remote answered a different ref than {ref}: {lines[0][:200]}")
    if not FULL_SHA_RE.match(fields[0]):
        raise RuntimeError(f"git ls-remote returned a non-SHA for {ref}: {lines[0][:100]}")
    return fields[0]


def _remote_source_tip(repo: Path, machine: str, dry_run: bool,
                       notes: list[str]) -> str | None:
    """Observed remote source tip (authoritative ls-remote), or cached refs in dry-run."""
    ref = source_ref(machine)
    if dry_run:
        cached = git(repo, "rev-parse", "--verify", "--quiet",
                     f"refs/remotes/origin/machine/{machine}").stdout.strip()
        notes.append(f"[dry-run] using cached {ref} = {cached or '(absent)'} (no fetch)")
        return cached or None
    fetch = git(repo, "fetch", "origin", "--prune", "--quiet")
    if fetch.returncode != 0:
        raise RuntimeError(f"fetch failed: {(fetch.stderr or fetch.stdout).strip()[:300]}")
    return _ls_remote(repo, ref)


def _select_repo(repos: list[Path], sha: str) -> Path:
    matches = []
    for repo in repos:
        probe = git(repo, "rev-parse", "--verify", "--quiet", f"{sha}^{{commit}}")
        if probe.returncode == 0 and probe.stdout.strip() == sha:
            matches.append(repo)
    if len(matches) != 1:
        raise RuntimeError(f"reviewed tip {sha} is not a commit in exactly one registered "
                           f"repo ({len(matches)} matches)")
    return matches[0]


def _require_local_tip(repo: Path, machine: str, sha: str) -> str:
    """The reviewed tip must be HEAD or an ancestor of it on this transport branch."""
    allowed, reason = branch_policy(repo, machine)
    if not allowed:
        raise RuntimeError(reason)
    tip = _full_sha(sha, "reviewed tip")
    probe = git(repo, "rev-parse", "--verify", "--quiet", f"{tip}^{{commit}}")
    if probe.returncode != 0:
        raise RuntimeError(f"reviewed tip {tip} is not a commit in this repository")
    if git(repo, "merge-base", "--is-ancestor", tip, "HEAD").returncode != 0:
        raise RuntimeError(f"reviewed tip {tip} is not HEAD or an ancestor of HEAD; "
                           f"refusing to integrate a commit outside this transport history")
    return tip


def _read_history_review_file(path: str) -> dict:
    try:
        value = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot read history review {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError("history review must be a JSON object")
    extra = set(value) - HISTORY_REVIEW_KEYS
    if extra:
        raise RuntimeError(f"unexpected history review fields: {', '.join(sorted(extra))}")
    return value


def _normalize_history_review(payload: dict, tip: str, commits: list[str]) -> list[dict]:
    """Validate the agent's review against the exact tip and commit range."""
    core = workflow_core()
    if payload.get("schema") != core.HISTORY_REVIEW_SCHEMA:
        raise RuntimeError(f"history review schema must be {core.HISTORY_REVIEW_SCHEMA}")
    if payload.get("tip") != tip:
        raise RuntimeError(f"history review is bound to {payload.get('tip')}, not {tip}")
    if payload.get("scope") != "shared-generic":
        raise RuntimeError("history review scope must be 'shared-generic' for a transport push")
    if not str(payload.get("summary") or "").strip():
        raise RuntimeError("history review summary must state the profile-scope conclusion")
    rows = payload.get("commits")
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("history review must classify every unpublished commit")
    seen: set[str] = set()
    normalized: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            raise RuntimeError("history review commit rows must be objects")
        extra = set(row) - HISTORY_REVIEW_ROW_KEYS
        if extra:
            raise RuntimeError(f"unexpected history review row fields: {', '.join(sorted(extra))}")
        sha = row.get("sha")
        if not isinstance(sha, str) or not FULL_SHA_RE.match(sha):
            raise RuntimeError(f"history review row has no full commit SHA: {sha!r}")
        if sha in seen:
            raise RuntimeError(f"history review lists commit {sha} twice")
        seen.add(sha)
        if row.get("classification") not in core.HISTORY_CLASSIFICATIONS:
            raise RuntimeError(f"history review classification {row.get('classification')!r} "
                               f"is not one of {', '.join(core.HISTORY_CLASSIFICATIONS)}")
        if not str(row.get("reason") or "").strip():
            raise RuntimeError(f"history review row {sha} needs a reason")
        normalized.append({"sha": sha, "classification": row["classification"],
                           "reason": row["reason"]})
    missing = [sha for sha in commits if sha not in seen]
    if missing:
        raise RuntimeError(f"history review omits unpublished commit {missing[0]} "
                           f"({len(missing)} of {len(commits)} uncovered)")
    extra_shas = sorted(seen - set(commits))
    if extra_shas:
        raise RuntimeError(f"history review names commit {extra_shas[0]} outside the "
                           f"unpublished range {commits[0]}..{tip}")
    order = {sha: index for index, sha in enumerate(commits)}
    return sorted(normalized, key=lambda row: order[row["sha"]])


def _history_review_problem(record: object, tip: str, commits: list[str]) -> str | None:
    """Why a stored review cannot authorise this tip ('' means it can)."""
    if not isinstance(record, dict):
        return (f"no history review recorded for this repository; review the unpublished "
                f"history of {tip} and record it before pushing")
    if record.get("tip") != tip:
        return (f"history review is bound to {record.get('tip')}, not the requested tip {tip}; "
                f"review this exact tip")
    core = workflow_core()
    payload = {"schema": record.get("schema"), "tip": record.get("tip"),
               "scope": record.get("scope"), "commits": record.get("commits")}
    try:
        digest = core.history_review_digest(payload)
    except (RuntimeError, ValueError, TypeError) as exc:
        return f"history review record is unreadable: {exc}"
    if digest != record.get("digest"):
        return "history review digest does not match the record content; re-record the review"
    recorded = {row.get("sha") for row in record.get("commits") or []}
    missing = [sha for sha in commits if sha not in recorded]
    if missing:
        return (f"history review does not cover unpublished commit {missing[0]} "
                f"({len(missing)} uncovered); review the full range again")
    return None


def _print_screen(notes: list[str], screen: dict, tip: str) -> None:
    base = screen.get("base_tip") or "(entire history)"
    notes.append(f"history screen: {tip} ^ {base}")
    notes.append(f"commits: {len(screen['commits'])}")
    for commit in screen["commits"]:
        notes.append(f"  {commit}")
    notes.append(f"findings: {len(screen['findings'])}")
    for finding in screen["findings"]:
        notes.append(f"  {finding['commit'][:12]} {finding['path']} "
                     f"[{finding['category']}] {finding['reason']}")


def screen_history(repo: Path, machine: str, sha: str, dry_run: bool,
                   verbose: bool) -> tuple[int, list[str]]:
    """Read-only mechanical screen of the whole unpublished source range."""
    notes: list[str] = []
    tip = _require_local_tip(repo, machine, sha)
    base = _remote_source_tip(repo, machine, dry_run, notes)
    screen = workflow_core().screen_source_history(repo, tip, base)
    _print_screen(notes, screen, tip)
    if screen["findings"]:
        notes.append("mechanical exposure found: this history cannot be shared as-is; "
                     "rewriting it (never force-pushing) is the only remedy")
        return 10, notes
    notes.append("no forbidden path or credential pattern in the unpublished range; "
                 "profile-scope judgement is still the reviewer's")
    return 0, notes


def record_history_review(repo: Path, machine: str, sha: str, review_path: str,
                          dry_run: bool, verbose: bool) -> tuple[int, list[str]]:
    """Persist the agent's semantic review bound to one exact tip and commit set."""
    notes: list[str] = []
    core = workflow_core()
    tip = _require_local_tip(repo, machine, sha)
    state = load_state()
    token = None
    if not dry_run:
        token = core.acquire_contributor_lock(repo)
    try:
        base = _remote_source_tip(repo, machine, dry_run, notes)
        screen = core.screen_source_history(repo, tip, base)
        payload = _read_history_review_file(review_path)
        rows = _normalize_history_review(payload, tip, screen["commits"])
        record = {
            "schema": core.HISTORY_REVIEW_SCHEMA,
            "tip": tip,
            "base_tip": screen["base_tip"],
            "scope": payload["scope"],
            "summary": payload["summary"],
            "commits": rows,
            "digest": core.history_review_digest({"schema": core.HISTORY_REVIEW_SCHEMA,
                                                  "tip": tip, "scope": payload["scope"],
                                                  "commits": rows}),
            "findings": screen["findings"],
            "reviewed_at": _utc_stamp(),
        }
        if dry_run:
            notes.append(f"[dry-run] would record a history review for {tip} covering "
                         f"{len(rows)} commit(s)")
            _print_screen(notes, screen, tip)
            return 0, notes
        state.setdefault(HISTORY_REVIEWS_KEY, {})[str(repo.resolve())] = record
        state["last_history_review_at"] = record["reviewed_at"]
        save_state(state)
        notes.append(f"history review recorded for {tip}: {len(rows)} commit(s), digest "
                     f"{record['digest'][:12]}")
        if screen["findings"]:
            notes.append(f"WARNING: {len(screen['findings'])} mechanical finding(s) remain; "
                         f"the push will refuse until the history is rewritten")
            _print_screen(notes, screen, tip)
        return 0, notes
    except (OSError, RuntimeError, ValueError) as exc:
        notes.append(f"history review not recorded: {exc}")
        return 12, notes
    finally:
        if token is not None:
            _release_contributor_lock(repo, token, notes)


def push_reviewed(repo: Path, machine: str, sha: str, dry_run: bool,
                  verbose: bool) -> tuple[int, list[str]]:
    """Push exactly one reviewed commit to the source ref, never the branch name.

    Refuses a tip outside local history, a non-fast-forward remote state, mechanical
    exposure findings in the whole unpublished range, or a missing/mismatched
    history review. A later local T2 stays local; `last_pushed_tip` is metadata only.
    """
    notes: list[str] = []
    core = workflow_core()
    ref = source_ref(machine)
    try:
        tip = _require_local_tip(repo, machine, sha)
    except RuntimeError as exc:
        return 12, [f"machine/{machine}: {exc}"]

    token = None
    if not dry_run:
        try:
            token = core.acquire_contributor_lock(repo)
        except (OSError, RuntimeError) as exc:
            return 12, [f"machine/{machine}: {exc}"]
    try:
        base = _remote_source_tip(repo, machine, dry_run, notes)
        if base == tip:
            notes.append(f"{tip} is already the integrated tip of {ref}; nothing to push")
            if not dry_run:
                _record_pushed_tip(repo, tip, ref)
            return 0, notes
        if base is not None and git(repo, "merge-base", "--is-ancestor", base, tip).returncode != 0:
            return 12, [f"machine/{machine}: remote {ref} is {base}, which is not an ancestor of "
                        f"reviewed tip {tip}; refusing a non-fast-forward integration (rewritten "
                        f"history is a separate incident, never repaired by force)"]
        screen = core.screen_source_history(repo, tip, base)
        if screen["findings"]:
            _print_screen(notes, screen, tip)
            notes.append(f"machine/{machine}: refusing to integrate {tip}: the unpublished history "
                         f"contains prohibited content even if the final tree does not "
                         f"(already-pushed exposure is a separate incident)")
            return 12, notes
        state = load_state()
        problem = _history_review_problem(
            (state.get(HISTORY_REVIEWS_KEY) or {}).get(str(repo.resolve())),
            tip, screen["commits"])
        if problem:
            return 12, [f"machine/{machine}: {problem}"]

        if dry_run:
            notes.append(f"[dry-run] would push {tip}:{ref} (remote now {base or '(absent)'})")
            return 0, notes

        pushed = git(repo, "push", "--no-verify", "origin", f"{tip}:{ref}")
        if pushed.returncode != 0:
            return 12, [f"machine/{machine}: push of {tip} to {ref} failed: "
                        f"{(pushed.stderr or pushed.stdout).strip()[:300]}"]
        observed = _ls_remote(repo, ref)
        if observed != tip:
            return 12, [f"machine/{machine}: push returned but {ref} reads "
                        f"{observed or '(absent)'}, not {tip}; refusing to record "
                        f"last_pushed_tip"]
        _record_pushed_tip(repo, tip, ref)
        notes.append(f"pushed {tip} to {ref} and confirmed it with ls-remote; "
                     f"last_pushed_tip recorded (metadata only — it never authorises a reset)")
        if git(repo, "rev-parse", "HEAD").stdout.strip() != tip:
            notes.append(f"note: local HEAD stays at {git(repo, 'rev-parse', 'HEAD').stdout.strip()[:12]}; "
                         f"later commits remain unpublished until reviewed")
        return 0, notes
    except (OSError, RuntimeError, ValueError) as exc:
        return 12, [f"machine/{machine}: {exc}"]
    finally:
        if token is not None:
            _release_contributor_lock(repo, token, notes)


def _record_pushed_tip(repo: Path, tip: str, ref: str) -> None:
    """Persist integration metadata; no code path reads it as permission to rewrite history."""
    state = load_state()
    state["last_pushed_tip"] = tip
    state["last_pushed_ref"] = ref
    state["last_pushed_at"] = _utc_stamp()
    state.setdefault("pushed_tips", {})[str(repo.resolve())] = tip
    save_state(state)


def lock_contributor(repos: list[Path], dry_run: bool, verbose: bool) -> tuple[int, list[str]]:
    """Hold the contributor lock across a deliberate pre-integration merge (then --unlock)."""
    notes: list[str] = []
    core = workflow_core()
    ordered = sorted(repos, key=lambda repo: str(repo.resolve()))
    if dry_run:
        for repo in ordered:
            notes.append(f"[dry-run] would lock {core.contributor_lock_path(repo)}")
        return 0, notes
    state = load_state()
    acquired: dict[str, str] = {}
    try:
        for repo in ordered:
            token = core.acquire_contributor_lock(repo)
            acquired[str(repo.resolve())] = token
            notes.append(f"contributor lock acquired: {core.contributor_lock_path(repo)} "
                         f"(release with --unlock; never hold it for a whole session)")
        state.setdefault(PRODUCER_LOCKS_KEY, {}).update(acquired)
        save_state(state)
        return 0, notes
    except (OSError, RuntimeError) as exc:
        for repo_text, token in acquired.items():
            try:
                core.release_contributor_lock(Path(repo_text), token)
            except (OSError, RuntimeError):
                pass
        return 12, [f"contributor lock not acquired: {exc}"]


def unlock_contributor(repos: list[Path], dry_run: bool, verbose: bool) -> tuple[int, list[str]]:
    """Release only locks this installation recorded an owner token for."""
    notes: list[str] = []
    core = workflow_core()
    state = load_state()
    locks = state.get(PRODUCER_LOCKS_KEY) or {}
    if not locks:
        return 12, ["no contributor lock token recorded — refusing to break an unowned lock"]
    if dry_run:
        for repo_text in sorted(locks):
            notes.append(f"[dry-run] would release {core.contributor_lock_path(Path(repo_text))}")
        return 0, notes
    for repo_text in sorted(list(locks)):
        core.release_contributor_lock(Path(repo_text), locks[repo_text])
        locks.pop(repo_text, None)
        state[PRODUCER_LOCKS_KEY] = locks
        save_state(state)
        notes.append(f"contributor lock released: {core.contributor_lock_path(Path(repo_text))}")
    state.pop(PRODUCER_LOCKS_KEY, None)
    save_state(state)
    return 0, notes


# --- selfcheck ------------------------------------------------------------------------------------

def _installer_version(state: dict) -> str:
    """Read the installer release next to this engine, or the version the
    installer recorded in state for an installed engine/core pair (the installer
    file itself is not copied into the runtime bin directory)."""
    path = _HERE / "install-skill-repo-sync.py"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        recorded = state.get("installer_version") or state.get("version") or ""
        return str(recorded).strip() or "not recorded"
    match = re.search(r'^INSTALLER_VERSION\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if match:
        return match.group(1)
    recorded = state.get("installer_version") or state.get("version") or ""
    return str(recorded).strip() or "not recorded"


def _maintainer_facts(notes: list[str]) -> bool:
    """Report observed maintainer-config/report-root facts on this installation.

    A contributor-only machine legitimately has no maintainer config; that is
    reported, not invented into a failure. An invalid config is a finding.
    """
    store = hermes_home() / "skill-repo-sync-v3"
    config_path = store / "maintainer.json"
    if not config_path.is_file():
        notes.append(f"maintainer config: absent ({config_path}) — contributor-only installation")
        return True
    try:
        config = workflow_core().load_maintainer_config(store)
    except (OSError, RuntimeError) as exc:
        notes.append(f"maintainer config: INVALID ({config_path}): {exc}")
        return False
    report = Path(config["report"]["vault_root"])
    notes.append(f"maintainer config: present ({config_path})")
    notes.append(f"  report root: {'present' if report.is_dir() else 'MISSING'} ({report})")
    return report.is_dir()


def selfcheck(verbose: bool, machine_override: str | None) -> tuple[int, list[str]]:
    notes: list[str] = []
    state = load_state()
    if not state:
        return 13, [f"not installed: {state_path()} missing"]
    notes.append(f"script version: {SCRIPT_VERSION} (state recorded {state.get('version', '?')})")
    try:
        core_version = workflow_core().CORE_VERSION
    except (OSError, RuntimeError) as exc:
        core_version = "missing"
        notes.append(f"core version: UNAVAILABLE ({exc})")
    else:
        notes.append(f"core version: {core_version}")
    installer_version = _installer_version(state)
    notes.append(f"installer version: {installer_version}")
    if core_version == "missing":
        # Do not invoke an unavailable/mixed core to make further health claims.
        return 12, notes
    if core_version != installer_version or core_version != SCRIPT_VERSION:
        notes.append("WARN version drift: engine/core/installer releases differ")
    machine = (machine_override or "").strip() or str(state.get("machine") or "").strip()
    if not machine:
        return 12, ["no machine name in state — reinstall with install-skill-repo-sync.py --machine <name>"]
    notes.append(f"machine: {machine}")
    ok = core_version != "missing"
    for repo in repos_from_state():
        remote = has_remote(repo)
        allowed, br_reason = branch_policy(repo, machine)
        head = git(repo, "rev-parse", "--short", "HEAD").stdout.strip()
        notes.append(f"repo {repo}: remote={'yes' if remote else 'NO'} head={head}")
        try:
            lock = workflow_core().read_contributor_lock(repo)
        except (OSError, RuntimeError) as exc:
            lock = {"malformed": str(exc)}
        if lock is None:
            notes.append("  contributor lock: not held")
        elif lock.get("malformed") is not None:
            notes.append("  contributor lock: unreadable content (refusing to guess an owner)")
        else:
            notes.append(f"  contributor lock: held by token {lock.get('token')} "
                         f"(pid {lock.get('pid')}, host {lock.get('host')})")
        if not remote:
            ok = False
        if not allowed:
            notes.append(f"WARN branch policy: {br_reason}")
            ok = False
    if not _maintainer_facts(notes):
        ok = False
    notes.append("hooks: not inspected by --selfcheck — consent/health is `hermes hooks doctor`")
    notes.append(f"last pushed tip: {state.get('last_pushed_tip') or '(none)'} "
                 f"(recorded metadata, never authority to reset)")
    cursor, total = int(state.get(CURSOR_KEY) or 0), len(read_ledger())
    notes.append(f"ledger: {total} entries, stage cursor at {cursor}, {max(0, total - cursor)} pending")
    return (0 if ok else 12), notes


def main() -> int:
    ap = argparse.ArgumentParser(description="stage/refresh/integrate layer for the shared skill repo (v3)")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--stage", action="store_true",
                      help="bundle pending work into one local commit on machine/<name> "
                           "(push-gate: the pre-integration run pushes) (default)")
    mode.add_argument("--sync-from-main", action="store_true",
                      help="session-start refresh: fetch; fast-forward when HEAD is an "
                           "ancestor of integrated main; never reset or rebase")
    mode.add_argument("--screen-history", metavar="SHA", default=None,
                      help="mechanical screen of the whole unpublished range of SHA "
                           "(paths/categories only; exit 10 on findings)")
    mode.add_argument("--record-history-review", metavar="SHA", default=None,
                      help="record the agent's profile-scope review for exactly SHA "
                           "(requires --history-review FILE)")
    mode.add_argument("--push-reviewed", metavar="SHA", default=None,
                      help="push the exact reviewed commit SHA to machine/<name>, not the "
                           "branch name; refuses without a matching history review")
    mode.add_argument("--lock", action="store_true",
                      help="hold the contributor lock across a deliberate pre-integration merge")
    mode.add_argument("--unlock", action="store_true",
                      help="release the contributor lock recorded by --lock")
    mode.add_argument("--selfcheck", action="store_true", help="verify the install")
    mode.add_argument("--version", action="store_true", help="print the script version")
    ap.add_argument("--machine", default=None, help="machine name override (default: from state file)")
    ap.add_argument("--history-review", default=None, metavar="FILE",
                    help="agent history review JSON for --record-history-review")
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
            # Validate the installed pair even for otherwise no-op/dry-run paths.
            workflow_core()
            state = load_state()
            machine = (args.machine or "").strip() or str(state.get("machine") or "").strip()
            if not machine:
                print("skill-repo-sync: no machine name in state — reinstall with "
                      "install-skill-repo-sync.py --machine <name>")
                return 12
            repos = repos_from_state()
            if args.lock:
                code, notes = lock_contributor(repos, args.dry_run, args.verbose)
            elif args.unlock:
                code, notes = unlock_contributor(repos, args.dry_run, args.verbose)
            elif args.sync_from_main:
                code, notes = 0, []
                for repo in repos:
                    repo_code, repo_notes = sync_from_main(repo, machine, args.dry_run, args.verbose)
                    notes += repo_notes
                    code = max(code, repo_code)
            elif args.screen_history or args.record_history_review or args.push_reviewed:
                tip = (args.screen_history or args.record_history_review
                       or args.push_reviewed or "").strip()
                try:
                    tip = _full_sha(tip, "reviewed tip")
                    repo = _select_repo(repos, tip)
                except RuntimeError as exc:
                    code, notes = 12, [f"skill-repo-sync: {exc}"]
                else:
                    if args.screen_history:
                        code, notes = screen_history(repo, machine, tip, args.dry_run, args.verbose)
                    elif args.record_history_review:
                        if not args.history_review:
                            code, notes = 12, ["skill-repo-sync: --record-history-review "
                                               "requires --history-review FILE"]
                        else:
                            code, notes = record_history_review(
                                repo, machine, tip, args.history_review, args.dry_run, args.verbose)
                    else:
                        code, notes = push_reviewed(repo, machine, tip, args.dry_run, args.verbose)
            else:
                code, notes = 0, []
                for repo in repos:
                    repo_code, repo_notes = stage(repo, machine, args.dry_run, args.verbose)
                    notes += repo_notes
                    code = max(code, repo_code)
            if (args.stage or not any((args.sync_from_main, args.lock, args.unlock,
                                       args.screen_history, args.record_history_review,
                                       args.push_reviewed))) \
                    and len(notes) < len(repos) and not any(n for n in notes) and args.verbose:
                notes = ["nothing to do"]
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        code, notes = 12, [f"skill-repo-sync: {type(exc).__name__}: {exc}"]
    for line in ([] if args.hook and code == 0 and not args.verbose else notes):
        print(line, file=sys.stderr if args.hook else sys.stdout)
    return code


if __name__ == "__main__":
    sys.exit(main())
