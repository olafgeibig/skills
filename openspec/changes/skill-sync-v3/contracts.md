# Implementation contracts

This is the selected engineering contract for OpenSpec change `skill-sync-v3`, extracted from the agreed plan at preparation time. These are proposed APIs and fixture code, not installed functionality. Read only the sections your work packet cites. The capability specs remain the observable acceptance contract; `design.md` settles architecture. Do not copy runtime private config or execute live deployment steps.

## 2. Exact state, API and CLI contract

### 2.1 New core API

These are **new proposed definitions**, not symbols that already exist. Keep them in CORE; CLI adapters import the sibling module using their script directory. All Git calls use argument lists, check return codes, `GIT_TERMINAL_PROMPT=0`, SSH batch mode and timeouts. `git_bytes()` preserves blob/index bytes; don't decode Git object content merely to copy it.

```text
class WorkflowError(RuntimeError):
    pass

# Pure state helpers
canonical_bytes(value: dict) -> bytes  # json, sort_keys=True, separators=(",", ":"), UTF-8
candidate_id(repo_id: str, ref: str, main: str, tip: str, policy: str, kind: str) -> str
# Return full sha256 hex of canonical values; no timestamps/paths in identity.
atomic_json(path: Path, value: dict) -> None
read_json(path: Path) -> dict
safe_relative(root: Path, relative: str) -> Path

# Git/discovery/capture
git(repo: Path, *args: str) -> subprocess.CompletedProcess
is_ancestor(repo: Path, older: str, newer: str) -> bool
source_status(repo: Path, main: str, tip: str) -> str  # consumed | pending; no empty-diff shortcut
capture(repo: Path, store: Path, source: dict, kind: str = "transport") -> dict
prepare(repo: Path, store: Path, candidate: dict) -> dict
load_candidate(store: Path, cid: str) -> dict

# Agent review, tests and reporting
validate_review(candidate: dict, review: dict, repo: Path, worktree: Path) -> None
validate_tree(candidate: dict, worktree: Path, review: dict) -> dict
run_checks(candidate: dict, worktree: Path) -> list[dict]
record_review(store: Path, cid: str, review: dict, checks: list[dict], validation: dict) -> dict
verify_result(store: Path, cid: str, report_root: Path) -> dict
render_review(candidate: dict, review: dict, checks: list[dict], tree: str) -> str
verify_report(candidate: dict, expected_text: str, report_root: Path) -> dict

# Integration/recovery: no shell commands or arbitrary callables in candidate JSON
publish(repo: Path, store: Path, cid: str, report_root: Path) -> dict
reconcile(repo: Path, store: Path, cid: str) -> dict
render_result(candidate: dict) -> str
submit_refactor(repo: Path, store: Path, ref: str, tip: str, brief: dict) -> dict
pending_lines(repo: Path, store: Path, sources: list[dict]) -> list[str]
```

`publish` calls validation again; a previous green check flag is not a bypass. It verifies report bytes, reviewed tree, full M,T, parent list, and authorized source registry. `publish`/`reconcile` acquire the publisher lock **once per public operation**; shared internal `_publish_locked`/`_reconcile_locked` routines never recursively acquire it. Existing publish-intent reuses saved P; a repeated call on published/complete performs only reconciliation/receipt work, never creates a fresh integration commit. Use `WorkflowError` with stable concise messages; CLI prints details to stderr and exits 12. Hard checks return exit 10, uninstalled 13, no work/success 0, argparse usage 2. Do not catch and hide programmer exceptions as “nothing pending”.

### 2.2 Local state schema

New state lives outside tracked repo files in `<HERMES_HOME>/skill-repo-sync-v3/`. Explicit publisher config `publisher.json`, atomic candidate journals `candidates/<cid>/state.json`, `review.json`, `checks.json`, rendered `review.md` and `result.md`, and candidate worktrees under `worktrees/<cid>/`. Use absolute `store` paths in APIs; never default scratch under a tracked repo.

Example **test values**, not production config:

```json
{
  "schema": 3,
  "repo_id": "owned-skills",
  "remote": "origin",
  "publisher_repo": "/path/to/publisher-clone",
  "runtime_roots": ["/path/to/runtime-checkout"],
  "policy": "skill-review-v1",
  "publisher_identity": {"machine": "publisher-test", "profile": "default", "scope": "shared-generic"},
  "sources": [{"ref": "refs/heads/machine/testlab", "machine": "testlab", "profile": "default", "scope": "shared-generic", "enabled": true}],
  "report": {"vault": "akademeia", "vault_root": "/path/to/registered/vault", "directory": "projects/hermes-agent/reports"}
}
```

Do not promise hard profile isolation from `scope`. Registry entries are operator assertions checked at deployment against real checkout ownership. A source not approved for this destination cannot be captured; do not let a candidate JSON override its registry entry. Defer legacy mixed-trust checkout migration to explicit operator action, without making it a daily human candidate gate.

Candidate journal required fields: `schema`, `id`, `repo_id`, `kind` (`transport`/`refactor`), `source_ref`, `source_machine`, `source_profile`, full `main_sha`, full `source_sha`, `policy`, `status`, `created_at`, `worktree`, `input_paths`, `conflict_paths`, `review_digest`, `reviewed_tree`, `report_relative_path`, `report_sha256`, `result_sha` (P if committed), `last_error`, `attempts`. Store `input_paths` as Git path strings obtained via NUL-delimited output; each ref SHA is resolved to a commit object, not validated by length alone.

API return and persistence rules:

`load_candidate(store,cid)`, `capture` and `prepare` return the persisted fields plus an **in-memory-only `_store`** absolute Path derived from the trusted caller's store. Never persist `_store` or accept it from review JSON. Functions such as `verify_report(candidate,...)` use it to reload the authoritative journal/config before writes. `validate_tree` returns `{"tree": "<full git tree SHA>", "paths": ["<review-covered paths>"]}`; it never fabricates a success flag. `run_checks` returns rows `{"name": "...", "required": true, "status": "passed|failed|not-applicable", "exit_code": 0, "stdout": "...", "stderr": "..."}`. Failed/not-run required checks cannot be recorded as reviewed. The minimal demo fixture has no package test/validator files: record their **absence as not-applicable**, while still performing whitespace, conflict, path-coverage and tree checks; the real maintenance package has required runner/validator checks. A missing previously-required runner is an error, not not-applicable.

State machine:

```text
captured -> prepared -> reviewed -> report-verified -> publish-intent -> published
                 \-> blocked          \-> stale
published -> receipt-pending -> complete
```

Every transition is atomically written, and loaders reject impossible combinations (e.g. published with no P). `blocked` retains evidence; repeat unchanged candidate isn't an automatic endless loop. Retry is explicit `--retry <cid>` (or one configured script-only bounded retry after a transient failure); no unbounded agent retries. `stale` cannot publish, new M produces a new cid. No `waiting-for-human` status in the default implementation. A review rejecting **all** lessons still advances to reviewed and may publish an empty-net merge that records consumption, not blocked forever.

### 2.3 Review schema (agent output, not execution permission)

```json
{
  "schema": 1,
  "candidate_id": "<full candidate id>",
  "main_sha": "<M>",
  "source_sha": "<T>",
  "summary": "Accept a useful generic addition; no existing instruction is replaced",
  "files": [{
    "path": "skills/demo/SKILL.md",
    "change_type": "addition",
    "decision": "accept",
    "source_anchors": [{"ref": "<T>", "path": "skills/demo/SKILL.md", "quote": "Exact source text"}],
    "reason": "A useful generic instruction not already present",
    "replacements": []
  }]
}
```

A nonempty top-level `summary` is required, including for an empty-diff acknowledgment with `files: []`; it explains why the no-net-change source tip is being consumed. Allowed `change_type`: `addition`, `correction`, `replacement`, `duplicate`, `unsuitable`, `integration`. Allowed `decision`: `accept`, `combine`, `reject`. File coverage must exactly cover input paths **and** any additionally modified path used to deduplicate/reconcile (the reason must name why that extra file was needed). Every source quote must occur in the named blob; source refs are limited to captured M,T and merge bases, not arbitrary filesystem locations. Replacements contain `{old_ref,old_path,old_quote,new_path,new_quote,reason}`; old quote must exist in old ref, new quote in final staged result, old instruction must not remain as a live conflicting instruction. The agent must explain example-vs-instruction warnings. Empty reasons, invented source quotes, extra actions or arbitrary command fields are rejected; “confidence: high” is not evidence. A judgment's semantic truth is reviewed by the agent, not provable from a JSON schema.

### 2.4 Proposed CLI surface

Keep ENGINE `--stage`, `--sync-from-main`, `--selfcheck`, `--version`; require unexpected `main` checkout to warn/refuse rather than silently pass as healthy. HELPER gains modes below, all accepting explicit `--repo`, `--store` (publisher config root) and `--dry-run` (no fetch, files, index, commits or state writes; inspect cached refs and label them cached):

```text
--capture-source refs/heads/machine/testlab
--prepare <cid>
--record-review <cid> --review-file <path>
--render-report <cid>                 # saves only scratch payload under store in normal mode
--verify-report <cid>                 # exact local read at configured registered vault path
--publish <cid>
--reconcile <cid>
--render-result <cid>
--verify-result <cid>
--submit-refactor refs/heads/refactor/topic --tip <fullsha> --brief <jsonpath>
--pending
--retry <cid>
```

Legacy `--reset-branch` (even with `--confirm-consumed`), `--init-last-pushed`, and `--refresh-strip` exit 12 with `retired: v3 preserves merge ancestry; no reset or rebase`. **Do not retain a compatibility alias:** the new producer session refresh is ENGINE `--sync-from-main`; conflictful merge preparation belongs to the explicit pre-consolidation runbook below. `--note-pushed` verifies remote HEAD equals the producer tip and records metadata but never decides that a reset is safe. Old `--collect`, `--merge-map`, `--apply-decisions`, `--preflight` become compatibility diagnostics/refusals; they must not leave the old publication path usable to bypass v3 gates. Update cron templates to the new commands before activation.

## 3. Git invariants and crash safety (authoritative algorithms)

### Capture/prepare

- Fetch **once**, then resolve M and T from fetched `refs/remotes/origin/...`; no racing `ls-remote` SHA that hasn't been fetched. `source_status`: if T ancestor M => consumed; otherwise pending, regardless of diff size. For a same-tree unacknowledged tip, prepare a normal merge and report why its unchanged tree is being acknowledged.
- Create candidate ID with the declared inputs; identical capture returns the same journal. Pin input commits via `refs/hermes-sync/candidates/<cid>/main` and `/source` in the publisher clone using `git update-ref`; do not use remote branch names as immutable input references.
- `git worktree add --detach <candidate-dir> M`; fail if candidate dir already exists in an inconsistent state, never `rm -rf` it. Candidate worktree must not be under or equal any runtime discovery root, report root or live project directory.
- Precheck changed modes/blobs from merge-base→T and M: regular text files `100644` and executable text `100755` are supported. Binary/NUL, symlink `120000` and submodule `160000` are blocked before candidate merge. Use Git merge for add/delete/modify/rename and modes; never interpret missing blobs as empty files. UTF-8 reports can describe unsupported binary paths without decoding payloads.
- Native `git merge --no-ff --no-commit T`, with repo-local `core.hooksPath` pointing at a **nonexistent path inside candidate store** and `GIT_MERGE_AUTOEDIT=no`, `rerere.enabled=false`. Do not execute repository hooks during preparation/promotion. Exit 1 is acceptable **only** when `git ls-files -u -z` actually lists unmerged entries; any other merge failure blocks. Keep `MERGE_HEAD=T` for correct parent formation.
- Agent edits only this candidate, resolves staged conflicts with explicit path adds, and stages clean/add/delete paths too. Do not lose additions because they were “clean”; Git's index is the complete proposed tree. On a manual agent error don't abort/delete work blindly: mark blocked with paths/status for inspection.

### Final gate

- Require HEAD=M, MERGE_HEAD exactly T, no unmerged entries and no unstaged or untracked edits; `git diff --cached --check` exit 0. Derive final tree via `git write-tree`, and changed file coverage via `git diff --cached --name-only -z M` UNION captured input paths (so dropped paths cannot disappear from review coverage).
- Validate staged blobs, not dirty files; final regular text code must compile (`compile`/`ast.parse` in memory), JSON parse, package validation/tests from a clean matching candidate worktree. Run only fixed allowlisted validation commands; never execute `review.json` fields or report text.
- Required package tests for this package: `sys.executable -m pytest -p no:cacheprovider skills/skill-library-maintenance/tests -q`; record stdout/stderr/exit. The package validator is `./skills/skill-builder/scripts/skills-ref.sh validate ./skills/skill-library-maintenance` when that package changed; library audit `sys.executable skills/skill-library-maintenance/scripts/audit-skill-library.py skills --json`. For a newly discovered changed package with tests/validator, report an explicit configured check; no pretending “all checked” when unknown. Mechanical failures block, malformed Markdown examples don't become unsupported APIs. Report substantive semantic findings to the reviewer, not a regex veto.
- Record exact checks and tree; if either content or index changes, require revalidation and a newly rendered report. No report with a stale tree can authorize a push.

### Promotion (core, not ad-hoc model shell)

1. Resolve the configured publisher repository with `git rev-parse --path-format=absolute --git-common-dir` (or resolve the returned relative common-dir against the actual repo root on Git versions without that flag). Acquire `<git-common-dir>/hermes-sync/publisher.lock` via atomic `O_CREAT|O_EXCL`. All linked worktrees and alternate state stores of **this same publisher clone** use this exact lock; do not key it to `--git-dir` or `<store>`. Write owner token, pid, host and acquisition time; release only with matching token in `finally`. A crash leaves a visible lock for explicit recovery; no broad cron-db or age-only deletion.
2. Re-read candidate/review/report/checks; revalidate tree/hash and source registry. Fetch and require current remote M unchanged. Source T can advance to descendant T2; a rewrite deleting/replacing T is a block requiring recapture, not permission to push different contents. Candidate worktree HEAD and MERGE_HEAD still M,T.
3. Form the integration commit from the final index with Git's actual merge parent state (or `git commit-tree <tree> -p M -p T` if all inputs validated); choose **commit-tree** to avoid mutable MERGE_HEAD and hooks at promotion, then verify parent order and tree. Commit message has `consolidator:` prefix plus `Skill-Sync-Candidate: <cid>`, `Source-Ref: <ref>`, `Source-Tip: <T>`, `Review-Digest: <digest>`, `Reviewed-Tree: <tree>`. Use a repo-local identity, never modify global Git config. Preserve P with `refs/hermes-sync/candidates/<cid>/result`.
4. Save journal `publish-intent`, P, full parents/tree and report hash **before** remote push. `git push origin P:refs/heads/main` with no force; normal Git FF rule prevents overwriting an advanced main. On rejection, inspect remote; if P is absent and M changed => stale. Never amend/rebase/retry by force. For transport T2 advance, push still contains only T's candidate.
5. Read exact `refs/heads/main` with checked `git ls-remote`; on successful P or P being an ancestor of later remote main, mark published (if later main has not been fetched, fetch before ancestry check). On network uncertainty keep publish-intent and reconcile; do not manufacture “pushed” from the command's success text.
6. `reconcile`: find saved P on fetched main ancestry and verify candidate trailer/tree/parents. If present, repair state/receipt only; if remote remains M, retry same P only under lock; otherwise stale/incident, no duplicate commit. If report was altered, retain incident state even if P is already published: fix/report discrepancy, never pretend publication didn't happen.
7. Render/read-back result note and mark complete. Never reset transport ref T/T2. Reject-only merge has same tree as M but parents M,T and an honest rejection report. Expected repeat behavior: captured T now consumed, T2 pending, no reprocessing of old text.

### Producer refresh (merges, never rebase)

Session-start is conservative: in clean registered transport checkout, fetch; if HEAD ancestor origin/main and its own unpushed work is absent, `git merge --ff-only origin/main`; if origin/main ancestor HEAD do nothing; if diverged print “pre-consolidation merge required” without changing files/index. Dirty status => don't integrate. Never use rewritten-history `last_pushed_tip` counts or reset. Pre-consolidation agent may perform `git merge --no-ff --no-commit origin/main`, resolve/review, commit the merge then normal push; preserve pending local changes by deliberate staging first. Check no merge/rebase already in progress. Unexpected branch (including `main`) refuses stage/push, `refactor/*` emits explicit skip, not transport success. No resume catch-up promise: daily schedule or explicit user-triggered pre-consolidation only.

## 4. Test harness to paste first (new TEST)

This creates only pytest temp fixtures and local bare remotes. It is complete code, not production implementation. Set `TMPDIR` to the managed scratch directory when running tests. Include these helpers exactly; tests below extend this file.

```python
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
```

Run harness-only collection before CORE exists: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider skills/skill-library-maintenance/tests/test_skill_repo_workflow.py --collect-only -q`. Expected no tests collected, not a syntax error. The first behavior test below fails because CORE does not exist; after CORE is created failures must be behavior assertions, not missing fixture imports.


## Reviewed candidate fixture (needed by publication tests)

**C5. Shared helper for later tests** (complete test helper to add after C4, not a bypass in production):

```python
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
```

Add the required `record_review(store,cid,review,checks,validation) -> dict` API to CORE: validate cid/refs, full path coverage, checks green and tree; persist review/checks, exact review hash and reviewed_tree atomically, status reviewed. `verify_report` transitions to report-verified via store location carried by validated candidate. Don't trust caller's arbitrary paths or status booleans; load authoritative candidate/config again.

