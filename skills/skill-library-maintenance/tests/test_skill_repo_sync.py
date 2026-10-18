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
AUDITOR = SKILL_ROOT / "scripts" / "audit-skill-library.py"


def run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return result


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def setup_repo(tmp_path: Path, branch: str = "main") -> tuple[Path, Path, Path]:
    repo = tmp_path / "shared skill repo"
    remote = tmp_path / "shared skill remote.git"
    target = repo / "skills" / "demo" / "SKILL.md"
    target.parent.mkdir(parents=True)
    target.write_text("name: demo\n\nOriginal text.\n", encoding="utf-8")

    subprocess.run(["git", "init", "--initial-branch", branch, str(repo)], check=True, capture_output=True)
    run_git(repo, "config", "user.name", "Sync Test")
    run_git(repo, "config", "user.email", "sync-test@example.invalid")
    run_git(repo, "add", "--", "skills/demo/SKILL.md")
    run_git(repo, "commit", "-m", "initial")
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    run_git(repo, "remote", "add", "origin", str(remote))
    run_git(repo, "push", "--set-upstream", "origin", branch)
    return repo, remote, target


def write_state(home: Path, repos: list[Path], cursor: int = 0) -> Path:
    (home / "skills").mkdir(parents=True, exist_ok=True)
    state_path = home / "skill-repo-sync.json"
    state_path.write_text(
        json.dumps(
            {
                "version": "1.0.2",
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


def entry_for(target: Path, before: str, after: str, entry_id: str = "entry-1", ts: str = "2026-10-18T10:00:00+00:00") -> dict:
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


def remote_head(repo: Path, branch: str = "main") -> str:
    result = run_git(repo, "ls-remote", "origin", f"refs/heads/{branch}")
    return result.stdout.split()[0]


def test_dry_run_does_not_mutate_cursor_git_or_remote(tmp_path: Path) -> None:
    repo, _, target = setup_repo(tmp_path)
    before = target.read_text(encoding="utf-8")
    after = "name: demo\n\nReviewed guidance unique to this test.\n"
    target.write_text(after, encoding="utf-8")
    home = tmp_path / "hermes home"
    state_path = write_state(home, [repo], cursor=0)
    write_ledger(home, [entry_for(target, before, after)])

    state_before = state_path.read_bytes()
    head_before = run_git(repo, "rev-parse", "HEAD").stdout.strip()
    remote_before = remote_head(repo)
    index_before = run_git(repo, "diff", "--cached", "--binary").stdout
    worktree_before = run_git(repo, "status", "--porcelain").stdout

    result = invoke_engine(home, "--safety", "--dry-run", "--verbose")

    assert result.returncode == 0, result.stderr or result.stdout
    assert "would commit" in result.stdout
    assert state_path.read_bytes() == state_before
    assert run_git(repo, "rev-parse", "HEAD").stdout.strip() == head_before
    assert remote_head(repo) == remote_before
    assert run_git(repo, "diff", "--cached", "--binary").stdout == index_before
    assert run_git(repo, "status", "--porcelain").stdout == worktree_before


def test_successful_publish_commits_and_advances_cursor(tmp_path: Path) -> None:
    repo, _, target = setup_repo(tmp_path)
    before = target.read_text(encoding="utf-8")
    after = "name: demo\n\nReviewed guidance unique to this test.\n"
    target.write_text(after, encoding="utf-8")
    home = tmp_path / "hermes home"
    state_path = write_state(home, [repo], cursor=0)
    write_ledger(home, [entry_for(target, before, after)])

    result = invoke_engine(home, "--safety", "--verbose")

    assert result.returncode == 0, result.stderr or result.stdout
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["ledger_cursor"] == 1
    assert run_git(repo, "status", "--porcelain").stdout == ""
    assert remote_head(repo) == run_git(repo, "rev-parse", "HEAD").stdout.strip()


def test_gate_block_keeps_ledger_entry_retryable(tmp_path: Path) -> None:
    repo, _, target = setup_repo(tmp_path)
    before = target.read_text(encoding="utf-8")
    after = "name: demo\n\nDo not publish /Users/testuser/private/path.\n"
    target.write_text(after, encoding="utf-8")
    home = tmp_path / "hermes home"
    state_path = write_state(home, [repo], cursor=0)
    write_ledger(home, [entry_for(target, before, after)])
    head_before = run_git(repo, "rev-parse", "HEAD").stdout.strip()
    remote_before = remote_head(repo)

    result = invoke_engine(home, "--safety", "--verbose")

    assert result.returncode == 10
    assert "instance-pointer" in result.stdout
    assert json.loads(state_path.read_text(encoding="utf-8"))["ledger_cursor"] == 0
    assert run_git(repo, "rev-parse", "HEAD").stdout.strip() == head_before
    assert remote_head(repo) == remote_before
    report = json.loads((repo / ".git" / "hermes-skill-sync-report.json").read_text(encoding="utf-8"))
    assert report["findings"]


def test_unledgered_edit_to_candidate_file_is_held(tmp_path: Path) -> None:
    repo, _, target = setup_repo(tmp_path)
    before = target.read_text(encoding="utf-8")
    reviewed = "name: demo\n\nReviewed guidance unique to this test.\n"
    target.write_text(reviewed, encoding="utf-8")
    target.write_text(reviewed + "Manual change not covered by the ledger.\n", encoding="utf-8")
    home = tmp_path / "hermes home"
    state_path = write_state(home, [repo], cursor=0)
    write_ledger(home, [entry_for(target, before, reviewed)])
    head_before = run_git(repo, "rev-parse", "HEAD").stdout.strip()
    remote_before = remote_head(repo)

    result = invoke_engine(home, "--safety", "--verbose")

    assert result.returncode == 10
    assert "hash" in result.stdout.lower() or "ledger" in result.stdout.lower()
    assert json.loads(state_path.read_text(encoding="utf-8"))["ledger_cursor"] == 0
    assert run_git(repo, "rev-parse", "HEAD").stdout.strip() == head_before
    assert remote_head(repo) == remote_before
    assert run_git(repo, "diff", "--cached", "--name-only").stdout == ""


def test_preexisting_staged_change_stops_publisher(tmp_path: Path) -> None:
    repo, _, target = setup_repo(tmp_path)
    before = target.read_text(encoding="utf-8")
    after = "name: demo\n\nReviewed guidance unique to this test.\n"
    target.write_text(after, encoding="utf-8")
    (repo / "unrelated.txt").write_text("operator staged this\n", encoding="utf-8")
    run_git(repo, "add", "--", "unrelated.txt")
    home = tmp_path / "hermes home"
    state_path = write_state(home, [repo], cursor=0)
    write_ledger(home, [entry_for(target, before, after)])
    head_before = run_git(repo, "rev-parse", "HEAD").stdout.strip()

    result = invoke_engine(home, "--safety", "--verbose")

    assert result.returncode == 12
    assert "staged" in (result.stdout + result.stderr).lower()
    assert json.loads(state_path.read_text(encoding="utf-8"))["ledger_cursor"] == 0
    assert run_git(repo, "rev-parse", "HEAD").stdout.strip() == head_before
    assert run_git(repo, "diff", "--cached", "--name-only").stdout.strip() == "unrelated.txt"


def test_unexpected_branch_stops_publisher(tmp_path: Path) -> None:
    repo, _, target = setup_repo(tmp_path, branch="feature/test")
    before = target.read_text(encoding="utf-8")
    after = "name: demo\n\nReviewed guidance unique to this test.\n"
    target.write_text(after, encoding="utf-8")
    home = tmp_path / "hermes home"
    state_path = write_state(home, [repo], cursor=0)
    write_ledger(home, [entry_for(target, before, after)])
    head_before = run_git(repo, "rev-parse", "HEAD").stdout.strip()
    remote_before = remote_head(repo, "feature/test")

    result = invoke_engine(home, "--safety", "--verbose")

    assert result.returncode == 12
    assert "main" in (result.stdout + result.stderr)
    assert json.loads(state_path.read_text(encoding="utf-8"))["ledger_cursor"] == 0
    assert run_git(repo, "rev-parse", "HEAD").stdout.strip() == head_before
    assert remote_head(repo, "feature/test") == remote_before


def test_pull_only_failure_is_nonzero_and_visible(tmp_path: Path) -> None:
    repo, _, _ = setup_repo(tmp_path)
    home = tmp_path / "hermes home"
    write_state(home, [repo])
    run_git(repo, "remote", "set-url", "origin", str(tmp_path / "missing remote.git"))

    result = invoke_engine(home, "--pull-only", "--hook")

    assert result.returncode == 12
    assert result.stderr
    assert "pull" in result.stderr.lower() or "remote" in result.stderr.lower()


def test_installer_requires_explicit_historical_ledger_bootstrap(tmp_path: Path) -> None:
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
    home = tmp_path / "hermes profile"
    (home / "skills").mkdir(parents=True)
    write_ledger(home, [{"id": "historic-1", "before": [], "after": [], "ts": "2026-10-18T10:00:00+00:00"}])
    env = dict(os.environ, HERMES_HOME=str(home))

    result = subprocess.run(
        [sys.executable, str(scripts / INSTALLER.name)], env=env, capture_output=True, text=True, check=False
    )

    assert result.returncode != 0
    assert "bootstrap" in (result.stdout + result.stderr).lower()
    assert not (home / "skill-repo-sync.json").exists()
    assert not (home / "bin" / "skill-repo-sync").exists()


def test_installer_bootstrap_is_explicit_and_does_not_enable_global_consent(tmp_path: Path) -> None:
    repo = tmp_path / "installer fixture with spaces"
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

    home = tmp_path / "hermes profile with spaces"
    (home / "skills").mkdir(parents=True)
    write_ledger(home, [{"id": "historic-1", "before": [], "after": [], "ts": "2026-10-18T10:00:00+00:00"}])
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
    python_link = tmp_path / "python interpreter"
    python_link.symlink_to(sys.executable)
    env = dict(os.environ, HERMES_HOME=str(home), FAKE_HERMES_LOG=str(calls_log))
    env["PATH"] = str(fake_bin) + os.pathsep + env.get("PATH", "")

    result = subprocess.run(
        [sys.executable, str(scripts / INSTALLER.name), "--bootstrap-current-ledger", "--apply-config", "--python", str(python_link)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    state = json.loads((home / "skill-repo-sync.json").read_text(encoding="utf-8"))
    assert state["ledger_cursor"] == 1
    wrapper = home / "bin" / "skill-repo-sync"
    wrapper_text = wrapper.read_text(encoding="utf-8")
    assert f"'{python_link}'" in wrapper_text
    assert f"'{scripts / ENGINE.name}'" in wrapper_text
    calls = [json.loads(line) for line in calls_log.read_text(encoding="utf-8").splitlines()]
    assert all("hooks_auto_accept" not in call for call in calls)
    set_calls = [call for call in calls if call[:2] == ["config", "set"]]
    assert len(set_calls) == 2


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


def test_blocked_entry_can_be_retried_after_review_correction(tmp_path: Path) -> None:
    repo, _, target = setup_repo(tmp_path)
    original = target.read_text(encoding="utf-8")
    blocked = "name: demo\n\nDo not publish /Users/testuser/private/path.\n"
    corrected = "name: demo\n\nReviewed guidance corrected in the same review run.\n"
    target.write_text(blocked, encoding="utf-8")
    first = entry_for(target, original, blocked, "entry-1", "2026-10-18T10:00:00+00:00")
    home = tmp_path / "hermes home"
    state_path = write_state(home, [repo], cursor=0)
    write_ledger(home, [first])

    first_result = invoke_engine(home, "--safety", "--verbose")

    assert first_result.returncode == 10
    assert json.loads(state_path.read_text(encoding="utf-8"))["ledger_cursor"] == 0

    target.write_text(corrected, encoding="utf-8")
    second = entry_for(target, blocked, corrected, "entry-2", "2026-10-18T10:00:30+00:00")
    write_ledger(home, [first, second])
    second_result = invoke_engine(home, "--safety", "--verbose")

    assert second_result.returncode == 0, second_result.stderr or second_result.stdout
    assert json.loads(state_path.read_text(encoding="utf-8"))["ledger_cursor"] == 2
    assert remote_head(repo) == run_git(repo, "rev-parse", "HEAD").stdout.strip()


def test_multiple_pending_review_runs_for_one_file_fail_closed(tmp_path: Path) -> None:
    repo, _, target = setup_repo(tmp_path)
    original = target.read_text(encoding="utf-8")
    first_text = "name: demo\n\nFirst reviewed revision.\n"
    final_text = "name: demo\n\nSecond reviewed revision.\n"
    target.write_text(final_text, encoding="utf-8")
    entries = [
        entry_for(target, original, first_text, "entry-1", "2026-10-18T10:00:00+00:00"),
        entry_for(target, first_text, final_text, "entry-2", "2026-10-18T10:05:00+00:00"),
    ]
    home = tmp_path / "hermes home"
    state_path = write_state(home, [repo], cursor=0)
    write_ledger(home, entries)
    head_before = run_git(repo, "rev-parse", "HEAD").stdout.strip()

    result = invoke_engine(home, "--safety", "--verbose")

    assert result.returncode == 10
    assert "multiple review runs" in result.stdout
    assert json.loads(state_path.read_text(encoding="utf-8"))["ledger_cursor"] == 0
    assert run_git(repo, "rev-parse", "HEAD").stdout.strip() == head_before


def test_push_failure_is_reported_and_cursor_remains_pending(tmp_path: Path) -> None:
    repo, remote, target = setup_repo(tmp_path)
    before = target.read_text(encoding="utf-8")
    after = "name: demo\n\nReviewed guidance unique to this test.\n"
    target.write_text(after, encoding="utf-8")
    home = tmp_path / "hermes home"
    state_path = write_state(home, [repo], cursor=0)
    write_ledger(home, [entry_for(target, before, after)])
    remote_before = remote_head(repo)
    hook = remote / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)

    result = invoke_engine(home, "--safety", "--hook")

    assert result.returncode == 12
    assert "push failed" in result.stderr.lower()
    assert json.loads(state_path.read_text(encoding="utf-8"))["ledger_cursor"] == 0
    assert remote_head(repo) == remote_before
    assert run_git(repo, "rev-parse", "HEAD").stdout.strip() != remote_before


def test_pull_network_failure_does_not_write_conflict_marker(tmp_path: Path) -> None:
    repo, _, target = setup_repo(tmp_path)
    before = target.read_text(encoding="utf-8")
    after = "name: demo\n\nReviewed guidance unique to this test.\n"
    target.write_text(after, encoding="utf-8")
    home = tmp_path / "hermes home"
    state_path = write_state(home, [repo], cursor=0)
    write_ledger(home, [entry_for(target, before, after)])
    run_git(repo, "remote", "set-url", "origin", str(tmp_path / "missing remote.git"))

    result = invoke_engine(home, "--safety", "--hook")

    assert result.returncode == 12
    assert "fetch failed" in result.stderr.lower()
    assert not (repo / ".git" / "hermes-skill-sync-conflict.json").exists()
    assert json.loads(state_path.read_text(encoding="utf-8"))["ledger_cursor"] == 0


def test_real_rebase_conflict_is_aborted_and_marked(tmp_path: Path) -> None:
    repo, remote, target = setup_repo(tmp_path)
    before = target.read_text(encoding="utf-8")
    local_after = "name: demo\n\nLocal reviewed replacement.\n"
    target.write_text(local_after, encoding="utf-8")
    home = tmp_path / "hermes home"
    state_path = write_state(home, [repo], cursor=0)
    write_ledger(home, [entry_for(target, before, local_after)])

    other = tmp_path / "other installation"
    subprocess.run(["git", "clone", str(remote), str(other)], check=True, capture_output=True)
    run_git(other, "config", "user.name", "Other Install")
    run_git(other, "config", "user.email", "other-install@example.invalid")
    remote_after = "name: demo\n\nRemote reviewed replacement.\n"
    (other / "skills" / "demo" / "SKILL.md").write_text(remote_after, encoding="utf-8")
    run_git(other, "add", "--", "skills/demo/SKILL.md")
    run_git(other, "commit", "-m", "remote review")
    run_git(other, "push", "origin", "main")

    result = invoke_engine(home, "--safety", "--hook")

    assert result.returncode == 11
    assert "conflict" in result.stderr.lower()
    marker = repo / ".git" / "hermes-skill-sync-conflict.json"
    assert marker.is_file()
    assert "conflict" in json.loads(marker.read_text(encoding="utf-8"))["note"]
    assert json.loads(state_path.read_text(encoding="utf-8"))["ledger_cursor"] == 0
    assert run_git(repo, "status", "--porcelain").stdout == ""
    assert run_git(repo, "show", "HEAD:skills/demo/SKILL.md").stdout == local_after
    assert run_git(other, "show", "HEAD:skills/demo/SKILL.md").stdout == remote_after

    merge = subprocess.run(["git", "-C", str(repo), "merge", "origin/main"], capture_output=True, text=True, check=False)
    assert merge.returncode != 0
    reconciled = "name: demo\n\nLocal reviewed replacement.\nRemote reviewed replacement.\n"
    target.write_text(reconciled, encoding="utf-8")
    run_git(repo, "add", "--", "skills/demo/SKILL.md")
    run_git(repo, "commit", "-m", "reconcile both review lessons")

    retry = invoke_engine(home, "--safety", "--hook")

    assert retry.returncode == 0, retry.stderr or retry.stdout
    assert json.loads(state_path.read_text(encoding="utf-8"))["ledger_cursor"] == 1
    assert not marker.exists()
    assert remote_head(repo) == run_git(repo, "rev-parse", "HEAD").stdout.strip()
    assert "Local reviewed" in target.read_text(encoding="utf-8")
    assert "Remote reviewed" in target.read_text(encoding="utf-8")
