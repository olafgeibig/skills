from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shlex
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_ROOT = REPO_ROOT / "skills" / "skill-library-maintenance"
ENGINE = SKILL_ROOT / "scripts" / "skill-repo-sync.py"
CORE = SKILL_ROOT / "scripts" / "skill_repo_workflow.py"
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
    remote_before = remote_head(repo, f"machine/{MACHINE}")

    result = invoke_engine(home, "--stage", "--verbose")

    assert result.returncode == 0, result.stderr or result.stdout
    assert "holding push" in result.stdout + result.stderr
    state = json.loads((home / "skill-repo-sync.json").read_text(encoding="utf-8"))
    assert state["ledger_cursor"] == 1
    assert run_git(repo, "status", "--porcelain").stdout == ""
    # push-gate: the commit exists locally, the remote branch is untouched
    assert run_git(repo, "rev-parse", "HEAD").stdout.strip() != remote_before
    assert remote_head(repo, f"machine/{MACHINE}") == remote_before
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
    state_path = write_state(home, [repo])
    state_before = state_path.read_bytes()
    head_before = run_git(repo, "rev-parse", "HEAD").stdout.strip()
    dirty_before = target.read_bytes()

    result = invoke_engine(home, "--stage")

    assert result.returncode == 12
    output = result.stdout + result.stderr
    assert "stage never touches main" in output
    assert "branch policy" in output
    assert run_git(repo, "rev-parse", "HEAD").stdout.strip() == head_before
    assert run_git(repo, "diff", "--cached", "--name-only").stdout == ""
    assert target.read_bytes() == dirty_before
    assert state_path.read_bytes() == state_before


def test_stage_refuses_clean_main_as_branch_policy(tmp_path: Path) -> None:
    """A clean main is not healthy transport staging — the sweep refuses it like a dirty one."""
    repo, _, _, home = setup_repo(tmp_path)
    run_git(repo, "checkout", "main")
    state_path = write_state(home, [repo])
    state_before = state_path.read_bytes()
    head_before = run_git(repo, "rev-parse", "HEAD").stdout.strip()

    result = invoke_engine(home, "--stage", "--verbose")

    assert result.returncode == 12
    output = result.stdout + result.stderr
    assert "branch policy" in output and "main" in output
    assert run_git(repo, "rev-parse", "HEAD").stdout.strip() == head_before
    assert run_git(repo, "status", "--porcelain").stdout == ""
    assert state_path.read_bytes() == state_before


def test_stage_excludes_refactor_branch(tmp_path: Path) -> None:
    """A deliberate refactor worktree is excluded from the sweep — no commit, index, state or
    branch switch, and the unfinished tracked edit stays exactly as it was."""
    repo, _, target, home = setup_repo(tmp_path)
    run_git(repo, "checkout", "-b", "refactor/topic")
    target.write_text("name: demo\n\nUnfinished refactor edit.\n", encoding="utf-8")
    state_path = write_state(home, [repo])
    state_before = state_path.read_bytes()
    head_before = run_git(repo, "rev-parse", "HEAD").stdout.strip()
    bytes_before = target.read_bytes()

    result = invoke_engine(home, "--stage")

    assert result.returncode == 0, result.stderr or result.stdout
    assert "refactor branch: excluded from sweep" in result.stdout + result.stderr
    assert run_git(repo, "rev-parse", "HEAD").stdout.strip() == head_before
    assert run_git(repo, "diff", "--cached", "--name-only").stdout == ""
    assert run_git(repo, "status", "--porcelain").stdout == " M skills/demo/SKILL.md\n"
    assert target.read_bytes() == bytes_before
    assert state_path.read_bytes() == state_before
    # the exclusion never checks anything out
    assert run_git(repo, "branch", "--show-current").stdout.strip() == "refactor/topic"


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


def test_stage_skips_missing_untracked_ledger_path(tmp_path: Path) -> None:
    """One stale ledger path (missing, never tracked) must not block the valid tracked edit."""
    repo, _, target, home = setup_repo(tmp_path)
    original = target.read_text(encoding="utf-8")
    target.write_text("name: demo\n\nValid tracked edit beside a stale ledger path.\n",
                      encoding="utf-8")
    missing = repo / "skills" / "demo" / "removed-long-ago.md"
    write_state(home, [repo])
    write_ledger(home, [
        {"id": "entry-stale", "ts": "2026-11-01T09:00:00+00:00", "skill": "demo",
         "action": "patch", "before": [],
         "after": [{"path": str(missing), "sha256": sha("gone")}]},
        entry_for(target, original, target.read_text(encoding="utf-8"), entry_id="entry-valid"),
    ])

    result = invoke_engine(home, "--stage", "--verbose")

    assert result.returncode == 0, result.stderr or result.stdout
    committed = run_git(repo, "show", "--name-only", "--format=", "HEAD").stdout.split()
    assert committed == ["skills/demo/SKILL.md"]
    assert run_git(repo, "status", "--porcelain").stdout == ""
    report = json.loads((home / "stage-report.json").read_text(encoding="utf-8"))
    assert [s["path"] for s in report["skipped_ledger_paths"]] == \
        ["skills/demo/removed-long-ago.md"]
    state = json.loads((home / "skill-repo-sync.json").read_text(encoding="utf-8"))
    assert state["ledger_cursor"] == 2


def test_stage_preserves_tracked_deletion(tmp_path: Path) -> None:
    """A ledger path that is missing but still tracked is a real deletion — never a stale skip."""
    repo, _, target, home = setup_repo(tmp_path)
    extra = repo / "skills" / "demo" / "obsolete.md"
    extra.write_text("retired guidance\n", encoding="utf-8")
    run_git(repo, "add", "--", "skills/demo/obsolete.md")
    run_git(repo, "commit", "-m", "add obsolete file")
    run_git(repo, "push")
    original = target.read_text(encoding="utf-8")
    target.write_text("name: demo\n\nEdit beside the deletion.\n", encoding="utf-8")
    extra.unlink()
    write_state(home, [repo])
    write_ledger(home, [
        {"id": "entry-delete", "ts": "2026-11-01T09:00:00+00:00", "skill": "demo",
         "action": "remove", "after": [],
         "before": [{"path": str(extra), "sha256": sha("retired guidance\n")}]},
        entry_for(target, original, target.read_text(encoding="utf-8"), entry_id="entry-edit"),
    ])

    result = invoke_engine(home, "--stage")

    assert result.returncode == 0, result.stderr or result.stdout
    status = run_git(repo, "show", "--name-status", "--format=", "HEAD").stdout.split()
    assert "D" in status and "skills/demo/obsolete.md" in status
    assert not extra.exists()
    assert run_git(repo, "status", "--porcelain").stdout == ""
    state = json.loads((home / "skill-repo-sync.json").read_text(encoding="utf-8"))
    assert state["ledger_cursor"] == 2


def test_stage_whitespace_failure_is_retryable(tmp_path: Path) -> None:
    """A whitespace failure undoes only this run's index entries; correcting and retrying succeeds."""
    repo, _, target, home = setup_repo(tmp_path)
    original = target.read_text(encoding="utf-8")
    bad = "name: demo\n\nTrailing space stays here. \n"
    target.write_text(bad, encoding="utf-8")
    write_state(home, [repo])
    write_ledger(home, [entry_for(target, original, bad)])

    first = invoke_engine(home, "--stage")

    assert first.returncode == 12
    assert "whitespace" in (first.stdout + first.stderr).lower()
    assert run_git(repo, "diff", "--cached", "--name-only").stdout == ""
    assert target.read_text(encoding="utf-8") == bad
    assert json.loads((home / "skill-repo-sync.json").read_text(encoding="utf-8"))["ledger_cursor"] == 0

    target.write_text("name: demo\n\nWhitespace fixed, retry succeeds.\n", encoding="utf-8")
    second = invoke_engine(home, "--stage")

    assert second.returncode == 0, second.stderr or second.stdout
    assert run_git(repo, "status", "--porcelain").stdout == ""
    assert json.loads((home / "skill-repo-sync.json").read_text(encoding="utf-8"))["ledger_cursor"] == 1


def test_stage_commit_failure_leaves_index_clean(tmp_path: Path) -> None:
    """A failed commit restores the empty index (only this run's paths), so a retry can run."""
    repo, _, target, home = setup_repo(tmp_path)
    original = target.read_text(encoding="utf-8")
    target.write_text("name: demo\n\nContent whose commit will fail.\n", encoding="utf-8")
    write_state(home, [repo])
    write_ledger(home, [entry_for(target, original, target.read_text(encoding="utf-8"))])
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)

    failed = invoke_engine(home, "--stage")

    assert failed.returncode == 12
    assert "commit failed" in (failed.stdout + failed.stderr)
    assert run_git(repo, "diff", "--cached", "--name-only").stdout == ""
    assert run_git(repo, "status", "--porcelain").stdout == " M skills/demo/SKILL.md\n"
    assert json.loads((home / "skill-repo-sync.json").read_text(encoding="utf-8"))["ledger_cursor"] == 0

    hook.unlink()
    retry = invoke_engine(home, "--stage")
    assert retry.returncode == 0, retry.stderr or retry.stdout
    assert run_git(repo, "status", "--porcelain").stdout == ""
    assert json.loads((home / "skill-repo-sync.json").read_text(encoding="utf-8"))["ledger_cursor"] == 1


def test_stage_commit_failure_preserves_added_deleted_and_modified_work(tmp_path: Path) -> None:
    """Staged restore reverses this attempt's mixed index changes, not worktree changes."""
    repo, _, target, home = setup_repo(tmp_path)
    deleted = repo / "retired.md"
    deleted.write_bytes(b"previously tracked content\n")
    run_git(repo, "add", "--", "retired.md")
    run_git(repo, "commit", "-m", "tracked deletion fixture")
    deleted.unlink()
    target.write_bytes(b"modified operator content\n")
    added = repo / "new-file.md"
    added.write_bytes(b"new operator content\n")
    state = write_state(home, [repo])
    state_before = state.read_bytes()
    head_before = run_git(repo, "rev-parse", "HEAD").stdout
    expected = {str(p.relative_to(repo)): p.read_bytes() for p in (target, added)}
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)

    failed = invoke_engine(home, "--stage")

    assert failed.returncode == 12, failed.stdout + failed.stderr
    assert "git commit failed" in failed.stdout + failed.stderr
    assert run_git(repo, "rev-parse", "HEAD").stdout == head_before
    assert run_git(repo, "diff", "--cached", "--name-only").stdout == ""
    assert {path: (repo / path).read_bytes() for path in expected} == expected
    assert not deleted.exists()
    assert state.read_bytes() == state_before

    hook.unlink()
    retried = invoke_engine(home, "--stage")
    assert retried.returncode == 0, retried.stdout + retried.stderr
    assert run_git(repo, "status", "--porcelain").stdout == ""
    assert not deleted.exists()
    assert {path: (repo / path).read_bytes() for path in expected} == expected


def test_stage_cursor_ignores_concurrent_ledger_append(tmp_path: Path) -> None:
    """The cursor advances through the entries snapshot read before staging; a row appended by
    another writer during the commit stays pending."""
    repo, _, target, home = setup_repo(tmp_path)
    original = target.read_text(encoding="utf-8")
    target.write_text("name: demo\n\nEdit staged while another writer appends.\n", encoding="utf-8")
    write_state(home, [repo])
    write_ledger(home, [entry_for(target, original, target.read_text(encoding="utf-8"),
                                  entry_id="entry-1")])
    ledger = home / "skills" / ".curator_ledger.jsonl"
    late = entry_for(target, original, target.read_text(encoding="utf-8"), entry_id="entry-late")
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text(
        f"#!{sys.executable}\n"
        "import json\n"
        "from pathlib import Path\n"
        f"p = Path({str(ledger)!r})\n"
        "p.write_text(p.read_text(encoding='utf-8') + json.dumps(" + repr(late) + ") + '\\n', "
        "encoding='utf-8')\n",
        encoding="utf-8")
    hook.chmod(0o755)

    result = invoke_engine(home, "--stage")

    assert result.returncode == 0, result.stderr or result.stdout
    rows = [line for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 2                                   # the other writer's row exists
    state = json.loads((home / "skill-repo-sync.json").read_text(encoding="utf-8"))
    assert state["ledger_cursor"] == 1                      # ... and stays pending this attempt


def test_stage_never_pushes(tmp_path: Path) -> None:
    """Push-gate: stage secures work locally; the pre-consolidation run owns the push."""
    repo, _, target, home = setup_repo(tmp_path)
    original = target.read_text(encoding="utf-8")
    target.write_text("name: demo\n\nReviewed hold-for-pre-consolidation change.\n", encoding="utf-8")
    write_state(home, [repo])
    write_ledger(home, [entry_for(target, original, target.read_text(encoding="utf-8"), entry_id="entry-1")])
    remote_before = remote_head(repo, f"machine/{MACHINE}")

    first = invoke_engine(home, "--stage")
    assert first.returncode == 0, first.stderr or first.stdout
    # one local commit, remote untouched
    assert remote_head(repo, f"machine/{MACHINE}") == remote_before
    assert len(run_git(repo, "log", "--format=%h", f"{remote_before}..HEAD").stdout.splitlines()) == 1
    assert json.loads((home / "skill-repo-sync.json").read_text(encoding="utf-8"))["ledger_cursor"] == 1

    # a second sweep with new content lands a SECOND local commit — still no push
    target.write_text("name: demo\n\nSecond reviewed change after the first local commit.\n", encoding="utf-8")
    write_ledger(home, [
        entry_for(target, original, target.read_text(encoding="utf-8"), entry_id="entry-1"),
        entry_for(target, original, target.read_text(encoding="utf-8"), entry_id="entry-2"),
    ])
    second = invoke_engine(home, "--stage")
    assert second.returncode == 0, second.stderr or second.stdout
    assert remote_head(repo, f"machine/{MACHINE}") == remote_before
    assert len(run_git(repo, "log", "--format=%h", f"{remote_before}..HEAD").stdout.splitlines()) == 2


# --- refresh (merge ancestry, never reset/rebase) -------------------------------------------------


def load_core():
    spec = importlib.util.spec_from_file_location("producer_test_workflow", CORE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def publish_merge(repo: Path, remote: Path, tmp_path: Path, *, quote: str) -> str:
    """Create a real v3 publisher merge P (parents M,T) through the shared core.

    The producer test files deliberately do not hand-build the integration merge:
    refresh has to work against the exact artifact the publisher produces.
    """
    core = load_core()
    publisher = tmp_path / "producer publisher clone"
    subprocess.run(["git", "clone", "-q", "-b", "main", str(remote), str(publisher)], check=True)
    run_git(publisher, "config", "user.name", "Publisher")
    run_git(publisher, "config", "user.email", "publisher@example.invalid")
    store = tmp_path / "producer publisher store"
    vault = tmp_path / "producer report vault"
    store.mkdir()
    vault.mkdir()
    config = {
        "schema": 3,
        "repo_id": "producer-refresh-fixture",
        "remote": "origin",
        "publisher_repo": str(publisher),
        "runtime_roots": [str(repo)],
        "policy": "skill-review-v1",
        "publisher_identity": {"machine": "publisher-test", "profile": "default",
                               "scope": "shared-generic"},
        "sources": [{"ref": f"refs/heads/machine/{MACHINE}", "machine": MACHINE,
                     "profile": "default", "scope": "shared-generic", "enabled": True}],
        "report": {"vault": "fixture", "vault_root": str(vault),
                   "directory": "projects/hermes-agent/reports"},
    }
    (store / "publisher.json").write_text(json.dumps(config), encoding="utf-8")
    candidate = core.capture(publisher, store, config["sources"][0])
    candidate = core.prepare(publisher, store, candidate)
    worktree = Path(candidate["worktree"])
    review = {
        "schema": 1,
        "candidate_id": candidate["id"],
        "main_sha": candidate["main_sha"],
        "source_sha": candidate["source_sha"],
        "summary": "Accept the producer's generic lesson",
        "files": [{
            "path": "skills/demo/SKILL.md",
            "change_type": "addition",
            "decision": "accept",
            "source_anchors": [{"ref": candidate["source_sha"], "path": "skills/demo/SKILL.md",
                                "quote": quote}],
            "reason": "Generic skill guidance",
            "replacements": [],
        }],
    }
    core.validate_review(candidate, review, publisher, worktree)
    checks = core.run_checks(candidate, worktree)
    validation = core.validate_tree(candidate, worktree, review)
    core.record_review(store, candidate["id"], review, checks, validation)
    current = core.load_candidate(store, candidate["id"])
    text = core.render_review(current, review, checks, validation["tree"])
    note = vault / current["report_relative_path"]
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(text, encoding="utf-8")
    core.verify_report(current, text, vault)
    result = core.publish(publisher, store, candidate["id"], vault)
    assert result["status"] == "published"
    return result["result_sha"]


def write_history_review(path: Path, tip: str, commits: list[str],
                         classification: str = "generic-only") -> Path:
    """The agent's semantic profile-scope review for the whole unpublished range."""
    payload = {
        "schema": 1,
        "tip": tip,
        "scope": "shared-generic",
        "summary": "Every unpublished commit classified for profile scope.",
        "commits": [{"sha": sha, "classification": classification,
                     "reason": "Only generic skill guidance across this commit."}
                    for sha in commits],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def read_state(home: Path) -> dict:
    return json.loads((home / "skill-repo-sync.json").read_text(encoding="utf-8"))


def test_refresh_refuses_held_producer_lock_without_writes(tmp_path: Path) -> None:
    """A held producer lock blocks an otherwise eligible FF before even fetching."""
    repo, remote, _, home = setup_repo(tmp_path)
    write_state(home, [repo])
    publisher = tmp_path / "refresh publisher"
    run_git(tmp_path, "clone", "-q", "-b", "main", str(remote), str(publisher))
    run_git(publisher, "config", "user.name", "Publisher")
    run_git(publisher, "config", "user.email", "publisher@example.invalid")
    (publisher / "published.md").write_text("new published main content\n", encoding="utf-8")
    run_git(publisher, "add", "--", "published.md")
    run_git(publisher, "commit", "-m", "advance published main")
    run_git(publisher, "push", "origin", "main")
    published = run_git(publisher, "rev-parse", "HEAD").stdout.strip()
    core = load_core()
    token = core.acquire_producer_lock(repo)
    lock_file = core.producer_lock_path(repo)
    before = (_repo_snapshot(repo), _file_inventory(home))
    try:
        result = invoke_engine(home, "--sync-from-main", "--hook")

        assert result.returncode == 12, result.stdout + result.stderr
        assert "producer lock is held" in result.stderr
        assert str(lock_file) in result.stderr
        assert result.stdout == ""
        assert (_repo_snapshot(repo), _file_inventory(home)) == before
    finally:
        core.release_producer_lock(repo, token)

    retry = invoke_engine(home, "--sync-from-main")
    assert retry.returncode == 0, retry.stdout + retry.stderr
    assert run_git(repo, "rev-parse", "HEAD").stdout.strip() == published
    assert (repo / "published.md").read_text(encoding="utf-8") == "new published main content\n"
    assert not lock_file.exists()


@pytest.mark.parametrize("status", ["clean", "dirty", "staged", "untracked"])
@pytest.mark.parametrize("hook", [False, True], ids=["cli", "hook"])
def test_refresh_refuses_any_main_checkout_as_branch_policy(
    tmp_path: Path, status: str, hook: bool,
) -> None:
    repo, _, target, home = setup_repo(tmp_path)
    run_git(repo, "checkout", "main")
    write_state(home, [repo])
    if status in ("dirty", "staged"):
        target.write_bytes(b"operator work on main\n")
        if status == "staged":
            run_git(repo, "add", "--", "skills/demo/SKILL.md")
    if status == "untracked":
        (repo / "untracked.md").write_bytes(b"untracked operator work\n")
    before = (_repo_snapshot(repo), _file_inventory(home))

    result = invoke_engine(home, "--sync-from-main", *(["--hook"] if hook else []))

    assert result.returncode == 12, result.stdout + result.stderr
    diagnostic = (f"machine/{MACHINE}: branch policy refuses main — expected machine/{MACHINE}; "
                  "refresh never touches main (a clean main is not healthy transport refresh, "
                  "a dirty one is a decision)")
    assert diagnostic in (result.stderr if hook else result.stdout)
    assert (_repo_snapshot(repo), _file_inventory(home)) == before


def test_refresh_fast_forwards_consumed_source(tmp_path: Path) -> None:
    """A v3 publisher merge makes the producer tip consumed; refresh fast-forwards.

    No reset, rebase or autostash: the reflog of the refresh must say
    "Fast-forward" and the transport branch name stays exactly as it was.
    """
    repo, remote, target, home = setup_repo(tmp_path)
    original = target.read_text(encoding="utf-8")
    target.write_text("name: demo\n\nConsumed update.\n", encoding="utf-8")
    write_state(home, [repo])
    write_ledger(home, [entry_for(target, original, target.read_text(encoding="utf-8"))])
    assert invoke_engine(home, "--stage").returncode == 0
    tip = run_git(repo, "rev-parse", "HEAD").stdout.strip()
    run_git(repo, "push", "origin", f"HEAD:refs/heads/machine/{MACHINE}")

    published = publish_merge(repo, remote, tmp_path, quote="Consumed update.")
    run_git(repo, "fetch", "origin")
    parents = run_git(repo, "show", "-s", "--format=%P", published).stdout.split()
    assert parents == [run_git(repo, "rev-parse", "origin/main^1").stdout.strip(), tip]

    result = invoke_engine(home, "--sync-from-main", "--verbose")

    assert result.returncode == 0, result.stdout + result.stderr
    output = result.stdout + result.stderr
    assert "fast-forward" in output.lower()
    head = run_git(repo, "rev-parse", "HEAD").stdout.strip()
    assert head == published
    assert head == run_git(repo, "rev-parse", "origin/main").stdout.strip()
    assert run_git(repo, "branch", "--show-current").stdout.strip() == f"machine/{MACHINE}"
    assert run_git(repo, "status", "--porcelain").stdout == ""
    # A reset would write "reset: moving to …"; the FF is a merge-ancestry fact.
    assert "Fast-forward" in run_git(repo, "reflog", "-1", "--format=%gs").stdout
    assert remote_head(repo, f"machine/{MACHINE}") == tip


def test_refresh_diverged_work_is_preserved(tmp_path: Path) -> None:
    """Divergence keeps the local commit, index and dirty bytes; the hook reports it.

    The deliberate pre-consolidation merge is a real Git merge of P into C and
    both sides' content survives — never an ours/theirs default.
    """
    repo, remote, target, home = setup_repo(tmp_path)
    original = target.read_text(encoding="utf-8")
    target.write_text("name: demo\n\nConsumed update.\n", encoding="utf-8")
    write_state(home, [repo])
    write_ledger(home, [entry_for(target, original, target.read_text(encoding="utf-8"),
                                  entry_id="entry-1")])
    assert invoke_engine(home, "--stage").returncode == 0
    run_git(repo, "push", "origin", f"HEAD:refs/heads/machine/{MACHINE}")
    published = publish_merge(repo, remote, tmp_path, quote="Consumed update.")

    # Local work C is a sibling of P (both children of the published T).
    lesson = repo / "skills" / "demo" / "lesson-c.md"
    lesson.write_text("Local lesson C.\n", encoding="utf-8")
    target.write_text("name: demo\n\nConsumed update.\nLocal lesson C in SKILL.\n",
                      encoding="utf-8")
    run_git(repo, "add", "--", "skills/demo/lesson-c.md", "skills/demo/SKILL.md")
    run_git(repo, "commit", "-m", "local lesson C")
    local = run_git(repo, "rev-parse", "HEAD").stdout.strip()
    dirty = repo / "skills" / "demo" / "dirty-note.md"
    dirty.write_bytes(b"uncommitted local bytes that must survive\n")

    result = invoke_engine(home, "--sync-from-main", "--hook")

    assert result.returncode == 12
    assert "pre-consolidation merge required" in (result.stdout + result.stderr)
    assert run_git(repo, "rev-parse", "HEAD").stdout.strip() == local
    assert run_git(repo, "diff", "--cached", "--name-only").stdout == ""
    assert dirty.read_bytes() == b"uncommitted local bytes that must survive\n"
    assert run_git(repo, "rev-parse", "origin/main").stdout.strip() == published

    # Deliberate pre-consolidation merge: both C and the curated P survive.
    run_git(repo, "merge", "--no-ff", "-m", "pre-consolidation merge", "origin/main")
    merge = run_git(repo, "rev-parse", "HEAD").stdout.strip()
    assert run_git(repo, "show", "-s", "--format=%P", merge).stdout.split() == [local, published]
    assert lesson.read_text(encoding="utf-8") == "Local lesson C.\n"
    assert "Consumed update." in target.read_text(encoding="utf-8")
    assert dirty.read_bytes() == b"uncommitted local bytes that must survive\n"
    assert "?? skills/demo/dirty-note.md" in run_git(repo, "status", "--porcelain").stdout


def test_refresh_noop_does_not_create_echo_commit(tmp_path: Path) -> None:
    """Already-equal and locally-ahead checkouts are no-ops: no echo merge commit."""
    repo, _, target, home = setup_repo(tmp_path)
    write_state(home, [repo])
    head_before = run_git(repo, "rev-parse", "HEAD").stdout.strip()

    equal = invoke_engine(home, "--sync-from-main", "--verbose")

    assert equal.returncode == 0, equal.stdout + equal.stderr
    assert "already at origin/main" in equal.stdout + equal.stderr
    assert run_git(repo, "rev-parse", "HEAD").stdout.strip() == head_before

    # Local work ahead of a published main: main is already an ancestor, so the
    # refresh integrates nothing and must not create an empty echo merge.
    target.write_text("name: demo\n\nLocal pending work.\n", encoding="utf-8")
    run_git(repo, "add", "--", "skills/demo/SKILL.md")
    run_git(repo, "commit", "-m", "local pending lesson")
    local = run_git(repo, "rev-parse", "HEAD").stdout.strip()
    count_before = run_git(repo, "rev-list", "--count", "HEAD").stdout.strip()

    ahead = invoke_engine(home, "--sync-from-main", "--verbose")

    assert ahead.returncode == 0, ahead.stdout + ahead.stderr
    assert "nothing to integrate" in ahead.stdout + ahead.stderr
    assert run_git(repo, "rev-parse", "HEAD").stdout.strip() == local
    assert run_git(repo, "rev-list", "--count", "HEAD").stdout.strip() == count_before
    assert len(run_git(repo, "show", "-s", "--format=%P", local).stdout.split()) == 1
    assert run_git(repo, "status", "--porcelain").stdout == ""
    assert remote_head(repo, f"machine/{MACHINE}") == run_git(
        repo, "rev-parse", "origin/machine/{0}".format(MACHINE)).stdout.strip()


def test_refresh_fetch_failure_is_nonzero_and_leaves_head(tmp_path: Path) -> None:
    repo, _, _, home = setup_repo(tmp_path)
    write_state(home, [repo])
    run_git(repo, "remote", "set-url", "origin", str(tmp_path / "missing remote.git"))
    head_before = run_git(repo, "rev-parse", "HEAD").stdout.strip()

    result = invoke_engine(home, "--sync-from-main", "--hook")

    assert result.returncode == 12
    assert "fetch failed" in result.stderr.lower()
    assert run_git(repo, "rev-parse", "HEAD").stdout.strip() == head_before


def test_refresh_on_dirty_worktree_is_noop(tmp_path: Path) -> None:
    """A dirty worktree is never integrated, even when published main is ahead."""
    repo, remote, target, home = setup_repo(tmp_path)
    write_state(home, [repo])
    # Advance published main through an independent clone.
    other = tmp_path / "main-only clone"
    run_git(tmp_path, "clone", "-q", "-b", "main", str(remote), str(other))
    run_git(other, "config", "user.name", "Other")
    run_git(other, "config", "user.email", "other@example.invalid")
    (other / "main-only.md").write_text("published main work\n", encoding="utf-8")
    run_git(other, "add", "--", "main-only.md")
    run_git(other, "commit", "-m", "published main work")
    run_git(other, "push", "origin", "main")
    target.write_text("name: demo\n\nDirty local edit.\n", encoding="utf-8")
    head_before = run_git(repo, "rev-parse", "HEAD").stdout.strip()

    result = invoke_engine(home, "--sync-from-main", "--verbose")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "sync skipped" in result.stdout + result.stderr
    assert run_git(repo, "rev-parse", "HEAD").stdout.strip() == head_before
    assert target.read_text(encoding="utf-8") == "name: demo\n\nDirty local edit.\n"


def test_refresh_refuses_an_in_progress_merge(tmp_path: Path) -> None:
    repo, remote, target, home = setup_repo(tmp_path)
    write_state(home, [repo])
    # A real merge leaves MERGE_HEAD behind when it stops on a conflict.
    run_git(repo, "checkout", "-b", "other")
    target.write_text("name: demo\n\nOther side line.\n", encoding="utf-8")
    run_git(repo, "commit", "-am", "other side line")
    run_git(repo, "checkout", f"machine/{MACHINE}")
    target.write_text("name: demo\n\nMachine side line.\n", encoding="utf-8")
    run_git(repo, "commit", "-am", "machine side line")
    merged = run_git(repo, "merge", "other", check=False)

    assert merged.returncode != 0 and (repo / ".git" / "MERGE_HEAD").is_file()
    result = invoke_engine(home, "--sync-from-main")

    assert result.returncode == 12
    assert "Git operation already in progress" in (result.stdout + result.stderr)


# --- producer lock (staging vs pre-consolidation) ---------------------------------------------------


def test_stage_refuses_preconsolidation_lock(tmp_path: Path) -> None:
    """A held pre-consolidation lock blocks staging without touching files or index.

    The lock is one owner-token file at the producer repo's Git common dir, so
    the same refusal applies in both directions (staging vs push) — there is no
    second lock to accidentally bypass.
    """
    repo, _, target, home = setup_repo(tmp_path)
    original = target.read_text(encoding="utf-8")
    target.write_text("name: demo\n\nPending work blocked by the lock.\n", encoding="utf-8")
    state_path = write_state(home, [repo])
    write_ledger(home, [entry_for(target, original, target.read_text(encoding="utf-8"))])
    remote_before = remote_head(repo, f"machine/{MACHINE}")

    locked = invoke_engine(home, "--lock")
    assert locked.returncode == 0, locked.stdout + locked.stderr
    common = run_git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()
    lock_file = Path(common) / "hermes-sync" / "producer.lock"
    assert lock_file.is_file()

    head_before = run_git(repo, "rev-parse", "HEAD").stdout.strip()
    status_before = run_git(repo, "status", "--porcelain").stdout
    index_before = run_git(repo, "diff", "--cached", "--name-only").stdout
    state_before = state_path.read_bytes()

    refused = invoke_engine(home, "--stage")

    assert refused.returncode == 12
    assert "producer lock is held" in refused.stdout + refused.stderr
    assert run_git(repo, "rev-parse", "HEAD").stdout.strip() == head_before
    assert run_git(repo, "status", "--porcelain").stdout == status_before
    assert run_git(repo, "diff", "--cached", "--name-only").stdout == index_before
    assert state_path.read_bytes() == state_before
    assert remote_head(repo, f"machine/{MACHINE}") == remote_before

    # Reciprocal: the pre-consolidation push refuses while the same lock is held.
    push = invoke_engine(home, "--push-reviewed", head_before)
    assert push.returncode == 12
    assert "producer lock is held" in push.stdout + push.stderr
    assert remote_head(repo, f"machine/{MACHINE}") == remote_before

    unlocked = invoke_engine(home, "--unlock")
    assert unlocked.returncode == 0, unlocked.stdout + unlocked.stderr
    assert not lock_file.exists()

    staged = invoke_engine(home, "--stage")
    assert staged.returncode == 0, staged.stdout + staged.stderr
    assert run_git(repo, "rev-parse", "HEAD").stdout.strip() != head_before


# --- push the exact reviewed tip -------------------------------------------------------------------


def test_push_publishes_reviewed_tip_not_advanced_head(tmp_path: Path) -> None:
    """Publish T only; a later local T2 stays local and unpublished."""
    repo, remote, target, home = setup_repo(tmp_path)
    original = target.read_text(encoding="utf-8")
    target.write_text("name: demo\n\nReviewed tip content.\n", encoding="utf-8")
    write_state(home, [repo])
    write_ledger(home, [entry_for(target, original, target.read_text(encoding="utf-8"),
                                  entry_id="entry-1")])
    assert invoke_engine(home, "--stage").returncode == 0
    reviewed = run_git(repo, "rev-parse", "HEAD").stdout.strip()
    base = remote_head(repo, f"machine/{MACHINE}")

    review_file = write_history_review(tmp_path / "history review.json", reviewed, [reviewed])
    recorded = invoke_engine(home, "--record-history-review", reviewed,
                             "--history-review", str(review_file))
    assert recorded.returncode == 0, recorded.stdout + recorded.stderr
    record = read_state(home)["history_reviews"][str(repo.resolve())]
    assert record["tip"] == reviewed and len(record["digest"]) == 64

    # A second sweep advances HEAD after the review.
    target.write_text("name: demo\n\nSecond, unreviewed local change.\n", encoding="utf-8")
    write_ledger(home, [
        entry_for(target, original, "name: demo\n\nReviewed tip content.\n", entry_id="entry-1"),
        entry_for(target, original, target.read_text(encoding="utf-8"), entry_id="entry-2"),
    ])
    assert invoke_engine(home, "--stage").returncode == 0
    advanced = run_git(repo, "rev-parse", "HEAD").stdout.strip()
    assert advanced != reviewed and run_git(repo, "rev-parse", "HEAD^").stdout.strip() == reviewed

    pushed = invoke_engine(home, "--push-reviewed", reviewed)

    assert pushed.returncode == 0, pushed.stdout + pushed.stderr
    assert remote_head(repo, f"machine/{MACHINE}") == reviewed
    assert remote_head(repo, f"machine/{MACHINE}") != advanced
    assert base != reviewed
    # T2 really stayed local: the bare remote has no object for it.
    bare = tmp_path / "shared skill remote.git"
    assert run_git(bare, "cat-file", "-e", f"{advanced}^{{commit}}", check=False).returncode != 0
    state = read_state(home)
    assert state["last_pushed_tip"] == reviewed
    assert state["last_pushed_ref"] == f"refs/heads/machine/{MACHINE}"
    # Pushing the reviewed tip never moves the local branch to it.
    assert run_git(repo, "rev-parse", "HEAD").stdout.strip() == advanced

    # T2 has no history review of its own, so it is refused and stays unpublished.
    refused = invoke_engine(home, "--push-reviewed", advanced)
    assert refused.returncode == 12
    assert "history review" in (refused.stdout + refused.stderr).lower()
    assert remote_head(repo, f"machine/{MACHINE}") == reviewed


def test_push_reviewed_refuses_commit_outside_transport_history(tmp_path: Path) -> None:
    """A reviewed SHA must be this transport branch's HEAD or one of its ancestors."""
    repo, _, target, home = setup_repo(tmp_path)
    write_state(home, [repo])
    base = remote_head(repo, f"machine/{MACHINE}")
    run_git(repo, "checkout", "-b", "side")
    target.write_text("name: demo\n\nSide-branch content.\n", encoding="utf-8")
    run_git(repo, "commit", "-am", "side work")
    side = run_git(repo, "rev-parse", "HEAD").stdout.strip()
    run_git(repo, "checkout", f"machine/{MACHINE}")

    result = invoke_engine(home, "--push-reviewed", side)

    assert result.returncode == 12
    assert "not HEAD or an ancestor of HEAD" in result.stdout + result.stderr
    assert remote_head(repo, f"machine/{MACHINE}") == base


def test_source_history_removed_exposure_still_blocks_push(tmp_path: Path) -> None:
    """A clean final tree does not make the removed exposure publishable.

    The fixture value is synthetic and must never appear in output or state.
    """
    repo, remote, target, home = setup_repo(tmp_path)
    write_state(home, [repo])
    base = run_git(repo, "rev-parse", "HEAD").stdout.strip()
    synthetic_value = "SYNTHETIC_FIXTURE_VALUE_NOT_A_REAL_CREDENTIAL_0001"
    env_file = repo / ".env"
    env_file.write_text(f"DEMO_API_KEY={synthetic_value}\n", encoding="utf-8")
    target.write_text("name: demo\n\nClean final lesson.\n", encoding="utf-8")
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-m", "temporary local exposure (never pushed)")
    exposed = run_git(repo, "rev-parse", "HEAD").stdout.strip()

    env_file.unlink()
    target.write_text("name: demo\n\nClean final lesson after redaction.\n", encoding="utf-8")
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-m", "remove the fixture file")
    tip = run_git(repo, "rev-parse", "HEAD").stdout.strip()
    assert ".env" not in run_git(repo, "ls-tree", "-r", "--name-only", "HEAD").stdout.split()
    assert run_git(repo, "status", "--porcelain").stdout == ""

    review_file = write_history_review(tmp_path / "history review.json", tip, [exposed, tip])
    recorded = invoke_engine(home, "--record-history-review", tip,
                             "--history-review", str(review_file))
    assert recorded.returncode == 0, recorded.stdout + recorded.stderr

    refused = invoke_engine(home, "--push-reviewed", tip)

    assert refused.returncode == 12
    output = refused.stdout + refused.stderr
    assert ".env" in output and "forbidden-path" in output
    assert synthetic_value not in output
    assert synthetic_value not in state_values_containing(home)
    assert remote_head(repo, f"machine/{MACHINE}") == base
    assert "last_pushed_tip" not in read_state(home)
    assert run_git(repo, "rev-parse", "HEAD").stdout.strip() == tip

    # The read-only screen reports the same range without echoing the value.
    screened = invoke_engine(home, "--screen-history", tip)
    assert screened.returncode == 10
    assert ".env" in screened.stdout and "credential-pattern" in screened.stdout
    assert synthetic_value not in screened.stdout + screened.stderr


def state_values_containing(home: Path) -> str:
    """Serialize producer state and the stage report for a no-echo assertion."""
    parts = []
    for name in ("skill-repo-sync.json", "stage-report.json"):
        path = home / name
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


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


def test_consolidate_legacy_modes_are_retired_and_reset_never_writes(tmp_path: Path) -> None:
    """The v2 collection/preflight/merge modes cannot be used as a publication
    bypass: they refuse before any fetch or write, and --reset-branch stays a
    no-write policy refusal."""
    repo, remote, target, home = setup_repo(tmp_path)
    target.write_text("name: demo\n\nConsolidatable rule change.\n", encoding="utf-8")
    run_git(repo, "add", "--", "skills/demo/SKILL.md")
    run_git(repo, "commit", "-m", "stage: local work")
    run_git(repo, "push")
    staged_tip = run_git(repo, "rev-parse", "HEAD").stdout.strip()

    consolidator = tmp_path / "consolidator clone"
    run_git(tmp_path, "clone", str(remote), str(consolidator))
    run_git(consolidator, "config", "user.name", "Consolidator")
    run_git(consolidator, "config", "user.email", "consolidator@example.invalid")
    outdir = tmp_path / "collect out"

    before = remote_head(consolidator, f"machine/{MACHINE}")
    for mode, args in (
        ("--collect", ["--collect", "--outdir", str(outdir)]),
        ("--preflight", ["--preflight", "--outdir", str(outdir)]),
        ("--merge-map", ["--merge-map", MACHINE, "--outdir", str(outdir)]),
        ("--apply-decisions", ["--apply-decisions", str(tmp_path / "d.json"),
                               "--outdir", str(outdir)]),
    ):
        result = invoke_consolidate(home, *args, "--repo", str(consolidator))
        assert result.returncode == 12, (mode, result.stderr)
        assert "retired:" in result.stderr and mode in result.stderr
        assert result.stdout == ""
    assert not outdir.exists()
    assert remote_head(consolidator, f"machine/{MACHINE}") == before == staged_tip

    # --reset-branch is retired: no force push, the branch keeps its content.
    reset = invoke_consolidate(home, "--reset-branch", MACHINE, "--repo", str(consolidator),
                               "--confirm-consumed")
    assert reset.returncode == 12
    assert "retired:" in reset.stderr and "--reset-branch" in reset.stderr
    assert remote_head(consolidator, f"machine/{MACHINE}") == staged_tip


def test_consolidate_retired_reset_refuses_without_confirmation(tmp_path: Path) -> None:
    """The old confirmation gate is moot: the mode is retired and never writes a remote."""
    repo, remote, target, home = setup_repo(tmp_path)
    target.write_text("name: demo\n\nNot yet consolidated.\n", encoding="utf-8")
    run_git(repo, "add", "--", "skills/demo/SKILL.md")
    run_git(repo, "commit", "-m", "stage: unique pending work")
    run_git(repo, "push")

    consolidator = tmp_path / "consolidator clone"
    run_git(tmp_path, "clone", str(remote), str(consolidator))
    run_git(consolidator, "config", "user.name", "Consolidator")
    run_git(consolidator, "config", "user.email", "consolidator@example.invalid")
    branch_before = remote_head(consolidator, f"machine/{MACHINE}")
    main_before = remote_head(consolidator, "main")

    result = invoke_consolidate(home, "--reset-branch", MACHINE, "--repo", str(consolidator))

    assert result.returncode == 12
    assert "retired:" in result.stderr
    assert remote_head(consolidator, f"machine/{MACHINE}") == branch_before
    assert remote_head(consolidator, "main") == main_before


# --- installer ------------------------------------------------------------------------------------


def installer_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo = tmp_path / "installer fixture"
    skill = repo / "skills" / "skill-library-maintenance"
    scripts = skill / "scripts"
    scripts.mkdir(parents=True)
    (skill / "assets").mkdir(parents=True)
    shutil.copy2(ENGINE, scripts / ENGINE.name)
    shutil.copy2(CORE, scripts / CORE.name)
    shutil.copy2(INSTALLER, scripts / INSTALLER.name)
    shutil.copy2(SKILL_ROOT / "assets" / "skill-sync-report.md.example",
                 skill / "assets" / "skill-sync-report.md.example")
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


def install_hermes_stub(tmp_path: Path,
                        config: dict[str, object] | None = None) -> tuple[Path, Path, Path]:
    """Fake ``hermes`` CLI: ``config get … --json`` answers from a JSON file, ``config set`` rewrites it.

    Returns ``(fake bin dir, call log, config file)``. The real Hermes configuration is never read
    or written — every installer hook decision in these tests is made against this file. An unset
    key fails like the real CLI ("Config key not set", exit 1); ``FAKE_HERMES_GET_RAW`` makes
    ``config get`` print arbitrary bytes so malformed responses are testable.
    """
    fake_bin = tmp_path / "fake bin"
    fake_bin.mkdir()
    calls_log = tmp_path / "hermes calls.jsonl"
    config_file = tmp_path / "fake hermes config.json"
    config_file.write_text(json.dumps(config or {}), encoding="utf-8")
    fake_hermes = fake_bin / "hermes"
    fake_hermes.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "args = sys.argv[1:]\n"
        "with open(os.environ['FAKE_HERMES_LOG'], 'a', encoding='utf-8') as f: f.write(json.dumps(args)+'\\n')\n"
        "path = os.environ['FAKE_HERMES_CONFIG']\n"
        "with open(path, encoding='utf-8') as f: config = json.load(f)\n"
        "if args[:2] == ['config', 'get']:\n"
        "    raw = os.environ.get('FAKE_HERMES_GET_RAW')\n"
        "    if raw is not None:\n"
        "        print(raw, end=''); sys.exit(0)\n"
        "    key = args[2]\n"
        "    if key not in config:\n"
        "        print(f'Config key not set: {key}', file=sys.stderr); sys.exit(1)\n"
        "    print(json.dumps(config[key])); sys.exit(0)\n"
        "if args[:2] == ['config', 'set']:\n"
        "    config[args[2]] = json.loads(args[3])\n"
        "    with open(path, 'w', encoding='utf-8') as f: json.dump(config, f)\n"
        "    print(f'updated {args[2]}'); sys.exit(0)\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    fake_hermes.chmod(0o755)
    return fake_bin, calls_log, config_file


def installer_env(tmp_path: Path, home: Path, config: dict[str, object] | None = None,
                  **extra: str) -> tuple[dict[str, str], Path, Path]:
    """Environment for the installer with the fake ``hermes`` first on PATH."""
    fake_bin, calls_log, config_file = install_hermes_stub(tmp_path, config)
    env = dict(os.environ, HERMES_HOME=str(home), FAKE_HERMES_LOG=str(calls_log),
               FAKE_HERMES_CONFIG=str(config_file))
    env["PATH"] = str(fake_bin) + os.pathsep + env.get("PATH", "")
    env.update(extra)
    return env, calls_log, config_file


def invoke_installer(scripts: Path, env: dict[str, str],
                     *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(scripts / INSTALLER.name), "--machine", MACHINE, *args],
        env=env, capture_output=True, text=True, check=False,
    )


def log_calls(calls_log: Path) -> list[list[str]]:
    if not calls_log.is_file():
        return []
    return [json.loads(line) for line in calls_log.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def session_hook_command(home: Path) -> str:
    return f"{shlex.quote(str(home / 'bin' / 'skill-repo-sync'))} --sync-from-main --hook"


def machine_repo(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo, scripts, remote = installer_fixture(tmp_path)
    run_git(repo, "checkout", "-b", f"machine/{MACHINE}")
    run_git(repo, "push", "--set-upstream", "origin", f"machine/{MACHINE}")
    return repo, scripts, remote


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
    _, scripts, _ = machine_repo(tmp_path)
    home = tmp_path / "hermes profile with spaces"
    (home / "skills").mkdir(parents=True)
    write_ledger(home, [])
    env, calls_log, _ = installer_env(tmp_path, home)
    python_link = tmp_path / "python interpreter"
    python_link.symlink_to(sys.executable)

    result = invoke_installer(scripts, env, "--bootstrap-current-ledger", "--apply-config",
                              "--python", str(python_link))

    assert result.returncode == 0, result.stderr or result.stdout
    state = json.loads((home / "skill-repo-sync.json").read_text(encoding="utf-8"))
    assert state["machine"] == MACHINE and state["sync_model"] == "stage-consolidate-v2"
    assert state["ledger_cursor"] == 0
    wrapper_text = (home / "bin" / "skill-repo-sync").read_text(encoding="utf-8")
    installed_engine = home / "bin" / ENGINE.name
    installed_core = home / "bin" / CORE.name
    assert f"'{installed_engine}'" in wrapper_text
    assert installed_engine.is_file() and installed_core.is_file()
    assert stat.S_IMODE(installed_engine.stat().st_mode) == 0o755
    assert stat.S_IMODE(installed_core.stat().st_mode) == 0o755
    assert (home / "bin" / "skill-sync-report.md.example").is_file()
    assert state["script"] == str(installed_engine)
    assert state["core"] == str(installed_core)
    calls = log_calls(calls_log)
    assert all("hooks_auto_accept" not in call for call in calls)
    set_calls = [call for call in calls if call[:2] == ["config", "set"]]
    assert len(set_calls) == 1
    assert set_calls[0][2] == "hooks.on_session_start"
    assert json.loads(set_calls[0][3]) == [{"command": session_hook_command(home), "timeout": 20}]


def test_installer_refuses_fresh_state_without_bootstrap_flag(tmp_path: Path) -> None:
    """A fresh install without the explicit bootstrap choice refuses before any write or chmod."""
    _, scripts, _ = machine_repo(tmp_path)
    home = tmp_path / "hermes profile"
    (home / "skills").mkdir(parents=True)
    write_ledger(home, [{"id": "old-1"}, {"id": "old-2"}])
    env, calls_log, config_file = installer_env(tmp_path, home)
    engine = scripts / ENGINE.name
    engine.chmod(0o640)                       # deliberately not executable: a chmod is a write
    ledger = home / "skills" / ".curator_ledger.jsonl"
    ledger_before = ledger.read_bytes()

    result = invoke_installer(scripts, env, "--apply-config")

    assert result.returncode == 12, result.stdout + result.stderr
    output = result.stdout + result.stderr
    assert "--bootstrap-current-ledger" in output
    assert "refus" in output.lower()
    assert not (home / "skill-repo-sync.json").exists()      # no state
    assert not (home / "bin").exists()                       # no wrapper, not even its directory
    assert stat.S_IMODE(engine.stat().st_mode) == 0o640      # no file-mode write
    assert log_calls(calls_log) == []                        # no config read or write
    assert config_file.read_text(encoding="utf-8") == "{}"
    assert ledger.read_bytes() == ledger_before


def test_installer_bootstrap_flag_records_initial_cursor(tmp_path: Path) -> None:
    _, scripts, _ = machine_repo(tmp_path)
    home = tmp_path / "hermes profile"
    (home / "skills").mkdir(parents=True)
    write_ledger(home, [{"id": "old-1"}, {"id": "old-2"}])
    env, calls_log, _ = installer_env(tmp_path, home)
    (scripts / ENGINE.name).chmod(0o640)

    result = invoke_installer(scripts, env, "--bootstrap-current-ledger")

    assert result.returncode == 0, result.stderr or result.stdout
    state = json.loads((home / "skill-repo-sync.json").read_text(encoding="utf-8"))
    assert state["ledger_cursor"] == 2                      # the current ledger end, not a rewind
    wrapper = home / "bin" / "skill-repo-sync"
    assert wrapper.is_file() and stat.S_IMODE(wrapper.stat().st_mode) == 0o755
    assert stat.S_IMODE((home / "bin" / ENGINE.name).stat().st_mode) == 0o755
    # The repository copy is not mutated by an install; only the installed pair is.
    assert stat.S_IMODE((scripts / ENGINE.name).stat().st_mode) == 0o640
    assert log_calls(calls_log) == []


def test_installer_rejects_bootstrap_flag_on_existing_state(tmp_path: Path) -> None:
    repo, scripts, _ = machine_repo(tmp_path)
    home = tmp_path / "hermes profile"
    (home / "skills").mkdir(parents=True)
    state_path = write_state(home, [repo], cursor=3)
    before = state_path.read_bytes()
    env, _, _ = installer_env(tmp_path, home)

    result = invoke_installer(scripts, env, "--bootstrap-current-ledger")

    assert result.returncode == 12, result.stdout + result.stderr
    output = result.stdout + result.stderr
    assert "--bootstrap-current-ledger" in output and "existing" in output.lower()
    assert state_path.read_bytes() == before                # the saved cursor is never rewound
    assert not (home / "bin").exists()


def test_installer_upgrade_keeps_the_existing_cursor(tmp_path: Path) -> None:
    """An upgrade (no bootstrap flag) never moves the cursor to the current ledger end."""
    repo, scripts, _ = machine_repo(tmp_path)
    home = tmp_path / "hermes profile"
    (home / "skills").mkdir(parents=True)
    write_ledger(home, [{"id": "entry-1"}, {"id": "entry-2"}, {"id": "entry-3"}])
    state_path = write_state(home, [repo], cursor=1)
    env, _, _ = installer_env(tmp_path, home)

    result = invoke_installer(scripts, env, "--apply-config")

    assert result.returncode == 0, result.stderr or result.stdout
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["ledger_cursor"] == 1                  # preserved, not advanced to 3
    assert state["version"] == "3.0.0"
    assert (home / "bin" / "skill-repo-sync").is_file()


def load_installer_module():
    spec = importlib.util.spec_from_file_location("install_skill_repo_sync", INSTALLER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("existing", [True, False], ids=["upgrade", "fresh"])
@pytest.mark.parametrize("failed_target", [CORE.name, "skill-sync-report.md.example"])
@pytest.mark.parametrize("failure", [OSError, RuntimeError, KeyboardInterrupt],
                         ids=["io-error", "unexpected-error", "interrupt"])
def test_installer_rolls_back_all_artifacts_on_replace_failure(
    tmp_path: Path, monkeypatch, existing: bool, failed_target: str, failure: type,
) -> None:
    """Even a second/third replacement failure leaves the previous runnable release intact."""
    repo, _, _, home = setup_repo(tmp_path)
    write_state(home, [repo])
    monkeypatch.setenv("HERMES_HOME", str(home))
    module = load_installer_module()
    target_dir = home / "bin"
    target_dir.mkdir()
    old = {
        ENGINE.name: ENGINE.read_bytes().replace(b'SCRIPT_VERSION = "3.0.0"',
                                                b'SCRIPT_VERSION = "2.0.0"'),
        CORE.name: CORE.read_bytes().replace(b'CORE_VERSION = "3.0.0"',
                                            b'CORE_VERSION = "2.0.0"'),
        "skill-sync-report.md.example": b"previous report template\r\n\x00exact bytes\n",
    }
    modes = {ENGINE.name: 0o750, CORE.name: 0o640, "skill-sync-report.md.example": 0o600}
    if existing:
        for name, data in old.items():
            (target_dir / name).write_bytes(data)
            (target_dir / name).chmod(modes[name])
        before = subprocess.run([sys.executable, str(target_dir / ENGINE.name), "--selfcheck"],
                                capture_output=True, text=True)
        assert before.returncode == 0, before.stdout + before.stderr

    real_replace = module.os.replace
    replaced = []

    def fail_replace(source, target):
        if Path(target).name == failed_target:
            raise failure("injected replacement failure")
        real_replace(source, target)
        replaced.append(Path(target).name)

    monkeypatch.setattr(module.os, "replace", fail_replace)
    with pytest.raises((module.InstallError, failure), match="injected replacement failure"):
        module.install_engine_pair(home)

    assert ENGINE.name in replaced  # The failure happened after the first real replacement.
    expected = old if existing else {}
    actual = {p.name: p.read_bytes() for p in target_dir.iterdir() if p.is_file()}
    assert actual == expected, "failed installation must restore every old artifact byte-for-byte"
    assert sorted(p.name for p in target_dir.iterdir()) == sorted(expected)
    if existing:
        assert {name: stat.S_IMODE((target_dir / name).stat().st_mode)
                for name in expected} == modes
        check = subprocess.run([sys.executable, str(target_dir / ENGINE.name), "--selfcheck"],
                               capture_output=True, text=True)
        assert check.returncode == 0, check.stdout + check.stderr
        assert "script version: 2.0.0" in check.stdout
        assert "core version: 2.0.0" in check.stdout


def test_installer_version_is_read_only_without_install_context(tmp_path: Path) -> None:
    """Version discovery needs no machine, Git checkout, state, or bootstrap consent."""
    standalone = tmp_path / INSTALLER.name
    shutil.copy2(INSTALLER, standalone)
    home = tmp_path / "absent profile"
    env = dict(os.environ, HERMES_HOME=str(home))
    env.pop("SKILL_REPO_MACHINE", None)

    result = subprocess.run([sys.executable, str(standalone), "--version"],
                            cwd=tmp_path, env=env, capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == "install-skill-repo-sync 3.0.0\n"
    assert result.stderr == ""
    assert not home.exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == [INSTALLER.name]


def test_installer_version_is_recorded_in_state_and_wrapper(tmp_path: Path) -> None:
    """The installer stamps its own release version; the wrapper records it for consent review."""
    module = load_installer_module()
    assert module.INSTALLER_VERSION == "3.0.0"
    _, scripts, _ = machine_repo(tmp_path)
    home = tmp_path / "hermes profile"
    (home / "skills").mkdir(parents=True)
    env, _, _ = installer_env(tmp_path, home)

    result = invoke_installer(scripts, env, "--bootstrap-current-ledger")

    assert result.returncode == 0, result.stderr or result.stdout
    state = json.loads((home / "skill-repo-sync.json").read_text(encoding="utf-8"))
    assert state["version"] == "3.0.0"
    wrapper_text = (home / "bin" / "skill-repo-sync").read_text(encoding="utf-8")
    assert "INSTALLER_VERSION 3.0.0" in wrapper_text


def test_installer_appends_session_hook_and_preserves_unrelated_hooks(tmp_path: Path) -> None:
    """The installer reads the hook list as JSON and appends only its own entry."""
    _, scripts, _ = machine_repo(tmp_path)
    home = tmp_path / "hermes profile with spaces"
    (home / "skills").mkdir(parents=True)
    unrelated = {"command": "/opt/team/session-hook.sh", "timeout": 45, "matcher": "*"}
    telemetry = {"command": "~/.hermes/agent-hooks/telemetry.sh", "event": "on_session_start"}
    lifecycle = [{"command": "/opt/team/v1-publisher.sh", "timeout": 30}]
    env, calls_log, config_file = installer_env(tmp_path, home, {
        "hooks.on_session_start": [dict(unrelated), dict(telemetry)],
        "hooks.on_skill_lifecycle": [dict(item) for item in lifecycle],
    })

    result = invoke_installer(scripts, env, "--bootstrap-current-ledger", "--apply-config")

    assert result.returncode == 0, result.stderr or result.stdout
    expected = [unrelated, telemetry, {"command": session_hook_command(home), "timeout": 20}]
    config_after = json.loads(config_file.read_text(encoding="utf-8"))
    assert config_after["hooks.on_session_start"] == expected          # unrelated entries intact
    assert config_after["hooks.on_skill_lifecycle"] == lifecycle       # never blanket-cleared
    calls = log_calls(calls_log)
    assert ["config", "get", "hooks.on_session_start", "--json"] in calls
    set_calls = [call for call in calls if call[:2] == ["config", "set"]]
    assert [call[2] for call in set_calls] == ["hooks.on_session_start"]
    assert json.loads(set_calls[0][3]) == expected
    assert not any("on_skill_lifecycle" in call for call in calls)     # not even read/cleared
    assert all("hooks_auto_accept" not in call for call in calls)


def test_installer_keeps_an_existing_session_hook_without_duplicating_it(tmp_path: Path) -> None:
    """A hook entry that already runs the wrapper (another timeout) is preserved as it is."""
    _, scripts, _ = machine_repo(tmp_path)
    home = tmp_path / "hermes profile"
    (home / "skills").mkdir(parents=True)
    existing = [{"command": session_hook_command(home), "timeout": 45}]
    env, calls_log, config_file = installer_env(tmp_path, home,
                                                {"hooks.on_session_start": existing})
    before = config_file.read_bytes()

    result = invoke_installer(scripts, env, "--bootstrap-current-ledger", "--apply-config")

    assert result.returncode == 0, result.stderr or result.stdout
    assert [call for call in log_calls(calls_log) if call[:2] == ["config", "set"]] == []
    assert config_file.read_bytes() == before
    assert json.loads(config_file.read_text(encoding="utf-8"))["hooks.on_session_start"] == existing


@pytest.mark.parametrize("raw", ["not json at all\n", '{"on_session_start": []}\n'])
def test_installer_fails_closed_on_malformed_hook_config(tmp_path: Path, raw: str) -> None:
    """An unreadable hook list is never replaced by a freshly written one."""
    _, scripts, _ = machine_repo(tmp_path)
    home = tmp_path / "hermes profile"
    (home / "skills").mkdir(parents=True)
    env, calls_log, config_file = installer_env(
        tmp_path, home, {"hooks.on_session_start": [{"command": "/opt/team/keep.sh"}]},
        FAKE_HERMES_GET_RAW=raw)
    before = config_file.read_bytes()

    result = invoke_installer(scripts, env, "--bootstrap-current-ledger", "--apply-config")

    assert result.returncode == 12, result.stdout + result.stderr
    output = result.stdout + result.stderr
    assert "hooks.on_session_start" in output and "json" in output.lower()
    assert [call for call in log_calls(calls_log) if call[:2] == ["config", "set"]] == []
    assert config_file.read_bytes() == before
    assert not (home / "skill-repo-sync.json").exists()     # refused before any write
    assert not (home / "bin").exists()


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


def test_installed_engine_pair_runs_from_a_temp_prefix(tmp_path: Path) -> None:
    """The installed engine ships with its core and runs without the repo scripts:
    moving the checkout's scripts directory away must not break `--version` or
    `--selfcheck` (the core is loaded from the install prefix)."""
    _, scripts, _ = machine_repo(tmp_path)
    home = tmp_path / "installed profile"
    (home / "skills").mkdir(parents=True)
    env, _, _ = installer_env(tmp_path, home)

    result = invoke_installer(scripts, env, "--bootstrap-current-ledger")
    assert result.returncode == 0, result.stderr or result.stdout
    installed = home / "bin" / ENGINE.name
    assert installed.is_file() and (home / "bin" / CORE.name).is_file()

    # Remove the repository copy of the scripts: only the install prefix is left.
    shutil.move(str(scripts), str(tmp_path / "scripts moved away"))
    run_env = dict(env)
    run_env["PATH"] = os.defpath
    version = subprocess.run([sys.executable, str(installed), "--version"],
                             cwd=tmp_path, env=run_env, capture_output=True, text=True)
    assert version.returncode == 0, version.stderr or version.stdout
    assert "skill-repo-sync 3.0.0" in version.stdout

    check = subprocess.run([sys.executable, str(installed), "--selfcheck", "--verbose"],
                           cwd=tmp_path, env=run_env, capture_output=True, text=True)
    assert check.returncode == 0, check.stderr or check.stdout
    assert "core version: 3.0.0" in check.stdout
    assert "installer version: 3.0.0" in check.stdout
    assert "hooks: not inspected" in check.stdout


@pytest.mark.parametrize("args", [
    ["--stage"], ["--sync-from-main"], ["--sync-from-main", "--dry-run"], ["--selfcheck"],
], ids=["stage-noop", "refresh-noop", "dry-run", "selfcheck"])
def test_engine_refuses_mixed_core_before_operating(tmp_path: Path, args: list[str]) -> None:
    """Even no-op paths and selfcheck fail closed on an installed mixed-version pair."""
    repo, _, _, home = setup_repo(tmp_path)
    write_state(home, [repo])
    installed = home / "bin"
    installed.mkdir()
    shutil.copy2(ENGINE, installed / ENGINE.name)
    core_text = CORE.read_text(encoding="utf-8")
    assert 'CORE_VERSION = "3.0.0"' in core_text
    (installed / CORE.name).write_text(
        core_text.replace('CORE_VERSION = "3.0.0"', 'CORE_VERSION = "0.0.0"'), encoding="utf-8")
    before = (_repo_snapshot(repo), _file_inventory(home))

    result = subprocess.run([sys.executable, str(installed / ENGINE.name), *args],
                            env=dict(os.environ, HERMES_HOME=str(home)),
                            capture_output=True, text=True)

    assert result.returncode == 12, result.stdout + result.stderr
    assert ("mixed installation: engine SCRIPT_VERSION 3.0.0 does not match core "
            "CORE_VERSION 0.0.0; reinstall the engine/core pair together") in result.stdout + result.stderr
    assert (_repo_snapshot(repo), _file_inventory(home)) == before


def test_installer_refuses_a_missing_core_before_any_write(tmp_path: Path) -> None:
    """A partial pair (engine without core) must not produce a wrapper or state."""
    _, scripts, _ = machine_repo(tmp_path)
    home = tmp_path / "hermes profile partial"
    (home / "skills").mkdir(parents=True)
    env, _, _ = installer_env(tmp_path, home)
    (scripts / CORE.name).unlink()

    result = invoke_installer(scripts, env, "--bootstrap-current-ledger")

    assert result.returncode == 1
    assert "partial installation" in (result.stdout + result.stderr)
    assert CORE.name in (result.stdout + result.stderr)
    assert not (home / "bin").exists()
    assert not (home / "skill-repo-sync.json").exists()


def test_installer_refuses_mixed_engine_core_versions(tmp_path: Path) -> None:
    """The pair must agree on release; a doctored core version refuses."""
    _, scripts, _ = machine_repo(tmp_path)
    home = tmp_path / "hermes profile mixed"
    (home / "skills").mkdir(parents=True)
    env, _, _ = installer_env(tmp_path, home)
    core_path = scripts / CORE.name
    text = core_path.read_text(encoding="utf-8")
    core_path.write_text(text.replace('CORE_VERSION = "3.0.0"', 'CORE_VERSION = "3.0.1"'),
                        encoding="utf-8")

    result = invoke_installer(scripts, env, "--bootstrap-current-ledger")

    assert result.returncode == 1
    assert "does not match" in (result.stdout + result.stderr)
    assert not (home / "bin").exists()
    assert not (home / "skill-repo-sync.json").exists()


# --- engine dry-run snapshot ----------------------------------------------------------------------

def _file_inventory(root: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    if not root.exists():
        return rows
    for item in sorted(root.rglob("*")):
        relative = str(item.relative_to(root))
        if item.is_symlink():
            rows[relative] = "link:" + os.readlink(item)
        elif item.is_file():
            rows[relative] = hashlib.sha256(item.read_bytes()).hexdigest()
        elif item.is_dir():
            rows[relative] = "dir"
    return rows


def _repo_snapshot(repo: Path) -> dict:
    git_dir = Path(run_git(repo, "rev-parse", "--absolute-git-dir").stdout.strip())
    fetch = git_dir / "FETCH_HEAD"
    index = git_dir / "index"
    return {
        "head": run_git(repo, "rev-parse", "HEAD").stdout.strip(),
        "refs": run_git(repo, "for-each-ref", "--format=%(refname) %(objectname)").stdout,
        "fetch_head": fetch.read_bytes().hex() if fetch.is_file() else "",
        "index_sha256": hashlib.sha256(index.read_bytes()).hexdigest() if index.is_file() else "",
        "files": _file_inventory(repo),
    }


@pytest.mark.parametrize("mode", ["--stage", "--sync-from-main"])
def test_engine_dry_run_performs_no_writes(tmp_path: Path, mode: str) -> None:
    """--stage/--sync-from-main --dry-run leave state, HEAD, all refs incl.
    FETCH_HEAD, the index, worktree inventory and bare-remote refs identical."""
    repo, remote, target, home = setup_repo(tmp_path)
    write_state(home, [repo])
    if mode == "--stage":
        target.write_text("name: demo\n\nPending dry-run change.\n", encoding="utf-8")
        write_ledger(home, [{"id": "e1", "before": [],
                             "after": [{"path": str(target)}]}])
    else:
        # Advance main remotely: a fetch would move origin/main and FETCH_HEAD,
        # so an unchanged FETCH_HEAD proves the dry run never fetched.
        clone = tmp_path / "main advance"
        subprocess.run(["git", "clone", "-q", "-b", "main", str(remote), str(clone)],
                       check=True, capture_output=True)
        run_git(clone, "config", "user.name", "Advance")
        run_git(clone, "config", "user.email", "advance@example.invalid")
        (clone / "remote-advance.md").write_text("remote main moved\n", encoding="utf-8")
        run_git(clone, "add", "remote-advance.md")
        run_git(clone, "commit", "-m", "remote main advance")
        run_git(clone, "push", "origin", "main")

    before = {
        "repo": _repo_snapshot(repo),
        "home": _file_inventory(home),
        "remote": run_git(remote, "for-each-ref", "--format=%(refname) %(objectname)").stdout,
    }
    result = invoke_engine(home, mode, "--dry-run", "--verbose")
    after = {
        "repo": _repo_snapshot(repo),
        "home": _file_inventory(home),
        "remote": run_git(remote, "for-each-ref", "--format=%(refname) %(objectname)").stdout,
    }
    assert result.returncode == 0, result.stderr or result.stdout
    assert after == before
