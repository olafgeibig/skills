#!/usr/bin/env python3
# skill-repo-maintain — v3 maintainer helper (runs on the maintainer host only).
#
# SCRIPT_VERSION: 3.0.0
# Companion of skill-repo-sync.py. Every candidate/review/report/integration
# operation is a thin CLI adapter over the shared v3 core
# (skill_repo_workflow.py); this file owns argument parsing and JSON output, not
# a second implementation of the policy.
#
# Modes (all action modes accept explicit --repo and --store):
#   --capture-source REF              fetch once, pin M/T and persist the candidate
#   --prepare CID                     isolated candidate worktree + native merge
#   --record-review CID --review-file PATH
#                                     validate the agent review, run the fixed
#                                     checks and persist reviewed tree/digest
#   --render-report CID               deterministic report payload -> store only
#   --verify-report CID               exact-byte read-back at the registered vault
#   --integrate CID                     one ordered-parent merge commit + push
#   --reconcile CID                   reconcile an uncertain integration from saved P
#   --render-result CID               result receipt payload -> store only
#   --verify-result CID               exact receipt read-back; records complete
#   --pending                         monitor protocol: sorted `pending <cid>` /
#                                     `blocked <cid>` lines; technical failure is
#                                     exactly `error: monitor-unhealthy` on stdout
#                                     plus a diagnostic on stderr (exit 0: a monitor
#                                     source must stay runnable; the bytes change)
#   --retry CID                       one explicit retry generation (blocked only)
#   --selfcheck                       observed versions/config/report/lock facts
#   --lock / --unlock                 owner-token maintainer lock (core-backed)
#   --note-pushed                     legacy metadata: records HEAD only after the
#                                     remote transport tip equals HEAD
#   --collect / --preflight / --merge-map / --apply-decisions
#                                     RETIRED (exit 12): v3 uses capture -> prepare ->
#                                     review -> report -> integrate instead
#   --refresh-strip / --reset-branch / --init-last-pushed
#                                     RETIRED (exit 12, `retired:` diagnostic)
#
# Exit codes: 0 ok/no-op · 10 required checks failed · 12 policy refusal/error
#             (incl. retired modes, repo/store disagreement, held lock) · 13 not
#             installed or maintainer config missing · 2 argparse usage.
# Action modes print machine-readable JSON on stdout and diagnostics on stderr;
# only --pending uses the stable line protocol.
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path

SCRIPT_VERSION = "3.0.0"
STATE_NAME = "skill-repo-sync.json"
WORKFLOW_STORE_NAME = "skill-repo-sync-v3"
REVIEW_FILE = "review.md"
RESULT_FILE = "result.md"
RETIRED_V2_MODES = ("--collect", "--preflight", "--merge-map", "--apply-decisions")

# Reuse the canonical instance-pointer patterns from the engine (single source of truth).
_here = Path(__file__).resolve().parent
_engine_candidates = [
    _here / "skill-repo-sync.py",  # beside this script inside the repo
]
# A copy of this helper running outside the repo points at the engine explicitly:
_env_engine = os.environ.get("SKILL_REPO_SYNC_ENGINE", "").strip()
if _env_engine:
    _engine_candidates.append(Path(_env_engine).expanduser())
_engine_path = next((p for p in _engine_candidates if p.is_file()), None)
assert _engine_path is not None, "engine module not found beside this script or in the repo"
_spec = spec_from_file_location("srs_engine", _engine_path)
assert _spec is not None and _spec.loader is not None, "engine module missing beside this script"
srs = module_from_spec(_spec)
_spec.loader.exec_module(srs)
INSTANCE_PATTERNS = srs.INSTANCE_PATTERNS
LINK_RE = srs.LINK_RE
REF_RE = srs.REF_RE

# The maintainer lock is owned by the shared v3 core, keyed to the configured
# maintainer clone's Git common dir. This adapter never reimplements it.
_core_candidates = [_here / "skill_repo_workflow.py"]
_env_core = os.environ.get("SKILL_REPO_WORKFLOW_CORE", "").strip()
if _env_core:
    _core_candidates.append(Path(_env_core).expanduser())
_core_path = next((p for p in _core_candidates if p.is_file()), None)
assert _core_path is not None, "workflow core not found beside this script or in the repo"
_core_spec = spec_from_file_location("skill_repo_workflow_core", _core_path)
assert _core_spec is not None and _core_spec.loader is not None, "workflow core loader missing"
core = module_from_spec(_core_spec)
_core_spec.loader.exec_module(core)

WORKFLOW_STORE_NAME = "skill-repo-sync-v3"
LOCK_TOKEN_NAME = "maintainer-lock.token"


def hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes")).expanduser()


def git(repo: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    env.setdefault("GIT_SSH_COMMAND", "ssh -oBatchMode=yes -oConnectTimeout=10")
    env.setdefault("GIT_ASKPASS", "/bin/true")
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                          check=check, timeout=180, env=env)


def main_sha(repo: Path) -> tuple[str, str | None]:
    fetch = git(repo, "fetch", "origin", "--quiet")
    if fetch.returncode != 0:
        return "", f"fetch failed: {(fetch.stderr or fetch.stdout).strip()[:300]}"
    local = git(repo, "rev-parse", "refs/remotes/origin/main").stdout.strip()
    remote = git(repo, "rev-parse", "refs/heads/main").stdout.strip()
    if local != remote:
        return local, (f"local main ({remote[:12]}) != origin/main ({local[:12]}); "
                       "reset or merge main first — never reset a consumed branch from a stale base")
    return local, None


def machine_shas(repo: Path) -> dict[str, str]:
    out = git(repo, "ls-remote", "origin", "refs/heads/machine/*").stdout.splitlines()
    shas = {}
    for line in out:
        sha, ref = line.split()
        shas[ref.split("refs/heads/machine/")[-1]] = sha
    return dict(sorted(shas.items()))


def refresh_strip(repo: Path, init_last_pushed: bool = False) -> tuple[int, list[str]]:
    """RETIRED: --refresh-strip no longer replays commits with a rebase.

    Kept as a named refusal (not deleted) so an old cron prompt or runbook step gets one
    explicit, testable error instead of silently falling through to another mode. Contributor
    refresh fast-forwards a clean transport when integrated main is an ancestor, does nothing
    when main is already its ancestor, and preserves divergent work for a deliberate merge.
    It never resets, rebases or autostashes contributor work.
    """
    return 12, ["retired: --refresh-strip is retired — refresh fast-forwards when integrated "
                "main is an ancestor and otherwise preserves divergent work for a deliberate "
                "merge; no reset, rebase or autostash of contributor work. Nothing was written "
                "(no ref, index or state change)."]


def note_pushed(repo: Path, dry_run: bool = False) -> tuple[int, list[str]]:
    """Legacy metadata only: record HEAD as `last_pushed_tip` after a push.

    It verifies that the remote transport tip equals HEAD (a stale or unrelated
    remote refuses), and it never decides that a reset is safe. `--dry-run`
    reports the verified fact without touching the state file.
    """
    head = git(repo, "rev-parse", "HEAD").stdout.strip()
    if not head:
        return 12, ["strip: cannot read HEAD"]
    branch = srs.branch_name(repo)
    if not branch or branch == "main" or srs.is_refactor_branch(branch):
        return 12, [f"strip: HEAD is on {branch or '<detached>'}; --note-pushed records a "
                    f"transport branch tip, never main or a refactor branch"]
    remote = git(repo, "ls-remote", "origin", f"refs/heads/{branch}")
    if remote.returncode != 0:
        return 12, [f"strip: cannot read origin/refs/heads/{branch}: "
                    f"{(remote.stderr or remote.stdout).strip()[:200]}"]
    fields = remote.stdout.split()
    remote_tip = fields[0] if fields else ""
    if remote_tip != head:
        return 12, [f"strip: remote {branch} is {remote_tip[:12] or '(missing)'}, HEAD is "
                    f"{head[:12]} — push the reviewed tip first; the remote is the authority"]
    if dry_run:
        return 0, [f"[dry-run] would record last-pushed-tip {head[:12]} for {branch} "
                   f"(remote tip verified; nothing written)"]
    state = srs.load_state()
    state["last_pushed_tip"] = head
    srs.save_state(state)
    return 0, [f"strip: last-pushed-tip -> {head[:12]}"]


def collect(repo: Path, outdir: Path, verbose: bool) -> tuple[int, list[str]]:
    notes: list[str] = []
    notes.append("update origin in this clone before trusting the diff output")
    main, err = main_sha(repo)
    if err:
        return 12, [f"machine collection: {err}"]
    shas = machine_shas(repo)
    if not shas:
        return 12, ["machine collection: no machine/* branches on the remote"]

    rows = []
    outdir.mkdir(parents=True, exist_ok=True)
    for host, sha in shas.items():
        name_only = git(repo, "diff", "--name-only", f"{main}...{sha}").stdout.strip()
        if not name_only:
            rows.append({"machine": host, "sha": sha[:12], "empty": True})
            continue
        shortstat = git(repo, "diff", "--shortstat", f"{main}...{sha}").stdout.strip()
        subjects = [l for l in git(repo, "log", "--format=%h %s", f"{main}..{sha}").stdout.splitlines()
                    if l.strip()]
        diff_target = outdir / f"machine-{host}.diff"
        diff = git(repo, "diff", f"{main}...{sha}")
        diff_target.write_text(diff.stdout, encoding="utf-8")
        # Overlaps between machine branches: files another pending branch also touches.
        overlaps = [r["machine"] for r in rows
                    for f in r.get("files", [])
                    if f in name_only.splitlines()]
        files = name_only.splitlines()
        rows.append({"machine": host, "sha": sha[:12], "empty": False,
                     "shortstat": shortstat, "files": files, "subjects": subjects,
                     "overlaps": overlaps, "diff_path": str(diff_target)})
        if verbose:
            notes.append(f"machine/{host}: {shortstat} → {diff_target.name}")

    report = {"at": datetime.now(tz=timezone.utc).isoformat(),
              "main_sha": main[:12], "out_dir": str(outdir), "branches": rows}
    (outdir / "collect.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0, notes


def added_pairs_from_diff(diff_text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    current = ""
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith("+") and not line.startswith("+++ b/"):
            out.append((current, line[1:]))
    return out


DIFF3_RE = re.compile(
    r"^<<<<<<< [^\n]*\n(.*?)^\|\|\|\|\|\|\| [^\n]*\n(.*?)^=======\n(.*?)^>>>>>>> [^\n]*\n",
    re.M | re.S)

MAX_PACKET_LINES = 80  # packets bigger than this are kept whole but flagged "oversized"


def _blob(repo: Path, rev: str, path: str) -> str:
    out = git(repo, "show", f"{rev}:{path}")
    return out.stdout if out.returncode == 0 else ""


def _blob_file(outdir: Path, safe: str, tag: str, text: str) -> Path:
    p = outdir / "blobs" / f"{safe}.{tag}"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _section_for(merged_text: str, needle: str) -> str:
    heading = ""
    for line in merged_text.splitlines():
        if line.startswith("#"):
            heading = line.strip()
        if needle and line == needle:
            break
    return heading


def _added_hunks(diff_text: str, f: str, merged_text: str) -> list[dict]:
    """Added-Hunk-Digest: je Hunk nur Datei + Heading-Anker + neue Zeilen — der
    Scope/Dedupe-Review liest Deltas, nie ganze Dateien."""
    hunks: list[dict] = []
    cur = None
    for line in diff_text.splitlines():
        if line.startswith("@@"):
            cur = {"file": f, "hunk": line[:60], "added": []}
            hunks.append(cur)
        elif cur is not None and line.startswith("+") and not line.startswith("+++"):
            cur["added"].append(line[1:])
    for h in hunks:
        h["heading"] = _section_for(merged_text, h["added"][0] if h["added"] else "")
    return hunks


def merge_map(repo: Path, host: str, outdir: Path) -> tuple[int, list[str]]:
    """Mechanische 3-Wege-Map fuer EINEN Transport-Branch (base=merge-base, ours=main,
    theirs=branch). Saubere Dateien sind ohne LLM fertig; nur Konfliktbloecke werden als
    Pakete mit je 10 Zeilen Kontext ausgeschnitten."""
    notes: list[str] = []
    main, err = main_sha(repo)
    if err:
        return 12, [f"merge-map: {err}"]
    sha = machine_shas(repo).get(host)
    if sha is None:
        return 12, [f"merge-map: machine/{host} not on the remote"]
    base = git(repo, "merge-base", main, sha).stdout.strip()
    files = git(repo, "diff", "--name-only", f"{main}...{sha}").stdout.splitlines()
    merged_dir = outdir / "merged"
    merged_dir.mkdir(parents=True, exist_ok=True)
    clean, unmergeable, packets, added_hunks = [], [], [], []
    for f in files:
        safe = f.replace("/", "__")
        ours, base_txt, theirs = _blob(repo, main, f), _blob(repo, base, f), _blob(repo, sha, f)
        po = _blob_file(outdir, safe, "our", ours)
        pb = _blob_file(outdir, safe, "base", base_txt)
        pt = _blob_file(outdir, safe, "their", theirs)
        proc = subprocess.run(
            ["git", "merge-file", "-L", "main", "-L", "base", "-L", f"machine/{host}",
             "--diff3", "-p", str(po), str(pb), str(pt)],
            capture_output=True, text=True)
        if proc.returncode < 0:
            unmergeable.append(f)
            continue
        (merged_dir / f"{safe}.merged").write_text(proc.stdout, encoding="utf-8")
        if proc.returncode == 0:
            clean.append(f)
            added_hunks.extend(_added_hunks(
                git(repo, "diff", f"{main}...{sha}", "--", f).stdout, f, proc.stdout))
            continue
        for idx, m in enumerate(DIFF3_RE.finditer(proc.stdout)):
            packet = {
                "file": f, "block": idx,
                "context_before": proc.stdout[:m.start()].splitlines()[-10:],
                "ours": m.group(1), "base": m.group(2), "theirs": m.group(3),
                "context_after": proc.stdout[m.end():].splitlines()[:10],
            }
            # R1: packets over MAX_PACKET_LINES are kept whole (never silently cut)
            # but flagged so the review knows the packet blew its line budget.
            size = (len(packet["context_before"]) + len(packet["context_after"])
                    + len(m.group(1).splitlines()) + len(m.group(2).splitlines())
                    + len(m.group(3).splitlines()))
            packet["oversized"] = size > MAX_PACKET_LINES
            packets.append(packet)
    report = {"at": datetime.now(tz=timezone.utc).isoformat(), "machine": host,
              "main_sha": main[:12], "branch_sha": sha[:12], "base": base[:12],
              "clean_files": clean, "unmergeable": unmergeable,
              "conflict_blocks": len(packets), "max_packet_lines": MAX_PACKET_LINES,
              "merged_dir": str(merged_dir)}
    (outdir / "merge-map.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (outdir / "conflict-packets.json").write_text(json.dumps(packets, indent=2), encoding="utf-8")
    (outdir / "added-hunks.json").write_text(json.dumps(added_hunks, indent=2), encoding="utf-8")
    notes.append(f"merge-map machine/{host}: {len(clean)} auto-merged, {len(packets)} conflict "
                 f"block(s) in {len({p['file'] for p in packets})} file(s), {len(unmergeable)} unmergeable")
    return 0, notes


def apply_decisions(repo: Path, decisions_path: Path, outdir: Path) -> tuple[int, list[str]]:
    """decisions.json = {"decisions": [{"file", "block", "action": ours|theirs|synthesize|drop, "text"?}]}
    Ersetzt jeden Konfliktblock in merged/<safe>.merged der Reihe nach und schreibt die
    geloeste Datei in den Worktree. All-or-nothing pro Datei (R2): eine Datei mit
    Konfliktbloecken braucht Entscheidungen fuer ALLE Bloecke; die Fehlermeldung nennt
    Datei + fehlende Block-Indizes, damit ein Re-Run nur die nachtraegt."""
    data = json.loads(decisions_path.read_text(encoding="utf-8"))
    by_file: dict[str, list[dict]] = {}
    for d in sorted(data.get("decisions", []), key=lambda d: d["block"]):
        by_file.setdefault(d["file"], []).append(d)
    # Every file with conflict blocks needs a decision per block — files the decisions
    # JSON omits entirely are missing just as much as half-covered ones.
    counts: dict[str, int] = {}
    packets_path = outdir / "conflict-packets.json"
    if packets_path.is_file():
        for p in json.loads(packets_path.read_text(encoding="utf-8")):
            counts[p["file"]] = max(counts.get(p["file"], 0), int(p["block"]) + 1)
    for f in by_file:
        counts.setdefault(f, 0)
    problems: list[str] = []
    for f in sorted(counts):
        want = counts[f]
        have = [int(d["block"]) for d in by_file.get(f, [])]
        missing = [i for i in range(want) if i not in have]
        if missing:
            problems.append(f"{f}: missing decisions for conflict block index(es) "
                            + ", ".join(map(str, missing)))
        extra = sorted({h for h in have if h < 0 or h >= want})
        if extra:
            problems.append(f"{f}: decisions for non-existent conflict block index(es) "
                            + ", ".join(map(str, extra)))
    if problems:
        return 12, ["apply-decisions: " + "; ".join(problems)
                    + " — all-or-nothing per file; a re-run only needs those blocks"]
    notes: list[str] = []
    for f, ds in sorted(by_file.items()):
        safe = f.replace("/", "__")
        merged = (outdir / "merged" / f"{safe}.merged").read_text(encoding="utf-8")
        blocks = list(DIFF3_RE.finditer(merged))
        if len(blocks) != len(ds):
            return 12, [f"apply-decisions: {f}: duplicate decisions for one conflict block "
                        f"({len(blocks)} block(s) but {len(ds)} decision(s))"]
        counter = {"i": -1}

        def repl(m):
            counter["i"] += 1
            d = ds[counter["i"]]
            action = str(d.get("action", ""))
            if action == "ours":
                return m.group(1)
            if action == "theirs":
                return m.group(3)
            if action == "drop":
                return ""
            return str(d.get("text", ""))

        resolved = DIFF3_RE.sub(repl, merged)
        assert not DIFF3_RE.search(resolved), f"{f}: conflict blocks remain"
        target = repo / f
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(resolved, encoding="utf-8")
        notes.append(f"{f}: {len(ds)} block(s) resolved -> worktree")
    return 0, notes


def preflight_scan(repo: Path, outdir: Path) -> tuple[int, list[str]]:
    """Scan every pending branch diff (as collected) for defects the agent must repair in its edit."""
    notes: list[str] = []
    main, err = main_sha(repo)
    if err:
        return 12, [f"machine preflight: {err}"]
    findings: list[dict] = []
    for host, sha in machine_shas(repo).items():
        diff = git(repo, "diff", f"{main}...{sha}")
        if diff.returncode != 0 or not diff.stdout.strip():
            continue
        for file, text in added_pairs_from_diff(diff.stdout):
            if not text.strip():
                continue
            for pattern, label in INSTANCE_PATTERNS:
                if re.search(pattern, text):
                    findings.append({"machine": host, "file": file, "kind": "instance-pointer",
                                     "detail": label, "line": text.strip()[:160]})
            for target in LINK_RE.findall(text) + REF_RE.findall(text):
                target = target.strip()
                if target.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                # Resolve against the referencing file's directory and every ancestor
                # up to the repo root: a support file under assets/ may legitimately point
                # at `references/<name>.md` relative to the package root.
                base = (repo / file).parent if file else repo
                probe, resolved = base, False
                while not resolved:
                    resolved = (probe / target).exists()
                    if probe == repo or probe.parent == probe:
                        break
                    probe = probe.parent
                if not resolved:
                    findings.append({"machine": host, "file": file, "kind": "dangling-reference",
                                     "detail": target, "line": text.strip()[:160]})
    seen: set = set()
    unique = [f for f in findings
              if not (f["machine"], f["file"], f["kind"], f["detail"], f["line"]) in seen
              and not seen.add((f["machine"], f["file"], f["kind"], f["detail"], f["line"]))]
    if unique:
        out = {"at": datetime.now(tz=timezone.utc).isoformat(), "findings": unique}
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "preflight-findings.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
        notes.append(f"preflight: {len(unique)} finding(s) — mechanism repair belongs to the agent's edit, "
                     "not to a forced push")
        for f in unique[:20]:
            notes.append(f"  ! [{f['machine']}] {f['kind']} in {f['file']}: {f['detail']} — {f['line'][:80]}")
        return 10, notes
    notes.append("preflight: no instance-pointer or dangling-reference findings in the pending diffs")
    return 0, notes


def retired_reset_branches(hosts: list[str]) -> tuple[int, list[str]]:
    """RETIRED: --reset-branch can no longer rewrite a transport branch.

    Consumption is an ancestry fact (`T ancestor main`), and the transport branch is never
    reset or force-pushed — a merge commit on main is the acknowledgment, so a newer source tip
    stays pending naturally and concurrent work survives integration. The refusal runs before
    any Git call: no local ref, remote ref, index or state is touched, even with --dry-run.
    """
    named = " ".join(hosts[:5]) + (" …" if len(hosts) > 5 else "")
    return 12, [f"retired: --reset-branch {named} is retired — a transport branch is never "
                f"reset or force-pushed; integrate the reviewed snapshot with a real merge "
                f"commit and let ancestry decide consumption. Nothing was written (no local "
                f"ref, remote ref, index or state change)."]


def _lock_token_path(store: Path) -> Path:
    return store / LOCK_TOKEN_NAME


def _maintainer_config_problem(store: Path) -> list[str] | None:
    """Honest exit-13 precondition: no maintainer config, no maintainer lock."""
    config_path = store / "maintainer.json"
    if not config_path.is_file():
        return [f"maintainer config missing: {config_path} — the maintainer lock is keyed to the "
                f"configured maintainer clone's Git common dir; there is no repo-path fallback "
                f"(nothing was written)"]
    try:
        core.load_maintainer_config(store)
    except core.WorkflowError as exc:
        return [f"maintainer config invalid: {exc} (nothing was written)"]
    return None


def _owner_description(record: dict) -> str:
    if record.get("malformed") is not None:
        return "unreadable lock content"
    return (f"owner token {record.get('token')}, pid {record.get('pid')}, "
            f"host {record.get('host')}, acquired {record.get('acquired_at')}")


def lock_maintainer(store: Path, force: bool = False,
                   dry_run: bool = False) -> tuple[int, list[str]]:
    """Thin adapter over core.acquire_maintainer_lock: one lock per maintainer clone."""
    problem = _maintainer_config_problem(store)
    if problem:
        return 13, problem
    try:
        lock_path = core.maintainer_lock_path(store)
        held = core.read_maintainer_lock(store)
    except core.WorkflowError as exc:
        return 12, [f"lock: {exc}"]
    if dry_run:
        state = f"held by {_owner_description(held)}" if held is not None else "free"
        return 0, [f"[dry-run] would acquire {lock_path} ({state}; nothing written)"]
    if force and held is not None:
        return 12, [f"lock: refused — {lock_path} is held by {_owner_description(held)}. "
                    f"--force-lock never breaks ownership; remove that exact file manually only "
                    f"after you have observed on that host that the owning executor is gone. "
                    f"Nothing was changed."]
    try:
        token = core.acquire_maintainer_lock(store)
    except core.WorkflowError as exc:
        return 12, [f"lock: {exc}"]
    token_path = _lock_token_path(store)
    try:
        tmp = token_path.with_name(f".{token_path.name}.{os.getpid()}.tmp")
        tmp.write_text(token + "\n", encoding="utf-8")
        os.replace(tmp, token_path)
    except OSError as exc:
        try:
            core.release_maintainer_lock(store, token)
        except core.WorkflowError as release_exc:
            return 12, [f"lock: acquired {lock_path} but could not record the owner token in "
                        f"{token_path}: {exc}; releasing it also failed: {release_exc}"]
        return 12, [f"lock: acquired {lock_path} but could not record the owner token in "
                    f"{token_path}: {exc}"]
    return 0, [f"lock: acquired {lock_path} (owner token {token})"]


def unlock_maintainer(store: Path, dry_run: bool = False) -> tuple[int, list[str]]:
    """Release through the recorded owner token; never guess or break another owner's lock."""
    problem = _maintainer_config_problem(store)
    if problem:
        return 13, problem
    token_path = _lock_token_path(store)
    try:
        lock_path = core.maintainer_lock_path(store)
        held = core.read_maintainer_lock(store)
    except core.WorkflowError as exc:
        return 12, [f"unlock: {exc}"]
    token = ""
    if token_path.is_file():
        try:
            token = token_path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            return 12, [f"unlock: cannot read the recorded owner token {token_path}: {exc}"]
    if dry_run:
        target = f"held by {_owner_description(held)}" if held is not None else "not held"
        recorded = "recorded" if token else "missing"
        return 0, [f"[dry-run] would release {lock_path} with the {recorded} owner token "
                   f"({target}; nothing written)"]
    if not token:
        return 12, [f"unlock: no owner token recorded in {token_path} — refusing to release "
                    f"{lock_path} without it (--force-lock cannot substitute); a manual break "
                    f"is allowed only after observed executor absence. Nothing was changed."]
    try:
        core.release_maintainer_lock(store, token)
    except core.WorkflowError as exc:
        return 12, [f"unlock: {exc}"]
    try:
        token_path.unlink(missing_ok=True)
    except OSError as exc:
        return 12, [f"unlock: released {lock_path} but could not remove {token_path}: {exc}"]
    return 0, [f"unlock: released {lock_path} (owner token {token})"]

# ---------------------------------------------------------------------------
# v3 CLI modes — adapters over core only
# ---------------------------------------------------------------------------


def _store_from_args(args: argparse.Namespace) -> Path:
    if args.store:
        store = Path(args.store).expanduser()
        if not store.is_absolute():
            store = Path.cwd() / store
        return store
    return hermes_home() / WORKFLOW_STORE_NAME


def _load_config_or_none(store: Path) -> dict | None:
    if not (store / "maintainer.json").is_file():
        return None
    try:
        return core.load_maintainer_config(store)
    except core.WorkflowError:
        return None


def _repo_from_config(config: dict, explicit: str | None) -> Path:
    configured = Path(config["maintainer_repo"]).expanduser()
    if explicit:
        root = git(Path(explicit).expanduser(), "rev-parse", "--show-toplevel")
        if root.returncode != 0:
            raise core.WorkflowError(f"not a Git repository: {explicit}")
        actual = Path(root.stdout.strip()).resolve()
        if actual != configured.resolve():
            raise core.WorkflowError(
                f"--repo {actual} does not match the store's maintainer_repo {configured} — "
                "refusing to mix a store with a different maintainer clone"
            )
        return actual
    if not configured.is_dir():
        raise core.WorkflowError(f"configured maintainer_repo is missing: {configured}")
    return configured


def _report_root(config: dict) -> Path:
    return Path(config["report"]["vault_root"])


def _candidate_file(store: Path, cid: str, name: str) -> Path:
    return store / "candidates" / cid / name


def _candidate_payload(state: dict, **extra) -> dict:
    fields = (
        "id",
        "status",
        "kind",
        "source_ref",
        "source_machine",
        "source_profile",
        "main_sha",
        "source_sha",
        "policy",
        "worktree",
        "input_paths",
        "conflict_paths",
        "review_digest",
        "reviewed_tree",
        "report_relative_path",
        "report_sha256",
        "result_sha",
        "integrated_main",
        "last_error",
        "attempts",
        "retry_generation",
    )
    payload = {field: state[field] for field in fields if field in state}
    payload.update(extra)
    return payload


def _review_artifacts(store: Path, cid: str) -> tuple[dict, list[dict]]:
    review_path = _candidate_file(store, cid, "review.json")
    checks_path = _candidate_file(store, cid, "checks.json")
    if not review_path.is_file():
        raise core.WorkflowError(f"candidate {cid} has no recorded review — record one first")
    if not checks_path.is_file():
        raise core.WorkflowError(f"candidate {cid} has no recorded checks — record the review first")
    review = core.read_json(review_path)
    checks = core.read_json(checks_path).get("checks")
    if not isinstance(checks, list) or not checks:
        raise core.WorkflowError(f"candidate {cid} checks.json carries no check rows")
    return review, checks


def _submit_refactor(repo: Path, store: Path, config: dict, ref: str, tip: str | None,
                     brief_file: str | None,
                     dry_run: bool) -> tuple[int, dict | None, list[str]]:
    """Explicit exact-tip refactor submission through the shared core."""
    if not tip or not brief_file:
        raise core.WorkflowError("--submit-refactor requires --tip <full-sha> and --brief <path>")
    brief_path = Path(brief_file).expanduser()
    if not brief_path.is_file():
        raise core.WorkflowError(f"refactor brief file is missing: {brief_path}")
    brief = core.validate_refactor_brief(core.read_json(brief_path))
    if not dry_run:
        record = core.submit_refactor(repo, store, ref, tip, brief)
        payload = {
            "mode": "submit-refactor",
            "candidate": record["id"],
            "ref": record["ref"],
            "tip": record["tip"],
            "main_sha": record["main_sha"],
            "maintainer_identity": record["maintainer_identity"],
            "brief_sha256": record["brief_sha256"],
            "submission": str(store / "refactor-submissions" / f"{record['id']}.json"),
        }
        return 0, payload, []

    # Dry run: cached refs only, no fetch, pin or record write.
    remote = config["remote"]
    branch = ref[len("refs/heads/"):] if ref.startswith("refs/heads/") else ref
    cached_main = git(repo, "rev-parse", "--verify", "--quiet",
                      f"refs/remotes/{remote}/main").stdout.strip()
    cached_tip = git(repo, "rev-parse", "--verify", "--quiet",
                     f"refs/remotes/{remote}/{branch}").stdout.strip()
    if not cached_main or not cached_tip:
        return 0, {"mode": "submit-refactor", "dry_run": True, "determined": False,
                   "reason": "cannot determine without fetch", "ref": ref, "tip": tip}, \
               ["cannot determine without fetch"]
    payload = {"mode": "submit-refactor", "dry_run": True, "determined": True,
               "cached": True, "ref": ref, "tip": tip, "cached_main": cached_main,
               "cached_ref_tip": cached_tip,
               "tip_is_remote_tip": cached_tip == tip,
               "main_is_ancestor": False}
    try:
        payload["main_is_ancestor"] = core.is_ancestor(repo, cached_main, tip)
    except core.WorkflowError:
        payload["main_is_ancestor"] = False
    if payload["tip_is_remote_tip"] and payload["main_is_ancestor"]:
        payload["candidate"] = core.candidate_id(
            config["repo_id"], ref, cached_main, tip, config["policy"], "refactor")
        payload["would_submit"] = True
    else:
        payload["would_submit"] = False
        payload["would_refuse"] = (
            "the cached ref tip or ancestry does not match the submission; "
            "a fetch may be required")
    return 0, payload, ["[dry-run] cached refs only — no fetch, no submission, no pin"]


def _capture_source(repo: Path, store: Path, config: dict, ref: str,
                    dry_run: bool) -> tuple[int, dict | None, list[str]]:
    if ref.startswith("refs/heads/refactor/"):
        # A submitted refactor is captured from its exact submission record, not
        # swept; an unsubmitted branch fails here and points at --submit-refactor.
        remote = config["remote"]
        branch = ref[len("refs/heads/"):]
        if dry_run:
            main = git(repo, "rev-parse", "--verify", "--quiet",
                       f"refs/remotes/{remote}/main").stdout.strip()
            tip = git(repo, "rev-parse", "--verify", "--quiet",
                      f"refs/remotes/{remote}/{branch}").stdout.strip()
            if not main or not tip:
                return 0, {"mode": "capture-source", "kind": "refactor", "dry_run": True,
                           "determined": False, "reason": "cannot determine without fetch",
                           "source_ref": ref}, ["cannot determine without fetch"]
            matches = [record for record in core.refactor_submissions(store)
                       if record["ref"] == ref and record["main_sha"] == main]
            if len(matches) != 1:
                return 0, {"mode": "capture-source", "kind": "refactor", "dry_run": True,
                           "determined": False, "source_ref": ref,
                           "reason": "no single exact-tip submission matches the cached main"}, \
                       ["[dry-run] cached refs only — no fetch, no pin, no journal write"]
            record = matches[0]
            return 0, {"mode": "capture-source", "kind": "refactor", "dry_run": True,
                       "determined": True, "cached": True, "candidate": record["id"],
                       "source_ref": ref, "main_sha": main, "source_sha": record["tip"]}, \
                   ["[dry-run] cached refs only — no fetch, no pin, no journal write"]
        candidate = core.capture(repo, store, {"ref": ref}, kind="refactor")
        return 0, _candidate_payload(candidate, mode="capture-source"), []
    entry = next((item for item in config["sources"] if item["ref"] == ref), None)
    if entry is None:
        raise core.WorkflowError(f"source is not registered for this maintainer: {ref}")
    if not entry["enabled"]:
        raise core.WorkflowError(f"source is disabled in the maintainer registry: {ref}")
    if dry_run:
        remote = config["remote"]
        branch = ref[len("refs/heads/"):] if ref.startswith("refs/heads/") else ref
        main = git(repo, "rev-parse", "--verify", "--quiet",
                   f"refs/remotes/{remote}/main")
        tip = git(repo, "rev-parse", "--verify", "--quiet",
                  f"refs/remotes/{remote}/{branch}")
        main_sha = main.stdout.strip()
        source_sha = tip.stdout.strip()
        if not main_sha or not source_sha:
            return 0, {"mode": "capture-source", "dry_run": True, "determined": False,
                       "reason": "cannot determine without fetch",
                       "source_ref": ref}, ["cannot determine without fetch"]
        cid = core.candidate_id(config["repo_id"], ref, main_sha, source_sha,
                                config["policy"], "transport")
        return 0, {"mode": "capture-source", "dry_run": True, "determined": True,
                   "cached": True, "candidate": cid, "source_ref": ref,
                   "main_sha": main_sha, "source_sha": source_sha}, \
               ["[dry-run] cached refs only — no fetch, no pin, no journal write"]
    candidate = core.capture(repo, store, {"ref": ref})
    return 0, _candidate_payload(candidate, mode="capture-source"), []


def _prepare(repo: Path, store: Path, cid: str,
             dry_run: bool) -> tuple[int, dict | None, list[str]]:
    state = core.load_candidate(store, cid)
    if dry_run:
        if state["status"] == "blocked":
            return 12, {"mode": "prepare", "dry_run": True, "candidate": cid,
                        "status": "blocked", "would_refuse": state["last_error"]}, \
                   [f"candidate {cid} is blocked: {state['last_error']}"]
        if state["status"] not in ("captured", "prepared"):
            return 12, {"mode": "prepare", "dry_run": True, "candidate": cid,
                        "status": state["status"],
                        "would_refuse": "candidate is beyond capture but not prepared"}, \
                   [f"candidate {cid} is {state['status']}; prepare applies to a captured candidate"]
        return 0, {"mode": "prepare", "dry_run": True, "candidate": cid,
                   "status": state["status"], "would_create": state["worktree"] or
                   str(store / "worktrees" / cid),
                   "would_merge": state["source_sha"]}, \
               ["[dry-run] would create the candidate worktree and run one native merge"]
    candidate = core.prepare(repo, store, state)
    return 0, _candidate_payload(candidate, mode="prepare"), []


def _record_review(repo: Path, store: Path, cid: str, review_file: str | None,
                   dry_run: bool) -> tuple[int, dict | None, list[str]]:
    if not review_file:
        raise core.WorkflowError("--record-review requires --review-file PATH")
    path = Path(review_file).expanduser()
    if not path.is_file():
        raise core.WorkflowError(f"review file is missing: {path}")
    review = core.read_json(path)
    state = core.load_candidate(store, cid)
    worktree = Path(state["worktree"]) if state["worktree"] else None
    if worktree is None or not worktree.is_dir():
        raise core.WorkflowError(f"candidate {cid} has no candidate worktree to review")
    if dry_run:
        core.validate_review(state, review, repo, worktree)
        return 0, {"mode": "record-review", "dry_run": True, "candidate": cid,
                   "would_run_checks": True,
                   "would_record_tree": state["reviewed_tree"] or "(computed at record time)"}, \
               ["[dry-run] review validation only — no checks, no journal write"]
    checks = core.run_checks(state, worktree)
    failed = [row["name"] for row in checks
              if row["required"] and row["status"] != "passed"]
    if failed:
        return 10, {"mode": "record-review", "candidate": cid,
                    "status": "checks-failed", "failed": failed, "checks": checks}, \
               ["required checks failed and cannot be recorded as reviewed: "
                + ", ".join(failed)]
    validation = core.validate_tree(state, worktree, review)
    recorded = core.record_review(store, cid, review, checks, validation)
    return 0, _candidate_payload(recorded, mode="record-review",
                                 checks=checks, tree=validation["tree"]), []


def _render_report(store: Path, cid: str,
                   dry_run: bool) -> tuple[int, dict | None, list[str]]:
    state = core.load_candidate(store, cid)
    if state["status"] not in ("reviewed", "report-verified") and not state["reviewed_tree"]:
        raise core.WorkflowError(
            f"candidate {cid} is {state['status']}; a report is rendered after the review is recorded"
        )
    review, checks = _review_artifacts(store, cid)
    payload_path = _candidate_file(store, cid, REVIEW_FILE)
    if dry_run:
        return 0, {"mode": "render-report", "dry_run": True, "candidate": cid,
                   "would_write": str(payload_path),
                   "report_relative_path": state["report_relative_path"]}, \
               ["[dry-run] would render the deterministic report payload under the store"]
    text = core.render_review(state, review, checks, state["reviewed_tree"])
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return 0, {"mode": "render-report", "candidate": cid,
               "report_relative_path": state["report_relative_path"],
               "payload_path": str(payload_path), "sha256": digest,
               "bytes": len(text.encode("utf-8"))}, []


def _verify_report(store: Path, config: dict, cid: str,
                   dry_run: bool) -> tuple[int, dict | None, list[str]]:
    state = core.load_candidate(store, cid)
    payload_path = _candidate_file(store, cid, REVIEW_FILE)
    if not payload_path.is_file():
        raise core.WorkflowError(f"candidate {cid} has no rendered report — run --render-report first")
    text = payload_path.read_text(encoding="utf-8")
    root = _report_root(config)
    if dry_run:
        target = root / state["report_relative_path"]
        matches = target.is_file() and target.read_bytes() == text.encode("utf-8")
        return (0 if matches else 12), {
            "mode": "verify-report", "dry_run": True, "candidate": cid,
            "report_relative_path": state["report_relative_path"],
            "note_present": target.is_file(), "would_match": matches}, \
            ([] if matches else [f"report at {target} does not match the stored payload"])
    verified = core.verify_report(state, text, root)
    return 0, _candidate_payload(verified, mode="verify-report"), []


def _integrate(repo: Path, store: Path, config: dict, cid: str,
             dry_run: bool) -> tuple[int, dict | None, list[str]]:
    state = core.load_candidate(store, cid)
    if dry_run:
        status = state["status"]
        if status == "report-verified":
            action = "integrate"
        elif status in ("integrate-intent", "integrated", "receipt-pending", "complete"):
            action = "reconcile"
        else:
            return 12, {"mode": "integrate", "dry_run": True, "candidate": cid,
                        "status": status,
                        "would_refuse": "candidate is not report-verified"}, \
                   [f"candidate {cid} is {status}; integrate requires report-verified"]
        cached = git(repo, "rev-parse", "--verify", "--quiet",
                     f"refs/remotes/{config['remote']}/main").stdout.strip()
        return 0, {"mode": "integrate", "dry_run": True, "candidate": cid,
                   "status": status, "would": action,
                   "cached_remote_main": cached or "(cached ref absent)",
                   "result_sha": state["result_sha"]}, \
               ["[dry-run] no lock, no fetch, no commit and no push"]
    result = core.integrate(repo, store, cid, _report_root(config))
    return 0, _candidate_payload(result, mode="integrate"), []


def _reconcile(repo: Path, store: Path, cid: str,
               dry_run: bool) -> tuple[int, dict | None, list[str]]:
    state = core.load_candidate(store, cid)
    if dry_run:
        if state["status"] not in ("integrate-intent", "integrated", "receipt-pending", "complete"):
            return 12, {"mode": "reconcile", "dry_run": True, "candidate": cid,
                        "status": state["status"],
                        "would_refuse": "no saved result to reconcile"}, \
                   [f"candidate {cid} is {state['status']}; nothing to reconcile"]
        return 0, {"mode": "reconcile", "dry_run": True, "candidate": cid,
                   "status": state["status"], "result_sha": state["result_sha"]}, \
               ["[dry-run] would reconcile the saved result; no lock or state write"]
    result = core.reconcile(repo, store, cid)
    return 0, _candidate_payload(result, mode="reconcile"), []


def _render_result(store: Path, cid: str,
                   dry_run: bool) -> tuple[int, dict | None, list[str]]:
    state = core.load_candidate(store, cid)
    if state["status"] not in ("integrated", "receipt-pending", "complete"):
        return 12, {"mode": "render-result", "dry_run": dry_run, "candidate": cid,
                    "status": state["status"],
                    "would_refuse": "no observed integration"}, \
               [f"candidate {cid} is {state['status']}; a result needs an observed integration"]
    payload_path = _candidate_file(store, cid, RESULT_FILE)
    if dry_run:
        return 0, {"mode": "render-result", "dry_run": True, "candidate": cid,
                   "would_write": str(payload_path),
                   "result_sha": state["result_sha"]}, \
               ["[dry-run] would render the result receipt under the store"]
    text = core.render_result(state)
    return 0, {"mode": "render-result", "candidate": cid,
               "payload_path": str(payload_path),
               "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
               "bytes": len(text.encode("utf-8"))}, []


def _verify_result(store: Path, config: dict, cid: str,
                   dry_run: bool) -> tuple[int, dict | None, list[str]]:
    state = core.load_candidate(store, cid)
    if state["status"] not in ("integrated", "receipt-pending", "complete"):
        return 12, {"mode": "verify-result", "dry_run": dry_run, "candidate": cid,
                    "status": state["status"],
                    "would_refuse": "no observed integration"}, \
               [f"candidate {cid} is {state['status']}; a receipt needs an observed integration"]
    payload_path = _candidate_file(store, cid, RESULT_FILE)
    if dry_run:
        if not payload_path.is_file():
            return 12, {"mode": "verify-result", "dry_run": True, "candidate": cid,
                        "would_refuse": "result payload not rendered"}, \
                   [f"candidate {cid} has no rendered result — run --render-result first"]
        relative = (str(config["report"]["directory"]).rstrip("/")
                    + f"/skill-sync-{cid}-result.md")
        target = _report_root(config) / relative
        text = payload_path.read_text(encoding="utf-8")
        matches = target.is_file() and target.read_bytes() == text.encode("utf-8")
        return (0 if matches else 12), {
            "mode": "verify-result", "dry_run": True, "candidate": cid,
            "receipt_relative_path": relative, "note_present": target.is_file(),
            "would_match": matches}, \
            ([] if matches else [f"receipt at {target} does not match the stored result payload"])
    verified = core.verify_result(store, cid, _report_root(config))
    return 0, _candidate_payload(verified, mode="verify-result"), []


def _retry(store: Path, cid: str,
           dry_run: bool) -> tuple[int, dict | None, list[str]]:
    state = core.load_candidate(store, cid)
    if state["status"] != "blocked":
        return 12, {"mode": "retry", "dry_run": dry_run, "candidate": cid,
                    "status": state["status"],
                    "would_refuse": "--retry applies only to a blocked candidate"}, \
               [f"candidate {cid} is {state['status']}; --retry applies only to a blocked candidate"]
    generation = int(state.get("retry_generation") or 0) + 1
    if dry_run:
        return 0, {"mode": "retry", "dry_run": True, "candidate": cid,
                   "status": "blocked", "would_generation": generation,
                   "last_error": state["last_error"]}, \
               [f"[dry-run] would move {cid} blocked -> captured at retry generation {generation}"]
    retried = core.retry_candidate(store, cid)
    return 0, _candidate_payload(retried, mode="retry"), []


def _installer_version() -> str:
    path = _here / "install-skill-repo-sync.py"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return "missing"
    match = re.search(r'^INSTALLER_VERSION\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return match.group(1) if match else "missing"


def selfcheck(repo: Path, store: Path, config: dict, verbose: bool) -> tuple[int, dict, list[str]]:
    """Observed facts only: versions, branch policy, config/report presence, lock state.

    There is deliberately no hook-health claim here; hook consent is inspected
    with `hermes hooks doctor`, not inferred from files this script can see.
    """
    state = srs.load_state()
    machine = str(state.get("machine") or "").strip()
    branch = srs.branch_name(repo)
    contributor_repos = []
    for entry in state.get("repos") or []:
        try:
            contributor_repos.append(Path(entry["path"]).expanduser().resolve())
        except (KeyError, TypeError):
            continue
    if machine and repo.resolve() in contributor_repos:
        allowed, reason = srs.branch_policy(repo, machine)
        policy = "pass" if allowed else f"refuse: {reason}"
    else:
        policy = ("not evaluated (this checkout is not a registered contributor repo; "
                  f"branch {branch or '<detached>'})")
    lock = core.read_maintainer_lock(store)
    vault_root = _report_root(config)
    report_directory = vault_root / str(config["report"]["directory"])
    payload = {
        "script_version": SCRIPT_VERSION,
        "core_version": core.CORE_VERSION,
        "installer_version": _installer_version(),
        "repo": str(repo),
        "branch": branch,
        "branch_policy": policy,
        "maintainer_config": str(store / "maintainer.json"),
        "report_root": str(vault_root),
        "report_root_present": vault_root.is_dir(),
        "report_directory": str(report_directory),
        "report_directory_present": report_directory.is_dir(),
        "maintainer_lock": "held by " + _owner_description(lock) if lock else "not held",
        "hooks": "not inspected by --selfcheck — use `hermes hooks doctor`",
    }
    notes = [f"created_at: {state.get('created_at') or '(not recorded)'}"] if verbose else []
    return 0, payload, notes


def _retired_v2_message(mode: str) -> tuple[int, list[str]]:
    return 12, [f"retired: {mode} is retired — v3 integration uses capture -> prepare -> "
                f"record-review -> render-report/verify-report -> integrate, with ancestry as "
                f"the consumption fact. Nothing was written (no fetch, ref, index or state change)."]


def _pending_mode(args: argparse.Namespace, store: Path) -> int:
    """Monitor protocol: stable stdout, technical failures observable and stable.

    A missing/invalid maintainer config is an installation fault (exit 13); a
    runtime read/fetch failure is the stable `error: monitor-unhealthy` signal
    with exit 0, so a monitor gate never mistakes a broken remote for health.
    """
    config_path = store / "maintainer.json"
    if not config_path.is_file():
        print(f"maintainer config missing: {config_path}", file=sys.stderr)
        return 13
    try:
        config = core.load_maintainer_config(store)
    except core.WorkflowError as exc:
        print(f"maintainer config invalid: {exc}", file=sys.stderr)
        return 13
    if args.dry_run:
        try:
            repo = _repo_from_config(config, args.repo)
        except core.WorkflowError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 12
        try:
            lines = core.pending_lines(repo, store, config["sources"], fetch=False)
        except (core.WorkflowError, OSError) as exc:
            detail = str(exc)
            print(detail if detail.startswith("cannot determine")
                  else f"cannot determine without fetch: {detail}", file=sys.stderr)
            return 0
        if lines:
            print("\n".join(lines))
        return 0
    try:
        repo = _repo_from_config(config, args.repo)
        lines = core.pending_lines(repo, store, config["sources"])
    except (core.WorkflowError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print("error: monitor-unhealthy")
        print(f"pending monitor: {exc}", file=sys.stderr)
        return 0
    if lines:
        print("\n".join(lines))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="v3 maintainer helper (maintainer host only) — candidate, review, "
                    "report and integration modes are thin adapters over skill_repo_workflow.py")
    mode = ap.add_mutually_exclusive_group(required=False)
    mode.add_argument("--capture-source", metavar="REF",
                      help="fetch once, pin the full M/T commits and persist the candidate; "
                           "a refs/heads/refactor/<slug> ref captures its submitted exact tip")
    mode.add_argument("--prepare", metavar="CID", help="create the isolated candidate worktree and merge")
    mode.add_argument("--record-review", metavar="CID",
                      help="validate --review-file, run the fixed checks and persist the reviewed tree")
    mode.add_argument("--render-report", metavar="CID",
                      help="render the deterministic review payload under the store")
    mode.add_argument("--verify-report", metavar="CID",
                      help="verify the exact report bytes at the configured report root")
    mode.add_argument("--integrate", metavar="CID", help="integrate one ordered-parent merge commit")
    mode.add_argument("--reconcile", metavar="CID", help="reconcile an uncertain integration from saved P")
    mode.add_argument("--render-result", metavar="CID", help="render the result receipt under the store")
    mode.add_argument("--verify-result", metavar="CID",
                      help="verify the exact receipt bytes and record completion")
    mode.add_argument("--pending", action="store_true",
                      help="monitor source: sorted `pending <cid>` / `blocked <cid>` lines; "
                           "technical failure prints exactly `error: monitor-unhealthy`")
    mode.add_argument("--retry", metavar="CID",
                      help="advance one blocked candidate by exactly one retry generation")
    mode.add_argument("--submit-refactor", metavar="REF",
                      help="record an explicit exact-tip refactor submission "
                           "(refs/heads/refactor/<slug>) with --tip and --brief")
    mode.add_argument("--selfcheck", action="store_true",
                      help="report observed versions, branch policy, config/report presence and lock state")
    mode.add_argument("--lock", action="store_true", help="acquire the owner-token maintainer lock")
    mode.add_argument("--unlock", action="store_true", help="release the maintainer lock with its owner token")
    mode.add_argument("--note-pushed", action="store_true",
                      help="legacy metadata: record HEAD only after the remote transport tip equals HEAD")
    mode.add_argument("--collect", action="store_true", help="RETIRED (exit 12): v3 capture replaces it")
    mode.add_argument("--preflight", action="store_true", help="RETIRED (exit 12): v3 review gates replace it")
    mode.add_argument("--merge-map", metavar="HOST",
                      help="RETIRED (exit 12): v3 prepare exposes real merge conflicts")
    mode.add_argument("--apply-decisions", metavar="FILE",
                      help="RETIRED (exit 12): v3 records the reviewed tree instead")
    mode.add_argument("--reset-branch", metavar="HOST", nargs="+", action="store",
                      help="RETIRED (exit 12): transport branches are never reset or force-pushed")
    mode.add_argument("--refresh-strip", action="store_true",
                      help="RETIRED (exit 12): the replay rebase is gone; refresh is ancestry-only")
    mode.add_argument("--init-last-pushed", action="store_true",
                      help="RETIRED (exit 12): consumption is an ancestry fact, not a cursor")
    ap.add_argument("--review-file", default=None, metavar="PATH",
                    help="agent review JSON for --record-review")
    ap.add_argument("--tip", default=None, metavar="SHA",
                    help="exact full remote refactor tip for --submit-refactor")
    ap.add_argument("--brief", default=None, metavar="PATH",
                    help="replacement brief JSON for --submit-refactor")
    ap.add_argument("--repo", default=None,
                    help="explicit maintainer clone path (default: the store's maintainer_repo)")
    ap.add_argument("--store", default=None,
                    help=f"explicit state store (default: <HERMES_HOME>/{WORKFLOW_STORE_NAME})")
    ap.add_argument("--outdir", default=None, help="legacy option, only for retired modes")
    ap.add_argument("--force-lock", action="store_true",
                    help="never bypasses ownership: a held lock is refused with its owner token")
    ap.add_argument("--confirm-consumed", action="store_true",
                    help="retained for compatibility; --reset-branch refuses either way")
    ap.add_argument("--dry-run", action="store_true",
                    help="no fetch, mkdir, update-ref, worktree add, lock, state write or push")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--version", action="store_true", help="print the helper version")
    args = ap.parse_args()

    if args.version:
        print(f"skill-repo-maintain {SCRIPT_VERSION} (core {core.CORE_VERSION})")
        return 0

    if args.submit_refactor and (not args.tip or not args.brief):
        ap.error("--submit-refactor requires --tip <full-sha> and --brief <json-path>")
    if not args.submit_refactor and (args.tip or args.brief):
        ap.error("--tip and --brief are only valid with --submit-refactor")

    known = any((args.capture_source, args.prepare, args.record_review, args.render_report,
                 args.verify_report, args.integrate, args.reconcile, args.render_result,
                 args.verify_result, args.pending, args.retry, args.submit_refactor,
                 args.selfcheck, args.lock, args.unlock, args.note_pushed, args.collect,
                 args.preflight, args.merge_map, args.apply_decisions, args.reset_branch,
                 args.refresh_strip, args.init_last_pushed))
    if not known:
        ap.error("a mode is required")

    # Retired modes refuse before any config, Git or state access — even with --dry-run.
    if args.collect:
        code, notes = _retired_v2_message("--collect")
    elif args.preflight:
        code, notes = _retired_v2_message("--preflight")
    elif args.merge_map:
        code, notes = _retired_v2_message("--merge-map")
    elif args.apply_decisions:
        code, notes = _retired_v2_message("--apply-decisions")
    elif args.reset_branch:
        code, notes = retired_reset_branches(args.reset_branch)
    elif args.refresh_strip:
        code, notes = refresh_strip(Path(args.repo) if args.repo else Path("."))
    elif args.init_last_pushed:
        code, notes = 12, ["retired: --init-last-pushed is retired — consumption is an ancestry "
                           "fact (T ancestor main), so no reset cursor exists to bootstrap; "
                           "explicit ledger bootstrap is an installer decision. Nothing was "
                           "written (no ref, index or state change)."]
    else:
        store = _store_from_args(args)
        if args.pending:
            return _pending_mode(args, store)
        if args.note_pushed:
            if not args.repo:
                print("error: --note-pushed requires --repo", file=sys.stderr)
                return 12
            repo_result = git(Path(args.repo).expanduser(), "rev-parse", "--show-toplevel")
            if repo_result.returncode != 0:
                print(f"error: not a Git repository: {args.repo}", file=sys.stderr)
                return 12
            try:
                code, notes = note_pushed(Path(repo_result.stdout.strip()), args.dry_run)
            except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
                code, notes = 12, [f"note-pushed: {type(exc).__name__}: {exc}"]
            for line in notes:
                print(line, file=sys.stderr)
            return code
        config = _load_config_or_none(store)
        if config is None:
            missing = not (store / "maintainer.json").is_file()
            detail = ("maintainer config missing" if missing else "maintainer config invalid")
            print(f"error: {detail}: {store / 'maintainer.json'}", file=sys.stderr)
            return 13
        try:
            repo = _repo_from_config(config, args.repo)
        except core.WorkflowError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 12
        try:
            if args.lock:
                code, notes = lock_maintainer(store, force=args.force_lock, dry_run=args.dry_run)
                payload = None
            elif args.unlock:
                code, notes = unlock_maintainer(store, dry_run=args.dry_run)
                payload = None
            elif args.selfcheck:
                code, payload, notes = selfcheck(repo, store, config, args.verbose)
            elif args.capture_source:
                code, payload, notes = _capture_source(
                    repo, store, config, args.capture_source, args.dry_run)
            elif args.submit_refactor:
                code, payload, notes = _submit_refactor(
                    repo, store, config, args.submit_refactor, args.tip, args.brief,
                    args.dry_run)
            elif args.prepare:
                code, payload, notes = _prepare(repo, store, args.prepare, args.dry_run)
            elif args.record_review:
                code, payload, notes = _record_review(
                    repo, store, args.record_review, args.review_file, args.dry_run)
            elif args.render_report:
                code, payload, notes = _render_report(store, args.render_report, args.dry_run)
            elif args.verify_report:
                code, payload, notes = _verify_report(
                    store, config, args.verify_report, args.dry_run)
            elif args.integrate:
                code, payload, notes = _integrate(repo, store, config, args.integrate, args.dry_run)
            elif args.reconcile:
                code, payload, notes = _reconcile(repo, store, args.reconcile, args.dry_run)
            elif args.render_result:
                code, payload, notes = _render_result(store, args.render_result, args.dry_run)
            elif args.verify_result:
                code, payload, notes = _verify_result(
                    store, config, args.verify_result, args.dry_run)
            elif args.retry:
                code, payload, notes = _retry(store, args.retry, args.dry_run)
            else:  # pragma: no cover - argparse mode group and known check cover this
                code, payload, notes = 2, None, ["no mode selected"]
        except core.WorkflowError as exc:
            code, payload, notes = 12, None, [f"error: {exc}"]
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            code, payload, notes = 12, None, [f"error: {type(exc).__name__}: {exc}"]

    for line in notes:
        print(line, file=sys.stderr)
    if "payload" in locals() and payload is not None:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
