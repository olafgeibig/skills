from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_ROOT = REPO_ROOT / "skills" / "skill-library-maintenance"
ENGINE = SKILL_ROOT / "scripts" / "skill-repo-sync.py"
INSTALLER = SKILL_ROOT / "scripts" / "install-skill-repo-sync.py"
CONSOLIDATE = SKILL_ROOT / "scripts" / "skill-repo-consolidate.py"
AUDITOR = SKILL_ROOT / "scripts" / "audit-skill-library.py"

MACHINE = "testlab"


def run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    )
    if check:
        assert result.returncode == 0, result.stderr or result.stdout
    return result


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def setup_repo(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """Work repo on machine/<MACHINE> + a bare remote; returns (repo, remote, target, home)."""
    repo = tmp_path / "shared skill repo"
    remote = tmp_path / "shared skill remote.git"
    target = repo / "skills" / "demo" / "SKILL.md"
    target.parent.mkdir(parents=True)
    target.write_text("name: demo\n\nOriginal text.\n", encoding="utf-8")

    subprocess.run(["git", "init", "--initial-branch", "main", str(repo)], check=True, capture_output=True)
    run_git(repo, "config", "user.name", "Sync Test")
    run_git(repo, "config", "user.email", "sync-test@example.invalid")
    run_git(repo, "add", "--", "skills/demo/SKILL.md")
    run_git(repo, "commit", "-m", "initial")
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    run_git(repo, "remote", "add", "origin", str(remote))
    run_git(repo, "push", "--set-upstream", "origin", "main")
    run_git(repo, "checkout", "-b", f"machine/{MACHINE}")
    run_git(repo, "push", "--set-upstream", "origin", f"machine/{MACHINE}")
    home = tmp_path / "hermes home"
    (home / "skills").mkdir(parents=True)
    return repo, remote, target, home


def write_state(home: Path, repos: list[Path], cursor: int = 0, machine: str = MACHINE) -> Path:
    state_path = home / "skill-repo-sync.json"
    state_path.write_text(
        json.dumps(
            {
                "version": "2.0.0",
                "machine": machine,
                "ledger_cursor": cursor,
                "repos": [{"name": repo.name, "path": str(repo), "remote": "origin"} for repo in repos],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return state_path


def write_ledger(home: Path, entries: list[dict]) -> None:
    ledger = home / "skills" / ".curator_ledger.jsonl"
    ledger.write_text("".join(json.dumps(item) + "\n" for item in entries), encoding="utf-8")


def entry_for(target: Path, before: str, after: str, entry_id: str = "entry-1",
              ts: str = "2026-11-01T10:00:00+00:00") -> dict:
    return {
        "id": entry_id,
        "ts": ts,
        "skill": "demo",
        "action": "patch",
        "before": [{"path": str(target), "sha256": sha(before)}],
        "after": [{"path": str(target), "sha256": sha(after)}],
    }


def invoke_engine(home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["HERMES_HOME"] = str(home)
    env["GIT_TERMINAL_PROMPT"] = "0"
    return subprocess.run(
        [sys.executable, str(ENGINE), *args], env=env, capture_output=True, text=True, check=False
    )


def invoke_consolidate(home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["HERMES_HOME"] = str(home)
    env["GIT_TERMINAL_PROMPT"] = "0"
    return subprocess.run(
        [sys.executable, str(CONSOLIDATE), *args], env=env, capture_output=True, text=True, check=False
    )


def remote_head(repo: Path, branch: str) -> str:
    result = run_git(repo, "ls-remote", "origin", f"refs/heads/{branch}")
    return result.stdout.split()[0]


# --- stage ----------------------------------------------------------------------------------------


def test_stage_noop_when_nothing_pending(tmp_path: Path) -> None:
    repo, _, _, home = setup_repo(tmp_path)
    state_path = write_state(home, [repo])
    head_before = run_git(repo, "rev-parse", "HEAD").stdout.strip()
    remote_before = remote_head(repo, f"machine/{MACHINE}")

    result = invoke_engine(home, "--stage", "--verbose")

    assert result.returncode == 0, result.stderr or result.stdout
    assert "nothing to stage" in result.stdout + result.stderr
    assert run_git(repo, "rev-parse", "HEAD").stdout.strip() == head_before
    assert remote_head(repo, f"machine/{MACHINE}") == remote_before


def test_stage_bundles_worktree_and_manual_into_one_commit(tmp_path: Path) -> None:
    repo, _, target, home = setup_repo(tmp_path)
    original = target.read_text(encoding="utf-8")
    target.write_text("name: demo\n\nReviewed guidance unique to this test.\n", encoding="utf-8")
    manual = repo / "notes.md"
    manual.write_text("unswept manual edit\n", encoding="utf-8")
    write_state(home, [repo])
    write_ledger(home, [entry_for(target, original, target.read_text(encoding="utf-8"))])

    result = invoke_engine(home, "--stage", "--verbose")

    assert result.returncode == 0, result.stderr or result.stdout
    state = json.loads((home / "skill-repo-sync.json").read_text(encoding="utf-8"))
    assert state["ledger_cursor"] == 1
    assert run_git(repo, "status", "--porcelain").stdout == ""
    assert remote_head(repo, f"machine/{MACHINE}") == run_git(repo, "rev-parse", "HEAD").stdout.strip()
    message = run_git(repo, "log", "-1", "--format=%B").stdout
    assert "Ledger-Entries: entry-1" in message
    assert "Manual additions" in message and "notes.md" in message
    # exactly ONE new commit
    assert len(run_git(repo, "log", "--format=%h", f"origin/main..HEAD").stdout.splitlines()) == 1


def test_stage_dry_run_mutates_nothing(tmp_path: Path) -> None:
    repo, _, target, home = setup_repo(tmp_path)
    target.write_text("name: demo\n\nPending reviewed change.\n", encoding="utf-8")
    state_path = write_state(home, [repo])
    write_ledger(home, [{"id": "e1", "after": [{"path": str(target)}], "before": []}])

    before = (state_path.read_bytes(), run_git(repo, "rev-parse", "HEAD").stdout.strip(),
              remote_head(repo, f"machine/{MACHINE}"))

    result = invoke_engine(home, "--stage", "--dry-run", "--verbose")

    assert result.returncode == 0, result.stderr or result.stdout
    assert "would stage" in result.stdout
    after = (state_path.read_bytes(), run_git(repo, "rev-parse", "HEAD").stdout.strip(),
             remote_head(repo, f"machine/{MACHINE}"))
    assert after == before


def test_stage_refuses_to_run_on_main(tmp_path: Path) -> None:
    repo, _, target, home = setup_repo(tmp_path)
    run_git(repo, "checkout", "main")
    target.write_text("name: demo\n\nChanged on main.\n", encoding="utf-8")
    write_state(home, [repo])
    head_before = run_git(repo, "rev-parse", "HEAD").stdout.strip()

    result = invoke_engine(home, "--stage")

    assert result.returncode == 12
    assert "stage never touches main" in result.stdout + result.stderr
    assert run_git(repo, "rev-parse", "HEAD").stdout.strip() == head_before
    assert run_git(repo, "diff", "--cached", "--name-only").stdout == ""


def test_stage_refuses_dirty_index(tmp_path: Path) -> None:
    repo, _, _, home = setup_repo(tmp_path)
    (repo / "unrelated.txt").write_text("operator staged this\n", encoding="utf-8")
    run_git(repo, "add", "--", "unrelated.txt")
    write_state(home, [repo])
    head_before = run_git(repo, "rev-parse", "HEAD").stdout.strip()

    result = invoke_engine(home, "--stage")

    assert result.returncode == 12
    assert "staged" in (result.stdout + result.stderr).lower()
    assert run_git(repo, "rev-parse", "HEAD").stdout.strip() == head_before


def test_stage_push_failure_retains_commit_and_retries_without_duplicate(tmp_path: Path) -> None:
    repo, remote, target, home = setup_repo(tmp_path)
    original = target.read_text(encoding="utf-8")
    target.write_text("name: demo\n\nReviewed push-retry change.\n", encoding="utf-8")
    write_state(home, [repo])
    write_ledger(home, [entry_for(target, original, target.read_text(encoding="utf-8"))])
    remote_before = remote_head(repo, f"machine/{MACHINE}")
    hook = remote / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)

    first = invoke_engine(home, "--stage")
    assert first.returncode == 12
    assert "push failed" in first.stdout.lower()
    assert remote_head(repo, f"machine/{MACHINE}") == remote_before
    assert json.loads((home / "skill-repo-sync.json").read_text(encoding="utf-8"))["ledger_cursor"] == 0
    local_after_commit = run_git(repo, "rev-parse", "HEAD").stdout.strip()
    assert local_after_commit != remote_before

    hook.unlink()
    retry = invoke_engine(home, "--stage", "--verbose")
    assert retry.returncode == 0, retry.stderr or retry.stdout
    # retried without building a duplicate commit; cursor advanced after the push only
    assert remote_head(repo, f"machine/{MACHINE}") == local_after_commit
    state = json.loads((home / "skill-repo-sync.json").read_text(encoding="utf-8"))
    assert state["ledger_cursor"] == 1
    assert len(run_git(repo, "log", "--format=%h", f"{remote_before}..HEAD").stdout.splitlines()) == 1


# --- sync-from-main -------------------------------------------------------------------------------


def test_sync_from_main_resets_consumed_branch(tmp_path: Path) -> None:
    repo, _, target, home = setup_repo(tmp_path)
    # a stage commit rides the machine branch
    target.write_text("name: demo\n\nConsumed update.\n", encoding="utf-8")
    write_state(home, [repo])
    assert invoke_engine(home, "--stage").returncode == 0
    stage_sha = run_git(repo, "rev-parse", "HEAD").stdout.strip()

    # the curator: main and the transport branch both move to the consolidated content
    curator = tmp_path / "curator clone"
    run_git(tmp_path, "clone", str(remote := repo) if False else str(tmp_path / "shared skill remote.git"), str(curator))
    run_git(curator, "config", "user.name", "Curator")
    run_git(curator, "config", "user.email", "curator@example.invalid")
    run_git(curator, "checkout", "main")
    run_git(curator, "merge", f"origin/machine/{MACHINE}")
    run_git(curator, "push", "origin", "main")
    run_git(curator, "push", "origin", f"HEAD:refs/heads/machine/{MACHINE}", "--force-with-lease")

    result = invoke_engine(home, "--sync-from-main", "--verbose")

    assert result.returncode == 0, result.stderr or result.stderr or result.stdout
    assert run_git(repo, "rev-parse", "HEAD").stdout.strip() == run_git(repo, "rev-parse", "origin/main").stdout.strip()
    assert run_git(repo, "show", "HEAD:skills/demo/SKILL.md").stdout == "name: demo\n\nConsumed update.\n"


def test_sync_from_main_skips_unconsolidated_branch(tmp_path: Path) -> None:
    repo, _, target, home = setup_repo(tmp_path)
    target.write_text("name: demo\n\nUnconsolidated work.\n", encoding="utf-8")
    write_state(home, [repo])
    assert invoke_engine(home, "--stage").returncode == 0
    head_before = run_git(repo, "rev-parse", "HEAD").stdout.strip()

    result = invoke_engine(home, "--sync-from-main", "--verbose")

    assert result.returncode == 0, result.stderr or result.stdout
    assert "unconsolidated" in result.stdout + result.stderr
    assert run_git(repo, "rev-parse", "HEAD").stdout.strip() == head_before


def test_sync_from_main_fetch_failure_is_nonzero_and_leaves_head(tmp_path: Path) -> None:
    repo, _, _, home = setup_repo(tmp_path)
    write_state(home, [repo])
    run_git(repo, "remote", "set-url", "origin", str(tmp_path / "missing remote.git"))
    head_before = run_git(repo, "rev-parse", "HEAD").stdout.strip()

    result = invoke_engine(home, "--sync-from-main", "--hook")

    assert result.returncode == 12
    assert "fetch failed" in result.stderr.lower()
    assert run_git(repo, "rev-parse", "HEAD").stdout.strip() == head_before


def test_sync_from_main_on_dirty_worktree_is_noop(tmp_path: Path) -> None:
    repo, _, target, home = setup_repo(tmp_path)
    write_state(home, [repo])
    target.write_text("name: demo\n\nDirty local edit.\n", encoding="utf-8")
    head_before = run_git(repo, "rev-parse", "HEAD").stdout.strip()

    result = invoke_engine(home, "--sync-from-main", "--verbose")

    assert result.returncode == 0, result.stderr or result.stdout
    assert "sync skipped" in result.stdout + result.stderr
    assert run_git(repo, "rev-parse", "HEAD").stdout.strip() == head_before


# --- selfcheck & consolidate helpers --------------------------------------------------------------


def test_selfcheck_reports_machine_and_policy(tmp_path: Path) -> None:
    repo, _, _, home = setup_repo(tmp_path)
    write_state(home, [repo])

    result = invoke_engine(home, "--selfcheck")

    assert result.returncode == 0, result.stderr or result.stdout
    assert f"machine: {MACHINE}" in result.stdout


def test_selfcheck_missing_machine_is_explicit(tmp_path: Path) -> None:
    repo, _, _, home = setup_repo(tmp_path)
    state_path = write_state(home, [repo])
    state = json.loads(state_path.read_text(encoding="utf-8"))
    del state["machine"]
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    result = invoke_engine(home, "--selfcheck")

    assert result.returncode == 12
    assert "machine" in (result.stdout + result.stderr).lower()


def test_consolidate_collect_and_reset_roundtrip(tmp_path: Path) -> None:
    repo, remote, target, home = setup_repo(tmp_path)
    # machine branch carries one committed change
    target.write_text("name: demo\n\nConsolidatable rule change.\n", encoding="utf-8")
    run_git(repo, "add", "--", "skills/demo/SKILL.md")
    run_git(repo, "commit", "-m", "stage: local work")
    run_git(repo, "push")

    # curator clone: collect shows the pending branch and its diff
    curator = tmp_path / "curator clone"
    run_git(tmp_path, "clone", str(remote), str(curator))
    run_git(curator, "config", "user.name", "Curator")
    run_git(curator, "config", "user.email", "curator@example.invalid")

    outdir = tmp_path / "collect out"
    collected = invoke_consolidate(home, "--collect", "--repo", str(curator), "--outdir", str(outdir))
    assert collected.returncode == 0, collected.stderr or collected.stdout
    report = json.loads(collected.stdout)
    pending = [r for r in report["branches"] if not r["empty"]]
    assert len(pending) == 1 and pending[0]["machine"] == MACHINE
    assert (outdir / f"machine-{MACHINE}.diff").is_file()
    assert pending[0]["subjects"] and "stage: local work" in pending[0]["subjects"][0]

    # preflight: clean diff is not held
    pre = invoke_consolidate(home, "--preflight", "--repo", str(curator), "--outdir", str(outdir))
    assert pre.returncode == 0, pre.stderr or pre.stdout

    # the curator consolidates by merging the branch into main (test sim of agent edit)
    run_git(curator, "checkout", "main")
    run_git(curator, "merge", f"origin/machine/{MACHINE}")
    run_git(curator, "push", "origin", "main")

    # reset the consumed branch: force-with-lease to origin/main
    reset = invoke_consolidate(home, "--reset-branch", MACHINE, "--repo", str(curator))
    assert reset.returncode == 0, reset.stderr or reset.stdout
    assert remote_head(curator, f"machine/{MACHINE}") == remote_head(curator, "main")

    # rerun reset is a no-op
    again = invoke_consolidate(home, "--reset-branch", MACHINE, "--repo", str(curator), "--dry-run")
    assert again.returncode == 0 and "already at origin/main" in again.stderr


def test_consolidate_reset_refuses_branch_with_unique_work(tmp_path: Path) -> None:
    repo, remote, target, home = setup_repo(tmp_path)
    target.write_text("name: demo\n\nNot yet consolidated.\n", encoding="utf-8")
    run_git(repo, "add", "--", "skills/demo/SKILL.md")
    run_git(repo, "commit", "-m", "stage: unique pending work")
    run_git(repo, "push")

    curator = tmp_path / "curator clone"
    run_git(tmp_path, "clone", str(remote), str(curator))
    run_git(curator, "config", "user.name", "Curator")
    run_git(curator, "config", "user.email", "curator@example.invalid")

    result = invoke_consolidate(home, "--reset-branch", MACHINE, "--repo", str(curator))

    assert result.returncode == 12
    assert "refusing force" in result.stderr
    assert remote_head(curator, f"machine/{MACHINE}") != remote_head(curator, "main")


def test_consolidate_preflight_flags_instance_pointer(tmp_path: Path) -> None:
    repo, remote, target, home = setup_repo(tmp_path)
    target.write_text("name: demo\n\nAlways read /Users/testuser/private/notes.md first.\n",
                      encoding="utf-8")
    run_git(repo, "add", "--", "skills/demo/SKILL.md")
    run_git(repo, "commit", "-m", "stage: work with a leaked pointer")
    run_git(repo, "push")

    curator = tmp_path / "curator clone"
    run_git(tmp_path, "clone", str(remote), str(curator))
    run_git(curator, "config", "user.name", "Curator")
    run_git(curator, "config", "user.email", "curator@example.invalid")
    outdir = tmp_path / "collect out pf"

    result = invoke_consolidate(home, "--preflight", "--repo", str(curator), "--outdir", str(outdir))

    assert result.returncode == 10
    assert "instance-pointer" in result.stderr
    findings = json.loads((outdir / "preflight-findings.json").read_text(encoding="utf-8"))
    assert findings["findings"][0]["kind"] == "instance-pointer"


# --- installer ------------------------------------------------------------------------------------


def installer_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo = tmp_path / "installer fixture"
    scripts = repo / "skills" / "skill-library-maintenance" / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy2(ENGINE, scripts / ENGINE.name)
    shutil.copy2(INSTALLER, scripts / INSTALLER.name)
    remote = tmp_path / "installer fixture remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    subprocess.run(["git", "init", "--initial-branch", "main", str(repo)], check=True, capture_output=True)
    run_git(repo, "config", "user.name", "Installer Test")
    run_git(repo, "config", "user.email", "installer-test@example.invalid")
    (repo / "README.md").write_text("installer fixture\n", encoding="utf-8")
    run_git(repo, "add", "--", "README.md")
    run_git(repo, "commit", "-m", "initial")
    run_git(repo, "remote", "add", "origin", str(remote))
    run_git(repo, "push", "--set-upstream", "origin", "main")
    return repo, scripts, remote


def install_hermes_stub(tmp_path: Path) -> tuple[Path, Path]:
    fake_bin = tmp_path / "fake bin"
    fake_bin.mkdir()
    calls_log = tmp_path / "hermes calls.jsonl"
    fake_hermes = fake_bin / "hermes"
    fake_hermes.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "with open(os.environ['FAKE_HERMES_LOG'], 'a', encoding='utf-8') as f: f.write(json.dumps(sys.argv[1:])+'\\n')\n"
        "sys.exit(1 if sys.argv[1:3] == ['config','get'] else 0)\n",
        encoding="utf-8",
    )
    fake_hermes.chmod(0o755)
    return fake_bin, calls_log


def test_installer_refuses_main_checkout(tmp_path: Path) -> None:
    repo, scripts, _ = installer_fixture(tmp_path)
    home = tmp_path / "hermes profile"
    (home / "skills").mkdir(parents=True)
    env = dict(os.environ, HERMES_HOME=str(home))

    result = subprocess.run(
        [sys.executable, str(scripts / INSTALLER.name), "--machine", MACHINE],
        env=env, capture_output=True, text=True, check=False,
    )

    assert result.returncode == 1
    assert "never writes main" in (result.stdout + result.stderr)
    assert not (home / "skill-repo-sync.json").exists()


def test_installer_installs_on_machine_branch_without_global_consent(tmp_path: Path) -> None:
    repo, scripts, remote = installer_fixture(tmp_path)
    run_git(repo, "checkout", "-b", f"machine/{MACHINE}")
    run_git(repo, "push", "--set-upstream", "origin", f"machine/{MACHINE}")
    home = tmp_path / "hermes profile with spaces"
    (home / "skills").mkdir(parents=True)
    write_ledger(home, [])
    fake_bin, calls_log = install_hermes_stub(tmp_path)
    python_link = tmp_path / "python interpreter"
    python_link.symlink_to(sys.executable)
    env = dict(os.environ, HERMES_HOME=str(home), FAKE_HERMES_LOG=str(calls_log))
    env["PATH"] = str(fake_bin) + os.pathsep + env.get("PATH", "")

    result = subprocess.run(
        [sys.executable, str(scripts / INSTALLER.name), "--machine", MACHINE,
         "--apply-config", "--python", str(python_link)],
        env=env, capture_output=True, text=True, check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    state = json.loads((home / "skill-repo-sync.json").read_text(encoding="utf-8"))
    assert state["machine"] == MACHINE and state["sync_model"] == "stage-curate-v2"
    assert state["ledger_cursor"] == 0
    wrapper_text = (home / "bin" / "skill-repo-sync").read_text(encoding="utf-8")
    assert f"'{scripts / ENGINE.name}'" in wrapper_text
    calls = [json.loads(line) for line in calls_log.read_text(encoding="utf-8").splitlines()]
    assert all("hooks_auto_accept" not in call for call in calls)
    set_calls = [call for call in calls if call[:2] == ["config", "set"]]
    # exactly two: on_session_start armed, v1 lifecycle emptied
    assert len(set_calls) == 2
    pairs = {c[2]: c[3] for c in set_calls}
    session_key = next(k for k in pairs if "on_session_start" in k)
    assert "--sync-from-main" in pairs[session_key]
    lifecycle_key = next(k for k in pairs if "on_skill_lifecycle" in k)
    assert pairs[lifecycle_key] == "[]"


def test_library_audit_expands_wildcard_support_file_references(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    skill = root / "demo"
    (skill / "references").mkdir(parents=True)
    (skill / "references" / "enterprise_one.md").write_text("one\n", encoding="utf-8")
    (skill / "references" / "enterprise_two.md").write_text("two\n", encoding="utf-8")
    (skill / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Test.\n---\n\nSee `references/enterprise_*.md`.\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(AUDITOR), str(root), "--json"], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout or result.stderr
    report = json.loads(result.stdout)
    assert report["summary"]["errors"] == 0
