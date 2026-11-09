# skills/skill-library-maintenance/tests/test_skill_repo_consolidate.py
"""Behavioral tests for skill-repo-consolidate.py (curator helpers) and the
staging curation scan. Self-contained: builds disposable repos, never touches a live one."""
from __future__ import annotations

import importlib.util
import json
import os
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


consolidate = _load("consolidate_under_test", SCRIPTS / "skill-repo-consolidate.py")


def git(repo: Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)
    return out.stdout

@pytest.fixture()
def three_branch_repo(tmp_path: Path) -> Path:
    """main with two files; three machine branches; gamma+conflict-branch overlap main."""
    repo = tmp_path / "skills"
    repo.mkdir()
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

    remote = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-q", "origin", "main",
        "refs/heads/machine/gamma:refs/heads/machine/gamma",
        "refs/heads/machine/alpha:refs/heads/machine/alpha",
        "refs/heads/machine/beta:refs/heads/machine/beta")
    return repo

def test_merge_map_separates_clean_from_conflict(three_branch_repo, tmp_path):
    out = tmp_path / "out"
    code, notes = consolidate.merge_map(three_branch_repo, "gamma", out)
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
    code, notes = consolidate.merge_map(three_branch_repo, "gamma", out)
    assert code == 0, notes
    report = json.loads((out / "merge-map.json").read_text())
    assert report["max_packet_lines"] == 80
    packets = json.loads((out / "conflict-packets.json").read_text())
    by_file = {p["file"]: p for p in packets}
    assert by_file["d.md"]["oversized"] is True     # whole block kept, 120 lines > 80
    assert by_file["a.md"]["oversized"] is False    # small conflict stays unflagged


def test_apply_decisions_resolves_blocks_in_order(three_branch_repo, tmp_path):
    out = tmp_path / "out"
    consolidate.merge_map(three_branch_repo, "gamma", out)
    decisions = {"decisions": [
        {"file": "a.md", "block": 0, "action": "synthesize", "text": "ONE-RULE-VERSION\n"}]}
    dpath = tmp_path / "decisions.json"
    dpath.write_text(json.dumps(decisions))
    code, notes = consolidate.apply_decisions(three_branch_repo, dpath, out)
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
    code, notes = consolidate.merge_map(three_branch_repo, "gamma", out)
    assert code == 0, notes
    packets = json.loads((out / "conflict-packets.json").read_text())
    assert sorted(p["block"] for p in packets if p["file"] == "a.md") == [0, 1]

    # only block 0 decided — block 1 must be named in the refusal
    decisions = {"decisions": [{"file": "a.md", "block": 0, "action": "ours"}]}
    dpath = tmp_path / "decisions.json"
    dpath.write_text(json.dumps(decisions))
    code, notes = consolidate.apply_decisions(three_branch_repo, dpath, out)
    assert code == 12
    msg = " ".join(notes)
    assert "a.md: missing decisions for conflict block index(es) 1" in msg

    # a file the decisions JSON omits entirely is missing just as much (R2)
    empty = tmp_path / "empty-decisions.json"
    empty.write_text(json.dumps({"decisions": []}))
    code2, notes2 = consolidate.apply_decisions(three_branch_repo, empty, out)
    assert code2 == 12
    msg2 = " ".join(notes2)
    assert "a.md: missing decisions for conflict block index(es) 0, 1" in msg2


def test_apply_decisions_drop_removes_the_block(three_branch_repo, tmp_path):
    """action 'drop' deletes the conflicted region entirely (no text required)."""
    out = tmp_path / "out"
    consolidate.merge_map(three_branch_repo, "gamma", out)
    decisions = {"decisions": [{"file": "a.md", "block": 0, "action": "drop"}]}
    dpath = tmp_path / "decisions.json"
    dpath.write_text(json.dumps(decisions))
    code, notes = consolidate.apply_decisions(three_branch_repo, dpath, out)
    assert code == 0, notes
    resolved = (three_branch_repo / "a.md").read_text()
    assert "MAIN-EDIT" not in resolved and "GAMMA-EDIT" not in resolved
    assert "<<<" not in resolved and "line3" in resolved


def test_lock_live_check_ignores_fresh_claims_and_refuses_old_ones(three_branch_repo, tmp_path):
    """A fresh claim is this very run (age-based self-exclusion); an old claim blocks."""
    import sqlite3
    from datetime import datetime, timezone

    db = tmp_path / "executions.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE executions (id TEXT PRIMARY KEY, job_id TEXT, source TEXT, "
                "process_id TEXT, pid INTEGER, process_started_at INTEGER, status TEXT, "
                "claimed_at TEXT, started_at TEXT, finished_at TEXT, error TEXT)")
    fresh = datetime.now(tz=timezone.utc).isoformat()
    con.execute("INSERT INTO executions VALUES ('own-claim','j','direct','p',1,0,"
                "'running',?,NULL,NULL,NULL)", (fresh,))
    con.commit()
    con.close()
    code, notes = consolidate.acquire_lock(three_branch_repo, ttl_seconds=10800, cron_db=db)
    assert code == 0, notes

    # a claim from minutes ago is a genuinely different run in flight
    con = sqlite3.connect(db)
    con.execute("INSERT INTO executions VALUES ('other-claim','j','direct','p',2,0,"
                "'running','2026-01-01T00:00:00',NULL,NULL,NULL)")
    con.commit()
    con.close()
    Path(three_branch_repo / ".git" / "hermes-consolidate.lock").unlink(missing_ok=True)
    code2, notes2 = consolidate.acquire_lock(three_branch_repo, ttl_seconds=10800, cron_db=db)
    assert code2 == 12 and "other execution" in notes2[0]


def test_lock_is_single_flight_and_expires(three_branch_repo, tmp_path):
    code, notes = consolidate.acquire_lock(three_branch_repo, ttl_seconds=10800, cron_db=None)
    assert code == 0, notes
    code2, notes2 = consolidate.acquire_lock(three_branch_repo, ttl_seconds=10800, cron_db=None)
    assert code2 == 12 and "already running" in notes2[0]
    # stale lock (crashed run): backdate the marker -> acquisition succeeds again
    lock = three_branch_repo / ".git" / "hermes-consolidate.lock"
    os.utime(lock, (1, 1))
    code3, _ = consolidate.acquire_lock(three_branch_repo, ttl_seconds=10800, cron_db=None)
    assert code3 == 0


def test_curation_scan_flags_duplicates_and_pointers(three_branch_repo):
    engine = consolidate.srs  # the engine module the consolidate script already loads
    added = [
        ("a.md", "a totally fresh rule line with enough words to matter here"),
        ("a.md", "line1"),                      # short: never a dup candidate
        ("b.md", "/home" + "/user/something"),  # instance pointer (split literal: scanner flags it at runtime, the diff gate stays clean)
    ]
    findings = engine.curation_scan(three_branch_repo, added)
    kinds = sorted(f["kind"] for f in findings)
    assert kinds == ["instance-pointer"]
    # duplicate: the exact normalized base line re-added, 8+ words
    (three_branch_repo / "a.md").write_text("wordy base line with more than eight words in it yes\n")
    git(three_branch_repo, "add", ".")
    git(three_branch_repo, "commit", "-m", "w", "-q")
    findings2 = engine.curation_scan(
        three_branch_repo, [("a.md", "wordy base line with more than eight words in it yes.")])
    assert [f["kind"] for f in findings2] == ["duplicate-candidate"]


def test_sync_from_main_warns_on_stage_report(three_branch_repo, tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    (home / "stage-report.json").write_text(
        json.dumps({"at": "2000-01-01T00:00:00+00:00", "needs_curation": 2, "findings": []}))
    code, notes = consolidate.srs.sync_from_main(three_branch_repo, "alpha", False, False)
    assert code == 0, notes
    assert any("2 addition(s) need curation" in n for n in notes)


def test_stage_scans_and_trails_needs_curation(three_branch_repo, tmp_path, monkeypatch):
    """R3: the staging scan is the safety net — stage-report.json + Needs-curation trailer."""
    home = tmp_path / "home"
    (home / "skills").mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(home))
    (home / "skill-repo-sync.json").write_text(
        json.dumps({"machine": "alpha", "repos": [{"path": str(three_branch_repo)}]}))
    git(three_branch_repo, "checkout", "-q", "machine/alpha")
    git(three_branch_repo, "branch", "--set-upstream-to=origin/machine/alpha", "machine/alpha")
    (three_branch_repo / "x.md").write_text("see /home" + "/user/pointer for details\n")

    code, notes = consolidate.srs.stage(three_branch_repo, "alpha", False, False)
    assert code == 0, notes
    report = json.loads((home / "stage-report.json").read_text())
    assert report["needs_curation"] == 1
    assert report["findings"][0]["kind"] == "instance-pointer"
    body = git(three_branch_repo, "log", "-1", "--format=%B")
    assert "Needs-curation: 1" in body
