#!/usr/bin/env python3
# install-skill-repo-sync — install the shared-skill-repo publisher on this machine.
#
# INSTALLER_VERSION: 1.0.0   (must match SCRIPT_VERSION of skill-repo-sync.py)
#
# What it does (all steps idempotent):
#   1. writes the stable wrapper   <hermes home>/bin/skill-repo-sync  -> execs the engine in this repo
#   2. writes the state file       <hermes home>/skill-repo-sync.json (repos, cursor, versions)
#   3. with --apply-config:        hooks_auto_accept + the two hook entries via `hermes config set`
#   4. prints the cron jobs to create and the verification commands
#
# The wrapper path is deliberately constant: the shell-hook consent pair is (event, command), so a
# moving target would need re-consent. Update only the engine in the repo — the wrapper stays.
#
# Usage
#   python3 install-skill-repo-sync.py [--apply-config] [--repo PATH ...] [--python BIN] [--selfcheck]
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

INSTALLER_VERSION = "1.0.1"
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
    ap = argparse.ArgumentParser(description="install the shared-skill-repo publisher for this machine")
    ap.add_argument("--apply-config", action="store_true", help="write the config.yaml hook entries too")
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
            print(f"skip: no remote (never conflicts, nothing to publish): {root_path}")
            continue
        repos.append({"name": root_path.name, "path": str(root_path), "remote": remotes[0]})
    if not any(r["path"] == str(repo) for r in repos):
        print(f"error: the repo holding this installer has no git remote: {repo}")
        return 1

    # 1) stable wrapper — written only when its content changes, so the hook consent
    #    (which records the script mtime) stays valid across repeated installer runs
    wrapper.parent.mkdir(parents=True, exist_ok=True)
    wrapper_text = (
        "#!/bin/sh\n"
        f"# {WRAPPER_NAME} wrapper — INSTALLER_VERSION {INSTALLER_VERSION}\n"
        "# Stable path: the shell-hook consent pair is (event, command); update the engine in the\n"
        "# repository, not this file.\n"
        f'exec {interpreter} "{engine}" "$@"\n')
    if wrapper.is_file() and wrapper.read_text(encoding="utf-8") == wrapper_text:
        print(f"wrapper: unchanged ({wrapper})")
    else:
        wrapper.write_text(wrapper_text, encoding="utf-8")
        os.chmod(wrapper, 0o755)
        print(f"wrapper: written {wrapper} -> {engine}")
    print(f"python:  {interpreter_note}")

    # 2) state file (cursor stays at 0 on purpose: pending review writes get published by the first run)
    state = {}
    if state_path.is_file():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            state = {}
    state.update({"version": INSTALLER_VERSION, "hermes_home": str(home), "repos": repos,
                  "wrapper": str(wrapper), "script": str(engine), "python": interpreter,
                  "installed_at": datetime.now(tz=timezone.utc).isoformat()})
    state.setdefault("ledger_cursor", 0)
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"state: {state_path} ({len(repos)} repo(s), cursor={state['ledger_cursor']})")

    # 3) config entries
    parent_cmd = f"{wrapper} --hook"
    pull_cmd = f"{wrapper} --pull-only --hook"
    settings = [
        ("hooks_auto_accept", "true", None),
        ("hooks.on_skill_lifecycle", json.dumps([{"command": parent_cmd, "timeout": 20}]), parent_cmd),
        ("hooks.on_session_start", json.dumps([{"command": pull_cmd, "timeout": 20}]), pull_cmd),
    ]
    hermes = shutil.which("hermes")
    for key, value, needle in settings:
        if needle:
            current = subprocess.run([hermes or "hermes", "config", "get", key],
                                     capture_output=True, text=True, timeout=60) if hermes else None
            if current and needle in current.stdout:
                print(f"config: {key} already carries this hook")
                continue
        if not args.apply_config:
            print(f"config: pending (run with --apply-config) — hermes config set {key} '{value}'")
            continue
        if not hermes:
            print(f"error: `hermes` not on PATH; set manually: {key} = {value}")
            continue
        done = subprocess.run([hermes, "config", "set", key, value], capture_output=True, text=True, timeout=120)
        print(("config: " + (done.stdout or done.stderr).strip().splitlines()[0]) if done.returncode == 0
              else f"error: config set {key} failed: {done.stderr.strip()[:200]}")

    # 4) next steps
    print()
    print("next steps (once per machine):")
    print("  1. create the two cron jobs (see references/shared-repo-sync.md § Cron)")
    print(f"  2. verify: hermes hooks list && hermes hooks doctor")
    print(f"  3. verify: {interpreter} {engine} --selfcheck --verbose")
    return 0


if __name__ == "__main__":
    sys.exit(main())
