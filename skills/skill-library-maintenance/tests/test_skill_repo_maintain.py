# skills/skill-library-maintenance/tests/test_skill_repo_maintain.py
"""Behavioral tests for skill-repo-maintain.py: the v3 maintainer CLI
(capture → prepare → record-review → render/verify-report → integrate →
reconcile → render/verify-result, stable --pending/--retry and write-free
--dry-run), plus the retained legacy scan helpers. Self-contained: builds
disposable repos, never touches a live one."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


integrate = _load("maintain_under_test", SCRIPTS / "skill-repo-maintain.py")


def git(repo: Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)
    return out.stdout


def run_cli(repo: Path, home: Path, *args: str) -> subprocess.CompletedProcess:
    """Run the helper's real CLI under an isolated HERMES_HOME (the state file lives there)."""
    env = dict(os.environ)
    env["HERMES_HOME"] = str(home)
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "skill-repo-maintain.py"), *args, "--repo", str(repo)],
        capture_output=True, text=True, env=env)


def remote_refs(repo: Path) -> dict[str, str]:
    """Every ref the bare remote currently advertises: {'refs/heads/main': sha, ...}."""
    out = subprocess.run(["git", "-C", str(repo), "ls-remote", "origin"],
                         capture_output=True, text=True, check=True).stdout
    refs: dict[str, str] = {}
    for line in out.splitlines():
        if line.strip():
            sha, ref = line.split("\t", 1)
            refs[ref] = sha
    return refs


def write_state(home: Path, repo: Path, machine: str) -> Path:
    home.mkdir(parents=True, exist_ok=True)
    p = home / "skill-repo-sync.json"
    p.write_text(json.dumps({"machine": machine, "repos": [{"path": str(repo)}]}))
    return p


def write_maintainer_config(home: Path, maintainer: Path, runtime: Path) -> Path:
    """v3 maintainer config under <HERMES_HOME>/skill-repo-sync/maintainer.json."""
    store = home / "skill-repo-sync"
    store.mkdir(parents=True, exist_ok=True)
    config = {
        "schema": 3,
        "repo_id": "owned-skills",
        "remote": "origin",
        "maintainer_repo": str(maintainer),
        "runtime_roots": [str(runtime)],
        "policy": "skill-review-v1",
        "maintainer_identity": {"machine": "maintainer-test", "profile": "default",
                               "scope": "shared-generic"},
        "sources": [{"ref": "refs/heads/machine/testlab", "machine": "testlab",
                     "profile": "default", "scope": "shared-generic", "enabled": True}],
        "report": {"path": str(runtime)},
    }
    (store / "maintainer.json").write_text(json.dumps(config))
    return store


def build_repo(root: Path) -> Path:
    """The three_branch_repo fixture body against a fresh root (second scenario per test).
    Branch names here are machine/gamma|alpha|beta."""
    repo = root / "skills"
    repo.mkdir(parents=True)
    git(repo, "init", "-b", "main", "-q")
    git(repo, "config", "user.email", "t@t"), git(repo, "config", "user.name", "t")
    (repo / "a.md").write_text("line1\nline2\nline3\nline4\nline5\nline6\nline7\nline8\n")
    (repo / "b.md").write_text("bbb\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "base", "-q")

    git(repo, "checkout", "-q", "-b", "machine/gamma")
    (repo / "a.md").write_text("line1\nGAMMA-EDIT\nline3\nline4\nline5\nline6\nline7\nline8\n")
    (repo / "c.md").write_text("new from gamma\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "gamma work")

    git(repo, "checkout", "-q", "main")
    git(repo, "checkout", "-q", "-b", "machine/alpha")
    (repo / "a.md").write_text("line1\nline2\nline3\nALPHA-EDIT\nline5\nline6\nline7\nline8\n")
    (repo / "b.md").write_text("bbb\nalso alpha\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "alpha work")

    git(repo, "checkout", "-q", "main")
    git(repo, "checkout", "-q", "-b", "machine/beta")
    (repo / "a.md").write_text("line1\nGAMMA-EDIT\nline3\nline4\nline5\nline6\nline7\nline8\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "beta same region as gamma")
    git(repo, "checkout", "-q", "main")

    # DEVIATION (plan fixture): main must move in the same region AFTER the branches
    # forked — with main == merge-base no 3-way merge can ever conflict (verified:
    # git merge-file returns 0 on the plan fixture as written). MAIN-EDIT at line 2
    # collides with gamma's GAMMA-EDIT at line 2 => exactly one conflict block on a.md.
    (repo / "a.md").write_text("line1\nMAIN-EDIT\nline3\nline4\nline5\nline6\nline7\nline8\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "main edits the same region")

    remote = root / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-q", "origin", "main",
        "refs/heads/machine/gamma:refs/heads/machine/gamma",
        "refs/heads/machine/alpha:refs/heads/machine/alpha",
        "refs/heads/machine/beta:refs/heads/machine/beta")
    return repo


@pytest.fixture()
def three_branch_repo(tmp_path: Path) -> Path:
    """main with two files; three machine branches (machine/gamma|alpha|beta);
    gamma+beta overlap main's later edit region."""
    return build_repo(tmp_path)

def test_preflight_resolves_package_root_refs(tmp_path):
    """R-preflight: `references/<name>.md` from a nested support file resolves at the
    package root; a genuinely missing target stays flagged."""
    repo = build_repo(tmp_path)
    git(repo, "checkout", "-q", "-b", "machine/delta")
    (repo / "pkg" / "references").mkdir(parents=True)
    (repo / "pkg" / "references" / "guide.md").write_text("guide\n")
    (repo / "pkg" / "assets").mkdir(parents=True)
    (repo / "pkg" / "assets" / "note.md.example").write_text(
        "see `references/guide.md`, also `references/missing.md`\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "delta work")
    git(repo, "push", "-q", "origin", "machine/delta")
    out = tmp_path / "out"
    code, notes = integrate.preflight_scan(repo, out)
    report = json.loads((out / "preflight-findings.json").read_text())
    dangling = [f["detail"] for f in report["findings"]
                if f["kind"] == "dangling-reference" and f["file"] == "pkg/assets/note.md.example"]
    assert dangling == ["references/missing.md"], notes


def test_merge_map_separates_clean_from_conflict(three_branch_repo, tmp_path):
    out = tmp_path / "out"
    code, notes = integrate.merge_map(three_branch_repo, "gamma", out)
    assert code == 0, notes
    report = json.loads((out / "merge-map.json").read_text())
    assert report["clean_files"] == ["c.md"]          # new file: auto-mergeable
    packets = json.loads((out / "conflict-packets.json").read_text())
    assert [p["file"] for p in packets] == ["a.md"]   # only the overlap needs the LLM
    # DEVIATION (plan asserted ours == "GAMMA-EDIT"): ours is the MAIN side of the
    # conflict (merge_map: current=main, other=branch — matches the run book's
    # "ours = main, theirs = Branch"); GAMMA-EDIT is the branch side = "theirs".
    assert packets[0]["ours"] == "MAIN-EDIT\n"
    assert packets[0]["theirs"] == "GAMMA-EDIT\n"
    assert "line2" in packets[0]["base"]
    hunks = json.loads((out / "added-hunks.json").read_text())
    assert hunks and hunks[0]["added"] == ["new from gamma"]   # digest for clean files too


def test_merge_map_flags_oversized_packets(three_branch_repo, tmp_path):
    """R1: packets over the line budget are kept whole but flagged 'oversized'."""
    (three_branch_repo / "d.md").write_text("".join(f"main-line-{i}\n" for i in range(60)))
    git(three_branch_repo, "add", ".")
    git(three_branch_repo, "commit", "-q", "-m", "main big add")
    git(three_branch_repo, "push", "-q", "origin", "main")
    git(three_branch_repo, "checkout", "-q", "machine/gamma")
    (three_branch_repo / "d.md").write_text("".join(f"gamma-line-{i}\n" for i in range(60)))
    git(three_branch_repo, "add", ".")
    git(three_branch_repo, "commit", "-q", "-m", "gamma big add")
    git(three_branch_repo, "push", "-q", "origin", "machine/gamma")
    git(three_branch_repo, "checkout", "-q", "main")

    out = tmp_path / "out-big"
    code, notes = integrate.merge_map(three_branch_repo, "gamma", out)
    assert code == 0, notes
    report = json.loads((out / "merge-map.json").read_text())
    assert report["max_packet_lines"] == 80
    packets = json.loads((out / "conflict-packets.json").read_text())
    by_file = {p["file"]: p for p in packets}
    assert by_file["d.md"]["oversized"] is True     # whole block kept, 120 lines > 80
    assert by_file["a.md"]["oversized"] is False    # small conflict stays unflagged


def test_apply_decisions_resolves_blocks_in_order(three_branch_repo, tmp_path):
    out = tmp_path / "out"
    integrate.merge_map(three_branch_repo, "gamma", out)
    decisions = {"decisions": [
        {"file": "a.md", "block": 0, "action": "synthesize", "text": "ONE-RULE-VERSION\n"}]}
    dpath = tmp_path / "decisions.json"
    dpath.write_text(json.dumps(decisions))
    code, notes = integrate.apply_decisions(three_branch_repo, dpath, out)
    assert code == 0, notes
    resolved = (three_branch_repo / "a.md").read_text()
    assert resolved.splitlines()[1] == "ONE-RULE-VERSION"
    assert "<<<" not in resolved


def test_apply_decisions_names_missing_block_indices(three_branch_repo, tmp_path):
    """R2: all-or-nothing per file — the error names file + the missing block indices."""
    (three_branch_repo / "a.md").write_text(
        "line1\nMAIN-EDIT\nline3\nline4\nline5\nX-B\nline7\nline8\n")
    git(three_branch_repo, "add", ".")
    git(three_branch_repo, "commit", "-q", "-m", "main second region")
    git(three_branch_repo, "push", "-q", "origin", "main")
    git(three_branch_repo, "checkout", "-q", "machine/gamma")
    (three_branch_repo / "a.md").write_text(
        "line1\nGAMMA-EDIT\nline3\nline4\nline5\nY-B\nline7\nline8\n")
    git(three_branch_repo, "add", ".")
    git(three_branch_repo, "commit", "-q", "-m", "gamma second region")
    git(three_branch_repo, "push", "-q", "origin", "machine/gamma")
    git(three_branch_repo, "checkout", "-q", "main")

    out = tmp_path / "out"
    code, notes = integrate.merge_map(three_branch_repo, "gamma", out)
    assert code == 0, notes
    packets = json.loads((out / "conflict-packets.json").read_text())
    assert sorted(p["block"] for p in packets if p["file"] == "a.md") == [0, 1]

    # only block 0 decided — block 1 must be named in the refusal
    decisions = {"decisions": [{"file": "a.md", "block": 0, "action": "ours"}]}
    dpath = tmp_path / "decisions.json"
    dpath.write_text(json.dumps(decisions))
    code, notes = integrate.apply_decisions(three_branch_repo, dpath, out)
    assert code == 12
    msg = " ".join(notes)
    assert "a.md: missing decisions for conflict block index(es) 1" in msg

    # a file the decisions JSON omits entirely is missing just as much (R2)
    empty = tmp_path / "empty-decisions.json"
    empty.write_text(json.dumps({"decisions": []}))
    code2, notes2 = integrate.apply_decisions(three_branch_repo, empty, out)
    assert code2 == 12
    msg2 = " ".join(notes2)
    assert "a.md: missing decisions for conflict block index(es) 0, 1" in msg2


def test_apply_decisions_drop_removes_the_block(three_branch_repo, tmp_path):
    """action 'drop' deletes the conflicted region entirely (no text required)."""
    out = tmp_path / "out"
    integrate.merge_map(three_branch_repo, "gamma", out)
    decisions = {"decisions": [{"file": "a.md", "block": 0, "action": "drop"}]}
    dpath = tmp_path / "decisions.json"
    dpath.write_text(json.dumps(decisions))
    code, notes = integrate.apply_decisions(three_branch_repo, dpath, out)
    assert code == 0, notes
    resolved = (three_branch_repo / "a.md").read_text()
    assert "MAIN-EDIT" not in resolved and "GAMMA-EDIT" not in resolved
    assert "<<<" not in resolved and "line3" in resolved


def test_lock_ignores_unrelated_cron_executions(three_branch_repo, tmp_path):
    """No cron row authorizes refusing or breaking the maintainer lock.

    The old test asserted that an executions.db claim older than 60 s blocks a run and that a
    fresh claim is "self" by age. Both infer maintainer liveness from a dispatcher-pid cron row,
    which can refuse a live run; the new policy never reads executions.db at all.
    """
    import sqlite3

    home = tmp_path / "home"
    store = write_maintainer_config(home, three_branch_repo, tmp_path / "runtime")
    db = home / "cron" / "executions.db"
    db.parent.mkdir(parents=True)
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE executions (id TEXT PRIMARY KEY, status TEXT, claimed_at TEXT)")
    con.execute("INSERT INTO executions VALUES ('other-claim','running','1999-01-01T00:00:00')")
    con.commit()
    con.close()

    result = run_cli(three_branch_repo, home, "--lock")
    assert result.returncode == 0, result.stderr + result.stdout
    assert (store / "maintainer-lock.token").is_file()

    # No maintainer config means exit 13, never a fallback to a repo-path lock.
    bare_home = tmp_path / "bare-home"
    bare_home.mkdir()
    missing = run_cli(three_branch_repo, bare_home, "--lock")
    assert missing.returncode == 13
    assert "maintainer config" in missing.stderr
    assert not (three_branch_repo / ".git" / "hermes-integrate.lock").exists()


def test_lock_is_owner_token_owned_and_never_age_broken(three_branch_repo, tmp_path):
    """The lock lives in the Git common dir and only its owner token releases it.

    The old test asserted that an aged lock is auto-replaced and that --force-lock may override
    a live run. Age is not evidence of death and a repo-path lock misses linked worktrees; the
    new policy keeps the lock visible until the acquiring owner token releases it.
    """
    home = tmp_path / "home"
    store = write_maintainer_config(home, three_branch_repo, tmp_path / "runtime")
    common = Path(git(three_branch_repo, "rev-parse", "--path-format=absolute",
                      "--git-common-dir").strip())
    lock = common / "hermes-sync" / "maintainer.lock"

    first = run_cli(three_branch_repo, home, "--lock")
    assert first.returncode == 0, first.stderr + first.stdout
    assert lock.is_file()
    token = (store / "maintainer-lock.token").read_text().strip()
    record = json.loads(lock.read_text())
    assert record["token"] == token
    assert record["acquired_at"] and record["host"]

    second = run_cli(three_branch_repo, home, "--lock")
    assert second.returncode == 12
    assert token in second.stderr

    # --force-lock never bypasses ownership: it refuses with a recovery instruction.
    forced = run_cli(three_branch_repo, home, "--lock", "--force-lock")
    assert forced.returncode == 12
    assert token in forced.stderr and "observed" in forced.stderr
    assert lock.is_file()

    # A backdated lock (mtime and recorded acquisition time) still refuses.
    record["acquired_at"] = "1970-01-01T00:00:00Z"
    lock.write_text(json.dumps(record))
    os.utime(lock, (1, 1))
    old = run_cli(three_branch_repo, home, "--lock")
    assert old.returncode == 12
    assert lock.is_file()

    released = run_cli(three_branch_repo, home, "--unlock")
    assert released.returncode == 0, released.stderr + released.stdout
    assert not lock.exists()

    # A second unlock has no recorded owner token to guess with: it refuses.
    again = run_cli(three_branch_repo, home, "--unlock")
    assert again.returncode == 12


def test_pre_integration_scan_flags_duplicates_and_pointers(three_branch_repo):
    engine = integrate.srs  # the engine module the integrate script already loads
    added = [
        ("a.md", "a totally fresh rule line with enough words to matter here"),
        ("a.md", "line1"),                      # short: never a dup candidate
        ("b.md", "/home" + "/user/something"),  # instance pointer (split literal: scanner flags it at runtime, the diff gate stays clean)
    ]
    findings = engine.pre_integration_scan(three_branch_repo, added)
    kinds = sorted(f["kind"] for f in findings)
    assert kinds == ["instance-pointer"]
    # duplicate: the exact normalized base line re-added, 8+ words
    (three_branch_repo / "a.md").write_text("wordy base line with more than eight words in it yes\n")
    git(three_branch_repo, "add", ".")
    git(three_branch_repo, "commit", "-m", "w", "-q")
    findings2 = engine.pre_integration_scan(
        three_branch_repo, [("a.md", "wordy base line with more than eight words in it yes.")])
    assert [f["kind"] for f in findings2] == ["duplicate-candidate"]


def test_sync_from_main_warns_on_stage_report(three_branch_repo, tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    (home / "stage-report.json").write_text(
        json.dumps({"at": "2000-01-01T00:00:00+00:00", "needs_pre_integration": 2, "findings": []}))
    # v3 refresh refuses ANY main checkout (branch policy, exit 12), so this test runs on a
    # clean transport branch that is already at integrated main: refresh is a no-op and the
    # stage-report warning is the only thing under test here.
    git(three_branch_repo, "checkout", "-q", "-b", "machine/clean", "origin/main")
    git(three_branch_repo, "push", "-q", "-u", "origin", "machine/clean")
    code, notes = integrate.srs.sync_from_main(three_branch_repo, "clean", False, False)
    assert code == 0, notes
    assert any("2 addition(s) need pre-integration" in n for n in notes)


def test_stage_scans_and_trails_needs_pre_integration(three_branch_repo, tmp_path, monkeypatch):
    """R3: the staging scan is the safety net — stage-report.json + Needs-pre-integration trailer."""
    home = tmp_path / "home"
    (home / "skills").mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(home))
    (home / "skill-repo-sync.json").write_text(
        json.dumps({"machine": "alpha", "repos": [{"path": str(three_branch_repo)}]}))
    git(three_branch_repo, "checkout", "-q", "machine/alpha")
    git(three_branch_repo, "branch", "--set-upstream-to=origin/machine/alpha", "machine/alpha")
    (three_branch_repo / "x.md").write_text("see /home" + "/user/pointer for details\n")

    code, notes = integrate.srs.stage(three_branch_repo, "alpha", False, False)
    assert code == 0, notes
    report = json.loads((home / "stage-report.json").read_text())
    assert report["needs_pre_integration"] == 1
    assert report["findings"][0]["kind"] == "instance-pointer"
    body = git(three_branch_repo, "log", "-1", "--format=%B")
    assert "Needs-pre-integration: 1" in body


def strip_scenario(repo: Path, root: Path, c_edits_same_line: bool = False) -> dict:
    """Refresh-Strip scenario on machine/gamma: commit A (pushed, --note-pushed records it),
    then a CONSUMPTION simulated in a clone — the curated content lands on main as the
    maintainer's own commit and the one sanctioned force points the strip at it —
    then commit C on the A chain, never pushed."""
    home = root / "home"
    write_state(home, repo, "gamma")
    remote_url = git(repo, "remote", "get-url", "origin").strip()
    git(repo, "checkout", "-q", "machine/gamma")
    git(repo, "branch", "--set-upstream-to=origin/machine/gamma", "machine/gamma")
    (repo / "fa.md").write_text("A-MARKER\nL2\nL3\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "A work")
    git(repo, "push", "-q", "origin", "machine/gamma")
    a_sha = git(repo, "rev-parse", "HEAD").strip()
    r = run_cli(repo, home, "--note-pushed")   # lpt = A — recorded BEFORE C exists
    assert r.returncode == 0, r.stderr
    assert f"strip: last-pushed-tip -> {a_sha[:12]}" in r.stderr

    # the maintainer (in a clone): A's net curated onto main as its OWN commit ...
    clone = root / "clone"
    subprocess.run(["git", "clone", "-q", remote_url, str(clone)], check=True)
    git(clone, "config", "user.email", "t@t")
    git(clone, "config", "user.name", "t")
    git(clone, "checkout", "-q", "-B", "main", "origin/main")
    git(clone, "checkout", "-q", "origin/machine/gamma", "--", ".")
    (clone / "fa.md").write_text("A-MARKER\nCURATED\nL3\n")
    (clone / "fb.md").write_text("B-MARKER\n")
    git(clone, "add", "-A")
    git(clone, "commit", "-q", "-m", "maintainer: curated rewrite of A's net")
    git(clone, "push", "-q", "origin", "main")
    b_sha = git(clone, "rev-parse", "HEAD").strip()
    # ... and the ONE sanctioned force points the strip at the curated content
    git(clone, "push", "-q", "--force-with-lease", "origin", "main:refs/heads/machine/gamma")

    # C on top of the A chain, never pushed
    if c_edits_same_line:
        (repo / "fa.md").write_text("A-MARKER\nC-EDIT\nL3\n")   # the line the curator rewrote
    else:
        (repo / "fc.md").write_text("C-MARKER\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "C work")
    c_sha = git(repo, "rev-parse", "HEAD").strip()
    return {"home": home, "a_sha": a_sha, "b_sha": b_sha, "c_sha": c_sha}


def test_retired_reset_never_writes_remote(three_branch_repo, tmp_path):
    """A pending transport T plus --reset-branch --confirm-consumed must exit 12 with a `retired:`
    diagnostic and leave every bare-remote ref, local ref and the worktree exactly as it was."""
    home = tmp_path / "home"
    write_state(home, three_branch_repo, "gamma")
    before = remote_refs(three_branch_repo)
    pending_tip = before["refs/heads/machine/gamma"]
    assert pending_tip != before["refs/heads/main"]      # T genuinely carries unmerged work
    local_before = {
        "head": git(three_branch_repo, "rev-parse", "HEAD").strip(),
        "main": git(three_branch_repo, "rev-parse", "main").strip(),
        "branch": git(three_branch_repo, "rev-parse", "machine/gamma").strip(),
        "status": git(three_branch_repo, "status", "--porcelain"),
    }

    r = run_cli(three_branch_repo, home, "--reset-branch", "testlab", "--confirm-consumed")

    assert r.returncode == 12
    assert "retired:" in r.stderr
    assert "--reset-branch" in r.stderr
    assert "testlab" in r.stderr
    assert remote_refs(three_branch_repo) == before
    assert git(three_branch_repo, "rev-parse", "HEAD").strip() == local_before["head"]
    assert git(three_branch_repo, "rev-parse", "main").strip() == local_before["main"]
    assert git(three_branch_repo, "rev-parse", "machine/gamma").strip() == local_before["branch"]
    assert git(three_branch_repo, "status", "--porcelain") == local_before["status"]


def test_retired_reset_refuses_even_in_dry_run(three_branch_repo, tmp_path):
    """No green path exists for the retired mode — not even a dry-run reports a would-be reset."""
    home = tmp_path / "home"
    write_state(home, three_branch_repo, "gamma")
    before = remote_refs(three_branch_repo)

    r = run_cli(three_branch_repo, home, "--reset-branch", "gamma", "--dry-run")

    assert r.returncode == 12
    assert "retired:" in r.stderr
    assert "would push" not in r.stderr
    assert remote_refs(three_branch_repo) == before


def test_retired_refresh_strip_never_invokes_rebase(three_branch_repo, tmp_path, monkeypatch):
    """The rebase-based replay must be gone: any `git rebase` invocation fails the test."""
    s = strip_scenario(three_branch_repo, tmp_path)   # divergent never-pushed C on machine/gamma
    monkeypatch.setenv("HERMES_HOME", str(s["home"]))
    rebase_calls: list[list[str]] = []
    real_run = integrate.subprocess.run

    def guarded(cmd, *args, **kwargs):
        if isinstance(cmd, (list, tuple)) and "rebase" in cmd:
            rebase_calls.append(list(cmd))
            raise AssertionError("rebase must not be invoked for contributor work")
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(integrate.subprocess, "run", guarded)
    code, notes = integrate.refresh_strip(three_branch_repo)

    assert code == 12, notes
    assert "retired:" in " ".join(notes)
    assert rebase_calls == []
    assert git(three_branch_repo, "rev-parse", "HEAD").strip() == s["c_sha"]


def test_retired_refresh_strip_preserves_divergent_work(three_branch_repo, tmp_path):
    """A divergent never-pushed commit and the remote strip both survive; no rebase state is left."""
    s = strip_scenario(three_branch_repo, tmp_path)
    repo, home = three_branch_repo, s["home"]
    strip_before = remote_refs(repo)["refs/heads/machine/gamma"]

    r = run_cli(repo, home, "--refresh-strip")

    assert r.returncode == 12
    assert "retired:" in r.stderr and "rebase" in r.stderr
    assert git(repo, "rev-parse", "HEAD").strip() == s["c_sha"]
    assert remote_refs(repo)["refs/heads/machine/gamma"] == strip_before == s["b_sha"]
    assert git(repo, "branch", "--show-current").strip() == "machine/gamma"
    assert git(repo, "status", "--porcelain") == ""
    assert not (repo / ".git" / "rebase-merge").exists()
    assert not (repo / ".git" / "rebase-apply").exists()


def test_note_pushed_updates_state(three_branch_repo, tmp_path):
    home = tmp_path / "home"
    state_path = write_state(home, three_branch_repo, "gamma")
    git(three_branch_repo, "checkout", "-q", "machine/gamma")
    git(three_branch_repo, "push", "-q", "origin", "machine/gamma")
    r = run_cli(three_branch_repo, home, "--note-pushed")
    assert r.returncode == 0, r.stderr
    head = git(three_branch_repo, "rev-parse", "HEAD").strip()
    assert f"strip: last-pushed-tip -> {head[:12]}" in r.stderr
    state = json.loads(state_path.read_text())
    assert state["last_pushed_tip"] == head


def test_note_pushed_refuses_a_stale_remote_tip(three_branch_repo, tmp_path):
    """The remote is the authority: a local commit that was never pushed is not
    recordable as the integrated transport tip."""
    home = tmp_path / "home"
    state_path = write_state(home, three_branch_repo, "gamma")
    before = state_path.read_bytes()
    git(three_branch_repo, "checkout", "-q", "machine/gamma")
    (three_branch_repo / "unpushed.md").write_text("local only\n")
    git(three_branch_repo, "add", "unpushed.md")
    git(three_branch_repo, "commit", "-q", "-m", "unpushed")
    r = run_cli(three_branch_repo, home, "--note-pushed")
    assert r.returncode == 12
    assert "push the reviewed tip first" in r.stderr
    assert state_path.read_bytes() == before


def test_note_pushed_dry_run_writes_no_state(three_branch_repo, tmp_path):
    home = tmp_path / "home"
    state_path = write_state(home, three_branch_repo, "gamma")
    before = state_path.read_bytes()
    git(three_branch_repo, "checkout", "-q", "machine/gamma")
    git(three_branch_repo, "push", "-q", "origin", "machine/gamma")
    r = run_cli(three_branch_repo, home, "--note-pushed", "--dry-run")
    assert r.returncode == 0, r.stderr
    assert state_path.read_bytes() == before


def test_retired_init_last_pushed_writes_no_state(three_branch_repo, tmp_path):
    """`--init-last-pushed` seeds the retired reset cursor; it must refuse with exit 12 and a
    `retired:` diagnostic without touching the state file, refs or index."""
    home = tmp_path / "home"
    state_path = write_state(home, three_branch_repo, "gamma")
    state_before = state_path.read_bytes()
    refs_before = remote_refs(three_branch_repo)

    r = run_cli(three_branch_repo, home, "--init-last-pushed")

    assert r.returncode == 12
    assert "retired:" in r.stderr and "--init-last-pushed" in r.stderr
    assert state_path.read_bytes() == state_before
    assert remote_refs(three_branch_repo) == refs_before
    assert git(three_branch_repo, "status", "--porcelain") == ""


# ---------------------------------------------------------------------------
# v3 CLI: real subprocess round-trip, stable monitor signal and dry-run proof.
# ---------------------------------------------------------------------------

V3_HELPER = SCRIPTS / "skill-repo-maintain.py"
V3_ENGINE = SCRIPTS / "skill-repo-sync.py"


def v3_git(repo: Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                         check=True, env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))
    return out.stdout.strip()


def v3_commit(repo: Path, text: str, message: str = "change",
              path: str = "skills/demo/SKILL.md") -> str:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    v3_git(repo, "add", "--", path)
    v3_git(repo, "commit", "-q", "-m", message)
    return v3_git(repo, "rev-parse", "HEAD")


@pytest.fixture()
def v3lab(tmp_path: Path) -> dict:
    """Disposable v3 maintainer lab: bare remote, contributor transport branch,
    maintainer clone on main, isolated store/vault/HERMES_HOME."""
    remote = tmp_path / "v3 origin.git"
    contributor = tmp_path / "v3 contributor"
    maintainer = tmp_path / "v3 maintainer"
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
    contributor.mkdir()
    v3_git(contributor, "init", "-q", "-b", "main")
    v3_git(contributor, "config", "user.name", "Contributor")
    v3_git(contributor, "config", "user.email", "contributor@example.invalid")
    base_text = "---\nname: demo\ndescription: Demonstration skill.\n---\n\n# Demo\n\nBase instruction.\n"
    v3_commit(contributor, base_text, message="base")
    v3_git(contributor, "remote", "add", "origin", str(remote))
    v3_git(contributor, "push", "-q", "-u", "origin", "main")
    v3_git(contributor, "checkout", "-q", "-b", "machine/testlab")
    v3_git(contributor, "push", "-q", "-u", "origin", "machine/testlab")

    subprocess.run(["git", "clone", "-q", "-b", "main", str(remote), str(maintainer)],
                   check=True)
    v3_git(maintainer, "config", "user.name", "Maintainer")
    v3_git(maintainer, "config", "user.email", "maintainer@example.invalid")

    store, vault, home = tmp_path / "v3 store", tmp_path / "v3 vault", tmp_path / "v3 home"
    for directory in (store, vault, home):
        directory.mkdir()
    config = {
        "schema": 3, "repo_id": "owned-skills", "remote": "origin",
        "maintainer_repo": str(maintainer), "runtime_roots": [str(contributor)],
        "policy": "skill-review-v1",
        "maintainer_identity": {"machine": "maintainer-test", "profile": "default",
                               "scope": "shared-generic"},
        "sources": [{"ref": "refs/heads/machine/testlab", "machine": "testlab",
                     "profile": "default", "scope": "shared-generic", "enabled": True}],
        "report": {"path": str(vault)},
    }
    (store / "maintainer.json").write_text(json.dumps(config), encoding="utf-8")
    (home / "skill-repo-sync.json").write_text(json.dumps({
        "version": "3.0.0", "machine": "testlab",
        "repos": [{"name": "contributor", "path": str(contributor), "remote": "origin"}],
        "ledger_cursor": 0,
    }), encoding="utf-8")
    return {"tmp": tmp_path, "remote": remote, "contributor": contributor,
            "maintainer": maintainer, "store": store, "vault": vault, "home": home,
            "base": v3_git(contributor, "rev-parse", "main")}


def v3_helper(lab: dict, *args: str, repo: Path | None = None,
              store: Path | None = None, home: Path | None = None):
    env = dict(os.environ, HERMES_HOME=str(home or lab["home"]), GIT_TERMINAL_PROMPT="0")
    return subprocess.run(
        [sys.executable, str(V3_HELPER), *args,
         "--repo", str(repo or lab["maintainer"]), "--store", str(store or lab["store"])],
        capture_output=True, text=True, env=env, check=False)


def v3_engine(lab: dict, *args: str, home: Path | None = None):
    env = dict(os.environ, HERMES_HOME=str(home or lab["home"]), GIT_TERMINAL_PROMPT="0")
    return subprocess.run([sys.executable, str(V3_ENGINE), *args], capture_output=True,
                          text=True, env=env, check=False)


def v3_offer(lab: dict, text: str | None = None) -> str:
    text = text or ("---\nname: demo\ndescription: Demonstration skill.\n---\n\n"
                    "# Demo\n\nBase instruction.\nA useful generic rule.\n")
    tip = v3_commit(lab["contributor"], text)
    v3_git(lab["contributor"], "push", "-q", "origin", "machine/testlab")
    return tip


REFACTOR_TEXT = ("---\nname: demo\ndescription: Demonstration skill.\n---\n\n"
                 "# Demo\n\nRefactored base instruction.\n")


def v3_refactor_branch(lab: dict, name: str = "refactor/topic") -> tuple[str, str]:
    """A developer's own refactor branch, pushed as a backup (not readiness)."""
    contributor = lab["contributor"]
    v3_git(contributor, "fetch", "-q", "origin")
    v3_git(contributor, "checkout", "-q", "-b", name, "origin/main")
    tip = v3_commit(contributor, REFACTOR_TEXT, message="refactor the demo instruction")
    v3_git(contributor, "push", "-q", "-u", "origin", name)
    return f"refs/heads/{name}", tip


def v3_refactor_brief(lab: dict) -> Path:
    path = lab["tmp"] / "refactor-brief.json"
    path.write_text(json.dumps({
        "summary": "Rewrite the demo instruction on the refactor branch",
        "intended_replacements": [{
            "path": "skills/demo/SKILL.md",
            "old_quote": "Base instruction.",
            "new_instruction": "Refactored base instruction.",
            "reason": "The refactor replaces the one demo instruction."}],
        "validation_notes": "The exact submitted tip was reviewed; no other path changes.",
    }), encoding="utf-8")
    return path


def v3_capture(lab: dict) -> dict:
    result = v3_helper(lab, "--capture-source", "refs/heads/machine/testlab")
    assert result.returncode == 0, result.stderr + result.stdout
    return json.loads(result.stdout)


def v3_review(candidate: dict, path: str = "skills/demo/SKILL.md",
              quote: str = "A useful generic rule.") -> dict:
    return {"schema": 1, "candidate_id": candidate["id"],
            "main_sha": candidate["main_sha"], "source_sha": candidate["source_sha"],
            "summary": "Accept a useful generic addition",
            "files": [{"path": path, "change_type": "addition", "decision": "accept",
                       "source_anchors": [{"ref": candidate["source_sha"], "path": path,
                                           "quote": quote}],
                       "reason": "Useful generic addition", "replacements": []}]}


def v3_prepare(lab: dict, cid: str, expect: int = 0):
    result = v3_helper(lab, "--prepare", cid)
    assert result.returncode == expect, result.stderr + result.stdout
    return json.loads(result.stdout) if result.stdout.strip() else {}


def v3_record(lab: dict, candidate: dict, review: dict | None = None):
    review_file = lab["tmp"] / "review.json"
    review_file.write_text(json.dumps(review or v3_review(candidate)), encoding="utf-8")
    return v3_helper(lab, "--record-review", candidate["id"],
                     "--review-file", str(review_file))


def v3_render(lab: dict, cid: str, expect: int = 0) -> dict:
    result = v3_helper(lab, "--render-report", cid)
    assert result.returncode == expect, result.stderr + result.stdout
    return json.loads(result.stdout)


def v3_deliver_review(lab: dict, cid: str, rendered: dict) -> Path:
    target = lab["vault"] / rendered["report_relative_path"]
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(lab["store"] / "candidates" / cid / "review.md", target)
    return target


def v3_deliver_result(lab: dict, cid: str, rendered: dict) -> Path:
    relative = "skill-sync-" + cid + "-result.md"
    target = lab["vault"] / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(lab["store"] / "candidates" / cid / "result.md", target)
    return target


def v3_tree(root: Path) -> dict[str, str]:
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


def v3_repo_state(repo: Path) -> dict:
    git_dir = Path(v3_git(repo, "rev-parse", "--absolute-git-dir"))
    fetch = git_dir / "FETCH_HEAD"
    index = git_dir / "index"
    return {
        "head": v3_git(repo, "rev-parse", "HEAD"),
        "refs": v3_git(repo, "for-each-ref", "--format=%(refname) %(objectname)"),
        "fetch_head": fetch.read_bytes().hex() if fetch.is_file() else "",
        "index_sha256": hashlib.sha256(index.read_bytes()).hexdigest() if index.is_file() else "",
        "files": v3_tree(repo),
    }


def v3_remote_state(lab: dict) -> str:
    return v3_git(lab["remote"], "for-each-ref", "--format=%(refname) %(objectname)")


def v3_snapshot(lab: dict) -> dict:
    """Everything a dry run must leave byte-identical (state, refs incl.
    FETCH_HEAD, index, worktree inventory, reports, bare remote)."""
    return {
        "store": v3_tree(lab["store"]),
        "vault": v3_tree(lab["vault"]),
        "maintainer": v3_repo_state(lab["maintainer"]),
        "contributor": v3_repo_state(lab["contributor"]),
        "remote": v3_remote_state(lab),
    }


def test_cli_round_trip_capture_to_complete(v3lab):
    """Real subprocess HELPER: capture -> prepare -> record-review -> render ->
    verify -> integrate -> reconcile -> render-result -> verify-result."""
    v3_offer(v3lab)
    candidate = v3_capture(v3lab)
    assert candidate["status"] == "captured" and candidate["kind"] == "transport"

    prepared = v3_prepare(v3lab, candidate["id"])
    assert prepared["status"] == "prepared"
    assert prepared["input_paths"] == ["skills/demo/SKILL.md"]

    recorded = v3_record(v3lab, candidate)
    assert recorded.returncode == 0, recorded.stderr + recorded.stdout
    reviewed = json.loads(recorded.stdout)
    assert reviewed["status"] == "reviewed" and reviewed["reviewed_tree"]

    rendered = v3_render(v3lab, candidate["id"])
    assert (v3lab["store"] / "candidates" / candidate["id"] / "review.md").is_file()
    v3_deliver_review(v3lab, candidate["id"], rendered)
    verified = v3_helper(v3lab, "--verify-report", candidate["id"])
    assert verified.returncode == 0, verified.stderr + verified.stdout
    assert json.loads(verified.stdout)["status"] == "report-verified"

    integrated = v3_helper(v3lab, "--integrate", candidate["id"])
    assert integrated.returncode == 0, integrated.stderr + integrated.stdout
    integrated_state = json.loads(integrated.stdout)
    assert integrated_state["status"] == "integrated" and integrated_state["result_sha"]
    p = integrated_state["result_sha"]
    assert v3_git(v3lab["maintainer"], "show", "-s", "--format=%P", p).split() == [
        candidate["main_sha"], candidate["source_sha"]]
    assert v3_git(v3lab["contributor"], "ls-remote", "origin", "refs/heads/main").split()[0] == p

    reconciled = v3_helper(v3lab, "--reconcile", candidate["id"])
    assert reconciled.returncode == 0, reconciled.stderr + reconciled.stdout
    assert json.loads(reconciled.stdout)["result_sha"] == p

    result_render = v3_helper(v3lab, "--render-result", candidate["id"])
    assert result_render.returncode == 0, result_render.stderr + result_render.stdout
    result_payload = json.loads(result_render.stdout)
    assert (v3lab["store"] / "candidates" / candidate["id"] / "result.md").is_file()
    v3_deliver_result(v3lab, candidate["id"], result_payload)

    completed = v3_helper(v3lab, "--verify-result", candidate["id"])
    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert json.loads(completed.stdout)["status"] == "complete"


def test_submit_refactor_cli_records_exact_tip(v3lab):
    """--submit-refactor is the only CLI path that makes a refactor ready."""
    ref, tip = v3_refactor_branch(v3lab)
    brief = v3_refactor_brief(v3lab)

    usage = v3_helper(v3lab, "--submit-refactor", ref)
    assert usage.returncode == 2
    assert "--tip" in usage.stderr and "--brief" in usage.stderr

    bad_ref = v3_helper(v3lab, "--submit-refactor", "refs/heads/machine/testlab",
                        "--tip", tip, "--brief", str(brief))
    assert bad_ref.returncode == 12 and "refactor" in bad_ref.stderr

    bad_tip = v3_helper(v3lab, "--submit-refactor", ref,
                        "--tip", v3lab["base"], "--brief", str(brief))
    assert bad_tip.returncode == 12
    assert "not the current remote tip" in bad_tip.stderr

    command_brief = v3lab["tmp"] / "command-brief.json"
    command_brief.write_text(json.dumps({
        "summary": "x", "intended_replacements": [], "validation_notes": "y",
        "commands": ["rm -rf /"]}), encoding="utf-8")
    bad_brief = v3_helper(v3lab, "--submit-refactor", ref,
                          "--tip", tip, "--brief", str(command_brief))
    assert bad_brief.returncode == 12 and "commands" in bad_brief.stderr

    missing_brief = v3_helper(v3lab, "--submit-refactor", ref, "--tip", tip,
                              "--brief", str(v3lab["tmp"] / "absent.json"))
    assert missing_brief.returncode == 12

    missing_store = v3_helper(v3lab, "--submit-refactor", ref, "--tip", tip,
                              "--brief", str(brief), store=v3lab["tmp"] / "no-store")
    assert missing_store.returncode == 13

    ok = v3_helper(v3lab, "--submit-refactor", ref, "--tip", tip, "--brief", str(brief))
    assert ok.returncode == 0, ok.stderr + ok.stdout
    payload = json.loads(ok.stdout)
    assert payload["mode"] == "submit-refactor"
    assert payload["ref"] == ref and payload["tip"] == tip
    assert payload["main_sha"] == v3lab["base"]
    assert payload["maintainer_identity"]["machine"] == "maintainer-test"
    assert (v3lab["store"] / "refactor-submissions" / f"{payload['candidate']}.json").is_file()

    pending = v3_helper(v3lab, "--pending")
    assert pending.returncode == 0 and pending.stdout == f"pending {payload['candidate']}\n"

    captured = v3_helper(v3lab, "--capture-source", ref)
    assert captured.returncode == 0, captured.stderr + captured.stdout
    state = json.loads(captured.stdout)
    assert state["kind"] == "refactor" and state["source_sha"] == tip
    assert state["id"] == payload["candidate"]


def test_cli_exit_codes_and_repo_store_agreement(v3lab):
    """Missing config 13, usage 2, mismatch policy 12, retired 12, success 0."""
    v3_offer(v3lab)
    other = v3lab["tmp"] / "other clone"
    subprocess.run(["git", "clone", "-q", "-b", "main", str(v3lab["remote"]), str(other)],
                   check=True)

    mismatch = v3_helper(v3lab, "--capture-source", "refs/heads/machine/testlab",
                         repo=other)
    assert mismatch.returncode == 12
    assert "maintainer_repo" in mismatch.stderr

    missing = v3_helper(v3lab, "--capture-source", "refs/heads/machine/testlab",
                        store=v3lab["tmp"] / "no-store")
    assert missing.returncode == 13
    assert "maintainer config missing" in missing.stderr

    missing_pending = v3_helper(v3lab, "--pending", store=v3lab["tmp"] / "no-store")
    assert missing_pending.returncode == 13
    assert missing_pending.stdout == ""
    assert "maintainer config missing" in missing_pending.stderr

    usage = subprocess.run([sys.executable, str(V3_HELPER)], capture_output=True, text=True)
    assert usage.returncode == 2

    version = subprocess.run([sys.executable, str(V3_HELPER), "--version"],
                             capture_output=True, text=True)
    assert version.returncode == 0 and "3.0.0" in version.stdout
    help_text = subprocess.run([sys.executable, str(V3_HELPER), "--help"],
                               capture_output=True, text=True)
    assert help_text.returncode == 0
    for mode in ("--capture-source", "--record-review", "--integrate", "--pending", "--retry"):
        assert mode in help_text.stdout
    assert "RETIRED" in help_text.stdout

    retired = v3_helper(v3lab, "--collect")
    assert retired.returncode == 12
    assert "retired:" in retired.stderr and "--collect" in retired.stderr

    ok = v3_helper(v3lab, "--capture-source", "refs/heads/machine/testlab")
    assert ok.returncode == 0 and json.loads(ok.stdout)["status"] == "captured"


def test_record_review_hard_check_failure_exits_10(v3lab):
    """Required checks fail -> exit 10 and no reviewed journal is written."""
    v3_commit(v3lab["contributor"],
              "---\nname: demo\ndescription: Demonstration skill.\n---\n\n# Demo\n\n"
              "Base instruction.\nA useful generic rule.\n",
              message="generic rule")
    audit = v3lab["contributor"] / "skills/skill-library-maintenance/scripts/audit-skill-library.py"
    audit.parent.mkdir(parents=True, exist_ok=True)
    audit.write_text("import sys\n\nsys.exit(1)\n", encoding="utf-8")
    v3_git(v3lab["contributor"], "add", "--", str(audit.relative_to(v3lab["contributor"])))
    v3_git(v3lab["contributor"], "commit", "-q", "-m", "failing package audit runner")
    v3_git(v3lab["contributor"], "push", "-q", "origin", "machine/testlab")

    candidate = v3_capture(v3lab)
    v3_prepare(v3lab, candidate["id"])
    review = v3_review(candidate)
    review["files"].append({
        "path": "skills/skill-library-maintenance/scripts/audit-skill-library.py",
        "change_type": "addition", "decision": "accept",
        "source_anchors": [{"ref": candidate["source_sha"],
                            "path": "skills/skill-library-maintenance/scripts/"
                                    "audit-skill-library.py",
                            "quote": "sys.exit(1)"}],
        "reason": "Adversarial failing runner fixture", "replacements": []})
    result = v3_record(v3lab, candidate, review)
    assert result.returncode == 10, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "checks-failed"
    assert "library-audit" in payload["failed"]
    assert not (v3lab["store"] / "candidates" / candidate["id"] / "review.json").exists()
    assert json.loads((v3lab["store"] / "candidates" / candidate["id"]
                       / "state.json").read_text())["status"] == "prepared"


def test_pending_cli_reports_candidate_ids(v3lab):
    v3_offer(v3lab)
    first = v3_helper(v3lab, "--pending")
    assert first.returncode == 0 and first.stderr == ""
    lines = first.stdout.splitlines()
    assert len(lines) == 1 and lines[0].startswith("pending ")
    cid = lines[0].split()[1]
    assert len(cid) == 64 and first.stdout == v3_helper(v3lab, "--pending").stdout

    # Consume the tip by merging it into main: the line disappears.
    consumer = v3lab["tmp"] / "consumer"
    subprocess.run(["git", "clone", "-q", "-b", "main", str(v3lab["remote"]), str(consumer)],
                   check=True)
    v3_git(consumer, "config", "user.name", "Consumer")
    v3_git(consumer, "config", "user.email", "consumer@example.invalid")
    v3_git(consumer, "merge", "-q", "--no-ff", "-m", "consume", "origin/machine/testlab")
    v3_git(consumer, "push", "-q", "origin", "main")
    assert v3_helper(v3lab, "--pending").stdout == ""


def test_pending_error_signal_is_stable(v3lab):
    """A technical monitor failure is exactly one stable stdout line plus stderr
    diagnostics; recovery changes the hash back to real pending lines."""
    v3_offer(v3lab)
    v3_git(v3lab["maintainer"], "remote", "set-url", "origin",
           str(v3lab["tmp"] / "missing remote.git"))
    first = v3_helper(v3lab, "--pending")
    second = v3_helper(v3lab, "--pending")
    assert first.returncode == 0 and second.returncode == 0
    assert first.stdout == "error: monitor-unhealthy\n"
    assert second.stdout == first.stdout
    assert first.stderr.startswith("pending monitor:") and first.stderr.strip()

    v3_git(v3lab["maintainer"], "remote", "set-url", "origin", str(v3lab["remote"]))
    recovered = v3_helper(v3lab, "--pending")
    assert recovered.returncode == 0
    assert recovered.stdout.startswith("pending ")
    assert recovered.stdout != first.stdout


def test_pending_dry_run_reports_cannot_determine_without_fetch(v3lab):
    v3_offer(v3lab)
    v3_git(v3lab["maintainer"], "update-ref", "-d", "refs/remotes/origin/machine/testlab")
    result = v3_helper(v3lab, "--pending", "--dry-run")
    assert result.returncode == 0
    assert result.stdout == ""
    assert "cannot determine without fetch" in result.stderr


def v3_setup_mode(lab: dict, mode: str) -> tuple[list[str], bool]:
    """Advance the lab to the state one dry-run mode needs; return its argv and
    whether it is an engine mode."""
    if mode == "engine-stage":
        (lab["contributor"] / "notes.md").write_text("pending sweep content\n", encoding="utf-8")
        return ["--stage", "--dry-run"], True
    if mode == "engine-sync":
        return ["--sync-from-main", "--dry-run"], True

    if mode == "submit-refactor":
        ref, tip = v3_refactor_branch(lab)
        return ["--submit-refactor", ref, "--tip", tip,
                "--brief", str(v3_refactor_brief(lab))], False

    if mode == "retry":
        link = lab["contributor"] / "skills/demo/link"
        os.symlink("SKILL.md", link)
        v3_git(lab["contributor"], "add", "--", "skills/demo/link")
        v3_git(lab["contributor"], "commit", "-q", "-m", "symlink source")
        v3_git(lab["contributor"], "push", "-q", "origin", "machine/testlab")
        candidate = v3_capture(lab)
        v3_prepare(lab, candidate["id"], expect=12)
        return ["--retry", candidate["id"]], False

    v3_offer(lab)
    candidate = v3_capture(lab)
    cid = candidate["id"]
    if mode == "capture":
        return ["--capture-source", "refs/heads/machine/testlab"], False
    v3_prepare(lab, cid)
    if mode == "prepare":
        return ["--prepare", cid], False
    if mode == "record-review":
        review_file = lab["tmp"] / "dry-run-review.json"
        review_file.write_text(json.dumps(v3_review(candidate)), encoding="utf-8")
        return ["--record-review", cid, "--review-file", str(review_file)], False
    recorded = v3_record(lab, candidate)
    assert recorded.returncode == 0, recorded.stderr + recorded.stdout
    if mode == "render-report":
        return ["--render-report", cid], False
    rendered = v3_render(lab, cid)
    v3_deliver_review(lab, cid, rendered)
    if mode == "verify-report":
        return ["--verify-report", cid], False
    verified = v3_helper(lab, "--verify-report", cid)
    assert verified.returncode == 0, verified.stderr + verified.stdout
    if mode == "integrate":
        return ["--integrate", cid], False
    integrated = v3_helper(lab, "--integrate", cid)
    assert integrated.returncode == 0, integrated.stderr + integrated.stdout
    if mode == "reconcile":
        return ["--reconcile", cid], False
    if mode == "render-result":
        return ["--render-result", cid], False
    result = v3_helper(lab, "--render-result", cid)
    assert result.returncode == 0, result.stderr + result.stdout
    v3_deliver_result(lab, cid, json.loads(result.stdout))
    if mode == "verify-result":
        return ["--verify-result", cid], False
    raise AssertionError(f"unknown mode {mode}")


DRY_RUN_MODES = ("capture", "prepare", "record-review", "render-report", "verify-report",
                 "integrate", "reconcile", "render-result", "verify-result", "retry",
                 "submit-refactor", "engine-stage", "engine-sync")


@pytest.mark.parametrize("mode", DRY_RUN_MODES)
def test_dry_run_performs_no_writes(v3lab, mode):
    """Every mutating mode under --dry-run leaves the store, both repositories
    (HEAD, all refs incl. FETCH_HEAD, index, worktree inventory), the report
    root and the bare remote byte-identical."""
    args, engine = v3_setup_mode(v3lab, mode)
    before = v3_snapshot(v3lab)
    if engine:
        result = v3_engine(v3lab, *args)
    else:
        result = v3_helper(v3lab, *args, "--dry-run")
    after = v3_snapshot(v3lab)
    assert result.returncode == 0, result.stderr + result.stdout
    assert after == before
    if not engine:
        payload = json.loads(result.stdout)
        assert payload["dry_run"] is True, payload


def test_helper_selfcheck_reports_observed_facts_only(v3lab):
    result = v3_helper(v3lab, "--selfcheck")
    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["script_version"] == "3.0.0"
    assert payload["core_version"] == "3.0.0"
    assert payload["installer_version"] == "3.0.0"
    assert payload["maintainer_config"].endswith("maintainer.json")
    assert payload["report_directory_present"] is True
    assert payload["maintainer_lock"] == "not held"
    assert "not inspected" in payload["hooks"]
    assert "healthy" not in json.dumps(payload).lower()   # no fabricated hook-health claim

    missing = v3_helper(v3lab, "--selfcheck", store=v3lab["tmp"] / "none")
    assert missing.returncode == 13
    assert "maintainer config missing" in missing.stderr


def test_capture_dry_run_reports_cannot_determine_without_fetch(v3lab):
    v3_offer(v3lab)
    v3_git(v3lab["maintainer"], "update-ref", "-d", "refs/remotes/origin/machine/testlab")
    result = v3_helper(v3lab, "--capture-source", "refs/heads/machine/testlab", "--dry-run")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["determined"] is False
    assert payload["reason"] == "cannot determine without fetch"
    assert "cannot determine without fetch" in result.stderr
    assert not (v3lab["store"] / "candidates").exists()


# --- deployment artifacts: render + drift detection -----------------------------------------------

ARTIFACT_NAMES = {"maintainer-cron-prompt", "pre-integration-cron-prompt",
                  "maintain-monitor-script", "stage-sweep-script",
                  "stage-sweep-pointer", "maintain-monitor-pointer"}


def artifact_lab(tmp_path: Path) -> tuple[Path, Path, Path, dict]:
    home = tmp_path / "art home"
    (home / "cron").mkdir(parents=True)
    maintainer_repo = tmp_path / "art maintainer"
    assets_src = SCRIPTS.parent / "assets"
    assets_dst = maintainer_repo / "skills" / "skill-library-maintenance" / "assets"
    shutil.copytree(assets_src, assets_dst)
    store = tmp_path / "art store"
    store.mkdir()
    config = {"maintainer_repo": str(maintainer_repo),
              "maintainer_identity": {"machine": "durin", "profile": "default",
                                      "scope": "shared-generic"}}
    jobs = {"jobs": [{"id": "job-maintainer", "name": "skill-repo maintainer (nightly)", "prompt": "stale"},
                     {"id": "job-pre", "name": "skill-repo pre-integration (instance review)",
                      "prompt": "stale"}]}
    (home / "cron" / "jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
    return home, store, assets_dst, config


def fake_cron_writer(monkeypatch, home: Path) -> None:
    def write(home_path: Path, job_id: str, text: str) -> None:
        path = home_path / "cron" / "jobs.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        for job in payload["jobs"]:
            if job["id"] == job_id:
                job["prompt"] = text
        path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(integrate, "_write_cron_prompt", write)
    monkeypatch.setattr(integrate, "hermes_home", lambda: home)


def test_render_artifacts_records_digests_and_is_idempotent(tmp_path: Path, monkeypatch) -> None:
    home, store, assets, config = artifact_lab(tmp_path)
    fake_cron_writer(monkeypatch, home)

    first = integrate.render_artifacts(store, config, home)
    assert set(first["rendered"]) == ARTIFACT_NAMES
    second = integrate.render_artifacts(store, config, home)
    assert second["rendered"] == []                       # idempotent: nothing rewritten
    assert integrate.artifact_problems(store, config, home) == []

    manifest = json.loads((store / "rendered.json").read_text(encoding="utf-8"))
    assert set(manifest["artifacts"]) == ARTIFACT_NAMES
    for record in manifest["artifacts"].values():
        assert record["asset_sha256"] == record["rendered_sha256"]

    shim = (store / "scripts" / "skill-repo-maintain-monitor.sh").read_text(encoding="utf-8")
    assert "skill-repo-maintain.py\" --pending" in shim
    assert str(store) in shim and "{" not in shim        # placeholders resolved
    prompt = json.loads((home / "cron" / "jobs.json").read_text(encoding="utf-8"))["jobs"][0]["prompt"]
    assert str(store) in prompt and "{store}" not in prompt


def test_artifact_drift_is_reported_and_render_clears_it(tmp_path: Path, monkeypatch) -> None:
    home, store, assets, config = artifact_lab(tmp_path)
    fake_cron_writer(monkeypatch, home)
    integrate.render_artifacts(store, config, home)
    assert integrate.artifact_problems(store, config, home) == []

    asset = assets / "maintainer-cron-prompt.md.example"
    asset.write_text(asset.read_text(encoding="utf-8") + "\nZusätzlicher Hinweis.\n", encoding="utf-8")
    drift = integrate.artifact_problems(store, config, home)
    assert any("maintainer-cron-prompt" in item and "asset changed" in item for item in drift)

    integrate.render_artifacts(store, config, home)
    assert integrate.artifact_problems(store, config, home) == []

    shim = store / "scripts" / "skill-repo-sync-stage.sh"
    shim.write_text(shim.read_text(encoding="utf-8") + "# tampered\n", encoding="utf-8")
    tampered = integrate.artifact_problems(store, config, home)
    assert any("stage-sweep-script" in item and "differs" in item for item in tampered)

    integrate.render_artifacts(store, config, home)
    assert integrate.artifact_problems(store, config, home) == []

    pointer = home / "scripts" / "skill-repo-sync-stage.sh"
    assert pointer.read_text(encoding="utf-8").startswith("#!/bin/sh")
    assert str(store / "scripts" / "skill-repo-sync-stage.sh") in pointer.read_text(encoding="utf-8")
    pointer.unlink()
    missing = integrate.artifact_problems(store, config, home)
    assert any("pointer is missing" in item for item in missing)
    integrate.render_artifacts(store, config, home)
    assert integrate.artifact_problems(store, config, home) == []


def test_render_artifacts_dry_run_writes_nothing(tmp_path: Path, monkeypatch) -> None:
    home, store, assets, config = artifact_lab(tmp_path)
    fake_cron_writer(monkeypatch, home)
    before_jobs = (home / "cron" / "jobs.json").read_bytes()

    result = integrate.render_artifacts(store, config, home, dry_run=True)

    assert result["dry_run"] is True and set(result["rendered"]) == ARTIFACT_NAMES
    assert (home / "cron" / "jobs.json").read_bytes() == before_jobs
    assert not (store / "rendered.json").exists()
    assert not (store / "scripts").exists()
    assert not (home / "scripts").exists()          # pointers are not written either
