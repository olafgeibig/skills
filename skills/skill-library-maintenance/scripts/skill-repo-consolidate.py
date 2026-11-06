#!/usr/bin/env python3
# skill-repo-consolidate — v2 "Stage & Curate" consolidation helpers (runs on the curator host only).
#
# SCRIPT_VERSION: 2.0.0
# Companion of skill-repo-sync.py. The nightly consolidation is AGENT work: the cron job loads
# skill-library-maintenance, reads the collected diffs, edits files on main deliberately
# (dedupe, scope discipline, SemVer — rules in skill-governance), commits, pushes main and
# resets the consumed transport branches. This script is the mechanical scaffold around that:
#
#   --collect [--outdir DIR]   fetch spray; for every machine branch with a non-empty net diff
#                              against origin/main, write the diff and a metadata row; print JSON
#                              (read-only apart from the fetch — feeds the agent prompt)
#   --preflight [--outdir DIR] scan the pending consolidation target (working tree on main after
#                              the agent's edits) for instance pointers and dangling references;
#                              exit 10 on findings (the agent must repair, not force through)
#   --reset-branch NAME ...    for each consumed host: push --force-with-lease origin
#                              <origin/main sha>:refs/heads/machine/<host>  (the ONE allowed force)
#                              refuses when local main != origin/main or the branch still has
#                              unconsolidated content
#
# Exit codes: 0 ok/no-op · 10 preflight findings · 12 other error · 13 not installed
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path

SCRIPT_VERSION = "2.0.0"
STATE_NAME = "skill-repo-sync.json"

# Reuse the canonical instance-pointer patterns from the engine (single source of truth).
_here = Path(__file__).resolve().parent
_engine_candidates = [
    _here / "skill-repo-sync.py",  # beside this script inside the repo
]
# A copy of this helper running outside the repo points at the engine explicitly:
_env_engine = os.environ.get("SKILL_REPO_SYNC_ENGINE", "").strip()
if _env_engine:
    _engine_candidates.append(Path(_env_engine).expanduser())
_engine_path = next((p for p in _engine_candidates if p.is_file()), None)
assert _engine_path is not None, "engine module not found beside this script or in the repo"
_spec = spec_from_file_location("srs_engine", _engine_path)
assert _spec is not None and _spec.loader is not None, "engine module missing beside this script"
srs = module_from_spec(_spec)
_spec.loader.exec_module(srs)
INSTANCE_PATTERNS = srs.INSTANCE_PATTERNS
LINK_RE = srs.LINK_RE
REF_RE = srs.REF_RE


def hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes")).expanduser()


def git(repo: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    env.setdefault("GIT_SSH_COMMAND", "ssh -oBatchMode=yes -oConnectTimeout=10")
    env.setdefault("GIT_ASKPASS", "/bin/true")
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                          check=check, timeout=180, env=env)


def repo_from_args(args: argparse.Namespace) -> Path:
    root = git(Path(args.repo), "rev-parse", "--show-toplevel")
    if root.returncode != 0:
        raise SystemExit(f"error: not a git repo: {args.repo}")
    return Path(root.stdout.strip())


def main_sha(repo: Path) -> tuple[str, str | None]:
    fetch = git(repo, "fetch", "origin", "--quiet")
    if fetch.returncode != 0:
        return "", f"fetch failed: {(fetch.stderr or fetch.stdout).strip()[:300]}"
    local = git(repo, "rev-parse", "refs/remotes/origin/main").stdout.strip()
    remote = git(repo, "rev-parse", "refs/heads/main").stdout.strip()
    if local != remote:
        return local, (f"local main ({remote[:12]}) != origin/main ({local[:12]}); "
                       "reset or merge main first — never reset a consumed branch from a stale base")
    return local, None


def machine_shas(repo: Path) -> dict[str, str]:
    out = git(repo, "ls-remote", "origin", "refs/heads/machine/*").stdout.splitlines()
    shas = {}
    for line in out:
        sha, ref = line.split()
        shas[ref.split("refs/heads/machine/")[-1]] = sha
    return dict(sorted(shas.items()))


def collect(repo: Path, outdir: Path, verbose: bool) -> tuple[int, list[str]]:
    notes: list[str] = []
    notes.append("update origin in this clone before trusting the diff output")
    main, err = main_sha(repo)
    if err:
        return 12, [f"machine collection: {err}"]
    shas = machine_shas(repo)
    if not shas:
        return 12, ["machine collection: no machine/* branches on the remote"]

    rows = []
    outdir.mkdir(parents=True, exist_ok=True)
    for host, sha in shas.items():
        name_only = git(repo, "diff", "--name-only", f"{main}...{sha}").stdout.strip()
        if not name_only:
            rows.append({"machine": host, "sha": sha[:12], "empty": True})
            continue
        shortstat = git(repo, "diff", "--shortstat", f"{main}...{sha}").stdout.strip()
        subjects = [l for l in git(repo, "log", "--format=%h %s", f"{main}..{sha}").stdout.splitlines()
                    if l.strip()]
        diff_target = outdir / f"machine-{host}.diff"
        diff = git(repo, "diff", f"{main}...{sha}")
        diff_target.write_text(diff.stdout, encoding="utf-8")
        # Overlaps between machine branches: files another pending branch also touches.
        overlaps = [r["machine"] for r in rows
                    for f in r.get("files", [])
                    if f in name_only.splitlines()]
        files = name_only.splitlines()
        rows.append({"machine": host, "sha": sha[:12], "empty": False,
                     "shortstat": shortstat, "files": files, "subjects": subjects,
                     "overlaps": overlaps, "diff_path": str(diff_target)})
        if verbose:
            notes.append(f"machine/{host}: {shortstat} → {diff_target.name}")

    report = {"at": datetime.now(tz=timezone.utc).isoformat(),
              "main_sha": main[:12], "out_dir": str(outdir), "branches": rows}
    (outdir / "collect.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0, notes


def added_pairs_from_diff(diff_text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    current = ""
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith("+") and not line.startswith("+++ b/"):
            out.append((current, line[1:]))
    return out


def preflight_scan(repo: Path, outdir: Path) -> tuple[int, list[str]]:
    """Scan every pending branch diff (as collected) for defects the agent must repair in its edit."""
    notes: list[str] = []
    main, err = main_sha(repo)
    if err:
        return 12, [f"machine preflight: {err}"]
    findings: list[dict] = []
    for host, sha in machine_shas(repo).items():
        diff = git(repo, "diff", f"{main}...{sha}")
        if diff.returncode != 0 or not diff.stdout.strip():
            continue
        for file, text in added_pairs_from_diff(diff.stdout):
            if not text.strip():
                continue
            for pattern, label in INSTANCE_PATTERNS:
                if re.search(pattern, text):
                    findings.append({"machine": host, "file": file, "kind": "instance-pointer",
                                     "detail": label, "line": text.strip()[:160]})
            for target in LINK_RE.findall(text) + REF_RE.findall(text):
                target = target.strip()
                if target.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                base = repo / file if file else repo
                if not (base.parent / target).exists() and not (repo / target).exists():
                    findings.append({"machine": host, "file": file, "kind": "dangling-reference",
                                     "detail": target, "line": text.strip()[:160]})
    seen: set = set()
    unique = [f for f in findings
              if not (f["machine"], f["file"], f["kind"], f["detail"], f["line"]) in seen
              and not seen.add((f["machine"], f["file"], f["kind"], f["detail"], f["line"]))]
    if unique:
        out = {"at": datetime.now(tz=timezone.utc).isoformat(), "findings": unique}
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "preflight-findings.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
        notes.append(f"preflight: {len(unique)} finding(s) — mechanism repair belongs to the agent's edit, "
                     "not to a forced push")
        for f in unique[:20]:
            notes.append(f"  ! [{f['machine']}] {f['kind']} in {f['file']}: {f['detail']} — {f['line'][:80]}")
        return 10, notes
    notes.append("preflight: no instance-pointer or dangling-reference findings in the pending diffs")
    return 0, notes


def reset_branches(repo: Path, hosts: list[str], dry_run: bool) -> tuple[int, list[str]]:
    """Push origin/main onto the consumed transport branches. The ONLY allowed force in v2."""
    notes: list[str] = []
    main, err = main_sha(repo)
    if err:
        return 12, [f"machine reset: {err}"]
    remote_shas = machine_shas(repo)
    for host in hosts:
        ref = f"refs/heads/machine/{host}"
        old = remote_shas.get(host)
        if old is None:
            notes.append(f"machine/{host}: not on remote — nothing to reset")
            continue
        if old == main:
            notes.append(f"machine/{host}: already at origin/main")
            continue
        # Safety: never clamp a branch that still carries unique work.
        ancestor = git(repo, "merge-base", "--is-ancestor", old, main).returncode == 0
        if not ancestor:
            return 12, ([f"machine/{host}: branch {old[:12]} has content main lacks — "
                         "consolidate before resetting (refusing force)"] + notes)
        if dry_run:
            notes.append(f"[dry-run] would push {main[:12]}:{ref} (was {old[:12]})")
            continue
        push = git(repo, "push", f"--force-with-lease={ref}:{old}", f"{main}:{ref}")
        if push.returncode != 0:
            notes.insert(0, f"machine/{host}: reset push failed: {(push.stderr or push.stdout).strip()[:300]}")
            return 12, notes
        notes.append(f"machine/{host}: reset to origin/main ({main[:12]})")
    return 0, notes


def main() -> int:
    ap = argparse.ArgumentParser(description="v2 consolidation helpers (curator host only)")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--collect", action="store_true",
                      help="fetch and write pending branch diffs + metadata JSON")
    mode.add_argument("--preflight", action="store_true",
                      help="scan pending branch diffs for instance pointers and dangling refs")
    mode.add_argument("--reset-branch", metavar="HOST", nargs="+", action="store",
                      help="reset consumed machine branches to origin/main (force-with-lease)")
    ap.add_argument("--repo", default=None, help="path to the shared skill repo (default: from state)")
    ap.add_argument("--outdir", default=None, help="where collect writes diffs (default: <repo>/.consolidate-scratch)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    if args.repo:
        repo = repo_from_args(args)
    else:
        state = srs.load_state()
        repos = list(state.get("repos") or [])
        if not repos:
            print("error: no repo configured — pass --repo")
            return 13
        repo = Path(repos[0]["path"]).expanduser()
        if not repo.is_dir():
            print(f"error: configured repo missing: {repo}")
            return 13

    outdir = Path(args.outdir) if args.outdir else repo / ".consolidate-scratch"
    try:
        if args.collect:
            code, notes = collect(repo, outdir, args.verbose)
        elif args.preflight:
            code, notes = preflight_scan(repo, outdir)
        else:
            code, notes = reset_branches(repo, args.reset_branch, args.dry_run)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        code, notes = 12, [f"skill-repo-consolidate: {type(exc).__name__}: {exc}"]
    for line in notes:
        print(line, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
