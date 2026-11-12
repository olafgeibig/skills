"""Regression tests for the declaration audit's local/external override contract.

The audit used to treat every duplicate name as a loader-refused collision. Runtime
actually resolves a profile-local package before an external one, so one local plus
one external hit is the development working copy — visible, but not fatal. Everything
else must stay a collision: a second local copy, a second external copy, or an
ambiguous pair on either side.

These tests protect the changed observable contract only. They are not an exhaustive
combinatorial matrix, and they never mutate a runtime root.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
AUDIT = SCRIPTS / "audit-skill-declarations.py"


def load_audit():
    spec = importlib.util.spec_from_file_location("audit_skill_declarations", AUDIT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def audit():
    return load_audit()


def make_skill(root: Path, name: str, description: str = "does a thing", extra: str = "") -> Path:
    """Create a real skill directory with a minimal SKILL.md. Never a runtime root."""
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n{extra}---\n\n# {name}\n",
        encoding="utf-8",
    )
    return skill_dir


def run_audit(audit, roots, threshold=0.10, managed=(), created_by=None, include_managed=False):
    index, missing = audit.collect(roots)
    report = audit.build_report(
        index, threshold, set(managed), created_by or {}, include_managed
    )
    return report, missing


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-B", str(AUDIT), *args],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "HOME": "/tmp", "PYTHONDONTWRITEBYTECODE": "1"},
    )


# --------------------------------------------------------------------------- #
# classification
# --------------------------------------------------------------------------- #
def test_local_external_pair_is_visible_override(audit, tmp_path):
    local, external = tmp_path / "local", tmp_path / "external"
    made_local = make_skill(local, "demo-skill", "audits a demo skill library")
    made_external = make_skill(external, "demo-skill", "audits a demo skill library")

    report, _ = run_audit(audit, [("local", str(local)), ("ext:one", str(external))])

    assert report["collisions"] == {}
    pair = report["overrides"]["demo-skill"]
    assert pair["active"]["root"] == "local"
    assert Path(pair["active"]["dir"]) == made_local
    assert [Path(entry["dir"]) for entry in pair["shadowed"]] == [made_external]

    rows = report["agent_created"] + report["unattributed"]
    row = next(item for item in rows if item["name"] == "demo-skill")
    assert row["status"] == "override"
    assert row["adapted_from"] is None
    assert row["scope"] is None


def test_two_local_copies_remain_collision(audit, tmp_path):
    first, second = tmp_path / "local-a", tmp_path / "local-b"
    make_skill(first, "demo-skill", "one variant of the description")
    make_skill(second, "demo-skill", "a different variant entirely")

    report, _ = run_audit(audit, [("local", str(first)), ("local", str(second))])

    assert "demo-skill" in report["collisions"]
    assert report["overrides"] == {}


def test_two_external_copies_remain_collision(audit, tmp_path):
    first, second = tmp_path / "ext-a", tmp_path / "ext-b"
    make_skill(first, "demo-skill", "first external copy")
    make_skill(second, "demo-skill", "second external copy")

    report, _ = run_audit(
        audit, [("local", str(tmp_path / "empty")), ("ext:a", str(first)), ("ext:b", str(second))]
    )

    assert "demo-skill" in report["collisions"]
    assert report["overrides"] == {}


def test_ambiguous_external_pair_is_not_hidden_by_local_copy(audit, tmp_path):
    local, first, second = tmp_path / "local", tmp_path / "ext-a", tmp_path / "ext-b"
    make_skill(local, "demo-skill", "the working copy")
    make_skill(first, "demo-skill", "external copy one")
    make_skill(second, "demo-skill", "external copy two")

    report, _ = run_audit(
        audit, [("local", str(local)), ("ext:a", str(first)), ("ext:b", str(second))]
    )

    assert "demo-skill" in report["collisions"]
    assert report["overrides"] == {}


# --------------------------------------------------------------------------- #
# CLI behaviour
# --------------------------------------------------------------------------- #
def test_override_cli_reports_both_paths_and_exits_zero(tmp_path):
    local, external = tmp_path / "local", tmp_path / "external"
    local_skill = make_skill(local, "demo-skill", "audits a demo skill library")
    external_skill = make_skill(external, "demo-skill", "audits a demo skill library")

    as_json = run_cli("--root", f"{local}:local", "--root", f"{external}:ext", "--json")
    assert as_json.returncode == 0, as_json.stderr
    payload = json.loads(as_json.stdout)
    assert payload["collisions"] == {}
    assert "demo-skill" in payload["overrides"]
    assert Path(payload["overrides"]["demo-skill"]["active"]["dir"]) == local_skill

    as_text = run_cli("--root", f"{local}:local", "--root", f"{external}:ext")
    assert as_text.returncode == 0, as_text.stderr
    assert "LOCAL OVERRIDES: 1" in as_text.stdout
    assert str(local_skill) in as_text.stdout
    assert str(external_skill) in as_text.stdout
    assert "not proof of an authorized development session" in as_text.stdout


def test_strict_undeclared_overlap_is_still_fatal(tmp_path):
    local, external = tmp_path / "local", tmp_path / "external"
    make_skill(local, "demo-skill", "audits a demo skill library")
    make_skill(external, "demo-skill", "audits a demo skill library")
    # A separate, genuinely undeclared agent-created skill overlapping the external topic.
    make_skill(local, "library-audit-helper", "audits a demo skill library")
    (local / ".usage.json").write_text(
        json.dumps({"library-audit-helper": {"created_by": "agent"}}), encoding="utf-8"
    )
    roots = ("--root", f"{local}:local", "--root", f"{external}:ext")

    lenient = run_cli(*roots)
    assert lenient.returncode == 0, lenient.stderr  # override alone is clean

    strict = run_cli(*roots, "--strict", "--json")
    assert strict.returncode == 1
    payload = json.loads(strict.stdout)
    assert "demo-skill" in payload["overrides"]
    gap = next(row for row in payload["agent_created"] if row["name"] == "library-audit-helper")
    assert gap["status"] == "UNDECLARED"
    assert gap["candidates"]


# --------------------------------------------------------------------------- #
# root discovery
# --------------------------------------------------------------------------- #
def test_default_config_roots_stop_before_sibling_key(audit, tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / "skills").mkdir(parents=True)
    (home / "config.yaml").write_text(
        "model:\n"
        "  provider: somewhere\n"
        "skills:\n"
        "  external_dirs:\n"
        "    - /tmp/alpha\n"
        "    - /tmp/beta\n"
        "  disabled:\n"
        "    - /tmp/not-a-root\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_HOME", str(home))

    assert audit.external_dirs_from_config() == ["/tmp/alpha", "/tmp/beta"]
    roots = audit.default_roots()
    assert roots[0] == ("local", str(home / "skills"))
    assert [path for _, path in roots[1:]] == ["/tmp/alpha", "/tmp/beta"]
