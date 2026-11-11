#!/usr/bin/env python3
# skill_repo_workflow — shared core for the shared-skill repository workflow (v3).
#
# WORKFLOW_SCHEMA: 3
# CORE_VERSION: 3.0.0
# Part of the skill-library-maintenance skill. CLI adapters
# (skill-repo-sync.py, skill-repo-maintain.py, install-skill-repo-sync.py)
# import this module from their script directory; it is a library and owns no
# command surface of its own.
#
# Scope of this unit (OpenSpec change skill-sync-v3, packets 03-07):
#   * pure state helpers: canonical JSON bytes, candidate identity, atomic
#     state writes, strict JSON reads, safe relative paths
#   * strict maintainer registry/config validation
#   * git() with argument lists, no terminal prompt, batch-mode SSH, timeouts
#   * ancestry: is_ancestor(), source_status() (consumed == T is an ancestor of
#     main; no diff-size or empty-diff shortcut)
#   * capture(): fetch once, resolve M and T from the fetched remote-tracking
#     refs, pin both commits under refs/hermes-sync/candidates/<cid>/, and
#     persist an idempotent candidate journal in an absolute store path
#   * validate_source_history(): cooperative transport provenance guard that
#     refuses unpublished side-parent merges and known unfinished refactor
#     ancestry
#   * prepare(): precheck supported blob modes, create a detached candidate
#     worktree outside runtime/report roots, disable hooks/rerere locally and
#     run one native `git merge --no-ff --no-commit T`, keeping MERGE_HEAD so
#     the complete index (or the genuine conflicts) is the candidate artifact
#   * validate_review(): exact path coverage, real source quotes at captured
#     M/T/merge bases, old->new replacement proof and an advisory
#     instance-scope check; unknown review fields (commands, flags) are refused
#   * validate_tree(): HEAD==M, MERGE_HEAD==T, no unmerged/dirty content,
#     `git diff --cached --check`, `git write-tree` and in-memory validation of
#     the staged blobs; returns only {tree, paths}, never a success flag
#   * run_checks(): fixed allowlisted adapters with real exit codes/output and
#     honest not-applicable rows; the worktree must be unchanged afterwards
#   * record_review(): reloads the authoritative journal/config, requires green
#     required checks and the current tree, persists review/checks/digest/tree
#     atomically and advances to `reviewed`
#   * render_review()/verify_report(): deterministic payload (captured
#     timestamp, no wall clock) saved only under the store, then exact-byte
#     read-back at the configured report root before `report-verified`
#   * acquire_maintainer_lock()/release_maintainer_lock(): one owner-token lock
#     at <maintainer git-common-dir>/hermes-sync/maintainer.lock created with
#     atomic O_CREAT|O_EXCL; every linked worktree and alternate state store of
#     the same maintainer clone contends on it, release requires the matching
#     token, and there is no age expiry, TTL override or cron-claim heuristic
#   * acquire_contributor_lock()/release_contributor_lock(): the same owner-token
#     mechanism at the PRODUCER repo's common dir (hermes-sync/contributor.lock),
#     used only for the short staging and pre-integration merge/push operations
#   * screen_source_history(): walks the entire unpublished range
#     `tip ^ base_tip` and reports forbidden paths / suspected credential
#     patterns as path + category only — never the matched value, line or blob
#   * history_review_digest(): digest binding an agent's semantic profile-scope
#     review to one tip and its exact commit rows
#   * pending_lines(): the stable monitor protocol — sorted `pending <cid>` /
#     `blocked <cid>` lines for enabled registered machine/* tips that are not
#     ancestors of integrated main, plus submitted refactor candidates. Independent
#     journal recovery emits `recover <cid>` / `incident <cid>` after consumption
#     too; retry suffixes affect existing pending/blocked lines only
#   * next_skill(): deterministic one-skill-per-run cursor for the periodic
#     whole-skill review (sorted, de-duplicated, deletion-safe, wrapping)
#   * retry_candidate(): one explicit generation step for a blocked candidate
#   * integrate()/reconcile()/render_result(): promotion re-reads and revalidates
#     review/tree/report/registry, requires remote main to remain the captured
#     M while tolerating a source T2, forms P with `git commit-tree <tree>
#     -p M -p T` (ordered parents, no second merge, no hooks, repo-local
#     process identity), persists integrate-intent before a non-force push,
#     confirms the result with `git ls-remote` plus fetched ancestry, and makes
#     repeated calls reconcile the saved P instead of creating a new commit
#
# Deliberately NOT implemented here (later packet, contracts.md 2.1):
#   submit_refactor(). Receipt delivery is implemented (verify_result); a
#   refactor candidate is only ever listed by pending_lines once a journal
#   exists, because packet 11 owns the submitted-refactor entry point.
#
# Design rules this module enforces:
#   * identity binds repo_id, source ref, full M, full T, policy and kind;
#     timestamps and local paths never enter the hash
#   * candidate journals are trusted local workflow state, source/review text
#     is data and is never executed
#   * the store is an absolute caller-provided path; capture never uses a
#     scratch directory inside a tracked repository
#   * capture does not check out, reset, merge or stage anything in the
#     maintainer clone: HEAD and the index stay exactly as found
#   * preparation never resets, rebases, force-applies text or defaults to
#     "ours": Git's own three-way merge builds the index, and unresolvable
#     inputs block instead of being repaired silently
#   * the transport guard is cooperative provenance, not an adversarial
#     security boundary (see references/shared-repo-sync.md)
from __future__ import annotations

import ast
import hashlib
import json
import os
import posixpath
import re
import socket
import stat
import subprocess
from contextlib import contextmanager
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

WORKFLOW_SCHEMA = 3
CORE_VERSION = "3.0.0"

STATE_DIR = "candidates"
STATE_FILE = "state.json"
WORKTREES_DIR = "worktrees"
HOOKS_DISABLED_DIR = "hooks-disabled"
PIN_ROOT = "refs/hermes-sync/candidates"
MAIN_BRANCH = "main"
PUBLISHER_LOCK_DIR = "hermes-sync"
PUBLISHER_LOCK_NAME = "maintainer.lock"
PUBLISHER_LOCK_SCHEMA = 1
# A contributor checkout has its own short-operation lock: staging and the
# pre-integration merge/push must never interleave, while the maintainer's
# integration lock stays a different repository and a different file.
PRODUCER_LOCK_NAME = "contributor.lock"
PRODUCER_LOCK_SCHEMA = 1

# Semantic classifications an agent may record per unpublished source commit.
# The mechanical screen cannot prove profile scope; this is the agent's answer,
# bound to the exact tip and the exact commit set it was written for.
HISTORY_REVIEW_SCHEMA = 1
HISTORY_CLASSIFICATIONS = (
    "generic-only",
    "no-profile-content",
    "profile-content-removed",
)

# Candidate merge inputs are regular text blobs only. A deletion is the
# all-zero new mode; symlinks and gitlinks are unsupported artifacts.
MODE_FILE = "100644"
MODE_EXECUTABLE = "100755"
MODE_DELETED = "000000"
MODE_SYMLINK = "120000"
MODE_GITLINK = "160000"
SUPPORTED_MODES = frozenset({MODE_FILE, MODE_EXECUTABLE, MODE_DELETED})
# Attribute values handled by Git itself. Any other `merge=<name>` needs an
# external command from configuration, which preparation refuses to execute.
BUILTIN_MERGE_DRIVERS = frozenset({"text", "binary", "union", "normal"})

KINDS = ("transport", "refactor")
STATUSES = (
    "captured",
    "prepared",
    "reviewed",
    "report-verified",
    "integrate-intent",
    "integrated",
    "receipt-pending",
    "complete",
    "blocked",
    "stale",
)
# Statuses that may only exist with a recorded reviewed tree/review digest.
_REVIEWED_STATUSES = frozenset(
    {"reviewed", "report-verified", "integrate-intent", "integrated", "receipt-pending", "complete"}
)
# Statuses that may only exist with a recorded result commit P.
_RESULT_STATUSES = frozenset({"integrated", "receipt-pending", "complete"})
# A saved P may already exist here; only reconciliation or receipt work is
# allowed, never a second integration commit.
_RECONCILABLE_STATUSES = frozenset(
    {"integrate-intent", "integrated", "receipt-pending", "complete"}
)

_SHA_RE = re.compile(r"\A[0-9a-f]{40}(?:[0-9a-f]{24})?\Z")
_DIGEST_RE = re.compile(r"\A[0-9a-f]{64}\Z")
_CID_RE = _DIGEST_RE
_REMOTE_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]*\Z")
_REF_BAD_CHARS = frozenset(" ~^:?*[\\")

# A fetch of a big shared repository can legitimately take a while; every
# other local Git call is expected to finish quickly.
GIT_TIMEOUT = 120
FETCH_TIMEOUT = 300

__all__ = [
    "WorkflowError",
    "WORKFLOW_SCHEMA",
    "CORE_VERSION",
    "KINDS",
    "STATUSES",
    "REVIEW_SCHEMA",
    "CHANGE_TYPES",
    "DECISIONS",
    "CHECK_STATUSES",
    "canonical_bytes",
    "candidate_id",
    "atomic_json",
    "read_json",
    "safe_relative",
    "git",
    "git_bytes",
    "is_ancestor",
    "source_status",
    "git_common_dir",
    "contributor_lock_path",
    "read_contributor_lock",
    "acquire_contributor_lock",
    "release_contributor_lock",
    "screen_source_history",
    "history_review_digest",
    "HISTORY_REVIEW_SCHEMA",
    "HISTORY_CLASSIFICATIONS",
    "load_maintainer_config",
    "load_candidate",
    "capture",
    "prepare",
    "validate_source_history",
    "validate_review",
    "validate_tree",
    "run_checks",
    "record_review",
    "render_review",
    "verify_report",
    "integrate",
    "reconcile",
    "render_result",
    "verify_result",
    "pending_lines",
    "retry_candidate",
]


class WorkflowError(RuntimeError):
    """A refused workflow operation with a stable, human-readable message."""


# ---------------------------------------------------------------------------
# Small validation helpers
# ---------------------------------------------------------------------------


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise WorkflowError(f"{field} must be text")
    text = value.strip()
    if not text:
        raise WorkflowError(f"{field} must not be empty")
    if text != value:
        raise WorkflowError(f"{field} must not have leading or trailing whitespace")
    return text


def _text_in(value: Any, field: str, allowed: Iterable[str]) -> str:
    text = _text(value, field)
    if text not in allowed:
        raise WorkflowError(f"{field} must be one of: {', '.join(sorted(allowed))}")
    return text


def _absolute_text(value: Any, field: str) -> str:
    text = _text(value, field)
    if not Path(text).is_absolute():
        raise WorkflowError(f"{field} must be an absolute path: {text}")
    return text


def _boolean(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise WorkflowError(f"{field} must be true or false")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise WorkflowError(f"{field} must be a JSON object")
    return value


def _list(value: Any, field: str) -> list:
    if not isinstance(value, list):
        raise WorkflowError(f"{field} must be a JSON array")
    return value


def _is_full_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(_SHA_RE.match(value))


def _is_digest(value: Any) -> bool:
    return isinstance(value, str) and bool(_DIGEST_RE.match(value))


def _validate_branch_ref(value: Any, field: str = "source ref") -> str:
    ref = _text(value, field)
    if not ref.startswith("refs/heads/"):
        raise WorkflowError(f"{field} must be a branch ref under refs/heads/: {ref}")
    name = ref[len("refs/heads/"):]
    if not name or name.startswith("/") or name.endswith("/") or name.endswith("."):
        raise WorkflowError(f"{field} is not a valid branch ref: {ref}")
    if "//" in name or ".." in name or "@{" in name:
        raise WorkflowError(f"{field} is not a valid branch ref: {ref}")
    if any(ch in _REF_BAD_CHARS or ord(ch) < 0x20 or ord(ch) == 0x7F for ch in name):
        raise WorkflowError(f"{field} is not a valid branch ref: {ref}")
    if any(part.startswith(".") or part.endswith(".lock") for part in name.split("/")):
        raise WorkflowError(f"{field} is not a valid branch ref: {ref}")
    return ref


def _validate_git_path(value: Any, field: str) -> str:
    path = _text(value, field)
    if path.startswith(("/", "\\", "~")):
        raise WorkflowError(f"{field} must be relative: {path}")
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts) or "\\" in path:
        raise WorkflowError(f"{field} is not a safe relative Git path: {path}")
    return path


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Pure state helpers
# ---------------------------------------------------------------------------


def canonical_bytes(value: dict) -> bytes:
    """Deterministic UTF-8 JSON bytes for identity and state hashing."""
    if not isinstance(value, dict):
        raise WorkflowError("canonical JSON requires an object")
    try:
        text = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise WorkflowError(f"value is not canonical JSON: {exc}") from exc
    return text.encode("utf-8")


def candidate_id(repo_id: str, ref: str, main: str, tip: str, policy: str, kind: str) -> str:
    """Full sha256 identity of declared inputs; no timestamps or local paths."""
    repo_id = _text(repo_id, "repo_id")
    ref = _validate_branch_ref(ref, "source ref")
    main = _text(main, "main")
    tip = _text(tip, "source tip")
    policy = _text(policy, "policy")
    kind = _text_in(kind, "kind", KINDS)
    payload = {
        "schema": WORKFLOW_SCHEMA,
        "kind": kind,
        "repo_id": repo_id,
        "ref": ref,
        "main": main,
        "tip": tip,
        "policy": policy,
    }
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def atomic_json(path: Path, value: dict) -> None:
    """Write JSON atomically with a unique sibling temp file.

    The parent directory must already exist: an atomic write must never create
    a new directory tree outside the caller's validated store.
    """
    target = Path(path)
    parent = target.parent
    if not parent.is_dir():
        raise WorkflowError(f"state directory does not exist: {parent}")
    if target.is_dir():
        raise WorkflowError(f"state path is a directory: {target}")
    data = canonical_bytes(value) + b"\n"
    try:
        fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(parent))
    except OSError as exc:
        raise WorkflowError(f"cannot create a temporary state file next to {target}: {exc}") from exc
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
    except OSError as exc:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise WorkflowError(f"cannot write state file {target}: {exc}") from exc


def read_json(path: Path) -> dict:
    target = Path(path)
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise WorkflowError(f"cannot read state file {target}: {exc}") from exc
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"invalid JSON in {target}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"state file is not a JSON object: {target}")
    return value


def safe_relative(root: Path, relative: str) -> Path:
    """Resolve a relative path under an absolute root, refusing escapes.

    Rejects absolute paths, `~`, empty components, `.`/`..`, and symlink
    escapes (the fully resolved target must stay inside the resolved root).
    """
    relative = _text(relative, "relative path")
    if relative.startswith(("/", "\\", "~")):
        raise WorkflowError(f"absolute path is not allowed: {relative}")
    root_path = Path(root)
    if not root_path.is_absolute():
        raise WorkflowError(f"containment root must be absolute: {root}")
    parts = relative.replace("\\", "/").split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise WorkflowError(f"unsafe relative path: {relative}")
    root_resolved = root_path.resolve()
    target = root_resolved.joinpath(*parts)
    resolved = target.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise WorkflowError(f"path escapes {root_resolved}: {relative}")
    return target


def next_skill(skills: Iterable[str], last: str | None) -> str | None:
    """Return the next skill for a deterministic one-skill-per-run review cycle.

    Names are sorted and de-duplicated. `last` is the cursor: when it is still
    present the next sorted name follows it; when it was deleted the next name
    after it in sorted order is chosen, so a removed skill neither skips its
    successor nor restarts the cycle at the first skill. A cursor at (or beyond)
    the final name wraps to the first. An empty inventory returns None — a
    periodic review never invents a skill to inspect.
    """
    names = sorted({name for name in skills if isinstance(name, str) and name})
    if not names:
        return None
    if not isinstance(last, str) or not last:
        return names[0]
    for name in names:
        if name > last:
            return name
    return names[0]


def _store_path(store: Path) -> Path:
    path = Path(store)
    if not path.is_absolute():
        raise WorkflowError("store must be an absolute path")
    if not path.is_dir():
        raise WorkflowError(f"store directory does not exist: {path}")
    return path.resolve()


def _candidate_path(store: Path, cid: str, *parts: str) -> Path:
    if not isinstance(cid, str) or not _CID_RE.match(cid):
        raise WorkflowError(f"invalid candidate id: {cid!r}")
    return safe_relative(store, "/".join((STATE_DIR, cid, *parts)))


# ---------------------------------------------------------------------------
# Git plumbing
# ---------------------------------------------------------------------------


def _git_env() -> dict:
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env.setdefault("GIT_SSH_COMMAND", "ssh -oBatchMode=yes -oConnectTimeout=10")
    env.setdefault("GIT_ASKPASS", "/bin/true")
    return env


def _git_error(result: subprocess.CompletedProcess, action: str) -> WorkflowError:
    detail = (result.stderr or result.stdout or "").strip().splitlines()
    tail = detail[-1][:500] if detail else "no output"
    return WorkflowError(f"git {action} failed ({result.returncode}): {tail}")


def git(
    repo: Path,
    *args: str,
    check: bool = False,
    input_text: str | None = None,
    timeout: int = GIT_TIMEOUT,
    extra_env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Run Git with an argument list and unattended, bounded execution."""
    if not args:
        raise WorkflowError("git requires at least one argument")
    env = _git_env()
    if extra_env:
        env.update(extra_env)
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            input=input_text,
            timeout=timeout,
            env=env,
        )
    except FileNotFoundError as exc:
        raise WorkflowError("git executable not found") from exc
    except subprocess.TimeoutExpired as exc:
        raise WorkflowError(f"git {args[0]} timed out after {timeout}s") from exc
    if check and result.returncode != 0:
        raise _git_error(result, args[0])
    return result


def git_bytes(
    repo: Path,
    *args: str,
    timeout: int = GIT_TIMEOUT,
    extra_env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Run Git and preserve stdout bytes (blob/index content, not text)."""
    if not args:
        raise WorkflowError("git requires at least one argument")
    env = _git_env()
    if extra_env:
        env.update(extra_env)
    try:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=False,
            timeout=timeout,
            env=env,
        )
    except FileNotFoundError as exc:
        raise WorkflowError("git executable not found") from exc
    except subprocess.TimeoutExpired as exc:
        raise WorkflowError(f"git {args[0]} timed out after {timeout}s") from exc


def _git_text(repo: Path, *args: str) -> str:
    return git(repo, *args, check=True).stdout.strip()


def _resolve_commit(repo: Path, revision: str, label: str = "commit") -> str:
    revision = _text(revision, label)
    if revision.startswith("-"):
        raise WorkflowError(f"invalid {label}: {revision!r}")
    result = git(repo, "rev-parse", "--verify", "--quiet", f"{revision}^{{commit}}")
    if result.returncode != 0:
        raise WorkflowError(f"{label} does not resolve to a commit: {revision}")
    sha = result.stdout.strip()
    if not _is_full_sha(sha):
        raise WorkflowError(f"{label} did not resolve to a full commit SHA: {revision}")
    return sha


def is_ancestor(repo: Path, older: str, newer: str) -> bool:
    older_sha = _resolve_commit(repo, older, "ancestor commit")
    newer_sha = _resolve_commit(repo, newer, "descendant commit")
    result = git(repo, "merge-base", "--is-ancestor", older_sha, newer_sha)
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    raise _git_error(result, "merge-base --is-ancestor")


def source_status(repo: Path, main: str, tip: str) -> str:
    """Consumed only when T is an ancestor of integrated main.

    A same-tree but non-ancestor tip is pending: there is deliberately no
    diff-size or empty-diff shortcut that would suppress its acknowledgment.
    """
    main_sha = _resolve_commit(repo, main, "main")
    tip_sha = _resolve_commit(repo, tip, "source tip")
    return "consumed" if is_ancestor(repo, tip_sha, main_sha) else "pending"


# ---------------------------------------------------------------------------
# Maintainer registry (strict)
# ---------------------------------------------------------------------------


def _validate_report(value: Any) -> Mapping[str, Any]:
    report = _mapping(value, "report")
    path = _absolute_text(report.get("path"), "report.path")
    allowed = _list(report.get("allowed_scopes", ["shared-generic"]), "report.allowed_scopes")
    for scope in allowed:
        _text(scope, "report.allowed_scopes entry")
    if len(set(allowed)) != len(allowed):
        raise WorkflowError("report.allowed_scopes must not contain duplicates")
    return {"path": path, "allowed_scopes": list(allowed)}


def _validate_identity(value: Any) -> Mapping[str, Any]:
    identity = _mapping(value, "maintainer_identity")
    for field in ("machine", "profile", "scope"):
        _text(identity.get(field), f"maintainer_identity.{field}")
    return identity


def _validate_source_entry(value: Any) -> Mapping[str, Any]:
    entry = _mapping(value, "source")
    _validate_branch_ref(entry.get("ref"), "source.ref")
    for field in ("machine", "profile", "scope"):
        _text(entry.get(field), f"source.{field}")
    _boolean(entry.get("enabled"), f"source {entry.get('ref')}.enabled")
    return entry


def _validate_config(raw: Any, store: Path) -> dict:
    config = dict(_mapping(raw, "maintainer config"))
    schema = config.get("schema")
    if isinstance(schema, bool) or not isinstance(schema, int) or schema != WORKFLOW_SCHEMA:
        raise WorkflowError(f"maintainer config schema must be {WORKFLOW_SCHEMA}")
    _text(config.get("repo_id"), "repo_id")
    remote = _text(config.get("remote"), "remote")
    if not _REMOTE_RE.match(remote):
        raise WorkflowError(f"remote is not a valid Git remote name: {remote}")
    _absolute_text(config.get("maintainer_repo"), "maintainer_repo")
    roots = _list(config.get("runtime_roots"), "runtime_roots")
    for index, root in enumerate(roots):
        _absolute_text(root, f"runtime_roots[{index}]")
    _text(config.get("policy"), "policy")
    _validate_identity(config.get("maintainer_identity"))

    sources = _list(config.get("sources"), "sources")
    seen: set[str] = set()
    for entry in sources:
        validated = _validate_source_entry(entry)
        ref = validated["ref"]
        if ref in seen:
            raise WorkflowError(f"duplicate source registration: {ref}")
        seen.add(ref)

    config["report"] = _validate_report(config.get("report"))
    # The state store is an absolute caller path; it is not persisted in the
    # config, but validating it here keeps every entry point consistent.
    _store_path(store)
    return config


def _read_config(store: Path) -> dict:
    return _validate_config(read_json(store / "maintainer.json"), store)


def load_maintainer_config(store: Path) -> dict:
    """Load and strictly validate `<store>/maintainer.json`."""
    store_path = _store_path(store)
    return _read_config(store_path)


def _require_report_scope(config: Mapping[str, Any], ref: str, scope: str) -> None:
    if scope not in config["report"]["allowed_scopes"]:
        # Ref and declared scope only: no source text, profile data or quotes.
        raise WorkflowError(f"source {ref} scope {scope} is not permitted for the report destination")


def _require_candidate_report_scope(state: Mapping[str, Any], config: Mapping[str, Any]) -> None:
    if state["kind"] == "transport":
        _registry_entry(config, {"ref": state["source_ref"], "machine": state["source_machine"],
                                 "profile": state["source_profile"]})
    else:
        _require_report_scope(config, state["source_ref"], config["maintainer_identity"]["scope"])


def _registry_entry(config: Mapping[str, Any], source: Any) -> Mapping[str, Any]:
    candidate = _mapping(source, "source")
    ref = _validate_branch_ref(candidate.get("ref"), "source.ref")
    for entry in config["sources"]:
        if entry["ref"] != ref:
            continue
        for field in ("machine", "profile", "scope"):
            if field in candidate and candidate[field] != entry[field]:
                raise WorkflowError(
                    f"source {ref} {field} does not match the maintainer registry"
                )
        if not entry["enabled"]:
            raise WorkflowError(f"source is disabled in the maintainer registry: {ref}")
        _require_report_scope(config, ref, entry["scope"])
        return entry
    raise WorkflowError(f"source is not registered for this maintainer: {ref}")


def _assert_maintainer(repo: Path, config: Mapping[str, Any]) -> None:
    repo_path = Path(repo)
    if not repo_path.is_absolute():
        raise WorkflowError("repository path must be absolute")
    top = git(repo, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        raise _git_error(top, "rev-parse --show-toplevel")
    actual = Path(top.stdout.strip()).resolve()
    configured = Path(config["maintainer_repo"]).resolve()
    if actual != configured:
        raise WorkflowError(
            f"configured maintainer_repo does not match the actual checkout: {configured} != {actual}"
        )
    remote = git(repo, "remote", "get-url", config["remote"])
    if remote.returncode != 0:
        raise WorkflowError(f"configured remote does not exist in the maintainer: {config['remote']}")


def _assert_store_outside_repo(repo: Path, store: Path) -> None:
    top = Path(_git_text(repo, "rev-parse", "--show-toplevel")).resolve()
    if store == top or top in store.parents:
        raise WorkflowError("state store must live outside the maintainer working tree")


# ---------------------------------------------------------------------------
# Explicit refactor submission (F1)
#
# A pushed `refs/heads/refactor/*` branch is a backup, not readiness. Only an
# operator submission that names the exact ref, the exact remote tip and a
# bounded replacement brief authorises a refactor candidate. The record lives
# outside the transport registry, so transport source validation is unchanged:
# a refactor journal is loadable only through its own submission record.
# ---------------------------------------------------------------------------

REFACTOR_REF_PREFIX = "refs/heads/refactor/"
REFACTOR_SUBMISSION_SCHEMA = 1
REFACTOR_SUBMISSIONS_DIR = "refactor-submissions"
REFACTOR_BRIEF_KEYS = frozenset({"summary", "intended_replacements", "validation_notes"})
REFACTOR_REPLACEMENT_KEYS = frozenset({"path", "old_quote", "new_instruction", "reason"})


def _refactor_ref(value: Any) -> str:
    """Exactly `refs/heads/refactor/<slug>`; no other ref shape is submittable."""
    ref = _validate_branch_ref(value, "refactor ref")
    if not ref.startswith(REFACTOR_REF_PREFIX):
        raise WorkflowError(f"refactor ref must be {REFACTOR_REF_PREFIX}<slug>: {ref}")
    slug = ref[len(REFACTOR_REF_PREFIX):]
    if not slug or "/" in slug:
        raise WorkflowError(f"refactor ref must be {REFACTOR_REF_PREFIX}<slug>: {ref}")
    return ref


def validate_refactor_brief(brief: Any) -> dict:
    """Exact replacement brief: no commands, no arbitrary nested payloads."""
    source = _exact_keys(brief, REFACTOR_BRIEF_KEYS, "refactor brief")
    replacements = []
    rows = _list(source["intended_replacements"], "refactor brief intended_replacements")
    for index, row in enumerate(rows):
        entry = _exact_keys(row, REFACTOR_REPLACEMENT_KEYS,
                            f"refactor brief intended_replacements[{index}]")
        replacements.append({
            "path": _validate_git_path(entry["path"],
                                       f"refactor brief intended_replacements[{index}].path"),
            "old_quote": _quote_text(entry["old_quote"],
                                     f"refactor brief intended_replacements[{index}].old_quote"),
            "new_instruction": _quote_text(
                entry["new_instruction"],
                f"refactor brief intended_replacements[{index}].new_instruction"),
            "reason": _text(entry["reason"],
                            f"refactor brief intended_replacements[{index}].reason"),
        })
    return {
        "summary": _text(source["summary"], "refactor brief summary"),
        "intended_replacements": replacements,
        "validation_notes": _text(source["validation_notes"],
                                  "refactor brief validation_notes"),
    }


def _brief_digest(brief: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(dict(brief))).hexdigest()


def _submission_path(store: Path, cid: str) -> Path:
    return store / REFACTOR_SUBMISSIONS_DIR / f"{cid}.json"


def _validate_submission(raw: Any, cid: str, config: Mapping[str, Any]) -> dict:
    record = dict(_mapping(raw, "refactor submission"))
    required = (
        "schema", "id", "repo_id", "kind", "ref", "main_sha", "tip", "policy",
        "maintainer_identity", "brief", "brief_sha256", "submitted_at",
    )
    missing = [field for field in required if field not in record]
    if missing:
        raise WorkflowError(
            f"refactor submission is missing fields: {', '.join(missing)}")
    schema = record["schema"]
    if isinstance(schema, bool) or not isinstance(schema, int) \
            or schema != REFACTOR_SUBMISSION_SCHEMA:
        raise WorkflowError(f"refactor submission schema must be {REFACTOR_SUBMISSION_SCHEMA}")
    if record["id"] != cid:
        raise WorkflowError(f"refactor submission id does not match its record: {record['id']}")
    if record["kind"] != "refactor":
        raise WorkflowError("refactor submission kind must be refactor")
    if record["repo_id"] != config["repo_id"]:
        raise WorkflowError("refactor submission repo_id does not match the maintainer config")
    if record["policy"] != config["policy"]:
        raise WorkflowError("refactor submission policy does not match the maintainer config")
    ref = _refactor_ref(record["ref"])
    if not _is_full_sha(record["main_sha"]) or not _is_full_sha(record["tip"]):
        raise WorkflowError("refactor submission main and tip must be full commit SHAs")
    identity = _validate_identity(record["maintainer_identity"])
    configured = config["maintainer_identity"]
    for field in ("machine", "profile", "scope"):
        if identity[field] != configured[field]:
            raise WorkflowError(
                "refactor submission was not made by the configured maintainer identity")
    brief = validate_refactor_brief(record["brief"])
    if record["brief_sha256"] != _brief_digest(brief):
        raise WorkflowError("refactor submission brief digest does not match its brief")
    _text(record["submitted_at"], "refactor submission submitted_at")
    expected = candidate_id(
        record["repo_id"], ref, record["main_sha"], record["tip"], record["policy"], "refactor")
    if expected != cid:
        raise WorkflowError(f"refactor submission {cid} does not match its identity fields")
    return record


def _load_submission(store: Path, cid: str, config: Mapping[str, Any]) -> dict:
    if not isinstance(cid, str) or not _CID_RE.match(cid):
        raise WorkflowError(f"invalid candidate id: {cid!r}")
    path = _submission_path(store, cid)
    if not path.is_file():
        raise WorkflowError(
            f"refactor candidate {cid} has no exact-tip submission record; "
            "run --submit-refactor with the ref, tip and brief"
        )
    return _validate_submission(read_json(path), cid, config)


def refactor_submissions(store: Path) -> list[dict]:
    """Every validated submission for the configured maintainer, sorted by id."""
    store_path = _store_path(store)
    config = _read_config(store_path)
    root = store_path / REFACTOR_SUBMISSIONS_DIR
    if not root.is_dir():
        return []
    records: list[dict] = []
    for path in sorted(root.glob("*.json")):
        cid = path.stem
        if not _CID_RE.match(cid):
            raise WorkflowError(f"unexpected refactor submission filename: {path.name}")
        records.append(_load_submission(store_path, cid, config))
    return records


def submit_refactor(repo: Path, store: Path, ref: str, tip: str, brief: dict) -> dict:
    """Record one explicit exact-tip refactor submission.

    The ref must be `refs/heads/refactor/<slug>`, `tip` must be a full SHA that
    is exactly the fetched remote tip, and captured main must be an ancestor of
    the tip. The brief is the only review scope; identity and scope are taken
    from the configured `maintainer_identity`, never from the caller. The tip is
    pinned immediately and a later main advance makes this submission stale
    (merge main into the branch and submit again), never silently extended.
    """
    store_path = _store_path(store)
    config = _read_config(store_path)
    _assert_maintainer(repo, config)
    _assert_store_outside_repo(repo, store_path)

    ref = _refactor_ref(ref)
    tip_text = _text(tip, "refactor tip")
    if not _is_full_sha(tip_text):
        raise WorkflowError("refactor tip must be a full commit SHA")
    brief_value = validate_refactor_brief(brief)

    remote = config["remote"]
    _fetch_inputs(repo, remote)
    resolved = _resolve_commit(repo, tip_text, "refactor tip")
    if resolved != tip_text:
        raise WorkflowError(
            f"refactor tip {tip_text} does not resolve to that exact commit ({resolved})")
    tracking = _remote_tracking_ref(remote, ref)
    remote_tip_result = git(repo, "rev-parse", "--verify", "--quiet", f"{tracking}^{{commit}}")
    if remote_tip_result.returncode != 0:
        raise WorkflowError(
            f"refactor ref {ref} does not exist on {remote}; push the exact tip first")
    remote_tip = remote_tip_result.stdout.strip()
    if remote_tip != tip_text:
        raise WorkflowError(
            f"refactor tip {tip_text} is not the current remote tip {remote_tip} of {ref}; "
            "a backup push is not readiness — push the exact tip you are submitting")
    main_sha = _resolve_commit(
        repo, f"refs/remotes/{remote}/{MAIN_BRANCH}", f"{remote}/{MAIN_BRANCH}")
    if not is_ancestor(repo, main_sha, tip_text):
        raise WorkflowError(
            f"refactor tip {tip_text} does not contain the captured main {main_sha}; "
            f"merge {remote}/{MAIN_BRANCH} into {ref} and submit the merged exact tip")

    cid = candidate_id(config["repo_id"], ref, main_sha, tip_text, config["policy"], "refactor")
    record = {
        "schema": REFACTOR_SUBMISSION_SCHEMA,
        "id": cid,
        "repo_id": config["repo_id"],
        "kind": "refactor",
        "ref": ref,
        "main_sha": main_sha,
        "tip": tip_text,
        "policy": config["policy"],
        "maintainer_identity": {
            "machine": config["maintainer_identity"]["machine"],
            "profile": config["maintainer_identity"]["profile"],
            "scope": config["maintainer_identity"]["scope"],
        },
        "brief": brief_value,
        "brief_sha256": _brief_digest(brief_value),
        "submitted_at": _utc_now(),
    }
    path = _submission_path(store_path, cid)
    if path.is_file():
        existing = _load_submission(store_path, cid, config)
        if canonical_bytes(existing["brief"]) != canonical_bytes(brief_value):
            raise WorkflowError(
                f"refactor submission {cid} already exists with a different brief; "
                "a changed brief requires a new refactor commit and a new exact tip")
        _pin_inputs(repo, cid, main_sha, tip_text)
        return existing
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise WorkflowError(
            f"cannot create the refactor submission directory {path.parent}: {exc}") from exc
    _pin_inputs(repo, cid, main_sha, tip_text)
    atomic_json(path, record)
    return record


# ---------------------------------------------------------------------------
# Maintainer lock
# ---------------------------------------------------------------------------

def git_common_dir(repo: Path) -> Path:
    """Absolute Git common dir shared by one repository and all of its linked worktrees.

    A lock must cover the whole repository, so this deliberately derives
    `--git-common-dir` and never a per-worktree `--git-dir` or a state-store
    path. Git >= 2.31 answers absolutely with `--path-format=absolute`; older
    versions return a path relative to the repo root, which is resolved here.
    """
    result = git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if result.returncode == 0:
        text = result.stdout.strip()
        if text:
            return Path(text).resolve()
    fallback = git(repo, "rev-parse", "--git-common-dir")
    if fallback.returncode != 0:
        raise _git_error(fallback, "rev-parse --git-common-dir")
    text = fallback.stdout.strip()
    if not text:
        raise WorkflowError(f"git returned an empty common directory for {repo}")
    common = Path(text)
    if not common.is_absolute():
        top = git(repo, "rev-parse", "--show-toplevel")
        if top.returncode != 0:
            raise _git_error(top, "rev-parse --show-toplevel")
        common = Path(top.stdout.strip()) / common
    return common.resolve()


def maintainer_git_common_dir(repo: Path) -> Path:
    """Backward-compatible name for the maintainer clone's common directory."""
    return git_common_dir(repo)


def maintainer_lock_path(store: Path) -> Path:
    """The one lock path covering the configured maintainer clone."""
    config = load_maintainer_config(store)
    common = maintainer_git_common_dir(Path(config["maintainer_repo"]))
    return common / PUBLISHER_LOCK_DIR / PUBLISHER_LOCK_NAME


def _read_lock_file(path: Path) -> dict | None:
    """Read a lock record; `None` when absent, malformed content is reported, never repaired."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise WorkflowError(f"cannot read maintainer lock {path}: {exc}") from exc
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return {"path": str(path), "malformed": text[:500], "token": None}
    if not isinstance(value, dict):
        return {"path": str(path), "malformed": text[:500], "token": None}
    value = dict(value)
    value["path"] = str(path)
    return value


def read_maintainer_lock(store: Path) -> dict | None:
    """Diagnostic view of the held lock; never creates, breaks or releases it."""
    return _read_lock_file(maintainer_lock_path(store))


def _lock_held_error(path: Path, label: str = "maintainer") -> WorkflowError:
    record = _read_lock_file(path)
    if record is None:
        return WorkflowError(f"{label} lock is held: {path} (owner details unavailable)")
    if record.get("malformed") is not None:
        return WorkflowError(
            f"{label} lock is held: {path} (unreadable content, refusing to guess an owner)"
        )
    return WorkflowError(
        f"{label} lock is held: {path} (owner token {record.get('token')}, "
        f"pid {record.get('pid')}, host {record.get('host')}, "
        f"acquired {record.get('acquired_at')}); no age expiry or TTL override"
    )


def _acquire_lock(lock_path: Path, label: str, schema: int) -> str:
    """Atomically acquire one owner-token lock file and return its token."""
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise WorkflowError(
            f"cannot create {label} lock directory {lock_path.parent}: {exc}") from exc
    token = os.urandom(32).hex()
    payload = {
        "schema": schema,
        "token": token,
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "acquired_at": _utc_now(),
    }
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        raise _lock_held_error(lock_path, label) from None
    except OSError as exc:
        raise WorkflowError(f"cannot create {label} lock {lock_path}: {exc}") from exc
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(canonical_bytes(payload) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        try:
            os.unlink(lock_path)
        except OSError:
            pass
        raise WorkflowError(f"cannot write {label} lock {lock_path}: {exc}") from exc
    return token


def _release_lock(lock_path: Path, token: str, label: str) -> None:
    """Release one lock only with the acquiring owner token."""
    token = _text(token, f"{label} lock owner token")
    record = _read_lock_file(lock_path)
    if record is None:
        raise WorkflowError(f"{label} lock is not held: {lock_path}")
    stored = record.get("token")
    if record.get("malformed") is not None or stored != token:
        shown = stored if isinstance(stored, str) and stored else "<unreadable>"
        raise WorkflowError(
            f"{label} lock {lock_path} is owned by another token ({shown}); "
            f"refusing to release it — only the acquiring owner token may release"
        )
    try:
        lock_path.unlink()
    except FileNotFoundError:
        raise WorkflowError(f"{label} lock disappeared before release: {lock_path}") from None
    except OSError as exc:
        raise WorkflowError(f"cannot release {label} lock {lock_path}: {exc}") from exc


def acquire_maintainer_lock(store: Path) -> str:
    """Atomically acquire the maintainer clone's single lock and return its owner token.

    `O_CREAT|O_EXCL` at `<git-common-dir>/hermes-sync/maintainer.lock`; the record
    carries the owner token, pid, host and acquisition time. There is no age
    expiry and no TTL: an old lock is never evidence that its owner is gone.
    """
    return _acquire_lock(maintainer_lock_path(store), "maintainer", PUBLISHER_LOCK_SCHEMA)


def release_maintainer_lock(store: Path, token: str) -> None:
    """Release only with the acquiring owner token; never guess or break another owner's lock."""
    _release_lock(maintainer_lock_path(store), token, "maintainer")


def contributor_lock_path(repo: Path) -> Path:
    """The one short-operation lock path covering a contributor checkout.

    Derived from the contributor repository's Git **common dir**, so every linked
    worktree of that checkout contends on the same file. It is deliberately a
    different file from the maintainer lock and never lives in the store.
    """
    return git_common_dir(repo) / PUBLISHER_LOCK_DIR / PRODUCER_LOCK_NAME


def read_contributor_lock(repo: Path) -> dict | None:
    """Diagnostic view of the held contributor lock; never creates, breaks or releases it."""
    return _read_lock_file(contributor_lock_path(repo))


def acquire_contributor_lock(repo: Path) -> str:
    """Acquire the contributor checkout's short-operation lock and return its owner token.

    Used only for the staging commit and the pre-integration merge/push, never
    for a whole chat session. An existing file is a refusal with its owner
    details; there is no age expiry that could silently break a live owner.
    """
    return _acquire_lock(contributor_lock_path(repo), "contributor", PRODUCER_LOCK_SCHEMA)


def release_contributor_lock(repo: Path, token: str) -> None:
    """Release the contributor lock only with the acquiring owner token."""
    _release_lock(contributor_lock_path(repo), token, "contributor")


# ---------------------------------------------------------------------------
# Candidate state
# ---------------------------------------------------------------------------


def _public_state(state: Mapping[str, Any], store: Path) -> dict:
    public = {key: value for key, value in state.items() if not str(key).startswith("_")}
    public["_store"] = store
    return public


def _persisted_state(state: Mapping[str, Any]) -> dict:
    return {key: value for key, value in state.items() if not str(key).startswith("_")}


def _validate_candidate_state(
    state: Mapping[str, Any],
    cid: str,
    config: Mapping[str, Any],
    *,
    submission: Mapping[str, Any] | None = None,
) -> dict:
    required = (
        "schema",
        "id",
        "repo_id",
        "kind",
        "source_ref",
        "source_machine",
        "source_profile",
        "main_sha",
        "source_sha",
        "policy",
        "status",
        "created_at",
        "worktree",
        "input_paths",
        "conflict_paths",
        "review_digest",
        "reviewed_tree",
        "report_relative_path",
        "report_sha256",
        "result_sha",
        "last_error",
        "attempts",
    )
    missing = [field for field in required if field not in state]
    if missing:
        raise WorkflowError(f"candidate state is missing fields: {', '.join(missing)}")
    forbidden = [key for key in state if str(key).startswith("_")]
    if forbidden:
        raise WorkflowError(
            f"candidate state must not persist private fields: {', '.join(sorted(forbidden))}"
        )
    schema = state["schema"]
    if isinstance(schema, bool) or not isinstance(schema, int) or schema != WORKFLOW_SCHEMA:
        raise WorkflowError(f"candidate schema must be {WORKFLOW_SCHEMA}")
    if state["id"] != cid:
        raise WorkflowError(f"candidate id does not match its journal: {state['id']}")
    if state["repo_id"] != config["repo_id"]:
        raise WorkflowError("candidate repo_id does not match the maintainer config")
    kind = _text_in(state["kind"], "kind", KINDS)
    source_ref = _validate_branch_ref(state["source_ref"], "source_ref")
    if kind == "transport":
        if source_ref.startswith(REFACTOR_REF_PREFIX):
            raise WorkflowError("transport candidates cannot name a refactor source ref")
        # Transport authorisation is the configured source registry. It is
        # deliberately unchanged: a submission record never authorises transport.
        registry = next(
            (entry for entry in config["sources"] if entry["ref"] == source_ref), None
        )
        # Saved integration intents must remain inspectable after registry
        # revocation: remote P may already exist. Loading this recovery journal
        # is NOT authorization to push; the shared pre-push gate still requires
        # the current registry entry and exact recorded identity.
        recovering = _is_full_sha(state.get("result_sha")) and state.get("status") in (
            *_RECONCILABLE_STATUSES, "stale", "blocked")
        if recovering:
            machine, profile = state["source_machine"], state["source_profile"]
        else:
            if registry is None:
                raise WorkflowError(f"candidate source is not registered: {source_ref}")
            machine, profile = registry["machine"], registry["profile"]
    else:
        source_ref = _refactor_ref(state["source_ref"])
        if submission is None:
            raise WorkflowError(
                f"refactor candidate {cid} requires its exact-tip submission record")
        for field, value in (
            ("id", cid),
            ("ref", source_ref),
            ("main_sha", state["main_sha"]),
            ("tip", state["source_sha"]),
            ("policy", state["policy"]),
        ):
            if submission.get(field) != value:
                raise WorkflowError(
                    f"refactor candidate {cid} does not match its submission record ({field})")
        identity = _validate_identity(submission["maintainer_identity"])
        machine, profile = identity["machine"], identity["profile"]
    _text(state["source_machine"], "source_machine")
    _text(state["source_profile"], "source_profile")
    if state["source_machine"] != machine or state["source_profile"] != profile:
        raise WorkflowError("candidate source identity does not match its authorisation")
    if not _is_full_sha(state["main_sha"]):
        raise WorkflowError("candidate main_sha must be a full commit SHA")
    if not _is_full_sha(state["source_sha"]):
        raise WorkflowError("candidate source_sha must be a full commit SHA")
    _text(state["policy"], "policy")
    status = _text_in(state["status"], "status", STATUSES)
    _text(state["created_at"], "created_at")
    worktree = state["worktree"]
    if not isinstance(worktree, str):
        raise WorkflowError("candidate worktree must be text")
    if worktree and not Path(worktree).is_absolute():
        raise WorkflowError("candidate worktree must be an absolute path")
    for field in ("input_paths", "conflict_paths"):
        paths = state[field]
        if not isinstance(paths, list):
            raise WorkflowError(f"candidate {field} must be an array")
        for path in paths:
            _validate_git_path(path, f"candidate {field} entry")
    for field in ("review_digest", "report_sha256"):
        value = state[field]
        if value and not _is_digest(value):
            raise WorkflowError(f"candidate {field} must be a sha256 hex digest")
    checks_digest = state.get("checks_digest", "")
    if checks_digest and not _is_digest(checks_digest):
        raise WorkflowError("candidate checks_digest must be a sha256 hex digest")
    for field in ("reviewed_tree", "result_sha"):
        value = state[field]
        if value and not _is_full_sha(value):
            raise WorkflowError(f"candidate {field} must be a full Git object SHA")
    result_parents = state.get("result_parents")
    if result_parents not in (None, []):
        if not isinstance(result_parents, list) or len(result_parents) != 2:
            raise WorkflowError("candidate result_parents must list exactly two commits")
        for parent in result_parents:
            if not _is_full_sha(parent):
                raise WorkflowError("candidate result_parents must contain full commit SHAs")
    result_tree = state.get("result_tree", "")
    if result_tree and not _is_full_sha(result_tree):
        raise WorkflowError("candidate result_tree must be a full Git tree SHA")
    integrated_main = state.get("integrated_main", "")
    if integrated_main and not _is_full_sha(integrated_main):
        raise WorkflowError("candidate integrated_main must be a full commit SHA")
    result_observed_at = state.get("result_observed_at", "")
    if result_observed_at:
        _text(result_observed_at, "result_observed_at")
    receipt_sha256 = state.get("receipt_sha256", "")
    if receipt_sha256 and not _is_digest(receipt_sha256):
        raise WorkflowError("candidate receipt_sha256 must be a sha256 hex digest")
    receipt_verified_at = state.get("receipt_verified_at", "")
    if receipt_verified_at:
        _text(receipt_verified_at, "receipt_verified_at")
    incident = state.get("incident", "")
    if incident:
        _text(incident, "incident")
    receipt_attempts = state.get("receipt_attempts", 0)
    if (
        isinstance(receipt_attempts, bool)
        or not isinstance(receipt_attempts, int)
        or receipt_attempts < 0
    ):
        raise WorkflowError("candidate receipt_attempts must be a non-negative integer")
    relative = state["report_relative_path"]
    if not isinstance(relative, str):
        raise WorkflowError("candidate report_relative_path must be text")
    if relative:
        _validate_git_path(relative, "candidate report_relative_path")
    if not isinstance(state["last_error"], str):
        raise WorkflowError("candidate last_error must be text")
    attempts = state["attempts"]
    if isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 0:
        raise WorkflowError("candidate attempts must be a non-negative integer")
    retry_generation = state.get("retry_generation", 0)
    if (
        isinstance(retry_generation, bool)
        or not isinstance(retry_generation, int)
        or retry_generation < 0
    ):
        raise WorkflowError("candidate retry_generation must be a non-negative integer")
    if status in _REVIEWED_STATUSES:
        if not state["reviewed_tree"] or not state["review_digest"]:
            raise WorkflowError(f"candidate status {status} requires a reviewed tree and digest")
    if status in _RESULT_STATUSES or status == "integrate-intent":
        if not state["result_sha"]:
            raise WorkflowError(f"candidate status {status} requires a result commit")
        if state.get("result_parents") != [state["main_sha"], state["source_sha"]]:
            raise WorkflowError(
                f"candidate status {status} requires result parents "
                "[captured main, captured source tip]"
            )
        if state.get("result_tree") != state["reviewed_tree"]:
            raise WorkflowError(
                f"candidate status {status} requires result_tree == reviewed_tree"
            )
    if status == "complete" and not state.get("receipt_sha256"):
        raise WorkflowError(
            "candidate status complete requires a verified receipt digest; "
            "only an exact read-back of the delivered result may claim completion"
        )

    expected = candidate_id(
        state["repo_id"],
        source_ref,
        state["main_sha"],
        state["source_sha"],
        state["policy"],
        kind,
    )
    if expected != cid:
        raise WorkflowError(f"candidate {cid} state does not match its identity fields")
    return dict(state)


def _validate_state(
    store: Path, state: Mapping[str, Any], cid: str, config: Mapping[str, Any]
) -> dict:
    """Validate a journal against its authorisation: registry or submission.

    A refactor journal is never accepted from the transport registry; it must
    name an existing submission record that matches its ref, main, tip, policy
    and maintainer identity exactly.
    """
    submission = None
    if state.get("kind") == "refactor":
        submission = _load_submission(store, cid, config)
    return _validate_candidate_state(
        _persisted_state(state), cid, config, submission=submission
    )


def load_candidate(store: Path, cid: str) -> dict:
    """Load the authoritative candidate journal plus an in-memory `_store`.

    The maintainer registry is parsed and validated before any candidate file is
    trusted; `_store` is never read from disk and never persisted. A refactor
    journal additionally requires its exact-tip submission record.
    """
    store_path = _store_path(store)
    if not isinstance(cid, str) or not _CID_RE.match(cid):
        raise WorkflowError(f"invalid candidate id: {cid!r}")
    config = _read_config(store_path)
    path = _candidate_path(store_path, cid, STATE_FILE)
    if not path.is_file():
        raise WorkflowError(f"candidate not found: {cid}")
    state = _validate_state(store_path, read_json(path), cid, config)
    return _public_state(state, store_path)


def _write_candidate_state(store: Path, cid: str, state: Mapping[str, Any]) -> None:
    directory = _candidate_path(store, cid)
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise WorkflowError(f"cannot create candidate state directory {directory}: {exc}") from exc
    atomic_json(directory / STATE_FILE, _persisted_state(state))


# ---------------------------------------------------------------------------
# Monitor protocol and explicit retry
# ---------------------------------------------------------------------------


def _retry_suffix(state: Mapping[str, Any]) -> str:
    generation = state.get("retry_generation", 0) or 0
    return f" retry {generation}" if generation else ""


def _candidate_monitor_line(store: Path, cid: str, *, fallback: str) -> str:
    """One stable line for a candidate id: blocked or pending, plus the retry
    generation once an explicit retry advanced it. Never a timestamp."""
    state_file = _candidate_path(store, cid, STATE_FILE)
    if not state_file.is_file():
        return f"{fallback} {cid}"
    state = read_json(state_file)
    status = state.get("status")
    prefix = "blocked" if status == "blocked" else "pending"
    return f"{prefix} {cid}{_retry_suffix(state)}"


def _submitted_refactor_lines(
    repo: Path, store: Path, main_sha: str
) -> list[str]:
    """Only explicit, current submissions are monitor work.

    An unsubmitted `refs/heads/refactor/*` branch has no record and is never
    listed, so a backup push cannot look ready. A submission whose captured main
    is no longer the integrated main is stale (merge main, review, submit again)
    and is omitted rather than reported as pending forever. When the journal
    exists its blocked/pending status and retry generation win, exactly as for a
    transport candidate.
    """
    lines: list[str] = []
    for submission in refactor_submissions(store):
        ref = submission["ref"]
        if not ref.startswith(REFACTOR_REF_PREFIX):
            continue
        if submission["main_sha"] != main_sha:
            continue
        if is_ancestor(repo, submission["tip"], main_sha):
            continue
        lines.append(
            _candidate_monitor_line(store, submission["id"], fallback="pending")
        )
    return lines


def pending_lines(
    repo: Path,
    store: Path,
    sources: Sequence[Mapping[str, Any]] | None = None,
    *,
    fetch: bool = True,
) -> list[str]:
    """Return the monitor's stable line protocol for this store.

    * one `pending <cid>` line per enabled registered `machine/*` tip that is
      not an ancestor of integrated main (an unacknowledged empty-diff tip
      included: consumption is ancestry, never diff size)
    * one `blocked <cid>` line instead when that exact candidate journal is
      blocked, so an unchanged block never looks like fresh work
    * submitted refactor candidates (a refactor journal exists) are listed the
      same way; unsubmitted refactor refs are never listed
    * consumed tips are omitted from source discovery, but unfinished journals
      independently emit `recover <cid>` (integrate-intent/integrated/receipt-pending)
      or `incident <cid>` (sticky incident), even for disabled sources
    * `retry <n>` is appended once an explicit `retry_candidate()` advanced the
      generation, so the monitor key changes exactly once per invocation
    * `fetch=False` reads only cached remote-tracking refs and refuses with a
      "cannot determine without fetch" WorkflowError when they are insufficient

    Technical failures raise WorkflowError; the CLI adapter turns that into the
    stable `error: monitor-unhealthy` signal so a broken fetch never looks like
    a healthy empty result.
    """
    store_path = _store_path(store)
    config = _read_config(store_path)
    repo_path = Path(repo)
    _assert_maintainer(repo_path, config)
    if sources is None:
        source_entries: Sequence[Mapping[str, Any]] = config["sources"]
    else:
        source_entries = sources
    remote = config["remote"]
    main_ref = f"refs/remotes/{remote}/{MAIN_BRANCH}"

    if fetch:
        result = git(
            repo_path, "fetch", remote, "--prune", "--quiet", timeout=FETCH_TIMEOUT
        )
        if result.returncode != 0:
            raise WorkflowError(
                f"cannot read {remote}: {_result_tail(result)}"
            )
    main = git(repo_path, "rev-parse", "--verify", "--quiet", main_ref)
    if main.returncode != 0 or not _is_full_sha(main.stdout.strip()):
        reason = "no successful fetch is recorded" if not fetch else "it is missing"
        raise WorkflowError(f"cannot determine integrated main: {main_ref} {reason}")
    main_sha = main.stdout.strip()

    lines: list[str] = []
    for raw in source_entries:
        entry = _validate_source_entry(raw)
        ref = entry["ref"]
        if not entry["enabled"] or not ref.startswith("refs/heads/machine/"):
            continue
        tracking = _remote_tracking_ref(remote, ref)
        tip_result = git(repo_path, "rev-parse", "--verify", "--quiet", tracking)
        if tip_result.returncode != 0 or not _is_full_sha(tip_result.stdout.strip()):
            if not fetch:
                raise WorkflowError(
                    f"cannot determine without fetch: {tracking} is not cached"
                )
            raise WorkflowError(f"registered source {ref} is missing from {remote}")
        tip = tip_result.stdout.strip()
        if is_ancestor(repo_path, tip, main_sha):
            continue
        cid = candidate_id(
            config["repo_id"], ref, main_sha, tip, config["policy"], "transport"
        )
        lines.append(_candidate_monitor_line(store_path, cid, fallback="pending"))

    lines.extend(_submitted_refactor_lines(repo_path, store_path, main_sha))
    # Source discovery cannot see delivery work once T is consumed, M moved, or
    # the source was disabled. Journals are the independent recovery inventory.
    recovery: dict[str, str] = {}
    journals = store_path / STATE_DIR
    for path in sorted(journals.glob(f"*/{STATE_FILE}")):
        state = load_candidate(store_path, path.parent.name)
        if state.get("incident"):
            recovery[state["id"]] = f"incident {state['id']}"
        elif state["status"] in ("integrate-intent", "integrated", "receipt-pending"):
            recovery[state["id"]] = f"recover {state['id']}"
    lines = [line for line in lines if line.split()[1] not in recovery]
    lines.extend(recovery.values())
    return sorted(set(lines))


def retry_candidate(store: Path, cid: str) -> dict:
    """Advance one blocked candidate by exactly one explicit retry generation.

    The state transition is `blocked -> captured` so preparation can run again;
    the previous `last_error`/worktree evidence is retained for inspection and
    the generation is persisted atomically. A candidate that is not blocked is
    refused rather than retried implicitly, and `--dry-run` never calls this.
    """
    store_path = _store_path(store)
    config = _read_config(store_path)
    if not isinstance(cid, str) or not _CID_RE.match(cid):
        raise WorkflowError(f"invalid candidate id: {cid!r}")
    state = load_candidate(store_path, cid)
    if state["status"] != "blocked":
        raise WorkflowError(
            f"candidate {cid} is {state['status']}; --retry applies only to a blocked candidate"
        )
    updated = _persisted_state(state)
    updated["status"] = "captured"
    updated["retry_generation"] = int(state.get("retry_generation") or 0) + 1
    _validate_state(store_path, updated, cid, config)
    _write_candidate_state(store_path, cid, updated)
    return _public_state(updated, store_path)


def _remote_tracking_ref(remote: str, ref: str) -> str:
    branch = ref[len("refs/heads/"):]
    return f"refs/remotes/{remote}/{branch}"


def _pin_inputs(repo: Path, cid: str, main_sha: str, source_sha: str) -> None:
    """Pin both captured commits locally; never use a remote branch as input."""
    pins = {
        f"{PIN_ROOT}/{cid}/main": main_sha,
        f"{PIN_ROOT}/{cid}/source": source_sha,
    }
    updates: list[str] = []
    for ref, sha in pins.items():
        current = git(repo, "rev-parse", "--verify", "--quiet", ref)
        if current.returncode == 0:
            if current.stdout.strip() != sha:
                raise WorkflowError(
                    f"local pin {ref} already names {current.stdout.strip()}, expected {sha}"
                )
            continue
        updates.append(f"update {ref} {sha}")
    if updates:
        git(repo, "update-ref", "--stdin", input_text="\n".join(updates) + "\n", check=True)


def _fetch_inputs(repo: Path, remote: str) -> None:
    """One fetch, all heads, so M/T and refactor diagnostics come from fetched refs."""
    refspec = f"+refs/heads/*:refs/remotes/{remote}/*"
    result = git(repo, "fetch", "--prune", "--no-tags", remote, refspec, timeout=FETCH_TIMEOUT)
    if result.returncode != 0:
        raise _git_error(result, "fetch")


def _known_refactor_refs(repo: Path, remote: str) -> list[str]:
    prefix = f"refs/remotes/{remote}/refactor/"
    result = git(repo, "for-each-ref", "--format=%(refname)", prefix)
    if result.returncode != 0:
        raise _git_error(result, "for-each-ref")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _rev_list(repo: Path, include: str, exclude: str) -> set[str]:
    result = git(repo, "rev-list", include, exclude)
    if result.returncode != 0:
        raise _git_error(result, "rev-list")
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def _rev_list_with_parents(repo: Path, include: str, exclude: str) -> dict[str, list[str]]:
    result = git(repo, "rev-list", "--parents", include, exclude)
    if result.returncode != 0:
        raise _git_error(result, "rev-list --parents")
    commits: dict[str, list[str]] = {}
    for line in result.stdout.splitlines():
        fields = line.split()
        if fields:
            commits[fields[0]] = fields[1:]
    return commits


def validate_source_history(
    repo: Path, main: str, tip: str, known_refactors: Sequence[str] | None = None
) -> None:
    """Cooperative transport provenance guard.

    Refuses a transport tip that:
      * contains an unpublished merge whose non-first parent is not already an
        ancestor of captured main (an indirect side-parent import), or
      * shares unpublished history with a known remote `refactor/*` branch
        (including a direct fast-forward to an unsubmitted refactor tip).

    Messages name refs and commit SHAs only; no content is inspected or quoted.
    This is a DAG rule, not a security boundary: cherry-picks, deleted refs and
    a malicious writer who rewrites history are outside what it can prove.
    """
    main_sha = _resolve_commit(repo, main, "main")
    tip_sha = _resolve_commit(repo, tip, "source tip")
    unpublished = _rev_list(repo, tip_sha, f"^{main_sha}")
    if not unpublished:
        return
    for commit, parents in _rev_list_with_parents(repo, tip_sha, f"^{main_sha}").items():
        if len(parents) < 2:
            continue
        for parent in parents[1:]:
            if is_ancestor(repo, parent, main_sha):
                continue
            raise WorkflowError(
                f"transport tip {tip_sha} merges unpublished parent {parent} in merge {commit}; "
                "a transport branch may only merge commits already integrated on main"
            )
    if isinstance(known_refactors, str):
        known_refactors = (known_refactors,)
    for item in known_refactors or ():
        ref = item.get("ref") if isinstance(item, Mapping) else item
        ref = _text(ref, "known refactor ref")
        refactor_tip = _resolve_commit(repo, ref, f"refactor tip {ref}")
        exclusive = _rev_list(repo, refactor_tip, f"^{main_sha}")
        overlap = unpublished & exclusive
        if overlap:
            raise WorkflowError(
                f"transport tip {tip_sha} contains unpublished refactor history {sorted(overlap)[0]} "
                f"from {ref}; submit that refactor ref explicitly"
            )


# ---------------------------------------------------------------------------
# History exposure screen (before any source snapshot is shared)
#
# The screen exists because a final tree is not the history that gets pushed:
# an intermediate commit may add prohibited content that a later commit
# deletes. It walks every commit in the unpublished range and reports only a
# path and a category — never the matched line, value or blob content. Already
# integrated exposure is a separate incident; this screen deliberately only
# covers `<tip> ^<last verified remote source tip>`.
# ---------------------------------------------------------------------------

FORBIDDEN_PATH_CATEGORY = "forbidden-path"
CREDENTIAL_CATEGORY = "credential-pattern"

# (basename predicate, reason). Reasons are labels, not content.
_FORBIDDEN_BASENAMES = {
    ".env": "environment file",
    ".netrc": "credential file",
    "id_rsa": "private key file",
    "id_dsa": "private key file",
    "id_ecdsa": "private key file",
    "id_ed25519": "private key file",
    "credentials": "credential file",
    "credentials.json": "credential file",
    "secrets.json": "credential file",
}
# Templates are not secret material; anything else starting with `.env.` is.
_ENV_TEMPLATES = frozenset({".env.example", ".env.sample", ".env.template"})
# (compiled pattern, reason). Every hit is reported as CREDENTIAL_CATEGORY; the
# reason is deliberately generic so a file layout cannot leak the match shape.
_CREDENTIAL_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE if flags else 0)
    for pattern, flags in (
        (r"AKIA[0-9A-Z]{16}", 0),
        (r"ASIA[0-9A-Z]{16}", 0),
        (r"gh[pousr]_[A-Za-z0-9]{20,}", 0),
        (r"github_pat_[A-Za-z0-9_]{20,}", 0),
        (r"xox[abprs]-[A-Za-z0-9-]{10,}", 0),
        (r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----", 0),
        (r"sk-[A-Za-z0-9]{20,}", 0),
        (r"\b[A-Za-z0-9_]*(?:api[_-]?key|secret|passwd|password|token)\b\s*[:=]\s*['\"]?"
         r"[A-Za-z0-9_./+=-]{16,}", re.IGNORECASE),
        (r"\bbearer\s+[A-Za-z0-9._~+/-]{20,}=*", re.IGNORECASE),
        (r"[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@", re.IGNORECASE),
    )
)


def _forbidden_path_reason(path: str) -> str | None:
    name = path.rsplit("/", 1)[-1].lower()
    if name.startswith(".env.") and name not in _ENV_TEMPLATES:
        return "environment file"
    if name == ".env":
        return "environment file"
    if name in _FORBIDDEN_BASENAMES:
        return _FORBIDDEN_BASENAMES[name]
    if name.rsplit(".", 1)[-1] in ("pem", "key", "p12", "pfx", "kdbx") and "." in name:
        return "key material file"
    return None


def _added_lines_in_commit(repo: Path, sha: str) -> list[tuple[str, str]]:
    """(path, added line) pairs for one commit.

    A normal commit contributes its added lines. A merge contributes only the
    conflict-resolution lines (``--cc`` combined diff), because content coming
    from either parent is already screened in that parent's own commit: this is
    what catches a credential introduced while resolving a conflict.
    """
    parents = git(repo, "show", "-s", "--format=%P", sha)
    if parents.returncode != 0:
        raise _git_error(parents, f"show {sha}")
    parent_count = len(parents.stdout.split())
    args = ["show", "--format=", "--unified=0", "--no-color", "--no-ext-diff", "--no-textconv"]
    if parent_count > 1:
        args.append("--cc")
    result = git(repo, *args, sha)
    if result.returncode != 0:
        raise _git_error(result, f"show {sha}")
    prefix = "+" if parent_count <= 1 else "++"
    pairs: list[tuple[str, str]] = []
    current = ""
    for line in result.stdout.splitlines():
        if line.startswith("+++ b/") or line.startswith("+++ /dev/null"):
            current = "" if line.startswith("+++ /dev/null") else line[6:].split("\t", 1)[0]
        elif line.startswith(prefix) and len(line) > len(prefix):
            pairs.append((current, line[len(prefix):]))
    return pairs


def screen_source_history(repo: Path, tip: str, base_tip: str | None = None) -> dict:
    """Screen the whole unpublished source range, returning paths and categories only.

    `base_tip` is the last verified remote source tip (``None`` screens the whole
    history). Every commit in ``git rev-list <tip> ^<base_tip>`` is inspected:
    changed paths for forbidden file names and added lines for suspected
    credential material. The result never carries a matched value, line or
    blob, so it is safe to print and persist; semantic profile-scope review
    remains the reviewing agent's job.
    """
    tip_sha = _resolve_commit(repo, tip, "source tip")
    base_sha = _resolve_commit(repo, base_tip, "integrated source tip") if base_tip else ""
    if base_sha:
        result = git(repo, "rev-list", "--reverse", tip_sha, f"^{base_sha}")
    else:
        result = git(repo, "rev-list", "--reverse", tip_sha)
    if result.returncode != 0:
        raise _git_error(result, "rev-list")
    commits = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    findings: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    def add(commit: str, path: str, category: str, reason: str) -> None:
        key = (commit, path, category)
        if key in seen:
            return
        seen.add(key)
        findings.append({"commit": commit, "path": path, "category": category,
                         "reason": reason})

    for commit in commits:
        listed = git(repo, "show", "--format=", "--name-only", "-z", commit)
        if listed.returncode != 0:
            raise _git_error(listed, f"show {commit}")
        for path in listed.stdout.split("\0"):
            path = path.strip()
            if not path:
                continue
            reason = _forbidden_path_reason(path)
            if reason:
                add(commit, path, FORBIDDEN_PATH_CATEGORY, reason)
        for path, line in _added_lines_in_commit(repo, commit):
            if any(pattern.search(line) for pattern in _CREDENTIAL_PATTERNS):
                add(commit, path or "<unknown>", CREDENTIAL_CATEGORY,
                    "suspected credential material")

    return {
        "tip": tip_sha,
        "base_tip": base_sha,
        "commits": commits,
        "findings": findings,
    }


def _require_unexposed_history(repo: Path, main: str, tip: str) -> None:
    findings = screen_source_history(repo, tip, main)["findings"]
    if findings:
        details = sorted({(row["path"], row["category"]) for row in findings})
        raise WorkflowError("source history exposure incident: " + "; ".join(
            f"{json.dumps(path, ensure_ascii=True)} [{category}]" for path, category in details))


def history_review_digest(payload: Mapping[str, Any]) -> str:
    """Digest binding an agent's semantic review to one tip and its exact commits.

    Only the semantic fields enter the digest (schema, tip, scope and the
    per-commit classification rows); timestamps and the mechanical findings do
    not, so a re-run after a clock change stays stable.
    """
    commits = []
    for row in payload.get("commits") or []:
        if not isinstance(row, Mapping):
            raise WorkflowError("history review commit rows must be objects")
        commits.append({
            "sha": _text(row.get("sha"), "history review commit sha"),
            "classification": _text_in(row.get("classification"),
                                       "history review classification",
                                       HISTORY_CLASSIFICATIONS),
            "reason": _text(row.get("reason"), "history review reason"),
        })
    canonical = {
        "schema": int(payload.get("schema") or HISTORY_REVIEW_SCHEMA),
        "tip": _text(payload.get("tip"), "history review tip"),
        "scope": _text(payload.get("scope"), "history review scope"),
        "commits": commits,
    }
    return hashlib.sha256(canonical_bytes(canonical)).hexdigest()


def _new_candidate_state(
    config: Mapping[str, Any],
    entry: Mapping[str, Any],
    kind: str,
    main_sha: str,
    source_sha: str,
    cid: str,
) -> dict:
    return {
        "schema": WORKFLOW_SCHEMA,
        "id": cid,
        "repo_id": config["repo_id"],
        "kind": kind,
        "source_ref": entry["ref"],
        "source_machine": entry["machine"],
        "source_profile": entry["profile"],
        "main_sha": main_sha,
        "source_sha": source_sha,
        "policy": config["policy"],
        "status": "captured",
        "created_at": _utc_now(),
        "worktree": "",
        "input_paths": [],
        "conflict_paths": [],
        "review_digest": "",
        "reviewed_tree": "",
        "checks_digest": "",
        "report_relative_path": "",
        "report_sha256": "",
        "result_sha": "",
        "last_error": "",
        "attempts": 0,
        # Explicit monitor/retry state: only --retry advances it, once per call.
        "retry_generation": 0,
        # Integration/receipt fields are created empty so every journal has one
        # stable shape; they are filled only from observed evidence.
        "result_observed_at": "",
        "receipt_sha256": "",
        "receipt_verified_at": "",
        "receipt_attempts": 0,
        "incident": "",
    }


def _assert_captured_inputs(
    state: Mapping[str, Any],
    cid: str,
    config: Mapping[str, Any],
    entry: Mapping[str, Any],
    kind: str,
    main_sha: str,
    source_sha: str,
) -> None:
    expected = {
        "repo_id": config["repo_id"],
        "kind": kind,
        "source_ref": entry["ref"],
        "main_sha": main_sha,
        "source_sha": source_sha,
    }
    for field, value in expected.items():
        if state.get(field) != value:
            raise WorkflowError(
                f"candidate journal {cid} does not match the captured inputs ({field})"
            )


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------


def _capture_refactor(repo: Path, store: Path, config: Mapping[str, Any], source: Any) -> dict:
    """Capture the exact tip of one explicit submission; never discover refs.

    The submission record is the authorisation: the journal cannot be created
    (or later loaded) without it. A submission whose main is no longer the
    current remote main is stale and must be renewed with a merge on the
    refactor branch — this is never extended silently.
    """
    given = _mapping(source, "source")
    extra = sorted(set(given) - {"ref"})
    if extra:
        raise WorkflowError(
            "refactor capture takes only a ref; identity comes from maintainer_identity, "
            f"not from caller fields: {', '.join(extra)}")
    ref = _refactor_ref(given.get("ref"))
    _require_report_scope(config, ref, config["maintainer_identity"]["scope"])
    remote = config["remote"]
    _fetch_inputs(repo, remote)
    main_sha = _resolve_commit(
        repo, f"refs/remotes/{remote}/{MAIN_BRANCH}", f"{remote}/{MAIN_BRANCH}")
    submissions = [record for record in refactor_submissions(store) if record["ref"] == ref]
    current = [record for record in submissions if record["main_sha"] == main_sha]
    if not current:
        if submissions:
            stale = max(submissions, key=lambda record: record["submitted_at"])
            raise WorkflowError(
                f"refactor submission for {ref} is stale: submitted main {stale['main_sha']} "
                f"is not the current remote main {main_sha}; merge {remote}/{MAIN_BRANCH} into "
                f"{ref}, review the merged result and submit the new exact tip")
        raise WorkflowError(
            f"refactor ref {ref} has no exact-tip submission; run --submit-refactor with the "
            "ref, tip and brief (a pushed backup branch is not readiness)")
    if len(current) > 1:
        tip_result = git(repo, "rev-parse", "--verify", "--quiet",
                         f"{_remote_tracking_ref(remote, ref)}^{{commit}}")
        remote_tip = tip_result.stdout.strip() if tip_result.returncode == 0 else ""
        exact = [record for record in current if record["tip"] == remote_tip]
        if len(exact) != 1:
            raise WorkflowError(
                f"multiple refactor submissions for {ref} at main {main_sha}; "
                "submit the current exact tip again")
        submission = exact[0]
    else:
        submission = current[0]

    tip = submission["tip"]
    tip_result = git(repo, "rev-parse", "--verify", "--quiet",
                     f"{_remote_tracking_ref(remote, ref)}^{{commit}}")
    if tip_result.returncode != 0:
        raise WorkflowError(f"refactor ref {ref} no longer exists on {remote}")
    remote_tip = tip_result.stdout.strip()
    if not is_ancestor(repo, tip, remote_tip):
        raise WorkflowError(
            f"submitted refactor tip {tip} is not contained in the current {ref} tip "
            f"{remote_tip}; submit the new exact tip")
    if not is_ancestor(repo, main_sha, tip):
        raise WorkflowError(
            f"submitted refactor tip {tip} does not contain the captured main {main_sha}; "
            f"merge {remote}/{MAIN_BRANCH} into {ref} and submit the merged exact tip")

    _require_unexposed_history(repo, main_sha, tip)
    identity = submission["maintainer_identity"]
    entry = {"ref": ref, "machine": identity["machine"], "profile": identity["profile"]}
    cid = submission["id"]
    state_file = _candidate_path(store, cid, STATE_FILE)
    if state_file.is_file():
        state = load_candidate(store, cid)
        _assert_captured_inputs(state, cid, config, entry, "refactor", main_sha, tip)
        _pin_inputs(repo, cid, main_sha, tip)
        return state

    _pin_inputs(repo, cid, main_sha, tip)
    state = _new_candidate_state(config, entry, "refactor", main_sha, tip, cid)
    _validate_state(store, state, cid, config)
    _write_candidate_state(store, cid, state)
    return _public_state(state, store)


def capture(repo: Path, store: Path, source: dict, kind: str = "transport") -> dict:
    """Capture immutable fetched M and T and persist an idempotent candidate.

    One fetch, then M and T are resolved from the fetched remote-tracking refs
    and pinned under `refs/hermes-sync/candidates/<cid>/`. The maintainer clone's
    HEAD and index are never touched. Transport sources come from the registry;
    a refactor tip comes only from an explicit submission record.
    """
    kind = _text_in(kind, "kind", KINDS)
    store_path = _store_path(store)
    config = _read_config(store_path)
    _assert_maintainer(repo, config)
    _assert_store_outside_repo(repo, store_path)

    if kind == "refactor":
        return _capture_refactor(repo, store_path, config, source)

    entry = _registry_entry(config, source)
    ref = entry["ref"]
    if ref.startswith("refs/heads/refactor/"):
        raise WorkflowError(f"refactor ref cannot be captured as transport: {ref}")

    remote = config["remote"]
    _fetch_inputs(repo, remote)
    main_sha = _resolve_commit(
        repo, f"refs/remotes/{remote}/{MAIN_BRANCH}", f"{remote}/{MAIN_BRANCH}"
    )
    source_sha = _resolve_commit(repo, _remote_tracking_ref(remote, ref), ref)
    _require_unexposed_history(repo, main_sha, source_sha)
    cid = candidate_id(config["repo_id"], ref, main_sha, source_sha, config["policy"], kind)

    state_file = _candidate_path(store_path, cid, STATE_FILE)
    if state_file.is_file():
        state = load_candidate(store_path, cid)
        _assert_captured_inputs(state, cid, config, entry, kind, main_sha, source_sha)
        _pin_inputs(repo, cid, main_sha, source_sha)
        return state

    validate_source_history(repo, main_sha, source_sha, _known_refactor_refs(repo, remote))
    _pin_inputs(repo, cid, main_sha, source_sha)
    state = _new_candidate_state(config, entry, kind, main_sha, source_sha, cid)
    _validate_state(store_path, state, cid, config)
    _write_candidate_state(store_path, cid, state)
    return _public_state(state, store_path)


# ---------------------------------------------------------------------------
# Preparation: detached candidate worktree plus one native merge
# ---------------------------------------------------------------------------

_ZERO_OID_RE = re.compile(r"\A0+\Z")


def _result_tail(result: subprocess.CompletedProcess) -> str:
    detail = (result.stderr or result.stdout or "").strip().splitlines()
    return detail[-1][:400] if detail else "no output"


def _verify_pins(repo: Path, cid: str, main_sha: str, source_sha: str) -> None:
    """Resolution must come from the pinned input refs, not remote branches."""
    for name, expected in (("main", main_sha), ("source", source_sha)):
        ref = f"{PIN_ROOT}/{cid}/{name}"
        result = git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
        if result.returncode != 0:
            raise WorkflowError(f"captured input is not pinned: {ref}")
        actual = result.stdout.strip()
        if actual != expected:
            raise WorkflowError(f"captured pin {ref} names {actual}, expected {expected}")


def _assert_candidate_dir_allowed(worktree: Path, config: Mapping[str, Any]) -> None:
    """Refuse a candidate checkout inside runtime, report or maintainer roots."""
    candidate = Path(worktree).resolve()
    protected = [("runtime root", root) for root in config["runtime_roots"]]
    protected.append(("report root", config["report"]["path"]))
    protected.append(("maintainer repository", config["maintainer_repo"]))
    for label, root in protected:
        resolved = Path(root).resolve()
        if candidate == resolved or resolved in candidate.parents:
            raise WorkflowError(
                f"candidate worktree {candidate} is inside the {label} {resolved}"
            )


def _diff_entries(repo: Path, older: str, newer: str) -> list[dict]:
    """Changed paths and modes between two commits, without rename detection.

    `--no-renames` deliberately reports a rename as delete plus add so both
    paths stay visible to the review scope. Modes and blob ids come from Git's
    raw diff; no blob content is decoded as text.
    """
    result = git_bytes(
        repo,
        "diff",
        "--raw",
        "-z",
        "--no-renames",
        "--no-ext-diff",
        "--no-textconv",
        "--abbrev=40",
        older,
        newer,
    )
    if result.returncode != 0:
        raise _git_error(result, "diff --raw")
    tokens = result.stdout.split(b"\0")
    entries: list[dict] = []
    index = 0
    while index < len(tokens) and tokens[index]:
        header = tokens[index]
        index += 1
        if not header.startswith(b":"):
            raise WorkflowError("unexpected git diff --raw output while prechecking inputs")
        fields = header[1:].split(b" ")
        if len(fields) != 5:
            raise WorkflowError("unexpected git diff --raw header while prechecking inputs")
        old_mode, new_mode, old_sha, new_sha, status = (field.decode("ascii") for field in fields)
        if index >= len(tokens):
            raise WorkflowError("truncated git diff --raw output while prechecking inputs")
        raw_path = tokens[index]
        index += 1
        try:
            path = raw_path.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise WorkflowError("unsupported non-UTF-8 path in the merge inputs") from exc
        _validate_git_path(path, "merge input path")
        entries.append(
            {
                "path": path,
                "old_mode": old_mode,
                "new_mode": new_mode,
                "old_sha": old_sha,
                "new_sha": new_sha,
                "status": status,
            }
        )
    return entries


def _input_paths(repo: Path, base: str, tip: str) -> list[str]:
    """Source-side review scope: every path T changes relative to the merge base."""
    return sorted({entry["path"] for entry in _diff_entries(repo, base, tip)})


def _blob_is_binary(repo: Path, blob_sha: str) -> bool:
    result = git_bytes(repo, "cat-file", "blob", blob_sha)
    if result.returncode != 0:
        raise _git_error(result, "cat-file blob")
    return b"\0" in result.stdout[:8000]


def _attribute_blobs(repo: Path, revision: str) -> list[tuple[str, str]]:
    """Every `.gitattributes` blob reachable from a revision."""
    result = git_bytes(repo, "ls-tree", "-r", "-z", "--full-tree", revision)
    if result.returncode != 0:
        raise _git_error(result, "ls-tree")
    found: list[tuple[str, str]] = []
    for record in result.stdout.split(b"\0"):
        if not record or b"\t" not in record:
            continue
        meta, raw_path = record.split(b"\t", 1)
        fields = meta.split(b" ")
        if len(fields) != 3:
            continue
        mode, object_type, sha = fields
        if object_type != b"blob":
            continue
        if raw_path.rsplit(b"/", 1)[-1] != b".gitattributes":
            continue
        try:
            path = raw_path.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise WorkflowError("unsupported non-UTF-8 .gitattributes path") from exc
        found.append((path, sha.decode("ascii")))
    return found


def _merge_drivers(repo: Path, blob_sha: str) -> set[str]:
    """Attribute names outside the builtin set; config definitions are checked separately."""
    result = git_bytes(repo, "cat-file", "blob", blob_sha)
    if result.returncode != 0:
        raise _git_error(result, "cat-file blob")
    return _custom_merge_drivers(result.stdout.decode("utf-8", "replace"))


def _custom_merge_drivers(text: str) -> set[str]:
    """Inspect attribute text without executing configured implementations."""
    drivers: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) < 2:
            continue
        for token in fields[1:]:
            if not token.startswith("merge="):
                continue
            value = token[len("merge="):].strip('"')
            if value and value not in BUILTIN_MERGE_DRIVERS:
                drivers.add(value)
    return drivers


def _configured_merge_problems(repo: Path) -> list[str]:
    """Config includes local/global/includes; attributes also live outside trees."""
    problems: list[str] = []
    definitions = git(repo, "config", "--includes", "--null", "--name-only", "--get-regexp",
                      r"^merge\..*\.driver$")
    if definitions.returncode not in (0, 1):
        raise _git_error(definitions, "config merge.*.driver")
    if definitions.returncode == 0:
        # A configured implementation is external even when called text/binary/
        # union/normal, or when no attribute/default currently selects it.
        problems.append("merge.*.driver defines an unsupported external merge driver")
    defaults = git(repo, "config", "--null", "--get-all", "merge.default")
    if defaults.returncode not in (0, 1):
        raise _git_error(defaults, "config merge.default")
    if any(value not in BUILTIN_MERGE_DRIVERS for value in defaults.stdout.split("\0") if value):
        problems.append("merge.default configures an unsupported external merge driver")
    configured = git(repo, "config", "--null", "--path", "--get-all", "core.attributesFile")
    if configured.returncode not in (0, 1):
        raise _git_error(configured, "config core.attributesFile")
    paths = [git_common_dir(repo) / "info" / "attributes"]
    if configured.returncode == 0:
        for value in configured.stdout.split("\0"):
            if not value:
                continue
            path = Path(value)
            if not path.is_absolute():
                # Its meaning changes in the candidate checkout; fail closed.
                problems.append("core.attributesFile has an unsupported relative merge attributes path")
            else:
                paths.append(path)
    else:
        paths.append(Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
                     / "git" / "attributes")
    for path in dict.fromkeys(paths):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise WorkflowError("cannot inspect merge attributes configuration") from exc
        if _custom_merge_drivers(text):
            problems.append(f"{path} configures an unsupported external merge driver")
    return problems


def _precheck_inputs(repo: Path, base: str, main_sha: str, source_sha: str) -> list[str]:
    """Unsupported file kinds/bytes/drivers are refused before any merge runs."""
    problems: dict[str, str] = {}
    blob_cache: dict[str, bool] = {}
    for label, revision in (("main", main_sha), ("source", source_sha)):
        for entry in _diff_entries(repo, base, revision):
            path = entry["path"]
            for mode_key in ("old_mode", "new_mode"):
                mode = entry[mode_key]
                if mode in SUPPORTED_MODES:
                    continue
                kind = {
                    MODE_SYMLINK: "symlink",
                    MODE_GITLINK: "submodule",
                }.get(mode, f"mode {mode}")
                problems.setdefault(
                    f"{path}|{mode}",
                    f"{path} is an unsupported {kind} artifact on {label}",
                )
            for mode_key, sha_key in (("old_mode", "old_sha"), ("new_mode", "new_sha")):
                mode, sha = entry[mode_key], entry[sha_key]
                if mode not in (MODE_FILE, MODE_EXECUTABLE) or _ZERO_OID_RE.match(sha):
                    continue
                binary = blob_cache.get(sha)
                if binary is None:
                    binary = _blob_is_binary(repo, sha)
                    blob_cache[sha] = binary
                if binary:
                    problems.setdefault(
                        f"{path}|binary",
                        f"{path} is a binary blob on {label}",
                    )
    for label, revision in (("merge base", base), ("main", main_sha), ("source", source_sha)):
        for path, blob_sha in _attribute_blobs(repo, revision):
            drivers = _merge_drivers(repo, blob_sha)
            if drivers:
                problems.setdefault(
                    f"{path}|driver",
                    f"{path} on {label} configures unsupported custom merge driver(s) "
                    f"{', '.join(sorted(drivers))}; external drivers are never executed",
                )
    return list(problems.values())


def _unmerged_paths(worktree: Path) -> list[str]:
    """Conflict paths from the real index, NUL-delimited and never text-guessed."""
    result = git_bytes(worktree, "ls-files", "-u", "-z")
    if result.returncode != 0:
        raise _git_error(result, "ls-files -u")
    paths: list[str] = []
    for record in result.stdout.split(b"\0"):
        if not record:
            continue
        if b"\t" not in record:
            raise WorkflowError("unexpected git ls-files -u output")
        _meta, raw_path = record.split(b"\t", 1)
        try:
            path = raw_path.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise WorkflowError("unsupported non-UTF-8 conflict path") from exc
        _validate_git_path(path, "conflict path")
        if path not in paths:
            paths.append(path)
    return sorted(paths)


def _worktree_revisions(worktree: Path) -> dict | None:
    head = git(worktree, "rev-parse", "--verify", "--quiet", "HEAD")
    if head.returncode != 0:
        return None
    merge_head = git(worktree, "rev-parse", "--verify", "--quiet", "MERGE_HEAD")
    return {
        "head": head.stdout.strip(),
        "merge_head": merge_head.stdout.strip() if merge_head.returncode == 0 else "",
    }


def _same_repository(repo: Path, worktree: Path) -> bool:
    """A candidate worktree must share the maintainer's common Git directory."""
    left = git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    right = git(worktree, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if left.returncode != 0 or right.returncode != 0:
        return False
    return Path(left.stdout.strip()).resolve() == Path(right.stdout.strip()).resolve()


def _registered_worktrees(repo: Path) -> set[Path]:
    result = git(repo, "worktree", "list", "--porcelain")
    if result.returncode != 0:
        raise _git_error(result, "worktree list")
    registered: set[Path] = set()
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            registered.add(Path(line[len("worktree "):]).resolve())
    return registered


def _block_candidate(
    store: Path,
    cid: str,
    state: Mapping[str, Any],
    worktree: Path,
    input_paths: list[str],
    conflict_paths: list[str],
    message: str,
    config: Mapping[str, Any],
) -> None:
    """Persist blocked evidence, then refuse: no silent retry loop."""
    updated = _persisted_state(state)
    updated.update(
        status="blocked",
        worktree=str(worktree),
        input_paths=list(input_paths),
        conflict_paths=list(conflict_paths),
        last_error=message,
        attempts=state["attempts"] + 1,
    )
    _validate_state(store, updated, cid, config)
    _write_candidate_state(store, cid, updated)
    raise WorkflowError(message)


def _persist_prepared(
    store: Path,
    cid: str,
    state: Mapping[str, Any],
    worktree: Path,
    input_paths: list[str],
    conflict_paths: list[str],
    config: Mapping[str, Any],
) -> dict:
    updated = _persisted_state(state)
    updated.update(
        status="prepared",
        worktree=str(worktree),
        input_paths=list(input_paths),
        conflict_paths=list(conflict_paths),
        last_error="",
        attempts=state["attempts"] + 1,
    )
    _validate_state(store, updated, cid, config)
    _write_candidate_state(store, cid, updated)
    return _public_state(updated, store)


def prepare(repo: Path, store: Path, candidate: dict) -> dict:
    """Create the detached candidate worktree and stop with a real merge index.

    Isolation: the worktree lives under `<store>/worktrees/<cid>/`, never inside
    a runtime discovery root, report root or the maintainer checkout; repository
    hooks and rerere are disabled in the maintainer's own config. The merge is
    native `git merge --no-ff --no-commit T`, so `MERGE_HEAD` is exactly T and
    the index is the complete proposed tree. Exit status 1 is accepted only
    when the index really lists unmerged entries; everything else blocks.
    """
    store_path = _store_path(store)
    config = _read_config(store_path)
    _assert_maintainer(repo, config)
    _assert_store_outside_repo(repo, store_path)

    cid = candidate.get("id") if isinstance(candidate, Mapping) else None
    if not isinstance(cid, str) or not _CID_RE.match(cid):
        raise WorkflowError("prepare requires a captured candidate with a full id")
    state = load_candidate(store_path, cid)
    _require_candidate_report_scope(state, config)
    worktree_path = safe_relative(store_path, f"{WORKTREES_DIR}/{cid}")
    recorded = state["worktree"]
    if recorded and Path(recorded).resolve() != worktree_path.resolve():
        raise WorkflowError(
            f"candidate {cid} journal names a different worktree ({recorded})"
        )
    _assert_candidate_dir_allowed(worktree_path, config)

    if state["status"] == "blocked":
        detail = state["last_error"] or "no recorded detail"
        raise WorkflowError(
            f"candidate {cid} is blocked: {detail}; "
            f"inspect {state['worktree'] or worktree_path} and retry explicitly"
        )

    if worktree_path.is_symlink():
        raise WorkflowError(
            f"candidate worktree path is a symlink, refusing it: {worktree_path}"
        )

    if worktree_path.exists():
        revisions = _worktree_revisions(worktree_path)
        consistent = (
            revisions is not None
            and _same_repository(repo, worktree_path)
            and revisions["head"] == state["main_sha"]
            and revisions["merge_head"] == state["source_sha"]
        )
        if not consistent:
            raise WorkflowError(
                f"candidate worktree already exists in an inconsistent state: {worktree_path}; "
                "inspect it and remove it deliberately (it is never deleted automatically)"
            )
        if state["status"] != "captured":
            # Already prepared (or further along): never re-merge or discard work.
            return state
        # Crash after Git completed the merge but before the journal write:
        # adopt the consistent worktree and record the computed evidence.
        base = _merge_base(repo, state)
        input_paths = _input_paths(repo, base, state["source_sha"])
        conflict_paths = _unmerged_paths(worktree_path)
        return _persist_prepared(
            store_path, cid, state, worktree_path, input_paths, conflict_paths, config
        )

    if worktree_path in _registered_worktrees(repo):
        raise WorkflowError(
            f"candidate worktree is registered but missing on disk: {worktree_path}; "
            "inspect and prune it deliberately"
        )
    if state["status"] != "captured":
        raise WorkflowError(
            f"candidate {cid} is {state['status']} but its worktree is missing: {worktree_path}"
        )

    _verify_pins(repo, cid, state["main_sha"], state["source_sha"])
    base = _merge_base(repo, state)
    input_paths = _input_paths(repo, base, state["source_sha"])

    problems = _configured_merge_problems(repo)
    problems.extend(_precheck_inputs(repo, base, state["main_sha"], state["source_sha"]))
    if problems:
        _block_candidate(
            store_path,
            cid,
            state,
            worktree_path,
            input_paths,
            [],
            "unsupported merge input: " + "; ".join(problems),
            config,
        )

    hooks_path = store_path / HOOKS_DISABLED_DIR / cid
    if hooks_path.exists():
        raise WorkflowError(f"hook isolation path unexpectedly exists: {hooks_path}")
    git(repo, "config", "--local", "core.hooksPath", str(hooks_path), check=True)
    git(repo, "config", "--local", "rerere.enabled", "false", check=True)
    try:
        (store_path / WORKTREES_DIR).mkdir(exist_ok=True)
    except OSError as exc:
        raise WorkflowError(f"cannot create the candidate worktree root: {exc}") from exc

    added = git(repo, "worktree", "add", "--detach", str(worktree_path), state["main_sha"])
    if added.returncode != 0:
        _block_candidate(
            store_path,
            cid,
            state,
            worktree_path,
            input_paths,
            [],
            f"cannot create the candidate worktree: {_result_tail(added)}",
            config,
        )

    try:
        merged = git(
            worktree_path,
            "merge",
            "--no-ff",
            "--no-commit",
            state["source_sha"],
            extra_env={"GIT_MERGE_AUTOEDIT": "no", "GIT_ATTR_NOSYSTEM": "1"},
        )
    except WorkflowError as exc:
        _block_candidate(
            store_path, cid, state, worktree_path, input_paths, [],
            f"native merge could not run: {exc}", config,
        )
        raise
    conflict_paths = _unmerged_paths(worktree_path)
    head = git(worktree_path, "rev-parse", "--verify", "--quiet", "HEAD")
    merge_head = git(worktree_path, "rev-parse", "--verify", "--quiet", "MERGE_HEAD")
    head_sha = head.stdout.strip() if head.returncode == 0 else ""
    merge_sha = merge_head.stdout.strip() if merge_head.returncode == 0 else ""

    if head_sha != state["main_sha"]:
        _block_candidate(
            store_path, cid, state, worktree_path, input_paths, conflict_paths,
            f"candidate worktree HEAD is not M after merging ({head_sha or 'unknown'})",
            config,
        )
    if merge_sha != state["source_sha"]:
        _block_candidate(
            store_path, cid, state, worktree_path, input_paths, conflict_paths,
            f"native merge did not preserve MERGE_HEAD=T ({merge_sha or 'missing'})",
            config,
        )
    if merged.returncode not in (0, 1):
        _block_candidate(
            store_path, cid, state, worktree_path, input_paths, conflict_paths,
            f"native merge failed ({merged.returncode}): {_result_tail(merged)}",
            config,
        )
    if merged.returncode == 1 and not conflict_paths:
        _block_candidate(
            store_path, cid, state, worktree_path, input_paths, conflict_paths,
            "native merge exited 1 without any unmerged index entries",
            config,
        )

    return _persist_prepared(
        store_path, cid, state, worktree_path, input_paths, conflict_paths, config
    )


def _merge_base(repo: Path, state: Mapping[str, Any]) -> str:
    result = git(repo, "merge-base", state["main_sha"], state["source_sha"])
    if result.returncode != 0:
        raise WorkflowError("merge inputs have no common merge base")
    base = result.stdout.strip()
    if not _is_full_sha(base):
        raise WorkflowError("merge base did not resolve to a full commit SHA")
    return base


# ---------------------------------------------------------------------------
# Review schema: agent output, never execution permission
# ---------------------------------------------------------------------------

REVIEW_SCHEMA = 1
CHANGE_TYPES = ("addition", "correction", "replacement", "duplicate", "unsuitable", "integration")
DECISIONS = ("accept", "combine", "reject")
CHECK_STATUSES = ("passed", "failed", "not-applicable")

REVIEW_KEYS = frozenset({"schema", "candidate_id", "main_sha", "source_sha", "summary", "files"})
REVIEW_FILE_KEYS = frozenset(
    {"path", "change_type", "decision", "source_anchors", "reason", "replacements"}
)
REVIEW_ANCHOR_KEYS = frozenset({"ref", "path", "quote"})
REVIEW_REPLACEMENT_KEYS = frozenset(
    {"old_ref", "old_path", "old_quote", "new_path", "new_quote", "reason"}
)
CHECK_ROW_KEYS = frozenset({"name", "required", "status", "exit_code", "stdout", "stderr"})

REVIEW_FILE = "review.md"
CHECKS_FILE = "checks.json"

# Fixed, allowlisted validation adapters. `run_checks` builds these argument
# lists itself; nothing from a review or a report is ever executed.
CHECK_INDEX_WHITESPACE = "index-whitespace"
CHECK_STAGED_SYNTAX = "staged-syntax"
CHECK_PACKAGE = "skills/skill-library-maintenance"
CHECK_PACKAGE_TESTS_DIR = f"{CHECK_PACKAGE}/tests"
CHECK_PACKAGE_VALIDATOR = "skills/skill-builder/scripts/skills-ref.sh"
CHECK_AUDIT_SCRIPT = f"{CHECK_PACKAGE}/scripts/audit-skill-library.py"
CHECK_PACKAGE_TESTS = f"package-tests:{CHECK_PACKAGE}"
CHECK_PACKAGE_VALIDATOR_NAME = f"package-validator:{CHECK_PACKAGE}"
CHECK_LIBRARY_AUDIT = "library-audit"
CHECK_TIMEOUT = 900
CHECK_OUTPUT_LIMIT = 20000
# Fixed policy, not candidate config: bind these exact bytes into check evidence.
CHECK_PYTEST_CONFIG = "[pytest]\n"
# Versioned in every package-test plan row, including unchanged/N/A rows.
CHECK_CONFTEST_POLICY = "ast-no-module-pytest-bindings-v4"

# Advisory scope patterns. A hit never vetoes a path or a date by itself; it
# only means the review must name the surviving text and explain why it stays
# (for example a clearly labeled illustrative path).
INSTANCE_PATTERNS = (
    re.compile(r"(?:^|[\s`'\"(])(?:/home|/Users)/[A-Za-z0-9._-]+/"),
    re.compile(r"(?:^|[\s`'\"(])~/[A-Za-z0-9._-]+/"),
    re.compile(r"\b(?:[A-Za-z0-9-]+\.)+(?:local|lan|internal)\b"),
    re.compile(r"\b20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}"),
)


def _exact_keys(value: Any, allowed: frozenset[str], field: str) -> Mapping[str, Any]:
    """Whitelist object keys: unknown fields (commands, flags) are refused."""
    mapping = _mapping(value, field)
    unknown = sorted(str(key) for key in mapping if key not in allowed)
    if unknown:
        raise WorkflowError(f"{field} has unsupported fields: {', '.join(unknown)}")
    missing = sorted(allowed - set(mapping))
    if missing:
        raise WorkflowError(f"{field} is missing fields: {', '.join(missing)}")
    return mapping


def _quote_text(value: Any, field: str) -> str:
    quote = _text(value, field)
    if "\x00" in quote:
        raise WorkflowError(f"{field} must not contain NUL bytes")
    return quote


def _normalize_review(review: Any) -> dict:
    """Structural review validation; Git facts are checked by validate_review."""
    value = _exact_keys(review, REVIEW_KEYS, "review")
    schema = value["schema"]
    if isinstance(schema, bool) or not isinstance(schema, int) or schema != REVIEW_SCHEMA:
        raise WorkflowError(f"review schema must be {REVIEW_SCHEMA}")
    cid = value["candidate_id"]
    if not isinstance(cid, str) or not _CID_RE.match(cid):
        raise WorkflowError("review candidate_id must be a full candidate id")
    main_sha = value["main_sha"]
    source_sha = value["source_sha"]
    for field, sha in (("review main_sha", main_sha), ("review source_sha", source_sha)):
        if not _is_full_sha(sha):
            raise WorkflowError(f"{field} must be a full commit SHA")
    summary = _text(value["summary"], "review summary")
    files: list[dict] = []
    seen: set[str] = set()
    for index, raw in enumerate(_list(value["files"], "review files")):
        entry = _exact_keys(raw, REVIEW_FILE_KEYS, f"review files[{index}]")
        path = _validate_git_path(entry["path"], f"review files[{index}].path")
        if path in seen:
            raise WorkflowError(f"duplicate review path: {path}")
        seen.add(path)
        change_type = _text_in(entry["change_type"], f"{path} change_type", CHANGE_TYPES)
        decision = _text_in(entry["decision"], f"{path} decision", DECISIONS)
        reason = _text(entry["reason"], f"{path} reason")
        anchors: list[dict] = []
        raw_anchors = _list(entry["source_anchors"], f"{path} source_anchors")
        if not raw_anchors:
            raise WorkflowError(f"{path} needs at least one source anchor")
        for position, raw_anchor in enumerate(raw_anchors):
            anchor = _exact_keys(
                raw_anchor, REVIEW_ANCHOR_KEYS, f"{path} source_anchors[{position}]"
            )
            anchor_ref = _text(anchor["ref"], f"{path} anchor ref")
            anchors.append(
                {
                    "ref": anchor_ref,
                    "path": _validate_git_path(anchor["path"], f"{path} anchor path"),
                    "quote": _quote_text(anchor["quote"], f"{path} anchor quote"),
                }
            )
        replacements: list[dict] = []
        for position, raw_replacement in enumerate(
            _list(entry["replacements"], f"{path} replacements")
        ):
            replacement = _exact_keys(
                raw_replacement,
                REVIEW_REPLACEMENT_KEYS,
                f"{path} replacements[{position}]",
            )
            replacements.append(
                {
                    "old_ref": _text(replacement["old_ref"], f"{path} replacement old_ref"),
                    "old_path": _validate_git_path(
                        replacement["old_path"], f"{path} replacement old_path"
                    ),
                    "old_quote": _quote_text(
                        replacement["old_quote"], f"{path} replacement old_quote"
                    ),
                    "new_path": _validate_git_path(
                        replacement["new_path"], f"{path} replacement new_path"
                    ),
                    "new_quote": _quote_text(
                        replacement["new_quote"], f"{path} replacement new_quote"
                    ),
                    "reason": _text(replacement["reason"], f"{path} replacement reason"),
                }
            )
        files.append(
            {
                "path": path,
                "change_type": change_type,
                "decision": decision,
                "source_anchors": anchors,
                "reason": reason,
                "replacements": replacements,
            }
        )
    return {
        "schema": REVIEW_SCHEMA,
        "candidate_id": cid,
        "main_sha": main_sha,
        "source_sha": source_sha,
        "summary": summary,
        "files": files,
    }


def _review_digest(normalized: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(dict(normalized))).hexdigest()


def _require_candidate(candidate: Any) -> Mapping[str, Any]:
    state = _mapping(candidate, "candidate")
    for field in ("id", "main_sha", "source_sha", "input_paths", "worktree"):
        if field not in state:
            raise WorkflowError(f"candidate is missing {field}")
    return state


def _candidate_store(candidate: Any) -> Path:
    """The trusted store carried in memory by load_candidate/capture/prepare."""
    state = _mapping(candidate, "candidate")
    store = state.get("_store")
    if not isinstance(store, Path):
        raise WorkflowError("candidate is missing its trusted store")
    return _store_path(store)


def _bind_review_identity(state: Mapping[str, Any], normalized: Mapping[str, Any]) -> None:
    if normalized["candidate_id"] != state["id"]:
        raise WorkflowError("review candidate_id does not match the candidate")
    if normalized["main_sha"] != state["main_sha"]:
        raise WorkflowError("review main_sha does not match the captured main")
    if normalized["source_sha"] != state["source_sha"]:
        raise WorkflowError("review source_sha does not match the captured source")


def _require_merge_head(state: Mapping[str, Any], worktree: Path) -> None:
    head = git(worktree, "rev-parse", "--verify", "--quiet", "HEAD")
    if head.returncode != 0 or head.stdout.strip() != state["main_sha"]:
        raise WorkflowError(
            f"candidate worktree HEAD is not the captured main {state['main_sha']}"
        )
    merge_head = git(worktree, "rev-parse", "--verify", "--quiet", "MERGE_HEAD")
    if merge_head.returncode != 0 or merge_head.stdout.strip() != state["source_sha"]:
        raise WorkflowError(
            f"candidate worktree MERGE_HEAD is not the captured source {state['source_sha']}"
        )


def _staged_paths(worktree: Path, main_sha: str) -> list[str]:
    """Paths whose index entry differs from M, with both sides of a rename."""
    result = git_bytes(
        worktree,
        "diff",
        "--cached",
        "--name-only",
        "-z",
        "--no-renames",
        "--no-ext-diff",
        main_sha,
    )
    if result.returncode != 0:
        raise _git_error(result, "diff --cached --name-only")
    paths: list[str] = []
    for record in result.stdout.split(b"\0"):
        if not record:
            continue
        try:
            path = record.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise WorkflowError("unsupported non-UTF-8 path in the candidate index") from exc
        _validate_git_path(path, "candidate index path")
        paths.append(path)
    return sorted(set(paths))


def _coverage_paths(state: Mapping[str, Any], worktree: Path) -> list[str]:
    """Review scope: staged changes UNION captured input paths."""
    return sorted(set(_staged_paths(worktree, state["main_sha"])) | set(state["input_paths"]))


def _index_map(worktree: Path) -> dict[str, tuple[str, str]]:
    """Stage-0 index entries only; unmerged stages are checked separately."""
    result = git_bytes(worktree, "ls-files", "--stage", "-z")
    if result.returncode != 0:
        raise _git_error(result, "ls-files --stage")
    entries: dict[str, tuple[str, str]] = {}
    for record in result.stdout.split(b"\0"):
        if not record:
            continue
        if b"\t" not in record:
            raise WorkflowError("unexpected git ls-files --stage output")
        meta, raw_path = record.split(b"\t", 1)
        try:
            mode, sha, stage = meta.decode("ascii").split()
            path = raw_path.decode("utf-8")
        except (UnicodeDecodeError, ValueError) as exc:
            raise WorkflowError("unexpected git ls-files --stage output") from exc
        if stage != "0":
            continue
        entries[path] = (mode, sha)
    return entries


def _blob_text_at(repo: Path, ref: str, path: str) -> str | None:
    """Text of `ref:path`, or None when the path does not exist there."""
    commit = git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    if commit.returncode != 0:
        raise WorkflowError(f"source ref does not resolve to a commit: {ref}")
    lookup = git(repo, "rev-parse", "--verify", "--quiet", f"{ref}:{path}")
    if lookup.returncode != 0:
        return None
    blob_sha = lookup.stdout.strip()
    if not _is_full_sha(blob_sha):
        raise WorkflowError(f"{path} at {ref} is not a regular blob")
    data = git_bytes(repo, "cat-file", "blob", blob_sha)
    if data.returncode != 0:
        raise _git_error(data, "cat-file blob")
    payload = data.stdout
    if b"\0" in payload[:8000]:
        raise WorkflowError(f"{path} at {ref} is a binary blob and cannot be quoted")
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WorkflowError(f"{path} at {ref} is not valid UTF-8 text") from exc


def _index_text(worktree: Path, entry: tuple[str, str], path: str) -> str:
    mode, blob_sha = entry
    if mode not in (MODE_FILE, MODE_EXECUTABLE):
        raise WorkflowError(f"{path} has unsupported staged mode {mode}")
    data = git_bytes(worktree, "cat-file", "blob", blob_sha)
    if data.returncode != 0:
        raise _git_error(data, "cat-file blob")
    payload = data.stdout
    if b"\0" in payload[:8000]:
        raise WorkflowError(f"{path} is a binary blob in the candidate index")
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WorkflowError(f"{path} is not valid UTF-8 text") from exc


def _allowed_anchor_refs(repo: Path, state: Mapping[str, Any]) -> set[str]:
    """Captured M, T and merge bases only, never an arbitrary filesystem object."""
    refs = {state["main_sha"], state["source_sha"]}
    result = git(repo, "merge-base", "--all", state["main_sha"], state["source_sha"])
    if result.returncode != 0:
        raise WorkflowError("merge inputs have no common merge base")
    bases = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not bases:
        raise WorkflowError("merge inputs have no common merge base")
    refs.update(bases)
    return refs


def _validate_anchor(repo: Path, anchor: Mapping[str, Any], allowed_refs: set[str]) -> None:
    if anchor["ref"] not in allowed_refs:
        raise WorkflowError(
            f"anchor ref {anchor['ref']} is not the captured main, source or a merge base"
        )
    text = _blob_text_at(repo, anchor["ref"], anchor["path"])
    if text is None:
        raise WorkflowError(
            f"anchor path {anchor['path']} does not exist at {anchor['ref']}"
        )
    if anchor["quote"] not in text:
        raise WorkflowError(
            f"anchor quote for {anchor['path']} does not occur at {anchor['ref']}"
        )


def _validate_replacement(
    repo: Path,
    replacement: Mapping[str, Any],
    allowed_refs: set[str],
    coverage: set[str],
    index_entries: Mapping[str, tuple[str, str]],
    worktree: Path,
) -> None:
    if replacement["old_ref"] not in allowed_refs:
        raise WorkflowError(
            f"replacement old_ref {replacement['old_ref']} is not the captured main, "
            "source or a merge base"
        )
    for key in ("old_path", "new_path"):
        if replacement[key] not in coverage:
            raise WorkflowError(
                f"replacement {key} {replacement[key]} is outside the reviewed candidate"
            )
    old_text = _blob_text_at(repo, replacement["old_ref"], replacement["old_path"])
    if old_text is None:
        raise WorkflowError(
            f"replacement old path {replacement['old_path']} does not exist at "
            f"{replacement['old_ref']}"
        )
    if replacement["old_quote"] not in old_text:
        raise WorkflowError(
            f"replacement old quote does not occur in {replacement['old_path']} at "
            f"{replacement['old_ref']}"
        )
    staged_entry = index_entries.get(replacement["new_path"])
    if staged_entry is None:
        raise WorkflowError(
            f"replacement new_path {replacement['new_path']} is not present in the "
            "final staged result"
        )
    new_text = _index_text(worktree, staged_entry, replacement["new_path"])
    if replacement["new_quote"] not in new_text:
        raise WorkflowError(
            f"replacement new quote does not occur in the final staged result for "
            f"{replacement['new_path']}"
        )
    if replacement["old_quote"] in new_text:
        raise WorkflowError(
            f"the replaced instruction still occurs in {replacement['new_path']}; "
            "remove the conflicting remnant"
        )
    if replacement["old_path"] != replacement["new_path"]:
        old_entry = index_entries.get(replacement["old_path"])
        if old_entry is not None:
            remaining = _index_text(worktree, old_entry, replacement["old_path"])
            if replacement["old_quote"] in remaining:
                raise WorkflowError(
                    f"the replaced instruction still occurs in {replacement['old_path']}"
                )


def _incoming_added_lines(
    repo: Path, base: str, source_sha: str, path: str
) -> list[str]:
    """Lines T adds relative to the merge base; advisory input to review only."""
    before = _blob_text_at(repo, base, path)
    after = _blob_text_at(repo, source_sha, path)
    if after is None:
        return []
    known = set(before.splitlines()) if before else set()
    added: list[str] = []
    for line in after.splitlines():
        stripped = line.strip()
        if stripped and stripped not in known:
            added.append(stripped)
    return added


def _looks_instance_specific(line: str) -> bool:
    return any(pattern.search(line) for pattern in INSTANCE_PATTERNS)


def _validate_instance_findings(
    repo: Path,
    state: Mapping[str, Any],
    normalized: Mapping[str, Any],
    index_entries: Mapping[str, tuple[str, str]],
    worktree: Path,
) -> None:
    """Surviving incoming instance text must be named and explained by the review.

    This is scope guidance, not a path/date veto: a generalized instruction, a
    removed one and a clearly labeled example all pass. Only text that survives
    into the final staged result without being named in the file's reason fails.
    """
    base = _merge_base(repo, state)
    for entry in normalized["files"]:
        index_entry = index_entries.get(entry["path"])
        if index_entry is None:
            continue
        staged_text = _index_text(worktree, index_entry, entry["path"])
        for line in _incoming_added_lines(repo, base, state["source_sha"], entry["path"]):
            if not _looks_instance_specific(line):
                continue
            if line not in staged_text:
                continue
            if line in entry["reason"]:
                continue
            raise WorkflowError(
                f"{entry['path']}: incoming instance-specific text remains in the final "
                f"staged result and the review does not name it: {line!r}"
            )


def validate_review(candidate: dict, review: dict, repo: Path, worktree: Path) -> None:
    """Check review scope, real source quotes and old->new replacement proof.

    Every decision must cover exactly the staged paths plus the captured input
    paths. Quotes must occur in the named blob at a captured M, T or merge base;
    replacements must exist on both sides and must not leave the replaced
    instruction live in the final staged result. Unknown fields are refused, so
    a review can never carry commands or an `approved` flag.
    """
    state = _require_candidate(candidate)
    normalized = _normalize_review(review)
    _bind_review_identity(state, normalized)
    candidate_worktree = Path(worktree)
    if not candidate_worktree.is_dir():
        raise WorkflowError(f"candidate worktree does not exist: {candidate_worktree}")
    recorded = state.get("worktree")
    if recorded and Path(recorded).resolve() != candidate_worktree.resolve():
        raise WorkflowError("review worktree is not the candidate worktree")
    _require_merge_head(state, candidate_worktree)

    reviewed = [entry["path"] for entry in normalized["files"]]
    coverage = _coverage_paths(state, candidate_worktree)
    missing = sorted(set(coverage) - set(reviewed))
    unexpected = sorted(set(reviewed) - set(coverage))
    if missing or unexpected:
        detail: list[str] = []
        if missing:
            detail.append("missing " + ", ".join(missing))
        if unexpected:
            detail.append("not part of the candidate " + ", ".join(unexpected))
        raise WorkflowError(
            "review does not cover exactly the candidate paths: " + "; ".join(detail)
        )

    allowed_refs = _allowed_anchor_refs(repo, state)
    index_entries = _index_map(candidate_worktree)
    input_paths = set(state["input_paths"])
    for entry in normalized["files"]:
        path = entry["path"]
        if path not in input_paths:
            reason = entry["reason"]
            if path not in reason and Path(path).name not in reason:
                raise WorkflowError(
                    f"{path} is not an input path; the reason must name why that extra "
                    "file was needed"
                )
        for anchor in entry["source_anchors"]:
            _validate_anchor(repo, anchor, allowed_refs)
        for replacement in entry["replacements"]:
            _validate_replacement(
                repo,
                replacement,
                allowed_refs,
                set(coverage),
                index_entries,
                candidate_worktree,
            )
    _validate_instance_findings(
        repo, state, normalized, index_entries, candidate_worktree
    )


# ---------------------------------------------------------------------------
# Final gate: the staged index is the integration artifact
# ---------------------------------------------------------------------------


def _status_entries(worktree: Path) -> list[tuple[str, str]]:
    """Parsed `git status --porcelain -z` rows: (XY, path)."""
    result = git_bytes(worktree, "status", "--porcelain", "-z", "--untracked-files=all")
    if result.returncode != 0:
        raise _git_error(result, "status --porcelain")
    records = result.stdout.split(b"\0")
    entries: list[tuple[str, str]] = []
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        if len(record) < 4:
            raise WorkflowError("unexpected git status --porcelain output")
        code = record[:2].decode("ascii", "replace")
        try:
            path = record[3:].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise WorkflowError("unsupported non-UTF-8 path in git status") from exc
        if code[0] in ("R", "C"):
            # With -z the rename/copy source is a separate record.
            index += 1
        entries.append((code, path))
    return entries


def _dirty_entries(worktree: Path) -> list[tuple[str, str]]:
    """Index/worktree rows that are not a clean, fully staged merge result."""
    dirty: list[tuple[str, str]] = []
    for code, path in _status_entries(worktree):
        if code[1] != " ":
            dirty.append((code, path))
    return dirty


def _validate_staged_blobs(
    worktree: Path,
    index_entries: Mapping[str, tuple[str, str]],
    paths: Sequence[str],
) -> int:
    """Validate the staged blobs, never the dirty working files."""
    checked = 0
    for path in paths:
        entry = index_entries.get(path)
        if entry is None:
            continue
        mode, blob_sha = entry
        if mode not in (MODE_FILE, MODE_EXECUTABLE):
            raise WorkflowError(f"{path} has unsupported staged mode {mode}")
        data = git_bytes(worktree, "cat-file", "blob", blob_sha)
        if data.returncode != 0:
            raise _git_error(data, "cat-file blob")
        payload = data.stdout
        if b"\0" in payload[:8000]:
            raise WorkflowError(f"{path} is a binary blob in the candidate index")
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise WorkflowError(f"{path} is not valid UTF-8 text") from exc
        if path.endswith(".py"):
            try:
                compile(text, path, "exec")
            except SyntaxError as exc:
                raise WorkflowError(
                    f"{path} does not compile: line {exc.lineno}: {exc.msg}"
                ) from exc
        elif path.endswith(".json"):
            try:
                json.loads(text)
            except json.JSONDecodeError as exc:
                raise WorkflowError(f"{path} is not valid JSON: {exc}") from exc
        checked += 1
    return checked


def _require_visible_index(worktree: Path) -> None:
    """Porcelain can hide working bytes behind either of these index flags."""
    result = git_bytes(worktree, "ls-files", "-v", "-z")
    if result.returncode != 0:
        raise _git_error(result, "ls-files -v")
    for record in result.stdout.split(b"\0"):
        # -v lowercases the tag for assume-unchanged; S/s is skip-worktree.
        if record and (record[:1] == b"S" or 97 <= record[0] <= 122):
            raise WorkflowError(
                "candidate index has skip-worktree or assume-unchanged flags; "
                "clear those flags before checks and the final gate")


def _require_clean_merge_index(
    state: Mapping[str, Any], worktree: Path
) -> tuple[str, list[str]]:
    """HEAD==M, MERGE_HEAD==T, visible index, no unmerged/dirty paths or whitespace errors."""
    _require_merge_head(state, worktree)
    _require_visible_index(worktree)
    unmerged = _unmerged_paths(worktree)
    if unmerged:
        raise WorkflowError(
            "candidate index still has unmerged entries: " + ", ".join(unmerged)
        )
    dirty = _dirty_entries(worktree)
    if dirty:
        detail = ", ".join(f"{code} {path}" for code, path in dirty)
        raise WorkflowError(
            "candidate worktree has unstaged or untracked changes: " + detail
        )
    whitespace = git(worktree, "diff", "--cached", "--check")
    if whitespace.returncode != 0:
        raise WorkflowError(
            "candidate index has whitespace errors: " + _result_tail(whitespace)
        )
    written = git(worktree, "write-tree")
    if written.returncode != 0:
        raise _git_error(written, "write-tree")
    tree = written.stdout.strip()
    if not _is_full_sha(tree):
        raise WorkflowError("write-tree did not return a full tree SHA")
    return tree, _staged_paths(worktree, state["main_sha"])


def validate_tree(candidate: dict, worktree: Path, review: dict) -> dict:
    """Validate the actual staged tree and return its tree id and review scope.

    Returns `{"tree": <git tree SHA>, "paths": [<covered paths>]}` only: there is
    deliberately no `ok`/`passed` flag to trust later. The review must cover the
    staged changes UNION the captured input paths, so a dropped path (including
    a deliberately rejected one) cannot vanish from the record.
    """
    state = _require_candidate(candidate)
    normalized = _normalize_review(review)
    _bind_review_identity(state, normalized)
    candidate_worktree = Path(worktree)
    if not candidate_worktree.is_dir():
        raise WorkflowError(f"candidate worktree does not exist: {candidate_worktree}")
    tree, staged = _require_clean_merge_index(state, candidate_worktree)
    if state.get("kind") == "refactor":
        # Unlike transport curation, a refactor has no semantic edits after
        # submission: the staged index must be exactly the submitted tip tree.
        submitted = git(candidate_worktree, "rev-parse", "--verify", "--quiet",
                        f"{state['source_sha']}^{{tree}}")
        if submitted.returncode != 0:
            raise _git_error(submitted, "rev-parse submitted refactor tip")
        submitted_tree = submitted.stdout.strip()
        if tree != submitted_tree:
            raise WorkflowError(
                f"refactor candidate index tree {tree} differs from the submitted tip tree "
                f"{submitted_tree}; edits after submission are refused — commit the change "
                "on the refactor branch, push it and submit the new exact tip")
    coverage = sorted(set(staged) | set(state["input_paths"]))
    reviewed = sorted(entry["path"] for entry in normalized["files"])
    if reviewed != coverage:
        missing = sorted(set(coverage) - set(reviewed))
        unexpected = sorted(set(reviewed) - set(coverage))
        detail: list[str] = []
        if missing:
            detail.append("missing " + ", ".join(missing))
        if unexpected:
            detail.append("not part of the candidate " + ", ".join(unexpected))
        raise WorkflowError(
            "review does not cover exactly the candidate paths: " + "; ".join(detail)
        )
    index_entries = _index_map(candidate_worktree)
    _validate_staged_blobs(candidate_worktree, index_entries, coverage)
    final_tree, final_staged = _require_clean_merge_index(state, candidate_worktree)
    if final_tree != tree or final_staged != staged:
        raise WorkflowError("candidate index changed during the final tree gate")
    return {"tree": tree, "paths": coverage}


# ---------------------------------------------------------------------------
# Allowlisted validation commands: real captured results, never a green flag
# ---------------------------------------------------------------------------


def _tree_paths(repo: Path, revision: str) -> list[str]:
    result = git_bytes(repo, "ls-tree", "-r", "-z", "--name-only", "--full-tree", revision)
    if result.returncode != 0:
        raise _git_error(result, "ls-tree")
    paths: list[str] = []
    for record in result.stdout.split(b"\0"):
        if not record:
            continue
        try:
            paths.append(record.decode("utf-8"))
        except UnicodeDecodeError as exc:
            raise WorkflowError("unsupported non-UTF-8 path in a candidate tree") from exc
    return sorted(set(paths))


def _runner_present(runner: str, kind: str, paths: Sequence[str] | set[str]) -> bool:
    if kind == "file":
        return runner in paths
    return any(path == runner or path.startswith(runner + "/") for path in paths)


def _check_plan(
    state: Mapping[str, Any], worktree: Path, *, materialization: Path | None = None,
    pytest_config: Path | None = None,
) -> list[dict]:
    """Configure every changed package; use stable tree/config tokens in evidence."""
    bound_root = materialization if materialization is not None else Path("<bound-tree>")
    config_path = pytest_config if pytest_config is not None else Path("<check-config>/pytest.ini")
    staged = _staged_paths(worktree, state["main_sha"])
    packages = {"/".join(path.split("/")[:2]) for path in staged
                if path.startswith("skills/") and len(path.split("/")) >= 3}
    index_paths = set(_index_map(worktree))
    main_paths = set(_tree_paths(worktree, state["main_sha"]))
    config = _read_config(_candidate_store(state))
    maintainer = Path(config["maintainer_repo"]).resolve()
    candidates: list[dict] = []
    # Keep the historic maintenance rows (including unchanged N/A), then add
    # explicit rows for other changed packages. Captured-but-rejected paths do
    # not create fake changes; agent-added staged packages DO create checks.
    for package in [CHECK_PACKAGE, *sorted(packages - {CHECK_PACKAGE})]:
        tests = f"{package}/tests"
        unchanged = f"the {package} package is unchanged in this candidate"
        candidates.extend([
            {"name": f"package-tests:{package}", "runner": tests, "kind": "prefix",
             "changed": package in packages, "package": package, "cwd": str(bound_root),
             "execution": "candidate-tests", "tree_source": "git-tree-blobs-readonly-v1",
             # Isolate startup/module resolution from candidate cwd and PYTHON*;
             # -B is explicit because -I ignores PYTHONDONTWRITEBYTECODE.
             # No candidate config or ancestor conftest may control this gate.
             # Package conftests may provide fixtures/helpers, not runner control.
             "conftest_policy": CHECK_CONFTEST_POLICY,
             "pytest_config": CHECK_PYTEST_CONFIG,
             "argv": [sys.executable, "-I", "-B", "-m", "pytest", "-p", "no:cacheprovider",
                      "-c", str(config_path), f"--rootdir={package}", f"--confcutdir={package}",
                      tests, "-q"],
             "unchanged": unchanged},
            {"name": f"package-validator:{package}", "runner": CHECK_PACKAGE_VALIDATOR,
             "kind": "file", "changed": package in packages, "package": package,
             "execution": "trusted-tool", "unchanged": unchanged},
        ])
    candidates.append({
        "name": CHECK_LIBRARY_AUDIT, "runner": CHECK_AUDIT_SCRIPT, "kind": "file",
        "changed": any(path.startswith("skills/") for path in staged),
        "execution": "trusted-tool", "unchanged": "no skill package changed in this candidate",
    })
    plan: list[dict] = []
    for spec in candidates:
        if spec["execution"] == "candidate-tests":
            present = _runner_present(spec["runner"], spec["kind"], index_paths)
        else:
            # Absolute script AND trusted cwd: sibling imports and helper
            # resolution must not come from the unreviewed candidate either.
            runner = safe_relative(maintainer, spec["runner"]).resolve()
            spec["cwd"] = str(maintainer)
            if spec["name"] == CHECK_LIBRARY_AUDIT:
                spec["argv"] = [sys.executable, str(runner), str(bound_root / "skills"), "--json"]
            else:
                spec["argv"] = [str(runner), "validate", str(bound_root / spec["package"])]
            spec["tree_source"] = "git-tree-blobs-readonly-v1"
            present = runner.is_file()
            if spec["changed"] and not present and spec["runner"] in index_paths:
                spec["unavailable"] = "required validation tool is missing from trusted maintainer: " + spec["runner"]
            spec["tool_sha256"] = hashlib.sha256(runner.read_bytes()).hexdigest() if present else ""
        previously = _runner_present(spec["runner"], spec["kind"], main_paths)
        if not spec["changed"]:
            plan.append({**spec, "applicable": False, "required": False, "note": spec["unchanged"]})
        elif previously and not _runner_present(spec["runner"], spec["kind"], index_paths):
            raise WorkflowError("required check runner disappeared from the candidate: " + spec["runner"])
        elif present or spec.get("unavailable"):
            plan.append({**spec, "applicable": True, "required": True, "note": ""})
        elif previously:
            raise WorkflowError("required check runner disappeared from trusted maintainer: " + spec["runner"])
        else:
            plan.append({**spec, "applicable": False, "required": False,
                         "note": f"no runner is configured for {spec['name']} in this repository"})
    return plan


def _check_env(home: Path | None = None) -> dict:
    """Allowlist, not a credentials denylist; never inherit user configuration."""
    env = {
        "PATH": os.pathsep.join(dict.fromkeys((str(Path(sys.executable).parent), os.defpath))),
        "LANG": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PYTHONNOUSERSITE": "1",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
    }
    if home is not None:
        for directory in ("hermes", "config", "cache", "tmp"):
            (home / directory).mkdir()
        env.update(HOME=str(home), HERMES_HOME=str(home / "hermes"),
                   XDG_CONFIG_HOME=str(home / "config"), XDG_CACHE_HOME=str(home / "cache"),
                   TMPDIR=str(home / "tmp"))
    return env


def _run_check_process(argv: Sequence[str], cwd: Path) -> subprocess.CompletedProcess:
    """The single process entry point for validation commands (argument lists)."""
    if not isinstance(argv, (list, tuple)) or not argv:
        raise WorkflowError("a validation command must be a non-empty argument list")
    arguments = [str(argument) for argument in argv]
    try:
        # The only candidate code we run is its pytest suite. Each command gets
        # fresh user/config/cache roots and no inherited keys, agents or plugins.
        with tempfile.TemporaryDirectory(prefix="skill-sync-check-") as directory:
            env = _check_env(Path(directory))
            if arguments[1:5] != ["-I", "-B", "-m", "pytest"]:
                # Trusted wrappers may need operator-installed dependencies
                # (e.g. uvx). Keep only absolute search directories, never cwd;
                # candidate suites retain the restricted system/Python PATH.
                env["PATH"] = os.pathsep.join(
                    part for part in os.environ.get("PATH", os.defpath).split(os.pathsep)
                    if Path(part).is_absolute())
            return subprocess.run(
                arguments,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=CHECK_TIMEOUT,
                env=env,
            )
    except FileNotFoundError as exc:
        raise WorkflowError(f"validation command not found: {arguments[0]}") from exc
    except PermissionError as exc:
        raise WorkflowError(f"validation command is not executable: {arguments[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise WorkflowError(
            f"validation command timed out after {CHECK_TIMEOUT}s: {arguments[0]}"
        ) from exc


def _bounded_output(value: Any) -> str:
    text = value if isinstance(value, str) else ""
    if len(text) > CHECK_OUTPUT_LIMIT:
        return "(truncated) " + text[-CHECK_OUTPUT_LIMIT:]
    return text


def _result_row(name: str, required: bool, result: subprocess.CompletedProcess) -> dict:
    return {
        "name": name,
        "required": required,
        "status": "passed" if result.returncode == 0 else "failed",
        "exit_code": result.returncode,
        "stdout": _bounded_output(result.stdout),
        "stderr": _bounded_output(result.stderr),
    }


def _worktree_fingerprint(worktree: Path) -> tuple[str, bytes]:
    tree = git(worktree, "write-tree")
    status = git_bytes(worktree, "status", "--porcelain", "-z", "--untracked-files=all")
    if status.returncode != 0:
        raise _git_error(status, "status --porcelain")
    return (tree.stdout.strip() if tree.returncode == 0 else "", status.stdout)


def _check_tree_fingerprint(root: Path) -> dict[str, tuple[int, str]]:
    """Include every file/directory, even ignored bytes; never follow a symlink."""
    entries: dict[str, tuple[int, str]] = {}
    try:
        for path in [root, *root.rglob("*")]:
            mode = path.lstat().st_mode
            if stat.S_ISREG(mode):
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
            elif stat.S_ISDIR(mode):
                digest = ""
            else:
                raise WorkflowError("validation commands changed the clean bound-tree materialization")
            entries[str(path.relative_to(root))] = (mode, digest)
    except OSError as exc:
        raise WorkflowError("cannot verify the clean bound-tree materialization") from exc
    return entries


@contextmanager
def _clean_check_tree(repo: Path, tree: str):
    """Materialize raw blobs from one immutable Git tree, without filters/archive attributes.

    Read-only modes prevent accidental edits; a full byte/mode/path fingerprint
    invalidates results if a command alters the copy anyway. This is not an OS sandbox.
    No .git link/index is installed in the copy. TemporaryDirectory owns cleanup,
    including failures/timeouts; unlock only its directories before removal.
    """
    listing = git_bytes(repo, "ls-tree", "-r", "-z", "--full-tree", tree)
    if listing.returncode != 0:
        raise _git_error(listing, "ls-tree bound check tree")
    with tempfile.TemporaryDirectory(prefix="skill-sync-tree-") as directory:
        root = Path(directory)
        try:
            for record in listing.stdout.split(b"\0"):
                if not record:
                    continue
                meta, raw_path = record.split(b"\t", 1)
                mode, kind, sha = meta.decode("ascii").split(" ")
                try:
                    relative = raw_path.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise WorkflowError("unsupported non-UTF-8 path in bound check tree") from exc
                _validate_git_path(relative, "bound check tree path")
                if mode not in (MODE_FILE, MODE_EXECUTABLE) or kind != "blob":
                    raise WorkflowError("unsupported artifact in bound check tree: " + relative)
                payload = git_bytes(repo, "cat-file", "blob", sha)
                if payload.returncode != 0:
                    raise _git_error(payload, "cat-file bound check blob")
                target = safe_relative(root, relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload.stdout)
                target.chmod(0o555 if mode == MODE_EXECUTABLE else 0o444)
            for path in sorted(root.rglob("*"), reverse=True):
                if path.is_dir():
                    path.chmod(0o555)
            root.chmod(0o555)
            before = _check_tree_fingerprint(root)
            yield root
            if _check_tree_fingerprint(root) != before:
                raise WorkflowError("validation commands changed the clean bound-tree materialization")
        finally:
            # Owner code can chmod despite read-only modes; no sandbox is claimed.
            # Do not follow a command-created symlink while unlocking the temp copy.
            if not root.is_symlink() and root.is_dir():
                root.chmod(0o700)
                for parent, directories, _files in os.walk(root, followlinks=False):
                    for name in directories:
                        path = Path(parent) / name
                        if not path.is_symlink():
                            path.chmod(0o700)


class _ConftestRunnerBindings(ast.NodeVisitor):
    """Collect module runner-control bindings and their globals in every scope."""

    # A syntactic policy, not an attempt to evaluate dynamic Python code.
    _DYNAMIC_CALLS = frozenset({"exec", "eval", "compile", "globals", "locals", "setattr", "__import__"})
    _ATTRIBUTE_HOOKS = frozenset({"__getattr__", "__getattribute__", "__dir__"})

    def __init__(self) -> None:
        self.names: set[str] = set()
        self.dynamic_calls: set[str] = set()
        self.wildcard_imports: set[str] = set()
        self.global_names: set[str] = set()
        self.dynamic_references: set[str] = set()
        self.attribute_hooks: set[str] = set()

    def visit_Module(self, node: ast.Module) -> None:
        # A global declaration escapes any local namespace, even in uncalled
        # functions or nested classes. Inspect declarations without treating
        # ordinary local pytest_* or attribute-hook bindings as module names.
        self.global_names.update(name for child in ast.walk(node) if isinstance(child, ast.Global)
                                 for name in child.names
                                 if name.startswith("pytest_") or name in self._ATTRIBUTE_HOOKS)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = (node.func.id if isinstance(node.func, ast.Name) else
                node.func.attr if isinstance(node.func, ast.Attribute) else "")
        if name in self._DYNAMIC_CALLS:
            self.dynamic_calls.add(name)
        self.generic_visit(node)

    def _name(self, name: str) -> None:
        if name.startswith("pytest_"):
            self.names.add(name)  # Includes pytest_plugins, even an empty list.
        elif name in self._ATTRIBUTE_HOOKS:
            self.attribute_hooks.add(name)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id == "__builtins__":
            self.dynamic_references.add(node.id)
        # Assign/AnnAssign/AugAssign/NamedExpr, for/async-for and with/async-with
        # all express their targets as Store names, including starred unpacking.
        if isinstance(node.ctx, ast.Store):
            self._name(node.id)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # Covers bare sys.modules, subscripts and attribute/method chains rooted
        # there without evaluating them or resolving aliases.
        if node.attr == "modules" and isinstance(node.value, ast.Name) and node.value.id == "sys":
            self.dynamic_references.add("sys.modules")
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            # Without `as`, `import a.b` binds a, never b or the dotted string.
            self._name(alias.asname or alias.name.split(".")[0])

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name == "*":
                module = "." * node.level + (node.module or "")
                self.wildcard_imports.add(f"from {module} import *")
            else:
                self._name(alias.asname or alias.name)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name:
            self._name(node.name)
        self.generic_visit(node)

    def visit_MatchAs(self, node: ast.MatchAs | ast.MatchStar) -> None:
        if node.name:
            self._name(node.name)
        self.generic_visit(node)

    visit_MatchStar = visit_MatchAs

    def visit_MatchMapping(self, node: ast.MatchMapping) -> None:
        if node.rest:
            self._name(node.rest)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._name(node.name)
        # Decorators/defaults/annotations belong to the enclosing scope; bodies
        # are local. The separate whole-module walk covers global declarations.
        self.visit(node.args)
        for expression in [*node.decorator_list, node.returns]:
            if expression is not None:
                self.visit(expression)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._name(node.name)
        for expression in [*node.decorator_list, *node.bases, *node.keywords]:
            self.visit(expression)
        # Class-body names belong to the class namespace, not the module.

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self.visit(node.args)  # Defaults are outer-scope; the body is local.

    def visit_comprehension(self, node: ast.comprehension) -> None:
        # Iteration targets are comprehension-local, but walrus expressions in
        # iterables/filters/results can bind in the enclosing module scope.
        self.visit(node.iter)
        for condition in node.ifs:
            self.visit(condition)


def _validate_package_conftests(root: Path, plan: Sequence[Mapping[str, Any]]) -> None:
    """Preflight all conftests in changed packages from the bound tree, not cwd.

    Traverse module-level control flow too (if/try/etc.); inspect runner-control
    global declarations in every scope. This is a cooperative policy, not containment.
    """
    packages = sorted({spec["package"] for spec in plan
                       if spec.get("execution") == "candidate-tests" and spec["changed"]})
    for package in packages:
        for path in sorted((root / package).rglob("conftest.py")):
            relative = path.relative_to(root).as_posix()
            try:
                module = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
            except (OSError, UnicodeError, SyntaxError) as exc:
                raise WorkflowError(f"cannot inspect candidate conftest {relative}: {exc}") from exc
            bindings = _ConftestRunnerBindings()
            bindings.visit(module)
            findings = []
            if bindings.names:
                findings.append(", ".join(sorted(bindings.names)))
            for label, names in [
                ("module-level wildcard imports", bindings.wildcard_imports),
                ("global runner-control declarations", bindings.global_names),
                ("module-level dynamic calls", bindings.dynamic_calls),
                ("module-level dynamic references", bindings.dynamic_references),
                ("module-level attribute hooks", bindings.attribute_hooks),
            ]:
                if names:
                    findings.append(f"{label} refused by policy: " + ", ".join(sorted(names)))
            if findings:
                raise WorkflowError(
                    f"candidate conftest runner control is not allowed: {relative}: "
                    + "; ".join(findings)
                    + "; fixtures and ordinary helpers are allowed, but runner-control "
                    "bindings, declarations and dynamic routes are not")


def run_checks(candidate: dict, worktree: Path) -> list[dict]:
    """Run the fixed allowlisted validation adapters against the candidate.

    Only this function's own argument lists run: review fields, report text and
    package-local CLIs are never executed. Every row carries the real exit code
    and captured output, or `not-applicable` with the honest reason and
    `required: false` when the repository never configured that adapter. Checks
    execute from a read-only clean materialization of the bound Git tree, never
    from mutable working bytes. Copy mutations and candidate index/visibility
    changes invalidate the run. The exact tree, fixed plan and rows are persisted
    as checks-run.json with a canonical digest; returning rows does not let a
    caller rebind those results to a different tree.
    """
    store = _candidate_store(candidate)
    state = load_candidate(store, candidate["id"])
    candidate_worktree = Path(worktree)
    if candidate_worktree.resolve() != Path(state["worktree"]).resolve():
        raise WorkflowError("checks must run in the authoritative candidate worktree")
    if not candidate_worktree.is_dir():
        raise WorkflowError(f"candidate worktree does not exist: {candidate_worktree}")
    tree, _ = _require_clean_merge_index(state, candidate_worktree)
    before = _worktree_fingerprint(candidate_worktree)
    plan = _bound_check_plan(state, candidate_worktree)
    # Invalidate any older run before executing: a failed/interrupted rerun must
    # not leave a previous green run available to the recording gate.
    run_path = _candidate_path(store, state["id"], "checks-run.json")
    if run_path.exists():
        run_path.unlink()
    with tempfile.TemporaryDirectory(prefix="skill-sync-pytest-") as config_directory, \
            _clean_check_tree(candidate_worktree, tree) as clean_tree:
        execution_plan = _check_plan(state, candidate_worktree, materialization=clean_tree,
                                     pytest_config=Path(config_directory) / "pytest.ini")
        # Refuse runner-control declarations before running ANY check process,
        # even in unchanged conftests or packages that have no test runner.
        _validate_package_conftests(clean_tree, execution_plan)
        rows = [
            _result_row(
                CHECK_INDEX_WHITESPACE,
                True,
                _run_check_process(["git", "diff", "--cached", "--check"], candidate_worktree),
            )
        ]
        coverage = _coverage_paths(state, candidate_worktree)
        checked = _validate_staged_blobs(
            candidate_worktree, _index_map(candidate_worktree), coverage
        )
        rows.append(
            {
                "name": CHECK_STAGED_SYNTAX,
                "required": True,
                "status": "passed",
                "exit_code": 0,
                "stdout": f"{checked} staged file(s) validated in memory",
                "stderr": "",
            }
        )
        # This file is outside the candidate tree: neither root nor package
        # pytest.ini/setup.cfg/tox.ini/pyproject.toml participates in discovery.
        config_root = Path(config_directory)
        pytest_config = config_root / "pytest.ini"
        pytest_config.write_text(CHECK_PYTEST_CONFIG, encoding="utf-8")
        pytest_config.chmod(0o444)
        config_before = _check_tree_fingerprint(config_root)
        for spec in execution_plan:
            if not spec["applicable"]:
                rows.append(
                    {
                        "name": spec["name"],
                        "required": False,
                        "status": "not-applicable",
                        "exit_code": None,
                        "stdout": "",
                        "stderr": spec["note"],
                    }
                )
                continue
            if spec.get("unavailable"):
                # Never fall back to a candidate-supplied implementation.
                rows.append({"name": spec["name"], "required": True, "status": "failed",
                             "exit_code": 127, "stdout": "", "stderr": spec["unavailable"]})
                continue
            rows.append(
                _result_row(
                    spec["name"], True, _run_check_process(spec["argv"], Path(spec["cwd"]))
                )
            )
        if _check_tree_fingerprint(config_root) != config_before:
            raise WorkflowError("validation commands changed the plan-owned pytest configuration")
    if _worktree_fingerprint(candidate_worktree) != before:
        raise WorkflowError(
            "validation commands changed the candidate worktree; the check results are invalid"
        )
    _require_clean_merge_index(state, candidate_worktree)
    binding = {"schema": 1, "candidate_id": state["id"], "tree": tree,
               "plan": plan, "checks": rows}
    binding["digest"] = hashlib.sha256(canonical_bytes(binding)).hexdigest()
    atomic_json(run_path, binding)
    return rows


def _bound_check_plan(state: Mapping[str, Any], worktree: Path) -> list[dict]:
    """Bind command arguments, selection and builtin adapter identity, not names alone."""
    return [
        {"name": CHECK_INDEX_WHITESPACE, "required": True,
         "argv": ["git", "diff", "--cached", "--check"]},
        {"name": CHECK_STAGED_SYNTAX, "required": True, "adapter": "staged-syntax-v1"},
        *_check_plan(state, worktree),
    ]


def _require_bound_checks(
    store: Path, state: Mapping[str, Any], worktree: Path, rows: list[dict],
    tree: str, *, recorded: bool = False,
) -> dict:
    """Only run_checks can author evidence; callers may not relabel an old run."""
    filename = CHECKS_FILE if recorded else "checks-run.json"
    path = _candidate_path(store, state["id"], filename)
    if not path.is_file():
        raise WorkflowError("check evidence binding is missing; re-run checks for this tree")
    binding = _exact_keys(
        read_json(path), frozenset({"schema", "candidate_id", "tree", "plan", "checks", "digest"}),
        "check evidence binding")
    payload = {key: value for key, value in binding.items() if key != "digest"}
    digest = hashlib.sha256(canonical_bytes(payload)).hexdigest()
    if binding.get("digest") != digest or (recorded and state.get("checks_digest") != digest):
        raise WorkflowError("check evidence digest does not match the recorded binding")
    if binding.get("schema") != 1 or binding.get("candidate_id") != state["id"]:
        raise WorkflowError("check evidence is not bound to this candidate")
    if binding.get("tree") != tree:
        raise WorkflowError("check evidence tree does not match the candidate tree; re-run checks")
    if binding.get("plan") != _bound_check_plan(state, worktree):
        raise WorkflowError("check evidence plan changed; re-run checks for this tree")
    if binding.get("checks") != rows:
        raise WorkflowError("check rows do not match authoritative check evidence")
    return dict(binding)


def _validate_check_rows(checks: Any) -> list[dict]:
    rows = _list(checks, "checks")
    if not rows:
        raise WorkflowError("checks must record at least one result")
    normalized: list[dict] = []
    names: set[str] = set()
    for position, raw in enumerate(rows):
        row = _exact_keys(raw, CHECK_ROW_KEYS, f"checks[{position}]")
        name = _text(row["name"], f"checks[{position}].name")
        if name in names:
            raise WorkflowError(f"duplicate check name: {name}")
        names.add(name)
        required = _boolean(row["required"], f"{name} required")
        status = _text_in(row["status"], f"{name} status", CHECK_STATUSES)
        exit_code = row["exit_code"]
        if exit_code is not None and (
            isinstance(exit_code, bool) or not isinstance(exit_code, int)
        ):
            raise WorkflowError(f"{name} exit_code must be an integer or null")
        if status == "passed" and exit_code != 0:
            raise WorkflowError(f"{name} claims passed without exit code 0")
        if status == "failed" and exit_code in (0, None):
            raise WorkflowError(f"{name} claims failed without a non-zero exit code")
        if status == "not-applicable" and exit_code is not None:
            raise WorkflowError(f"{name} is not-applicable but records an exit code")
        for field in ("stdout", "stderr"):
            if not isinstance(row[field], str):
                raise WorkflowError(f"{name} {field} must be text")
        normalized.append(
            {
                "name": name,
                "required": required,
                "status": status,
                "exit_code": exit_code,
                "stdout": row["stdout"],
                "stderr": row["stderr"],
            }
        )
    return normalized


def _require_matching_check_rows(
    rows: Sequence[Mapping[str, Any]], state: Mapping[str, Any], worktree: Path
) -> None:
    """A caller cannot drop, rename or downgrade the candidate's own checks."""
    fixed = {CHECK_INDEX_WHITESPACE: True, CHECK_STAGED_SYNTAX: True}
    expected = {
        spec["name"]: spec["required"] for spec in _check_plan(state, worktree)
    }
    expected.update(fixed)
    observed = {row["name"]: row["required"] for row in rows}
    if set(observed) != set(expected):
        missing = sorted(set(expected) - set(observed))
        unexpected = sorted(set(observed) - set(expected))
        detail: list[str] = []
        if missing:
            detail.append("missing " + ", ".join(missing))
        if unexpected:
            detail.append("not a fixed check " + ", ".join(unexpected))
        raise WorkflowError("check results do not match the candidate: " + "; ".join(detail))
    for name, required in expected.items():
        if observed[name] != required:
            raise WorkflowError(f"check {name} has the wrong required flag")


def _report_relative_path(config: Mapping[str, Any], cid: str) -> str:
    """The configured report.path is the directory itself; the note sits directly in it."""
    _absolute_text(config["report"]["path"], "report.path")
    return f"skill-sync-{cid}-review.md"


def _atomic_text(path: Path, text: str) -> None:
    target = Path(path)
    parent = target.parent
    if not parent.is_dir():
        raise WorkflowError(f"state directory does not exist: {parent}")
    data = text.encode("utf-8")
    try:
        handle, name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=str(parent)
        )
    except OSError as exc:
        raise WorkflowError(f"cannot create a temporary payload next to {target}: {exc}") from exc
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, target)
    except OSError as exc:
        try:
            os.unlink(name)
        except OSError:
            pass
        raise WorkflowError(f"cannot write payload {target}: {exc}") from exc


def record_review(
    store: Path, cid: str, review: dict, checks: list[dict], validation: dict
) -> dict:
    """Persist a validated review, its checks and the reviewed tree atomically.

    The authoritative journal and config are reloaded; the caller's paths and
    booleans are never trusted. A failed or downgraded required check blocks the
    transition, and a tree that no longer matches the index invalidates the
    review instead of being recorded.
    """
    store_path = _store_path(store)
    config = _read_config(store_path)
    if not isinstance(cid, str) or not _CID_RE.match(cid):
        raise WorkflowError(f"invalid candidate id: {cid!r}")
    state = load_candidate(store_path, cid)
    if state["status"] not in ("prepared", "reviewed"):
        raise WorkflowError(
            f"candidate {cid} is {state['status']}; a review is recorded for a prepared candidate"
        )
    worktree = state["worktree"]
    if not worktree or not Path(worktree).is_dir():
        raise WorkflowError(f"candidate {cid} has no candidate worktree to review")
    candidate_worktree = Path(worktree)
    normalized = _normalize_review(review)
    validate_review(
        state, normalized, Path(config["maintainer_repo"]), candidate_worktree
    )
    rows = _validate_check_rows(checks)
    _require_matching_check_rows(rows, state, candidate_worktree)
    failed = [
        row["name"]
        for row in rows
        if row["required"] and row["status"] != "passed"
    ]
    if failed:
        raise WorkflowError(
            "required checks failed and cannot be recorded as reviewed: " + ", ".join(failed)
        )
    recomputed = validate_tree(state, candidate_worktree, normalized)
    supplied = _exact_keys(validation, frozenset({"tree", "paths"}), "validation")
    supplied_tree = supplied["tree"]
    if not isinstance(supplied_tree, str) or supplied_tree != recomputed["tree"]:
        raise WorkflowError(
            "validation tree does not match the current candidate index; re-run the final gate"
        )
    supplied_paths = supplied["paths"]
    if not isinstance(supplied_paths, list) or supplied_paths != recomputed["paths"]:
        raise WorkflowError(
            "validation paths do not match the current candidate coverage; re-run the final gate"
        )
    binding = _require_bound_checks(
        store_path, state, candidate_worktree, rows, recomputed["tree"])
    directory = _candidate_path(store_path, cid)
    atomic_json(directory / "review.json", normalized)
    atomic_json(directory / CHECKS_FILE, binding)
    updated = _persisted_state(state)
    updated.update(
        status="reviewed",
        review_digest=_review_digest(normalized),
        reviewed_tree=recomputed["tree"],
        checks_digest=binding["digest"],
        report_relative_path=_report_relative_path(config, cid),
        report_sha256="",
        last_error="",
    )
    _validate_state(store_path, updated, cid, config)
    _write_candidate_state(store_path, cid, updated)
    return _public_state(updated, store_path)


# ---------------------------------------------------------------------------
# Report rendering and exact read-back
# ---------------------------------------------------------------------------


def _report_template_path() -> Path:
    module_dir = Path(__file__).resolve().parent
    # Installed pair: the installer copies the template beside the scripts.
    beside = module_dir / "skill-sync-report.md.example"
    if beside.is_file():
        return beside
    return module_dir.parents[0] / "assets" / "skill-sync-report.md.example"


def _report_template() -> str:
    path = _report_template_path()
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise WorkflowError(f"report template is missing: {path}") from exc


def _one_line(value: str) -> str:
    return " ".join(value.split())


def _project_tag(config: Mapping[str, Any]) -> str:
    """Project tag for a report note, derived from the configured report path.

    Reports live in a plain configured directory (no vault hub note). When that
    path sits under `.../projects/<name>/...` the note carries `project/<name>`;
    otherwise a neutral `skill-sync` tag is used.
    """
    parts = str(config["report"]["path"]).split("/")
    if "projects" in parts:
        index = parts.index("projects")
        if index + 1 < len(parts) and parts[index + 1]:
            return f"project/{parts[index + 1]}"
    return "skill-sync"


def _render_decisions(normalized: Mapping[str, Any]) -> str:
    if not normalized["files"]:
        return "No path changed; the review acknowledges an empty-net candidate."
    blocks: list[str] = []
    for entry in normalized["files"]:
        lines = [
            f"### `{entry['path']}`",
            "",
            f"- Change: {entry['change_type']}",
            f"- Decision: {entry['decision']}",
            f"- Reason: {_one_line(entry['reason'])}",
        ]
        if entry["source_anchors"]:
            lines.append("- Source anchors:")
            for anchor in entry["source_anchors"]:
                lines.append(
                    f"  - `{anchor['ref']}` `{anchor['path']}`: "
                    f"\"{_one_line(anchor['quote'])}\""
                )
        else:
            lines.append("- Source anchors: none")
        if entry["replacements"]:
            lines.append("- Replacements:")
            for replacement in entry["replacements"]:
                lines.append(
                    f"  - from `{replacement['old_ref']}` `{replacement['old_path']}`: "
                    f"\"{_one_line(replacement['old_quote'])}\""
                )
                lines.append(
                    f"    to `{replacement['new_path']}`: "
                    f"\"{_one_line(replacement['new_quote'])}\""
                )
                lines.append(f"    reason: {_one_line(replacement['reason'])}")
        else:
            lines.append("- Replacements: none")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _render_checks(rows: Sequence[Mapping[str, Any]]) -> str:
    lines: list[str] = []
    for row in rows:
        flag = "required" if row["required"] else "optional"
        if row["status"] == "passed":
            detail = f"passed (exit {row['exit_code']})"
        elif row["status"] == "failed":
            detail = f"failed (exit {row['exit_code']})"
        else:
            detail = "not applicable"
        note = ""
        if row["status"] == "not-applicable" and row["stderr"]:
            note = " — " + _one_line(row["stderr"])
        elif row["status"] == "failed":
            note = " — see the candidate checks.json"
        lines.append(f"- `{row['name']}`: {detail} [{flag}]{note}")
    return "\n".join(lines)


def _render_report(
    state: Mapping[str, Any],
    normalized: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    tree: str,
    digest: str,
) -> str:
    config = _read_config(_candidate_store(state))
    _require_candidate_report_scope(state, config)
    template = _report_template()
    project_tag = _project_tag(config)
    values = {
        "CID": state["id"],
        "CID_SHORT": state["id"][:12],
        "CREATED_AT": state["created_at"],
        "SOURCE_REF": state["source_ref"],
        "SOURCE_MACHINE": state["source_machine"],
        "SOURCE_PROFILE": state["source_profile"],
        "POLICY": state["policy"],
        "MAIN_SHA": state["main_sha"],
        "SOURCE_SHA": state["source_sha"],
        "TREE": tree,
        "REVIEW_DIGEST": digest,
        "REPORT_PATH": state["report_relative_path"],
        "PROJECT_TAG": project_tag,
        "SUMMARY": _one_line(normalized["summary"]),
        "DECISIONS": _render_decisions(normalized),
        "CHECKS": _render_checks(rows),
    }
    text = template
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    if "{{" in text:
        raise WorkflowError("report template has unresolved placeholders")
    if not text.endswith("\n"):
        text += "\n"
    return text


def render_review(
    candidate: dict, review: dict, checks: list[dict], tree: str
) -> str:
    """Render the deterministic review payload and save it under the store.

    The timestamp is the captured candidate's `created_at`, never the wall
    clock, so the same inputs always produce the same bytes. Only the candidate
    store is written; the live note is written by the agent through TurboVault
    and then checked by `verify_report`.
    """
    store = _candidate_store(candidate)
    state = load_candidate(store, candidate["id"])
    normalized = _normalize_review(review)
    _bind_review_identity(state, normalized)
    rows = _validate_check_rows(checks)
    if not _is_full_sha(tree):
        raise WorkflowError("the reviewed tree must be a full Git tree SHA")
    if state["review_digest"] != _review_digest(normalized):
        raise WorkflowError("review is not the recorded review for this candidate")
    if state["reviewed_tree"] != tree:
        raise WorkflowError("tree is not the reviewed tree for this candidate")
    if state["report_relative_path"] != _report_relative_path(
        _read_config(store), state["id"]
    ):
        raise WorkflowError("candidate report path does not match the report directory")
    text = _render_report(state, normalized, rows, tree, state["review_digest"])
    _atomic_text(_candidate_path(store, state["id"], REVIEW_FILE), text)
    return text


def verify_report(candidate: dict, expected_text: str, report_root: Path) -> dict:
    """Verify the exact report bytes at the configured permitted destination.

    The journal, config and stored payload are reloaded: a caller's paths or
    status are never trusted. Missing, altered, symlinked or escaping notes are
    refused, and a successful read records `report-verified` plus the exact
    SHA-256 of the approved bytes.
    """
    store = _candidate_store(candidate)
    state = load_candidate(store, candidate["id"])
    config = _read_config(store)
    if state["status"] not in _REVIEWED_STATUSES:
        raise WorkflowError(
            f"candidate {state['id']} is {state['status']}; record a review before verifying its report"
        )
    if not isinstance(expected_text, str) or not expected_text:
        raise WorkflowError("the expected report payload must be non-empty text")
    root = Path(report_root)
    if not root.is_absolute():
        raise WorkflowError("report_root must be an absolute path")
    configured = Path(config["report"]["path"])
    if root.resolve() != configured.resolve():
        raise WorkflowError("report_root is not the configured report.path")
    expected_relative = _report_relative_path(config, state["id"])
    if state["report_relative_path"] != expected_relative:
        raise WorkflowError("candidate report path does not match the configured report directory")
    target = safe_relative(root, expected_relative)
    if target.is_symlink():
        raise WorkflowError(f"report path is a symlink, refusing it: {expected_relative}")
    if not target.is_file():
        raise WorkflowError(f"report is missing at {expected_relative}")
    data = target.read_bytes()
    payload = expected_text.encode("utf-8")
    if data != payload:
        raise WorkflowError(
            f"report at {expected_relative} does not match the rendered payload "
            f"(sha256 {hashlib.sha256(data).hexdigest()})"
        )
    stored = _candidate_path(store, state["id"], REVIEW_FILE)
    if not stored.is_file():
        raise WorkflowError("the rendered report payload is missing from the candidate store")
    if stored.read_bytes() != data:
        raise WorkflowError("the stored report payload differs from the note on disk")
    stored_review = read_json(_candidate_path(store, state["id"], "review.json"))
    if state["review_digest"] != _review_digest(stored_review):
        raise WorkflowError("recorded review digest does not match the stored review")
    digest = hashlib.sha256(data).hexdigest()
    if state["status"] != "reviewed" and state["report_sha256"] not in ("", digest):
        raise WorkflowError("the report bytes changed after this report was verified")
    updated = _persisted_state(state)
    updated["report_sha256"] = digest
    if state["status"] == "reviewed":
        updated["status"] = "report-verified"
    updated["last_error"] = ""
    _validate_state(store, updated, state["id"], config)
    _write_candidate_state(store, state["id"], updated)
    return _public_state(updated, store)


# ---------------------------------------------------------------------------
# Integration: exact merges, durable intent, observed remote evidence
#
# Promotion never re-merges and never rewrites history. The reviewed tree is
# committed once with `git commit-tree <tree> -p M -p T` (ordered parents, no
# hooks, an explicit author/committer identity supplied through the process
# environment so Git config is never modified), the intent is persisted
# atomically *before* a non-force push, and only a checked `git ls-remote` plus
# fetched ancestry may record `integrated`. A repeated call works from the saved
# P and reconciles; it never creates a second integration commit.
# ---------------------------------------------------------------------------

RESULT_FILE = "result.md"
# Result receipts are a separate note next to the immutable review note: a
# integration outcome is never backfilled into the approved report.
_RECEIPT_RECOVERY_HINT = "integrate-intent retained for reconcile"


def _result_relative_path(config: Mapping[str, Any], cid: str) -> str:
    _absolute_text(config["report"]["path"], "report.path")
    return f"skill-sync-{cid}-{RESULT_FILE}"


def _report_observation(
    config: Mapping[str, Any], state: Mapping[str, Any], store: Path,
) -> tuple[str, str]:
    """Read (never write) the approved review note at its configured destination.

    Returns `(observation, detail)` with observation in `present`, `missing` or
    `altered`. The configured vault root and the recorded digest are the only
    trusted inputs; the caller's report_root is irrelevant here.
    """
    relative = state["report_relative_path"]
    if not relative:
        return "missing", f"candidate {state['id']} has no recorded review report path"
    expected = state["report_sha256"]
    if not expected:
        return "missing", f"candidate {state['id']} has no recorded review report digest"
    if relative != _report_relative_path(config, state["id"]):
        return "altered", "review report path no longer matches the configured report directory"
    try:
        stored = _candidate_path(store, state["id"], REVIEW_FILE)
        if stored.is_symlink():
            return "altered", "stored review report payload is a symlink"
        payload = stored.read_bytes()
    except (OSError, WorkflowError) as exc:
        return "missing", f"stored review report payload is unreadable: {exc}"
    stored_digest = hashlib.sha256(payload).hexdigest()
    if stored_digest != expected:
        return "altered", (
            f"stored review report payload changed (sha256 {stored_digest}, expected {expected})"
        )
    root = Path(config["report"]["path"])
    try:
        target = safe_relative(root, relative)
    except WorkflowError as exc:
        return "altered", f"review report {relative} can no longer be resolved: {exc}"
    if target.is_symlink():
        return "altered", f"review report {relative} is now a symlink and cannot be trusted"
    if not target.is_file():
        return "missing", f"review report {relative} is missing at {root}"
    try:
        data = target.read_bytes()
    except OSError as exc:
        return "missing", f"review report {relative} is unreadable: {exc}"
    observed = hashlib.sha256(data).hexdigest()
    if observed != expected or data != payload:
        return "altered", (
            f"review report {relative} changed after review "
            f"(sha256 {observed}, expected {expected})"
        )
    return "present", ""


_RESULT_TRAILERS = (
    "Skill-Sync-Candidate",
    "Source-Ref",
    "Source-Tip",
    "Review-Digest",
    "Reviewed-Tree",
)


def _result_identity_env(config: Mapping[str, Any]) -> dict[str, str]:
    """Process-local author/committer identity; never writes Git config."""
    identity = config["maintainer_identity"]

    def clean(value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
        return cleaned or "maintainer"

    machine = clean(identity["machine"])
    profile = clean(identity["profile"])
    scope = clean(identity["scope"])
    name = f"skill-sync ({machine}/{profile}/{scope})"
    email = f"skill-sync@{machine}.invalid"
    return {
        "GIT_AUTHOR_NAME": name,
        "GIT_AUTHOR_EMAIL": email,
        "GIT_COMMITTER_NAME": name,
        "GIT_COMMITTER_EMAIL": email,
    }


def _result_message(state: Mapping[str, Any]) -> str:
    return (
        f"maintainer: integrate {state['source_ref']} {state['source_sha'][:12]} "
        f"as candidate {state['id'][:12]}\n"
        "\n"
        f"Skill-Sync-Candidate: {state['id']}\n"
        f"Source-Ref: {state['source_ref']}\n"
        f"Source-Tip: {state['source_sha']}\n"
        f"Review-Digest: {state['review_digest']}\n"
        f"Reviewed-Tree: {state['reviewed_tree']}\n"
    )


def _commit_facts(repo: Path, sha: str) -> dict[str, Any]:
    commit = _resolve_commit(repo, sha, "result commit")
    return {
        "sha": commit,
        "parents": _git_text(repo, "show", "-s", "--format=%P", commit).split(),
        "tree": _git_text(repo, "show", "-s", "--format=%T", commit),
        "message": _git_text(repo, "log", "-1", "--format=%B", commit),
    }


def _trailer(message: str, key: str) -> str:
    prefix = f"{key}: "
    for line in message.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return ""


def _verify_result_commit(repo: Path, state: Mapping[str, Any]) -> str:
    """Verify saved P is exactly the journal's candidate merge (never a new one)."""
    sha = state["result_sha"]
    if not sha:
        raise WorkflowError(f"candidate {state['id']} has no saved result commit")
    facts = _commit_facts(repo, sha)
    if facts["sha"] != sha:
        raise WorkflowError(f"saved result commit did not resolve exactly: {sha}")
    expected_parents = [state["main_sha"], state["source_sha"]]
    if facts["parents"] != expected_parents:
        raise WorkflowError(
            f"result commit {sha} parents {facts['parents']} are not the ordered "
            f"[captured main, source tip] {expected_parents}"
        )
    if facts["tree"] != state["reviewed_tree"]:
        raise WorkflowError(
            f"result commit {sha} tree {facts['tree']} is not the reviewed tree "
            f"{state['reviewed_tree']}"
        )
    expected_trailers = {
        "Skill-Sync-Candidate": state["id"],
        "Source-Ref": state["source_ref"],
        "Source-Tip": state["source_sha"],
        "Review-Digest": state["review_digest"],
        "Reviewed-Tree": state["reviewed_tree"],
    }
    for key in _RESULT_TRAILERS:
        observed = _trailer(facts["message"], key)
        if observed != expected_trailers[key]:
            raise WorkflowError(
                f"result commit {sha} trailer {key} is {observed!r}, "
                f"expected {expected_trailers[key]!r}"
            )
    if not facts["message"].startswith("maintainer:"):
        raise WorkflowError(f"result commit {sha} is not a maintainer merge")
    return sha


def _pin_result(repo: Path, cid: str, sha: str) -> None:
    ref = f"{PIN_ROOT}/{cid}/result"
    current = git(repo, "rev-parse", "--verify", "--quiet", ref)
    if current.returncode == 0:
        if current.stdout.strip() != sha:
            raise WorkflowError(
                f"saved result pin {ref} already names {current.stdout.strip()}, expected {sha}"
            )
        return
    git(repo, "update-ref", ref, sha, check=True)


def _create_result_commit(repo: Path, state: Mapping[str, Any], config: Mapping[str, Any]) -> str:
    """One `git commit-tree` from the reviewed tree with exactly ordered parents."""
    env = _result_identity_env(config)
    env["GIT_AUTHOR_DATE"] = state["created_at"]
    env["GIT_COMMITTER_DATE"] = state["created_at"]
    result = git(
        repo,
        "commit-tree",
        state["reviewed_tree"],
        "-p",
        state["main_sha"],
        "-p",
        state["source_sha"],
        input_text=_result_message(state),
        extra_env=env,
    )
    if result.returncode != 0:
        raise _git_error(result, "commit-tree")
    sha = result.stdout.strip()
    if not _is_full_sha(sha):
        raise WorkflowError("commit-tree did not return a full commit SHA")
    probe = dict(state)
    probe["result_sha"] = sha
    _verify_result_commit(repo, probe)
    _pin_result(repo, state["id"], sha)
    return sha


def _remote_main_sha(repo: Path, remote: str) -> str:
    """Exact remote reading of refs/heads/main; checked output, never inferred."""
    result = git(
        repo, "ls-remote", "--refs", remote, f"refs/heads/{MAIN_BRANCH}", timeout=FETCH_TIMEOUT
    )
    if result.returncode != 0:
        raise _git_error(result, "ls-remote")
    rows = [line.split() for line in result.stdout.splitlines() if line.strip()]
    if len(rows) != 1 or len(rows[0]) != 2:
        raise WorkflowError(
            f"git ls-remote did not report exactly one {MAIN_BRANCH} ref for {remote}"
        )
    sha, refname = rows[0]
    if refname != f"refs/heads/{MAIN_BRANCH}" or not _is_full_sha(sha):
        raise WorkflowError(f"git ls-remote returned an unusable main ref for {remote}")
    return sha


def _mark_failed(
    store: Path,
    cid: str,
    state: Mapping[str, Any],
    status: str,
    message: str,
    config: Mapping[str, Any],
) -> dict:
    """Persist a stale/blocked journal that retains its evidence; never a success."""
    updated = _persisted_state(state)
    updated.update(status=status, last_error=message)
    _validate_state(store, updated, cid, config)
    _write_candidate_state(store, cid, updated)
    return _public_state(updated, store)


def _remember_intent_error(
    store: Path,
    cid: str,
    state: Mapping[str, Any],
    message: str,
    config: Mapping[str, Any],
) -> dict:
    """Keep `integrate-intent` and its saved P; the outcome stays uncertain until reconcile.

    The persisted diagnostic always names the recovery step, so an operator or a
    later run can distinguish an uncertain outcome from a failed or absent push
    without inventing a success.
    """
    detail = message.strip()
    if _RECEIPT_RECOVERY_HINT not in detail:
        detail = f"{detail}; {_RECEIPT_RECOVERY_HINT}"
    updated = _persisted_state(state)
    updated["last_error"] = detail
    _validate_state(store, updated, cid, config)
    _write_candidate_state(store, cid, updated)
    return _public_state(updated, store)


def _mark_integrated(
    store: Path,
    cid: str,
    state: Mapping[str, Any],
    observed_main: str,
    config: Mapping[str, Any],
) -> dict:
    """Record observed integration evidence, then render the receipt payload.

    `integrated` is only ever written from an exact remote reading; a later main
    that already contains P is recorded as the observed main too. An existing
    `receipt-pending`/`complete` status is not downgraded by a repeat call, and
    the observation timestamp is fixed the first time so every later render of
    the result is byte-identical. A review note that no longer matches its
    recorded digest is recorded as an incident: integration is not undone and
    the immutable note is never rewritten to fit the result.
    """
    updated = _persisted_state(state)
    if updated["status"] == "integrate-intent":
        updated["status"] = "integrated"
    updated["integrated_main"] = observed_main
    if not updated.get("result_observed_at"):
        updated["result_observed_at"] = _utc_now()
    incident = updated.get("incident", "")
    observation, detail = _report_observation(config, updated, store)
    if observation != "present" and not incident:
        incident = (
            f"integration incident: {detail}; result {updated['result_sha']} remains "
            "integrated and the immutable review note is never rewritten"
        )
    if incident:
        updated["incident"] = incident
        updated["last_error"] = incident
        if updated["status"] == "complete":
            updated.update(status="receipt-pending", receipt_sha256="", receipt_verified_at="")
    else:
        updated["last_error"] = ""
    _validate_state(store, updated, cid, config)
    _write_candidate_state(store, cid, updated)
    public = _public_state(updated, store)
    render_result(public)
    return load_candidate(store, cid)


def _push_and_confirm(
    repo: Path,
    store: Path,
    cid: str,
    state: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict:
    """Push the already-persisted P without force and record only real evidence."""
    remote = config["remote"]
    result_sha = state["result_sha"]
    pushed = git(
        repo,
        "push",
        "--no-verify",
        remote,
        f"{result_sha}:refs/heads/{MAIN_BRANCH}",
        timeout=FETCH_TIMEOUT,
    )
    try:
        observed = _remote_main_sha(repo, remote)
    except WorkflowError as exc:
        message = f"saved result {result_sha} could not be confirmed on {remote}: {exc}"
        _remember_intent_error(store, cid, state, message, config)
        raise WorkflowError(f"candidate {cid} integrate-intent retained: {message}") from exc
    if observed == result_sha:
        return _mark_integrated(store, cid, state, observed, config)

    # A later main still counts when it contains P; fetch before the ancestry
    # check so a remote object that is not local yet is present.
    _fetch_inputs(repo, remote)
    fetched = _resolve_commit(
        repo, f"refs/remotes/{remote}/{MAIN_BRANCH}", f"{remote}/{MAIN_BRANCH}"
    )
    if is_ancestor(repo, result_sha, fetched):
        return _mark_integrated(store, cid, state, observed, config)

    if fetched == state["main_sha"]:
        detail = _result_tail(pushed) if pushed.returncode != 0 else "remote main did not advance"
        message = (
            f"saved result {result_sha} was not accepted and remote main is still the captured "
            f"main {state['main_sha']} ({detail}); integrate-intent retained for reconcile"
        )
        _remember_intent_error(store, cid, state, message, config)
        raise WorkflowError(f"candidate {cid} integrate-intent retained: {message}")

    message = (
        f"remote main {fetched} no longer contains the captured main {state['main_sha']} and "
        f"does not contain the saved result {result_sha}; recapture against the new main"
    )
    _mark_failed(store, cid, state, "stale", message, config)
    raise WorkflowError(f"candidate {cid} is stale: {message}")


def _require_remote_inputs(
    repo: Path,
    store: Path,
    cid: str,
    state: Mapping[str, Any],
    config: Mapping[str, Any],
) -> None:
    """Remote main must still be the captured M; the source may only have advanced."""
    remote = config["remote"]
    _fetch_inputs(repo, remote)
    remote_main = _resolve_commit(
        repo, f"refs/remotes/{remote}/{MAIN_BRANCH}", f"{remote}/{MAIN_BRANCH}"
    )
    if remote_main != state["main_sha"]:
        message = (
            f"captured main {state['main_sha']} is no longer the remote main {remote_main}; "
            "the candidate is stale and a new capture and review are required"
        )
        _mark_failed(store, cid, state, "stale", message, config)
        raise WorkflowError(f"candidate {cid} is stale: {message}")

    source_ref = state["source_ref"]
    tracking = _remote_tracking_ref(remote, source_ref)
    lookup = git(repo, "rev-parse", "--verify", "--quiet", f"{tracking}^{{commit}}")
    if lookup.returncode != 0:
        message = (
            f"registered source {source_ref} no longer exists on {remote}; "
            "the candidate is blocked and must be recaptured"
        )
        _mark_failed(store, cid, state, "blocked", message, config)
        raise WorkflowError(f"candidate {cid} is blocked: {message}")
    tip = lookup.stdout.strip()
    if not _is_full_sha(tip) or not is_ancestor(repo, state["source_sha"], tip):
        message = (
            f"source {source_ref} was rewritten: captured tip {state['source_sha']} is not an "
            f"ancestor of the remote tip {tip}; recapture instead of integrating replaced history"
        )
        _mark_failed(store, cid, state, "blocked", message, config)
        raise WorkflowError(f"candidate {cid} is blocked: {message}")


def _render_result_payload(state: Mapping[str, Any], result_sha: str, config: Mapping[str, Any]) -> str:
    integrated = state.get("integrated_main") or "not recorded"
    report = state["report_relative_path"] or "not rendered"
    observed_at = state.get("result_observed_at") or state["created_at"]
    project_tag = _project_tag(config)
    lines = [
        "---",
        "type: zettel",
        f'description: "Skill sync result for candidate {state["id"][:12]}"',
        "tags:",
        "  - skill-sync",
        f"  - {project_tag}",
        f"created: {observed_at}",
        f"updated: {observed_at}",
        "---",
        "",
        f"# Skill sync result — {state['id']}",
        "",
        f"- Candidate: `{state['id']}`",
        f"- Source: `{state['source_ref']}` from "
        f"`{state['source_machine']}/{state['source_profile']}`",
        f"- Policy: `{state['policy']}`",
        f"- Captured main: `{state['main_sha']}`",
        f"- Integrated source tip: `{state['source_sha']}`",
        f"- Integration commit: `{result_sha}`",
        f"- Parents (ordered): `{state['main_sha']}`, `{state['source_sha']}`",
        f"- Result tree: `{state['reviewed_tree']}`",
        f"- Review digest: `{state['review_digest']}`",
        f"- Review report: `{report}`",
        f"- Integrated main observed at `refs/heads/{MAIN_BRANCH}`: `{integrated}`",
        f"- Integration observed at: `{observed_at}`",
        "- Source consumption: `consumed` — the integrated tip is an ancestor of the "
        "integrated main",
        "- Integration outcome: `integrated` — a receipt never restates its own "
        "delivery state",
        "- Immutability: the review report stays the reviewed evidence; this receipt records "
        "only the integration outcome and never rewrites or re-approves that review",
    ]
    if state.get("incident"):
        lines.append(f"- Incident: {_one_line(state['incident'])}")
    lines.extend(
        [
            "",
            "The integration is a real merge commit: the ordered parents are the captured main and",
            "the reviewed source tip, and the tree is exactly the reviewed tree. No force, reset,",
            "rebase or amended source ref was used.",
            "",
        ]
    )
    return "\n".join(lines)


def render_result(candidate: dict) -> str:
    """Render the deterministic integration result and save it under the store.

    Only a candidate whose saved P was verified may be rendered: the payload
    names the exact commit, parents, tree and observed remote main from the
    authoritative journal, never from the caller's copy or the wall clock.
    """
    store = _candidate_store(candidate)
    state = load_candidate(store, candidate["id"])
    if state["status"] not in _RESULT_STATUSES:
        raise WorkflowError(
            f"candidate {state['id']} is {state['status']}; a result is rendered only "
            "after the integration commit was observed on main"
        )
    config = _read_config(store)
    result_sha = _verify_result_commit(Path(config["maintainer_repo"]), state)
    text = _render_result_payload(state, result_sha, config)
    _atomic_text(_candidate_path(store, state["id"], RESULT_FILE), text)
    return text


def verify_result(store: Path, cid: str, report_root: Path) -> dict:
    """Verify the exact result-receipt bytes and record delivery completion.

    `integrate`/`reconcile` only render a payload under the candidate store; the
    live receipt note is delivered separately (TurboVault by the agent) and is
    verified here by exact bytes at
    `<report.path>/<report.directory>/skill-sync-<cid>-result.md`.

    The maintainer lock is acquired exactly once for the journal transition, so a
    receipt attempt cannot lose an update against a concurrent reconcile. The
    journal, config and stored result are reloaded: the caller's status is never
    trusted. Every completed attempt records either `receipt-pending` or exact
    delivery evidence. A missing, altered, symlinked or
    escaping receipt is refused and the receipt stays pending; an exact match
    records `complete` plus the SHA-256 of the delivered bytes. A recorded
    integration incident blocks completion and the immutable review note is
    never written here.
    """
    store_path = _store_path(store)
    config = _read_config(store_path)
    if not isinstance(cid, str) or not _CID_RE.match(cid):
        raise WorkflowError(f"invalid candidate id: {cid!r}")
    root = Path(report_root)
    if not root.is_absolute():
        raise WorkflowError("report_root must be an absolute path")
    token = acquire_maintainer_lock(store_path)
    try:
        return _verify_result_locked(store_path, cid, root, config)
    finally:
        release_maintainer_lock(store_path, token)


def _verify_result_locked(
    store: Path, cid: str, root: Path, config: Mapping[str, Any]
) -> dict:
    """Receipt read-back under the already-acquired maintainer lock."""
    state = load_candidate(store, cid)
    if state["status"] not in _RESULT_STATUSES:
        raise WorkflowError(
            f"candidate {cid} is {state['status']}; only an observed integration has a "
            "result receipt to verify"
        )
    configured = Path(config["report"]["path"])
    if root.resolve() != configured.resolve():
        raise WorkflowError("report_root is not the configured report.path")
    result_sha = _verify_result_commit(Path(config["maintainer_repo"]), state)
    # Receipt completion must itself observe the immutable review, even when no
    # integrate/reconcile call has run since the note was altered (or since complete).
    observation, detail = _report_observation(config, state, store)
    if observation != "present" and not state.get("incident"):
        state["incident"] = (
            f"integration incident: {detail}; result {result_sha} remains integrated "
            "and the immutable review note is never rewritten"
        )
    expected_text = _render_result_payload(state, result_sha, config)
    payload = expected_text.encode("utf-8")
    relative = _result_relative_path(config, cid)

    problem = ""
    data = b""
    if state.get("incident"):
        problem = (
            f"candidate {cid} has a recorded integration incident: {state['incident']}; "
            "the receipt cannot complete until that discrepancy is resolved and the "
            "immutable review note is never rewritten"
        )
    else:
        try:
            target = safe_relative(root, relative)
        except WorkflowError as exc:
            problem = f"result receipt path for {cid} is unsafe: {exc}"
        else:
            if target.is_symlink():
                problem = f"result receipt {relative} is a symlink, refusing it"
            elif not target.is_file():
                problem = f"result receipt is missing at {relative}"
            else:
                try:
                    data = target.read_bytes()
                except OSError as exc:
                    problem = f"result receipt {relative} is unreadable: {exc}"
                if not problem and data != payload:
                    problem = (
                        f"result receipt at {relative} does not match the rendered payload "
                        f"(sha256 {hashlib.sha256(data).hexdigest()})"
                    )

    updated = _persisted_state(state)
    updated["receipt_attempts"] = int(updated.get("receipt_attempts") or 0) + 1
    if problem:
        # `integrated` -> `receipt-pending`: delivery is attempted but unverified.
        updated["status"] = "receipt-pending"
        updated["receipt_sha256"] = ""
        updated["receipt_verified_at"] = ""
        updated["last_error"] = problem
        _validate_state(store, updated, cid, config)
        _write_candidate_state(store, cid, updated)
        raise WorkflowError(problem)

    updated["status"] = "complete"
    updated["receipt_sha256"] = hashlib.sha256(payload).hexdigest()
    if not updated.get("receipt_verified_at"):
        updated["receipt_verified_at"] = _utc_now()
    updated["last_error"] = ""
    _validate_state(store, updated, cid, config)
    _write_candidate_state(store, cid, updated)
    return _public_state(updated, store)


def _reconcile_locked(
    repo: Path, store: Path, cid: str, config: Mapping[str, Any]
) -> dict:
    """Repair state around the saved P; never creates a second integration commit."""
    state = load_candidate(store, cid)
    if state["status"] not in _RECONCILABLE_STATUSES:
        raise WorkflowError(
            f"candidate {cid} is {state['status']}; there is no saved integration to reconcile"
        )
    result_sha = _verify_result_commit(repo, state)
    remote = config["remote"]
    observed = _remote_main_sha(repo, remote)
    _fetch_inputs(repo, remote)
    fetched = _resolve_commit(
        repo, f"refs/remotes/{remote}/{MAIN_BRANCH}", f"{remote}/{MAIN_BRANCH}"
    )
    if fetched != observed:
        raise WorkflowError(
            f"remote {remote} main moved while reconciling candidate {cid} "
            f"({observed} -> {fetched}); retry reconcile"
        )
    if is_ancestor(repo, result_sha, fetched):
        return _mark_integrated(store, cid, state, observed, config)
    if fetched == state["main_sha"]:
        try:
            if state["status"] != "integrate-intent":
                raise WorkflowError("previously observed integration is absent from remote main")
            state = _authorize_publication(
                repo, store, cid, Path(config["report"]["path"]), config, state)
            _verify_result_commit(repo, state)
        except WorkflowError as exc:
            message = f"integration retry incident: re-authorisation refused: {exc}"
            refused = _persisted_state(state)
            refused["incident"] = refused.get("incident") or message
            _mark_failed(store, cid, refused, "stale", message, config)
            raise WorkflowError(message) from exc
        return _push_and_confirm(repo, store, cid, state, config)
    message = (
        f"remote main {fetched} no longer contains the captured main {state['main_sha']} and "
        f"does not contain the saved result {result_sha}; recapture against the new main"
    )
    _mark_failed(store, cid, state, "stale", message, config)
    raise WorkflowError(f"candidate {cid} is stale: {message}")


def _authorize_publication(
    repo: Path, store: Path, cid: str, report_root: Path,
    config: Mapping[str, Any], state: dict,
) -> dict:
    """The same pre-push gate for first integration and retrying an absent P."""
    if state.get("incident"):
        raise WorkflowError(f"candidate {cid} has a recorded incident: {state['incident']}")
    # Source authorisation, review, checks, tree and report are re-read and
    # revalidated from the store: none of the earlier green results is trusted.
    # Transport keeps its configured registry; a refactor keeps its submission.
    if state["kind"] == "transport":
        _registry_entry(
            config,
            {
                "ref": state["source_ref"],
                "machine": state["source_machine"],
                "profile": state["source_profile"],
            },
        )
    else:
        _validate_state(store, state, cid, config)
    _require_candidate_report_scope(state, config)
    try:
        _require_unexposed_history(repo, state["main_sha"], state["source_sha"])
    except WorkflowError as exc:
        incident = _persisted_state(state)
        incident["incident"] = str(exc)
        _mark_failed(store, cid, incident, "blocked", str(exc), config)
        raise
    worktree = state["worktree"]
    if not worktree or not Path(worktree).is_dir():
        raise WorkflowError(f"candidate {cid} has no candidate worktree to revalidate")
    candidate_worktree = Path(worktree)
    stored_review = _normalize_review(read_json(_candidate_path(store, cid, "review.json")))
    _bind_review_identity(state, stored_review)
    digest = _review_digest(stored_review)
    if digest != state["review_digest"]:
        raise WorkflowError("stored review does not match the candidate review digest")
    stored_checks = _validate_check_rows(
        read_json(_candidate_path(store, cid, CHECKS_FILE))["checks"]
    )
    _require_matching_check_rows(stored_checks, state, candidate_worktree)
    failed = [
        row["name"] for row in stored_checks if row["required"] and row["status"] != "passed"
    ]
    if failed:
        raise WorkflowError(
            "required checks are not green for integration: " + ", ".join(failed)
        )
    validation = validate_tree(state, candidate_worktree, stored_review)
    if validation["tree"] != state["reviewed_tree"]:
        raise WorkflowError(
            f"candidate index tree {validation['tree']} is not the reviewed tree "
            f"{state['reviewed_tree']}; re-run the final gate and the report"
        )
    _require_bound_checks(
        store, state, candidate_worktree, stored_checks, state["reviewed_tree"], recorded=True)
    expected_text = _render_report(
        state, stored_review, stored_checks, state["reviewed_tree"], digest
    )
    state = verify_report(state, expected_text, report_root)

    _require_remote_inputs(repo, store, cid, state, config)
    return state


def _integrate_locked(
    repo: Path, store: Path, cid: str, report_root: Path, config: Mapping[str, Any]
) -> dict:
    """Promotion under the already-acquired maintainer lock (no recursive acquire)."""
    state = load_candidate(store, cid)
    status = state["status"]
    if status in _RECONCILABLE_STATUSES:
        return _reconcile_locked(repo, store, cid, config)
    if status in ("stale", "blocked"):
        raise WorkflowError(
            f"candidate {cid} is {status}: {state['last_error'] or 'no recorded detail'}; "
            "capture a new candidate instead of integrating this one"
        )
    if status != "report-verified":
        raise WorkflowError(
            f"candidate {cid} is {status}; integrate requires a report-verified candidate "
            "(review, checks and report read-back must all still match)"
        )
    state = _authorize_publication(repo, store, cid, report_root, config, state)
    result_sha = _create_result_commit(repo, state, config)
    updated = _persisted_state(state)
    updated.update(
        status="integrate-intent",
        result_sha=result_sha,
        result_parents=[state["main_sha"], state["source_sha"]],
        result_tree=state["reviewed_tree"],
        integrated_main="",
        last_error="",
    )
    _validate_state(store, updated, cid, config)
    # Durable intent before any remote write: a crash from here on reconciles.
    _write_candidate_state(store, cid, updated)
    return _push_and_confirm(repo, store, cid, _public_state(updated, store), config)


def integrate(repo: Path, store: Path, cid: str, report_root: Path) -> dict:
    """Promote a report-verified candidate as one exact merge commit on main.

    The maintainer lock is acquired exactly once for the whole public operation
    and released with its owner token in `finally`. Everything is revalidated
    from the store, remote main must still be the captured M, and the resulting
    P is persisted before a non-force push and confirmed from `git ls-remote`.
    """
    store_path = _store_path(store)
    config = _read_config(store_path)
    _assert_maintainer(repo, config)
    _assert_store_outside_repo(repo, store_path)
    if not isinstance(cid, str) or not _CID_RE.match(cid):
        raise WorkflowError(f"invalid candidate id: {cid!r}")
    root = Path(report_root)
    if not root.is_absolute():
        raise WorkflowError("report_root must be an absolute path")
    token = acquire_maintainer_lock(store_path)
    try:
        return _integrate_locked(Path(repo), store_path, cid, root, config)
    finally:
        release_maintainer_lock(store_path, token)


def reconcile(repo: Path, store: Path, cid: str) -> dict:
    """Reconcile an uncertain integration from the saved P; never re-integrates."""
    store_path = _store_path(store)
    config = _read_config(store_path)
    _assert_maintainer(repo, config)
    _assert_store_outside_repo(repo, store_path)
    if not isinstance(cid, str) or not _CID_RE.match(cid):
        raise WorkflowError(f"invalid candidate id: {cid!r}")
    token = acquire_maintainer_lock(store_path)
    try:
        return _reconcile_locked(Path(repo), store_path, cid, config)
    finally:
        release_maintainer_lock(store_path, token)


# ---------------------------------------------------------------------------
# No CLI surface: adapters own commands. The guard keeps import side-effect free.
# ---------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in ("--version", "-V"):
        print(f"skill_repo_workflow {CORE_VERSION} (workflow schema {WORKFLOW_SCHEMA})")
        return 0
    print(
        "skill_repo_workflow is a shared library; use the skill CLI adapters",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
