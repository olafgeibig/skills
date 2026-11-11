from __future__ import annotations
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"

def load_core():
    spec = importlib.util.spec_from_file_location("skill_repo_workflow", SCRIPTS / "skill_repo_workflow.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

@pytest.fixture
def core():
    return load_core()

def g(repo, *args, check=True):
    p = subprocess.run(["git", "-C", str(repo), *args], text=True,
                       capture_output=True, env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))
    if check:
        assert p.returncode == 0, p.stderr + p.stdout
    return p.stdout.strip() if check else p

def commit(repo, text, message="change", path="skills/demo/SKILL.md"):
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    g(repo, "add", "--", path)
    g(repo, "commit", "-q", "-m", message)
    return g(repo, "rev-parse", "HEAD")

@pytest.fixture
def lab(tmp_path):
    remote, producer, publisher = (tmp_path / n for n in ("origin.git", "producer", "publisher"))
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
    producer.mkdir()
    g(producer, "init", "-q", "-b", "main")
    for k,v in (("user.name","Test"),("user.email","test@example.invalid")):
        g(producer,"config",k,v)
    base = commit(producer, "---\nname: demo\ndescription: Demonstration skill.\n---\n\n# Demo\n\nBase instruction.\n")
    g(producer,"remote","add","origin",str(remote))
    g(producer,"push","-q","-u","origin","main")
    g(producer,"checkout","-q","-b","machine/testlab")
    g(producer,"push","-q","-u","origin","machine/testlab")
    subprocess.run(["git","clone","-q","-b","main",str(remote),str(publisher)],check=True)
    for k,v in (("user.name","Publisher"),("user.email","pub@example.invalid")):
        g(publisher,"config",k,v)
    store, vault = tmp_path / "state", tmp_path / "vault"
    store.mkdir(); vault.mkdir()
    config = {"schema":3,"repo_id":"owned-skills","remote":"origin",
              "publisher_repo":str(publisher),"runtime_roots":[str(producer)],
              "policy":"skill-review-v1",
              "publisher_identity":{"machine":"publisher-test","profile":"default","scope":"shared-generic"},
              "sources":[{"ref":"refs/heads/machine/testlab","machine":"testlab",
                          "profile":"default","scope":"shared-generic","enabled":True}],
              "report":{"vault":"fixture","vault_root":str(vault),
                        "directory":"projects/hermes-agent/reports"}}
    (store / "publisher.json").write_text(json.dumps(config))
    return {"remote":remote,"producer":producer,"publisher":publisher,
            "store":store,"vault":vault,"base":base,"source":config["sources"][0]}

def offer(lab, text="---\nname: demo\ndescription: Demonstration skill.\n---\n\n# Demo\n\nBase instruction.\nA useful generic rule.\n"):
    tip = commit(lab["producer"],text)
    g(lab["producer"],"push","-q","origin","machine/testlab")
    return tip


# ---------------------------------------------------------------------------
# Test-local helpers (fixtures only; each creates real commits).
# ---------------------------------------------------------------------------

def register_source(lab, entry):
    config_path = lab["store"] / "publisher.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["sources"].append(entry)
    config_path.write_text(json.dumps(config), encoding="utf-8")


# The lab fixture's unwrapped builder, so one test can stand up a second
# isolated repository set without touching the shared harness above.
build_lab = getattr(lab, "__wrapped__")


def capture(lab, core):
    return core.capture(lab["publisher"], lab["store"], lab["source"])


# ---------------------------------------------------------------------------
# B1: identity, canonical state, path safety.
# ---------------------------------------------------------------------------

def test_candidate_identity_and_path_safety(core, tmp_path):
    x = core.candidate_id("owned-skills","refs/heads/machine/testlab","a"*40,"b"*40,"p","transport")
    assert x == core.candidate_id("owned-skills","refs/heads/machine/testlab","a"*40,"b"*40,"p","transport")
    assert len(x) == 64
    assert x != core.candidate_id("owned-skills","refs/heads/machine/testlab","c"*40,"b"*40,"p","transport")
    for p in ("../escape", "/absolute"):
        with pytest.raises(core.WorkflowError): core.safe_relative(tmp_path,p)

    # Extensions: kind is part of identity, canonical bytes are key-order free.
    assert x != core.candidate_id("owned-skills","refs/heads/machine/testlab","a"*40,"b"*40,"p","refactor")
    assert core.canonical_bytes({"b":1,"a":[1,2]}) == core.canonical_bytes({"a":[1,2],"b":1})

    # Relative paths inside the root resolve; traversal and symlink escapes do not.
    assert core.safe_relative(tmp_path, "candidates/ab/state.json") == tmp_path.resolve() / "candidates/ab/state.json"
    with pytest.raises(core.WorkflowError):
        core.safe_relative(tmp_path, "nested/../../escape")
    outside = tmp_path.parent / "outside"
    outside.mkdir()
    (tmp_path / "link").symlink_to(outside, target_is_directory=True)
    with pytest.raises(core.WorkflowError):
        core.safe_relative(tmp_path, "link/state.json")

    # Atomic state writes round-trip and leave no shared or stray temp file.
    core.atomic_json(tmp_path / "state.json", {"b":1,"a":[1,2]})
    assert core.read_json(tmp_path / "state.json") == {"a":[1,2],"b":1}
    assert not list(tmp_path.glob(".*.tmp"))
    with pytest.raises(core.WorkflowError):
        core.atomic_json(tmp_path / "missing" / "state.json", {"a":1})
    with pytest.raises(core.WorkflowError):
        core.read_json(tmp_path / "absent.json")


# ---------------------------------------------------------------------------
# B2: capture pins immutable M,T and is idempotent.
# ---------------------------------------------------------------------------

def test_capture_is_idempotent_and_pins_inputs(core, lab):
    t=offer(lab)
    a=core.capture(lab["publisher"],lab["store"],lab["source"])
    b=core.capture(lab["publisher"],lab["store"],lab["source"])
    assert a["id"]==b["id"] and a["source_sha"]==t
    assert a["main_sha"]==lab["base"]
    assert g(lab["publisher"],"rev-parse",f'refs/hermes-sync/candidates/{a["id"]}/source')==t

    # Extensions: full journal, both pins, in-memory store, no publisher mutation.
    assert a["schema"] == 3 and a["kind"] == "transport" and a["status"] == "captured"
    assert a["repo_id"] == "owned-skills" and a["policy"] == "skill-review-v1"
    assert a["source_ref"] == "refs/heads/machine/testlab"
    assert a["source_machine"] == "testlab" and a["source_profile"] == "default"
    assert g(lab["publisher"],"rev-parse",f'refs/hermes-sync/candidates/{a["id"]}/main') == lab["base"]
    assert a["_store"] == lab["store"].resolve()
    persisted = json.loads((lab["store"] / "candidates" / a["id"] / "state.json").read_text(encoding="utf-8"))
    assert "_store" not in persisted and persisted["id"] == a["id"]
    # HEAD and index of the publisher clone are exactly where capture found them.
    assert g(lab["publisher"],"rev-parse","HEAD") == lab["base"]
    assert g(lab["publisher"],"rev-parse","refs/heads/main") == lab["base"]
    assert g(lab["publisher"],"status","--porcelain") == ""
    assert g(lab["publisher"],"diff-index","--cached","--quiet","HEAD") == ""


def test_recapture_after_source_advance_keeps_captured_main(core, lab):
    t1 = offer(lab)
    first = capture(lab, core)
    t2 = commit(lab["producer"], "---\nname: demo\ndescription: Demonstration skill.\n---\n\n# Demo\n\nBase instruction.\nA useful generic rule.\nA second generic rule.\n", message="second rule")
    g(lab["producer"], "push", "-q", "origin", "machine/testlab")
    second = capture(lab, core)
    assert second["id"] != first["id"]
    assert second["main_sha"] == first["main_sha"] == lab["base"]
    assert second["source_sha"] == t2
    # The earlier candidate still represents T1 only.
    old = core.load_candidate(lab["store"], first["id"])
    assert old["source_sha"] == t1 and old["status"] == "captured"


def test_capture_refuses_unknown_disabled_and_refactor_sources(core, lab):
    offer(lab)
    unknown = {"ref": "refs/heads/machine/other", "machine": "other",
               "profile": "default", "scope": "shared-generic", "enabled": True}
    with pytest.raises(core.WorkflowError):
        core.capture(lab["publisher"], lab["store"], unknown)

    config_path = lab["store"] / "publisher.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["sources"][0]["enabled"] = False
    config_path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(core.WorkflowError):
        capture(lab, core)
    config["sources"][0]["enabled"] = True
    config_path.write_text(json.dumps(config), encoding="utf-8")

    # A real refactor-side commit, registered as a source, still cannot be
    # captured as transport kind.
    producer = lab["producer"]
    g(producer, "checkout", "-q", "-b", "refactor/topic", "main")
    commit(producer, "---\nname: demo\ndescription: Demonstration skill.\n---\n\n# Demo\n\nRefactor draft.\n", message="refactor draft")
    g(producer, "push", "-q", "origin", "refactor/topic")
    g(producer, "checkout", "-q", "machine/testlab")
    register_source(lab, {"ref": "refs/heads/refactor/topic", "machine": "testlab",
                          "profile": "default", "scope": "shared-generic", "enabled": True})
    with pytest.raises(core.WorkflowError) as excinfo:
        core.capture(lab["publisher"], lab["store"], {"ref": "refs/heads/refactor/topic"})
    assert "refactor" in str(excinfo.value)


def test_capture_refuses_unapproved_report_scope_before_content(core, lab):
    offer(lab, "PRIVATE_FIXTURE_CONTEXT_MUST_NOT_RENDER\n")
    path = lab["store"] / "publisher.json"
    config = json.loads(path.read_text())
    config["sources"][0]["scope"] = "mixed-trust"
    path.write_text(json.dumps(config))
    with pytest.raises(core.WorkflowError) as excinfo:
        core.capture(lab["publisher"], lab["store"], {"ref": lab["source"]["ref"]})
    assert lab["source"]["ref"] in str(excinfo.value)
    assert "mixed-trust" in str(excinfo.value)
    assert "PRIVATE_FIXTURE_CONTEXT" not in str(excinfo.value)
    assert not list(lab["vault"].rglob("*.md"))
    assert not list((lab["store"] / "candidates").glob("*/state.json"))
    assert g(lab["publisher"], "for-each-ref", "refs/hermes-sync/candidates") == ""


def test_capture_allows_configured_shared_generic_report_scope(core, lab):
    offer(lab)
    path = lab["store"] / "publisher.json"
    config = json.loads(path.read_text())
    config["report"]["allowed_scopes"] = ["shared-generic"]
    path.write_text(json.dumps(config))
    assert capture(lab, core)["status"] == "captured"
    config["report"]["allowed_scopes"] = []
    path.write_text(json.dumps(config))
    with pytest.raises(core.WorkflowError, match="scope"):
        capture(lab, core)  # Existing journals do not bypass a changed destination policy.


@pytest.mark.parametrize("action", ["render", "publish"])
def test_report_scope_revocation_blocks_existing_candidate(core, lab, action):
    offer(lab)
    c = reviewed(core, lab)
    directory = lab["store"] / "candidates" / c["id"]
    original = (directory / "review.md").read_bytes()
    path = lab["store"] / "publisher.json"
    config = json.loads(path.read_text())
    config["report"]["allowed_scopes"] = []
    path.write_text(json.dumps(config))
    with pytest.raises(core.WorkflowError, match="scope shared-generic is not permitted"):
        if action == "render":
            core.render_review(c, json.loads((directory / "review.json").read_text()),
                               json.loads((directory / "checks.json").read_text())["checks"],
                               c["reviewed_tree"])
        else:
            core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    assert (directory / "review.md").read_bytes() == original
    assert remote_ref(lab["producer"], "refs/heads/main") == c["main_sha"]


@pytest.mark.parametrize("phase", ["capture", "publish"])
@pytest.mark.parametrize("material", ["credential", "forbidden-path"])
def test_incoming_history_exposure_blocks_even_after_final_tree_cleanup(core, lab, monkeypatch, phase, material):
    path = "skills/demo/exposure.md" if material == "credential" else "skills/demo/.env"
    value = "ghp_" + "X" * 24  # Synthetic scanner fixture, never a real credential.
    commit(lab["producer"], value + "\n", path=path)
    g(lab["producer"], "rm", "--", path)
    g(lab["producer"], "commit", "-q", "-m", "remove exposed fixture material")
    g(lab["producer"], "push", "-q", "origin", "machine/testlab")
    if phase == "publish":
        # A journal created by an older implementation (before capture screened
        # history) must still be stopped by the real publication gate.
        with monkeypatch.context() as legacy:
            legacy.setattr(core, "screen_source_history", lambda *args: {"findings": []})
            c = core.prepare(lab["publisher"], lab["store"], capture(lab, core))
            assert c["input_paths"] == []
            review = {**review_for(c), "summary": "Acknowledge a no-net-change source tip", "files": []}
            c = record_full_review(core, lab, c, review)
        action = lambda: core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    else:
        c = None
        action = lambda: capture(lab, core)
    before = remote_ref(lab["producer"], "refs/heads/main")
    with pytest.raises(core.WorkflowError) as excinfo:
        action()
    diagnostic = str(excinfo.value)
    assert "incident" in diagnostic and path in diagnostic
    assert ("credential-pattern" if material == "credential" else "forbidden-path") in diagnostic
    assert value not in diagnostic
    assert remote_ref(lab["producer"], "refs/heads/main") == before
    if phase == "capture":
        assert not list((lab["store"] / "candidates").glob("*/state.json"))
        assert g(lab["publisher"], "for-each-ref", "refs/hermes-sync/candidates") == ""
    else:
        assert c is not None
        state = core.load_candidate(lab["store"], c["id"])
        assert state["status"] == "blocked" and "incident" in state["last_error"]
        assert value not in json.dumps(state, default=str)


def test_publisher_config_is_validated_strictly(core, lab):
    offer(lab)
    config_path = lab["store"] / "publisher.json"
    good = json.loads(config_path.read_text(encoding="utf-8"))

    missing_field = json.loads(json.dumps(good))
    missing_field.pop("repo_id")
    bad_ref = json.loads(json.dumps(good))
    bad_ref["sources"][0]["ref"] = "machine/testlab"
    duplicate = json.loads(json.dumps(good))
    duplicate["sources"].append(dict(duplicate["sources"][0]))
    bad_enabled = json.loads(json.dumps(good))
    bad_enabled["sources"][0]["enabled"] = "yes"

    for broken in (missing_field, bad_ref, duplicate, bad_enabled):
        config_path.write_text(json.dumps(broken), encoding="utf-8")
        with pytest.raises(core.WorkflowError):
            core.load_publisher_config(lab["store"])

    # A syntactically valid registry that names a different checkout is refused
    # at capture time, as is a relative store path.
    wrong_repo = json.loads(json.dumps(good))
    wrong_repo["publisher_repo"] = str(lab["store"])
    config_path.write_text(json.dumps(wrong_repo), encoding="utf-8")
    with pytest.raises(core.WorkflowError):
        capture(lab, core)
    config_path.write_text(json.dumps(good), encoding="utf-8")
    with pytest.raises(core.WorkflowError):
        core.capture(lab["publisher"], Path("relative/state"), lab["source"])


def test_load_candidate_rejects_tampered_or_traversing_id(core, lab):
    offer(lab)
    candidate = capture(lab, core)
    state_path = lab["store"] / "candidates" / candidate["id"] / "state.json"
    tampered = json.loads(state_path.read_text(encoding="utf-8"))
    tampered["main_sha"] = "d" * 40
    state_path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(core.WorkflowError):
        core.load_candidate(lab["store"], candidate["id"])
    with pytest.raises(core.WorkflowError):
        core.load_candidate(lab["store"], "../../publisher")


# ---------------------------------------------------------------------------
# B2a: transport provenance guard.
# ---------------------------------------------------------------------------

def test_transport_rejects_unpublished_side_parent(core, lab):
    t = offer(lab)
    producer = lab["producer"]
    g(producer, "checkout", "-q", "-b", "topic", t)
    side = commit(producer, "---\nname: demo\ndescription: Demonstration skill.\n---\n\n# Demo\n\nSide rule.\n", message="side work")
    g(producer, "checkout", "-q", "machine/testlab")
    commit(producer, "trunk note\n", message="trunk work", path="skills/demo/TRUNK.md")
    g(producer, "merge", "-q", "--no-ff", "-m", "merge unpublished topic", "topic")
    merge = g(producer, "rev-parse", "HEAD")
    merge_parents = g(producer, "rev-list", "--parents", "-n", "1", merge).split()[1:]
    assert merge_parents[0] != side and side in merge_parents
    assert len(merge_parents) == 2
    g(producer, "push", "-q", "origin", "machine/testlab")

    with pytest.raises(core.WorkflowError) as excinfo:
        capture(lab, core)
    message = str(excinfo.value)
    assert merge in message and side in message
    # Rejected before any candidate journal or pin was created.
    assert not list((lab["store"] / "candidates").glob("*/state.json"))
    assert g(lab["publisher"], "for-each-ref", "refs/hermes-sync/candidates") == ""


def test_transport_rejects_known_refactor_fast_forward(core, lab):
    producer = lab["producer"]
    g(producer, "checkout", "-q", "-b", "refactor/topic", "main")
    refactor_tip = commit(producer, "---\nname: demo\ndescription: Demonstration skill.\n---\n\n# Demo\n\nRefactor draft.\n", message="refactor draft")
    g(producer, "push", "-q", "origin", "refactor/topic")
    g(producer, "checkout", "-q", "machine/testlab")
    g(producer, "merge", "-q", "--ff-only", "refactor/topic")
    assert g(producer, "rev-parse", "HEAD") == refactor_tip
    assert g(producer, "rev-parse", "refs/remotes/origin/refactor/topic") == refactor_tip
    g(producer, "push", "-q", "origin", "machine/testlab")

    with pytest.raises(core.WorkflowError) as excinfo:
        capture(lab, core)
    message = str(excinfo.value)
    assert refactor_tip in message and "refactor/topic" in message
    assert not list((lab["store"] / "candidates").glob("*/state.json"))


def test_transport_accepts_published_main_merge(core, lab):
    producer = lab["producer"]
    g(producer, "checkout", "-q", "machine/testlab")
    commit(producer, "---\nname: demo\ndescription: Demonstration skill.\n---\n\n# Demo\n\nBase instruction.\nSource rule.\n", message="source work")
    g(producer, "checkout", "-q", "main")
    main_tip = commit(producer, "main side\n", message="main work", path="skills/demo/MAIN.md")
    g(producer, "push", "-q", "origin", "main")
    g(producer, "checkout", "-q", "machine/testlab")
    source_commit = g(producer, "rev-parse", "HEAD")
    g(producer, "fetch", "-q", "origin")
    g(producer, "merge", "-q", "--no-ff", "-m", "merge published main", "origin/main")
    merge = g(producer, "rev-parse", "HEAD")
    merge_parents = g(producer, "rev-list", "--parents", "-n", "1", merge).split()[1:]
    assert merge_parents == [source_commit, main_tip]
    g(producer, "push", "-q", "origin", "machine/testlab")

    candidate = capture(lab, core)
    assert candidate["main_sha"] == main_tip
    assert candidate["source_sha"] == merge
    assert core.source_status(lab["publisher"], candidate["main_sha"], candidate["source_sha"]) == "pending"


# ---------------------------------------------------------------------------
# B3: consumption is ancestry only, including same-tree tips.
# ---------------------------------------------------------------------------

def test_source_status_acknowledges_empty_diff(core, lab):
    t = offer(lab)
    a = capture(lab, core)
    assert core.source_status(lab["publisher"], a["main_sha"], t) == "pending"
    assert core.source_status(lab["publisher"], a["main_sha"], a["main_sha"]) == "consumed"

    producer = lab["producer"]
    tree_of_t = g(producer, "rev-parse", f"{t}^{{tree}}")
    g(producer, "commit", "-q", "--allow-empty", "-m", "empty tip")
    empty = g(producer, "rev-parse", "HEAD")
    assert empty != t
    assert g(producer, "rev-parse", f"{empty}^{{tree}}") == tree_of_t
    g(producer, "push", "-q", "origin", "machine/testlab")

    b = capture(lab, core)
    assert b["id"] != a["id"] and b["source_sha"] == empty
    # Same tree as M's line, but not an ancestor: still pending, not consumed.
    assert core.source_status(lab["publisher"], b["main_sha"], empty) == "pending"
    assert not core.is_ancestor(lab["publisher"], empty, b["main_sha"])


# ---------------------------------------------------------------------------
# B4-B6: native merge preparation (packet 04).
# ---------------------------------------------------------------------------

EMPTY_BLOB = "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"


def git_out(repo, *args):
    """Raw stdout bytes from a checked Git call (NUL-delimited formats)."""
    p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=False,
                       env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))
    assert p.returncode == 0, (p.stderr + p.stdout).decode("utf-8", "replace")
    return p.stdout


def index_stage(repo):
    entries = {}
    for record in git_out(repo, "ls-files", "--stage", "-z").split(b"\0"):
        if not record:
            continue
        meta, path = record.split(b"\t", 1)
        mode, sha, stage = meta.decode("ascii").split()
        entries[path.decode("utf-8")] = (mode, sha, int(stage))
    return entries


def unmerged_rows(repo):
    rows = []
    for record in git_out(repo, "ls-files", "-u", "-z").split(b"\0"):
        if not record:
            continue
        meta, path = record.split(b"\t", 1)
        mode, sha, stage = meta.decode("ascii").split()
        rows.append((path.decode("utf-8"), int(stage), mode, sha))
    return rows


def staged_status(repo, base, *options):
    tokens = git_out(repo, "diff", "--cached", "--name-status", "-z", *options, base).decode("utf-8").split("\0")
    rows, i = [], 0
    while i < len(tokens) and tokens[i]:
        status = tokens[i]; i += 1
        if status[:1] in ("R", "C"):
            rows.append((status, tokens[i], tokens[i + 1])); i += 2
        else:
            rows.append((status, tokens[i])); i += 1
    return sorted(rows, key=lambda row: row[1:])


def publish_files(lab, files, message="extend base"):
    """Commit real base files on producer main, then fast-forward transport."""
    producer = lab["producer"]
    g(producer, "checkout", "-q", "main")
    for path, (data, mode) in files.items():
        target = producer / path
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, bytes):
            target.write_bytes(data)
        else:
            target.write_text(data, encoding="utf-8")
        if mode is not None:
            os.chmod(target, mode)
        g(producer, "add", "--", path)
    g(producer, "commit", "-q", "-m", message)
    g(producer, "push", "-q", "origin", "main")
    g(producer, "checkout", "-q", "machine/testlab")
    g(producer, "merge", "-q", "--ff-only", "main")
    g(producer, "push", "-q", "origin", "machine/testlab")
    return g(producer, "rev-parse", "HEAD")


def source_commit(lab, mutate, message="source change", stage=True):
    producer = lab["producer"]
    mutate(producer)
    if stage:
        g(producer, "add", "-A")
    g(producer, "commit", "-q", "-m", message)
    g(producer, "push", "-q", "origin", "machine/testlab")
    return g(producer, "rev-parse", "HEAD")


def replace_text(path, old, new):
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def test_prepare_materializes_clean_addition(core, lab):
    t=offer(lab)
    c=core.capture(lab["publisher"],lab["store"],lab["source"])
    p=core.prepare(lab["publisher"],lab["store"],c)
    w=Path(p["worktree"])
    assert "A useful generic rule." in (w/"skills/demo/SKILL.md").read_text()
    assert g(w,"rev-parse","HEAD")==lab["base"]
    assert g(w,"rev-parse","MERGE_HEAD")==t
    assert g(lab["producer"],"branch","--show-current")=="machine/testlab"

    # Extensions: isolated worktree, complete index, no hooks/rerere, journal.
    assert p["status"] == "prepared" and p["conflict_paths"] == []
    assert p["input_paths"] == ["skills/demo/SKILL.md"]
    assert w == (lab["store"] / "worktrees" / c["id"]).resolve()
    assert w.is_relative_to(lab["store"].resolve())
    assert not w.is_relative_to(lab["producer"].resolve())
    assert not w.is_relative_to(lab["vault"].resolve())
    assert g(w, "diff", "--cached", "--name-only") == "skills/demo/SKILL.md"
    hooks = g(w, "config", "core.hooksPath")
    assert hooks == str(lab["store"] / "hooks-disabled" / c["id"])
    assert not Path(hooks).exists()
    assert g(w, "config", "rerere.enabled") == "false"
    assert g(lab["publisher"], "rev-parse", "refs/heads/main") == lab["base"]
    assert g(lab["publisher"], "rev-parse", "HEAD") == lab["base"]
    assert g(lab["publisher"], "status", "--porcelain") == ""
    journal = json.loads((lab["store"] / "candidates" / c["id"] / "state.json").read_text(encoding="utf-8"))
    assert journal["status"] == "prepared" and journal["worktree"] == str(w)
    assert journal["input_paths"] == ["skills/demo/SKILL.md"] and journal["conflict_paths"] == []
    assert p["_store"] == lab["store"].resolve()

    # Preparing the same captured candidate again is idempotent, not destructive.
    again = core.prepare(lab["publisher"], lab["store"], p)
    assert again["worktree"] == str(w) and again["status"] == "prepared"
    assert g(w, "rev-parse", "MERGE_HEAD") == t


def test_prepare_does_not_execute_repository_hooks(core, lab):
    offer(lab)
    sentinel = lab["publisher"] / "hook-executed"
    hook = lab["publisher"] / ".git" / "hooks" / "post-checkout"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(f"#!/bin/sh\ntouch {sentinel}\n", encoding="utf-8")
    os.chmod(hook, 0o755)

    c = capture(lab, core)
    p = core.prepare(lab["publisher"], lab["store"], c)
    assert p["status"] == "prepared"
    assert g(Path(p["worktree"]), "config", "core.hooksPath") == str(lab["store"] / "hooks-disabled" / c["id"])
    assert not sentinel.exists()


def test_prepare_preserves_deleted_and_empty_files(core, lab):
    base = publish_files(lab, {
        "skills/demo/old.md": ("Obsolete guidance.\n", None),
        "skills/demo/empty.md": ("Will be emptied.\n", None),
    })
    tip = source_commit(lab, lambda root: (
        (root / "skills/demo/old.md").unlink(),
        (root / "skills/demo/empty.md").write_text("", encoding="utf-8"),
        (root / "skills/demo/added-empty.md").write_text("", encoding="utf-8"),
    ), "delete, empty and add an empty file")
    c = capture(lab, core)
    p = core.prepare(lab["publisher"], lab["store"], c)
    w = Path(p["worktree"])
    stages = index_stage(w)
    assert "skills/demo/old.md" not in stages
    for path in ("skills/demo/empty.md", "skills/demo/added-empty.md"):
        assert stages[path] == ("100644", EMPTY_BLOB, 0)
    assert not (w / "skills/demo/old.md").exists()
    assert (w / "skills/demo/empty.md").read_bytes() == b""
    assert (w / "skills/demo/added-empty.md").read_bytes() == b""
    assert staged_status(w, base) == [
        ("A", "skills/demo/added-empty.md"),
        ("M", "skills/demo/empty.md"),
        ("D", "skills/demo/old.md"),
    ]
    assert p["status"] == "prepared" and p["conflict_paths"] == []
    assert set(p["input_paths"]) == {
        "skills/demo/old.md", "skills/demo/empty.md", "skills/demo/added-empty.md",
    }
    assert c["source_sha"] == tip
    assert c["main_sha"] != lab["base"]
    assert g(lab["publisher"], "rev-parse", "refs/heads/main") == lab["base"]


def test_prepare_preserves_executable_mode(core, lab):
    base = publish_files(lab, {"skills/demo/tool.sh": ("#!/bin/sh\necho base\n", 0o755)})

    def mutate(root):
        os.chmod(root / "skills/demo/tool.sh", 0o644)
        runner = root / "skills/demo/runner.sh"
        runner.write_text("#!/bin/sh\necho runner\n", encoding="utf-8")
        os.chmod(runner, 0o755)

    source_commit(lab, mutate, "toggle and add executable text")
    c = capture(lab, core)
    p = core.prepare(lab["publisher"], lab["store"], c)
    w = Path(p["worktree"])
    stages = index_stage(w)
    assert stages["skills/demo/tool.sh"][0] == "100644"
    assert stages["skills/demo/runner.sh"][0] == "100755"
    assert staged_status(w, base) == [
        ("A", "skills/demo/runner.sh"),
        ("M", "skills/demo/tool.sh"),
    ]
    assert not os.access(w / "skills/demo/tool.sh", os.X_OK)
    assert os.access(w / "skills/demo/runner.sh", os.X_OK)
    assert p["status"] == "prepared" and p["conflict_paths"] == []


@pytest.mark.parametrize("kind,label", [("binary", "binary"), ("symlink", "symlink"), ("gitlink", "submodule")])
def test_prepare_blocks_binary_and_symlink(core, lab, kind, label):
    def mutate(root):
        if kind == "binary":
            (root / "skills/demo/blob.bin").write_bytes(b"header\x00binary payload\n")
        elif kind == "symlink":
            os.symlink("SKILL.md", root / "skills/demo/link.md")
        else:
            g(root, "update-index", "--add", "--cacheinfo",
              f"160000,{lab['base']},skills/demo/module")

    tip = source_commit(lab, mutate, f"unsupported {kind}", stage=kind != "gitlink")

    # The fixture really contains the unsupported Git object mode/bytes.
    listing = g(lab["producer"], "ls-tree", "-r", tip)
    if kind == "binary":
        assert "100644 blob" in listing and "skills/demo/blob.bin" in listing
        assert b"\x00" in git_out(lab["producer"], "cat-file", "blob", f"{tip}:skills/demo/blob.bin")
    elif kind == "symlink":
        assert "120000 blob" in listing and "skills/demo/link.md" in listing
    else:
        assert "160000 commit" in listing and "skills/demo/module" in listing

    c = capture(lab, core)
    publisher_main = g(lab["publisher"], "rev-parse", "refs/heads/main")
    producer_main = g(lab["producer"], "rev-parse", "refs/heads/main")
    with pytest.raises(core.WorkflowError) as excinfo:
        core.prepare(lab["publisher"], lab["store"], c)
    message = str(excinfo.value)
    assert "skills/demo/" in message and label in message and "unsupported" in message
    assert g(lab["publisher"], "rev-parse", "refs/heads/main") == publisher_main
    assert g(lab["producer"], "rev-parse", "refs/heads/main") == producer_main
    assert not (lab["store"] / "worktrees" / c["id"]).exists()
    blocked = core.load_candidate(lab["store"], c["id"])
    assert blocked["status"] == "blocked" and blocked["last_error"]


def test_prepare_handles_rename(core, lab):
    base = publish_files(lab, {"skills/demo/old-name.md": ("Renamable guidance.\n", None)})
    source_commit(lab, lambda root: g(root, "mv", "skills/demo/old-name.md", "skills/demo/new-name.md"),
                  "rename a text file")
    c = capture(lab, core)
    p = core.prepare(lab["publisher"], lab["store"], c)
    w = Path(p["worktree"])
    assert staged_status(w, base, "-M") == [
        ("R100", "skills/demo/old-name.md", "skills/demo/new-name.md"),
    ]
    stages = index_stage(w)
    assert "skills/demo/old-name.md" not in stages
    assert "skills/demo/new-name.md" in stages
    assert (w / "skills/demo/new-name.md").read_text(encoding="utf-8") == "Renamable guidance.\n"
    assert not (w / "skills/demo/old-name.md").exists()
    assert set(p["input_paths"]) == {"skills/demo/old-name.md", "skills/demo/new-name.md"}
    assert p["status"] == "prepared" and p["conflict_paths"] == []


def test_prepare_exposes_conflicts_without_ours_default(core, lab):
    producer = lab["producer"]
    g(producer, "checkout", "-q", "main")
    replace_text(producer / "skills/demo/SKILL.md", "Base instruction.", "Main branch instruction.")
    g(producer, "add", "--", "skills/demo/SKILL.md")
    g(producer, "commit", "-q", "-m", "main-side same-line edit")
    g(producer, "push", "-q", "origin", "main")
    g(producer, "checkout", "-q", "machine/testlab")
    replace_text(producer / "skills/demo/SKILL.md", "Base instruction.", "Transport branch instruction.")
    g(producer, "add", "--", "skills/demo/SKILL.md")
    g(producer, "commit", "-q", "-m", "transport-side same-line edit")
    g(producer, "push", "-q", "origin", "machine/testlab")
    main_sha = g(producer, "rev-parse", "refs/heads/main")
    tip = g(producer, "rev-parse", "HEAD")
    assert main_sha != tip

    c = capture(lab, core)
    assert c["main_sha"] == main_sha and c["source_sha"] == tip
    p = core.prepare(lab["publisher"], lab["store"], c)
    w = Path(p["worktree"])
    assert p["status"] == "prepared"
    assert p["conflict_paths"] == ["skills/demo/SKILL.md"]
    assert g(w, "rev-parse", "HEAD") == main_sha
    assert g(w, "rev-parse", "MERGE_HEAD") == tip
    rows = unmerged_rows(w)
    assert {stage for path, stage, _mode, _sha in rows if path == "skills/demo/SKILL.md"} == {1, 2, 3}
    text = (w / "skills/demo/SKILL.md").read_text(encoding="utf-8")
    assert "<<<<<<< HEAD" in text and "=======" in text and ">>>>>>>" in text
    assert "Main branch instruction." in text and "Transport branch instruction." in text
    main_blob = git_out(lab["publisher"], "show", f"{main_sha}:skills/demo/SKILL.md").decode("utf-8")
    assert text != main_blob  # a silent keep-ours default would equal the main blob
    journal = json.loads((lab["store"] / "candidates" / c["id"] / "state.json").read_text(encoding="utf-8"))
    assert journal["status"] == "prepared"
    assert journal["conflict_paths"] == ["skills/demo/SKILL.md"]
    assert g(lab["publisher"], "rev-parse", "refs/heads/main") == lab["base"]


def test_prepare_blocks_custom_merge_driver_without_running_it(core, lab):
    publish_files(lab, {".gitattributes": ("skills/demo/*.md merge=sentinel\n", None)})
    producer = lab["producer"]
    g(producer, "checkout", "-q", "main")
    replace_text(producer / "skills/demo/SKILL.md", "# Demo\n", "# Demo\n\nMain branch context.\n")
    g(producer, "add", "--", "skills/demo/SKILL.md")
    g(producer, "commit", "-q", "-m", "main edit before fork")
    g(producer, "push", "-q", "origin", "main")
    g(producer, "checkout", "-q", "machine/testlab")
    source_commit(lab, lambda root: replace_text(
        root / "skills/demo/SKILL.md", "Base instruction.",
        "Base instruction.\nA useful generic rule."), "source edit under custom driver")
    sentinel = lab["publisher"] / "sentinel-executed"
    g(lab["publisher"], "config", "merge.sentinel.driver", f"touch {sentinel}")
    assert g(lab["publisher"], "config", "merge.sentinel.driver")

    c = capture(lab, core)
    assert g(lab["publisher"], "show", f"{c['main_sha']}:.gitattributes").strip() == "skills/demo/*.md merge=sentinel"
    publisher_main = g(lab["publisher"], "rev-parse", "refs/heads/main")
    with pytest.raises(core.WorkflowError) as excinfo:
        core.prepare(lab["publisher"], lab["store"], c)
    message = str(excinfo.value)
    assert "sentinel" in message and "unsupported" in message
    assert not sentinel.exists()
    assert not (lab["store"] / "worktrees" / c["id"]).exists()
    assert g(lab["publisher"], "rev-parse", "refs/heads/main") == publisher_main


@pytest.mark.parametrize("route", ["local-default", "global-default", "info-attributes", "attributes-file"])
def test_prepare_refuses_external_merge_configuration_without_execution(core, lab, monkeypatch, route):
    producer = lab["producer"]
    g(producer, "checkout", "-q", "main")
    commit(producer, "Main side conflicts.\n")
    g(producer, "push", "-q", "origin", "main")
    g(producer, "checkout", "-q", "machine/testlab")
    offer(lab, "Source side conflicts.\n")
    sentinel = lab["store"] / "external-merge-executed"
    g(lab["publisher"], "config", "merge.sentinel.driver", f"touch '{sentinel}'")
    if route == "global-default":
        global_config = lab["store"] / "gitconfig"
        global_config.write_text("[merge]\n\tdefault = sentinel\n")
        monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))
    elif route == "local-default":
        g(lab["publisher"], "config", "merge.default", "sentinel")
    else:
        attributes = (lab["publisher"] / ".git/info/attributes" if route == "info-attributes"
                      else lab["store"] / "global-attributes")
        attributes.parent.mkdir(parents=True, exist_ok=True)
        attributes.write_text("skills/demo/*.md merge=sentinel\n")
        if route == "attributes-file":
            g(lab["publisher"], "config", "core.attributesFile", str(attributes))
    c = capture(lab, core)
    before = {key: (g(lab[key], "show-ref"), g(lab[key], "write-tree"),
                    g(lab[key], "status", "--porcelain")) for key in ("publisher", "producer")}
    with pytest.raises(core.WorkflowError, match="unsupported.*merge|merge.*unsupported"):
        core.prepare(lab["publisher"], lab["store"], c)
    assert not sentinel.exists()
    assert not Path(c["_store"] / "worktrees" / c["id"]).exists()
    assert core.load_candidate(lab["store"], c["id"])["status"] == "blocked"
    assert {key: (g(lab[key], "show-ref"), g(lab[key], "write-tree"),
                  g(lab[key], "status", "--porcelain")) for key in before} == before
    assert remote_ref(producer, "refs/heads/main") == c["main_sha"]
    assert remote_ref(producer, lab["source"]["ref"]) == c["source_sha"]


@pytest.mark.parametrize("scope", ["local", "global", "include"])
@pytest.mark.parametrize("driver", ["text", "unreferenced"])
def test_prepare_refuses_any_defined_merge_driver(core, lab, monkeypatch, scope, driver):
    """A merge.text.driver definition overrides Git's builtin text implementation."""
    other = second_main_clone(lab, lab["store"])
    commit(other, BASE_TEXT.replace("Base instruction.", "Main instruction."))
    g(other, "push", "-q", "origin", "main")
    offer(lab, BASE_TEXT.replace("Base instruction.", "Source instruction."))
    sentinel = lab["store"] / "builtin-merge-driver-ran"
    definition = f"touch {sentinel}; exit 1"
    if scope == "local":
        g(lab["publisher"], "config", f"merge.{driver}.driver", definition)
    else:
        external = lab["store"] / "driver.gitconfig"
        g(lab["publisher"], "config", "--file", str(external), f"merge.{driver}.driver", definition)
        if scope == "global":
            monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(external))
        else:
            g(lab["publisher"], "config", "include.path", str(external))
    # The text case is the exact review probe; the other definition is unused.
    g(lab["publisher"], "config", "merge.default", "text")
    c = capture(lab, core)
    before = {key: (g(lab[key], "show-ref"), g(lab[key], "write-tree"),
                    (lab[key] / ".git/index").read_bytes(),
                    (lab[key] / "skills/demo/SKILL.md").read_bytes())
              for key in ("publisher", "producer")}
    refusal = None
    try:
        core.prepare(lab["publisher"], lab["store"], c)
    except core.WorkflowError as exc:
        refusal = str(exc)
    assert refusal and not sentinel.exists(), (
        f"configured merge.{driver}.driver was not refused: "
        f"refusal={refusal!r}, sentinel={sentinel.exists()}")
    assert "unsupported" in refusal and "merge" in refusal
    assert core.load_candidate(lab["store"], c["id"])["status"] == "blocked"
    assert not (lab["store"] / "worktrees" / c["id"]).exists()
    assert {key: (g(lab[key], "show-ref"), g(lab[key], "write-tree"),
                  (lab[key] / ".git/index").read_bytes(),
                  (lab[key] / "skills/demo/SKILL.md").read_bytes()) for key in before} == before
    assert remote_ref(lab["producer"], "refs/heads/main") == c["main_sha"]
    assert remote_ref(lab["producer"], lab["source"]["ref"]) == c["source_sha"]


@pytest.mark.parametrize("driver", ["text", "binary", "union", "normal"])
def test_prepare_accepts_builtin_default_merge_driver(core, lab, driver):
    offer(lab)
    g(lab["publisher"], "config", "merge.default", driver)
    c = core.prepare(lab["publisher"], lab["store"], capture(lab, core))
    assert c["status"] == "prepared"


@pytest.mark.parametrize("root", ["runtime", "report"])
def test_prepare_refuses_candidate_dir_inside_runtime_or_report_root(core, lab, root):
    offer(lab)
    c = capture(lab, core)
    config_path = lab["store"] / "publisher.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if root == "runtime":
        config["runtime_roots"] = [str(lab["store"])]
    else:
        config["report"]["vault_root"] = str(lab["store"])
    config_path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(core.WorkflowError) as excinfo:
        core.prepare(lab["publisher"], lab["store"], c)
    assert f"{root} root" in str(excinfo.value)
    assert not (lab["store"] / "worktrees" / c["id"]).exists()


def test_prepare_refuses_inconsistent_existing_dir_without_deleting(core, lab):
    offer(lab)
    c = capture(lab, core)
    candidate_dir = lab["store"] / "worktrees" / c["id"]
    candidate_dir.mkdir(parents=True)
    marker = candidate_dir / "foreign-work.txt"
    marker.write_text("keep me\n", encoding="utf-8")

    with pytest.raises(core.WorkflowError) as excinfo:
        core.prepare(lab["publisher"], lab["store"], c)
    assert "inconsistent state" in str(excinfo.value)
    assert marker.read_text(encoding="utf-8") == "keep me\n"
    assert not (candidate_dir / "skills").exists()
    assert core.load_candidate(lab["store"], c["id"])["status"] == "captured"
    assert g(lab["publisher"], "rev-parse", "refs/heads/main") == lab["base"]


# ---------------------------------------------------------------------------
# C1: review scope, real source anchors and old->new replacement proof.
# ---------------------------------------------------------------------------

def clone(value):
    return json.loads(json.dumps(value))


def review_for(c, path="skills/demo/SKILL.md", *, change_type="addition", decision="accept",
               quote="A useful generic rule.", reason="Useful generic addition",
               anchors=None, replacements=None, summary="Accept a useful generic addition"):
    if anchors is None:
        anchors = [{"ref": c["source_sha"], "path": path, "quote": quote}]
    return {"schema": 1, "candidate_id": c["id"], "main_sha": c["main_sha"],
            "source_sha": c["source_sha"], "summary": summary,
            "files": [{"path": path, "change_type": change_type, "decision": decision,
                       "source_anchors": anchors, "reason": reason,
                       "replacements": replacements or []}]}


def test_review_rejects_missing_paths_or_invented_quotes(core, lab):
    tip = offer(lab)
    c = capture(lab, core)
    c = core.prepare(lab["publisher"], lab["store"], c)
    w = Path(c["worktree"])
    good = review_for(c)
    assert core.validate_review(c, good, lab["publisher"], w) is None

    # An empty file list cannot cover a candidate that changes a path.
    with pytest.raises(core.WorkflowError) as excinfo:
        core.validate_review(c, {**good, "files": []}, lab["publisher"], w)
    message = str(excinfo.value)
    assert "cover" in message and "skills/demo/SKILL.md" in message

    # A fabricated quote is refused even when ref and path exist.
    invented = clone(good)
    invented["files"][0]["source_anchors"][0]["quote"] = "A rule nobody wrote."
    with pytest.raises(core.WorkflowError) as excinfo:
        core.validate_review(c, invented, lab["publisher"], w)
    assert "quote" in str(excinfo.value) and "skills/demo/SKILL.md" in str(excinfo.value)

    # Source refs are limited to captured M, T and merge bases.
    foreign = clone(good)
    foreign["files"][0]["source_anchors"][0]["ref"] = "f" * 40
    with pytest.raises(core.WorkflowError) as excinfo:
        core.validate_review(c, foreign, lab["publisher"], w)
    assert "merge base" in str(excinfo.value)

    # Review text is data: no command/execution fields anywhere in the schema.
    for mutate in (
        lambda r: r.update({"command": "git push --force"}),
        lambda r: r["files"][0].update({"exec": "rm -rf ."}),
        lambda r: r["files"][0]["source_anchors"][0].update({"shell": "true"}),
        lambda r: r.update({"approved": True}),
    ):
        armed = clone(good)
        mutate(armed)
        with pytest.raises(core.WorkflowError) as excinfo:
            core.validate_review(c, armed, lab["publisher"], w)
        assert "unsupported" in str(excinfo.value)

    with pytest.raises(core.WorkflowError):
        core.validate_review(c, {**good, "summary": "   "}, lab["publisher"], w)

    # An additionally edited path is allowed only when its reason names it.
    extra = w / "skills/demo/extra.md"
    extra.write_text("Collapsed duplicate guidance.\n", encoding="utf-8")
    g(w, "add", "--", "skills/demo/extra.md")
    two_paths = review_for(c)
    two_paths["files"].append({
        "path": "skills/demo/extra.md", "change_type": "integration", "decision": "combine",
        "source_anchors": [{"ref": tip, "path": "skills/demo/SKILL.md", "quote": "A useful generic rule."}],
        "reason": "Collapsed a duplicate", "replacements": [],
    })
    with pytest.raises(core.WorkflowError) as excinfo:
        core.validate_review(c, two_paths, lab["publisher"], w)
    assert "skills/demo/extra.md" in str(excinfo.value) and "reason" in str(excinfo.value)
    two_paths["files"][1]["reason"] = "Collapsed duplicate guidance into skills/demo/extra.md"
    assert core.validate_review(c, two_paths, lab["publisher"], w) is None


def test_review_acknowledges_empty_diff_with_summary(core, lab):
    g(lab["producer"], "commit", "-q", "--allow-empty", "-m", "empty tip")
    g(lab["producer"], "push", "-q", "origin", "machine/testlab")
    c = capture(lab, core)
    assert c["main_sha"] == lab["base"] and c["source_sha"] != lab["base"]
    c = core.prepare(lab["publisher"], lab["store"], c)
    assert c["input_paths"] == [] and c["conflict_paths"] == []
    ack = {"schema": 1, "candidate_id": c["id"], "main_sha": c["main_sha"],
           "source_sha": c["source_sha"],
           "summary": "Consume an empty tip that changes no canonical content", "files": []}
    assert core.validate_review(c, ack, lab["publisher"], Path(c["worktree"])) is None
    with pytest.raises(core.WorkflowError) as excinfo:
        core.validate_review(c, {**ack, "summary": "  "}, lab["publisher"], Path(c["worktree"]))
    assert "summary" in str(excinfo.value)


def test_review_replacement_requires_old_and_new_anchors(core, lab):
    instance = "Use the path /home/olaf/vaults/private on this machine."
    portable = "Use a portable path relative to the skill root."
    tip = offer(lab, "---\nname: demo\ndescription: Demonstration skill.\n---\n\n# Demo\n\n"
                     f"Base instruction.\n{instance}\n")
    c = capture(lab, core)
    c = core.prepare(lab["publisher"], lab["store"], c)
    w = Path(c["worktree"])
    staged = (w / "skills/demo/SKILL.md").read_text(encoding="utf-8")
    assert instance in staged and tip == c["source_sha"]

    # The agent generalizes the incoming instruction in the candidate index.
    replace_text(w / "skills/demo/SKILL.md", instance, portable)
    g(w, "add", "--", "skills/demo/SKILL.md")

    replacement = {"old_ref": c["source_sha"], "old_path": "skills/demo/SKILL.md",
                   "old_quote": instance, "new_path": "skills/demo/SKILL.md",
                   "new_quote": portable, "reason": "Instance path is not portable"}
    anchors = [{"ref": c["main_sha"], "path": "skills/demo/SKILL.md", "quote": "Base instruction."},
               {"ref": c["source_sha"], "path": "skills/demo/SKILL.md", "quote": instance}]
    review = review_for(c, change_type="correction", decision="combine",
                        reason="Replace an instance-specific path with portable text",
                        anchors=anchors, replacements=[replacement])
    assert core.validate_review(c, review, lab["publisher"], w) is None

    def broken(mutate):
        value = clone(review)
        mutate(value["files"][0])
        return value

    cases = {
        "old quote": broken(lambda f: f["replacements"][0].update({"old_quote": "A rule nobody wrote."})),
        "new quote": broken(lambda f: f["replacements"][0].update({"new_quote": "Text that was never staged."})),
        "outside the reviewed candidate": broken(
            lambda f: f["replacements"][0].update({"new_path": "skills/demo/missing.md"})),
        "old_path": broken(lambda f: f["replacements"][0].update({"old_path": "skills/demo/missing.md"})),
        "merge base": broken(lambda f: f["replacements"][0].update({"old_ref": "f" * 40})),
        "reason": broken(lambda f: f["replacements"][0].update({"reason": ""})),
    }
    for expected, value in cases.items():
        with pytest.raises(core.WorkflowError) as excinfo:
            core.validate_review(c, value, lab["publisher"], w)
        assert expected in str(excinfo.value), (expected, str(excinfo.value))

    # Re-introducing the old instruction next to the new one keeps it live.
    with (w / "skills/demo/SKILL.md").open("a", encoding="utf-8") as handle:
        handle.write(instance + "\n")
    g(w, "add", "--", "skills/demo/SKILL.md")
    with pytest.raises(core.WorkflowError) as excinfo:
        core.validate_review(c, review, lab["publisher"], w)
    assert "still occurs" in str(excinfo.value)


# ---------------------------------------------------------------------------
# C2: the final gate checks the actual staged tree, not the incoming diff.
# ---------------------------------------------------------------------------

def test_final_gate_ignores_fixed_incoming_pointer(core, lab):
    instance = "Deploy only from /home/olaf/vaults/private on durin."
    example_line = "Example: /home/example/skills/demo/SKILL.md"
    tip = offer(lab, "---\nname: demo\ndescription: Demonstration skill.\n---\n\n# Demo\n\n"
                     f"Base instruction.\n{instance}\n")
    tip = source_commit(
        lab,
        lambda root: (root / "skills/demo/example.md").write_text(
            f"# Example\n\n{example_line}\n", encoding="utf-8"),
        "add an illustrative example",
    )
    c = capture(lab, core)
    c = core.prepare(lab["publisher"], lab["store"], c)
    w = Path(c["worktree"])
    assert c["source_sha"] == tip
    assert instance in (w / "skills/demo/SKILL.md").read_text(encoding="utf-8")

    unchanged = {
        "schema": 1, "candidate_id": c["id"], "main_sha": c["main_sha"],
        "source_sha": c["source_sha"], "summary": "Accept the incoming skill text",
        "files": [
            {"path": "skills/demo/SKILL.md", "change_type": "addition", "decision": "accept",
             "source_anchors": [{"ref": c["source_sha"], "path": "skills/demo/SKILL.md",
                                 "quote": instance}],
             "reason": "Useful generic addition", "replacements": []},
            {"path": "skills/demo/example.md", "change_type": "addition", "decision": "accept",
             "source_anchors": [{"ref": c["source_sha"], "path": "skills/demo/example.md",
                                 "quote": example_line}],
             "reason": f"Illustrative example path {example_line} in a documented example",
             "replacements": []},
        ],
    }
    # A surviving instance instruction with no justification is a review failure,
    # even though a source anchor quotes it: the hit is not a path/date veto, but
    # the review still has to name what stays and why.
    with pytest.raises(core.WorkflowError) as excinfo:
        core.validate_review(c, unchanged, lab["publisher"], w)
    message = str(excinfo.value)
    assert "instance-specific" in message and instance in message

    # Generalizing the incoming instruction makes the corrected final result pass.
    replace_text(w / "skills/demo/SKILL.md", instance,
                 "Deploy only from the configured private vault root.")
    g(w, "add", "--", "skills/demo/SKILL.md")
    corrected = clone(unchanged)
    corrected["files"][0]["reason"] = "Generalize an instance-specific deployment path"
    assert core.validate_review(c, corrected, lab["publisher"], w) is None
    tree = core.validate_tree(c, w, corrected)
    assert tree == {"tree": g(w, "write-tree"),
                    "paths": ["skills/demo/SKILL.md", "skills/demo/example.md"]}
    assert "/home/olaf" not in (w / "skills/demo/SKILL.md").read_text(encoding="utf-8")


def test_final_gate_blocks_unmerged_and_unstaged(core, lab):
    producer = lab["producer"]
    g(producer, "checkout", "-q", "main")
    replace_text(producer / "skills/demo/SKILL.md", "Base instruction.", "Main branch instruction.")
    g(producer, "add", "--", "skills/demo/SKILL.md")
    g(producer, "commit", "-q", "-m", "main-side same-line edit")
    g(producer, "push", "-q", "origin", "main")
    g(producer, "checkout", "-q", "machine/testlab")
    replace_text(producer / "skills/demo/SKILL.md", "Base instruction.", "Transport branch instruction.")
    g(producer, "add", "--", "skills/demo/SKILL.md")
    g(producer, "commit", "-q", "-m", "transport-side same-line edit")
    g(producer, "push", "-q", "origin", "machine/testlab")

    c = capture(lab, core)
    c = core.prepare(lab["publisher"], lab["store"], c)
    w = Path(c["worktree"])
    assert c["conflict_paths"] == ["skills/demo/SKILL.md"]
    conflict_review = {
        "schema": 1, "candidate_id": c["id"], "main_sha": c["main_sha"],
        "source_sha": c["source_sha"], "summary": "Resolve the conflicting instruction",
        "files": [{"path": "skills/demo/SKILL.md", "change_type": "correction",
                   "decision": "combine",
                   "source_anchors": [{"ref": c["source_sha"], "path": "skills/demo/SKILL.md",
                                       "quote": "Transport branch instruction."}],
                   "reason": "Both sides rewrote the same instruction", "replacements": []}],
    }
    with pytest.raises(core.WorkflowError) as excinfo:
        core.validate_tree(c, w, conflict_review)
    message = str(excinfo.value)
    assert "unmerged" in message and "skills/demo/SKILL.md" in message

    resolved = ("---\nname: demo\ndescription: Demonstration skill.\n---\n\n# Demo\n\n"
                "Merged canonical instruction.\n")
    (w / "skills/demo/SKILL.md").write_text(resolved, encoding="utf-8")
    g(w, "add", "--", "skills/demo/SKILL.md")
    assert unmerged_rows(w) == []
    review = clone(conflict_review)
    review["files"][0]["source_anchors"] = [
        {"ref": c["main_sha"], "path": "skills/demo/SKILL.md", "quote": "Main branch instruction."},
        {"ref": c["source_sha"], "path": "skills/demo/SKILL.md",
         "quote": "Transport branch instruction."},
    ]
    review["files"][0]["replacements"] = [{
        "old_ref": c["source_sha"], "old_path": "skills/demo/SKILL.md",
        "old_quote": "Transport branch instruction.", "new_path": "skills/demo/SKILL.md",
        "new_quote": "Merged canonical instruction.", "reason": "Resolve the conflicting rewrite",
    }]
    assert core.validate_review(c, review, lab["publisher"], w) is None
    clean = core.validate_tree(c, w, review)
    assert set(clean) == {"tree", "paths"}
    assert clean["tree"] == g(w, "write-tree")

    # A dirty working tree is not the reviewed artifact.
    with (w / "skills/demo/SKILL.md").open("a", encoding="utf-8") as handle:
        handle.write("Extra local note.\n")
    with pytest.raises(core.WorkflowError) as excinfo:
        core.validate_tree(c, w, review)
    assert "unstaged" in str(excinfo.value) and "skills/demo/SKILL.md" in str(excinfo.value)
    g(w, "add", "--", "skills/demo/SKILL.md")
    staged_note = core.validate_tree(c, w, review)
    assert staged_note["tree"] != clean["tree"]

    scratch = w / "skills/demo/scratch.md"
    scratch.write_text("scratch\n", encoding="utf-8")
    with pytest.raises(core.WorkflowError) as excinfo:
        core.validate_tree(c, w, review)
    assert "untracked" in str(excinfo.value) and "skills/demo/scratch.md" in str(excinfo.value)
    scratch.unlink()
    assert core.validate_tree(c, w, review)["tree"] == staged_note["tree"]


def test_final_gate_preserves_all_manifest_paths(core, lab):
    publish_files(lab, {"skills/demo/old.md": ("Obsolete guidance.\n", None)})
    instance = "Local only: /home/olaf/private/notes.md"

    def mutate(root):
        (root / "skills/demo/old.md").unlink()
        (root / "skills/demo/new.md").write_text("A second useful generic rule.\n", encoding="utf-8")
        (root / "skills/demo/rejected.md").write_text(instance + "\n", encoding="utf-8")
        replace_text(root / "skills/demo/SKILL.md", "Base instruction.",
                     "Base instruction.\nA useful generic rule.")

    source_commit(lab, mutate, "add, delete and add a rejected path")
    c = capture(lab, core)
    c = core.prepare(lab["publisher"], lab["store"], c)
    w = Path(c["worktree"])
    assert set(c["input_paths"]) == {
        "skills/demo/old.md", "skills/demo/new.md", "skills/demo/rejected.md",
        "skills/demo/SKILL.md",
    }

    # The agent rejects the instance-specific addition outright.
    (w / "skills/demo/rejected.md").unlink()
    g(w, "add", "-A", "--", "skills/demo/rejected.md")
    assert "skills/demo/rejected.md" not in index_stage(w)
    assert staged_status(w, c["main_sha"]) == [
        ("M", "skills/demo/SKILL.md"),
        ("A", "skills/demo/new.md"),
        ("D", "skills/demo/old.md"),
    ]

    review = {
        "schema": 1, "candidate_id": c["id"], "main_sha": c["main_sha"],
        "source_sha": c["source_sha"], "summary": "Accept two lessons, drop an obsolete rule and reject local text",
        "files": [
            {"path": "skills/demo/SKILL.md", "change_type": "addition", "decision": "accept",
             "source_anchors": [{"ref": c["source_sha"], "path": "skills/demo/SKILL.md",
                                 "quote": "A useful generic rule."}],
             "reason": "Useful generic addition", "replacements": []},
            {"path": "skills/demo/new.md", "change_type": "addition", "decision": "accept",
             "source_anchors": [{"ref": c["source_sha"], "path": "skills/demo/new.md",
                                 "quote": "A second useful generic rule."}],
             "reason": "Second useful generic addition", "replacements": []},
            {"path": "skills/demo/old.md", "change_type": "unsuitable", "decision": "accept",
             "source_anchors": [{"ref": c["main_sha"], "path": "skills/demo/old.md",
                                 "quote": "Obsolete guidance."}],
             "reason": "Obsolete guidance that the source deliberately deletes",
             "replacements": []},
            {"path": "skills/demo/rejected.md", "change_type": "unsuitable", "decision": "reject",
             "source_anchors": [{"ref": c["source_sha"], "path": "skills/demo/rejected.md",
                                 "quote": instance}],
             "reason": "Instance-specific local path; not a shared lesson", "replacements": []},
        ],
    }
    assert core.validate_review(c, review, lab["publisher"], w) is None
    gate = core.validate_tree(c, w, review)
    assert gate["paths"] == [
        "skills/demo/SKILL.md", "skills/demo/new.md",
        "skills/demo/old.md", "skills/demo/rejected.md",
    ]
    assert gate["tree"] == g(w, "write-tree")

    # A dropped decision — clean, deleted or rejected — is a coverage failure.
    for index in range(len(review["files"])):
        partial = clone(review)
        dropped = partial["files"].pop(index)["path"]
        with pytest.raises(core.WorkflowError) as excinfo:
            core.validate_tree(c, w, partial)
        assert dropped in str(excinfo.value) and "cover" in str(excinfo.value)

    # A replacement cannot point at a covered path that the final index drops.
    ghost = clone(review)
    ghost["files"][3]["replacements"] = [{
        "old_ref": c["source_sha"], "old_path": "skills/demo/rejected.md",
        "old_quote": instance, "new_path": "skills/demo/rejected.md",
        "new_quote": "portable text", "reason": "Portable replacement",
    }]
    with pytest.raises(core.WorkflowError) as excinfo:
        core.validate_review(c, ghost, lab["publisher"], w)
    assert "not present in the final staged result" in str(excinfo.value)


# ---------------------------------------------------------------------------
# C3: validation commands are real, allowlisted evidence.
# ---------------------------------------------------------------------------

FAILING_PACKAGE_TEST = "def test_the_candidate_is_wrong():\n    assert 1 == 2\n"


def failing_package_candidate(core, lab):
    """Candidate that adds one deliberately failing package test."""
    publish_files(lab, {"skills/skill-library-maintenance/SKILL.md":
                        ("---\nname: skill-library-maintenance\ndescription: Maintenance.\n---\n\n"
                         "# Maintenance\n\nBase guidance.\n", None)})

    def mutate(root):
        target = root / "skills/skill-library-maintenance/tests/test_deliberate_failure.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(FAILING_PACKAGE_TEST, encoding="utf-8")

    tip = source_commit(lab, mutate, "add a deliberately failing package test")
    c = capture(lab, core)
    c = core.prepare(lab["publisher"], lab["store"], c)
    w = Path(c["worktree"])
    path = "skills/skill-library-maintenance/tests/test_deliberate_failure.py"
    review = review_for(c, path=path, quote="assert 1 == 2",
                        reason="Deliberate failing fixture proving check propagation")
    core.validate_review(c, review, lab["publisher"], w)
    assert c["source_sha"] == tip
    return c, w, review


def test_checks_run_every_changed_package_and_block_omitted_suite(core, lab):
    publish_files(lab, {
        "skills/unchanged/tests/test_never_run.py": (FAILING_PACKAGE_TEST, None),
    })
    paths = ["skills/demo/tests/test_failure.py", "skills/other/tests/test_success.py"]
    def mutate(root):
        for path, text in zip(paths, (FAILING_PACKAGE_TEST, "def test_other():\n    assert True\n")):
            (root / path).parent.mkdir(parents=True, exist_ok=True)
            (root / path).write_text(text)
    source_commit(lab, mutate)
    c = core.prepare(lab["publisher"], lab["store"], capture(lab, core))
    w = Path(c["worktree"])
    rows = core.run_checks(c, w)
    by_name = {row["name"]: row for row in rows}
    assert "package-tests:skills/demo" in by_name, "changed demo package suite was silently omitted"
    assert by_name["package-tests:skills/demo"]["status"] == "failed"
    assert by_name["package-tests:skills/demo"]["exit_code"] == 1
    assert "test_the_candidate_is_wrong" in by_name["package-tests:skills/demo"]["stdout"]
    assert by_name["package-tests:skills/other"]["status"] == "passed"
    assert by_name["package-tests:skills/other"]["required"] is True
    assert "package-tests:skills/unchanged" not in by_name
    assert by_name["package-tests:skills/skill-library-maintenance"]["status"] == "not-applicable"
    review = {**review_for(c), "files": [
        review_for(c, path=path, quote="def test_")["files"][0] for path in paths]}
    validation = core.validate_tree(c, w, review)
    missing = [row for row in rows if row["name"] != "package-tests:skills/demo"]
    with pytest.raises(core.WorkflowError, match="missing.*package-tests:skills/demo"):
        core.record_review(lab["store"], c["id"], review, missing, validation)
    with pytest.raises(core.WorkflowError, match="failed.*package-tests:skills/demo"):
        core.record_review(lab["store"], c["id"], review, rows, validation)
    assert core.load_candidate(lab["store"], c["id"])["status"] == "prepared"


def test_checks_discover_packages_from_agent_staged_changes(core, lab):
    offer(lab)
    c = core.prepare(lab["publisher"], lab["store"], capture(lab, core))
    w = Path(c["worktree"])
    path = "skills/agent-added/tests/test_failure.py"
    (w / path).parent.mkdir(parents=True)
    (w / path).write_text(FAILING_PACKAGE_TEST)
    g(w, "add", "--", path)
    rows = {row["name"]: row for row in core.run_checks(c, w)}
    assert "package-tests:skills/agent-added" in rows
    assert rows["package-tests:skills/agent-added"]["status"] == "failed"
    assert rows["package-tests:skills/demo"]["status"] == "not-applicable"


def test_other_package_cannot_remove_previously_required_suite(core, lab):
    path = "skills/demo/tests/test_old.py"
    publish_files(lab, {path: ("def test_old():\n    assert True\n", None)})
    source_commit(lab, lambda root: (root / path).unlink())
    c = core.prepare(lab["publisher"], lab["store"], capture(lab, core))
    with pytest.raises(core.WorkflowError, match="disappeared.*skills/demo/tests"):
        core.run_checks(c, Path(c["worktree"]))


def test_each_changed_package_gets_its_trusted_validator(core, lab):
    validator = "skills/skill-builder/scripts/skills-ref.sh"
    publish_files(lab, {validator: ("#!/bin/sh\nprintf 'validated %s\\n' \"$2\"\n", 0o755)})
    g(lab["publisher"], "fetch", "-q", "origin")
    g(lab["publisher"], "merge", "-q", "--ff-only", "origin/main")
    offer(lab)
    c = core.prepare(lab["publisher"], lab["store"], capture(lab, core))
    rows = {row["name"]: row for row in core.run_checks(c, Path(c["worktree"]))}
    assert "package-validator:skills/demo" in rows
    assert rows["package-validator:skills/demo"]["status"] == "passed"
    assert rows["package-validator:skills/demo"]["required"] is True
    validated = Path(rows["package-validator:skills/demo"]["stdout"].strip().removeprefix("validated "))
    assert validated.parts[-2:] == ("skills", "demo")
    assert validated != Path(c["worktree"]) / "skills/demo"
    assert validated.parent.parent.name.startswith("skill-sync-tree-")
    assert not validated.parent.parent.exists()  # validator consumed the same disposable tree


def test_failed_check_blocks_publication(core, lab):
    c, w, review = failing_package_candidate(core, lab)
    checks = core.run_checks(c, w)
    assert isinstance(checks, list) and checks
    by_name = {row["name"]: row for row in checks}
    row = by_name["package-tests:skills/skill-library-maintenance"]
    assert set(row) == {"name", "required", "status", "exit_code", "stdout", "stderr"}
    assert row["required"] is True and row["status"] == "failed"
    assert isinstance(row["exit_code"], int) and row["exit_code"] != 0
    assert "test_the_candidate_is_wrong" in row["stdout"] + row["stderr"]
    assert not any("passed" in current for current in checks)
    assert by_name["index-whitespace"]["status"] == "passed"
    assert by_name["staged-syntax"]["status"] == "passed"

    validation = core.validate_tree(c, w, review)
    with pytest.raises(core.WorkflowError) as excinfo:
        core.record_review(lab["store"], c["id"], review, checks, validation)
    message = str(excinfo.value)
    assert "failed" in message and "package-tests" in message
    assert core.load_candidate(lab["store"], c["id"])["status"] == "prepared"


@pytest.mark.parametrize("shadow_paths,marker", [
    pytest.param(["pytest.py"], "SHADOW_PYTEST_EXECUTED", id="pytest-module"),
    pytest.param(["pytest/__init__.py", "pytest/__main__.py"],
                 "SHADOW_PYTEST_PACKAGE_EXECUTED", id="pytest-package"),
    pytest.param(["sitecustomize.py"], "SHADOW_SITECUSTOMIZE_EXECUTED", id="sitecustomize"),
    pytest.param(["usercustomize.py"], "SHADOW_USERCUSTOMIZE_EXECUTED", id="usercustomize"),
    pytest.param(["_pytest/__init__.py"], "SHADOW_INTERNAL_PYTEST_EXECUTED", id="_pytest-package"),
])
def test_candidate_root_modules_cannot_replace_pytest_runner(core, lab, shadow_paths, marker):
    path = "skills/demo/tests/test_failure.py"
    failing = "def test_failure():\n    assert False\n"
    # The pytest.py payload is the independent reviewer's exact reproduction.
    shadow = f"print({marker!r})\nraise SystemExit(0)\n"
    if shadow_paths[0] in ("sitecustomize.py", "usercustomize.py"):
        shadow = f"import os\nprint({marker!r}, flush=True)\nos._exit(0)\n"

    def mutate(root):
        for relative, text in [(path, failing), *[(p, shadow) for p in shadow_paths]]:
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)

    source_commit(lab, mutate)
    c = core.prepare(lab["publisher"], lab["store"], capture(lab, core))
    w = Path(c["worktree"])
    rows = core.run_checks(c, w)
    row = next(row for row in rows if row["name"] == "package-tests:skills/demo")
    assert row["required"] is True
    assert row["status"] == "failed" and row["exit_code"] == 1, row
    assert "1 failed" in row["stdout"] and "test_failure" in row["stdout"]
    assert all(marker not in result["stdout"] + result["stderr"] for result in rows), rows
    review = review_for(c, path=path, quote="assert False")
    for relative in shadow_paths:
        review["files"].extend(review_for(c, path=relative, quote=marker)["files"])
    validation = core.validate_tree(c, w, review)
    with pytest.raises(core.WorkflowError, match="failed.*package-tests:skills/demo"):
        core.record_review(lab["store"], c["id"], review, rows, validation)
    with pytest.raises(core.WorkflowError):
        core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    assert core.load_candidate(lab["store"], c["id"])["status"] == "prepared"
    assert remote_ref(lab["producer"], "refs/heads/main") == c["main_sha"]


def pytest_control_candidate(core, lab, files):
    """Stage real candidate controls without changing the trusted test harness."""
    def mutate(root):
        for relative, text in files.items():
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)

    source_commit(lab, mutate)
    c = core.prepare(lab["publisher"], lab["store"], capture(lab, core))
    review = review_for(c)
    review["files"] = [review_for(c, path=path, quote=text.splitlines()[0])["files"][0]
                       for path, text in files.items()]
    return c, Path(c["worktree"]), review


def refuse_failed_pytest_publication(core, lab, c, w, review, rows):
    validation = core.validate_tree(c, w, review)
    with pytest.raises(core.WorkflowError, match="failed.*package-tests:skills/demo"):
        core.record_review(lab["store"], c["id"], review, rows, validation)
    with pytest.raises(core.WorkflowError):
        core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    assert core.load_candidate(lab["store"], c["id"])["status"] == "prepared"
    assert remote_ref(lab["producer"], "refs/heads/main") == c["main_sha"]


@pytest.mark.parametrize("payload", [
    pytest.param("def pytest_sessionfinish(session, exitstatus):\n    session.exitstatus = 0\n",
                 id="session-exit"),
    pytest.param("def pytest_cmdline_main(config):\n"
                 "    print('ROOT_CONFTEST_REPLACED_RUNNER')\n    return 0\n",
                 id="cmdline-main"),
    pytest.param("def pytest_ignore_collect(collection_path, config):\n"
                 "    return collection_path.name == 'test_failure.py'\n", id="ignore-failure"),
    pytest.param("def pytest_collection_modifyitems(config, items):\n"
                 "    rejected = [item for item in items if 'candidate_is_wrong' in item.name]\n"
                 "    items[:] = [item for item in items if item not in rejected]\n"
                 "    config.hook.pytest_deselected(items=rejected)\n", id="deselect-failure"),
])
def test_candidate_root_conftest_cannot_control_required_package_checks(core, lab, payload):
    # The first two payloads are the independent reviewer's exact N3 probes.
    files = {"skills/demo/tests/test_failure.py": FAILING_PACKAGE_TEST,
             "skills/demo/tests/test_control.py": "def test_control():\n    assert True\n",
             "conftest.py": payload}
    c, w, review = pytest_control_candidate(core, lab, files)
    rows = core.run_checks(c, w)
    row = next(row for row in rows if row["name"] == "package-tests:skills/demo")
    assert row["required"] is True
    assert row["status"] == "failed" and row["exit_code"] == 1, row
    assert "1 failed" in row["stdout"] and "1 passed" in row["stdout"], row
    assert "test_the_candidate_is_wrong" in row["stdout"], row
    assert "ROOT_CONFTEST_REPLACED_RUNNER" not in row["stdout"] + row["stderr"], row
    refuse_failed_pytest_publication(core, lab, c, w, review, rows)


@pytest.mark.parametrize("config_path,configuration", [
    pytest.param("pytest.ini", "[pytest]\naddopts = -k nothing\n", id="pytest-ini-nothing"),
    pytest.param("pytest.ini", "[pytest]\naddopts = --ignore=skills/demo/tests\n",
                 id="pytest-ini-ignore-suite"),
    pytest.param("pytest.ini", "[pytest]\naddopts = --ignore=skills/demo/tests/test_failure.py\n",
                 id="pytest-ini-ignore-failure"),
    pytest.param("setup.cfg", "[tool:pytest]\naddopts = -k test_control\n", id="setup-cfg"),
    pytest.param("tox.ini", "[pytest]\naddopts = -k test_control\n", id="tox-ini"),
    pytest.param("pyproject.toml", '[tool.pytest.ini_options]\naddopts = "-k test_control"\n',
                 id="pyproject-toml"),
    pytest.param("skills/demo/pytest.ini", "[pytest]\naddopts = -k nothing\n",
                 id="package-config-also-untrusted"),
])
def test_candidate_pytest_configuration_cannot_suppress_required_failure(
    core, lab, config_path, configuration,
):
    files = {"skills/demo/tests/test_failure.py": FAILING_PACKAGE_TEST,
             "skills/demo/tests/test_control.py": "def test_control():\n    assert True\n",
             config_path: configuration}
    c, w, review = pytest_control_candidate(core, lab, files)
    rows = core.run_checks(c, w)
    row = next(row for row in rows if row["name"] == "package-tests:skills/demo")
    assert row["required"] is True
    assert row["status"] == "failed" and row["exit_code"] == 1, row
    assert "1 failed" in row["stdout"] and "1 passed" in row["stdout"], row
    assert "test_the_candidate_is_wrong" in row["stdout"], row
    refuse_failed_pytest_publication(core, lab, c, w, review, rows)


@pytest.mark.parametrize("conftest_path,payload,offending_name", [
    pytest.param("skills/demo/conftest.py",
                 "def pytest_sessionfinish(session, exitstatus):\n    session.exitstatus = 0\n",
                 "pytest_sessionfinish", id="session-finish"),
    pytest.param("skills/demo/conftest.py",
                 "def pytest_cmdline_main(config):\n    return 0\n",
                 "pytest_cmdline_main", id="cmdline-main"),
    pytest.param("skills/demo/tests/conftest.py",
                 "import pytest\ndef pytest_collection_modifyitems(items):\n"
                 "    for item in items:\n"
                 "        if 'candidate_is_wrong' in item.name:\n"
                 "            item.add_marker(pytest.mark.skip(reason='hide the failure'))\n",
                 "pytest_collection_modifyitems", id="collection-skip-failure"),
    pytest.param("skills/demo/conftest.py", "pytest_plugins = ['runner_plugin']\n",
                 "pytest_plugins", id="plugin-injection"),
    pytest.param("skills/demo/tests/nested/conftest.py", "pytest_runtest_makereport = None\n",
                 "pytest_runtest_makereport", id="nested-conftest-assignment"),
    pytest.param("skills/demo/helpers/deep/conftest.py", "pytest_plugins: list = []\n",
                 "pytest_plugins", id="outside-tests-annotated-plugins"),
    pytest.param("skills/demo/conftest.py", "alias = pytest_plugins = []\n",
                 "pytest_plugins", id="chained-assignment"),
    pytest.param("skills/demo/conftest.py", "(alias, pytest_plugins) = (None, [])\n",
                 "pytest_plugins", id="unpacked-assignment"),
    pytest.param("skills/demo/conftest.py", "if True:\n    pytest_plugins = []\n",
                 "pytest_plugins", id="conditional-module-binding"),
    pytest.param("skills/demo/conftest.py", "async def pytest_fake():\n    pass\n",
                 "pytest_fake", id="async-hook"),
    # v3 closes unknown namespaces, escaping globals and dynamic module access.
    pytest.param("skills/demo/conftest.py", "from runner_helper import *\n",
                 "module-level wildcard imports refused by policy: from runner_helper import *",
                 id="v3-wildcard-exported-hook"),
    pytest.param("skills/demo/conftest.py", "if False:\n    from contextlib import *\n",
                 "module-level wildcard imports refused by policy: from contextlib import *",
                 id="v3-conditional-benign-wildcard"),
    pytest.param("skills/demo/conftest.py",
                 "class Bind:\n    global pytest_sessionfinish\n"
                 "    def pytest_sessionfinish(session, exitstatus):\n        session.exitstatus = 0\n",
                 "global runner-control declarations refused by policy: pytest_sessionfinish",
                 id="v3-class-global-hook"),
    pytest.param("skills/demo/conftest.py",
                 "def helper():\n    global pytest_plugins\n    pytest_plugins = ['runner_plugin']\nhelper()\n",
                 "global runner-control declarations refused by policy: pytest_plugins",
                 id="v3-function-global-plugins"),
    pytest.param("skills/demo/conftest.py", "global pytest_plugins\n",
                 "global runner-control declarations refused by policy: pytest_plugins",
                 id="v3-module-global-declaration"),
    pytest.param("skills/demo/conftest.py",
                 "async def outer():\n    class Inner:\n        def helper():\n"
                 "            global ordinary, pytest_plugins\n",
                 "global runner-control declarations refused by policy: pytest_plugins",
                 id="v3-nested-uncalled-global"),
    pytest.param("skills/demo/conftest.py", "import sys\nregistry = sys.modules\n",
                 "module-level dynamic references refused by policy: sys.modules",
                 id="v3-sys-modules-reference"),
    pytest.param("skills/demo/conftest.py",
                 "import sys\nfrom runner_helper import pytest_sessionfinish as finish\n"
                 "sys.modules[__name__].__dict__['pytest_sessionfinish'] = finish\n",
                 "module-level dynamic references refused by policy: sys.modules",
                 id="v3-sys-modules-subscript"),
    pytest.param("skills/demo/conftest.py",
                 "import sys\nfrom runner_helper import pytest_sessionfinish as finish\n"
                 "sys.modules[__name__].__setattr__('pytest_sessionfinish', finish)\n",
                 "module-level dynamic references refused by policy: sys.modules",
                 id="v3-sys-modules-dunder-setattr"),
    pytest.param("skills/demo/conftest.py", "ordinary = __builtins__['__import__']('sys')\n",
                 "module-level dynamic references refused by policy: __builtins__",
                 id="v3-builtins-subscript"),
    pytest.param("skills/demo/conftest.py", "ordinary = __builtins__\n",
                 "module-level dynamic references refused by policy: __builtins__",
                 id="v3-builtins-reference"),
    pytest.param("skills/demo/conftest.py", "ordinary = __builtins__.__import__\n",
                 "module-level dynamic references refused by policy: __builtins__",
                 id="v3-builtins-attribute"),
    pytest.param("skills/demo/conftest.py",
                 "def __getattr__(name):\n    if name == 'pytest_plugins':\n"
                 "        return ['runner_plugin']\n    raise AttributeError(name)\n",
                 "module-level attribute hooks refused by policy: __getattr__",
                 id="v3-pep562-getattr"),
    pytest.param("skills/demo/conftest.py", "def __getattribute__(name):\n    raise AttributeError(name)\n",
                 "module-level attribute hooks refused by policy: __getattribute__",
                 id="v3-getattribute-definition"),
    pytest.param("skills/demo/conftest.py", "def __dir__():\n    return ['pytest_sessionfinish']\n",
                 "module-level attribute hooks refused by policy: __dir__",
                 id="v3-dir-definition"),
    pytest.param("skills/demo/conftest.py", "if False:\n    async def __getattr__(name):\n        pass\n",
                 "module-level attribute hooks refused by policy: __getattr__",
                 id="v3-conditional-async-attribute-hook"),
    # Round 9: ordinary dunder bindings must use the same guard as pytest_*.
    pytest.param("skills/demo/conftest.py",
                 "def missing(name):\n    raise AttributeError(name)\n"
                 "__getattr__ = lambda name: (lambda session, exitstatus: "
                 "session.__setattr__('exitstatus', 0)) if name == 'pytest_sessionfinish' else missing(name)\n"
                 "__dir__ = lambda: ['pytest_sessionfinish']\n",
                 "module-level attribute hooks refused by policy: __dir__, __getattr__",
                 id="v4-round9-lambda-assignments"),
    pytest.param("skills/demo/conftest.py",
                 "class Bind:\n    global __getattr__, __dir__\n"
                 "    def __getattr__(name):\n        if name == 'pytest_sessionfinish':\n"
                 "            def finish(session, exitstatus):\n                session.exitstatus = 0\n"
                 "            return finish\n        raise AttributeError(name)\n"
                 "    def __dir__():\n        return ['pytest_sessionfinish']\n",
                 "global runner-control declarations refused by policy: __dir__, __getattr__",
                 id="v4-round9-class-global-dunder-defs"),
    *[pytest.param("skills/demo/conftest.py", template.replace("HOOK", name),
                   f"module-level attribute hooks refused by policy: {name}",
                   id=f"v4-{name}-{form}")
      for name in ("__getattr__", "__getattribute__", "__dir__")
      for form, template in [
          ("assignment", "HOOK = None\n"),
          ("annotated-assignment", "HOOK: object = None\n"),
          ("augmented-assignment", "HOOK += []\n"),
          ("chained-assignment", "ordinary = HOOK = None\n"),
          ("tuple-unpacking", "ordinary, HOOK = (None, None)\n"),
          ("starred-unpacking", "ordinary, *HOOK = [None]\n"),
          ("import-alias", "import contextlib as HOOK\n"),
          ("from-import-alias", "from contextlib import nullcontext as HOOK\n"),
          ("from-import-name", "from runner_helper import HOOK\n"),
          ("walrus", "if (HOOK := None):\n    pass\n"),
          ("for-target", "for HOOK in [None]:\n    pass\n"),
          ("async-for-target", "async for HOOK in source:\n    pass\n"),
          ("with-target", "with open(__file__) as HOOK:\n    pass\n"),
          ("async-with-target", "async with manager() as HOOK:\n    pass\n"),
          ("except-target", "try:\n    pass\nexcept Exception as HOOK:\n    pass\n"),
          ("match-capture", "match None:\n    case HOOK:\n        pass\n"),
          ("match-star", "match []:\n    case [*HOOK]:\n        pass\n"),
          ("match-mapping", "match {}:\n    case {**HOOK}:\n        pass\n"),
          ("class-definition", "class HOOK:\n    pass\n"),
          ("function-default", "def helper(value=(HOOK := None)):\n    pass\n"),
          ("lambda-default", "helper = lambda value=(HOOK := None): value\n"),
          ("decorator", "@decorator(HOOK := None)\ndef helper():\n    pass\n"),
          ("class-base", "class Helper((HOOK := object)):\n    pass\n"),
          ("comprehension-walrus", "values = [(HOOK := None) for item in [1]]\n"),
      ]],
    *[pytest.param("skills/demo/conftest.py", template.replace("HOOK", name),
                   f"global runner-control declarations refused by policy: {name}",
                   id=f"v4-{name}-global-{scope}")
      for name in ("__getattr__", "__getattribute__", "__dir__")
      for scope, template in [
          ("module", "global HOOK\n"),
          ("function", "def helper():\n    global HOOK\n    HOOK = None\n"),
          ("class", "class Bind:\n    global HOOK\n    def HOOK(name):\n        pass\n"),
          ("deep-uncalled", "async def outer():\n    class Inner:\n        def helper():\n"
                            "            global ordinary, HOOK\n"),
      ]],
    # The reviewer's ordinary static bindings previously published real failures.
    pytest.param("skills/demo/conftest.py", "from runner_helper import pytest_sessionfinish\n",
                 "pytest_sessionfinish", id="direct-import-hook"),
    pytest.param("skills/demo/conftest.py", "for pytest_plugins in [['runner_plugin']]:\n    pass\n",
                 "pytest_plugins", id="loop-plugins"),
    pytest.param("skills/demo/conftest.py", "from runner_helper import pytest_sessionfinish as pytest_cmdline_main\n",
                 "pytest_cmdline_main", id="from-import-alias"),
    pytest.param("skills/demo/conftest.py", "import contextlib as pytest_plugins\n",
                 "pytest_plugins", id="import-alias"),
    pytest.param("skills/demo/conftest.py", "import xml.etree as pytest_plugins\n",
                 "pytest_plugins", id="dotted-import-alias"),
    pytest.param("skills/demo/conftest.py", "import pytest_fake.child\n",
                 "pytest_fake", id="dotted-import-top-level-name"),
    pytest.param("skills/demo/conftest.py", "for alias, pytest_plugins in [(None, ['runner_plugin'])]:\n    pass\n",
                 "pytest_plugins", id="tuple-loop-target"),
    pytest.param("skills/demo/conftest.py", "for [alias, *pytest_plugins] in [[None, 'runner_plugin']]:\n    pass\n",
                 "pytest_plugins", id="list-starred-loop-target"),
    pytest.param("skills/demo/conftest.py", "async for pytest_plugins in source:\n    pass\n",
                 "pytest_plugins", id="async-loop-target"),
    pytest.param("skills/demo/conftest.py", "with open(__file__) as pytest_plugins:\n    pass\n",
                 "pytest_plugins", id="with-target"),
    pytest.param("skills/demo/conftest.py", "with manager() as (alias, [pytest_plugins]):\n    pass\n",
                 "pytest_plugins", id="unpacked-with-target"),
    pytest.param("skills/demo/conftest.py", "async with manager() as pytest_plugins:\n    pass\n",
                 "pytest_plugins", id="async-with-target"),
    pytest.param("skills/demo/conftest.py", "try:\n    raise Exception()\nexcept Exception as pytest_sessionfinish:\n    pass\n",
                 "pytest_sessionfinish", id="except-target"),
    pytest.param("skills/demo/conftest.py", "if (pytest_plugins := ['runner_plugin']):\n    pass\n",
                 "pytest_plugins", id="walrus-binding"),
    pytest.param("skills/demo/conftest.py", "pytest_plugins += ['runner_plugin']\n",
                 "pytest_plugins", id="augmented-binding"),
    pytest.param("skills/demo/conftest.py", "class pytest_fake:\n    pass\n",
                 "pytest_fake", id="class-binding"),
    pytest.param("skills/demo/conftest.py", "match None:\n    case pytest_plugins:\n        pass\n",
                 "pytest_plugins", id="match-capture"),
    pytest.param("skills/demo/conftest.py", "match []:\n    case [*pytest_plugins]:\n        pass\n",
                 "pytest_plugins", id="match-star-capture"),
    pytest.param("skills/demo/conftest.py", "match {}:\n    case {**pytest_plugins}:\n        pass\n",
                 "pytest_plugins", id="match-mapping-capture"),
    pytest.param("skills/demo/conftest.py", "def helper(value=(pytest_plugins := [])):\n    pass\n",
                 "pytest_plugins", id="function-default-outer-binding"),
    pytest.param("skills/demo/conftest.py", "@decorator(pytest_plugins := [])\ndef helper():\n    pass\n",
                 "pytest_plugins", id="decorator-outer-binding"),
    pytest.param("skills/demo/conftest.py", "helper = lambda value=(pytest_plugins := []): value\n",
                 "pytest_plugins", id="lambda-default-outer-binding"),
    pytest.param("skills/demo/conftest.py", "class Helper((pytest_plugins := object)):\n    pass\n",
                 "pytest_plugins", id="class-base-outer-binding"),
    pytest.param("skills/demo/conftest.py", "values = [(pytest_plugins := []) for item in [1]]\n",
                 "pytest_plugins", id="comprehension-walrus-outer-binding"),
    *[pytest.param("skills/demo/conftest.py", payload, name, id=f"dynamic-{name}")
      for name, payload in [
          ("exec", "exec('pass')\n"),
          ("eval", "eval('None')\n"),
          ("compile", "compile('pass', '<candidate>', 'exec')\n"),
          ("globals", "globals()\n"),
          ("locals", "locals()\n"),
          ("setattr", "import sys\nsetattr(sys.modules[__name__], 'ordinary', None)\n"),
          ("__import__", "__import__('sys')\n"),
      ]],
    pytest.param("skills/demo/conftest.py", "import builtins\nbuiltins.exec('pass')\n",
                 "exec", id="dynamic-qualified-exec"),
    pytest.param("skills/demo/conftest.py", "if False:\n    globals()\n",
                 "globals", id="dynamic-conditional-call"),
    pytest.param("skills/demo/conftest.py", "def helper(value=locals()):\n    pass\n",
                 "locals", id="dynamic-function-default-call"),
])
def test_package_conftest_runner_control_refuses_publication(
    core, lab, monkeypatch, conftest_path, payload, offending_name,
):
    failure_path = "skills/demo/tests/test_failure.py"
    files = {failure_path: FAILING_PACKAGE_TEST,
             "skills/demo/tests/test_control.py": "def test_control():\n    assert True\n",
             conftest_path: payload}
    if "runner_plugin" in payload:
        files["skills/demo/runner_plugin.py"] = (
            "def pytest_sessionfinish(session, exitstatus):\n    session.exitstatus = 0\n")
    if "runner_helper" in payload:
        files["skills/demo/runner_helper.py"] = (
            "def pytest_sessionfinish(session, exitstatus):\n    session.exitstatus = 0\n")
    c, w, review = pytest_control_candidate(core, lab, files)
    # Prove that the bound candidate contains a real failure, independently of
    # its conftest. A hook that returns zero must not turn that artifact green.
    actual = execute_artifact_test(lab, g(w, "show", f":{failure_path}") + "\n")
    assert actual.returncode == 1 and "1 failed" in actual.stdout, actual.stdout
    check_calls, real = [], core._run_check_process
    def observe(argv, cwd):
        check_calls.append(list(argv))
        return real(argv, cwd)
    monkeypatch.setattr(core, "_run_check_process", observe)
    try:
        rows = core.run_checks(c, w)
    except core.WorkflowError as exc:
        message = str(exc)
        assert "runner control" in message and conftest_path in message
        assert offending_name in message
        if offending_name in {"exec", "eval", "compile", "globals", "locals", "setattr", "__import__"}:
            assert "module-level dynamic calls refused by policy" in message
    else:
        pytest.fail(f"runner-control conftest was accepted: {rows!r}")
    assert check_calls == [], "runner-control preflight ran a check before refusing"
    directory = lab["store"] / "candidates" / c["id"]
    assert not (directory / "checks-run.json").exists(), "refusal left green check evidence"
    assert not (directory / "checks.json").exists()
    with pytest.raises(core.WorkflowError):
        core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    assert core.load_candidate(lab["store"], c["id"])["status"] == "prepared"
    assert remote_ref(lab["producer"], "refs/heads/main") == c["main_sha"]


@pytest.mark.parametrize("with_suite", [False, True], ids=["without-suite", "with-suite"])
def test_changed_package_checks_unchanged_conftests_even_without_suite(core, lab, with_suite):
    path = "skills/demo/helpers/deep/conftest.py"
    payload = "def pytest_sessionfinish(session, exitstatus):\n    session.exitstatus = 0\n"
    publish_files(lab, {path: (payload, None)})
    files = {"skills/demo/new-guidance.md": "New guidance in this package.\n"}
    if with_suite:
        files["skills/demo/tests/test_failure.py"] = FAILING_PACKAGE_TEST
    c, w, _review = pytest_control_candidate(core, lab, files)
    assert path not in c["input_paths"], "control must inspect an unchanged conftest"
    with pytest.raises(core.WorkflowError, match=f"{path}: pytest_sessionfinish"):
        core.run_checks(c, w)
    assert not (lab["store"] / "candidates" / c["id"] / "checks-run.json").exists()
    with pytest.raises(core.WorkflowError):
        core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    assert remote_ref(lab["producer"], "refs/heads/main") == c["main_sha"]


def test_runner_control_refusal_removes_previous_green_run(core, lab):
    c, w, _review = isolated_pytest_candidate(core, lab)
    rows = core.run_checks(c, w)
    assert all(row["status"] == "passed" for row in rows if row["required"])
    evidence = lab["store"] / "candidates" / c["id"] / "checks-run.json"
    assert evidence.is_file()
    (w / "skills/demo/conftest.py").write_text(
        "def pytest_sessionfinish(session, exitstatus):\n    session.exitstatus = 0\n")
    (w / "skills/demo/tests/test_failure.py").write_text(FAILING_PACKAGE_TEST)
    g(w, "add", "--", "skills/demo/conftest.py", "skills/demo/tests/test_failure.py")
    with pytest.raises(core.WorkflowError, match="runner control.*pytest_sessionfinish"):
        core.run_checks(c, w)
    assert not evidence.exists(), "refused rerun kept earlier green evidence"
    with pytest.raises(core.WorkflowError):
        core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    assert remote_ref(lab["producer"], "refs/heads/main") == c["main_sha"]


@pytest.mark.parametrize("conftest_kind", ["fixtures-only", "nested-function-locals", "nested-dunder-locals",
                                         "class-local-getattr", "ordinary-globals"])
def test_package_owned_conftest_fixture_still_applies_and_candidate_publishes(core, lab, conftest_kind):
    files = {
        "conftest.py": "def pytest_cmdline_main(config):\n"
                       "    print('ROOT_CONFTEST_REPLACED_RUNNER')\n    return 0\n",
        "pytest.ini": "[pytest]\naddopts = -k nothing\n",
        "skills/demo/pytest.ini": "[pytest]\naddopts = -k nothing\n",
        "skills/demo/conftest.py": "import pytest\n@pytest.fixture\n"
                                   "def candidate_value():\n    return 42\n",
        "skills/demo/tests/test_fixture.py": "from pathlib import Path\n"
                                             "def test_package_fixture(candidate_value, pytestconfig):\n"
                                             "    assert candidate_value == 42\n"
                                             "    assert pytestconfig.rootpath == Path.cwd() / 'skills/demo'\n"
                                             "    assert pytestconfig.getini('addopts') == []\n"
                                             "    assert pytestconfig.inipath.read_text() == '[pytest]\\n'\n"
                                             "    assert pytestconfig.inipath.parent != Path.cwd()\n",
    }
    if conftest_kind == "nested-function-locals":
        files["skills/demo/conftest.py"] = (
            "import pytest\n"
            "# def pytest_comment(): ...; pytest_plugins = ['not a binding']\n"
            "example = 'def pytest_string(): pass'\n"
            "def helper():\n"
            "    def pytest_fake():\n        return 42\n"
            "    pytest_plugins = ['function-local, not plugin injection']\n"
            "    return pytest_fake()\n"
            "def uncalled_local_controls():\n"
            "    global ordinary_global_only\n"
            "    from contextlib import nullcontext as pytest_import\n"
            "    import xml.etree as pytest_module\n"
            "    for pytest_loop in [1]:\n        pass\n"
            "    with pytest_import() as pytest_with:\n        pass\n"
            "    try:\n        pass\n    except Exception as pytest_except:\n        pass\n"
            "    if (pytest_walrus := []):\n        pass\n"
            "    exec('pass'); eval('None'); compile('pass', '<local>', 'exec')\n"
            "    globals(); locals(); setattr(pytest_module, 'ordinary', None); __import__('sys')\n"
            "    import sys\n    registry = sys.modules\n    ordinary = __builtins__\n"
            "    def __getattr__(name):\n        return None\n"
            "lambda_helper = lambda: (pytest_plugins := [])\n"
            "class Helper:\n    pytest_plugins = []\n"
            "    def __getattribute__(self, name):\n        return None\n"
            "    def __dir__(self):\n        return []\n"
            "values = [pytest_comp for pytest_comp in [1]]\n"
            "import xml.etree\n"
            "from contextlib import nullcontext as ordinary_helper\n"
            "@pytest.fixture\ndef candidate_value():\n    return helper()\n")
    elif conftest_kind == "nested-dunder-locals":
        files["skills/demo/conftest.py"] = (
            "import pytest\n"
            "def helper():\n"
            "    def __getattr__(name):\n        return 42\n"
            "    __getattribute__ = lambda name: name\n"
            "    __dir__ = lambda: ['candidate_value']\n"
            "    assert __getattribute__(__dir__()[0]) == 'candidate_value'\n"
            "    return __getattr__('candidate_value')\n"
            "@pytest.fixture\ndef candidate_value():\n    return helper()\n")
    elif conftest_kind == "class-local-getattr":
        files["skills/demo/conftest.py"] = (
            "import pytest\n"
            "class Helper:\n"
            "    def __getattr__(self, name):\n"
            "        if name == 'candidate_value':\n            return 42\n"
            "        raise AttributeError(name)\n"
            "@pytest.fixture\ndef candidate_value():\n    return Helper().candidate_value\n")
    elif conftest_kind == "ordinary-globals":
        files["skills/demo/conftest.py"] = (
            "import pytest\nglobal ordinary_module_name\nordinary_module_name = 'allowed'\n"
            "class Bind:\n    global ordinary_class_name\n    ordinary_class_name = 'allowed'\n"
            "def helper():\n    global ordinary_value\n    ordinary_value = 42\n    return ordinary_value\n"
            "@pytest.fixture\ndef candidate_value():\n    return helper()\n")
    c, w, review = pytest_control_candidate(core, lab, files)
    rows = core.run_checks(c, w)
    row = next(row for row in rows if row["name"] == "package-tests:skills/demo")
    assert row["required"] is True and row["status"] == "passed" and row["exit_code"] == 0, row
    assert "1 passed" in row["stdout"], row
    assert "ROOT_CONFTEST_REPLACED_RUNNER" not in row["stdout"] + row["stderr"], row
    validation = core.validate_tree(c, w, review)
    c = core.record_review(lab["store"], c["id"], review, rows, validation)
    text = core.render_review(c, review, rows, validation["tree"])
    note = lab["vault"] / c["report_relative_path"]
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(text)
    core.verify_report(c, text, lab["vault"])
    published = core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    assert published["status"] == "published"
    assert g(lab["remote"], "rev-parse", "refs/heads/main^{tree}") == validation["tree"]


def isolated_pytest_candidate(core, lab):
    files = {
        "skills/demo/tests/runner_helper.py": "def candidate_value():\n    return 42\n",
        "skills/demo/tests/test_runner.py": (
            "import os\nimport sys\nfrom pathlib import Path\n"
            "from runner_helper import candidate_value\n"
            "def test_candidate_imports_with_isolated_runner():\n"
            "    assert candidate_value() == 42\n"
            "    assert sys.flags.isolated == 1\n"
            "    assert sys.flags.ignore_environment == 1\n"
            "    assert sys.flags.no_user_site == 1\n"
            "    assert sys.dont_write_bytecode\n"
            "    assert Path.cwd().name.startswith('skill-sync-tree-')\n"
            "    assert not Path('.git').exists()\n"
            "    assert 'untrusted-operator-bin' not in os.environ['PATH']\n"),
    }

    def mutate(root):
        for relative, text in files.items():
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)

    source_commit(lab, mutate)
    c = core.prepare(lab["publisher"], lab["store"], capture(lab, core))
    review = review_for(c)
    review["files"] = [review_for(c, path=path, quote=text.splitlines()[0])["files"][0]
                       for path, text in files.items()]
    return c, Path(c["worktree"]), review


def test_clean_candidate_uses_real_isolated_pytest_and_can_publish(core, lab, monkeypatch):
    # A changed argv must not misclassify pytest as a trusted wrapper and restore
    # the operator's broader PATH. Candidate imports still use pytest's prepend.
    monkeypatch.setenv("PATH", str(lab["store"] / "untrusted-operator-bin") + os.pathsep + os.environ["PATH"])
    c, w, review = isolated_pytest_candidate(core, lab)
    rows = core.run_checks(c, w)
    row = next(row for row in rows if row["name"] == "package-tests:skills/demo")
    assert row["required"] is True and row["status"] == "passed" and row["exit_code"] == 0, row
    assert "1 passed" in row["stdout"], row
    directory = lab["store"] / "candidates" / c["id"]
    binding = json.loads((directory / "checks-run.json").read_text())
    runner = next(spec for spec in binding["plan"] if spec["name"] == row["name"])
    assert runner["argv"] == [sys.executable, "-I", "-B", "-m", "pytest", "-p", "no:cacheprovider",
                              "-c", "<check-config>/pytest.ini", "--rootdir=skills/demo",
                              "--confcutdir=skills/demo", "skills/demo/tests", "-q"]
    assert runner["pytest_config"] == "[pytest]\n"
    assert runner["conftest_policy"] == "ast-no-module-pytest-bindings-v4"
    assert runner["package"] == "skills/demo"
    assert runner["cwd"] == "<bound-tree>"
    payload = {key: value for key, value in binding.items() if key != "digest"}
    assert binding["digest"] == hashlib.sha256(core.canonical_bytes(payload)).hexdigest()
    validation = core.validate_tree(c, w, review)
    c = core.record_review(lab["store"], c["id"], review, rows, validation)
    assert c["checks_digest"] == binding["digest"]
    assert json.loads((directory / "checks.json").read_text()) == binding
    text = core.render_review(c, review, rows, validation["tree"])
    note = lab["vault"] / c["report_relative_path"]
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(text)
    core.verify_report(c, text, lab["vault"])
    published = core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    assert published["status"] == "published"
    assert g(lab["remote"], "rev-parse", "refs/heads/main^{tree}") == binding["tree"]


@pytest.mark.parametrize("phase", ["record", "publish"])
@pytest.mark.parametrize("changed", ["isolated-startup", "confcutdir", "rootdir", "config-path", "config-bytes"])
def test_changed_pytest_invocation_invalidates_check_evidence(core, lab, monkeypatch, phase, changed):
    c, w, review = isolated_pytest_candidate(core, lab)
    rows = core.run_checks(c, w)
    validation = core.validate_tree(c, w, review)
    filename = "checks-run.json"
    if phase == "publish":
        c = core.record_review(lab["store"], c["id"], review, rows, validation)
        text = core.render_review(c, review, rows, validation["tree"])
        note = lab["vault"] / c["report_relative_path"]
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text(text)
        core.verify_report(c, text, lab["vault"])
        filename = "checks.json"
    target = lab["store"] / "candidates" / c["id"] / filename
    binding = json.loads(target.read_text())
    runner = next(spec for spec in binding["plan"] if spec["name"] == "package-tests:skills/demo")
    if changed == "isolated-startup":
        runner["argv"].remove("-I")
    elif changed == "confcutdir":
        runner["argv"].remove("--confcutdir=skills/demo")
    elif changed == "rootdir":
        runner["argv"].remove("--rootdir=skills/demo")
    elif changed == "config-path":
        runner["argv"][runner["argv"].index("-c") + 1] = "pytest.ini"
    else:
        runner["pytest_config"] = "[pytest]\naddopts = -k nothing\n"
    original_digest = binding.pop("digest")
    binding["digest"] = hashlib.sha256(core.canonical_bytes(binding)).hexdigest()
    assert binding["digest"] != original_digest
    target.write_text(json.dumps(binding))
    calls = record_git_calls(core, monkeypatch)
    with pytest.raises(core.WorkflowError, match="check evidence (plan changed|digest)"):
        if phase == "record":
            core.record_review(lab["store"], c["id"], review, rows, validation)
        else:
            core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    no_publication_writes(calls)
    assert remote_ref(lab["producer"], "refs/heads/main") == c["main_sha"]


@pytest.mark.parametrize("phase", ["record", "publish"])
@pytest.mark.parametrize("changed", ["saved-policy", "missing-policy", "current-policy", "previous-policy"])
def test_changed_conftest_policy_invalidates_check_evidence(core, lab, monkeypatch, phase, changed):
    c, w, review = isolated_pytest_candidate(core, lab)
    rows = core.run_checks(c, w)
    validation = core.validate_tree(c, w, review)
    filename = "checks-run.json"
    if phase == "publish":
        c = core.record_review(lab["store"], c["id"], review, rows, validation)
        text = core.render_review(c, review, rows, validation["tree"])
        note = lab["vault"] / c["report_relative_path"]
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text(text)
        core.verify_report(c, text, lab["vault"])
        filename = "checks.json"
    target = lab["store"] / "candidates" / c["id"] / filename
    binding = json.loads(target.read_text())
    runner = next(spec for spec in binding["plan"] if spec["name"] == "package-tests:skills/demo")
    assert runner["conftest_policy"] == "ast-no-module-pytest-bindings-v4"
    if changed == "current-policy":
        monkeypatch.setattr(core, "CHECK_CONFTEST_POLICY", "changed-runner-control-policy-v2")
    else:
        if changed == "missing-policy":
            del runner["conftest_policy"]
        elif changed == "previous-policy":
            runner["conftest_policy"] = "ast-no-module-pytest-bindings-v1"
        else:
            runner["conftest_policy"] = "old-unrestricted-conftests"
        original_digest = binding.pop("digest")
        binding["digest"] = hashlib.sha256(core.canonical_bytes(binding)).hexdigest()
        assert binding["digest"] != original_digest
        target.write_text(json.dumps(binding))
    calls = record_git_calls(core, monkeypatch)
    with pytest.raises(core.WorkflowError, match="check evidence (plan changed|digest)"):
        if phase == "record":
            core.record_review(lab["store"], c["id"], review, rows, validation)
        else:
            core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    no_publication_writes(calls)
    assert remote_ref(lab["producer"], "refs/heads/main") == c["main_sha"]


@pytest.mark.parametrize("phase", ["record", "publish"])
@pytest.mark.parametrize("previous_policy", ["ast-no-module-pytest-bindings-v1", "ast-no-module-pytest-bindings-v2",
                                            "ast-no-module-pytest-bindings-v3"])
def test_v4_refuses_genuine_previous_policy_evidence(core, lab, monkeypatch, phase, previous_policy):
    c, w, review = isolated_pytest_candidate(core, lab)
    # Produce real, internally consistent earlier-policy evidence, not merely a
    # corrupted field. Restoring v4 must invalidate it at either public gate.
    with monkeypatch.context() as previous:
        previous.setattr(core, "CHECK_CONFTEST_POLICY", previous_policy)
        rows = core.run_checks(c, w)
        validation = core.validate_tree(c, w, review)
        filename = "checks-run.json"
        if phase == "publish":
            c = core.record_review(lab["store"], c["id"], review, rows, validation)
            text = core.render_review(c, review, rows, validation["tree"])
            note = lab["vault"] / c["report_relative_path"]
            note.parent.mkdir(parents=True, exist_ok=True)
            note.write_text(text)
            core.verify_report(c, text, lab["vault"])
            filename = "checks.json"
    assert core.CHECK_CONFTEST_POLICY == "ast-no-module-pytest-bindings-v4"
    evidence = json.loads((lab["store"] / "candidates" / c["id"] / filename).read_text())
    assert all(spec["conftest_policy"] == previous_policy for spec in evidence["plan"]
               if spec.get("execution") == "candidate-tests")
    digest = evidence.pop("digest")
    assert digest == hashlib.sha256(core.canonical_bytes(evidence)).hexdigest()
    calls = record_git_calls(core, monkeypatch)
    with pytest.raises(core.WorkflowError, match="check evidence plan changed"):
        if phase == "record":
            core.record_review(lab["store"], c["id"], review, rows, validation)
        else:
            core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    no_publication_writes(calls)
    assert remote_ref(lab["producer"], "refs/heads/main") == c["main_sha"]


def execute_artifact_test(lab, text):
    """Run actual artifact bytes outside Git and outside the mutable candidate."""
    directory = lab["store"] / "artifact-test"
    directory.mkdir()
    (directory / "test_failure.py").write_text(text)
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", "test_failure.py"],
        cwd=directory, capture_output=True, text=True,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1"))


@pytest.mark.parametrize("bit", ["--skip-worktree", "--assume-unchanged"])
def test_hidden_working_bytes_cannot_certify_published_tree(core, lab, bit):
    path = "skills/demo/tests/test_failure.py"
    failing = "def test_failure():\n    assert False\n"
    source_commit(lab, lambda root: (
        (root / path).parent.mkdir(parents=True), (root / path).write_text(failing)))
    c = core.prepare(lab["publisher"], lab["store"], capture(lab, core))
    w = Path(c["worktree"])
    tree = g(w, "write-tree")
    g(w, "update-index", bit, "--", path)
    (w / path).write_text(failing.replace("assert False", "assert True"))
    # Git porcelain really hides the replacement; this is the review's exact probe.
    assert g(w, "diff", "--", path) == ""
    review = review_for(c, path=path, quote="assert False")
    try:
        rows = core.run_checks(c, w)
    except core.WorkflowError as exc:
        assert "skip-worktree" in str(exc) or "assume-unchanged" in str(exc)
        assert core.load_candidate(lab["store"], c["id"])["status"] == "prepared"
        assert remote_ref(lab["producer"], "refs/heads/main") == c["main_sha"]
        assert not (lab["store"] / "candidates" / c["id"] / "checks-run.json").exists()
        actual = execute_artifact_test(lab, g(w, "show", f"{tree}:{path}") + "\n")
        assert actual.returncode == 1 and "1 failed" in actual.stdout
        return
    row = next(row for row in rows if row["name"] == "package-tests:skills/demo")
    validation = core.validate_tree(c, w, review)
    if row["status"] == "failed":
        with pytest.raises(core.WorkflowError, match="failed.*package-tests"):
            core.record_review(lab["store"], c["id"], review, rows, validation)
        assert remote_ref(lab["producer"], "refs/heads/main") == c["main_sha"]
        return
    c = core.record_review(lab["store"], c["id"], review, rows, validation)
    text = core.render_review(c, review, rows, validation["tree"])
    note = lab["vault"] / c["report_relative_path"]
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(text)
    core.verify_report(c, text, lab["vault"])
    published = core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    actual = execute_artifact_test(lab, g(lab["remote"], "show", f"refs/heads/main:{path}") + "\n")
    assert actual.returncode == row["exit_code"], (
        f"checks={row['status']}/{row['exit_code']}, published pytest={actual.returncode}; "
        f"publication={published['status']}; {actual.stdout}")


@pytest.mark.parametrize("passes", [False, True])
def test_checks_execute_clean_bound_tree_despite_transient_working_bytes(core, lab, monkeypatch, passes):
    path = "skills/demo/tests/test_failure.py"
    staged = f"def test_failure():\n    assert {passes}\n"
    source_commit(lab, lambda root: (
        (root / path).parent.mkdir(parents=True), (root / path).write_text(staged)))
    c = core.prepare(lab["publisher"], lab["store"], capture(lab, core))
    w = Path(c["worktree"])
    real = core._run_check_process
    tested_roots = []

    def change_working_bytes(argv, cwd):
        if "pytest" not in argv:
            return real(argv, cwd)
        # A concurrent editor swaps ONLY working bytes for the duration of pytest,
        # then restores them. Before/after porcelain and index hashes are identical.
        tested_roots.append(Path(cwd))
        (w / path).write_text(staged.replace(f"assert {passes}", f"assert {not passes}"))
        try:
            return real(argv, cwd)
        finally:
            (w / path).write_text(staged)

    monkeypatch.setattr(core, "_run_check_process", change_working_bytes)
    rows = core.run_checks(c, w)
    row = next(row for row in rows if row["name"] == "package-tests:skills/demo")
    assert row["exit_code"] == (0 if passes else 1), row
    assert len(tested_roots) == 1 and tested_roots[0] != w
    assert not tested_roots[0].exists(), "clean materialization leaked after checks"
    binding = json.loads((lab["store"] / "candidates" / c["id"] / "checks-run.json").read_text())
    assert binding["tree"] == g(w, "write-tree")
    review = review_for(c, path=path, quote=f"assert {passes}")
    validation = core.validate_tree(c, w, review)
    if not passes:
        with pytest.raises(core.WorkflowError, match="failed.*package-tests"):
            core.record_review(lab["store"], c["id"], review, rows, validation)
        assert remote_ref(lab["producer"], "refs/heads/main") == c["main_sha"]
        artifact = g(w, "show", f"{binding['tree']}:{path}")
    else:
        c = core.record_review(lab["store"], c["id"], review, rows, validation)
        text = core.render_review(c, review, rows, validation["tree"])
        note = lab["vault"] / c["report_relative_path"]
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text(text)
        core.verify_report(c, text, lab["vault"])
        published = core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
        assert published["status"] == "published"
        artifact = g(lab["remote"], "show", f"refs/heads/main:{path}")
    actual = execute_artifact_test(lab, artifact + "\n")
    assert actual.returncode == row["exit_code"]
    assert ("1 passed" if passes else "1 failed") in actual.stdout


@pytest.mark.parametrize("failure", ["mutation", "timeout"])
def test_clean_check_materialization_is_invalidated_and_cleaned_on_failure(core, lab, monkeypatch, failure):
    path = "skills/demo/tests/test_failure.py"
    text = ("from pathlib import Path\ndef test_changes_its_copy():\n"
            "    p = Path(__file__)\n    p.chmod(0o644)\n"
            "    p.write_text('def test_changed(): pass\\n')\n" if failure == "mutation" else
            "import time\ndef test_slow():\n    time.sleep(10)\n")
    source_commit(lab, lambda root: (
        (root / path).parent.mkdir(parents=True), (root / path).write_text(text)))
    c = core.prepare(lab["publisher"], lab["store"], capture(lab, core))
    w = Path(c["worktree"])
    roots, configs, real = [], [], core._run_check_process
    def observe(argv, cwd):
        if "pytest" in argv:
            roots.append(Path(cwd))
            configs.append(Path(argv[argv.index("-c") + 1]))
        return real(argv, cwd)
    monkeypatch.setattr(core, "_run_check_process", observe)
    monkeypatch.setattr(core, "CHECK_TIMEOUT", 1)
    with pytest.raises(core.WorkflowError, match="materialization|timed out after 1s"):
        core.run_checks(c, w)
    assert len(roots) == 1 and roots[0] != w and not roots[0].exists()
    assert len(configs) == 1 and not configs[0].parent.exists()
    assert (w / path).read_text() == text
    assert not (lab["store"] / "candidates" / c["id"] / "checks-run.json").exists()
    assert remote_ref(lab["producer"], "refs/heads/main") == c["main_sha"]


def test_plan_owned_pytest_config_mutation_invalidates_checks_and_is_cleaned(core, lab, monkeypatch):
    files = {"skills/demo/tests/test_config.py":
             "def test_changes_gate_config(pytestconfig):\n"
             "    pytestconfig.inipath.chmod(0o644)\n"
             "    pytestconfig.inipath.write_text('[pytest]\\naddopts = -k nothing\\n')\n"}
    c, w, _review = pytest_control_candidate(core, lab, files)
    configs, real = [], core._run_check_process
    def observe(argv, cwd):
        if "pytest" in argv:
            configs.append(Path(argv[argv.index("-c") + 1]))
        return real(argv, cwd)
    monkeypatch.setattr(core, "_run_check_process", observe)
    with pytest.raises(core.WorkflowError, match="changed the plan-owned pytest configuration"):
        core.run_checks(c, w)
    assert len(configs) == 1 and not configs[0].parent.exists()
    assert not (lab["store"] / "candidates" / c["id"] / "checks-run.json").exists()
    assert core.load_candidate(lab["store"], c["id"])["status"] == "prepared"
    assert remote_ref(lab["producer"], "refs/heads/main") == c["main_sha"]


def test_check_materialization_uses_raw_tree_blobs_not_archive_attributes(core, lab):
    def mutate(root):
        (root / ".gitattributes").write_text(
            "skills/demo/tests/* export-ignore\nskills/demo/raw.txt export-subst whitespace=cr-at-eol\n")
        (root / "skills/demo/raw.txt").write_bytes(b"$Format:%H$\r\n")
        executable = root / "skills/demo/probe.sh"
        executable.write_bytes(b"#!/bin/sh\nexit 0\n")
        executable.chmod(0o755)
        tests = root / "skills/demo/tests"
        tests.mkdir()
        (tests / "test_raw.py").write_text(
            "from pathlib import Path\ndef test_exact_raw_bytes():\n"
            "    assert Path('skills/demo/raw.txt').read_bytes() == b'$Format:%H$\\r\\n'\n"
            "    assert Path('skills/demo/probe.sh').stat().st_mode & 0o111\n"
            "    assert not Path('skills/demo/raw.txt').stat().st_mode & 0o222\n"
            "    assert not Path('.git').exists()\n")
    source_commit(lab, mutate)
    c = core.prepare(lab["publisher"], lab["store"], capture(lab, core))
    rows = core.run_checks(c, Path(c["worktree"]))
    row = next(row for row in rows if row["name"] == "package-tests:skills/demo")
    assert row["status"] == "passed" and "1 passed" in row["stdout"]


@pytest.mark.parametrize("bit", ["--skip-worktree", "--assume-unchanged"])
@pytest.mark.parametrize("phase", ["during-checks", "during-validation", "validate", "record", "publish"])
def test_index_visibility_flags_refused_at_every_gate(core, lab, monkeypatch, bit, phase):
    offer(lab)
    c = core.prepare(lab["publisher"], lab["store"], capture(lab, core))
    w, path = Path(c["worktree"]), "skills/demo/SKILL.md"
    review = review_for(c)
    if phase == "during-checks":
        real = core._run_check_process
        def add_flag(argv, cwd):
            result = real(argv, cwd)
            g(w, "update-index", bit, "--", path)
            return result
        monkeypatch.setattr(core, "_run_check_process", add_flag)
        action = lambda: core.run_checks(c, w)
    else:
        rows = core.run_checks(c, w)
        validation = core.validate_tree(c, w, review)
        if phase == "publish":
            c = core.record_review(lab["store"], c["id"], review, rows, validation)
            text = core.render_review(c, review, rows, validation["tree"])
            note = lab["vault"] / c["report_relative_path"]
            note.parent.mkdir(parents=True, exist_ok=True)
            note.write_text(text)
            core.verify_report(c, text, lab["vault"])
        if phase == "during-validation":
            real_syntax = core._validate_staged_blobs
            def flag_during_validation(*args):
                result = real_syntax(*args)
                g(w, "update-index", bit, "--", path)
                return result
            monkeypatch.setattr(core, "_validate_staged_blobs", flag_during_validation)
        else:
            g(w, "update-index", bit, "--", path)
        action = {"during-validation": lambda: core.validate_tree(c, w, review),
                  "validate": lambda: core.validate_tree(c, w, review),
                  "record": lambda: core.record_review(lab["store"], c["id"], review, rows, validation),
                  "publish": lambda: core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])}[phase]
    with pytest.raises(core.WorkflowError, match="skip-worktree|assume-unchanged"):
        action()
    assert remote_ref(lab["producer"], "refs/heads/main") == c["main_sha"]
    if phase == "during-checks":
        assert not (lab["store"] / "candidates" / c["id"] / "checks-run.json").exists()


def test_stale_green_checks_cannot_authorize_revalidated_failing_tree(core, lab):
    """Recomputing validate_tree alone must not rebind yesterday's green checks."""
    c, w, review = failing_package_candidate(core, lab)
    path = "skills/skill-library-maintenance/tests/test_deliberate_failure.py"
    target = w / path
    failing = target.read_text(encoding="utf-8")
    target.write_text(failing.replace("assert 1 == 2", "assert 1 == 1"), encoding="utf-8")
    g(w, "add", "--", path)
    checks = core.run_checks(c, w)
    assert all(row["status"] == "passed" for row in checks if row["required"])
    checked_tree = g(w, "write-tree")

    target.write_text(failing, encoding="utf-8")
    g(w, "add", "--", path)
    validation = core.validate_tree(c, w, review)
    assert validation["tree"] != checked_tree  # syntax/coverage pass, pytest does not
    actual = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider",
         "skills/skill-library-maintenance/tests", "-q"], cwd=w,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), capture_output=True, text=True)
    assert actual.returncode == 1 and "1 failed" in actual.stdout
    with pytest.raises(core.WorkflowError, match="check.*tree|tree.*check"):
        core.record_review(lab["store"], c["id"], review, checks, validation)
    assert core.load_candidate(lab["store"], c["id"])["status"] == "prepared"
    assert remote_ref(lab["producer"], "refs/heads/main") == c["main_sha"]


@pytest.mark.parametrize("changed", ["missing-run", "forged-rows"])
def test_record_review_requires_authoritative_check_evidence(core, lab, changed):
    offer(lab)
    c = core.prepare(lab["publisher"], lab["store"], capture(lab, core))
    w, review = Path(c["worktree"]), review_for(c)
    rows = core.run_checks(c, w)
    binding_path = lab["store"] / "candidates" / c["id"] / "checks-run.json"
    if changed == "missing-run":
        binding_path.unlink(missing_ok=True)
    else:
        rows[0]["stdout"] = "A caller-supplied green claim"
    with pytest.raises(core.WorkflowError, match="check.*(binding|evidence)"):
        core.record_review(lab["store"], c["id"], review, rows,
                           core.validate_tree(c, w, review))
    assert core.load_candidate(lab["store"], c["id"])["status"] == "prepared"


def test_checks_bind_exact_tree_plan_and_rows_across_restart(core, lab):
    offer(lab)
    c = core.prepare(lab["publisher"], lab["store"], capture(lab, core))
    w, review = Path(c["worktree"]), review_for(c)
    rows = core.run_checks(c, w)
    directory = lab["store"] / "candidates" / c["id"]
    binding = json.loads((directory / "checks-run.json").read_text(encoding="utf-8"))
    assert set(binding) == {"schema", "candidate_id", "tree", "plan", "checks", "digest"}
    assert binding["schema"] == 1 and binding["candidate_id"] == c["id"]
    assert binding["tree"] == g(w, "write-tree") and binding["checks"] == rows
    assert [item["name"] for item in binding["plan"]] == [row["name"] for row in rows]
    assert binding["plan"][0]["argv"] == ["git", "diff", "--cached", "--check"]
    payload = {key: value for key, value in binding.items() if key != "digest"}
    assert binding["digest"] == hashlib.sha256(core.canonical_bytes(payload)).hexdigest()
    fresh = load_core()
    recorded = fresh.record_review(lab["store"], c["id"], review, rows,
                                   fresh.validate_tree(c, w, review))
    assert recorded["checks_digest"] == binding["digest"]
    assert json.loads((directory / "checks.json").read_text(encoding="utf-8")) == binding


@pytest.mark.parametrize("changed", ["binding", "tree", "plan", "rows"])
def test_publish_requires_untampered_recorded_check_binding(core, lab, monkeypatch, changed):
    offer(lab)
    c = reviewed(core, lab)
    target = lab["store"] / "candidates" / c["id"] / "checks.json"
    evidence = json.loads(target.read_text(encoding="utf-8"))
    if changed == "binding":
        evidence.pop("digest", None)
    elif changed == "tree":
        evidence["tree"] = g(lab["publisher"], "rev-parse", f"{c['main_sha']}^{{tree}}")
    elif changed == "plan":
        evidence["plan"] = []
    else:
        evidence["checks"][0]["stdout"] = "A substituted green row"
    target.write_text(json.dumps(evidence), encoding="utf-8")
    calls = record_git_calls(core, monkeypatch)
    with pytest.raises(core.WorkflowError, match="check.*(binding|digest)"):
        core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    no_publication_writes(calls)
    assert remote_ref(lab["producer"], "refs/heads/main") == c["main_sha"]


def test_missing_previously_required_runner_is_an_error(core, lab, tmp_path):
    publish_files(lab, {
        "skills/skill-library-maintenance/tests/test_package_ok.py":
            ("def test_package_works():\n    assert True\n", None),
    })
    path = "skills/skill-library-maintenance/tests/test_package_ok.py"
    source_commit(lab, lambda root: (root / path).unlink(),
                  "delete the only package test runner")
    c = capture(lab, core)
    c = core.prepare(lab["publisher"], lab["store"], c)
    w = Path(c["worktree"])
    review = review_for(c, path=path, quote="def test_package_works():",
                        change_type="unsuitable", reason="Remove the package test runner",
                        anchors=[{"ref": c["main_sha"], "path": path,
                                  "quote": "def test_package_works():"}])
    core.validate_review(c, review, lab["publisher"], w)
    with pytest.raises(core.WorkflowError) as excinfo:
        core.run_checks(c, w)
    assert "disappeared" in str(excinfo.value)
    assert "skills/skill-library-maintenance/tests" in str(excinfo.value)

    # A package that never configured a runner is honestly not-applicable.
    fresh = build_lab(tmp_path / "fresh")
    publish_files(fresh, {"skills/skill-library-maintenance/SKILL.md":
                          ("---\nname: skill-library-maintenance\ndescription: M.\n---\n\n"
                           "# Maintenance\n", None)})
    source_commit(fresh, lambda root: replace_text(
        root / "skills/skill-library-maintenance/SKILL.md", "# Maintenance\n",
        "# Maintenance\n\nA generic rule.\n"), "edit the package without a runner")
    other = core.capture(fresh["publisher"], fresh["store"], fresh["source"])
    other = core.prepare(fresh["publisher"], fresh["store"], other)
    rows = core.run_checks(other, Path(other["worktree"]))
    package_row = {row["name"]: row for row in rows}[
        "package-tests:skills/skill-library-maintenance"]
    assert package_row["status"] == "not-applicable"
    assert package_row["required"] is False and package_row["exit_code"] is None
    assert "no runner is configured" in package_row["stderr"]


def test_run_checks_dispatches_fixed_allowlisted_commands(core, lab, monkeypatch):
    c, w, _review = failing_package_candidate(core, lab)
    calls = []

    def fake(argv, cwd):
        calls.append((list(argv), str(cwd)))
        if "pytest" in argv:
            assert Path(cwd) != w.resolve()
            assert not (Path(cwd) / ".git").exists()
            assert not (Path(cwd).stat().st_mode & 0o222)
            test_file = Path(cwd) / "skills/skill-library-maintenance/tests/test_deliberate_failure.py"
            assert "assert 1 == 2" in test_file.read_text()
            assert not (test_file.stat().st_mode & 0o222)
            config = Path(argv[argv.index("-c") + 1])
            assert config.is_absolute() and config.parent != Path(cwd)
            assert config.read_text() == "[pytest]\n"
            assert not (config.stat().st_mode & 0o222)
        return subprocess.CompletedProcess(list(argv), 0, "49 passed\n", "")

    monkeypatch.setattr(core, "_run_check_process", fake)
    rows = core.run_checks(c, w)
    package_calls = [call for call in calls if "pytest" in call[0]]
    assert len(package_calls) == 1
    argv, cwd = package_calls[0]
    config_path = argv[argv.index("-c") + 1]
    assert argv == [sys.executable, "-I", "-B", "-m", "pytest", "-p", "no:cacheprovider",
                    "-c", config_path, "--rootdir=skills/skill-library-maintenance",
                    "--confcutdir=skills/skill-library-maintenance",
                    "skills/skill-library-maintenance/tests", "-q"]
    assert Path(config_path).name == "pytest.ini"
    assert Path(config_path).parent.name.startswith("skill-sync-pytest-")
    assert not Path(config_path).parent.exists()
    assert Path(cwd) != w.resolve()
    assert Path(cwd).name.startswith("skill-sync-tree-")
    assert not Path(cwd).exists()
    assert all(isinstance(argument, str) for argument in argv)
    by_name = {row["name"]: row for row in rows}
    passed = by_name["package-tests:skills/skill-library-maintenance"]
    assert passed["status"] == "passed" and passed["exit_code"] == 0
    assert passed["required"] is True and passed["stdout"] == "49 passed\n"

    # A non-zero process result is recorded as failed evidence, never a flag.
    monkeypatch.setattr(core, "_run_check_process",
                        lambda argv, cwd: subprocess.CompletedProcess(list(argv), 1, "", "boom"))
    failed = {row["name"]: row for row in core.run_checks(c, w)}[
        "package-tests:skills/skill-library-maintenance"]
    assert failed["status"] == "failed" and failed["exit_code"] == 1
    assert failed["stderr"] == "boom"
    env = core._check_env()
    assert env["PYTHONDONTWRITEBYTECODE"] == "1"
    assert "PYTEST_ADDOPTS" not in env


@pytest.mark.parametrize("tool", ["audit", "validator"])
def test_validation_uses_trusted_tools_and_isolates_candidate_tests(core, lab, monkeypatch, tool):
    audit = "skills/skill-library-maintenance/scripts/audit-skill-library.py"
    validator = "skills/skill-builder/scripts/skills-ref.sh"
    test = "skills/skill-library-maintenance/tests/test_isolation.py"
    publish_files(lab, {
        audit: ("import sys\nprint('trusted audit', sys.argv[1])\n", None),
        validator: ("#!/bin/sh\nprintf 'trusted validator %s\\n' \"$2\"\n", 0o755),
    })
    g(lab["publisher"], "fetch", "-q", "origin")
    g(lab["publisher"], "merge", "-q", "--ff-only", "origin/main")
    sentinel = lab["store"] / "candidate-tool-executed"
    live = lab["store"] / "live-profile"
    live.mkdir()
    (live / "config.yaml").write_text("private fixture config\n")
    monkeypatch.setenv("HERMES_HOME", str(live))
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-only-not-a-real-key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fixture-only-not-a-real-key")
    monkeypatch.setenv("PYTEST_ADDOPTS", "--unknown-inherited-option")
    selected = audit if tool == "audit" else validator
    replacement = (f"from pathlib import Path\nPath({str(sentinel)!r}).touch()\n"
                   if tool == "audit" else f"#!/bin/sh\ntouch '{sentinel}'\n")
    isolation_test = (
        "import os\nfrom pathlib import Path\n"
        "def test_candidate_suite_runs_isolated():\n"
        "    assert Path.cwd().name.startswith('skill-sync-tree-')\n"
        f"    assert Path.cwd().parent != Path({str(lab['store'] / 'worktrees')!r})\n"
        "    assert not (Path.cwd() / '.git').exists()\n"
        "    assert not (Path.cwd().stat().st_mode & 0o222)\n"
        "    assert (Path.cwd() / 'skills/skill-library-maintenance/tests/test_isolation.py').is_file()\n"
        "    assert 'OPENAI_API_KEY' not in os.environ\n"
        "    assert 'AWS_SECRET_ACCESS_KEY' not in os.environ\n"
        "    assert 'PYTEST_ADDOPTS' not in os.environ\n"
        f"    assert os.environ.get('HERMES_HOME') != {str(live)!r}\n"
        "    assert not (Path.home() / 'config.yaml').exists()\n"
        "    assert not (Path(os.environ['HERMES_HOME']) / 'config.yaml').exists()\n"
    )
    source_commit(lab, lambda root: (
        (root / selected).write_text(replacement),
        (root / test).parent.mkdir(parents=True, exist_ok=True),
        (root / test).write_text(isolation_test),
    ))
    c = core.prepare(lab["publisher"], lab["store"], capture(lab, core))
    rows = {row["name"]: row for row in core.run_checks(c, Path(c["worktree"]))}
    assert not sentinel.exists(), "candidate-supplied validation tooling executed before review"
    assert rows["library-audit"]["status"] == "passed"
    assert "trusted audit" in rows["library-audit"]["stdout"]
    assert rows["package-validator:skills/skill-library-maintenance"]["status"] == "passed"
    assert "trusted validator" in rows["package-validator:skills/skill-library-maintenance"]["stdout"]
    assert rows["package-tests:skills/skill-library-maintenance"]["status"] == "passed"
    assert "1 passed" in rows["package-tests:skills/skill-library-maintenance"]["stdout"]
    assert core.load_candidate(lab["store"], c["id"])["status"] == "prepared"


def test_candidate_tool_without_trusted_implementation_is_a_required_failure(core, lab):
    sentinel = lab["store"] / "untrusted-only-tool-executed"
    path = "skills/skill-library-maintenance/scripts/audit-skill-library.py"
    commit(lab["producer"], f"from pathlib import Path\nPath({str(sentinel)!r}).touch()\n", path=path)
    g(lab["producer"], "push", "-q", "origin", "machine/testlab")
    c = core.prepare(lab["publisher"], lab["store"], capture(lab, core))
    row = {r["name"]: r for r in core.run_checks(c, Path(c["worktree"]))}["library-audit"]
    assert row["required"] is True and row["status"] == "failed" and row["exit_code"] == 127
    assert "missing from trusted publisher" in row["stderr"]
    assert not sentinel.exists()


def test_candidate_test_execution_has_a_bounded_timeout(core, lab, monkeypatch):
    path = "skills/demo/tests/test_slow.py"
    commit(lab["producer"], "import time\ndef test_slow():\n    time.sleep(10)\n", path=path)
    g(lab["producer"], "push", "-q", "origin", "machine/testlab")
    c = core.prepare(lab["publisher"], lab["store"], capture(lab, core))
    monkeypatch.setattr(core, "CHECK_TIMEOUT", 1)
    with pytest.raises(core.WorkflowError, match="timed out after 1s"):
        core.run_checks(c, Path(c["worktree"]))
    assert not (lab["store"] / "candidates" / c["id"] / "checks-run.json").exists()
    assert core.load_candidate(lab["store"], c["id"])["status"] == "prepared"


def test_checks_are_invalidated_by_a_changed_candidate(core, lab):
    offer(lab)
    c = capture(lab, core)
    c = core.prepare(lab["publisher"], lab["store"], c)
    w = Path(c["worktree"])
    review = review_for(c)
    core.validate_review(c, review, lab["publisher"], w)
    checks = core.run_checks(c, w)
    validation = core.validate_tree(c, w, review)

    with (w / "skills/demo/SKILL.md").open("a", encoding="utf-8") as handle:
        handle.write("A late addition.\n")
    g(w, "add", "--", "skills/demo/SKILL.md")
    with pytest.raises(core.WorkflowError) as excinfo:
        core.record_review(lab["store"], c["id"], review, checks, validation)
    assert "tree" in str(excinfo.value)
    assert core.load_candidate(lab["store"], c["id"])["status"] == "prepared"

    # An untracked file after the checks is also a changed artifact.
    fresh = core.load_candidate(lab["store"], c["id"])
    scratch = w / "skills/demo/late.md"
    scratch.write_text("late\n", encoding="utf-8")
    with pytest.raises(core.WorkflowError) as excinfo:
        core.record_review(lab["store"], c["id"], review, checks, validation)
    assert "untracked" in str(excinfo.value)
    assert fresh["status"] == "prepared"


# ---------------------------------------------------------------------------
# C4: deterministic report rendering and exact file read-back.
# ---------------------------------------------------------------------------

def reviewed(core, lab):
    c=core.capture(lab["publisher"],lab["store"],lab["source"])
    c=core.prepare(lab["publisher"],lab["store"],c)
    w=Path(c["worktree"])
    r={"schema":1,"candidate_id":c["id"],"main_sha":c["main_sha"],"source_sha":c["source_sha"],
       "summary":"Accept a useful generic addition",
       "files":[{"path":"skills/demo/SKILL.md","change_type":"addition","decision":"accept",
                 "source_anchors":[{"ref":c["source_sha"],"path":"skills/demo/SKILL.md","quote":"A useful generic rule."}],
                 "reason":"Useful generic addition","replacements":[]}]}
    core.validate_review(c,r,lab["publisher"],w)
    checks=core.run_checks(c,w)
    v=core.validate_tree(c,w,r)
    # Implementation must persist normalized review/checks/tree in this API call:
    core.record_review(lab["store"],c["id"],r,checks,v)
    c=core.load_candidate(lab["store"],c["id"])
    text=core.render_review(c,r,checks,v["tree"])
    # TEST ADAPTER ONLY; live run writes these bytes with TurboVault.
    target=lab["vault"] / c["report_relative_path"]
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(text,encoding="utf-8")
    core.verify_report(c,text,lab["vault"])
    return core.load_candidate(lab["store"],c["id"])


def test_report_binds_inputs_review_and_tree(core, lab, monkeypatch):
    offer(lab)
    candidate = reviewed(core, lab)
    assert candidate["status"] == "report-verified"
    assert candidate["report_relative_path"] == (
        f"projects/hermes-agent/reports/skill-sync-{candidate['id']}-review.md")
    target = lab["vault"] / candidate["report_relative_path"]
    assert target.is_file()
    text = target.read_text(encoding="utf-8")

    # The report binds M, T, the reviewed tree, the candidate, reasons and checks.
    for expected in (candidate["main_sha"], candidate["source_sha"],
                     candidate["reviewed_tree"], candidate["id"], candidate["created_at"],
                     "Accept a useful generic addition", "Useful generic addition",
                     "A useful generic rule.", "skills/demo/SKILL.md"):
        assert expected in text, expected
    assert "passed" in text and "not applicable" in text
    # The note is a real vault note: project tag plus the local reports hub in
    # frontmatter topics and the mirrored footer. Usage fields are explicit.
    assert "project/hermes-agent" in text
    assert text.count("[[projects/hermes-agent/reports/+reports]]") == 2
    assert "Topics:" in text
    assert "measured" in text and "unavailable" in text and "not a token" in text
    assert "approve" not in text.lower() and "approval" not in text.lower()
    assert "sign-off" in text and text.endswith("\n")

    state_dir = lab["store"] / "candidates" / candidate["id"]
    stored_review = json.loads((state_dir / "review.json").read_text(encoding="utf-8"))
    stored_checks = json.loads((state_dir / "checks.json").read_text(encoding="utf-8"))["checks"]
    first = core.render_review(candidate, stored_review, stored_checks, candidate["reviewed_tree"])
    second = core.render_review(candidate, stored_review, stored_checks, candidate["reviewed_tree"])
    assert first == second == text
    assert (state_dir / "review.md").read_text(encoding="utf-8") == text
    assert candidate["report_sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()

    # Rendering never consults the wall clock: the timestamp is the captured one.
    monkeypatch.setattr(core, "_utc_now", lambda: "1999-01-01T00:00:00Z")
    assert core.render_review(candidate, stored_review, stored_checks,
                              candidate["reviewed_tree"]) == text
    assert "1999-01-01" not in text

    # A changed note is refused, not silently accepted.
    target.write_text(text + " ", encoding="utf-8")
    with pytest.raises(core.WorkflowError) as excinfo:
        core.verify_report(candidate, text, lab["vault"])
    assert "does not match" in str(excinfo.value)
    target.unlink()
    with pytest.raises(core.WorkflowError) as excinfo:
        core.verify_report(candidate, text, lab["vault"])
    assert "missing" in str(excinfo.value)

    # A note that resolves outside the configured root is refused.
    target.write_text(text, encoding="utf-8")
    outside = lab["vault"].parent / "outside-note.md"
    outside.write_text(text, encoding="utf-8")
    target.unlink()
    target.symlink_to(outside)
    with pytest.raises(core.WorkflowError) as excinfo:
        core.verify_report(candidate, text, lab["vault"])
    assert "escapes" in str(excinfo.value) or "symlink" in str(excinfo.value)
    target.unlink()
    target.write_text(text, encoding="utf-8")

    assert core.verify_report(candidate, text, lab["vault"])["status"] == "report-verified"
    with pytest.raises(core.WorkflowError):
        core.verify_report(candidate, text + "extra", lab["vault"])


def test_report_payload_is_not_written_to_the_vault(core, lab):
    offer(lab)
    c = capture(lab, core)
    c = core.prepare(lab["publisher"], lab["store"], c)
    w = Path(c["worktree"])
    review = review_for(c)
    core.validate_review(c, review, lab["publisher"], w)
    checks = core.run_checks(c, w)
    validation = core.validate_tree(c, w, review)
    with pytest.raises(core.WorkflowError):
        core.verify_report(c, "not rendered yet", lab["vault"])
    c = core.record_review(lab["store"], c["id"], review, checks, validation)
    text = core.render_review(c, review, checks, validation["tree"])

    # Python saves the payload under the candidate store only.
    note = lab["vault"] / c["report_relative_path"]
    assert not note.exists()
    assert (lab["store"] / "candidates" / c["id"] / "review.md").read_text(
        encoding="utf-8") == text

    # The test writes the note itself, exactly as the live TurboVault step would.
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(text, encoding="utf-8")
    verified = core.verify_report(c, text, lab["vault"])
    assert verified["status"] == "report-verified"

    other = lab["vault"].parent / "other-root"
    other.mkdir()
    with pytest.raises(core.WorkflowError) as excinfo:
        core.verify_report(verified, text, other)
    assert "configured" in str(excinfo.value)


# ---------------------------------------------------------------------------
# B7: one publisher lock, keyed to the Git common dir and owned by a token.
# ---------------------------------------------------------------------------

def _git_common(repo):
    return Path(g(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))


def _write_store_config(source_store, target_store, publisher_repo):
    target_store.mkdir(parents=True)
    config = json.loads((source_store / "publisher.json").read_text(encoding="utf-8"))
    config["publisher_repo"] = str(publisher_repo)
    (target_store / "publisher.json").write_text(json.dumps(config), encoding="utf-8")


def test_publisher_lock_is_owned_and_never_age_broken(core, lab):
    common = _git_common(lab["publisher"])
    expected = common / "hermes-sync" / "publisher.lock"
    assert core.publisher_lock_path(lab["store"]) == expected

    token = core.acquire_publisher_lock(lab["store"])
    assert expected.is_file()
    record = json.loads(expected.read_text(encoding="utf-8"))
    assert record["token"] == token
    assert record["pid"] == os.getpid()
    assert record["host"] and record["acquired_at"]

    # A second acquisition refuses and names the owner; nothing is overwritten.
    with pytest.raises(core.WorkflowError) as excinfo:
        core.acquire_publisher_lock(lab["store"])
    assert token in str(excinfo.value)

    # Only the matching owner token may release the lock.
    with pytest.raises(core.WorkflowError) as excinfo:
        core.release_publisher_lock(lab["store"], "0" * 64)
    assert expected.is_file()

    # Backdating both the file metadata and the recorded acquisition time is
    # still not evidence of death: no age expiry, no TTL override.
    record["acquired_at"] = "1970-01-01T00:00:00Z"
    expected.write_text(json.dumps(record), encoding="utf-8")
    os.utime(expected, (1, 1))
    with pytest.raises(core.WorkflowError):
        core.acquire_publisher_lock(lab["store"])
    assert expected.is_file()

    core.release_publisher_lock(lab["store"], token)
    assert not expected.exists()
    with pytest.raises(core.WorkflowError):
        core.release_publisher_lock(lab["store"], token)


def test_linked_worktrees_and_alternate_stores_share_publisher_lock(core, lab, tmp_path):
    linked_a = tmp_path / "publisher-linked-a"
    linked_b = tmp_path / "publisher-linked-b"
    g(lab["publisher"], "worktree", "add", "-q", "--detach", str(linked_a), "HEAD")
    g(lab["publisher"], "worktree", "add", "-q", "--detach", str(linked_b), "HEAD")
    store_a = tmp_path / "state-linked-a"
    store_b = tmp_path / "state-linked-b"
    _write_store_config(lab["store"], store_a, linked_a)
    _write_store_config(lab["store"], store_b, linked_b)

    # Different store paths and different per-worktree gitdirs, one common lock.
    expected = _git_common(lab["publisher"]) / "hermes-sync" / "publisher.lock"
    assert core.publisher_lock_path(store_a) == expected
    assert core.publisher_lock_path(store_b) == expected
    gitdir_a = Path(g(linked_a, "rev-parse", "--git-dir"))
    gitdir_b = Path(g(linked_b, "rev-parse", "--git-dir"))
    assert gitdir_a != gitdir_b

    token = core.acquire_publisher_lock(store_a)
    with pytest.raises(core.WorkflowError) as excinfo:
        core.acquire_publisher_lock(store_b)
    assert token in str(excinfo.value)
    core.release_publisher_lock(store_a, token)

    # A separate producer clone is a different repository and stays writable.
    assert _git_common(lab["producer"]) != _git_common(lab["publisher"])
    tip = commit(lab["producer"], "---\nname: demo\ndescription: Demonstration skill.\n---\n\n"
                 "# Demo\n\nBase instruction.\nProducer-only work.\n")
    g(lab["producer"], "push", "-q", "origin", "machine/testlab")
    remote = g(lab["producer"], "ls-remote", "origin", "refs/heads/machine/testlab")
    assert remote.split()[0] == tip


def test_publisher_lock_resolves_a_relative_git_common_dir(core, lab, monkeypatch):
    """Old Git without --path-format answers relative to the repo root."""
    real_git = core.git

    def old_git(repo, *args, **kwargs):
        if args[:2] == ("rev-parse", "--path-format=absolute"):
            return subprocess.CompletedProcess(
                ["git"], 129, "", "error: unknown option `path-format'")
        if args == ("rev-parse", "--git-common-dir"):
            return subprocess.CompletedProcess(["git"], 0, ".git\n", "")
        return real_git(repo, *args, **kwargs)

    monkeypatch.setattr(core, "git", old_git)
    assert core.publisher_lock_path(lab["store"]) == (
        _git_common(lab["publisher"]) / "hermes-sync" / "publisher.lock")


def test_producer_lock_lives_in_repo_common_dir_and_owns_its_token(core, lab, tmp_path):
    """The producer lock is separate from the publisher lock and shared by linked worktrees."""
    common = _git_common(lab["producer"])
    expected = common / "hermes-sync" / "producer.lock"
    assert core.producer_lock_path(lab["producer"]) == expected
    assert expected != core.publisher_lock_path(lab["store"])

    linked = tmp_path / "producer-linked"
    g(lab["producer"], "worktree", "add", "-q", "--detach", str(linked), "HEAD")
    assert core.producer_lock_path(linked) == expected

    token = core.acquire_producer_lock(lab["producer"])
    assert expected.is_file()
    record = core.read_producer_lock(linked)
    assert record["token"] == token and record["pid"] == os.getpid()
    with pytest.raises(core.WorkflowError) as excinfo:
        core.acquire_producer_lock(linked)
    assert token in str(excinfo.value)
    with pytest.raises(core.WorkflowError):
        core.release_producer_lock(lab["producer"], "0" * 64)
    assert expected.is_file()
    core.release_producer_lock(linked, token)
    assert not expected.exists()
    with pytest.raises(core.WorkflowError):
        core.release_producer_lock(lab["producer"], token)


def test_source_history_screen_reports_removed_exposure_without_values(core, lab):
    """An intermediate commit's prohibited content is found; no matched value is returned."""
    producer = lab["producer"]
    synthetic_value = "SYNTHETIC_FIXTURE_VALUE_NOT_A_REAL_CREDENTIAL_0002"
    added = commit(producer, f"DEMO_API_KEY={synthetic_value}\n", message="fixture env",
                  path=".env")
    exposed = commit(producer, "A clean-looking rule.\n", message="clean lesson")
    # Remove the file again: the final tree is clean, the history is not.
    (producer / ".env").unlink()
    g(producer, "add", "-A")
    g(producer, "commit", "-q", "-m", "remove fixture")
    tip = g(producer, "rev-parse", "HEAD")
    assert ".env" not in g(producer, "ls-tree", "-r", "--name-only", tip).split()

    result = core.screen_source_history(producer, tip, lab["base"])
    assert result["tip"] == tip and result["base_tip"] == lab["base"]
    assert result["commits"] == [added, exposed, tip]
    categories = {finding["category"] for finding in result["findings"]}
    assert categories == {"forbidden-path", "credential-pattern"}
    assert {".env"} <= {finding["path"] for finding in result["findings"]}
    dumped = json.dumps(result)
    assert synthetic_value not in dumped and "DEMO_API_KEY" not in dumped
    assert all(set(finding) == {"commit", "path", "category", "reason"}
               for finding in result["findings"])

    # A clean range has no findings.
    clean = core.screen_source_history(producer, lab["base"])
    assert clean["findings"] == [] and clean["commits"]

    # A conflict-resolution merge can introduce content that exists in neither
    # parent; the --cc combined diff is screened for exactly that.
    g(producer, "checkout", "-q", "-b", "conflict-side", lab["base"])
    commit(producer, "conflict side line\n", message="side line")
    g(producer, "checkout", "-q", "machine/testlab")
    commit(producer, "conflict machine line\n", message="machine line")
    merge_probe = subprocess.run(["git", "-C", str(producer), "merge", "conflict-side"],
                                 capture_output=True, text=True)
    assert merge_probe.returncode != 0
    resolved = producer / "skills/demo/SKILL.md"
    resolved.write_text(f"DEMO_API_KEY={synthetic_value}\n", encoding="utf-8")
    g(producer, "add", "--", "skills/demo/SKILL.md")
    g(producer, "commit", "-q", "-m", "resolve with synthetic content")
    merge = g(producer, "rev-parse", "HEAD")
    assert len(g(producer, "show", "-s", "--format=%P", merge).split()) == 2
    merge_screen = core.screen_source_history(producer, merge, lab["base"])
    assert any(finding["commit"] == merge and finding["category"] == "credential-pattern"
               for finding in merge_screen["findings"])
    assert synthetic_value not in json.dumps(merge_screen)

    # The digest binds tip, scope and the exact commit rows.
    payload = {"schema": 1, "tip": tip, "scope": "shared-generic",
               "commits": [{"sha": added, "classification": "generic-only",
                            "reason": "Reviewed."}]}
    digest = core.history_review_digest(payload)
    assert len(digest) == 64 and digest == core.history_review_digest(dict(payload))
    assert digest != core.history_review_digest({**payload, "tip": exposed})
    with pytest.raises(core.WorkflowError):
        core.history_review_digest({**payload, "commits": [
            {"sha": added, "classification": "looks-fine", "reason": "nope"}]})


# ---------------------------------------------------------------------------
# D: exact merge publication (packet 07).
#
# Every case publishes through core.publish() against the local bare remote;
# none of them builds the integration merge with `git merge` in the test.
# ---------------------------------------------------------------------------

BASE_TEXT = ("---\nname: demo\ndescription: Demonstration skill.\n---\n\n"
             "# Demo\n\nBase instruction.\n")
OFFER_TEXT = BASE_TEXT + "A useful generic rule.\n"


def record_full_review(core, lab, candidate, review=None):
    """Record a review for a prepared candidate and deliver its report note.

    The same steps as the C5 helper, but for a candidate prepared by the test
    (empty-diff, reject-only, or a recapture after main moved).
    """
    worktree = Path(candidate["worktree"])
    review = review if review is not None else review_for(candidate)
    core.validate_review(candidate, review, lab["publisher"], worktree)
    checks = core.run_checks(candidate, worktree)
    validation = core.validate_tree(candidate, worktree, review)
    core.record_review(lab["store"], candidate["id"], review, checks, validation)
    current = core.load_candidate(lab["store"], candidate["id"])
    text = core.render_review(current, review, checks, validation["tree"])
    note = lab["vault"] / current["report_relative_path"]
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(text, encoding="utf-8")
    core.verify_report(current, text, lab["vault"])
    return core.load_candidate(lab["store"], candidate["id"])


def second_main_clone(lab, tmp_path, name="second"):
    """An independent clone that can advance main without touching the lab."""
    clone = tmp_path / name
    subprocess.run(["git", "clone", "-q", "-b", "main", str(lab["remote"]), str(clone)],
                   check=True)
    for key, value in (("user.name", "Second"), ("user.email", "second@example.invalid")):
        g(clone, "config", key, value)
    return clone


def independent_main_commit(clone, path="docs/independent.md"):
    target = clone / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("Independent main work.\n", encoding="utf-8")
    g(clone, "add", "--", path)
    g(clone, "commit", "-q", "-m", "independent main work")
    g(clone, "push", "-q", "origin", "main")
    return g(clone, "rev-parse", "HEAD")


def record_git_calls(core, monkeypatch):
    """Record every core.git argv while still running it for real."""
    calls = []
    real = core.git

    def spy(repo, *args, **kwargs):
        calls.append(args)
        return real(repo, *args, **kwargs)

    monkeypatch.setattr(core, "git", spy)
    return calls


def assert_no_history_rewrite(calls):
    """No publication path may force, reset, rebase or run a second merge."""
    for args in calls:
        assert args[0] not in ("config", "merge", "reset", "rebase", "cherry-pick"), args
        assert "--force" not in args and "--force-with-lease" not in args, args
        if args[0] == "push":
            for arg in args:
                assert not (isinstance(arg, str) and arg.startswith("+")), args


def remote_ref(repo, ref):
    return g(repo, "ls-remote", "origin", ref).split()[0]


def test_publish_preserves_source_ancestry(core, lab):
    t = offer(lab)
    c = reviewed(core, lab)
    r = core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    p = r["result_sha"]
    assert g(lab["publisher"], "show", "-s", "--format=%P", p).split() == [lab["base"], t]
    assert g(lab["publisher"], "show", "-s", "--format=%T", p) == c["reviewed_tree"]
    assert g(lab["producer"], "ls-remote", "origin", "refs/heads/machine/testlab").split()[0] == t
    assert g(lab["producer"], "ls-remote", "origin", "refs/heads/main").split()[0] == p

    # The journal carries the exact result, the pin preserves P, and the note
    # the publisher produced is the reviewed report (no second content tree).
    assert r["status"] == "published" and r["published_main"] == p
    assert r["result_parents"] == [lab["base"], t]
    assert r["result_tree"] == c["reviewed_tree"]
    assert g(lab["publisher"], "rev-parse",
             f'refs/hermes-sync/candidates/{c["id"]}/result') == p
    assert core.source_status(lab["publisher"], p, t) == "consumed"

    message = g(lab["publisher"], "log", "-1", "--format=%B", p)
    assert message.startswith("consolidator:")
    for trailer in (f"Skill-Sync-Candidate: {c['id']}", f"Source-Ref: {c['source_ref']}",
                    f"Source-Tip: {t}", f"Review-Digest: {c['review_digest']}",
                    f"Reviewed-Tree: {c['reviewed_tree']}"):
        assert trailer in message

    # The publisher clone itself was not checked out, merged or advanced.
    assert g(lab["publisher"], "rev-parse", "HEAD") == lab["base"]
    assert g(lab["publisher"], "rev-parse", "refs/heads/main") == lab["base"]
    assert g(lab["publisher"], "status", "--porcelain") == ""


def test_publish_T_preserves_T2(core, lab, monkeypatch):
    t = offer(lab)
    c = reviewed(core, lab)
    t2 = offer(lab, OFFER_TEXT + "An extra T2 rule.\n")
    assert t2 != t and core.is_ancestor(lab["producer"], t, t2)

    calls = record_git_calls(core, monkeypatch)
    p = core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])["result_sha"]
    assert_no_history_rewrite(calls)

    # T2 is untouched, T is inside P and T2 is deliberately not.
    assert remote_ref(lab["producer"], "refs/heads/machine/testlab") == t2
    assert remote_ref(lab["producer"], "refs/heads/main") == p
    assert core.is_ancestor(lab["publisher"], t, p)
    assert not core.is_ancestor(lab["publisher"], t2, p)

    # The later candidate captures T2 and does not duplicate T's accepted text.
    n = core.capture(lab["publisher"], lab["store"], lab["source"])
    assert n["id"] != c["id"] and n["main_sha"] == p and n["source_sha"] == t2
    assert core.source_status(lab["publisher"], p, t2) == "pending"
    n = core.prepare(lab["publisher"], lab["store"], n)
    staged = (Path(n["worktree"]) / "skills/demo/SKILL.md").read_text(encoding="utf-8")
    assert staged.count("A useful generic rule.") == 1
    assert "An extra T2 rule." in staged


def test_stale_main_never_pushes(core, lab, tmp_path, monkeypatch):
    t = offer(lab)
    c = reviewed(core, lab)
    note = lab["vault"] / c["report_relative_path"]
    report_bytes = note.read_bytes()

    second = second_main_clone(lab, tmp_path)
    independent = independent_main_commit(second)

    calls = record_git_calls(core, monkeypatch)
    with pytest.raises(core.WorkflowError) as excinfo:
        core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    assert "stale" in str(excinfo.value)
    assert not any(args[0] in ("push", "commit-tree") for args in calls)

    # The independent commit survives; neither source nor report was disturbed.
    assert remote_ref(lab["producer"], "refs/heads/main") == independent
    assert remote_ref(lab["producer"], "refs/heads/machine/testlab") == t
    assert note.read_bytes() == report_bytes
    assert g(lab["publisher"], "rev-parse", "refs/heads/main") == lab["base"]
    stale = core.load_candidate(lab["store"], c["id"])
    assert stale["status"] == "stale" and stale["result_sha"] == ""
    assert independent[:12] in stale["last_error"]

    # A new M produces a distinct candidate that is reviewed and reported again.
    fresh = core.capture(lab["publisher"], lab["store"], lab["source"])
    assert fresh["id"] != c["id"] and fresh["main_sha"] == independent
    fresh = core.prepare(lab["publisher"], lab["store"], fresh)
    fresh = record_full_review(core, lab, fresh)
    assert fresh["status"] == "report-verified"
    assert fresh["report_relative_path"] != c["report_relative_path"]
    assert note.read_bytes() == report_bytes


def test_reject_only_merge_keeps_original_source(core, lab):
    t = offer(lab)
    c = core.capture(lab["publisher"], lab["store"], lab["source"])
    c = core.prepare(lab["publisher"], lab["store"], c)
    worktree = Path(c["worktree"])

    # The agent decided to reject: an explicit path checkout restores M's
    # content in index and worktree; MERGE_HEAD stays T so the history remains.
    g(worktree, "checkout", c["main_sha"], "--", "skills/demo/SKILL.md")
    assert g(worktree, "rev-parse", "MERGE_HEAD") == t
    assert (worktree / "skills/demo/SKILL.md").read_text(encoding="utf-8") == BASE_TEXT

    review = {
        "schema": 1, "candidate_id": c["id"], "main_sha": c["main_sha"],
        "source_sha": c["source_sha"],
        "summary": "Reject an unsuitable rule and acknowledge the source tip",
        "files": [{
            "path": "skills/demo/SKILL.md", "change_type": "unsuitable",
            "decision": "reject",
            "source_anchors": [{"ref": t, "path": "skills/demo/SKILL.md",
                                "quote": "A useful generic rule."}],
            "reason": "Not useful for this library; rejected explicitly",
            "replacements": [],
        }],
    }
    c = record_full_review(core, lab, c, review)
    r = core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    p = r["result_sha"]

    # Same tree as M, but a real merge commit with the original source history.
    assert g(lab["publisher"], "show", "-s", "--format=%P", p).split() == [c["main_sha"], t]
    assert g(lab["publisher"], "show", "-s", "--format=%T", p) == (
        g(lab["publisher"], "rev-parse", f'{c["main_sha"]}^{{tree}}'))
    # The rejected text is not in the published tree even though T keeps it.
    assert g(lab["publisher"], "show", "-s", "--format=%T", p) != g(
        lab["producer"], "rev-parse", f'{t}^{{tree}}')
    assert remote_ref(lab["producer"], "refs/heads/machine/testlab") == t
    assert r["status"] == "published"
    assert core.source_status(lab["publisher"], p, t) == "consumed"

    # The rejection is documented, not silently dropped.
    text = (lab["vault"] / c["report_relative_path"]).read_text(encoding="utf-8")
    assert "A useful generic rule." in text
    assert "Not useful for this library" in text and "reject" in text


def test_empty_diff_acknowledgment_publishes_merge(core, lab):
    g(lab["producer"], "commit", "-q", "--allow-empty", "-m", "empty tip")
    t = g(lab["producer"], "rev-parse", "HEAD")
    g(lab["producer"], "push", "-q", "origin", "machine/testlab")

    c = core.capture(lab["publisher"], lab["store"], lab["source"])
    assert c["source_sha"] == t and c["main_sha"] == lab["base"]
    c = core.prepare(lab["publisher"], lab["store"], c)
    assert c["input_paths"] == [] and c["conflict_paths"] == []

    review = {"schema": 1, "candidate_id": c["id"], "main_sha": c["main_sha"],
              "source_sha": c["source_sha"],
              "summary": "Consume an empty tip that changes no canonical content",
              "files": []}
    c = record_full_review(core, lab, c, review)
    r = core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    p = r["result_sha"]

    # A merge acknowledgment: parents M,T; tree stays exactly M's tree.
    assert g(lab["publisher"], "show", "-s", "--format=%P", p).split() == [lab["base"], t]
    assert g(lab["publisher"], "show", "-s", "--format=%T", p) == g(
        lab["publisher"], "rev-parse", f'{lab["base"]}^{{tree}}')
    assert remote_ref(lab["producer"], "refs/heads/machine/testlab") == t
    assert remote_ref(lab["producer"], "refs/heads/main") == p
    assert core.source_status(lab["publisher"], p, t) == "consumed"
    text = (lab["vault"] / c["report_relative_path"]).read_text(encoding="utf-8")
    assert "empty" in text.lower() and "no canonical content" in text


def test_repeat_publish_creates_no_second_integration_commit(core, lab, monkeypatch):
    t = offer(lab)
    c = reviewed(core, lab)
    first = core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    p = first["result_sha"]
    assert first["status"] == "published" and remote_ref(lab["producer"], "refs/heads/main") == p
    count = int(g(lab["publisher"], "rev-list", "--count", p))

    calls = record_git_calls(core, monkeypatch)
    second = core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    assert second["result_sha"] == p
    assert second["status"] in ("published", "receipt-pending", "complete")
    assert remote_ref(lab["producer"], "refs/heads/main") == p
    assert int(g(lab["publisher"], "rev-list", "--count", p)) == count
    assert not any(args[0] in ("commit-tree", "push", "update-ref") for args in calls)
    assert_no_history_rewrite(calls)

    # The result payload is deterministic and names the exact saved commit.
    text = core.render_result(second)
    assert text == core.render_result(second)
    for expected in (p, t, lab["base"], c["id"], c["reviewed_tree"], c["review_digest"]):
        assert expected in text
    assert (lab["store"] / "candidates" / c["id"] / "result.md").read_text(
        encoding="utf-8") == text


def test_ff_rejection_race_is_stale_not_forced(core, lab, tmp_path, monkeypatch):
    t = offer(lab)
    c = reviewed(core, lab)
    second = second_main_clone(lab, tmp_path, name="race")
    real = core.git
    raced = {"done": False}

    def racing_git(repo, *args, **kwargs):
        if args[0] == "push" and not raced["done"]:
            raced["done"] = True
            raced["sha"] = independent_main_commit(second)
        return real(repo, *args, **kwargs)

    monkeypatch.setattr(core, "git", racing_git)
    with pytest.raises(core.WorkflowError) as excinfo:
        core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    assert "stale" in str(excinfo.value)

    # The racing commit survives and the review evidence is preserved, not forced.
    independent = raced["sha"]
    assert remote_ref(lab["producer"], "refs/heads/main") == independent
    assert remote_ref(lab["producer"], "refs/heads/machine/testlab") == t
    stale = core.load_candidate(lab["store"], c["id"])
    assert stale["status"] == "stale" and stale["result_sha"]
    assert g(lab["publisher"], "rev-parse",
             f'refs/hermes-sync/candidates/{c["id"]}/result') == stale["result_sha"]
    assert g(lab["publisher"], "show", "-s", "--format=%P", stale["result_sha"]).split() == [
        lab["base"], t]


def test_publish_persists_intent_before_push(core, lab, monkeypatch):
    """The journal must already carry P and its parents when the push starts."""
    t = offer(lab)
    c = reviewed(core, lab)
    real = core.git
    seen = {}

    def spy(repo, *args, **kwargs):
        if args[0] == "push" and not seen:
            seen["journal"] = json.loads(
                (lab["store"] / "candidates" / c["id"] / "state.json").read_text(
                    encoding="utf-8"))
            seen["refspec"] = args[-1]
        return real(repo, *args, **kwargs)

    monkeypatch.setattr(core, "git", spy)
    r = core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    journal = seen["journal"]
    assert journal["status"] == "publish-intent"
    assert journal["result_sha"] == r["result_sha"]
    assert seen["refspec"] == f"{r['result_sha']}:refs/heads/main"
    assert journal["result_parents"] == [lab["base"], t]
    assert journal["result_tree"] == c["reviewed_tree"]
    assert journal["report_sha256"] == c["report_sha256"]
    assert r["status"] == "published"


def test_reconcile_confirms_a_crash_after_push(core, lab, monkeypatch):
    """A saved P that already reached main is recognised, never re-committed."""
    t = offer(lab)
    c = reviewed(core, lab)
    real = core.git

    def dying_git(repo, *args, **kwargs):
        if args[0] == "push":
            real(repo, *args, **kwargs)
            raise RuntimeError("simulated process death after the remote write")
        return real(repo, *args, **kwargs)

    monkeypatch.setattr(core, "git", dying_git)
    with pytest.raises(RuntimeError):
        core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    interrupted = core.load_candidate(lab["store"], c["id"])
    assert interrupted["status"] == "publish-intent" and interrupted["result_sha"]
    p = interrupted["result_sha"]
    assert remote_ref(lab["producer"], "refs/heads/main") == p
    # The lock was released even though the process died mid-call.
    token = core.acquire_publisher_lock(lab["store"])
    core.release_publisher_lock(lab["store"], token)

    monkeypatch.setattr(core, "git", real)
    count = int(g(lab["publisher"], "rev-list", "--count", p))
    reconciled = core.reconcile(lab["publisher"], lab["store"], c["id"])
    assert reconciled["status"] == "published"
    assert reconciled["result_sha"] == p
    assert reconciled["published_main"] == p
    assert remote_ref(lab["producer"], "refs/heads/main") == p
    assert int(g(lab["publisher"], "rev-list", "--count", p)) == count
    assert core.source_status(lab["publisher"], p, t) == "consumed"


def test_reconcile_retries_the_same_saved_result(core, lab, monkeypatch):
    """A transport failure keeps the intent; reconcile pushes exactly that P."""
    t = offer(lab)
    c = reviewed(core, lab)
    real = core.git

    def failing_push(repo, *args, **kwargs):
        if args[0] == "push":
            return subprocess.CompletedProcess(["git"], 128, "", "simulated transport failure")
        return real(repo, *args, **kwargs)

    monkeypatch.setattr(core, "git", failing_push)
    with pytest.raises(core.WorkflowError) as excinfo:
        core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    assert "publish-intent retained" in str(excinfo.value)
    interrupted = core.load_candidate(lab["store"], c["id"])
    assert interrupted["status"] == "publish-intent"
    p = interrupted["result_sha"]
    assert remote_ref(lab["producer"], "refs/heads/main") == lab["base"]

    monkeypatch.setattr(core, "git", real)
    reconciled = core.reconcile(lab["publisher"], lab["store"], c["id"])
    assert reconciled["status"] == "published" and reconciled["result_sha"] == p
    assert remote_ref(lab["producer"], "refs/heads/main") == p
    assert g(lab["publisher"], "show", "-s", "--format=%P", p).split() == [lab["base"], t]
    assert int(g(lab["publisher"], "rev-list", "--count", p)) == 3


def test_publish_blocks_a_rewritten_source(core, lab, monkeypatch):
    """A source rewrite that drops T is blocked, never published over."""
    t = offer(lab)
    c = reviewed(core, lab)
    producer = lab["producer"]
    g(producer, "checkout", "-q", "-B", "rewrite-sim", lab["base"])
    rewritten = commit(producer, BASE_TEXT + "Replacement rule.\n", message="rewrite transport")
    g(producer, "push", "--force", "origin", "rewrite-sim:machine/testlab")
    assert rewritten != t and not core.is_ancestor(producer, t, rewritten)

    calls = record_git_calls(core, monkeypatch)
    with pytest.raises(core.WorkflowError) as excinfo:
        core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    assert "blocked" in str(excinfo.value) and "recapture" in str(excinfo.value)
    assert not any(args[0] in ("push", "commit-tree") for args in calls)
    blocked = core.load_candidate(lab["store"], c["id"])
    assert blocked["status"] == "blocked" and "recapture" in blocked["last_error"]
    assert remote_ref(producer, "refs/heads/machine/testlab") == rewritten


def test_reconcile_accepts_a_later_main_containing_the_result(core, lab, tmp_path):
    """Main that advanced past P still counts; reconcile adds no commit."""
    t = offer(lab)
    c = reviewed(core, lab)
    p = core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])["result_sha"]
    later_clone = second_main_clone(lab, tmp_path, name="later")
    later = independent_main_commit(later_clone)

    reconciled = core.reconcile(lab["publisher"], lab["store"], c["id"])
    assert reconciled["status"] == "published"
    assert reconciled["published_main"] == later
    assert reconciled["result_sha"] == p
    assert remote_ref(lab["producer"], "refs/heads/main") == later
    assert core.is_ancestor(lab["publisher"], p, later)
    assert g(lab["publisher"], "show", "-s", "--format=%P", later).split() == [p]
    assert int(g(lab["publisher"], "rev-list", "--count", later)) == 4


def test_publish_rechecks_tree_review_and_report(core, lab, monkeypatch):
    t = offer(lab)
    c = reviewed(core, lab)
    note = lab["vault"] / c["report_relative_path"]
    report_bytes = note.read_bytes()
    review_path = lab["store"] / "candidates" / c["id"] / "review.json"
    review_bytes = review_path.read_bytes()
    candidate_file = Path(c["worktree"]) / "skills/demo/SKILL.md"
    reviewed_text = candidate_file.read_text(encoding="utf-8")

    calls = record_git_calls(core, monkeypatch)

    # A candidate edited after review is not published on the old green flag.
    candidate_file.write_text(reviewed_text + "Late unreviewed edit.\n", encoding="utf-8")
    with pytest.raises(core.WorkflowError) as excinfo:
        core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    assert "unstaged" in str(excinfo.value)
    candidate_file.write_text(reviewed_text, encoding="utf-8")

    # Altered report bytes block publication.
    note.write_text(report_bytes.decode("utf-8") + " ", encoding="utf-8")
    with pytest.raises(core.WorkflowError) as excinfo:
        core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    assert "does not match" in str(excinfo.value)
    note.write_bytes(report_bytes)

    # A rewritten stored review no longer matches the recorded digest.
    review_path.write_text(json.dumps({**json.loads(review_bytes), "summary": "Rewritten"}) + "",
                           encoding="utf-8")
    with pytest.raises(core.WorkflowError) as excinfo:
        core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    assert "digest" in str(excinfo.value)
    review_path.write_bytes(review_bytes)

    # Nothing above reached the remote or created an integration commit.
    assert not any(args[0] in ("push", "commit-tree") for args in calls)
    assert remote_ref(lab["producer"], "refs/heads/main") == lab["base"]
    assert remote_ref(lab["producer"], "refs/heads/machine/testlab") == t
    assert core.load_candidate(lab["store"], c["id"])["status"] == "report-verified"

    # A source disabled after review is refused by the registry re-check.
    config_path = lab["store"] / "publisher.json"
    config_bytes = config_path.read_bytes()
    config = json.loads(config_bytes)
    config["sources"][0]["enabled"] = False
    config_path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(core.WorkflowError) as excinfo:
        core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    assert "disabled" in str(excinfo.value)
    config_path.write_bytes(config_bytes)
    assert not any(args[0] in ("push", "commit-tree") for args in calls)

    # With every input restored the same candidate publishes normally.
    assert core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])["status"] == "published"
    assert remote_ref(lab["producer"], "refs/heads/main") != lab["base"]


# ---------------------------------------------------------------------------
# D6/D7/D8: recovery, receipts and incidents (packet 08).
#
# Every failure here is injected around a real Git operation: the push that
# "fails" is a real push attempt whose transport is reported broken, the crash
# happens after the real bare-remote push already updated the ref, and no test
# manufactures a successful process or remote result.
# ---------------------------------------------------------------------------

RECEIPT_FILE_SUFFIX = "-result.md"


def receipt_path(lab, cid):
    config = json.loads((lab["store"] / "publisher.json").read_text(encoding="utf-8"))
    return lab["vault"] / config["report"]["directory"] / f"skill-sync-{cid}{RECEIPT_FILE_SUFFIX}"


def store_result_text(lab, cid):
    return (lab["store"] / "candidates" / cid / "result.md").read_text(encoding="utf-8")


def crash_after_remote_write(core, lab, monkeypatch, cid):
    """Die right after a *real* successful push, exactly like a killed process."""
    real = core.git
    seen = {}

    def dying_git(repo, *args, **kwargs):
        if args and args[0] == "push":
            done = real(repo, *args, **kwargs)
            assert done.returncode == 0, done.stderr
            seen["refspec"] = args[-1]
            raise RuntimeError("simulated process death after the remote ref update")
        return real(repo, *args, **kwargs)

    monkeypatch.setattr(core, "git", dying_git)
    try:
        with pytest.raises(RuntimeError):
            core.publish(lab["publisher"], lab["store"], cid, lab["vault"])
    finally:
        monkeypatch.setattr(core, "git", real)
    return core.load_candidate(lab["store"], cid), seen


def no_publication_writes(calls):
    """Reconciliation and receipt work never integrate, push or move a pin."""
    assert not [args for args in calls if args and args[0] in ("push", "commit-tree", "update-ref")], calls


def rejected_publication(core, lab, cid):
    """A real local bare remote rejects P before updating main."""
    hook = lab["remote"] / "hooks/pre-receive"
    hook.write_text("#!/bin/sh\nprintf 'fixture rejects publication\\n' >&2\nexit 1\n",
                    encoding="utf-8")
    hook.chmod(0o755)
    try:
        with pytest.raises(core.WorkflowError, match="publish-intent retained"):
            core.publish(lab["publisher"], lab["store"], cid, lab["vault"])
    finally:
        hook.unlink()
    state = core.load_candidate(lab["store"], cid)
    assert state["status"] == "publish-intent"
    assert "was not accepted" in state["last_error"]
    assert remote_ref(lab["producer"], "refs/heads/main") == state["main_sha"]
    return state


@pytest.mark.parametrize("changed", ["report", "disabled-source", "removed-source", "source-identity", "review", "tree", "checks"])
def test_reconcile_reauthorizes_absent_result_before_retry(core, lab, monkeypatch, changed):
    offer(lab)
    c = reviewed(core, lab)
    intent = rejected_publication(core, lab, c["id"])
    directory = lab["store"] / "candidates" / c["id"]
    if changed == "report":
        target = lab["vault"] / c["report_relative_path"]
        target.write_bytes(target.read_bytes() + b"Altered before retry.\n")
    elif changed in ("disabled-source", "removed-source", "source-identity"):
        config_path = lab["store"] / "publisher.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if changed == "removed-source":
            config["sources"] = []
        elif changed == "source-identity":
            config["sources"][0]["profile"] = "changed-profile"
        else:
            config["sources"][0]["enabled"] = False
        config_path.write_text(json.dumps(config), encoding="utf-8")
    elif changed == "review":
        target = directory / "review.json"
        review = json.loads(target.read_text(encoding="utf-8"))
        review["summary"] = "Rewritten after the rejected push"
        target.write_text(json.dumps(review), encoding="utf-8")
    elif changed == "tree":
        w = Path(c["worktree"])
        with (w / "skills/demo/SKILL.md").open("a", encoding="utf-8") as handle:
            handle.write("Late staged edit after rejected push.\n")
        g(w, "add", "--", "skills/demo/SKILL.md")
    else:
        target = directory / "checks.json"
        checks = json.loads(target.read_text(encoding="utf-8"))
        checks["checks"][0]["stdout"] = "Rewritten check evidence"
        target.write_text(json.dumps(checks), encoding="utf-8")
    fresh = load_core()  # bindings and authorisation must survive process restart
    calls = record_git_calls(fresh, monkeypatch)
    with pytest.raises(fresh.WorkflowError):
        fresh.reconcile(lab["publisher"], lab["store"], c["id"])
    no_publication_writes(calls)
    refused = fresh.load_candidate(lab["store"], c["id"])
    assert refused["status"] == "stale" or refused["incident"]
    assert refused["result_sha"] == intent["result_sha"]
    assert remote_ref(lab["producer"], "refs/heads/main") == c["main_sha"]


def test_reconcile_real_rejection_retries_identical_authorized_result(core, lab, monkeypatch):
    offer(lab)
    c = reviewed(core, lab)
    intent = rejected_publication(core, lab, c["id"])
    fresh = load_core()
    calls = record_git_calls(fresh, monkeypatch)
    result = fresh.reconcile(lab["publisher"], lab["store"], c["id"])
    assert result["result_sha"] == intent["result_sha"] and result["status"] == "published"
    assert [args for args in calls if args[0] == "push"] == [
        ("push", "--no-verify", "origin", f"{intent['result_sha']}:refs/heads/main")]
    assert not [args for args in calls if args[0] in ("commit-tree", "update-ref")]
    assert remote_ref(lab["producer"], "refs/heads/main") == intent["result_sha"]


def test_reconcile_observed_result_repairs_without_retry_authorization(core, lab, monkeypatch):
    offer(lab)
    c = reviewed(core, lab)
    intent, _ = crash_after_remote_write(core, lab, monkeypatch, c["id"])
    note = lab["vault"] / c["report_relative_path"]
    note.write_bytes(note.read_bytes() + b"Tampered already published review.\n")
    config_path = lab["store"] / "publisher.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["sources"][0]["enabled"] = False
    config_path.write_text(json.dumps(config), encoding="utf-8")
    (lab["store"] / "candidates" / c["id"] / "checks.json").unlink()
    fresh = load_core()
    calls = record_git_calls(fresh, monkeypatch)
    result = fresh.reconcile(lab["publisher"], lab["store"], c["id"])
    no_publication_writes(calls)
    assert result["status"] == "published" and result["incident"]
    assert result["result_sha"] == result["published_main"] == intent["result_sha"]
    assert remote_ref(lab["producer"], "refs/heads/main") == intent["result_sha"]


def test_push_failure_retains_same_result_for_retry(core, lab, monkeypatch):
    """D6: a failed push keeps the exact saved P; the retry pushes that same P."""
    t = offer(lab)
    c = reviewed(core, lab)
    real = core.git
    attempts = []

    def failing_push(repo, *args, **kwargs):
        if args and args[0] == "push":
            attempts.append(args)
            return subprocess.CompletedProcess(
                ["git", *args], 128, "",
                "fatal: unable to access 'origin': simulated transport outage")
        return real(repo, *args, **kwargs)

    monkeypatch.setattr(core, "git", failing_push)
    with pytest.raises(core.WorkflowError) as excinfo:
        core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    assert "publish-intent retained" in str(excinfo.value)
    assert len(attempts) == 1

    intent = core.load_candidate(lab["store"], c["id"])
    p = intent["result_sha"]
    assert intent["status"] == "publish-intent"
    assert p and intent["result_parents"] == [lab["base"], t]
    assert intent["result_tree"] == c["reviewed_tree"]
    # P is a real commit-tree result whose parent order, tree and pin are exact.
    assert g(lab["publisher"], "cat-file", "-t", p) == "commit"
    assert g(lab["publisher"], "show", "-s", "--format=%P", p).split() == [lab["base"], t]
    assert g(lab["publisher"], "show", "-s", "--format=%T", p) == c["reviewed_tree"]
    assert g(lab["publisher"], "rev-parse",
             f'refs/hermes-sync/candidates/{c["id"]}/result') == p
    # The diagnostic names the exact outcome and the next action.
    assert "simulated transport outage" in intent["last_error"]
    assert "reconcile" in intent["last_error"]
    # Nothing reached the remote; both source refs are exactly where they were.
    assert remote_ref(lab["producer"], "refs/heads/main") == lab["base"]
    assert remote_ref(lab["producer"], "refs/heads/machine/testlab") == t
    assert intent["published_main"] == ""
    assert "result_observed_at" in intent and intent["result_observed_at"] == ""

    # Restored transport: reconcile retries the very same P, once.
    monkeypatch.setattr(core, "git", real)
    calls = record_git_calls(core, monkeypatch)
    reconciled = core.reconcile(lab["publisher"], lab["store"], c["id"])
    pushes = [args for args in calls if args and args[0] == "push"]
    assert pushes == [("push", "--no-verify", "origin", f"{p}:refs/heads/main")]
    assert not [args for args in calls if args and args[0] == "commit-tree"]
    assert reconciled["status"] == "published"
    assert reconciled["result_sha"] == p and reconciled["published_main"] == p
    assert reconciled["result_observed_at"]
    assert remote_ref(lab["producer"], "refs/heads/main") == p
    assert remote_ref(lab["producer"], "refs/heads/machine/testlab") == t
    # One integration commit plus the two history commits: no second merge.
    assert int(g(lab["publisher"], "rev-list", "--count", p)) == 3
    assert core.source_status(lab["publisher"], p, t) == "consumed"
    assert_no_history_rewrite(calls)


def test_reconcile_after_push_does_not_duplicate(core, lab, monkeypatch):
    """D7: a crash after the real push is repaired from the journal, not re-merged."""
    t = offer(lab)
    c = reviewed(core, lab)
    crashed, seen = crash_after_remote_write(core, lab, monkeypatch, c["id"])
    p = crashed["result_sha"]
    assert seen["refspec"] == f"{p}:refs/heads/main"
    assert crashed["status"] == "publish-intent" and crashed["published_main"] == ""
    assert remote_ref(lab["producer"], "refs/heads/main") == p

    # A fresh process reloads the module and must trust only the persisted journal.
    fresh = load_core()
    calls = record_git_calls(fresh, monkeypatch)
    reconciled = fresh.reconcile(lab["publisher"], lab["store"], c["id"])
    no_publication_writes(calls)
    assert reconciled["status"] in ("published", "receipt-pending")
    assert reconciled["result_sha"] == p and reconciled["published_main"] == p
    # Publication is proven from ancestry plus the exact trailers/tree.
    assert fresh.is_ancestor(lab["publisher"], p,
                             remote_ref(lab["producer"], "refs/heads/main"))
    message = g(lab["publisher"], "log", "-1", "--format=%B", p)
    assert message.startswith("consolidator:")
    for trailer in (f"Skill-Sync-Candidate: {c['id']}", f"Source-Tip: {t}",
                    f"Reviewed-Tree: {c['reviewed_tree']}"):
        assert trailer in message
    assert g(lab["publisher"], "show", "-s", "--format=%T", p) == c["reviewed_tree"]
    assert int(g(lab["publisher"], "rev-list", "--count", p)) == 3

    # The result payload is rendered once and never re-timestamped afterwards,
    # so a repeated reconcile is byte-identical even if the clock moved.
    first_text = store_result_text(lab, c["id"])
    observed_at = reconciled["result_observed_at"]
    assert observed_at in first_text
    monkeypatch.setattr(fresh, "_utc_now", lambda: "2099-12-31T23:59:59Z")
    again = fresh.reconcile(lab["publisher"], lab["store"], c["id"])
    assert again["result_sha"] == p and again["published_main"] == p
    assert again["result_observed_at"] == observed_at
    assert store_result_text(lab, c["id"]) == first_text
    assert "2099" not in first_text
    no_publication_writes(calls)
    assert remote_ref(lab["producer"], "refs/heads/main") == p


def test_receipt_failure_does_not_republish(core, lab, monkeypatch):
    """D8: receipt delivery is separate, retryable and never re-publishes P."""
    t = offer(lab)
    c = reviewed(core, lab)
    review_note = lab["vault"] / c["report_relative_path"]
    review_bytes = review_note.read_bytes()

    published = core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    p = published["result_sha"]
    assert published["status"] == "published"
    # Python renders a payload; it never writes the live receipt note itself.
    receipt = receipt_path(lab, c["id"])
    assert not receipt.exists()
    payload = store_result_text(lab, c["id"])

    calls = record_git_calls(core, monkeypatch)

    # The destination is still unavailable: the receipt stays pending, not done.
    with pytest.raises(core.WorkflowError) as excinfo:
        core.verify_result(lab["store"], c["id"], lab["vault"])
    assert "missing" in str(excinfo.value)
    pending = core.load_candidate(lab["store"], c["id"])
    assert pending["status"] == "receipt-pending"
    assert pending["result_sha"] == p and pending["published_main"] == p
    assert "missing" in pending["last_error"]
    assert pending["receipt_attempts"] == 1
    assert review_note.read_bytes() == review_bytes

    # Bytes that are not the rendered payload are refused, not completed.
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text("a hand-written receipt that was never rendered\n", encoding="utf-8")
    with pytest.raises(core.WorkflowError) as excinfo:
        core.verify_result(lab["store"], c["id"], lab["vault"])
    assert "does not match" in str(excinfo.value)
    assert core.load_candidate(lab["store"], c["id"])["status"] == "receipt-pending"

    # A receipt path that resolves outside the configured root is refused.
    receipt.unlink()
    outside = lab["vault"].parent / "outside-receipt.md"
    outside.write_text(payload, encoding="utf-8")
    receipt.symlink_to(outside)
    with pytest.raises(core.WorkflowError) as excinfo:
        core.verify_result(lab["store"], c["id"], lab["vault"])
    assert "symlink" in str(excinfo.value) or "escapes" in str(excinfo.value)
    receipt.unlink()

    # The exact rendered payload completes the receipt.
    receipt.write_text(payload, encoding="utf-8")
    other_root = lab["vault"].parent / "other-report-root"
    other_root.mkdir()
    with pytest.raises(core.WorkflowError) as excinfo:
        core.verify_result(lab["store"], c["id"], other_root)
    assert "configured report.vault_root" in str(excinfo.value)
    done = core.verify_result(lab["store"], c["id"], lab["vault"])
    assert done["status"] == "complete"
    assert done["receipt_sha256"] == hashlib.sha256(receipt.read_bytes()).hexdigest()
    assert done["receipt_attempts"] == 4
    assert done["result_sha"] == p and done["published_main"] == p
    assert done["result_observed_at"] and done["result_observed_at"] in payload

    # The receipt step read files only: no push, no commit, no pin movement.
    no_publication_writes(calls)
    assert remote_ref(lab["producer"], "refs/heads/main") == p
    assert int(g(lab["publisher"], "rev-list", "--count", p)) == 3
    assert remote_ref(lab["producer"], "refs/heads/machine/testlab") == t
    assert review_note.read_bytes() == review_bytes
    # Re-verifying an exact receipt stays complete and stays byte-identical.
    assert core.verify_result(lab["store"], c["id"], lab["vault"])["status"] == "complete"
    assert store_result_text(lab, c["id"]) == payload


@pytest.mark.parametrize("already_complete", [False, True], ids=["published", "complete"])
@pytest.mark.parametrize("changed", ["altered", "missing", "symlink", "stored-payload", "directory"])
def test_verify_result_reobserves_immutable_review_on_every_call(
        core, lab, monkeypatch, already_complete, changed):
    offer(lab)
    c = reviewed(core, lab)
    published = core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    review_note = lab["vault"] / c["report_relative_path"]
    original = review_note.read_bytes()
    receipt = receipt_path(lab, c["id"])
    receipt.write_text(core.render_result(published), encoding="utf-8")
    if already_complete:
        assert core.verify_result(lab["store"], c["id"], lab["vault"])["status"] == "complete"
    stored = lab["store"] / "candidates" / c["id"] / "review.md"
    config_path = lab["store"] / "publisher.json"
    config_bytes = config_path.read_bytes()
    if changed == "altered":
        review_note.write_bytes(original + b"Tampered after publication.\n")
    elif changed == "missing":
        review_note.unlink()
    elif changed == "symlink":
        outside = lab["vault"].parent / "outside-review.md"
        outside.write_bytes(original)
        review_note.unlink()
        review_note.symlink_to(outside)
    elif changed == "stored-payload":
        stored.write_bytes(original + b"Tampered stored report.\n")
    else:
        config = json.loads(config_bytes)
        config["report"]["directory"] = "projects/hermes-agent/other-reports"
        config_path.write_text(json.dumps(config), encoding="utf-8")
    calls = record_git_calls(core, monkeypatch)
    with pytest.raises(core.WorkflowError, match="incident"):
        core.verify_result(lab["store"], c["id"], lab["vault"])
    state = core.load_candidate(lab["store"], c["id"])
    assert state["status"] == "receipt-pending" and state["incident"]
    assert not state["receipt_sha256"] and not state["receipt_verified_at"]
    assert state["result_sha"] == published["result_sha"]
    no_publication_writes(calls)

    # Repairing files alone does not silently clear an already-recorded incident.
    if review_note.is_symlink():
        review_note.unlink()
    review_note.write_bytes(original)
    stored.write_bytes(original)
    config_path.write_bytes(config_bytes)
    with pytest.raises(core.WorkflowError, match="incident"):
        core.verify_result(lab["store"], c["id"], lab["vault"])
    assert core.load_candidate(lab["store"], c["id"])["incident"] == state["incident"]


def test_report_tampering_after_push_is_an_incident(core, lab, monkeypatch):
    """A report altered after P reached main is an incident, never a rollback story."""
    t = offer(lab)
    c = reviewed(core, lab)
    review_note = lab["vault"] / c["report_relative_path"]
    original = review_note.read_bytes()
    crashed, _ = crash_after_remote_write(core, lab, monkeypatch, c["id"])
    p = crashed["result_sha"]
    assert crashed["status"] == "publish-intent"

    tampered = original.decode("utf-8") + "Tampered after publication.\n"
    review_note.write_text(tampered, encoding="utf-8")

    calls = record_git_calls(core, monkeypatch)
    reconciled = core.reconcile(lab["publisher"], lab["store"], c["id"])
    no_publication_writes(calls)

    # Publication stays a fact: same P, same remote main, no "never published".
    assert reconciled["result_sha"] == p and reconciled["published_main"] == p
    assert reconciled["status"] in ("published", "receipt-pending")
    assert reconciled["status"] not in ("publish-intent", "stale", "blocked", "report-verified")
    assert "incident" in reconciled and reconciled["incident"]
    assert "review" in reconciled["incident"].lower()
    assert "incident" in reconciled["last_error"].lower()
    assert remote_ref(lab["producer"], "refs/heads/main") == p
    assert int(g(lab["publisher"], "rev-list", "--count", p)) == 3

    # The receipt cannot complete around an unresolved incident ...
    with pytest.raises(core.WorkflowError) as excinfo:
        core.verify_result(lab["store"], c["id"], lab["vault"])
    assert "incident" in str(excinfo.value)
    assert core.load_candidate(lab["store"], c["id"])["status"] in ("published", "receipt-pending")
    # ... and nothing rewrote the immutable review note.
    assert review_note.read_text(encoding="utf-8") == tampered

    # Restoring the exact bytes does not erase the recorded incident.
    review_note.write_bytes(original)
    again = core.reconcile(lab["publisher"], lab["store"], c["id"])
    assert again["incident"] == reconciled["incident"]
    assert again["result_sha"] == p
    with pytest.raises(core.WorkflowError) as excinfo:
        core.verify_result(lab["store"], c["id"], lab["vault"])
    assert "incident" in str(excinfo.value)


def test_unconfirmed_remote_read_keeps_intent_until_reconcile(core, lab, monkeypatch):
    """An unreadable ref after a real push is an unknown outcome, not a failure."""
    t = offer(lab)
    c = reviewed(core, lab)
    real = core.git

    def blind_git(repo, *args, **kwargs):
        if args and args[0] == "ls-remote":
            return subprocess.CompletedProcess(
                ["git", *args], 128, "",
                "fatal: unable to access 'origin': Could not resolve host: origin")
        return real(repo, *args, **kwargs)

    monkeypatch.setattr(core, "git", blind_git)
    with pytest.raises(core.WorkflowError) as excinfo:
        core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    message = str(excinfo.value)
    assert "publish-intent retained" in message and "could not be confirmed" in message

    uncertain = core.load_candidate(lab["store"], c["id"])
    p = uncertain["result_sha"]
    assert uncertain["status"] == "publish-intent"
    assert uncertain["published_main"] == ""
    assert "Could not resolve host" in uncertain["last_error"]
    assert "reconcile" in uncertain["last_error"]
    # The ref really moved: this is unknown, not a failed push to be re-created.
    assert remote_ref(lab["producer"], "refs/heads/main") == p
    assert g(lab["publisher"], "show", "-s", "--format=%P", p).split() == [lab["base"], t]
    # An uncertain outcome cannot be receipted either: only observed publication may.
    with pytest.raises(core.WorkflowError) as excinfo:
        core.verify_result(lab["store"], c["id"], lab["vault"])
    assert "publish-intent" in str(excinfo.value)

    monkeypatch.setattr(core, "git", real)
    calls = record_git_calls(core, monkeypatch)
    reconciled = core.reconcile(lab["publisher"], lab["store"], c["id"])
    no_publication_writes(calls)
    assert reconciled["status"] == "published"
    assert reconciled["result_sha"] == p and reconciled["published_main"] == p
    assert reconciled["last_error"] == ""
    assert reconciled["result_observed_at"]
    assert remote_ref(lab["producer"], "refs/heads/main") == p
    assert int(g(lab["publisher"], "rev-list", "--count", p)) == 3
    assert core.source_status(lab["publisher"], p, t) == "consumed"


# ---------------------------------------------------------------------------
# B10: stable pending monitor and explicit retry generation.
# ---------------------------------------------------------------------------

def pending_now(core, lab):
    return core.pending_lines(lab["publisher"], lab["store"], [lab["source"]])


@pytest.mark.parametrize("phase", ["publish-intent", "rejected-intent", "published", "receipt-pending", "incident"])
@pytest.mark.parametrize("enabled", [True, False], ids=["enabled", "disabled"])
def test_monitor_surfaces_unfinished_publication_journals(core, lab, monkeypatch, phase, enabled):
    offer(lab)
    c = reviewed(core, lab)
    if phase == "rejected-intent":
        rejected_publication(core, lab, c["id"])
    else:
        crash_after_remote_write(core, lab, monkeypatch, c["id"])
        if phase != "publish-intent":
            core.reconcile(lab["publisher"], lab["store"], c["id"])
        if phase in ("receipt-pending", "incident"):
            if phase == "incident":
                note = lab["vault"] / c["report_relative_path"]
                note.write_bytes(note.read_bytes() + b"Tampered report.\n")
                core.reconcile(lab["publisher"], lab["store"], c["id"])
            with pytest.raises(core.WorkflowError):
                core.verify_result(lab["store"], c["id"], lab["vault"])
    config_path = lab["store"] / "publisher.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["sources"][0]["enabled"] = enabled
    config_path.write_text(json.dumps(config), encoding="utf-8")
    state_path = lab["store"] / "candidates" / c["id"] / "state.json"
    original = state_path.read_bytes()
    prefix = "incident" if phase == "incident" else "recover"
    expected = [f"{prefix} {c['id']}"]
    first = core.pending_lines(lab["publisher"], lab["store"])
    assert first == expected
    monkeypatch.setattr(core, "_utc_now", lambda: "2099-12-31T23:59:59Z")
    assert core.pending_lines(lab["publisher"], lab["store"]) == first
    assert core.pending_lines(lab["publisher"], lab["store"], fetch=False) == first
    assert state_path.read_bytes() == original


def test_pending_excludes_unsubmitted_refactor_and_consumed_tips(core, lab, tmp_path):
    """Only enabled registered transport tips count: a pushed refactor branch that
    was never submitted is not pending work, and a transport tip that main already
    contains is consumed rather than listed forever."""
    t = offer(lab)
    producer = lab["producer"]
    g(producer, "checkout", "-q", "-b", "refactor/topic")
    refactor_tip = commit(producer, "---\nname: demo\ndescription: Demonstration skill.\n---\n\n# Demo\n\nRefactor-only instruction.\n",
                          message="unsubmitted refactor work",
                          path="skills/demo/REFACTOR.md")
    g(producer, "push", "-q", "origin", "refactor/topic")
    g(producer, "checkout", "-q", "machine/testlab")

    cid = core.candidate_id("owned-skills", "refs/heads/machine/testlab",
                            lab["base"], t, "skill-review-v1", "transport")
    assert pending_now(core, lab) == [f"pending {cid}"]
    refactor_cid = core.candidate_id("owned-skills", "refs/heads/refactor/topic",
                                     lab["base"], refactor_tip, "skill-review-v1", "transport")
    assert refactor_cid not in "\n".join(pending_now(core, lab))

    # Main now contains T: the transport tip is consumed and drops out; the
    # unsubmitted refactor branch must still not appear.
    second = second_main_clone(lab, tmp_path)
    g(second, "merge", "-q", "--no-ff", "-m", "consume T", t)
    g(second, "push", "-q", "origin", "main")
    assert pending_now(core, lab) == []


def test_pending_includes_unacknowledged_empty_diff_tip(core, lab):
    """A same-tree tip that is not an ancestor of main is genuine pending work:
    consumption is an ancestry fact, never a diff-size shortcut."""
    g(lab["producer"], "commit", "-q", "--allow-empty", "-m", "empty acknowledgment tip")
    g(lab["producer"], "push", "-q", "origin", "machine/testlab")
    tip = g(lab["producer"], "rev-parse", "HEAD")
    cid = core.candidate_id("owned-skills", "refs/heads/machine/testlab",
                            lab["base"], tip, "skill-review-v1", "transport")
    assert pending_now(core, lab) == [f"pending {cid}"]


def test_retry_changes_monitor_once(core, lab):
    """--retry is one explicit generation step: the blocked line changes to a
    pending line exactly once per invocation and then stays byte-stable."""
    producer = lab["producer"]
    link = producer / "skills/demo/link"
    os.symlink("SKILL.md", link)
    g(producer, "add", "--", "skills/demo/link")
    g(producer, "commit", "-q", "-m", "source adds a symlink")
    g(producer, "push", "-q", "origin", "machine/testlab")

    c = core.capture(lab["publisher"], lab["store"], lab["source"])
    with pytest.raises(core.WorkflowError):
        core.prepare(lab["publisher"], lab["store"], c)
    blocked = core.load_candidate(lab["store"], c["id"])
    assert blocked["status"] == "blocked" and blocked.get("retry_generation", 0) == 0
    assert pending_now(core, lab) == [f"blocked {c['id']}"]

    retried = core.retry_candidate(lab["store"], c["id"])
    assert retried["status"] == "captured"
    assert retried["retry_generation"] == 1
    first = pending_now(core, lab)
    assert first == [f"pending {c['id']} retry 1"]
    assert pending_now(core, lab) == first                 # stable, not timestamp churn

    # A second explicit retry requires a new block and increments exactly one step.
    with pytest.raises(core.WorkflowError):
        core.retry_candidate(lab["store"], c["id"])        # captured, not blocked
    with pytest.raises(core.WorkflowError):
        core.prepare(lab["publisher"], lab["store"], c)
    again = core.retry_candidate(lab["store"], c["id"])
    assert again["retry_generation"] == 2
    assert pending_now(core, lab) == [f"pending {c['id']} retry 2"]


# ---------------------------------------------------------------------------
# B11: explicit exact-tip refactor submission and integration (packet 11).
#
# A refactor branch is never transport work: it becomes a candidate only through
# an operator submission naming the exact ref, the exact remote tip and the
# replacement brief. Publication is one merge M,T whose tree is exactly the
# submitted tip tree, so an edit after submission is refused rather than curated.
# ---------------------------------------------------------------------------

REFACTOR_REF = "refs/heads/refactor/skill-sync"
REFACTOR_TEXT = ("---\nname: demo\ndescription: Demonstration skill.\n---\n\n"
                 "# Demo\n\nRefactored base instruction.\n")


def refactor_brief(**overrides):
    brief = {
        "summary": "Rewrite the demo instruction on the refactor branch",
        "intended_replacements": [
            {"path": "skills/demo/SKILL.md",
             "old_quote": "Base instruction.",
             "new_instruction": "Refactored base instruction.",
             "reason": "The refactor replaces the one demo instruction."}
        ],
        "validation_notes": "The exact submitted tip was reviewed; no other path changes.",
    }
    brief.update(overrides)
    return brief


def refactor_review(candidate, path="skills/demo/SKILL.md"):
    return {
        "schema": 1, "candidate_id": candidate["id"],
        "main_sha": candidate["main_sha"], "source_sha": candidate["source_sha"],
        "summary": "Accept the submitted refactor wording",
        "files": [{
            "path": path, "change_type": "replacement", "decision": "accept",
            "source_anchors": [{"ref": candidate["source_sha"], "path": path,
                                "quote": "Refactored base instruction."}],
            "reason": "Intentional rewrite of the demo instruction",
            "replacements": [{"old_ref": candidate["main_sha"], "old_path": path,
                              "old_quote": "Base instruction.", "new_path": path,
                              "new_quote": "Refactored base instruction.",
                              "reason": "The reviewed refactor replacement"}],
        }],
    }


def make_refactor_branch(lab, text=REFACTOR_TEXT, ref=REFACTOR_REF):
    """The developer's own refactor branch: branch from main, commit, back it up."""
    producer = lab["producer"]
    name = ref[len("refs/heads/"):]
    g(producer, "fetch", "-q", "origin")
    g(producer, "checkout", "-q", "-b", name, "origin/main")
    tip = commit(producer, text, message="refactor the demo instruction")
    g(producer, "push", "-q", "-u", "origin", name)
    return ref, tip


def merge_main_into_refactor(lab, ref=REFACTOR_REF):
    """Merge published main into the refactor branch (never a rebase); push T."""
    producer = lab["producer"]
    name = ref[len("refs/heads/"):]
    g(producer, "fetch", "-q", "origin")
    g(producer, "checkout", "-q", name)
    g(producer, "merge", "-q", "--no-ff", "--no-edit", "-m",
      "merge origin/main into the refactor branch", "origin/main")
    tip = g(producer, "rev-parse", "HEAD")
    g(producer, "push", "-q", "origin", name)
    return tip


def prepared_refactor(core, lab, ref=REFACTOR_REF):
    """Submit, capture and prepare one refactor candidate; returns (candidate, tip)."""
    ref, tip = make_refactor_branch(lab, ref=ref)
    core.submit_refactor(lab["publisher"], lab["store"], ref, tip, refactor_brief())
    candidate = core.capture(lab["publisher"], lab["store"], {"ref": ref}, kind="refactor")
    return core.prepare(lab["publisher"], lab["store"], candidate), tip


def test_refactor_requires_explicit_tip_submission(core, lab, tmp_path):
    """F1: only refs/heads/refactor/<slug> + exact remote tip + a bounded brief
    make a refactoring candidate; a backup push alone is never pending work."""
    ref, tip = make_refactor_branch(lab)
    assert pending_now(core, lab) == []

    # No submission record: a pushed refactor branch is not ready.
    with pytest.raises(core.WorkflowError) as excinfo:
        core.capture(lab["publisher"], lab["store"], {"ref": ref}, kind="refactor")
    message = str(excinfo.value)
    assert "submit" in message and "refactor" in message

    # The brief is exactly {summary, intended_replacements[], validation_notes};
    # there is no place for a command.
    for bad in (
        {**refactor_brief(), "commands": ["rm -rf /"]},
        {"summary": "x", "intended_replacements": []},
        refactor_brief(summary=""),
        {"summary": "x", "intended_replacements": [{"path": "skills/demo/SKILL.md"}],
         "validation_notes": "y"},
        {"summary": "x", "intended_replacements": [{"path": "../escape", "old_quote": "a",
                                                    "new_instruction": "b", "reason": "c"}],
         "validation_notes": "y"},
    ):
        with pytest.raises(core.WorkflowError):
            core.submit_refactor(lab["publisher"], lab["store"], ref, tip, bad)

    # Only a refactor branch ref and an exact full remote tip may be submitted.
    for bad_ref in ("refs/heads/machine/testlab", "refactor/skill-sync", "refs/heads/refactor/"):
        with pytest.raises(core.WorkflowError):
            core.submit_refactor(lab["publisher"], lab["store"], bad_ref, tip, refactor_brief())
    for bad_tip in (lab["base"], tip[:12], "f" * 40):
        with pytest.raises(core.WorkflowError):
            core.submit_refactor(lab["publisher"], lab["store"], ref, bad_tip, refactor_brief())

    submission = core.submit_refactor(lab["publisher"], lab["store"], ref, tip, refactor_brief())
    assert submission["id"] == core.candidate_id(
        "owned-skills", ref, lab["base"], tip, "skill-review-v1", "refactor")
    assert submission["kind"] == "refactor" and submission["tip"] == tip
    assert submission["main_sha"] == lab["base"]
    assert submission["publisher_identity"] == {
        "machine": "publisher-test", "profile": "default", "scope": "shared-generic"}
    assert submission["brief_sha256"]
    assert pending_now(core, lab) == [f"pending {submission['id']}"]
    # Repeating the identical submission is idempotent; a different brief for
    # the same tip is refused (the approved content cannot be swapped).
    assert core.submit_refactor(
        lab["publisher"], lab["store"], ref, tip, refactor_brief())["id"] == submission["id"]
    with pytest.raises(core.WorkflowError):
        core.submit_refactor(lab["publisher"], lab["store"], ref, tip,
                             refactor_brief(summary="A different approval"))

    candidate = core.capture(lab["publisher"], lab["store"], {"ref": ref}, kind="refactor")
    assert candidate["kind"] == "refactor" and candidate["source_sha"] == tip
    assert candidate["main_sha"] == lab["base"]
    assert candidate["source_machine"] == "publisher-test"
    assert candidate["source_profile"] == "default"
    assert g(lab["publisher"], "rev-parse",
             f"refs/hermes-sync/candidates/{submission['id']}/source") == tip
    # The journal loads only through its submission record; retry is a status
    # refusal, not a "not registered" registration failure.
    assert core.load_candidate(lab["store"], candidate["id"])["status"] == "captured"
    with pytest.raises(core.WorkflowError) as excinfo:
        core.retry_candidate(lab["store"], candidate["id"])
    assert "blocked" in str(excinfo.value)

    # The submission is the exact authorisation: removing the record removes the
    # candidate, even though the journal file itself still exists.
    record_path = lab["store"] / "refactor-submissions" / f"{submission['id']}.json"
    saved = record_path.read_bytes()
    record_path.unlink()
    with pytest.raises(core.WorkflowError) as excinfo:
        core.load_candidate(lab["store"], candidate["id"])
    assert "submission" in str(excinfo.value)
    record_path.write_bytes(saved)
    assert core.load_candidate(lab["store"], candidate["id"])["source_sha"] == tip

    # A later refactor backup commit does not move the submitted T or its cid.
    t2 = commit(lab["producer"], REFACTOR_TEXT + "An extra refactor note.\n",
                message="more refactor work")
    g(lab["producer"], "push", "-q", "origin", REFACTOR_REF[len("refs/heads/"):])
    again = core.capture(lab["publisher"], lab["store"], {"ref": ref}, kind="refactor")
    assert again["id"] == candidate["id"] and again["source_sha"] == tip
    assert pending_now(core, lab) == [f"pending {candidate['id']}"]

    # Main moves: the submission is stale and needs a merge + renewed submission.
    second = second_main_clone(lab, tmp_path)
    advanced = independent_main_commit(second)
    with pytest.raises(core.WorkflowError) as excinfo:
        core.capture(lab["publisher"], lab["store"], {"ref": ref}, kind="refactor")
    message = str(excinfo.value)
    assert "merge" in message and advanced[:12] in message and "rebase" not in message
    with pytest.raises(core.WorkflowError) as excinfo:
        core.submit_refactor(lab["publisher"], lab["store"], ref, t2, refactor_brief())
    message = str(excinfo.value)
    assert "does not contain" in message and "main" in message and "rebase" not in message

    # Merging current main into the branch and submitting the merged tip is the
    # only path forward: new main, new tip, new cid.
    merged = merge_main_into_refactor(lab, ref)
    renewed = core.submit_refactor(lab["publisher"], lab["store"], ref, merged, refactor_brief())
    assert renewed["main_sha"] == advanced and renewed["tip"] == merged
    assert renewed["id"] != submission["id"]
    fresh = core.capture(lab["publisher"], lab["store"], {"ref": ref}, kind="refactor")
    assert fresh["id"] == renewed["id"]
    assert fresh["main_sha"] == advanced and fresh["source_sha"] == merged


def test_refactor_promotion_tree_equals_submitted_tip(core, lab, tmp_path):
    """F2: a true merge P with ordered parents [M,T] and tree(P) == tree(T);
    the source branch is untouched and main ancestry is preserved."""
    ref, fork_tip = make_refactor_branch(lab)
    second = second_main_clone(lab, tmp_path)
    advanced_main = independent_main_commit(second)
    assert advanced_main != lab["base"]
    assert core.is_ancestor(second, lab["base"], advanced_main)

    tip = merge_main_into_refactor(lab, ref)
    assert core.is_ancestor(lab["producer"], advanced_main, tip)
    submitted_tree = g(lab["producer"], "rev-parse", f"{tip}^{{tree}}")

    submission = core.submit_refactor(lab["publisher"], lab["store"], ref, tip, refactor_brief())
    candidate = core.capture(lab["publisher"], lab["store"], {"ref": ref}, kind="refactor")
    assert candidate["id"] == submission["id"]
    assert candidate["main_sha"] == advanced_main and candidate["source_sha"] == tip
    candidate = core.prepare(lab["publisher"], lab["store"], candidate)
    assert candidate["input_paths"] == ["skills/demo/SKILL.md"]

    # The native merge of current main into T is already tree(T): no agent edit.
    worktree = Path(candidate["worktree"])
    review = refactor_review(candidate)
    core.validate_review(candidate, review, lab["publisher"], worktree)
    checks = core.run_checks(candidate, worktree)
    validation = core.validate_tree(candidate, worktree, review)
    assert validation["tree"] == submitted_tree
    core.record_review(lab["store"], candidate["id"], review, checks, validation)
    current = core.load_candidate(lab["store"], candidate["id"])
    text = core.render_review(current, review, checks, validation["tree"])
    note = lab["vault"] / current["report_relative_path"]
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(text, encoding="utf-8")
    core.verify_report(current, text, lab["vault"])

    result = core.publish(lab["publisher"], lab["store"], candidate["id"], lab["vault"])
    p = result["result_sha"]
    assert g(lab["publisher"], "show", "-s", "--format=%P", p).split() == [advanced_main, tip]
    assert g(lab["publisher"], "show", "-s", "--format=%T", p) == submitted_tree
    assert result["result_parents"] == [advanced_main, tip]
    assert result["result_tree"] == submitted_tree
    # Source ref untouched; main now contains both parents.
    assert remote_ref(lab["producer"], ref) == tip
    assert remote_ref(lab["producer"], "refs/heads/main") == p
    assert core.is_ancestor(lab["publisher"], advanced_main, p)
    assert core.is_ancestor(lab["publisher"], tip, p)
    assert core.source_status(lab["publisher"], p, tip) == "consumed"

    # The receipt path is the same for a refactor: exact bytes, then complete.
    result_text = (lab["store"] / "candidates" / candidate["id"] / "result.md").read_text(
        encoding="utf-8")
    receipt = lab["vault"] / (
        f"projects/hermes-agent/reports/skill-sync-{candidate['id']}-result.md")
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(result_text, encoding="utf-8")
    assert core.verify_result(lab["store"], candidate["id"], lab["vault"])["status"] == "complete"


def test_refactor_refuses_agent_edit_after_submission(core, lab):
    """F2: unlike transport curation, an unsubmitted extra edit is refused; the
    fix must be a new refactor commit, a new tip and a new submission."""
    candidate, tip = prepared_refactor(core, lab)
    current = record_full_review(core, lab, candidate, review=refactor_review(candidate))
    assert current["status"] == "report-verified"
    submitted_tree = g(lab["publisher"], "rev-parse", f"{tip}^{{tree}}")
    worktree = Path(current["worktree"])

    extra = worktree / "skills/demo/EXTRA.md"
    extra.write_text("A helpful extra edit.\n", encoding="utf-8")
    g(worktree, "add", "--", "skills/demo/EXTRA.md")
    assert g(worktree, "write-tree") != submitted_tree

    with pytest.raises(core.WorkflowError) as excinfo:
        core.validate_tree(current, worktree, refactor_review(current))
    message = str(excinfo.value)
    assert "submitted tip" in message and "submit" in message and "rebase" not in message

    with pytest.raises(core.WorkflowError) as excinfo:
        core.publish(lab["publisher"], lab["store"], current["id"], lab["vault"])
    assert "submitted tip" in str(excinfo.value)
    assert remote_ref(lab["producer"], "refs/heads/main") == lab["base"]
    assert core.load_candidate(lab["store"], current["id"])["status"] == "report-verified"

    # Discarding the extra edit restores the exact submitted tree and publishes.
    extra.unlink()
    g(worktree, "rm", "-q", "--cached", "skills/demo/EXTRA.md")
    assert core.validate_tree(current, worktree, refactor_review(current))["tree"] == submitted_tree
    result = core.publish(lab["publisher"], lab["store"], current["id"], lab["vault"])
    assert g(lab["publisher"], "show", "-s", "--format=%T", result["result_sha"]) == submitted_tree


def test_refactor_freeze_allows_producer_commits(core, lab, tmp_path):
    """F3: the refactor promotion takes the same short publisher lock; another
    publisher refuses while a producer clone still commits and pushes."""
    candidate, tip = prepared_refactor(core, lab)
    current = record_full_review(core, lab, candidate, review=refactor_review(candidate))
    # Preparation and the whole review run without holding the publisher lock:
    # only the final promotion freezes other publishers.
    assert core.read_publisher_lock(lab["store"]) is None

    token = core.acquire_publisher_lock(lab["store"])
    try:
        with pytest.raises(core.WorkflowError) as excinfo:
            core.publish(lab["publisher"], lab["store"], current["id"], lab["vault"])
        message = str(excinfo.value).lower()
        assert "publisher" in message and "lock" in message

        producer = tmp_path / "producer-during-freeze"
        subprocess.run(["git", "clone", "-q", "-b", "machine/testlab",
                        str(lab["remote"]), str(producer)], check=True)
        for key, value in (("user.name", "Freeze"), ("user.email", "freeze@example.invalid")):
            g(producer, "config", key, value)
        transport_tip = commit(producer, OFFER_TEXT + "A producer edit during the freeze.\n",
                               message="producer work during the refactor freeze")
        g(producer, "push", "-q", "origin", "machine/testlab")
        assert remote_ref(producer, "refs/heads/machine/testlab") == transport_tip
    finally:
        core.release_publisher_lock(lab["store"], token)

    published = core.publish(lab["publisher"], lab["store"], current["id"], lab["vault"])
    p = published["result_sha"]
    assert g(lab["publisher"], "show", "-s", "--format=%P", p).split() == [lab["base"], tip]
    assert g(lab["publisher"], "show", "-s", "--format=%T", p) == g(
        lab["publisher"], "rev-parse", f"{tip}^{{tree}}")

    # The producer's freeze-time work was not consumed and is still pending.
    transport_cid = core.candidate_id("owned-skills", "refs/heads/machine/testlab",
                                      p, transport_tip, "skill-review-v1", "transport")
    # Publication is consumed, but the refactor's receipt still needs delivery.
    assert pending_now(core, lab) == sorted([
        f"pending {transport_cid}", f"recover {current['id']}"])

    # Publication moved main, so the old refactor submission is stale: it needs
    # a merge-main, a fresh review and a new exact-tip submission.
    with pytest.raises(core.WorkflowError) as excinfo:
        core.capture(lab["publisher"], lab["store"], {"ref": REFACTOR_REF}, kind="refactor")
    message = str(excinfo.value)
    assert "merge" in message and "submit" in message and "rebase" not in message
    with pytest.raises(core.WorkflowError) as excinfo:
        core.submit_refactor(lab["publisher"], lab["store"], REFACTOR_REF, tip, refactor_brief())
    assert "does not contain" in str(excinfo.value)


# ---------------------------------------------------------------------------
# G4: periodic whole-skill review cursor.
# ---------------------------------------------------------------------------

def test_periodic_review_cursor_visits_each_skill_once(core):
    """One skill per run: sorted order, resume, wrap, deletion, no repeat."""
    skills = ["skill-zulu", "skill-alpha", "skill-mike", "skill-bravo"]
    ordered = []
    last = None
    for _ in range(len(skills)):
        last = core.next_skill(skills, last)
        assert last is not None
        ordered.append(last)
    assert ordered == sorted(skills)
    assert len(set(ordered)) == len(skills)

    # The first skill is not repeated mid-cycle; the cursor wraps after the last.
    assert core.next_skill(skills, ordered[0]) == ordered[1]
    assert core.next_skill(skills, ordered[-1]) == ordered[0]

    # Duplicate names collapse; a deleted cursor resumes at its successor.
    assert core.next_skill(skills + ["skill-alpha"], None) == "skill-alpha"
    remaining = ["skill-alpha", "skill-charlie"]
    assert core.next_skill(remaining, "skill-bravo") == "skill-charlie"
    assert core.next_skill(remaining, "skill-aaa") == "skill-alpha"

    # An empty inventory produces no invented work.
    assert core.next_skill([], None) is None
    assert core.next_skill(["", None], None) is None


# ---------------------------------------------------------------------------
# H: end-to-end acceptance matrix (packet 13).
#
# Every publisher step below goes through the CORE API against a real local
# bare remote; nothing here hand-builds the integration merge or fabricates a
# process result. The test acts only as producer (real commits and pushes),
# reviewing agent (review JSON, conflict resolution, report delivery), and
# operator (refactor submission, report-specific feedback). All repository,
# state and report artifacts live under the pytest tmp dir and are test data.
# Executed on Linux; this is not a macOS claim.
# ---------------------------------------------------------------------------

ENGINE = SCRIPTS / "skill-repo-sync.py"

SECTION_TEXT = (
    "---\nname: demo\ndescription: Demonstration skill.\n---\n\n"
    "# Demo\n\nBase instruction.\n\n"
    "## Alpha\n\nAlpha base paragraph.\n\n"
    "## Beta\n\nBeta base paragraph.\n"
)


def e2e_parents(repo, sha):
    return g(repo, "show", "-s", "--format=%P", sha).split()


def e2e_tree(repo, rev):
    return g(repo, "rev-parse", f"{rev}^{{tree}}")


def e2e_main(repo):
    return remote_ref(repo, "refs/heads/main")


def e2e_note(lab, candidate):
    return lab["vault"] / candidate["report_relative_path"]


def e2e_print(node, **values):
    """Record the concrete Git facts of one acceptance node in the test output."""
    print("\ne2e[" + node + "] " + " ".join(f"{key}={value}" for key, value in values.items()))


def e2e_file(path, change_type, decision, ref, quote, reason, replacements=None):
    return {
        "path": path,
        "change_type": change_type,
        "decision": decision,
        "source_anchors": [{"ref": ref, "path": path, "quote": quote}],
        "reason": reason,
        "replacements": replacements or [],
    }


def e2e_replacement(path, old_ref, old_quote, new_quote, reason):
    return {
        "old_ref": old_ref,
        "old_path": path,
        "old_quote": old_quote,
        "new_path": path,
        "new_quote": new_quote,
        "reason": reason,
    }


def e2e_review(candidate, summary, files):
    return {
        "schema": 1,
        "candidate_id": candidate["id"],
        "main_sha": candidate["main_sha"],
        "source_sha": candidate["source_sha"],
        "summary": summary,
        "files": files,
    }


def e2e_transport_commit(repo, changes, message):
    """A real producer commit on the current transport checkout, then a push."""
    for path, text in changes.items():
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        g(repo, "add", "--", path)
    g(repo, "commit", "-q", "-m", message)
    tip = g(repo, "rev-parse", "HEAD")
    g(repo, "push", "-q", "origin", "machine/testlab")
    return tip


def e2e_publish_candidate(core, lab, candidate, review):
    """Record the review and report through CORE, then publish exactly it."""
    current = record_full_review(core, lab, candidate, review)
    assert current["status"] == "report-verified"
    return core.publish(lab["publisher"], lab["store"], current["id"], lab["vault"])


def test_e2e_two_producers_curated_merge(core, lab, tmp_path, monkeypatch):
    """Two producer clones edit disjoint paths and separate regions of one file.

    Each contribution is captured, prepared (native merge), reviewed, reported
    and published through CORE. Main contains both effects, each source tip is
    an ancestor of published main, and neither source ref is ever reset.
    """
    producer_a = lab["producer"]

    # Shared-history setup: one demo skill with two independent sections.
    g(producer_a, "checkout", "-q", "main")
    (producer_a / "skills/demo/SKILL.md").write_text(SECTION_TEXT, encoding="utf-8")
    g(producer_a, "add", "--", "skills/demo/SKILL.md")
    g(producer_a, "commit", "-q", "-m", "expand the demo skill into sections")
    m0 = g(producer_a, "rev-parse", "HEAD")
    g(producer_a, "push", "-q", "origin", "main")
    g(producer_a, "checkout", "-q", "machine/testlab")
    g(producer_a, "merge", "-q", "--ff-only", "main")
    g(producer_a, "push", "-q", "origin", "machine/testlab")

    # Producer B is a separate clone with its own registered transport ref.
    g(producer_a, "checkout", "-q", "-b", "machine/lab2", m0)
    g(producer_a, "push", "-q", "-u", "origin", "machine/lab2")
    g(producer_a, "checkout", "-q", "machine/testlab")
    producer_b = tmp_path / "producer-b"
    subprocess.run(["git", "clone", "-q", "-b", "machine/lab2", str(lab["remote"]),
                    str(producer_b)], check=True)
    for key, value in (("user.name", "Producer B"), ("user.email", "b@example.invalid")):
        g(producer_b, "config", key, value)
    second_source = {"ref": "refs/heads/machine/lab2", "machine": "lab2",
                     "profile": "default", "scope": "shared-generic", "enabled": True}
    register_source(lab, second_source)

    # A edits the Alpha region and adds a disjoint path.
    replace_text(producer_a / "skills/demo/SKILL.md", "Alpha base paragraph.",
                 "Alpha rule from producer A.")
    (producer_a / "skills/demo/alpha.md").write_text(
        "Alpha note from producer A.\n", encoding="utf-8")
    g(producer_a, "add", "--", "skills/demo/SKILL.md", "skills/demo/alpha.md")
    g(producer_a, "commit", "-q", "-m", "producer A contribution")
    ta = g(producer_a, "rev-parse", "HEAD")
    g(producer_a, "push", "-q", "origin", "machine/testlab")

    # B edits the Beta region of the same file and adds another disjoint path.
    replace_text(producer_b / "skills/demo/SKILL.md", "Beta base paragraph.",
                 "Beta rule from producer B.")
    (producer_b / "skills/demo/beta.md").write_text(
        "Beta note from producer B.\n", encoding="utf-8")
    g(producer_b, "add", "--", "skills/demo/SKILL.md", "skills/demo/beta.md")
    g(producer_b, "commit", "-q", "-m", "producer B contribution")
    tb = g(producer_b, "rev-parse", "HEAD")
    g(producer_b, "push", "-q", "origin", "machine/lab2")

    # Candidate A: M0 + TA, native clean merge, real review/checks/report.
    ca = core.capture(lab["publisher"], lab["store"], lab["source"])
    assert ca["main_sha"] == m0 and ca["source_sha"] == ta
    ca = core.prepare(lab["publisher"], lab["store"], ca)
    assert ca["conflict_paths"] == []
    assert sorted(ca["input_paths"]) == ["skills/demo/SKILL.md", "skills/demo/alpha.md"]
    review_a = e2e_review(ca, "Accept producer A's Alpha wording and disjoint note", [
        e2e_file("skills/demo/SKILL.md", "correction", "accept", ta,
                 "Alpha rule from producer A.",
                 "Producer A's reviewed wording for the Alpha section",
                 [e2e_replacement("skills/demo/SKILL.md", m0, "Alpha base paragraph.",
                                  "Alpha rule from producer A.",
                                  "Reviewed Alpha wording replaces the base paragraph")]),
        e2e_file("skills/demo/alpha.md", "addition", "accept", ta,
                 "Alpha note from producer A.", "A disjoint generic reference note"),
    ])
    ca = record_full_review(core, lab, ca, review_a)
    assert ca["status"] == "report-verified"
    note_a = e2e_note(lab, ca)
    note_a_bytes = note_a.read_bytes()
    stored_review_a = json.loads(
        (lab["store"] / "candidates" / ca["id"] / "review.json").read_text(encoding="utf-8"))
    stored_checks_a = json.loads(
        (lab["store"] / "candidates" / ca["id"] / "checks.json").read_text(encoding="utf-8"))
    assert stored_review_a["candidate_id"] == ca["id"] and stored_review_a["files"]
    assert stored_checks_a["checks"] and all(
        row["status"] in ("passed", "not-applicable") or not row["required"]
        for row in stored_checks_a["checks"])
    assert ca["id"] in note_a_bytes.decode("utf-8").replace("`", "")

    calls = record_git_calls(core, monkeypatch)
    pa = core.publish(lab["publisher"], lab["store"], ca["id"], lab["vault"])["result_sha"]
    assert_no_history_rewrite(calls)
    assert e2e_parents(lab["publisher"], pa) == [m0, ta]
    assert e2e_tree(lab["publisher"], pa) == ca["reviewed_tree"]
    assert e2e_main(producer_a) == pa

    # Candidate B: captured against the published P_A, not against M0.
    cb = core.capture(lab["publisher"], lab["store"], second_source)
    assert cb["main_sha"] == pa and cb["source_sha"] == tb
    cb = core.prepare(lab["publisher"], lab["store"], cb)
    assert cb["conflict_paths"] == []
    staged_b = (Path(cb["worktree"]) / "skills/demo/SKILL.md").read_text(encoding="utf-8")
    assert "Alpha rule from producer A." in staged_b
    assert "Beta rule from producer B." in staged_b
    review_b = e2e_review(cb, "Accept producer B's Beta wording and disjoint note", [
        e2e_file("skills/demo/SKILL.md", "correction", "accept", tb,
                 "Beta rule from producer B.",
                 "Producer B's reviewed wording for the Beta section",
                 [e2e_replacement("skills/demo/SKILL.md", pa, "Beta base paragraph.",
                                  "Beta rule from producer B.",
                                  "Reviewed Beta wording replaces the base paragraph")]),
        e2e_file("skills/demo/beta.md", "addition", "accept", tb,
                 "Beta note from producer B.", "A disjoint generic reference note"),
    ])
    cb = record_full_review(core, lab, cb, review_b)
    assert e2e_note(lab, cb).is_file()
    calls = record_git_calls(core, monkeypatch)
    pb = core.publish(lab["publisher"], lab["store"], cb["id"], lab["vault"])["result_sha"]
    assert_no_history_rewrite(calls)
    assert e2e_parents(lab["publisher"], pb) == [pa, tb]
    assert e2e_tree(lab["publisher"], pb) == cb["reviewed_tree"]

    # Main contains both contributions exactly once; no path was duplicated.
    g(producer_a, "fetch", "-q", "origin")
    final_skill = g(producer_a, "show", f"{pb}:skills/demo/SKILL.md")
    assert final_skill.count("Alpha rule from producer A.") == 1
    assert final_skill.count("Beta rule from producer B.") == 1
    assert "Alpha base paragraph." not in final_skill
    assert "Beta base paragraph." not in final_skill
    assert g(producer_a, "show", f"{pb}:skills/demo/alpha.md") == "Alpha note from producer A."
    assert g(producer_a, "show", f"{pb}:skills/demo/beta.md") == "Beta note from producer B."

    # Both source tips are ancestors of published main; both refs are untouched.
    assert e2e_parents(lab["publisher"], pb) == [pa, tb]
    assert e2e_parents(lab["publisher"], pa) == [m0, ta]
    assert core.is_ancestor(lab["publisher"], ta, pb)
    assert core.is_ancestor(lab["publisher"], tb, pb)
    assert core.is_ancestor(lab["publisher"], m0, pb)
    assert remote_ref(producer_a, "refs/heads/machine/testlab") == ta
    assert remote_ref(producer_b, "refs/heads/machine/lab2") == tb
    assert core.source_status(lab["publisher"], pb, ta) == "consumed"
    assert core.source_status(lab["publisher"], pb, tb) == "consumed"
    assert e2e_main(producer_a) == pb

    # The report bytes the publisher verified are still the immutable fixture notes.
    assert note_a.read_bytes() == note_a_bytes
    assert ca["report_sha256"] == hashlib.sha256(note_a_bytes).hexdigest()
    note_b = e2e_note(lab, cb)
    assert note_b.is_file()
    assert cb["report_sha256"] == hashlib.sha256(note_b.read_bytes()).hexdigest()
    assert ca["main_sha"] in note_a.read_text(encoding="utf-8")
    assert cb["source_sha"] in note_b.read_text(encoding="utf-8")
    assert lab["vault"].is_relative_to(tmp_path)          # generated report = test data

    e2e_print("two_producers_curated_merge", M=m0, TA=ta, TB=tb, P_A=pa, P_B=pb,
              tree_A=ca["reviewed_tree"], tree_B=cb["reviewed_tree"], main=pb)


def test_e2e_same_line_semantic_replacement(core, lab, tmp_path):
    """Main and source rewrite the same instruction; one reviewed replacement wins."""
    second = second_main_clone(lab, tmp_path, name="main-editor")
    replace_text(second / "skills/demo/SKILL.md", "Base instruction.",
                 "Base instruction, revised on main.")
    g(second, "add", "--", "skills/demo/SKILL.md")
    g(second, "commit", "-q", "-m", "main rewrites the instruction")
    g(second, "push", "-q", "origin", "main")
    m = g(second, "rev-parse", "HEAD")

    producer = lab["producer"]
    replace_text(producer / "skills/demo/SKILL.md", "Base instruction.",
                 "Base instruction, revised on the machine.")
    g(producer, "add", "--", "skills/demo/SKILL.md")
    g(producer, "commit", "-q", "-m", "source rewrites the instruction")
    t = g(producer, "rev-parse", "HEAD")
    g(producer, "push", "-q", "origin", "machine/testlab")

    c = core.capture(lab["publisher"], lab["store"], lab["source"])
    assert c["main_sha"] == m and c["source_sha"] == t
    c = core.prepare(lab["publisher"], lab["store"], c)
    assert c["conflict_paths"] == ["skills/demo/SKILL.md"]
    worktree = Path(c["worktree"])
    conflicted = (worktree / "skills/demo/SKILL.md").read_text(encoding="utf-8")
    assert "<<<<<<<" in conflicted and ">>>>>>>" in conflicted
    rows = unmerged_rows(worktree)
    assert {stage for _, stage, _, _ in rows} == {1, 2, 3}
    assert all(path == "skills/demo/SKILL.md" for path, _, _, _ in rows)

    # The agent fixture synthesises ONE coherent replacement and stages it.
    resolved_text = (BASE_TEXT.replace(
        "Base instruction.", "Base instruction, unified and reviewed."))
    (worktree / "skills/demo/SKILL.md").write_text(resolved_text, encoding="utf-8")
    g(worktree, "add", "--", "skills/demo/SKILL.md")
    assert unmerged_rows(worktree) == []
    staged = (worktree / "skills/demo/SKILL.md").read_text(encoding="utf-8")
    assert "<<<<<<<" not in staged and "=======" not in staged and ">>>>>>>" not in staged
    assert staged.count("Base instruction") == 1
    assert "unified and reviewed." in staged

    review = e2e_review(c, "Replace both same-line rewrites with one reviewed instruction", [
        e2e_file("skills/demo/SKILL.md", "replacement", "combine", t,
                 "Base instruction, revised on the machine.",
                 "Both sides rewrote the same instruction; one coherent replacement is reviewed",
                 [e2e_replacement("skills/demo/SKILL.md", m,
                                  "Base instruction, revised on main.",
                                  "Base instruction, unified and reviewed.",
                                  "Synthesised replacement removes both conflicting rewrites")]),
    ])
    core.validate_review(c, review, lab["publisher"], worktree)
    checks = core.run_checks(c, worktree)
    validation = core.validate_tree(c, worktree, review)
    core.record_review(lab["store"], c["id"], review, checks, validation)
    current = core.load_candidate(lab["store"], c["id"])
    text = core.render_review(current, review, checks, validation["tree"])
    note = lab["vault"] / current["report_relative_path"]
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(text, encoding="utf-8")
    core.verify_report(current, text, lab["vault"])

    p = core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])["result_sha"]
    assert e2e_parents(lab["publisher"], p) == [m, t]
    assert e2e_tree(lab["publisher"], p) == validation["tree"]
    g(lab["producer"], "fetch", "-q", "origin")
    final_text = g(lab["producer"], "show", f"{p}:skills/demo/SKILL.md")
    assert final_text == resolved_text.rstrip("\n")
    assert final_text.count("Base instruction") == 1
    assert "revised on main." not in final_text
    assert "revised on the machine." not in final_text
    assert remote_ref(lab["producer"], "refs/heads/machine/testlab") == t
    assert e2e_main(lab["producer"]) == p

    # The report keeps the old and new anchors it validated.
    report = note.read_text(encoding="utf-8")
    assert "Base instruction, revised on main." in report
    assert "Base instruction, unified and reviewed." in report
    assert "Synthesised replacement removes both conflicting rewrites" in report

    e2e_print("same_line_semantic_replacement", M=m, T=t, P=p,
              tree=validation["tree"], main=p)


def test_e2e_concurrent_T2_after_capture(core, lab):
    """T2 arrives during review; P still contains exactly T and no text twice."""
    t = offer(lab)
    c = record_full_review(core, lab, core.prepare(
        lab["publisher"], lab["store"],
        core.capture(lab["publisher"], lab["store"], lab["source"])))
    assert c["status"] == "report-verified"

    # A later source commit lands while the reviewed candidate is still T.
    t2 = offer(lab, OFFER_TEXT + "An extra T2 rule.\n")
    assert t2 != t and core.is_ancestor(lab["producer"], t, t2)

    p = core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])["result_sha"]
    assert e2e_parents(lab["publisher"], p) == [lab["base"], t]
    assert e2e_tree(lab["publisher"], p) == c["reviewed_tree"]
    assert remote_ref(lab["producer"], "refs/heads/machine/testlab") == t2
    assert e2e_main(lab["producer"]) == p
    assert core.is_ancestor(lab["publisher"], t, p)
    assert not core.is_ancestor(lab["publisher"], t2, p)

    # The next candidate captures T2 against published P and adds only T2's effect.
    n = core.capture(lab["publisher"], lab["store"], lab["source"])
    assert n["id"] != c["id"]
    assert n["main_sha"] == p and n["source_sha"] == t2
    assert core.source_status(lab["publisher"], p, t2) == "pending"
    n = core.prepare(lab["publisher"], lab["store"], n)
    assert n["conflict_paths"] == []
    staged = (Path(n["worktree"]) / "skills/demo/SKILL.md").read_text(encoding="utf-8")
    assert staged.count("A useful generic rule.") == 1
    assert staged.count("An extra T2 rule.") == 1
    review = e2e_review(n, "Accept only the new T2 effect on published main", [
        e2e_file("skills/demo/SKILL.md", "addition", "accept", t2,
                 "An extra T2 rule.", "A new generic rule not yet on main"),
    ])
    n = record_full_review(core, lab, n, review)
    p2 = core.publish(lab["publisher"], lab["store"], n["id"], lab["vault"])["result_sha"]
    assert e2e_parents(lab["publisher"], p2) == [p, t2]
    g(lab["producer"], "fetch", "-q", "origin")
    final_text = g(lab["producer"], "show", f"{p2}:skills/demo/SKILL.md")
    assert final_text.count("A useful generic rule.") == 1
    assert final_text.count("An extra T2 rule.") == 1
    assert remote_ref(lab["producer"], "refs/heads/machine/testlab") == t2

    e2e_print("concurrent_T2_after_capture", M=lab["base"], T=t, T2=t2, P=p, P2=p2,
              parents_P=e2e_parents(lab["publisher"], p),
              parents_P2=e2e_parents(lab["publisher"], p2),
              tree_T=c["reviewed_tree"], tree_T2=n["reviewed_tree"],
              tree_P=e2e_tree(lab["publisher"], p),
              remote_main=e2e_main(lab["producer"]),
              remote_source=remote_ref(lab["producer"], "refs/heads/machine/testlab"))


def test_e2e_refactor_while_transport_continues(core, lab, tmp_path, monkeypatch):
    """A real refactor worktree integrates as an exact-tip merge while producer C
    keeps committing and pushing transport work that is never swept."""
    producer = lab["producer"]
    m0 = lab["base"]

    # A real refactor worktree from M, on its own refactor branch.
    refactor_wt = tmp_path / "refactor-worktree"
    g(producer, "worktree", "add", "-q", "-b", "refactor/skill-sync",
      str(refactor_wt), m0)
    (refactor_wt / "skills/demo/SKILL.md").write_text(REFACTOR_TEXT, encoding="utf-8")
    g(refactor_wt, "add", "--", "skills/demo/SKILL.md")
    g(refactor_wt, "commit", "-q", "-m", "refactor the demo instruction")
    r0 = g(refactor_wt, "rev-parse", "HEAD")
    g(refactor_wt, "push", "-q", "origin", "refactor/skill-sync")

    # Producer C is an independent transport clone; it keeps working throughout.
    producer_c = tmp_path / "producer-c"
    subprocess.run(["git", "clone", "-q", "-b", "machine/testlab", str(lab["remote"]),
                    str(producer_c)], check=True)
    for key, value in (("user.name", "Producer C"), ("user.email", "c@example.invalid")):
        g(producer_c, "config", key, value)
    tc1 = e2e_transport_commit(
        producer_c, {"skills/demo/normal.md": "Normal transport contribution.\n"},
        "producer C normal contribution")

    # main advances through the ordinary reviewed path.
    c1 = core.capture(lab["publisher"], lab["store"], lab["source"])
    assert c1["main_sha"] == m0 and c1["source_sha"] == tc1
    c1 = core.prepare(lab["publisher"], lab["store"], c1)
    review_c1 = e2e_review(c1, "Accept producer C's normal contribution", [
        e2e_file("skills/demo/normal.md", "addition", "accept", tc1,
                 "Normal transport contribution.", "A normal generic transport note"),
    ])
    r1 = e2e_publish_candidate(core, lab, c1, review_c1)
    p1 = r1["result_sha"]
    assert e2e_parents(lab["publisher"], p1) == [m0, tc1]
    assert e2e_main(producer_c) == p1

    # The developer merges main into the refactor branch (never rebases) and
    # pushes the exact merged tip; producer C keeps pushing meanwhile.
    g(refactor_wt, "fetch", "-q", "origin")
    g(refactor_wt, "merge", "-q", "--no-ff", "--no-edit", "-m",
      "merge origin/main into the refactor branch", "origin/main")
    tr = g(refactor_wt, "rev-parse", "HEAD")
    g(refactor_wt, "push", "-q", "origin", "refactor/skill-sync")
    g(lab["publisher"], "fetch", "-q", "origin")
    assert core.is_ancestor(lab["publisher"], p1, tr)
    tc2 = e2e_transport_commit(
        producer_c, {"skills/demo/later.md": "A later transport contribution.\n"},
        "producer C work while the refactor is reviewed")

    # No sweep stages the refactor branch: transport capture refuses it outright
    # and the monitor lists only the unacknowledged transport tip.
    refactor_cid = core.candidate_id("owned-skills", REFACTOR_REF, p1, tr,
                                     "skill-review-v1", "refactor")
    lines = core.pending_lines(lab["publisher"], lab["store"])
    transport_cid = core.candidate_id("owned-skills", "refs/heads/machine/testlab",
                                      p1, tc2, "skill-review-v1", "transport")
    assert lines == sorted([f"pending {transport_cid}", f"recover {c1['id']}"])
    assert refactor_cid not in "\n".join(lines)
    with pytest.raises(core.WorkflowError) as excinfo:
        core.capture(lab["publisher"], lab["store"], {"ref": REFACTOR_REF}, kind="transport")
    assert "not registered" in str(excinfo.value)
    assert not (lab["store"] / "candidates" / refactor_cid).exists()

    # Explicit exact-tip submission, capture, native merge, review, true merge.
    submission = core.submit_refactor(lab["publisher"], lab["store"], REFACTOR_REF, tr,
                                      refactor_brief())
    assert submission["id"] == refactor_cid and submission["tip"] == tr
    cand = core.capture(lab["publisher"], lab["store"], {"ref": REFACTOR_REF}, kind="refactor")
    assert cand["main_sha"] == p1 and cand["source_sha"] == tr
    cand = core.prepare(lab["publisher"], lab["store"], cand)
    assert cand["input_paths"] == ["skills/demo/SKILL.md"]
    cand = record_full_review(core, lab, cand, refactor_review(cand))

    # Producer C advances once more during the final review/promotion window.
    tc3 = e2e_transport_commit(
        producer_c, {"skills/demo/even-later.md": "Yet another transport contribution.\n"},
        "producer C work during the refactor promotion")
    calls = record_git_calls(core, monkeypatch)
    p2 = core.publish(lab["publisher"], lab["store"], cand["id"], lab["vault"])["result_sha"]
    assert_no_history_rewrite(calls)

    # P has ordered parents [M,T] and tree(P) == tree(submitted T).
    assert e2e_parents(lab["publisher"], p2) == [p1, tr]
    assert e2e_tree(lab["publisher"], p2) == e2e_tree(lab["publisher"], tr)
    assert cand["reviewed_tree"] == e2e_tree(lab["publisher"], tr)
    assert e2e_main(producer_c) == p2

    # The refactor source ref and worktree are untouched (no reset/rebase/force).
    assert remote_ref(producer, REFACTOR_REF) == tr
    assert g(refactor_wt, "rev-parse", "HEAD") == tr
    assert g(refactor_wt, "branch", "--show-current") == "refactor/skill-sync"
    assert g(refactor_wt, "status", "--porcelain") == ""

    # Producer C's last work is still pending; it was not swept into the refactor.
    g(producer_c, "fetch", "-q", "origin")
    assert "Yet another transport contribution." in g(
        producer_c, "show", f"{tc3}:skills/demo/even-later.md")
    assert "even-later.md" not in g(producer_c, "ls-tree", "-r", "--name-only", p2).split()
    pending_after = core.pending_lines(lab["publisher"], lab["store"])
    transport_cid_after = core.candidate_id(
        "owned-skills", "refs/heads/machine/testlab", p2, tc3,
        "skill-review-v1", "transport")
    assert pending_after == sorted([
        f"pending {transport_cid_after}", f"recover {c1['id']}", f"recover {cand['id']}"])
    assert core.source_status(lab["publisher"], p2, tr) == "consumed"
    assert core.source_status(lab["publisher"], p2, tc1) == "consumed"

    e2e_print("refactor_while_transport_continues", M0=m0, R0=r0, M1=p1, T=tr, P=p2,
              TC1=tc1, TC2=tc2, TC3=tc3, tree_P=e2e_tree(lab["publisher"], p2))


def test_e2e_report_failure_then_retry(core, lab, monkeypatch):
    """A missing report blocks publication before any push; the same candidate
    publishes exactly once after the fixture report is written and verified."""
    t = offer(lab)
    c = core.capture(lab["publisher"], lab["store"], lab["source"])
    c = core.prepare(lab["publisher"], lab["store"], c)
    worktree = Path(c["worktree"])
    review = review_for(c)
    core.validate_review(c, review, lab["publisher"], worktree)
    checks = core.run_checks(c, worktree)
    validation = core.validate_tree(c, worktree, review)
    core.record_review(lab["store"], c["id"], review, checks, validation)
    c = core.load_candidate(lab["store"], c["id"])
    assert c["status"] == "reviewed"
    expected_text = core.render_review(c, review, checks, validation["tree"])
    note = lab["vault"] / c["report_relative_path"]
    assert not note.exists()

    calls = record_git_calls(core, monkeypatch)
    with pytest.raises(core.WorkflowError) as excinfo:
        core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    assert "report-verified" in str(excinfo.value)
    with pytest.raises(core.WorkflowError) as excinfo:
        core.verify_report(c, expected_text, lab["vault"])
    assert "missing" in str(excinfo.value)
    assert not any(args and args[0] in ("push", "commit-tree") for args in calls)
    assert remote_ref(lab["producer"], "refs/heads/main") == lab["base"]
    assert remote_ref(lab["producer"], "refs/heads/machine/testlab") == t
    assert core.load_candidate(lab["store"], c["id"])["status"] == "reviewed"

    # The fixture report is written later; exact bytes verify, same candidate publishes.
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(expected_text, encoding="utf-8")
    verified = core.verify_report(c, expected_text, lab["vault"])
    assert verified["status"] == "report-verified"

    calls = record_git_calls(core, monkeypatch)
    p = core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])["result_sha"]
    assert len([args for args in calls if args and args[0] == "push"]) == 1
    assert e2e_parents(lab["publisher"], p) == [lab["base"], t]
    assert e2e_tree(lab["publisher"], p) == validation["tree"]
    assert e2e_main(lab["producer"]) == p
    assert remote_ref(lab["producer"], "refs/heads/machine/testlab") == t
    count = int(g(lab["publisher"], "rev-list", "--count", p))
    assert count == 3

    # A repeat call reuses the saved P and adds no integration commit or push.
    calls = record_git_calls(core, monkeypatch)
    again = core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    assert again["result_sha"] == p
    assert not any(args and args[0] in ("push", "commit-tree") for args in calls)
    assert int(g(lab["publisher"], "rev-list", "--count", p)) == count
    assert e2e_main(lab["producer"]) == p
    assert core.source_status(lab["publisher"], p, t) == "consumed"

    e2e_print("report_failure_then_retry", M=lab["base"], T=t, P=p, count=count)


def test_e2e_crash_after_publish_then_reconcile(core, lab, monkeypatch):
    """The push succeeds, the published-status write raises, and reconcile repairs
    the journal from saved P without a second merge; the receipt is idempotent."""
    t = offer(lab)
    c = reviewed(core, lab)
    real_write = core._write_candidate_state
    crashed = {"raised": False}

    def dying_write(store, cid, state):
        if state.get("status") == "published" and not crashed["raised"]:
            crashed["raised"] = True
            raise OSError("simulated disk failure writing the published status")
        return real_write(store, cid, state)

    monkeypatch.setattr(core, "_write_candidate_state", dying_write)
    with pytest.raises(OSError) as excinfo:
        core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])
    assert "published status" in str(excinfo.value)
    monkeypatch.setattr(core, "_write_candidate_state", real_write)

    interrupted = core.load_candidate(lab["store"], c["id"])
    p = interrupted["result_sha"]
    assert interrupted["status"] == "publish-intent"
    assert interrupted["published_main"] == ""
    assert e2e_main(lab["producer"]) == p            # the real push did land
    assert e2e_parents(lab["publisher"], p) == [lab["base"], t]
    count = int(g(lab["publisher"], "rev-list", "--count", p))
    assert count == 3
    # The publisher lock was released by the crash path and can be reacquired.
    token = core.acquire_publisher_lock(lab["store"])
    core.release_publisher_lock(lab["store"], token)

    calls = record_git_calls(core, monkeypatch)
    reconciled = core.reconcile(lab["publisher"], lab["store"], c["id"])
    no_publication_writes(calls)
    assert reconciled["status"] in ("published", "receipt-pending")
    assert reconciled["result_sha"] == p and reconciled["published_main"] == p
    assert e2e_main(lab["producer"]) == p
    assert int(g(lab["publisher"], "rev-list", "--count", p)) == count

    # Receipt delivery and its repeat are pure state/read work.
    payload = store_result_text(lab, c["id"])
    receipt = receipt_path(lab, c["id"])
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(payload, encoding="utf-8")
    calls = record_git_calls(core, monkeypatch)
    first = core.verify_result(lab["store"], c["id"], lab["vault"])
    assert first["status"] == "complete"
    assert first["receipt_sha256"] == hashlib.sha256(receipt.read_bytes()).hexdigest()
    second = core.verify_result(lab["store"], c["id"], lab["vault"])
    assert second["status"] == "complete"
    assert second["receipt_sha256"] == first["receipt_sha256"]
    assert store_result_text(lab, c["id"]) == payload
    no_publication_writes(calls)

    repeated = core.reconcile(lab["publisher"], lab["store"], c["id"])
    assert repeated["status"] == "complete" and repeated["result_sha"] == p
    assert int(g(lab["publisher"], "rev-list", "--count", p)) == count
    assert e2e_main(lab["producer"]) == p
    assert receipt_path(lab, c["id"]).read_text(encoding="utf-8") == payload

    e2e_print("crash_after_publish_then_reconcile", M=lab["base"], T=t, P=p,
              count=count, receipt_sha=first["receipt_sha256"])


def test_e2e_invalid_scope_does_not_leak_report(core, lab):
    """Unregistered and mixed-trust captures are refused before content is
    rendered; the diagnostic names only a non-sensitive source identifier."""
    producer = lab["producer"]
    marker = "PRIVATE_VAULT_MARKER_7c41e2_SHOULD_NOT_LEAK"
    (producer / "private/notes.md").parent.mkdir(parents=True, exist_ok=True)
    (producer / "private/notes.md").write_text(marker + "\n", encoding="utf-8")
    g(producer, "add", "--", "private/notes.md")
    g(producer, "commit", "-q", "-m", "private mixed-trust content")
    tip = g(producer, "rev-parse", "HEAD")
    g(producer, "push", "-q", "origin", "machine/testlab")
    g(producer, "push", "-q", "origin", "HEAD:refs/heads/machine/private-lab")
    private_tip = tip

    vault_before = sorted(path.relative_to(lab["vault"]).as_posix()
                          for path in lab["vault"].rglob("*") if path.is_file())
    assert vault_before == []
    main_before = remote_ref(producer, "refs/heads/main")

    # 1. A ref that is not registered for this publisher.
    with pytest.raises(core.WorkflowError) as excinfo:
        core.capture(lab["publisher"], lab["store"],
                     {"ref": "refs/heads/machine/unregistered"})
    message = str(excinfo.value)
    assert "not registered" in message
    assert "refs/heads/machine/unregistered" in message
    assert marker not in message

    # 2. A caller trying to override the registry's mixed-trust identity.
    with pytest.raises(core.WorkflowError) as excinfo:
        core.capture(lab["publisher"], lab["store"], {
            "ref": "refs/heads/machine/testlab",
            "machine": "private-machine",
            "profile": "private-profile",
            "scope": "profile-private",
        })
    message = str(excinfo.value)
    assert "does not match the publisher registry" in message
    assert "refs/heads/machine/testlab" in message
    assert marker not in message

    # Nothing was fetched, rendered, journaled or reported: no leak anywhere.
    assert not (lab["store"] / "candidates").exists()
    assert not (lab["store"] / "worktrees").exists()
    assert g(lab["publisher"], "for-each-ref", "--format=%(refname)", "refs/hermes-sync") == ""
    absent = subprocess.run(
        ["git", "-C", str(lab["publisher"]), "rev-parse", "--verify", "--quiet",
         "refs/remotes/origin/machine/unregistered"],
        capture_output=True, text=True, env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))
    assert absent.returncode != 0
    assert sorted(path.relative_to(lab["vault"]).as_posix()
                  for path in lab["vault"].rglob("*") if path.is_file()) == vault_before
    for path in lab["store"].rglob("*"):
        if path.is_file():
            assert marker not in path.read_text(encoding="utf-8", errors="replace")
    assert remote_ref(producer, "refs/heads/main") == main_before
    assert remote_ref(producer, "refs/heads/machine/testlab") == private_tip
    assert remote_ref(producer, "refs/heads/machine/private-lab") == private_tip

    e2e_print("invalid_scope_does_not_leak_report", tip=private_tip,
              main=main_before, vault_files=len(vault_before),
              diagnostic_ref="refs/heads/machine/testlab")


def test_e2e_optional_feedback_corrects_current_state(core, lab):
    """Report-specific feedback prepares a correction against the LATEST main,
    keeps unrelated later changes, and never rewrites the original report."""
    producer = lab["producer"]

    # P1: the reviewed rule that will later be corrected.
    t1 = e2e_transport_commit(
        producer,
        {"skills/demo/SKILL.md": BASE_TEXT + "Always use tabs for indentation.\n"},
        "add the indentation rule")
    c1 = core.capture(lab["publisher"], lab["store"], lab["source"])
    c1 = core.prepare(lab["publisher"], lab["store"], c1)
    r1 = e2e_review(c1, "Accept the indentation rule", [
        e2e_file("skills/demo/SKILL.md", "addition", "accept", t1,
                 "Always use tabs for indentation.", "A generic indentation rule"),
    ])
    r1 = e2e_publish_candidate(core, lab, c1, r1)
    p1 = r1["result_sha"]
    assert e2e_parents(lab["publisher"], p1) == [lab["base"], t1]

    # P2: another contribution edits the same skill and removes unrelated old bytes.
    g(producer, "fetch", "-q", "origin")
    g(producer, "merge", "-q", "--ff-only", "origin/main")
    t2 = e2e_transport_commit(
        producer,
        {"skills/demo/SKILL.md": "# Demo\n\nAlways use tabs for indentation.\n"
                                  "Document every command with one example.\n"},
        "later contribution on the same skill")
    c2 = core.capture(lab["publisher"], lab["store"], lab["source"])
    assert c2["main_sha"] == p1 and c2["source_sha"] == t2
    c2 = core.prepare(lab["publisher"], lab["store"], c2)
    r2 = e2e_review(c2, "Accept the later contribution that removes an obsolete line", [
        e2e_file("skills/demo/SKILL.md", "correction", "accept", t2,
                 "Document every command with one example.",
                 "Later contribution reviewed against the current skill"),
    ])
    r2 = e2e_publish_candidate(core, lab, c2, r2)
    p2 = r2["result_sha"]
    assert e2e_parents(lab["publisher"], p2) == [p1, t2]

    # The original report stays exactly as reviewed, including the bad rule.
    original_note = e2e_note(lab, r1)
    original_bytes = original_note.read_bytes()
    original_sha = hashlib.sha256(original_bytes).hexdigest()
    assert r1["report_sha256"] == original_sha
    assert "Always use tabs for indentation." in original_bytes.decode("utf-8")

    # User feedback on that report corrects the rule on top of the LATEST main.
    g(producer, "fetch", "-q", "origin")
    g(producer, "merge", "-q", "--ff-only", "origin/main")
    t3 = e2e_transport_commit(
        producer,
        {"skills/demo/SKILL.md": "# Demo\n\nPrefer spaces and follow repository style.\n"
                                  "Document every command with one example.\n"},
        "apply report-specific feedback")
    c3 = core.capture(lab["publisher"], lab["store"], lab["source"])
    assert c3["main_sha"] == p2 and c3["source_sha"] == t3
    assert c3["main_sha"] != c1["main_sha"]
    c3 = core.prepare(lab["publisher"], lab["store"], c3)
    review3 = e2e_review(
        c3, "Apply report-specific feedback to the current skill state", [
            e2e_file("skills/demo/SKILL.md", "correction", "accept", t3,
                     "Prefer spaces and follow repository style.",
                     "User feedback on the earlier report corrects only the indentation rule",
                     [e2e_replacement("skills/demo/SKILL.md", p2,
                                      "Always use tabs for indentation.",
                                      "Prefer spaces and follow repository style.",
                                      "The reviewed tabs rule is replaced per user feedback")]),
        ])
    r3 = e2e_publish_candidate(core, lab, c3, review3)
    p3 = r3["result_sha"]
    assert e2e_parents(lab["publisher"], p3) == [p2, t3]
    assert e2e_tree(lab["publisher"], p3) == r3["reviewed_tree"]

    g(producer, "fetch", "-q", "origin")
    final_text = g(producer, "show", f"{p3}:skills/demo/SKILL.md")
    assert final_text.count("Prefer spaces and follow repository style.") == 1
    assert "Always use tabs for indentation." not in final_text
    assert "Document every command with one example." in final_text
    assert "Base instruction." not in final_text          # unrelated old bytes stay removed

    # The original report is still byte-identical; the correction has its own report.
    assert original_note.read_bytes() == original_bytes
    assert hashlib.sha256(original_note.read_bytes()).hexdigest() == original_sha
    assert "Prefer spaces and follow repository style." not in original_bytes.decode("utf-8")
    correction_note = e2e_note(lab, r3).read_text(encoding="utf-8")
    assert "Always use tabs for indentation." in correction_note
    assert "Prefer spaces and follow repository style." in correction_note
    assert "per user feedback" in correction_note
    assert remote_ref(producer, "refs/heads/machine/testlab") == t3
    assert e2e_main(producer) == p3

    e2e_print("optional_feedback_corrects_current_state", P1=p1, P2=p2, P3=p3,
              latest_M=c3["main_sha"], T3=t3,
              original_report_sha=original_sha)


def test_e2e_no_change_monitor_is_quiet(core, lab, tmp_path):
    """A same-tree tip gets one reported merge acknowledgment; the producer FF
    refresh adds no commit and the monitor then stays quiet."""
    producer = lab["producer"]
    g(producer, "commit", "-q", "--allow-empty", "-m", "empty acknowledgment tip")
    t = g(producer, "rev-parse", "HEAD")
    g(producer, "push", "-q", "origin", "machine/testlab")
    assert e2e_tree(producer, t) == e2e_tree(producer, lab["base"])
    assert not core.is_ancestor(producer, t, lab["base"])

    cid = core.candidate_id("owned-skills", "refs/heads/machine/testlab",
                            lab["base"], t, "skill-review-v1", "transport")
    assert pending_now(core, lab) == [f"pending {cid}"]

    c = core.capture(lab["publisher"], lab["store"], lab["source"])
    assert c["main_sha"] == lab["base"] and c["source_sha"] == t
    c = core.prepare(lab["publisher"], lab["store"], c)
    assert c["input_paths"] == [] and c["conflict_paths"] == []
    review = {
        "schema": 1, "candidate_id": c["id"], "main_sha": c["main_sha"],
        "source_sha": c["source_sha"],
        "summary": "Consume an unacknowledged empty tip: the tree is unchanged and "
                   "there is no canonical content to merge",
        "files": [],
    }
    c = record_full_review(core, lab, c, review)
    p = core.publish(lab["publisher"], lab["store"], c["id"], lab["vault"])["result_sha"]
    assert e2e_parents(lab["publisher"], p) == [lab["base"], t]
    assert e2e_tree(lab["publisher"], p) == e2e_tree(lab["publisher"], lab["base"])
    assert e2e_main(producer) == p
    assert core.source_status(lab["publisher"], p, t) == "consumed"
    report = (lab["vault"] / c["report_relative_path"]).read_text(encoding="utf-8")
    assert "empty" in report.lower() and "acknowledges an empty-net candidate" in report
    assert pending_now(core, lab) == [f"recover {c['id']}"]
    # Consumed input is not completion: only exact receipt delivery makes it quiet.
    published = core.load_candidate(lab["store"], c["id"])
    receipt_path(lab, c["id"]).write_text(core.render_result(published), encoding="utf-8")
    assert core.verify_result(lab["store"], c["id"], lab["vault"])["status"] == "complete"
    assert pending_now(core, lab) == []

    # The producer's session-start refresh fast-forwards consumed work only.
    home = tmp_path / "producer-home"
    home.mkdir()
    (home / "skill-repo-sync.json").write_text(json.dumps({
        "version": "2.0.0",
        "machine": "testlab",
        "ledger_cursor": 0,
        "repos": [{"name": producer.name, "path": str(producer), "remote": "origin"}],
    }), encoding="utf-8")
    commits_before = int(g(lab["publisher"], "rev-list", "--count", p))
    head_before = g(producer, "rev-parse", "HEAD")
    assert head_before == t
    env = dict(os.environ, HERMES_HOME=str(home), GIT_TERMINAL_PROMPT="0")
    result = subprocess.run([sys.executable, str(ENGINE), "--sync-from-main", "--verbose"],
                            env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "fast-forwarded" in (result.stdout + result.stderr).lower()
    assert g(producer, "rev-parse", "HEAD") == p
    assert g(producer, "branch", "--show-current") == "machine/testlab"
    assert g(producer, "status", "--porcelain") == ""
    assert int(g(producer, "rev-list", "--count", p)) == commits_before
    assert "Fast-forward" in g(producer, "reflog", "-1", "--format=%gs")
    assert remote_ref(producer, "refs/heads/machine/testlab") == t
    assert e2e_main(producer) == p
    assert pending_now(core, lab) == []

    # A second refresh and monitor pass create nothing and report nothing.
    again = subprocess.run([sys.executable, str(ENGINE), "--sync-from-main", "--verbose"],
                           env=env, capture_output=True, text=True)
    assert again.returncode == 0, again.stdout + again.stderr
    assert "already at origin/main" in (again.stdout + again.stderr).lower()
    assert g(producer, "rev-parse", "HEAD") == p
    assert int(g(producer, "rev-list", "--count", p)) == commits_before
    assert pending_now(core, lab) == []
    assert pending_now(core, lab) == []

    e2e_print("no_change_monitor_is_quiet", M=lab["base"], T=t, P=p,
              tree=e2e_tree(lab["publisher"], p), commits=commits_before)
