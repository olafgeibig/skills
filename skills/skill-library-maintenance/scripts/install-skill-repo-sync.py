#!/usr/bin/env python3
# install-skill-repo-sync — install the v2 staging layer on this machine.
#
# INSTALLER_VERSION: 2.0.0   (must match SCRIPT_VERSION of skill-repo-sync.py)
#
#   1. writes the stable wrapper   <hermes home>/bin/skill-repo-sync  -> execs the engine in this repo
#   2. writes the state file       <hermes home>/skill-repo-sync.json (machine, repos, cursor, versions)
#   3. with --apply-config:        sets the on_session_start hook ONLY (the v1 per-mutation
#                                  on_skill_lifecycle hook is emptied, not re-registered);
#                                  never global hook auto-accept
#   4. prints cron, consent, and verification steps
#
# The repo must be checked out on `machine/<name>` tracking the same remote branch — the staging
# layer refuses everything else. The machine name is the logical name of the project's machine
# table: pass it with --machine or set SKILL_REPO_MACHINE.
#
# Usage
#   python3 install-skill-repo-sync.py --apply-config [--machine NAME] [--repo PATH ...] [--python BIN]
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

INSTALLER_VERSION = "2.0.0"
ENGINE = "skill-repo-sync.py"
WRAPPER_NAME = "skill-repo-sync"
STATE_NAME = "skill-repo-sync.json"


def hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes")).expanduser()


def git(path: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    env.setdefault("GIT_SSH_COMMAND", "ssh -oBatchMode=yes -oConnectTimeout=10")
    env.setdefault("GIT_ASKPASS", "/bin/true")
    return subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True,
                          timeout=60, env=env)


def ledger_entry_count(home: Path) -> int:
    ledger = home / "skills" / ".curator_ledger.jsonl"
    if not ledger.is_file():
        return 0
    count = 0
    for number, line in enumerate(ledger.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid mutation ledger JSON on line {number}") from exc
        if isinstance(record, dict):
            count += 1
    return count


def resolve_machine(explicit: str | None) -> str:
    if explicit and explicit.strip():
        return explicit.strip()
    env_name = os.environ.get("SKILL_REPO_MACHINE", "").strip()
    if env_name:
        return env_name
    raise SystemExit("error: pass --machine <logical name> — the machine name this installation "
                     "uses for its transport branch (or set SKILL_REPO_MACHINE)")


def machine_branch_ready(repo: Path, machine: str) -> tuple[bool, str]:
    branch = git(repo, "branch", "--show-current").stdout.strip()
    upstream = git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    upstream_name = upstream.stdout.strip() if upstream.returncode == 0 else "<none>"
    expected = f"machine/{machine}"
    if branch != expected:
        if branch == "main":
            return False, (f"the repo is on 'main' — the stage layer never writes main. "
                           f"checkout {expected} first")
        return False, f"expected {expected}; found {branch or '<detached>'} tracking {upstream_name}"
    if upstream_name != f"origin/{expected}":
        return False, f"expected upstream origin/{expected}; found {upstream_name}"
    return True, ""


def resolve_interpreter(name: str) -> tuple[str, str]:
    """Return (interpreter, note). ``python3`` on PATH; a missing one falls back to this process.

    macOS ships no ``python3`` without the Xcode command line tools, and a Homebrew python lives
    outside the default PATH a hook inherits — so a silent fallback beats a hook that never runs.
    """
    found = shutil.which(name)
    if found:
        return found, f"{name} -> {found}"
    return sys.executable, f"WARN {name} not on PATH — using {sys.executable} (pin with --python)"


def main() -> int:
    ap = argparse.ArgumentParser(description="install the v2 staging layer for the shared skill repo")
    ap.add_argument("--apply-config", action="store_true",
                    help="set the on_session_start hook; empty the v1 lifecycle hook")
    ap.add_argument("--machine", default=None,
                    help="logical machine name (default: SKILL_REPO_MACHINE env var)")
    ap.add_argument("--repo", action="append", default=[], help="additional shared repo (repeatable)")
    ap.add_argument("--python", default="python3", help="interpreter the wrapper execs (default: python3)")
    ap.add_argument("--selfcheck", action="store_true", help="report the current install and exit")
    args = ap.parse_args()
    interpreter, interpreter_note = resolve_interpreter(args.python)

    home = hermes_home()
    engine = Path(__file__).resolve().parent / ENGINE
    repo = Path(__file__).resolve().parents[3]          # <repo>/skills/<skill>/scripts/this.py
    state_path = home / STATE_NAME
    wrapper = home / "bin" / WRAPPER_NAME

    if args.selfcheck:
        return subprocess.run([sys.executable, str(engine), "--selfcheck", "--verbose"]).returncode

    if not engine.is_file():
        print(f"error: engine missing: {engine}")
        return 1
    machine = resolve_machine(args.machine)

    try:
        ledger_count = ledger_entry_count(home)
    except (OSError, ValueError) as exc:
        print(f"error: cannot establish ledger baseline: {exc}")
        return 1

    os.chmod(engine, 0o755)

    candidates = [repo] + [Path(p).expanduser() for p in args.repo]
    repos = []
    for cand in candidates:
        root = git(cand, "rev-parse", "--show-toplevel")
        if root.returncode != 0:
            print(f"skip: not a git repo: {cand}")
            continue
        root_path = Path(root.stdout.strip())
        remotes = git(root_path, "remote").stdout.split()
        if not remotes:
            print(f"skip: no remote (nothing to transport): {root_path}")
            continue
        ready, reason = machine_branch_ready(root_path, machine)
        if not ready:
            print(f"error: cannot register {root_path}: {reason}")
            return 1
        repos.append({"name": root_path.name, "path": str(root_path), "remote": remotes[0]})
    if not any(r["path"] == str(repo) for r in repos):
        print(f"error: the repo holding this installer must be registerable: {repo}")
        return 1

    # 1) stable wrapper — written only when its content changes, so the hook consent
    #    (which records the script mtime) stays valid across repeated installer runs
    wrapper.parent.mkdir(parents=True, exist_ok=True)
    wrapper_text = (
        "#!/bin/sh\n"
        f"# {WRAPPER_NAME} wrapper — INSTALLER_VERSION {INSTALLER_VERSION}\n"
        "# Stable path: the shell-hook consent pair is (event, command); update the engine in the\n"
        "# repository, not this file.\n"
        f'exec {shlex.quote(interpreter)} {shlex.quote(str(engine))} "$@"\n')
    if wrapper.is_file() and wrapper.read_text(encoding="utf-8") == wrapper_text:
        print(f"wrapper: unchanged ({wrapper})")
    else:
        wrapper.write_text(wrapper_text, encoding="utf-8")
        os.chmod(wrapper, 0o755)
        print(f"wrapper: written {wrapper} -> {engine}")
    print(f"python:  {interpreter_note}")

    # 2) state file — the staging layer is publish-safe by construction (machine branch only),
    #    so a fresh install simply starts at the current ledger end. An existing cursor is kept:
    #    an upgrade must not rewind already-staged history.
    existing_state = None
    if state_path.is_file():
        try:
            existing_state = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"error: invalid state file {state_path}; correct or remove it and reinstall")
            return 1
        if not isinstance(existing_state, dict):
            print(f"error: state file must contain a JSON object: {state_path}")
            return 1
    state = existing_state or {}
    state.update({"version": INSTALLER_VERSION, "hermes_home": str(home), "machine": machine,
                  "repos": repos, "wrapper": str(wrapper), "script": str(engine),
                  "python": interpreter, "sync_model": "stage-curate-v2",
                  "installed_at": datetime.now(tz=timezone.utc).isoformat()})
    state.setdefault("ledger_cursor", ledger_count)
    if not isinstance(state.get("ledger_cursor"), int):
        print(f"error: existing state has no valid ledger_cursor: {state_path}")
        return 1
    tmp_state = state_path.with_suffix(".tmp")
    tmp_state.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp_state, state_path)
    print(f"state: {state_path} (machine={machine}, {len(repos)} repo(s), cursor={state['ledger_cursor']})")

    # 3) config: session-start refresh in; the v1 per-mutation publisher hook out.
    hermes = shutil.which("hermes") if args.apply_config else None
    config_failed = False
    session_cmd = f"{wrapper} --sync-from-main --hook"
    actions = [
        ("hooks.on_session_start", json.dumps([{"command": session_cmd, "timeout": 20}]), session_cmd),
        ("hooks.on_skill_lifecycle", "[]", None),
    ]
    for key, value, needle in actions:
        if not hermes:
            print(f"config: pending (run with --apply-config) — hermes config set {key} '{value}'")
            continue
        current = subprocess.run([hermes, "config", "get", key],
                                 capture_output=True, text=True, timeout=60)
        if needle and current.returncode == 0 and needle in current.stdout:
            print(f"config: {key} already carries this hook")
            continue
        if needle is None and current.returncode == 0 and current.stdout.strip() in ("[]", ""):
            print(f"config: {key} already emptied")
            continue
        done = subprocess.run([hermes, "config", "set", key, value],
                              capture_output=True, text=True, timeout=120)
        if done.returncode == 0:
            message = (done.stdout or done.stderr).strip()
            print("config: " + (message.splitlines()[0] if message else f"updated {key}"))
        else:
            print(f"error: config set {key} failed: {done.stderr.strip()[:200]}")
        config_failed = config_failed or done.returncode != 0

    # 4) next steps
    print()
    print("next steps (once per machine):")
    print("  1. approve only the on_session_start hook pair; global hooks_auto_accept stays unchanged")
    print("  2. staging cron: hourly no_agent script running `<wrapper> --stage` "
          "(see references/shared-repo-sync.md § Crons)")
    print("  3. verify: hermes hooks list && hermes hooks doctor")
    print(f"  4. verify: {interpreter} {engine} --selfcheck --verbose")
    return 1 if config_failed else 0


if __name__ == "__main__":
    sys.exit(main())
