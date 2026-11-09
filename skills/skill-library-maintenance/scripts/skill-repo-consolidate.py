#!/usr/bin/env python3
# skill-repo-consolidate — v2 "Stage & Curate" consolidation helpers (runs on the curator host only).
#
# SCRIPT_VERSION: 2.1.0
# Companion of skill-repo-sync.py. The nightly consolidation is AGENT work: the cron job loads
# skill-library-maintenance, reads the collected diffs, edits files on main deliberately
# (dedupe, scope discipline, SemVer — rules in skill-governance), commits, pushes main and
# resets the consumed transport branches. This script is the mechanical scaffold around that:
#
#   --collect [--outdir DIR]   fetch spray; for every machine branch with a non-empty net diff
#                              against origin/main, write the diff and a metadata row; print JSON
#                              (read-only apart from the fetch — feeds the agent prompt)
#   --preflight [--outdir DIR] scan the pending consolidation target (working tree on main after
#                              the agent's edits) for instance pointers and dangling references;
#                              exit 10 on findings (the agent must repair, not force through)
#   --merge-map HOST           v2.1 hunk gate: mechanical 3-way map for ONE machine branch
#                              (base=merge-base, ours=main, theirs=branch) — clean files are
#                              merge-ready without the LLM; only conflict blocks are cut into
#                              packets (±10 context lines, over 80 lines flagged "oversized")
#   --apply-decisions FILE     apply decisions.json (file/block/action/text) to the conflict
#                              blocks of a --merge-map run; --outdir required (that run's
#                              merged/ dir). All-or-nothing per file (R2)
#   --lock / --unlock          single-flight guard for consolidation runs (exit 12 while a run
#                              holds the lock); --force-lock is the deliberate human override
#   --reset-branch NAME ...    for each consumed host: push --force-with-lease origin
#                              <origin/main sha>:refs/heads/machine/<host>  (the ONE allowed force)
#                              refuses when local main != origin/main or the branch still has
#                              unconsolidated content
#
# Exit codes: 0 ok/no-op · 10 preflight findings · 12 other error · 13 not installed
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path

SCRIPT_VERSION = "2.1.0"
STATE_NAME = "skill-repo-sync.json"

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


def hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes")).expanduser()


def git(repo: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    env.setdefault("GIT_SSH_COMMAND", "ssh -oBatchMode=yes -oConnectTimeout=10")
    env.setdefault("GIT_ASKPASS", "/bin/true")
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                          check=check, timeout=180, env=env)


def repo_from_args(args: argparse.Namespace) -> Path:
    root = git(Path(args.repo), "rev-parse", "--show-toplevel")
    if root.returncode != 0:
        raise SystemExit(f"error: not a git repo: {args.repo}")
    return Path(root.stdout.strip())


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
                base = repo / file if file else repo
                if not (base.parent / target).exists() and not (repo / target).exists():
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


def reset_branches(repo: Path, hosts: list[str], dry_run: bool, confirmed: bool) -> tuple[int, list[str]]:
    """Push origin/main onto the consumed transport branches. The ONLY allowed force in v2.

    `--confirm-consumed` is the curator's assertion that it has consolidated the branch.
    Git ancestry cannot replace that judgement: a curated commit on main rewrites the branch's
    content instead of merging it, so the branch tip is never an ancestor and the content is
    present all the same. Without the flag this refuses to touch anything.
    """
    notes: list[str] = []
    if not confirmed:
        return 12, ["machine reset: refusing without --confirm-consumed — the curator asserts "
                    "which branches it has consolidated; ancestry cannot decide this for a "
                    "curated commit"]
    main, err = main_sha(repo)
    if err:
        return 12, [f"machine reset: {err}"]
    remote_shas = machine_shas(repo)
    for host in hosts:
        ref = f"refs/heads/machine/{host}"
        old = remote_shas.get(host)
        if old is None:
            notes.append(f"machine/{host}: not on remote — nothing to reset")
            continue
        if old == main:
            notes.append(f"machine/{host}: already at origin/main")
            continue
        if dry_run:
            notes.append(f"[dry-run] would push {main[:12]}:{ref} (was {old[:12]})")
            continue
        push = git(repo, "push", "origin", f"--force-with-lease={ref}:{old}", f"{main}:{ref}")
        if push.returncode != 0:
            notes.insert(0, f"machine/{host}: reset push failed: {(push.stderr or push.stdout).strip()[:300]}")
            return 12, notes
        notes.append(f"machine/{host}: reset to origin/main ({main[:12]})")
    return 0, notes


def _iso_ts(value: str) -> float | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def acquire_lock(repo: Path, ttl_seconds: int = 10800,
                 cron_db: Path | None = None, force: bool = False) -> tuple[int, list[str]]:
    """Single-Flight-Guard: ein zweiter Lauf waehrend TTL wird abgewiesen (exit 12).
    Zusatz-Check: laufende Cron-Executionen ANDERER Laeufe (claimed/running und aelter
    als 60 s — der eigene Claim ist immer frisch; pid-Vergleich ist unbrauchbar, weil die
    executions.db die dispatchende Prozess-id notiert, nicht die Executor-Linie).
    cron_db=None deaktiviert den Live-Check (Tests); main() uebergibt executions.db explizit."""
    if force:
        pass  # deliberate override, fall through
    elif cron_db is not None and cron_db.is_file():
        import sqlite3
        con = sqlite3.connect(f"file:{cron_db}?mode=ro", uri=True)
        try:
            rows = con.execute(
                "SELECT id, claimed_at FROM executions "
                "WHERE status IN ('claimed','running')").fetchall()
        finally:
            con.close()
        # Self-exclusion by claim AGE: an execution claim is recorded with the
        # DISPATCHER's pid, not the executor's lineage (verified against the claims table), so identity
        # can never be matched by pid — but this run's own claim is always seconds old.
        # Anything claimed more than 60s ago is a genuinely different run in flight.
        now_ts = datetime.now(tz=timezone.utc).timestamp()
        others = []
        for rid, claimed_at in rows:
            ts = _iso_ts(str(claimed_at))
            if ts is None or now_ts - ts > 60:
                others.append((rid, claimed_at))
        if others:
            return 12, [f"lock: {len(others)} other execution(s) in flight since "
                        f"{others[0][1]} (claimed >60s ago) — refusing a second run"]
    gitdir = Path(git(repo, "rev-parse", "--git-dir").stdout.strip())
    if not gitdir.is_absolute():
        gitdir = repo / gitdir
    lock_path = gitdir / "hermes-consolidate.lock"
    notes: list[str] = []
    if lock_path.exists():
        age = time.time() - lock_path.stat().st_mtime
        if age < ttl_seconds and not force:
            return 12, [f"lock: already running — consolidation lock is {int(age)}s old "
                        f"(< {ttl_seconds}s); use --force-lock only deliberately"]
        notes.append(f"lock: stale lock ({int(age)}s) replaced")
        lock_path.unlink(missing_ok=True)
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return 12, ["lock: already running — another run acquired the lock this instant"]
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(str(os.getpid()))
    notes.insert(0, f"lock: acquired ({lock_path})")
    return 0, notes


def release_lock(repo: Path) -> None:
    gitdir = Path(git(repo, "rev-parse", "--git-dir").stdout.strip())
    if not gitdir.is_absolute():
        gitdir = repo / gitdir
    (gitdir / "hermes-consolidate.lock").unlink(missing_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="v2 consolidation helpers (curator host only)")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--collect", action="store_true",
                      help="fetch and write pending branch diffs + metadata JSON")
    mode.add_argument("--preflight", action="store_true",
                      help="scan pending branch diffs for instance pointers and dangling refs")
    mode.add_argument("--reset-branch", metavar="HOST", nargs="+", action="store",
                      help="reset consumed machine branches to origin/main (force-with-lease)")
    mode.add_argument("--merge-map", metavar="HOST", action="store",
                      help="mechanical 3-way map (base=merge-base, ours=main, theirs=branch) "
                           "with hunk-level conflict packets for one machine branch")
    mode.add_argument("--apply-decisions", metavar="FILE", action="store",
                      help="apply decisions.json to the conflict blocks of a --merge-map run "
                           "(--outdir required: that run's merged/ directory)")
    mode.add_argument("--lock", action="store_true",
                      help="single-flight guard: acquire the consolidation lock (exit 12 if a run is active)")
    mode.add_argument("--unlock", action="store_true", help="release the consolidation lock")
    ap.add_argument("--force-lock", action="store_true",
                    help="deliberate override of the single-flight lock (human decision only)")
    ap.add_argument("--confirm-consumed", action="store_true",
                    help="curator assertion: the named branches are consolidated; required by --reset-branch")
    ap.add_argument("--repo", default=None, help="path to the shared skill repo (default: from state)")
    ap.add_argument("--outdir", default=None, help="where collect writes diffs (default: <repo>/.consolidate-scratch)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    if args.repo:
        repo = repo_from_args(args)
    else:
        state = srs.load_state()
        repos = list(state.get("repos") or [])
        if not repos:
            print("error: no repo configured — pass --repo")
            return 13
        repo = Path(repos[0]["path"]).expanduser()
        if not repo.is_dir():
            print(f"error: configured repo missing: {repo}")
            return 13

    outdir = Path(args.outdir) if args.outdir else repo / ".consolidate-scratch"
    try:
        if args.lock:
            if args.dry_run:
                code, notes = 0, ["[dry-run] would acquire the consolidation lock (nothing written)"]
            else:
                code, notes = acquire_lock(repo, ttl_seconds=10800,
                                           cron_db=hermes_home() / "cron" / "executions.db",
                                           force=args.force_lock)
        elif args.unlock:
            if args.dry_run:
                code, notes = 0, ["[dry-run] would release the consolidation lock (nothing written)"]
            else:
                release_lock(repo)
                code, notes = 0, ["lock: released"]
        elif args.merge_map:
            code, notes = merge_map(repo, args.merge_map, outdir)
        elif args.apply_decisions:
            if not args.outdir:
                code, notes = 12, ["apply-decisions: --outdir is required "
                                   "(the merged/ directory written by --merge-map)"]
            else:
                code, notes = apply_decisions(repo, Path(args.apply_decisions), outdir)
        elif args.collect:
            code, notes = collect(repo, outdir, args.verbose)
        elif args.preflight:
            code, notes = preflight_scan(repo, outdir)
        else:
            code, notes = reset_branches(repo, args.reset_branch, args.dry_run, args.confirm_consumed)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        code, notes = 12, [f"skill-repo-consolidate: {type(exc).__name__}: {exc}"]
    for line in notes:
        print(line, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
