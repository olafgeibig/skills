#!/usr/bin/env python3
# install-skill-repo-sync — install the stage-and-consolidate sync layer on this machine.
#
# INSTALLER_VERSION: 3.0.0   (kept in step with SCRIPT_VERSION; --selfcheck reports drift)
#
#   1. installs the engine pair   <hermes home>/bin/skill-repo-sync.py
#                                 + <hermes home>/bin/skill_repo_workflow.py (same version)
#                                 + the report template; refuses a partial pair
#   2. writes the stable wrapper  <hermes home>/bin/skill-repo-sync  -> execs the installed engine
#   3. writes the state file       <hermes home>/skill-repo-sync.json (machine, repos, cursor, versions)
#   4. with --apply-config:        reads hooks.on_session_start with `hermes config get … --json`
#                                  and appends this wrapper's session hook, preserving every
#                                  unrelated entry; hooks.on_skill_lifecycle is never written or
#                                  cleared; never global hook auto-accept
#   5. prints cron, consent, and verification steps
#
# A fresh install (no state file) refuses before any write or chmod unless the operator states the
# historical-ledger choice with --bootstrap-current-ledger; an existing install keeps its cursor
# and refuses that flag.
#
# The repo must be checked out on `machine/<name>` tracking the same remote branch — the staging
# layer refuses everything else. The machine name is the logical name of the project's machine
# table: pass it with --machine or set SKILL_REPO_MACHINE.
#
# Usage
#   python3 install-skill-repo-sync.py --bootstrap-current-ledger --apply-config [--machine NAME]
#                                     [--repo PATH ...] [--python BIN]
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

INSTALLER_VERSION = "3.0.0"
ENGINE = "skill-repo-sync.py"
CORE = "skill_repo_workflow.py"
REPORT_TEMPLATE = "skill-sync-report.md.example"
WRAPPER_NAME = "skill-repo-sync"
STATE_NAME = "skill-repo-sync.json"
SESSION_HOOK_KEY = "hooks.on_session_start"
LIFECYCLE_HOOK_KEY = "hooks.on_skill_lifecycle"


class HookConfigError(RuntimeError):
    """The hook list could not be read, so no hook write may happen."""


class InstallError(RuntimeError):
    """The engine/core pair could not be installed completely."""


def _release_version(path: Path, marker: str) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    match = re.search(rf'^{marker}\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return match.group(1) if match else ""


def install_engine_pair(home: Path) -> tuple[Path, Path, list[str]]:
    """Copy the engine, its shared core and the report template into <home>/bin.

    Stage and verify all new files, then snapshot every previous target before
    replacing any of them. Any exception (including interruption) restores the
    old bytes and modes, or removes targets absent before a fresh installation.
    This is exception rollback, not a crash-atomic multi-file filesystem write;
    the engine's version gate refuses a mixed pair during the replacement window.
    """
    source_dir = Path(__file__).resolve().parent
    sources = {
        ENGINE: source_dir / ENGINE,
        CORE: source_dir / CORE,
        REPORT_TEMPLATE: source_dir.parent / "assets" / REPORT_TEMPLATE,
    }
    missing = [name for name, path in sources.items() if not path.is_file()]
    if missing:
        raise InstallError(
            "refusing a partial installation — the engine ships with its shared core "
            f"and report template; missing: {', '.join(missing)}"
        )
    engine_version = _release_version(sources[ENGINE], "SCRIPT_VERSION")
    core_version = _release_version(sources[CORE], "CORE_VERSION")
    if not engine_version or not core_version:
        raise InstallError("cannot read SCRIPT_VERSION/CORE_VERSION from the engine pair")
    if engine_version != core_version:
        raise InstallError(
            f"engine SCRIPT_VERSION {engine_version} does not match core CORE_VERSION "
            f"{core_version}; refusing a mixed installation"
        )
    if INSTALLER_VERSION != engine_version:
        raise InstallError(
            f"INSTALLER_VERSION {INSTALLER_VERSION} does not match engine SCRIPT_VERSION "
            f"{engine_version}; refusing a mixed installation"
        )

    target_dir = home / "bin"
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise InstallError(f"cannot create the install directory {target_dir}: {exc}") from exc
    transaction_dir = None
    staged: list[tuple[Path, Path]] = []
    backups: dict[Path, Path | None] = {}
    replacing = False
    keep_backups = False
    try:
        # Same filesystem as the targets: each replacement/restore is an atomic rename.
        transaction_dir = Path(tempfile.mkdtemp(prefix=".skill-repo-sync-", dir=target_dir))
        for name, source in sources.items():
            target = target_dir / name
            temporary = transaction_dir / f"{name}.new"
            shutil.copy2(source, temporary)
            os.chmod(temporary, 0o755 if name in (ENGINE, CORE) else 0o644)
            staged.append((temporary, target))
        # Verify the staged pair before any target is replaced.
        staged_engine = transaction_dir / f"{ENGINE}.new"
        staged_core = transaction_dir / f"{CORE}.new"
        if not staged_engine.is_file() or not staged_core.is_file():
            raise InstallError("staged engine/core pair is incomplete; nothing was installed")
        staged_engine_version = _release_version(staged_engine, "SCRIPT_VERSION")
        staged_core_version = _release_version(staged_core, "CORE_VERSION")
        if staged_engine_version != staged_core_version or not staged_engine_version:
            raise InstallError(
                "staged engine/core versions disagree; refusing a partial installation"
            )
        for _, target in staged:
            backup = transaction_dir / f"{target.name}.old"
            if target.exists():
                shutil.copy2(target, backup)
                backups[target] = backup
            else:
                backups[target] = None
        replacing = True
        for temporary, target in staged:
            os.replace(temporary, target)
    except BaseException as exc:
        rollback_errors = []
        if replacing:
            # Restore ALL targets, including the one whose replace failed: it may
            # have changed before the exception. POSIX rename replaces atomically
            # and does not depend on the failed os.replace installation primitive.
            for target, backup in backups.items():
                try:
                    if backup is None:
                        target.unlink(missing_ok=True)
                    else:
                        os.rename(backup, target)
                except OSError as rollback_exc:
                    rollback_errors.append(f"{target}: {rollback_exc}")
        if rollback_errors:
            keep_backups = True
            raise InstallError(
                f"installation failed: {exc}; rollback incomplete: {'; '.join(rollback_errors)}; "
                f"recovery files retained at {transaction_dir}"
            ) from exc
        if isinstance(exc, InstallError) or not isinstance(exc, Exception):
            raise
        raise InstallError(f"cannot install the engine/core pair into {target_dir}: {exc}") from exc
    finally:
        if transaction_dir is not None and not keep_backups:
            shutil.rmtree(transaction_dir, ignore_errors=True)
    return target_dir / ENGINE, target_dir / CORE, [
        f"engine:  {target_dir / ENGINE} (version {engine_version})",
        f"core:    {target_dir / CORE} (version {core_version})",
        f"template:{target_dir / REPORT_TEMPLATE}",
    ]


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


def read_hook_list(hermes: str, key: str) -> list:
    """Return the hooks configured under ``key`` as a list of entries — or refuse.

    An unset key is a normal fresh profile (the real CLI answers ``Config key not set``); any
    other failure or an answer that is not a JSON list is a refusal. An unparsed answer must
    never be replaced by a freshly written list, or unrelated hooks would be lost.
    """
    proc = subprocess.run([hermes, "config", "get", key, "--json"],
                          capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        message = ((proc.stderr or "").strip() or (proc.stdout or "").strip()
                   or f"exit {proc.returncode}")
        if not proc.stdout.strip() and "not set" in message.lower():
            return []
        raise HookConfigError(f"config get {key} failed: {message.splitlines()[0][:200]}")
    body = proc.stdout.strip()
    try:
        value = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HookConfigError(
            f"config get {key} --json returned malformed JSON: {body[:120]!r}") from exc
    if not isinstance(value, list):
        raise HookConfigError(f"config get {key} --json returned {type(value).__name__}, "
                              "expected a list")
    return value


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
    ap = argparse.ArgumentParser(description="install the stage-and-consolidate sync layer for the "
                                             "shared skill repo")
    ap.add_argument("--apply-config", action="store_true",
                    help="append the on_session_start hook (other hooks, including any "
                         "on_skill_lifecycle entry, are preserved)")
    ap.add_argument("--bootstrap-current-ledger", action="store_true",
                    help="fresh install only: start the staging cursor at the current ledger end "
                         "(without it a fresh install refuses)")
    ap.add_argument("--machine", default=None,
                    help="logical machine name (default: SKILL_REPO_MACHINE env var)")
    ap.add_argument("--repo", action="append", default=[], help="additional shared repo (repeatable)")
    ap.add_argument("--python", default="python3", help="interpreter the wrapper execs (default: python3)")
    ap.add_argument("--selfcheck", action="store_true", help="report the current install and exit")
    ap.add_argument("--version", action="store_true", help="print the installer version")
    args = ap.parse_args()
    if args.version:
        print(f"install-skill-repo-sync {INSTALLER_VERSION}")
        return 0
    interpreter, interpreter_note = resolve_interpreter(args.python)

    home = hermes_home()
    engine = Path(__file__).resolve().parent / ENGINE
    repo = Path(__file__).resolve().parents[3]          # <repo>/skills/<skill>/scripts/this.py
    state_path = home / STATE_NAME
    wrapper = home / "bin" / WRAPPER_NAME

    if args.selfcheck:
        installed = home / "bin" / ENGINE
        target = installed if installed.is_file() else engine
        return subprocess.run([sys.executable, str(target), "--selfcheck", "--verbose"]).returncode

    if not engine.is_file():
        print(f"error: engine missing: {engine}")
        return 1
    machine = resolve_machine(args.machine)

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

    # 0) consent gates — settled before the first write (wrapper, state, config or file mode).
    #    A fresh install must state its historical-ledger choice; an existing cursor is never
    #    silently rewound by re-running the installer.
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
    if existing_state is None and not args.bootstrap_current_ledger:
        print(f"error: refusing a fresh install without --bootstrap-current-ledger: {state_path} "
              "does not exist, so the staging cursor would start at 0 and the next sweep would "
              "transport every historical ledger entry. Re-run with --bootstrap-current-ledger to "
              "start at the current ledger end, or restore the existing state file.")
        return 12
    if existing_state is not None and args.bootstrap_current_ledger:
        print(f"error: --bootstrap-current-ledger is for a fresh install only: existing state at "
              f"{state_path} records cursor {existing_state.get('ledger_cursor')!r}. Omit the flag "
              "to keep the saved cursor.")
        return 12

    try:
        ledger_count = ledger_entry_count(home)
    except (OSError, ValueError) as exc:
        print(f"error: cannot establish ledger baseline: {exc}")
        return 1

    # Hook consent is read before the first write: an unreadable list means no write at all.
    hermes = shutil.which("hermes") if args.apply_config else None
    session_cmd = f"{shlex.quote(str(wrapper))} --sync-from-main --hook"
    session_entry = {"command": session_cmd, "timeout": 20}
    hooks: list = []
    session_present = False
    if hermes:
        try:
            hooks = read_hook_list(hermes, SESSION_HOOK_KEY)
        except (HookConfigError, OSError, subprocess.SubprocessError) as exc:
            print(f"error: refusing to write hooks: {exc}")
            return 12
        session_present = any(isinstance(entry, dict) and entry.get("command") == session_cmd
                              for entry in hooks)
        if not session_present:
            hooks.append(session_entry)

    # Install the engine/core pair together; a partial pair refuses before the
    # wrapper or state file exists, so a real install can never exec an engine
    # whose shared core was left behind in the repository.
    try:
        installed_engine, installed_core, install_notes = install_engine_pair(home)
    except InstallError as exc:
        print(f"error: {exc}")
        return 1
    for line in install_notes:
        print(line)

    # 1) stable wrapper — written only when its content changes, so the hook consent
    #    (which records the script mtime) stays valid across repeated installer runs
    wrapper.parent.mkdir(parents=True, exist_ok=True)
    wrapper_text = (
        "#!/bin/sh\n"
        f"# {WRAPPER_NAME} wrapper — INSTALLER_VERSION {INSTALLER_VERSION}\n"
        "# Stable path: the shell-hook consent pair is (event, command); update the engine in the\n"
        "# repository, not this file.\n"
        f'exec {shlex.quote(interpreter)} {shlex.quote(str(installed_engine))} "$@"\n')
    if wrapper.is_file() and wrapper.read_text(encoding="utf-8") == wrapper_text:
        print(f"wrapper: unchanged ({wrapper})")
    else:
        wrapper.write_text(wrapper_text, encoding="utf-8")
        os.chmod(wrapper, 0o755)
        print(f"wrapper: written {wrapper} -> {installed_engine}")
    print(f"python:  {interpreter_note}")

    # 2) state file — the staging layer is publish-safe by construction (machine branch only).
    #    A fresh install starts at the ledger end only because the operator chose
    #    --bootstrap-current-ledger above; an existing cursor is kept (an upgrade must not rewind
    #    already-staged history).
    state = existing_state or {}
    state.update({"version": INSTALLER_VERSION, "installer_version": INSTALLER_VERSION,
                  "hermes_home": str(home), "machine": machine,
                  "repos": repos, "wrapper": str(wrapper), "script": str(installed_engine),
                  "core": str(installed_core), "python": interpreter,
                  "sync_model": "stage-consolidate-v2",
                  "installed_at": datetime.now(tz=timezone.utc).isoformat()})
    state.setdefault("ledger_cursor", ledger_count)
    if not isinstance(state.get("ledger_cursor"), int):
        print(f"error: existing state has no valid ledger_cursor: {state_path}")
        return 1
    tmp_state = state_path.with_suffix(".tmp")
    tmp_state.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp_state, state_path)
    print(f"state: {state_path} (machine={machine}, {len(repos)} repo(s), cursor={state['ledger_cursor']})")

    # 3) config: append the session-start refresh hook to whatever the profile already has.
    #    on_skill_lifecycle is never written here — a v1 publisher hook is retired by a
    #    deliberate operator step, not silently by an installer rerun.
    config_failed = False
    if not hermes:
        print(f"config: pending (run with --apply-config) — hermes config set {SESSION_HOOK_KEY} "
              f"'{json.dumps([session_entry])}'")
    elif session_present:
        print(f"config: {SESSION_HOOK_KEY} already carries this hook "
              f"({len(hooks)} entries preserved)")
    else:
        done = subprocess.run([hermes, "config", "set", SESSION_HOOK_KEY, json.dumps(hooks)],
                              capture_output=True, text=True, timeout=120)
        if done.returncode == 0:
            message = (done.stdout or done.stderr).strip()
            print("config: " + (message.splitlines()[0] if message else
                                f"appended to {SESSION_HOOK_KEY} "
                                f"({len(hooks) - 1} other hook(s) preserved)"))
        else:
            print(f"error: config set {SESSION_HOOK_KEY} failed: {done.stderr.strip()[:200]}")
        config_failed = config_failed or done.returncode != 0
    print(f"config: {LIFECYCLE_HOOK_KEY} left unchanged — lifecycle hooks are never blanket-cleared")

    # 4) next steps
    print()
    print("next steps (once per machine):")
    print("  1. approve only the on_session_start hook pair; global hooks_auto_accept stays unchanged")
    print("  2. staging cron: hourly no_agent script running `<wrapper> --stage` "
          "(see references/shared-repo-sync.md § Crons)")
    print("  3. verify: hermes hooks list && hermes hooks doctor")
    print(f"  4. verify: {interpreter} {installed_engine} --selfcheck --verbose "
          f"(or `{wrapper} --selfcheck --verbose`)")
    return 1 if config_failed else 0


if __name__ == "__main__":
    sys.exit(main())
