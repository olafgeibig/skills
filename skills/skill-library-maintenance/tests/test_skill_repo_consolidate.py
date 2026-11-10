# skills/skill-library-maintenance/tests/test_skill_repo_consolidate.py
"""Behavioral tests for skill-repo-consolidate.py (consolidator helpers) and the
staging pre-consolidation scan. Self-contained: builds disposable repos, never touches a live one."""
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


def run_cli(repo: Path, home: Path, *args: str) -> subprocess.CompletedProcess:
    """Run the helper's real CLI under an isolated HERMES_HOME (the state file lives there)."""
    env = dict(os.environ)
    env["HERMES_HOME"] = str(home)
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "skill-repo-consolidate.py"), *args, "--repo", str(repo)],
        capture_output=True, text=True, env=env)


def write_state(home: Path, repo: Path, machine: str) -> Path:
    home.mkdir(parents=True, exist_ok=True)
    p = home / "skill-repo-sync.json"
    p.write_text(json.dumps({"machine": machine, "repos": [{"path": str(repo)}]}))
    return p


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
    code, notes = consolidate.preflight_scan(repo, out)
    report = json.loads((out / "preflight-findings.json").read_text())
    dangling = [f["detail"] for f in report["findings"]
                if f["kind"] == "dangling-reference" and f["file"] == "pkg/assets/note.md.example"]
    assert dangling == ["references/missing.md"], notes


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


def test_pre_consolidation_scan_flags_duplicates_and_pointers(three_branch_repo):
    engine = consolidate.srs  # the engine module the consolidate script already loads
    added = [
        ("a.md", "a totally fresh rule line with enough words to matter here"),
        ("a.md", "line1"),                      # short: never a dup candidate
        ("b.md", "/home" + "/user/something"),  # instance pointer (split literal: scanner flags it at runtime, the diff gate stays clean)
    ]
    findings = engine.pre_consolidation_scan(three_branch_repo, added)
    kinds = sorted(f["kind"] for f in findings)
    assert kinds == ["instance-pointer"]
    # duplicate: the exact normalized base line re-added, 8+ words
    (three_branch_repo / "a.md").write_text("wordy base line with more than eight words in it yes\n")
    git(three_branch_repo, "add", ".")
    git(three_branch_repo, "commit", "-m", "w", "-q")
    findings2 = engine.pre_consolidation_scan(
        three_branch_repo, [("a.md", "wordy base line with more than eight words in it yes.")])
    assert [f["kind"] for f in findings2] == ["duplicate-candidate"]


def test_sync_from_main_warns_on_stage_report(three_branch_repo, tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    (home / "stage-report.json").write_text(
        json.dumps({"at": "2000-01-01T00:00:00+00:00", "needs_pre_consolidation": 2, "findings": []}))
    code, notes = consolidate.srs.sync_from_main(three_branch_repo, "alpha", False, False)
    assert code == 0, notes
    assert any("2 addition(s) need pre-consolidation" in n for n in notes)


def test_stage_scans_and_trails_needs_pre_consolidation(three_branch_repo, tmp_path, monkeypatch):
    """R3: the staging scan is the safety net — stage-report.json + Needs-pre-consolidation trailer."""
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
    assert report["needs_pre_consolidation"] == 1
    assert report["findings"][0]["kind"] == "instance-pointer"
    body = git(three_branch_repo, "log", "-1", "--format=%B")
    assert "Needs-pre-consolidation: 1" in body


def strip_scenario(repo: Path, root: Path, c_edits_same_line: bool = False) -> dict:
    """Refresh-Strip scenario on machine/gamma: commit A (pushed, --note-pushed records it),
    then a CONSUMPTION simulated in a clone — the curated content lands on main as the
    consolidator's own commit and the one sanctioned force points the strip at it —
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

    # the consolidator (in a clone): A's net curated onto main as its OWN commit ...
    clone = root / "clone"
    subprocess.run(["git", "clone", "-q", remote_url, str(clone)], check=True)
    git(clone, "config", "user.email", "t@t")
    git(clone, "config", "user.name", "t")
    git(clone, "checkout", "-q", "-B", "main", "origin/main")
    git(clone, "checkout", "-q", "origin/machine/gamma", "--", ".")
    (clone / "fa.md").write_text("A-MARKER\nCURATED\nL3\n")
    (clone / "fb.md").write_text("B-MARKER\n")
    git(clone, "add", "-A")
    git(clone, "commit", "-q", "-m", "consolidator: curated rewrite of A's net")
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


def test_pending_is_byte_stable_and_tracks_net(three_branch_repo, tmp_path):
    """--pending is the monitor source: byte-stable sorted <host> <tip12> <n> lines where
    n counts the THREE-dot net (origin/main...<tip>) — main advancing alone never wakes it."""
    home = tmp_path / "home"
    write_state(home, three_branch_repo, "gamma")

    def out() -> str:
        r = run_cli(three_branch_repo, home, "--pending")
        assert r.returncode == 0, r.stderr          # the monitor source never fails
        assert r.stderr == ""
        return r.stdout

    first = out()
    lines = first.splitlines()
    assert first == out()                           # byte-identical on no change
    hosts = [ln.split()[0] for ln in lines]
    assert hosts == ["alpha", "beta", "gamma"]      # all three pending in the fixture
    assert hosts == sorted(hosts)                   # sorted, deterministic
    for ln in lines:
        host, tip12, n = ln.split()
        tip = git(three_branch_repo, "rev-parse", f"origin/machine/{host}").strip()
        assert tip12 == tip[:12]
        files = [f for f in git(three_branch_repo, "diff", "--name-only",
                                f"origin/main...{tip}").splitlines() if f.strip()]
        assert int(n) == len(files) and int(n) > 0

    # main advances with a commit that touches NO branch file -> output unchanged (three-dot proof)
    (three_branch_repo / "z.md").write_text("unrelated\n")
    git(three_branch_repo, "add", ".")
    git(three_branch_repo, "commit", "-q", "-m", "main unrelated advance")
    git(three_branch_repo, "push", "-q", "origin", "main")
    assert out() == first

    # a pushed branch change moves that branch's tip and count
    git(three_branch_repo, "checkout", "-q", "machine/alpha")
    (three_branch_repo / "y.md").write_text("alpha news\n")
    git(three_branch_repo, "add", ".")
    git(three_branch_repo, "commit", "-q", "-m", "alpha news")
    git(three_branch_repo, "push", "-q", "origin", "machine/alpha")
    git(three_branch_repo, "checkout", "-q", "main")
    second = out()
    assert second != first
    alpha_line = [ln for ln in second.splitlines() if ln.startswith("alpha ")][0]
    assert alpha_line.split()[1] == git(three_branch_repo, "rev-parse",
                                        "origin/machine/alpha").strip()[:12]
    assert alpha_line.split()[2] == "3"             # a.md b.md y.md


def test_pending_empty_output_when_consumed(three_branch_repo, tmp_path):
    """After a consolidation withdrawal (net curated onto main, machine refs set to main)
    nothing is pending -> the monitor output is an empty string."""
    home = tmp_path / "home"
    write_state(home, three_branch_repo, "gamma")
    (three_branch_repo / "a.md").write_text(
        "line1\nGAMMA-EDIT\nline3\nALPHA-EDIT\nline5\nline6\nline7\nline8\n")
    (three_branch_repo / "b.md").write_text("bbb\nalso alpha\n")
    (three_branch_repo / "c.md").write_text("new from gamma\n")
    git(three_branch_repo, "add", ".")
    git(three_branch_repo, "commit", "-q", "-m", "consolidator: everything consumed")
    git(three_branch_repo, "push", "-q", "origin", "main")
    for host in ("alpha", "beta", "gamma"):
        git(three_branch_repo, "push", "-q", "--force", "origin",
            f"main:refs/heads/machine/{host}")
    r = run_cli(three_branch_repo, home, "--pending")
    assert r.returncode == 0
    assert r.stdout == ""


def test_refresh_strip_replays_only_never_pushed(three_branch_repo, tmp_path):
    """Step 0 of pre-consolidation: only C (never pushed) is replayed onto the refreshed
    strip; the consumed content is not duplicated, and the follow-up push is a FF."""
    s = strip_scenario(three_branch_repo, tmp_path)
    repo, home = three_branch_repo, s["home"]
    r = run_cli(repo, home, "--refresh-strip")
    assert r.returncode == 0, r.stderr
    assert f"strip: replayed 1 commit(s) onto origin/machine/gamma (" in r.stderr
    assert git(repo, "rev-parse", "HEAD~1").strip() == git(repo, "rev-parse",
                                                           "origin/machine/gamma").strip()
    assert git(repo, "rev-list", "--count", "origin/machine/gamma..HEAD").strip() == "1"
    # A's and B's content is already on main — the strip carries exactly C, no second copy
    assert git(repo, "diff", "--name-only", "origin/main", "HEAD").splitlines() == ["fc.md"]
    assert (repo / "fa.md").read_text().count("A-MARKER") == 1
    assert (repo / "fb.md").read_text().count("B-MARKER") == 1
    # the pre-consolidation push afterwards is a fast-forward against the tmp remote
    git(repo, "push", "origin", "machine/gamma")
    assert git(repo, "rev-parse", "origin/machine/gamma").strip() == git(repo, "rev-parse",
                                                                        "HEAD").strip()


def test_refresh_strip_idempotent_and_conflict_safe(three_branch_repo, tmp_path):
    """After the full flow (strip -> push -> --note-pushed) a second strip run is a no-op.
    A replay that hits the curated line fails closed: exit 12, rebase aborted, clean tree."""
    s = strip_scenario(three_branch_repo, tmp_path)
    repo, home = three_branch_repo, s["home"]
    assert run_cli(repo, home, "--refresh-strip").returncode == 0
    git(repo, "push", "origin", "machine/gamma")
    assert run_cli(repo, home, "--note-pushed").returncode == 0
    r2 = run_cli(repo, home, "--refresh-strip")
    assert r2.returncode == 0
    assert "strip: nothing to replay" in r2.stderr

    # conflict case: C rewrites the very line the curator rewrote
    repo2 = build_repo(tmp_path / "case2")
    s2 = strip_scenario(repo2, tmp_path / "case2", c_edits_same_line=True)
    r = run_cli(repo2, s2["home"], "--refresh-strip")
    assert r.returncode == 12
    assert "strip: replay conflict against the refreshed strip" in r.stderr
    assert "resolve in the pre-consolidation review" in r.stderr
    # fail-closed but clean: the rebase is aborted, nothing half-rebased remains
    assert not (repo2 / ".git" / "rebase-merge").exists()
    assert not (repo2 / ".git" / "rebase-apply").exists()
    assert git(repo2, "status", "--porcelain") == ""
    assert git(repo2, "rev-parse", "HEAD").strip() == s2["c_sha"]
    assert git(repo2, "branch", "--show-current").strip() == "machine/gamma"


def test_note_pushed_updates_state(three_branch_repo, tmp_path):
    home = tmp_path / "home"
    state_path = write_state(home, three_branch_repo, "gamma")
    r = run_cli(three_branch_repo, home, "--note-pushed")
    assert r.returncode == 0, r.stderr
    head = git(three_branch_repo, "rev-parse", "HEAD").strip()
    assert f"strip: last-pushed-tip -> {head[:12]}" in r.stderr
    state = json.loads(state_path.read_text())
    assert state["last_pushed_tip"] == head
