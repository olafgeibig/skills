"""Tests for bulk-lock.py state-preserving unlock and restore."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
BULK_LOCK = SCRIPTS / "bulk-lock.py"


def load_bulk_lock():
    spec = importlib.util.spec_from_file_location("bulk_lock", BULK_LOCK)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mod():
    return load_bulk_lock()


def make_skill(root: Path, name: str) -> Path:
    d = root / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: test\n---\n", encoding="utf-8")
    return d


def test_parse_locked_skills(mod):
    sample = (
        "curator: ENABLED\n"
        "locked (3): alpha, beta, gamma  (the agent cannot change these; `hermes curator unlock <skill>` lifts it)\n"
    )
    assert mod.parse_locked_skills(sample) == {"alpha", "beta", "gamma"}
    assert mod.parse_locked_skills("locked (0): none\n") == set()


def test_unlock_and_restore_preserves_already_unlocked_skills(mod, tmp_path, monkeypatch):
    skills_dir = tmp_path / "skills"
    make_skill(skills_dir, "locked-a")
    make_skill(skills_dir, "locked-b")
    make_skill(skills_dir, "burnin-c")
    state_file = tmp_path / "state.json"

    calls: list[list[str]] = []

    def fake_run(cmd, text=True, capture_output=True):
        calls.append(cmd)
        if cmd[-2:] == ["curator", "status"]:
            return SimpleNamespace(
                returncode=0,
                stdout="locked (2): locked-a, locked-b  (the agent cannot change these)\n",
                stderr="",
            )
        return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    rc = mod.main(["unlock", str(skills_dir), "-p", "robert", "--state-file", str(state_file)])
    assert rc == 0
    assert state_file.is_file()
    saved = json.loads(state_file.read_text(encoding="utf-8"))
    assert saved["previously_locked"] == ["locked-a", "locked-b"]
    assert saved["already_unlocked"] == ["burnin-c"]
    assert ["hermes", "-p", "robert", "curator", "unlock", "burnin-c"] not in calls

    calls.clear()
    rc = mod.main(["restore", str(skills_dir), "-p", "robert", "--state-file", str(state_file)])
    assert rc == 0
    assert not state_file.exists()
    assert calls == [
        ["hermes", "-p", "robert", "curator", "lock", "locked-a"],
        ["hermes", "-p", "robert", "curator", "lock", "locked-b"],
    ]


def test_unlock_and_restore_require_explicit_profile(mod, tmp_path):
    skills_dir = tmp_path / "skills"
    make_skill(skills_dir, "locked-a")
    state_file = tmp_path / "state.json"

    assert mod.main(["unlock", str(skills_dir), "--state-file", str(state_file)]) == 2
    assert mod.main(["restore", str(skills_dir), "--state-file", str(state_file)]) == 2


def test_second_unlock_refuses_to_overwrite_existing_state(mod, tmp_path):
    skills_dir = tmp_path / "skills"
    make_skill(skills_dir, "locked-a")
    state_file = tmp_path / "state.json"
    state_file.write_text('{"previously_locked": ["locked-a"]}\n', encoding="utf-8")

    rc = mod.main(["unlock", str(skills_dir), "-p", "robert", "--state-file", str(state_file)])
    assert rc == 2


def test_restore_rejects_mismatched_profile_and_keeps_state(mod, tmp_path, monkeypatch):
    skills_dir = tmp_path / "skills"
    make_skill(skills_dir, "locked-a")
    state_file = tmp_path / "state.json"
    calls: list[list[str]] = []

    def fake_run(cmd, text=True, capture_output=True):
        calls.append(cmd)
        if cmd[-2:] == ["curator", "status"]:
            return SimpleNamespace(returncode=0, stdout="locked (1): locked-a\n", stderr="")
        return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    rc = mod.main(["unlock", str(skills_dir), "-p", "profile-a", "--state-file", str(state_file)])
    assert rc == 0
    calls.clear()

    rc = mod.main(["restore", str(skills_dir), "-p", "profile-b", "--state-file", str(state_file)])
    assert rc == 2
    assert calls == []
    assert state_file.is_file()


def test_restore_rejects_mismatched_directory_and_keeps_state(mod, tmp_path, monkeypatch):
    dir_a = tmp_path / "skills-a"
    dir_b = tmp_path / "skills-b"
    make_skill(dir_a, "locked-a")
    make_skill(dir_b, "locked-a")
    state_file = tmp_path / "state.json"
    calls: list[list[str]] = []

    def fake_run(cmd, text=True, capture_output=True):
        calls.append(cmd)
        if cmd[-2:] == ["curator", "status"]:
            return SimpleNamespace(returncode=0, stdout="locked (1): locked-a\n", stderr="")
        return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    rc = mod.main(["unlock", str(dir_a), "-p", "profile-a", "--state-file", str(state_file)])
    assert rc == 0
    calls.clear()

    rc = mod.main(["restore", str(dir_b), "-p", "profile-a", "--state-file", str(state_file)])
    assert rc == 2
    assert calls == []
    assert state_file.is_file()
