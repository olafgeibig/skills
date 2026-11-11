# Shared skill repo: stage and integrate (cross-installation sync)

Applies when the same skill repository is mounted on more than one Hermes installation
(`skills.external_dirs`). The design is **Stage & Integrate**: no machine session ever writes `main`;
each installation stages its work onto a transport branch `machine/<hostname>`, and one monitor-gated
maintainer consumes the transport branches one per pass, one `main` commit per consumed branch.

## The problem this solves

The background review writes lessons into skills through `skill_manage` — including skills in a
shared, git-versioned repository — and every installation accumulates manual edits beside them.
Left alone, those writes collide across machines. The previous design (a per-mutation maintainer
committing to `main` seconds after each `skill_manage` edit, gated by a ledger hash chain) failed in
two ways, both observed:

1. One commit per edit: a multi-edit review landed as a burst of single-file commits seconds apart,
   and the hash chain held files retroactively — any commit made outside the ledger broke the chain
   and stalled push and cursor for the whole repository, unfixable by retry.
2. `main` had as many writers as machines plus the review, so every collision arrived as an urgent
   merge and nothing carried responsibility for semantic conflicts.

Symptoms worth recognising: `git status` shows changes to `skill-governance` / `skill-builder` /
`skill-library-maintenance` that no human made. Attribute them from the mutation ledger
(`<hermes home>/skills/.curator_ledger.jsonl`), not from the ledger's `actor` field — review writes
are also recorded as `actor: curator`.

## Architecture (what must stay true)

| Piece | Rule |
|---|---|
| `main` | exactly one writer: the maintainer. Machine sessions, hooks and sweeps never touch it |
| Transport branch | `machine/<hostname>` per installation — a landing strip for commits, not a feature branch. **Never reset or force-pushed**: consumption is an ancestry fact (`T` ancestor of `main`) and the acknowledgment is a merge commit on `main`; the branch tip stays exactly as integrated |
| Staging trigger | hourly script-only cron → `--stage`: bundles the pending ledger paths **and** the dirty worktree into ONE LOCAL commit on the transport branch — the push belongs to the pre-integration run (what lands on a transport branch is always pre-integrated). Only `machine/<name>` is a sweep target: a `refactor/*` branch is excluded untouched and `main` is refused with exit 12 even when clean. A stale ledger path (missing, never tracked) is recorded as skipped in `stage-report.json`; a whitespace or commit failure undoes only that run's index entries, so correcting the cause and rerunning succeeds. The cursor advances only through the entries read at the start of the attempt — a row another writer appends during the commit stays pending |
| Instance pre-integration | daily agent run per installation before the maintainer: reviews that installation's own pending additions, moves instance-shaped lessons out of canonical edits into the *writing* profile's adaptation, leaves generic content for the maintainer — then screens the whole unpublished history, records its profile-scope review and integrates exactly the reviewed tip with `--push-reviewed`: it is the only pusher |
| Refresh trigger | `on_session_start` shell hook (`--sync-from-main`): fetch; fast-forward the transport branch when `HEAD` is an ancestor of `origin/main` (integrated main is newer); divergent or dirty work is preserved for a deliberate pre-integration merge — never reset, rebase or autostash |
| Monitor gate | `--monitor-script` gate: a cheap shim prints the stable pending report (`--pending --store … --repo …`) each tick; the exact-bytes hash suppresses unchanged output entirely — wake-on-change, the agent never runs idle. `blocked <cid>` is stable (no retry churn); unfinished integration journals emit `recover <cid>`, incidents emit `incident <cid>` even after consumption; `error: monitor-unhealthy` is the observable technical-failure signal |
| Integration trigger | monitor-gated (e.g. every 30 min) maintainer cron on the maintainer host (agent run, model-pinned; the monitor gate suppresses the run while nothing is pending): candidates are processed one at a time through capture → prepare → record-review → render/verify-report → integrate → render/verify-result; consumption is ancestry (`T ancestor main`), never a branch reset |
| Candidate worktree | the complete native merge index in an isolated worktree, with `MERGE_HEAD=T`; clean files and genuine conflicts are both in the artifact — the agent edits only that worktree and never a whole diff |
| Commit granularity | one staging commit per sweep (the ledger holds hashes, not intermediate contents — per-run commits are unreconstructable, so the sweep commits the current content per path, once); one integration merge commit `P` per consumed candidate, with ordered parents `M,T` and the reviewed tree |
| Commit message | names the skills whose files actually changed; ledger entry IDs ride in the trailers for attribution and recovery; the integration commit carries the candidate/source/review trailers |
| Overlap | one home per rule when two candidates touch the same file; conflicts are resolved explicitly in the candidate worktree, never `-X ours`/`-X theirs`, never a force-push of `main` |
| Review pass | the review covers every input and additionally modified path with exact source anchors and reasons; the reviewed tree is the integration gate (contracts §2.3/D4), not a scan of the original incoming diff |
| Gate before `main` | `validate_review` + `run_checks` + `validate_tree` + exact report read-back: complete path coverage, real quotes, fixed checks, staged-tree equality, reviewed tree; nothing reaches `main` unreviewed |
| Long sessions | the skill *index* is a start-of-session snapshot (prompt-cache invariant); skill *bodies* load from disk, so `/skill-name` always yields current content. Never pull mid-session to "fix" an index |

Two design facts the failure modes establish, worth keeping when this is next redesigned:

- Provenance must hold without old ledger entries matching current `HEAD` — the chain is evidence
  for the maintainer, never a hold on transport. The ledger selects and attributes paths; it cannot
  certify content against a moving `HEAD`.
- Semantic review gates canonical writes even when git reports no conflict: duplication, scope leaks
  and contradictory rules arrive conflict-free. Hash integrity proves provenance, not quality —
  the candidate review/tree gate (`--record-review`) plus the review rule in `skill-governance`
  is the quality side.

## v3 core: candidate state, capture and transport provenance

`scripts/skill_repo_workflow.py` is the shared core for the v3 merge workflow (workflow schema 3).
It is a library: CLI adapters import it from their script directory, and importing it has no side
effects. This section documents the implemented core surface (packets 03-11), including explicit
exact-tip refactor submission. Nothing is stubbed as successful.

### Store and registry

- State lives outside tracked repository files. The store is always an **absolute** path passed by
  the caller; the core never defaults a scratch directory inside a checkout, and `capture` refuses
  a store inside the maintainer working tree.
- `<store>/maintainer.json` is validated strictly before any candidate journal is trusted:
  `schema` 3, `repo_id`, `remote`, absolute `maintainer_repo`, absolute `runtime_roots`, `policy`,
  `maintainer_identity` (`machine`/`profile`/`scope`), report settings, and a source registry of
  `refs/heads/...` entries with explicit `enabled` booleans and no duplicate refs.
- `capture` verifies that `maintainer_repo` is the actual checkout and refuses unknown, disabled or
  identity-mismatched source entries. A candidate journal can never override its registry entry.
- `report.allowed_scopes` in `<store>/maintainer.json` is the destination's admission allowlist;
  omitted means `["shared-generic"]`, and `[]` denies every scope. Every entry must be nonempty
  text, without duplicates. For example, `"report": {"path": "/…/skill-sync-reports",
  "allowed_scopes": ["shared-generic"]}`. `report.path` is a plain absolute directory: no vault
  handle, no hub note and no vault write path.
  The registry's declared source `scope` must occur in that list **before capture fetches or
  renders content**. A refusal names only the ref and declared scope. Submitted refactors use
  the configured maintainer identity's scope. Preparation, report rendering and every integration
  authorization recheck the current destination policy, including existing candidates. These are
  operator declarations, not proof of data isolation or authority to admit mixed-trust content.
- Candidate journals are `<store>/candidates/<id>/state.json`, written atomically through a unique
  sibling temp file and `os.replace`. `_store` is attached in memory only and never persisted;
  loaders reject persisted private fields and impossible status/evidence combinations (for example
  `integrated` without a result commit). A transport journal that already has a saved P remains
  readable for recovery after registry removal or identity revocation: loading it is diagnostic,
  never push authorization. Capture/preparation still require the registry, and every absent-P
  retry uses the current registry and refuses revocation with a preserved stale/incident journal.

### Candidate identity

`candidate_id(repo_id, ref, M, T, policy, kind)` is the full sha256 of canonical JSON over the
workflow schema, kind, repository id, source ref, both full commits and the policy version.
Timestamps and local paths are not part of the identity, so identical inputs are the same candidate,
while a different main or source tip requires a new one. Journal loaders recompute the identity and
reject tampered or path-traversing ids.

### Capture

`capture()` fetches **once** (`+refs/heads/*:refs/remotes/<remote>/*`), resolves M and T from the
fetched refs only, and pins both with `git update-ref` under
`refs/hermes-sync/candidates/<id>/main` and `/source`. Remote branch names are never used as
immutable inputs. The operation is idempotent for identical inputs and does not touch the maintainer
clone's HEAD, index or worktree. It refuses a `refactor/*` ref as transport kind: a refactoring
candidate is captured only from its own explicit submission record (see below), and that record —
not the transport registry — is what authorises the journal.

Before creating/reusing a candidate or pinning its inputs, capture calls the existing
`screen_source_history(repo, T, M)` exposure screen over **every commit in `T ^ M`** (transport
and submitted refactor alike). Prohibited paths or credential-pattern hits block with an exposure
incident diagnostic containing paths/categories only, never matched values. An empty final diff
and `files: []` cannot erase exposed history. Integration and absent-P retries run the same screen
again before creating/pushing P; findings preserve a blocked incident journal. This mechanical
history gate is distinct from advisory instance-pointer review and does not rescan rejected
ordinary lessons as a semantic veto. It detects known patterns, not every possible secret; exposure
already in shared transport history requires incident handling, not a latest-tree redaction.

### Preparation

`prepare()` turns a captured journal into a real, uncommitted candidate:

- `git worktree add --detach <store>/worktrees/<id> M`. The directory must not exist. An existing
  directory is accepted only when it is already a maintainer worktree at HEAD=`M` with
  MERGE_HEAD=`T`; anything else is refused for deliberate inspection, and preparation never
  deletes, prunes or force-recreates it. The resolved path is refused if it is equal to or below a
  configured `runtime_roots` entry, the report vault root, or the maintainer checkout.
- Before any merge, changed modes and blob ids are read from `merge-base(M,T)` to both `M` and `T`.
  Regular text `100644`/`100755` and deletions are supported. Symlink `120000`, gitlink `160000`,
  NUL/binary blobs and non-UTF-8 paths block **before** a worktree exists. Every `.gitattributes`
  blob in the merge base, `M` and `T` is inspected: a `merge=<name>` outside Git's builtin driver
  names (`text`, `binary`, `union`, `normal`) blocks the candidate. **Any effective
  `merge.<name>.driver` definition also blocks**, including builtin names and unused or empty
  definitions, from local/global/include configuration: a definition overrides the builtin.
  The same refusal covers
  repo-local/global/include-provided `merge.default`, `.git/info/attributes`, configured
  `core.attributesFile` files and the default user Git attributes file. The default driver is
  checked even with **no `.gitattributes`**. Relative `core.attributesFile` paths fail closed
  because their meaning changes in a candidate worktree. The guard reads configuration and
  attribute bytes only; it never invokes the external driver, and refusal leaves refs/index/tree
  unchanged and creates no candidate checkout.
- Repository-local isolation only: `core.hooksPath` is pointed at a never-created directory under
  `<store>/hooks-disabled/<id>`, `rerere.enabled=false`, and the merge runs with
  `GIT_MERGE_AUTOEDIT=no` and `GIT_ATTR_NOSYSTEM=1` (no system attributes). These settings live in
  the maintainer clone/process, not in the contributor checkout or the user's global config.
- One native `git merge --no-ff --no-commit T`; HEAD stays `M`, `MERGE_HEAD` is exactly `T`. Exit 1
  is accepted only when `git ls-files -u -z` really lists unmerged entries: those paths become
  `conflict_paths` and the journal records `prepared` — a conflict is a review input, not a
  technical failure and never a silent keep-ours. Any other outcome (missing object, bad ref,
  unsupported driver, moved HEAD, lost MERGE_HEAD, exit 1 with no unmerged entries) persists
  `blocked` with `last_error` and raises `WorkflowError`.
- The index is the complete proposed tree. Clean additions, deletions, empty files, renames and
  executable-mode changes are staged by Git itself, not by a text applier. `input_paths` is the
  source review scope: every path `T` changes from the merge base, parsed from NUL-delimited
  `git diff --raw -z` (a rename contributes both paths). `conflict_paths` comes from NUL-delimited
  `git ls-files -u -z`. Re-running `prepare` on the same candidate returns the existing journal
  while the worktree stays consistent; it does not re-merge or discard work.

### Candidate edit scope

The candidate worktree is the only mutable artifact of a candidate, and it is detached from every
branch. The resolving agent may edit files inside it, resolve conflicts explicitly and `git add`
the resolved paths (Git already staged the clean ones). It must not commit, amend, rebase, reset,
push, create or switch branches, or modify the maintainer `main`, the transport checkout, the source
branch or any state outside the candidate journal. It must also not run the candidate's own
unreviewed scripts or commands. The single exception is the changed package's own pytest suite,
run by the fixed validation adapter with a scrubbed environment and timeout (see Checks).
All workflow/tool code, including this core, CLI adapters, library audit, skills-ref validator and
helper imports/scripts, runs from the **configured trusted `maintainer_repo` working tree**, never
from a candidate or `runtime_roots` checkout. A fixed command name is not trust in its candidate
implementation.

### Consumption

`source_status()` is ancestry only: `T` is `consumed` exactly when it is an ancestor of integrated
`main`; otherwise it is `pending`. A same-tree but unacknowledged tip stays pending — there is no
diff-size or empty-diff shortcut. The acknowledgment is the integration merge, not text equality.

### Cooperative transport provenance

`validate_source_history()` runs for transport candidates and refuses:

- a merge in the unpublished `T ^ M` set whose non-first parent is not already an ancestor of
  captured `M` — a transport branch may import only history already integrated on main;
- a transport tip that shares unpublished history with a known remote `refactor/*` branch,
  including a direct fast-forward to an unsubmitted refactor tip.

Diagnostics name refs and commit SHAs, never content. This is an enforceable cooperative DAG rule,
**not a hard security boundary**: a cherry-pick from an unpublished refactor, a deliberately deleted
ref, or a malicious writer rewriting history is outside what ancestry can prove. Scope, provenance
and semantic review remain required; do not describe this check as isolation from a branch name.

### Review evidence (packet 05)

`validate_review()` treats the review as data: object keys are a whitelist, so `command`, `exec`,
`approved` or `confidence` fields are refused rather than ignored. A review binds `candidate_id`,
`M` and `T`, needs a nonempty summary (including `files: []` for an empty-diff acknowledgment) and
must cover exactly `git diff --cached --name-only -z --no-renames M` **UNION** the captured
`input_paths`. A path that is not an input path is allowed only when its reason names that path, so
a deduplication edit to another file stays explainable. Every quote must occur in the named blob at
captured `M`, `T` or a merge base — never at an arbitrary local path. Each file decision needs at
least one anchor; a deletion is anchored at `M` or the merge base, where the removed text exists.
Replacements carry `{old_ref,old_path,old_quote,new_path,new_quote,reason}`: the old quote must
exist at the old ref, the new quote in the final staged result, and the replaced instruction must
not survive in either path.

An advisory scope scanner finds incoming lines that look instance-specific (`/home/<user>/`,
`~/…`, private hostnames, captured timestamps). It is **not a veto**: a generalized instruction
passes, an illustrative path passes when the reason names it, and only a *surviving* line that the
review does not name fails, as an unexplained live instruction. The semantic judgment (useful,
duplicate, illustrative, instance-specific) stays with the reviewing agent.

### Final gate

`validate_tree()` validates the actual index, not the incoming diff and not dirty files: HEAD must
be `M`, `MERGE_HEAD` exactly `T`, no unmerged entries, no unstaged or untracked content,
no `skip-worktree` or `assume-unchanged` index flags (`git ls-files -v -z`),
`git diff --cached --check` must exit 0, and the tree comes from `git write-tree`. Coverage must
equal the staged paths UNION `input_paths`, so a clean addition, a deletion and a deliberately
rejected path cannot disappear from the record. Changed blobs are read from the index: regular text
is required, `.py` must compile in memory and `.json` must parse. The return value is only
`{"tree": …, "paths": […]}` — there is deliberately no `ok`/`passed` flag for a later step to trust.

### Checks

`run_checks()` runs only fixed allowlisted adapters. It derives **every changed package** from
`git diff --cached --name-only -z --no-renames M`, not just the maintenance package or incoming
manifest; agent-added staged packages count too:

- `index-whitespace`: `git diff --cached --check`
- `staged-syntax`: in-memory compile/parse of the staged blobs
- `package-tests:skills/<package>`:
  `sys.executable -I -B -m pytest -p no:cacheprovider -c <check-config>/pytest.ini
  --rootdir=skills/<package> --confcutdir=skills/<package> skills/<package>/tests -q`
  when tests exist (`<check-config>` is a plan-owned temporary directory, not candidate content)
- `package-validator:skills/<package>`: the trusted maintainer's resolved
  `skills/skill-builder/scripts/skills-ref.sh validate <absolute candidate package path>`
- `library-audit`: `sys.executable <absolute trusted maintainer audit-skill-library.py>
  <absolute candidate skills directory> --json`

The maintenance package uses the same fixed test adapter and unchanged/not-applicable rows.
Every other changed package gets explicit test and validator rows, including honest
`not-applicable` when no runner was ever configured. A suite that exists must run; a missing,
dropped or downgraded required row blocks recording/integration. A previously required runner
that disappears is an error. The skills-ref adapter is the configured repository-wide package
validator; no candidate-declared CLI/command fields are discovered or executed. If a tool exists
only in the candidate but not the trusted maintainer, its row is **required/failed** (exit 127),
not omitted or executed from the candidate; CLI recording retains the hard-check exit 10.

Tool commands use absolute resolved maintainer scripts **and cwd=`maintainer_repo`**, so sibling
imports and relative helpers stay on the trusted side; only their input paths point at the
clean bound-tree materialization. Package tests use that materialization as cwd, never the mutable
candidate worktree. It is created under TMPDIR with `TemporaryDirectory` from the bound tree SHA
using `git ls-tree` and raw `git cat-file blob` bytes, without checkout filters or archive
`export-ignore`/`export-subst` transformations. Only regular/executable blobs are supported;
files/directories are read-only (executable bits retained), and no `.git` link is installed.
A full path/byte/mode fingerprint rejects changes to the copy. Cleanup unlocks its directories
and removes it on success, failure or timeout. Trusted tooling paths/cwd remain the maintainer
baseline; validator/audit inputs also point at the clean copy. Index visibility flags are refused
before and after checks and the final tree gate, including recording/integration revalidation.
Evidence uses a stable `<bound-tree>` plan token plus `git-tree-blobs-readonly-v1`, not an
ephemeral directory; older working-tree check plans require a fresh run.
Each subprocess has a fresh temporary HOME, HERMES_HOME, XDG config/cache roots and TMPDIR;
an environment allowlist removes inherited credentials, SSH agents, Python paths, pytest options
and user config. Pytest plugin autoload/user-site are disabled, global/system Git config is not
loaded, and execution is bounded by `CHECK_TIMEOUT` (900 seconds). Candidate tests use only the
system/Python binary PATH; trusted wrappers may use the operator's absolute PATH directories for
dependencies such as uvx, never relative/cwd entries. Dependencies must be installed in those
trusted locations. This is environment/config isolation, **not** an OS filesystem/network sandbox
against malicious test code; run fully hostile suites in a separate OS sandbox as well.

Rows are `{name, required, status, exit_code, stdout, stderr}` with `status` in
`passed|failed|not-applicable`; there is no green flag. The pytest interpreter's `-I` prevents
candidate cwd modules (`pytest.py`, `pytest/`, `_pytest/`, `sitecustomize.py`, `usercustomize.py`)
from replacing its installed trusted runner during startup, ignores `PYTHON*` environment variables
and excludes user-site packages. Pytest's normal test/rootdir prepend imports still load candidate
modules as the code under test; the bound-tree cwd does not change. Use explicit `-B` because `-I`
ignores `PYTHONDONTWRITEBYTECODE`; that environment setting remains for other Python tools.
Together with `-p no:cacheprovider` this keeps the copy bytecode/cache-free, and a fingerprint
change after the run invalidates the whole result. Checks never run review fields, report text or
a package's unreviewed CLI. Regress runner shadowing with a genuinely failing suite: require a
failed check, no shadow output, refused recording/integration and unchanged remote main; a separate
clean-candidate control must show real pytest's passed count and preserve candidate imports.

`--confcutdir=skills/<package>` excludes repository-root and other ancestor `conftest.py`
files entirely; the package's own `conftest.py` and descendants still apply (including fixtures),
subject to the runner-control preflight below.
`--rootdir=skills/<package>` fixes the collection root without changing the explicit `tests`
selection or the bound-tree cwd. `-c` selects a separately written read-only `pytest.ini` whose
exact contents are `[pytest]` followed by a newline; its temporary directory is fingerprinted
and removed on success, failure or timeout. Candidate-root **and package-owned** `pytest.ini`,
`setup.cfg`, `tox.ini` and `pyproject.toml` are not loaded: their `addopts`, `testpaths`, `pythonpath`,
plugin declarations and other pytest settings cannot alter the required gate. This deliberately
breaks suites dependent on automatic package configuration; they fail closed, rather than
silently skipping tests. Package-owned conftest fixtures remain supported and must have a real
passed-count/integration control. Shared/root hooks or extra configuration need an explicit
trusted-tool policy change; do not restore candidate autodiscovery to fix a compatibility error.
Regress root command-main takeover, session-exit rewriting, ignored/deselected failures and each
candidate config format with a genuinely failing test plus a passing control: the required row
must retain the real failure, recording/integration must refuse, and remote main must not move.
A marker-only command-main response is not a test report; `1 failed` must never become a green row.
Do not substitute stdout grepping for this discovery/configuration boundary.

Before executing any check process, `run_checks()` parses **every `conftest.py` under each
changed package in the bound tree** with Python's AST, including unchanged conftests, descendants
outside `tests/`, and packages with no configured suite. The same shared binding collector refuses
all syntactically named module-level `pytest_*` bindings (in particular `pytest_plugins` plugin
injection) **and the reserved module attribute hooks `__getattr__`, `__getattribute__` and `__dir__`**,
regardless of binding form:

- `import` / `from ... import` names and `as` aliases (`import a.b` binds `a`, not `b`);
- plain, annotated, augmented, chained and tuple/list/starred-unpacked assignments;
- `for` / `async for` targets and `with` / `async with` `as` targets, including unpacking;
- exception-handler `as` targets and assignment expressions (`:=`, including comprehension walruses);
- function/async-function and class definitions, plus structural-pattern captures (`match` names,
  starred captures and mapping-rest names).

Declarations inside module-level control flow still count. Definition-time decorators, defaults,
annotations and class bases are inspected in their enclosing scope. The module-scope walk does not
enter function/lambda bodies or class-local namespaces, **except that a separate whole-tree scan
refuses every `global` declaration naming `pytest_*`, `__getattr__`, `__getattribute__` or `__dir__`
in any scope**, including uncalled functions, class bodies and arbitrarily nested scopes. Ordinary
globals outside those reserved names remain allowed. A class-local `__getattr__` method without a
`global` declaration remains an ordinary class API; function-local dunder names remain allowed too.
Comprehension iteration targets are local, unlike walruses that bind in the enclosing module.
Ordinary helpers, nested local names such as `def helper(): def pytest_fake(): ...`, comments and
strings are not runner hooks. `@pytest.fixture` functions remain fully supported.

The v4 preflight also **refuses by policy**, without evaluating arguments or attempting dynamic-code
analysis:

- **every module-level wildcard import** (`from x import *`, including relative imports and
  module-level control flow), even a benign export set: the resulting namespace is statically
  unknowable, so the policy fails closed;
- module-level calls spelled `exec`, `eval`, `compile`, `globals`, `locals`, `setattr` or `__import__`,
  including attribute-qualified calls with those terminal names (for example `builtins.exec`);
- module-level references to `sys.modules` or `__builtins__`, including bare references, subscript
  access and attribute/method chains such as `sys.modules[__name__].__setattr__(...)` and
  `__builtins__['__import__']`.

The reserved module attribute hooks are covered by the binding/global rules above, not a separate
definition-only check: plain lambda assignments, import aliases, walruses, loop/context-manager
targets and pattern captures count just like `def`/`async def`. They are refused conservatively
because module attribute hooks can synthesise or advertise `pytest_*` attributes while the
syntactically named namespace appears clean.

Conditional code and enclosing-scope defaults/decorators remain subject to these rules. The scan
for `global` declarations of `pytest_*` or the three reserved module attribute-hook names alone
crosses all local scopes; the other rules do not inspect helper bodies
or resolve aliases. Refusing even benign syntax is intentional: these routes could fabricate
runner-control names at runtime. A refusal names the path and offending binding(s), declaration(s),
wildcard import(s), call(s), reference(s) or attribute hook(s), for example:

```text
candidate conftest runner control is not allowed: skills/demo/conftest.py: module-level wildcard imports refused by policy: from helper import *; fixtures and ordinary helpers are allowed, but runner-control bindings, declarations and dynamic routes are not
```

This preflight invalidates an earlier run before inspecting the tree and writes no green evidence
on refusal. Regress package `pytest_sessionfinish` exit rewriting, `pytest_cmdline_main` takeover,
`pytest_collection_modifyitems` skipping a genuine failure, `pytest_plugins` injection, every
binding form above for both `pytest_*` and the reserved module attribute hooks, wildcard imports,
reserved-name `global` declarations in class/function/nested scopes, each of the seven refused
calls, and `sys.modules`/`__builtins__` references with
genuinely failing artifacts, zero check-process calls before refusal, no check evidence,
integration-negative controls and remote-main read-back. Keep separate successful integration
controls for fixture-only conftests, nested function-local dunder names, class-local `__getattr__`
methods without `global`, ordinary globals outside the reserved names and clean candidate imports.

**Cooperative limit:** the preflight covers the listed syntactic bindings, wildcard imports,
reserved-name `global` declarations, dynamic-call/reference spellings and module attribute-hook
bindings, not arbitrary Python execution. Everything still evading these rules by indirection,
including import hooks, metaclass tricks, callable/module aliases and third-party plugin side
effects, remains outside the cooperative boundary. Containing such runner subversion requires
OS-level isolation, which this change does not provide.

`record_review()` reloads the journal and config, re-validates the review and the staged tree,
requires every required row to be `passed`, refuses a dropped, renamed or downgraded row, and
persists `review.json`, `checks.json`, the review digest, `checks_digest` and `reviewed_tree`
before advancing to `reviewed`. `run_checks` still returns the list of rows, but also atomically
persists authoritative `checks-run.json` under the candidate directory:

```json
{"schema": 1, "candidate_id": "<cid>", "tree": "<tested Git tree SHA>",
 "plan": ["<fixed adapter records: exact argv or builtin identity, selection and required flags>"],
 "checks": ["<exact returned rows, including stdout/stderr/exit codes>"], "digest": "<sha256>"}
```

`digest` is SHA-256 of canonical JSON over **all other fields** (`sort_keys=True`, compact
separators, UTF-8), including the exact pytest argv: interpreter path, `-I`, `-B`, `-m pytest`,
cache-provider option, `-c <check-config>/pytest.ini`, package rootdir/confcutdir, suite path and `-q`.
The plan binds the literal minimal config bytes in `pytest_config` and the versioned AST preflight
identity `conftest_policy: "ast-no-module-pytest-bindings-v4"` in every package-test row. Bump that
identity whenever this policy changes; v3 (and earlier) evidence is invalid for v4 recording and
integration. `<check-config>` is a stable evidence token for the
separately generated file, just as `<bound-tree>` stands for materialization. Changing any of
those controls changes the plan/digest; old evidence with a missing or different conftest policy
requires fresh checks, even for the same tree. Recording and integration compare the saved plan
against the current policy, not just its internally consistent digest.
A new run invalidates the previous run file before executing. Recording
requires the caller's rows to equal that authoritative run, its tree to equal the current final
index and its plan to equal the currently selected fixed plan; recomputing `validate_tree` alone
cannot re-authorize stale green checks. Recording copies that exact binding to `checks.json` and
pins its digest in the journal's `checks_digest`. Integration and absent-P retries verify the
binding again against `reviewed_tree`, the journal digest and the current candidate; no old green
flag or caller-supplied rows bypass it. Older unpublished journals without bindings need new checks
and review/report evidence, not a fabricated migration digest. Candidate journals remain trusted
local state; the digest is integrity evidence, not authentication against a writer who controls the
entire store.

### Report binding

`render_review()` is deterministic: the timestamp is the captured `created_at`, never the wall
clock, and the same candidate/review/checks/tree always render the same bytes. It writes
`review.md` under the candidate store only. The live note is written by the agent as a plain file
under `report.path`; `verify_report()` then reloads journal, config and stored payload, compares
the exact bytes at `<report.path>/skill-sync-<cid>-review.md`, and refuses a
missing, altered, symlinked or escaping file. Only an exact match advances to `report-verified`,
recording the SHA-256 of the approved bytes. The template is
`assets/skill-sync-report.md.example`.

### Report folder, note metadata and feedback

The report destination is deployment data: one plain absolute directory in `report.path`. Nothing
vault-specific is involved — the agent writes the rendered bytes as a regular file and reads them
back. The directory may live inside a vault (`…/projects/<project>/skill-sync-reports`); that only
means Obsidian indexes the notes, and no hub note or MoC link is required.

Every per-candidate note is a plain Markdown note: `type: zettel`, a one-sentence description, the
`skill-sync` tag plus — when the configured path contains `/projects/<name>/` — the project tag.
There is no `topics` block and no hub link. The rendered payload carries those fields;
the created/updated timestamps come from the captured/observed clock values in the candidate, never
from a later re-render, so exact re-delivery stays byte-identical. The review note is immutable
evidence of M, T, decisions, checks and tree. Integration outcome goes only to the separate result
note (`skill-sync-<cid>-result.md`); never edit the review to add an outcome and never backfill a
receipt into it.

**Feedback is optional and current-state based.** The user may refer to an older report in a normal
chat. The agent reads that report *and* the current skill, asks only when the correction is
ambiguous, and records its interpretation in a **new feedback note or a result-linked correction
report**. It then creates a normal corrective candidate against the current skill state through the
usual capture/prepare/review flow, preserving every unrelated later change. Never a blind
`git revert` of an older merge: later work sits on top of it, and a revert would delete that work.
There is no approve CLI and no human backlog requirement; silence is not approval.

### Integration

`integrate(repo, store, cid, report_root)` acquires the maintainer lock **once** for the whole public
call and releases it with its owner token in `finally`; shared internals never re-acquire it. It
then re-reads the journal, stored review, checks and report and revalidates all of them: review
digest, exact check rows, the staged tree (HEAD must still be `M`, `MERGE_HEAD` exactly `T`, index
clean) and the exact report bytes at the configured report root. A previous green result is never a
bypass, and the source must still be registered and enabled.

Remote `main` must still be the captured `M`. A source that advanced to a descendant `T2` is fine —
the candidate still integrates `T` only, and `T2` stays untouched and pending. A source that was
rewritten so `T` is no longer an ancestor of the remote tip blocks the candidate: recapture instead
of integrating replaced history. A main that moved marks the candidate `stale` before anything is
created or pushed; this path contains no force, reset or rebase.

The integration commit is formed once with `git commit-tree <reviewed_tree> -p M -p T`: ordered
parents, no second merge, no hooks, and an author/committer identity supplied through
`GIT_AUTHOR_*`/`GIT_COMMITTER_*` in the process environment (Git config is never written). The
message is `maintainer: …` plus the trailers `Skill-Sync-Candidate`, `Source-Ref`, `Source-Tip`,
`Review-Digest` and `Reviewed-Tree`; parents, tree and trailers are verified immediately. `P` is
pinned at `refs/hermes-sync/candidates/<cid>/result`, then the journal writes `integrate-intent` with
`result_sha`, `result_parents`, `result_tree` and the report hash **before** the push.

`git push --no-verify origin <P>:refs/heads/main` has no force. Success is never inferred from the
command: the exact `refs/heads/main` is read with `git ls-remote --refs`, and only that observation
(or a fetched later main that contains `P`) may write `integrated` plus `integrated_main`. A rejected
push whose remote main is still `M` keeps `integrate-intent` for reconcile; a rejected push whose
remote main moved marks the candidate `stale` and keeps the racing commit and `P` as evidence.
Transport refs are never reset, so `T2` remains exactly where the contributor left it.

Reject-only reviews integrate a real merge whose tree equals `M`'s tree with parents `M,T`; an
empty-diff acknowledgment works the same way. Both make the source tip `consumed` by ancestry,
never by a diff-size shortcut, and their report keeps the reason and the quoted source text.

`render_result(candidate)` re-reads the journal, verifies the saved `P` (parents, tree, trailers)
and writes a deterministic `result.md` under the candidate store; it refuses to render before
integration was observed. The payload's timestamp is the journal's `result_observed_at`, fixed the
first time integration was observed, and it states the integration outcome only — never its own
delivery status — so re-rendering after a clock change is byte-identical and a receipt delivered
once still matches after the receipt moves from `integrated` to `receipt-pending` to `complete`.

`verify_result(store, cid, report_root)` is the separate receipt step. It reloads the journal and
config, refuses a `report_root` that is not the configured `report.path`, re-verifies the
saved `P`, re-observes the immutable review at the **currently configured** destination against
the stored `review.md` bytes and recorded SHA-256 on every call (including calls on `complete`),
and then compares
`<report.path>/skill-sync-<cid>-result.md` byte for byte. Missing,
changed, symlinked or escaping receipts are refused and stay `receipt-pending`; an exact match
records `complete` with `receipt_sha256` (the SHA-256 of the delivered bytes) and
`receipt_verified_at`. `complete` without a recorded receipt digest is rejected by the journal
loader, and only an observed integration (`integrated`/`receipt-pending`/`complete`) has a receipt
to verify at all. A missing, changed, symlinked or relocated review, or an altered stored review
payload, persists a sticky `incident`, refuses completion and leaves `receipt-pending` with cleared
receipt verification fields. Restoring bytes alone never clears an incident. Python never writes the live receipt note: it
renders the payload and the agent delivers it, exactly like the review note it must never modify.

### Contributor lock, history review and exact-tip integration (packet 09)

The contributor engine (`scripts/skill-repo-sync.py`) owns short, serialised operations. They
share one lock at the **contributor repository's Git common dir** —
`<contributor git-common-dir>/hermes-sync/contributor.lock` — which is a different file from the
maintainer lock even when both repos live on the same host. It is an owner-token
`O_CREAT|O_EXCL` record with pid/host/acquisition time, no TTL and no age heuristic. Every linked
worktree of that checkout contends on it. It is held only for a staging commit, a session-start
refresh, a pre-integration review/push, or an explicit `--lock`/`--unlock` pair around a deliberate
merge — never for a whole chat session.

- `--stage` acquires it around the index/commit/state writes. A pre-integration merge or push
  holding the lock refuses staging with exit 12 **before** any index, worktree or state byte
  changes, and the same holds in reverse for `--push-reviewed`.
- `--sync-from-main` takes the same contributor lock before preflight/fetch/merge; a held lock
  refuses with exit 12 and names the lock path, without changing HEAD, files, index or fetch state.
  Every `main` checkout refuses with a branch-policy diagnostic (exit 12, clean or dirty), just
  like `--stage`. Dry-run is read-only and creates no lock. Clean transport checkout:
  fast-forward when `HEAD` is an ancestor of `origin/main` (integrated main is newer); no-op when
  main is an ancestor of `HEAD`; on divergence it prints
  `pre-integration merge required` and changes no file or index (exit 12 so the session hook
  reports it). Dirty worktrees are never integrated, an in-progress merge/rebase is refused, and
  there is no reset, rebase or autostash path left. There is also no automatic resume-triggered
  LLM: the daily schedule or an explicit pre-integration run is the only follow-up.
- Before a source snapshot is shared, `screen_source_history()` walks the **entire** unpublished
  range `git rev-list <T> ^<last verified remote source tip>` and inspects every commit's changed
  paths and added lines. Diagnostics are path + category only (`forbidden-path` with a reason such
  as `environment file`; `credential-pattern`); the matched value, line or blob is never printed or
  persisted. This deliberately catches content an intermediate commit added and a later commit
  deleted — a clean final tree is not permission to integrate that history. Already-pushed exposure
  is a separate incident and is never repaired by force or by redacting the latest tree.
- Semantic profile-scope review remains agent work. `--record-history-review <T> --history-review
  <file>` validates the agent's JSON against the exact tip and the exact commit set, then persists
  `history_reviews[<abs repo path>]`:

  ```json
  {"schema": 1, "tip": "<full T>", "base_tip": "<verified remote tip or ''>",
   "scope": "shared-generic", "summary": "…",
   "commits": [{"sha": "<full>", "classification": "generic-only|no-profile-content|profile-content-removed", "reason": "…"}],
   "digest": "<sha256 of schema/tip/scope/commits>",
   "findings": [{"commit": "…", "path": "…", "category": "…", "reason": "…"}],
   "reviewed_at": "…"}
  ```

  The digest binds the review to T and its commit rows; timestamps and the mechanical findings are
  not part of it, so a re-run after a clock change stays stable.
- `--push-reviewed <T>` takes the contributor lock, re-runs the mechanical screen, requires the
  matching, untampered history review (and coverage of the current unpublished range), requires T
  to be `HEAD` or an ancestor of `HEAD`, pushes `T:refs/heads/machine/<name>` — **not** the branch
  name — and then reads the exact source ref back with a checked `ls-remote`. Only that observation
  records `last_pushed_tip`/`last_pushed_ref`/`last_pushed_at`; the field is metadata and never
  authorises a reset or a shortened review. A sweep commit made after the review (T2) is not
  integrated by pushing T, and `--push-reviewed T2` refuses until T2 has its own review. The remote
  ref must fast-forward from its observed tip; a rewritten remote is refused, never forced.


`reconcile(repo, store, cid)` — and a repeat `integrate` on `integrate-intent`, `integrated`,
`receipt-pending` or `complete` — performs only reconciliation: verify the saved `P`, fetch, and
record integration when the remote main contains it. If remote main is still `M`, the **same**
saved `P` may be retried under the lock **only after the same pre-push authorization as integrate**:
current enabled source authorization (or exact refactor submission), stored review digest, bound
check evidence, clean reviewed tree, immutable report bytes at the configured destination and
fresh remote M/T ancestry. Any mismatch refuses the push and preserves P in a stale/incident
journal; repairing a report alone does not silently re-approve it. When fetched main already
contains P, reconciliation repairs integration/receipt state only and never pushes, even if the
source has since been disabled or the review note was altered (the latter remains an incident).
A previously observed integration missing from remote main is an incident, never reintegrated.
No path creates a second integration commit, so a crash after a successful push repairs state instead of re-merging.

### Integration outcomes and diagnostics

Every outcome is a journal field, not an inference from a command's exit text. A caller never has
to guess which case it is in: the persisted `last_error` (or `incident`) carries the same
diagnostic the raised `WorkflowError` reports.

| Observed situation | `status` | Observable evidence | Recovery |
|---|---|---|---|
| Push rejected or transport broken, remote `main` still `M` | `integrate-intent` | `result_sha`/`result_parents`/`result_tree` saved, `integrated_main` empty, pin `refs/hermes-sync/candidates/<cid>/result` = `P`, `last_error` ends `integrate-intent retained for reconcile` | `reconcile` re-authorizes all evidence before retrying the **same** `P` under the lock |
| Push returned, `git ls-remote` unreadable | `integrate-intent` | `last_error` = `saved result <P> could not be confirmed on <remote>: …; integrate-intent retained for reconcile`; the ref may already be `P` | `reconcile` reads the remote again and proves `P` by ancestry |
| `P` is on `main` (possibly with a later main containing it) | `integrated` | `integrated_main` = exact observed SHA, `result_observed_at` fixed, `last_error` empty | deliver the receipt |
| Receipt missing, changed, symlinked or outside the configured root | `receipt-pending` | `receipt_attempts` incremented, `last_error` names the file and the observed SHA-256 | re-deliver the exact bytes from `<store>/candidates/<cid>/result.md` |
| Receipt matches exactly | `complete` | `receipt_sha256` = SHA-256 of the delivered bytes, `receipt_verified_at` set | none |
| Review note altered or missing after `P` reached `main` | `integrated`/`receipt-pending` + `incident` | `incident` names the note and both digests, `last_error` repeats it; sticky once recorded | resolve the discrepancy deliberately; integration is never undone, never reintegrated and the note is never rewritten |
| Remote `main` moved and does not contain `P` | `stale` | `last_error` names the captured and observed main | capture and review against the new `main` |
| Source ref rewritten or deleted | `blocked` | `last_error` names the captured tip and the remote tip | recapture instead of integrating replaced history |

"Already integrated" is not an error path: a repeat `integrate`/`reconcile` on `integrated`,
`receipt-pending` or `complete` returns the saved `P` and performs no `commit-tree`, `push` or
`update-ref`. `verify_result` on a `integrate-intent` candidate is refused — an uncertain outcome has
nothing to receipt. An incident recorded in the journal blocks `complete`, so a receipt can never
claim a clean delivery over a tampered report.

### Implemented core API (packets 03-09)

```text
WorkflowError(RuntimeError)
canonical_bytes(value: dict) -> bytes
candidate_id(repo_id, ref, main, tip, policy, kind) -> str   # 64 hex
atomic_json(path: Path, value: dict) -> None
read_json(path: Path) -> dict
safe_relative(root: Path, relative: str) -> Path
git(repo: Path, *args, check=False, input_text=None, timeout=120, extra_env=None) -> CompletedProcess
git_bytes(repo: Path, *args, timeout=120, extra_env=None) -> CompletedProcess   # bytes
is_ancestor(repo: Path, older: str, newer: str) -> bool
source_status(repo: Path, main: str, tip: str) -> str           # consumed | pending
load_maintainer_config(store: Path) -> dict
load_candidate(store: Path, cid: str) -> dict                   # in-memory `_store`
capture(repo: Path, store: Path, source: dict, kind="transport") -> dict
prepare(repo: Path, store: Path, candidate: dict) -> dict       # worktree + staged merge
validate_source_history(repo: Path, main, tip, known_refactors) -> None
validate_review(candidate, review, repo, worktree) -> None
validate_tree(candidate, worktree, review) -> {"tree": str, "paths": list[str]}
run_checks(candidate, worktree) -> list[dict]                   # no success flag
record_review(store, cid, review, checks, validation) -> dict   # status reviewed
render_review(candidate, review, checks, tree) -> str           # store payload only
verify_report(candidate, expected_text, report_root) -> dict    # status report-verified
integrate(repo, store, cid, report_root) -> dict    # exact merge P, non-force push, observed main
reconcile(repo, store, cid) -> dict               # saved P only; never a second integration
render_result(candidate) -> str                   # deterministic result.md under the store
verify_result(store, cid, report_root) -> dict    # exact receipt read-back -> complete
git_common_dir(repo) -> Path                      # lock scope, linked worktrees included
contributor_lock_path(repo) -> Path                  # <contributor common dir>/hermes-sync/contributor.lock
read_contributor_lock(repo) -> dict | None
acquire_contributor_lock(repo) -> str                # owner token; no TTL, no age break
release_contributor_lock(repo, token) -> None
submit_refactor(repo, store, ref, tip, brief) -> dict   # exact-tip authorisation, pinned T
refactor_submissions(store) -> list[dict]         # validated records for this maintainer
validate_refactor_brief(brief) -> dict            # {summary, intended_replacements, validation_notes}
pending_lines(repo, store, sources=None, *, fetch=True) -> list[str]  # stable monitor protocol
retry_candidate(store, cid) -> dict               # one explicit blocked -> captured step
screen_source_history(repo, tip, base_tip=None) -> {tip, base_tip, commits, findings}
history_review_digest(payload) -> str             # binds tip + scope + commit rows
next_skill(skills: Iterable[str], last: str | None) -> str | None  # periodic review cursor
```

`submit_refactor` accepts only `refs/heads/refactor/<slug>`, a full SHA that is exactly the fetched
remote tip, and a brief whose only keys are `summary`, `intended_replacements`
(`path`, `old_quote`, `new_instruction`, `reason`) and `validation_notes`; there is no command
field. Identity and scope come from `maintainer_identity`, never from the caller, and the tip is
pinned immediately. Captured main must be an ancestor of the tip. The submission record lives at
`<store>/refactor-submissions/<cid>.json`; a refactor journal is loadable only while that record
matches its ref, main, tip, policy and identity. Transport candidates still require the configured
source registry — a submission record never authorises transport.

`integrate`/`reconcile` render the receipt payload but never claim it was delivered; only
`verify_result` may record `complete`.

## Platforms

Written for Linux and macOS alike — an installation may be either, and the two home layouts differ.

- Nothing is hardcoded: the Hermes home comes from `$HERMES_HOME` (falling back to `~/.hermes`),
  repositories are resolved with `git rev-parse --show-toplevel`, and every absolute path is
  recorded per machine in the state file.
- The gate's instance-pointer patterns cover `/home/<user>` **and** `/Users/<user>`, so a rule that
  leaks a local path is caught whichever installation writes it. A `~/` path is flagged only
  outside the portable runtime directories (`~/.local`, `~/.cache`, `~/.config`, `~/.hermes`): those
  resolve on every installation, so a model cache under `~/.local/share` is not an instance pointer.
- Both hook events and the cron jobs are Hermes-level features — nothing goes into `crontab` or
  `launchd`.
- The wrapper execs `python3` from `PATH`; a missing one falls back to the interpreter that ran the
  installer, and `--python` pins an explicit binary. Relevant on macOS: without the Xcode command
  line tools there is no `python3`, and a Homebrew python may sit outside the PATH a hook inherits.
- Every git call runs with `GIT_TERMINAL_PROMPT=0` and `GIT_SSH_COMMAND=ssh -oBatchMode=yes`, so an
  unattended hook fails fast instead of stalling on a credential or key-passphrase prompt.
- Paths are used exactly as git reports them — no case assumptions, which matters on a
  case-insensitive APFS volume.

## Files

| Path | Role |
|---|---|
| `scripts/skill-repo-sync.py` | the contributor engine (staging, ancestry refresh, history screen, exact reviewed-tip push, contributor lock); `SCRIPT_VERSION` in the header |
| `scripts/install-skill-repo-sync.py` | installer; copies the engine + shared core + report template into `<hermes home>/bin`, then writes the wrapper/state; `INSTALLER_VERSION` must match the engine |
| `scripts/skill-repo-maintain.py` | the maintainer helper: `--capture-source`, `--prepare`, `--record-review`, `--render-report`, `--verify-report`, `--integrate`, `--reconcile`, `--render-result`, `--verify-result`, `--pending`, `--retry`, `--selfcheck`, `--render-artifacts`, `--lock`/`--unlock`, `--note-pushed` (metadata only); retired (exit 12, `retired:` diagnostic): `--collect`, `--preflight`, `--merge-map`, `--apply-decisions`, `--refresh-strip`, `--reset-branch`, `--init-last-pushed` |
| `scripts/skill_repo_workflow.py` | shared v3 core (a library, not a CLI): candidate identity, strict maintainer state, fetched capture with local pins, ancestry-only consumption, cooperative transport provenance guard, the whole-unpublished-history exposure screen, review/tree/checks/report gates, exact merge integration/reconcile, the stable pending protocol and the two owner-token locks (maintainer at the clone's Git common dir, contributor at the contributor repo's Git common dir; atomic `O_CREAT`/`O_EXCL`, no TTL); imported by the adapters above |
| `<hermes home>/bin/skill-repo-sync` | stable wrapper the hooks/crons call; execs the installed engine pair |
| `<hermes home>/bin/skill-repo-sync.py` + `skill_repo_workflow.py` | installed engine + core (identical versions; the installer refuses a partial pair) |
| `<hermes home>/scripts/skill-repo-sync-stage.sh` | generated staging shim for the hourly `no_agent` job, rendered from `../assets/stage-sweep-script.sh.example` |
| `<hermes home>/scripts/skill-repo-maintain-monitor.sh` | generated monitor shim for the maintainer job's `--monitor-script` gate (prints `--pending --store … --repo …`), rendered from `../assets/maintain-monitor-script.sh.example` |
| `<hermes home>/skill-repo-sync.json` | state: repos, wrapper, engine path, ledger cursor, versions |
| `<hermes home>/skills/.curator_ledger.jsonl` | mutation ledger (written by Hermes, read here) |

The wrapper path must stay constant: the hook consent pair is `(event, command)`, so changing the
command needs fresh consent. The wrapper execs the **installed** engine pair under
`<hermes home>/bin`; update the repository and re-run the installer to refresh that pair, then
verify `--version` — never point the wrapper back at a checkout whose branch can change.

Deployment artifacts are rendered, not hand-written: `--render-artifacts` rebuilds the two cron
prompts and the two shims from `assets/*.example`, writes them, and records `asset`/`rendered`
SHA-256 pairs in `<store>/rendered.json`. `--selfcheck` compares both and reports
`artifacts_out_of_date` when an asset changed or a target drifted, so an asset edit cannot leave a
stale prompt running. Code changes need no such step: the wrapper and the maintainer prompt execute
the checkout/clone directly.

The wrapper, the staging shim and the monitor shim are the **only generated artifacts** of this
sync, and each exists for exactly one stable path: hook consent binds to the wrapper's
`(event, command)` pair, and `hermes cron create --script` / `--monitor-script` resolve scripts
under `<hermes home>/scripts/`. The installed engine pair is the one deliberate copy: the engine
refuses to operate with a missing or mixed-version `skill_repo_workflow.py`; `--selfcheck` also
returns 12 for a mixed pair. The installer stages and verifies both (same version), snapshots
every prior target, and restores the old bytes and modes if any replacement raises, including
interruption. Fresh-install rollback removes the new targets; the report template participates
in the same rollback. This is exception rollback, not crash-atomic replacement of multiple files.
If restoration itself fails, the diagnostic names retained recovery files; do not discard them.
The maintainer helper is called directly
from the repository tree (`python3 {skills_repo}/skills/skill-library-maintenance/scripts/skill-repo-maintain.py …`);
it imports the engine beside itself (`_engine_candidates`) and the shared core beside both, so
there is no `SKILL_REPO_SYNC_ENGINE` export.

## Modes

```bash
python3 scripts/install-skill-repo-sync.py --version  # installer version, no installation context or writes
python3 scripts/skill-repo-sync.py --version          # engine version
python3 scripts/skill-repo-sync.py --selfcheck        # install state, repos, engine/core/installer versions, branch policy, maintainer config/report root, contributor lock, ledger cursor
python3 scripts/skill-repo-sync.py --stage            # hourly sweep: ledger paths + dirty worktree → one LOCAL commit on machine/<name> (push = pre-integration); refactor/* excluded, main refused (exit 12); holds the contributor lock
python3 scripts/skill-repo-sync.py --sync-from-main   # on_session_start: fetch; fast-forward when HEAD is an ancestor of origin/main (integrated main is newer), no-op when main is an ancestor of HEAD, "pre-integration merge required" on divergence (never reset/rebase)
python3 scripts/skill-repo-sync.py --screen-history <SHA>   # mechanical screen of the whole unpublished range (path/category only, exit 10 on findings)
python3 scripts/skill-repo-sync.py --record-history-review <SHA> --history-review <file>  # persist the agent's profile-scope review bound to exactly SHA
python3 scripts/skill-repo-sync.py --push-reviewed <SHA>    # integrate exactly that reviewed commit to machine/<name>, verify ls-remote, record last_pushed_tip
python3 scripts/skill-repo-sync.py --lock / --unlock  # hold/release the contributor lock across a deliberate pre-integration merge

HELPER="python3 {skills_repo}/skills/skill-library-maintenance/scripts/skill-repo-maintain.py"
$HELPER --capture-source refs/heads/machine/<host> --store {store} --repo {maintainer_repo}
$HELPER --prepare <cid> --store {store} --repo {maintainer_repo}
$HELPER --record-review <cid> --review-file <path> --store {store} --repo {maintainer_repo}
$HELPER --render-report <cid> --store {store} --repo {maintainer_repo}
$HELPER --verify-report <cid> --store {store} --repo {maintainer_repo}
$HELPER --integrate <cid> --store {store} --repo {maintainer_repo}
$HELPER --reconcile <cid> --store {store} --repo {maintainer_repo}
$HELPER --render-result <cid> --store {store} --repo {maintainer_repo}
$HELPER --verify-result <cid> --store {store} --repo {maintainer_repo}
$HELPER --pending --store {store} --repo {maintainer_repo}   # monitor: sorted `pending <cid>` / `blocked <cid>` plus `recover <cid>` / `incident <cid>` journal lines; technical failure = stdout `error: monitor-unhealthy` + stderr diagnostic
$HELPER --retry <cid> --store {store} --repo {maintainer_repo}  # one explicit retry generation (blocked only)
$HELPER --selfcheck --store {store} --repo {maintainer_repo}    # observed versions/config/report/lock facts only
$HELPER --lock / --unlock --store {store} --repo {maintainer_repo}
$HELPER --note-pushed --repo {maintainer_repo}   # legacy metadata: records HEAD only when the remote transport tip equals HEAD
$HELPER --collect | --preflight | --merge-map | --apply-decisions  # RETIRED: exit 12 with `retired:` — v3 uses capture/prepare/review/report
$HELPER --refresh-strip | --reset-branch | --init-last-pushed      # RETIRED: exit 12 with `retired:`
```

Both scripts accept `--dry-run` (no state, index, commit, fetch, push or lock-file writes) and
`--verbose`. Every action mode prints machine-readable JSON on stdout and diagnostics on stderr;
`--pending` uses only the stable line protocol. Exit codes pinned by tests: `0` ok/no-op,
`10` required checks failed, `12` policy refusal or error (wrong branch incl. clean `main`, dirty
index, whitespace/commit failure, divergence needing a pre-integration merge, held contributor
lock, missing history review, repo/store disagreement, a retired mode — `--dry-run` does not
soften a refusal), `13` not installed or missing maintainer config, `2` argparse usage. Retired
modes fail closed: they exit `12` before any Git call and print a `retired:` line naming the
replacement, so an old cron prompt fails visibly instead of writing.

## Install (once per machine)

Treat installation as a separate approval from fetching, merging, or reviewing the repository.
First pass the disposable-repository acceptance checks in `repository-sync-safety.md` against
this revision. Inspect installer configuration writes before running it; do not enable global
hook auto-accept merely to approve this automation. Resolve historical-ledger bootstrap explicitly
so first activation cannot sweep old or mixed manual edits by surprise.

```bash
cd <repo>/skills/skill-library-maintenance/scripts
python3 install-skill-repo-sync.py --bootstrap-current-ledger --apply-config
hermes hooks list
hermes hooks doctor
<hermes home>/bin/skill-repo-sync --selfcheck --verbose
python3 -m pytest ../tests -q
```

The installer stages `skill-repo-sync.py` and its core `skill_repo_workflow.py` (plus the report
template) into `<hermes home>/bin`, verifies both exist and report the same version, and refuses
a partial pair before writing the wrapper or state. It never chmods or rewrites the repository
checkout.

For a fresh install, `--bootstrap-current-ledger` explicitly places the cursor at the current
ledger end; it skips historical entries rather than transporting them. On an existing install,
omit this flag so the saved cursor is preserved.

`--apply-config` writes only the `on_session_start` hook entry through `hermes config set`; it
never changes `hooks_auto_accept`, and an existing `on_skill_lifecycle` entry — v1 or otherwise —
is preserved untouched, not emptied or deleted. Approve the exact `(event, command)` pair through
Hermes' normal consent flow. For headless setup, use a verified exact-pair allowlist; do not enable
global auto-accept. Additional shared repos: repeat `--repo /path/to/other/repo`.

After consent, rerun `hermes hooks list`, `hermes hooks doctor`, and the engine's
`--selfcheck --verbose`; report automation active only when the pair is allowlisted and the checks
pass. A configured but not allowlisted hook is installed, not activated. If consent remains
pending, report that boundary and leave activation unverified; do not present a blocked selfcheck
as a passed check. In the handoff, separate repository state (exact remote SHA), installation
(wrapper, state, configuration), and activation (consent and health). Cite test results only for
the inspected revision; rerun affected checks after later edits before carrying their results into
the final handoff.

The installer rewrites the wrapper only when its content actually changes: the hook consent records
the script's mtime, so a needless rewrite would show up in `hermes hooks doctor` as "script modified
since approval". If the wrapper *is* rewritten, refresh the consent —
`hermes hooks revoke <wrapper>` and approve again on the next start — and re-run `doctor` until it
reports all hooks healthy.

The engine is stdlib-only Python 3.9+; the wrapper defaults to `python3` (pin a different
interpreter with `--python`).

## Crons

1. **Hourly staging sweep** — every machine, script-only, quiet on success:

   ```text
   every hour · no_agent: true · script: skill-repo-sync-stage.sh
   deliver: telegram (empty stdout sends nothing)
   ```

   The shim lives at `<hermes home>/scripts/skill-repo-sync-stage.sh` (rendered from
   `../assets/stage-sweep-script.sh.example`): `--script` resolves names under
   `<hermes home>/scripts/`, whatever the job's workdir is. It execs the stable wrapper's
   `--stage` and stays silent on a no-op.

2. **Maintainer** — the maintainer host only, an agent run on a monitor-gated schedule
   (e.g. every 30 min — the monitor script's byte-stable pending report wakes the agent only
   when it changes):

   ```text
   every 30 min · monitor-script: skill-repo-maintain-monitor.sh · skills: [skill-library-maintenance] · workdir: <repo> ·
   pinned --provider/--model · deliver: telegram · failure-deliver: telegram
   ```

   Pin the model (`hermes cron create/edit --provider <P> --model <M>`): an unpinned agent job
   resolves the config route at fire time and fails closed when `model.*` changes underneath it.
   Verify a job's recorded fields in `~/.hermes/cron/jobs.json` — `hermes cron status` shows the
   scheduler, not one job. Back `jobs.json` up before removing a job: its prompt often embeds
   procedure that exists nowhere else.

3. **Daily instance pre-integration** — every installation with a shared checkout, an agent run:

   ```text
   daily, before the maintainer · skills: [skill-governance, skill-library-maintenance] ·
   workdir: <repo> · pinned --provider/--model · deliver: telegram
   ```

   On a machine with several profiles this job runs **per profile** — each reviews only its own
   sessions' writes (attribution via `evidence.session_id`) and routes into its own adaptation.

## Maintainer run book (v3 — candidate → review → report → integrate)

Budget and context: a normal candidate targets **at most 35 assistant turns**, and that turn
target is **not** a token cap. Start from the prepared manifest — `input_paths` (including
deletions) and `conflict_paths` — plus the complete staged hunks; never load the implementation
plan or three full file versions. Focused context is at most one `read_file` window per file
(`offset`/`limit`) around the affected heading. Usage counters are reported as `measured`,
`estimated` or `unavailable`; an unsupported provider counter is `unavailable`, never guessed. If
the review cannot finish within its context/turn budget, record an **incomplete review** — keep the
candidate and decisions, do not integrate truncated work, and do not restart an unlimited full-file
loop.

All helper calls below mean the script invoked **directly from the repository tree** with explicit
`--store {store} --repo {maintainer_repo}`:
`python3 {skills_repo}/skills/skill-library-maintenance/scripts/skill-repo-maintain.py <mode> --store {store} --repo {maintainer_repo}`
— never a copy under `<hermes home>/scripts/` and never a `SKILL_REPO_SYNC_ENGINE` export: the
helper imports the engine and the shared core beside itself.

1. Preconditions: `--selfcheck --verbose` must report a consistent installed pair, config,
   report root and lock state. A technical failure ends the run with a report; write nothing.
2. Monitor: the job's shim runs `--pending`. Output is the stable wake-on-change key: sorted
   `pending <cid>` lines plus one `blocked <cid>` line for an unchanged blocked candidate.
   Independently scan unfinished journals: `recover <cid>` routes to `--reconcile <cid>` and
   receipt delivery, never recapture; `incident <cid>` routes to incident inspection, not an
   automatic push/retry. These lines are sorted, deduplicated and byte-stable, have no timestamp or
   retry suffix, and remain visible when T is already consumed or its source is disabled. Incident
   takes precedence over recover; recover replaces pending for the same cid. A clean `complete`
   journal is omitted. Existing pending/blocked lines and their explicit retry suffix stay unchanged.
   `error: monitor-unhealthy` on stdout means the monitor could not read the remote — report it,
   do not invent an empty success. `blocked` means inspect and report; retrying unchanged work is
   an explicit `--retry <cid>` (one generation), never an automatic loop. Select exactly **one**
   pending candidate for this pass, smallest first.
3. `--capture-source refs/heads/machine/<host>` — one fetch, pins M and T, persists the journal.
   The printed candidate id must equal the selected `pending <cid>` line. A refactoring candidate
   is different: `--submit-refactor <ref> --tip <fullsha> --brief <json>` creates the record first,
   then `--capture-source refs/heads/refactor/<slug>` captures its exact tip; only a submitted,
   current record is ever pending.
4. `--prepare <cid>` — detached candidate worktree plus one native merge. Read the full change
   manifest (`input_paths`, every path including deletions) and the conflict packets
   (`conflict_paths`) from the printed journal. Inspect the complete staged hunks read-only, e.g.
   `git -C <worktree> diff --cached --name-status M` and one per-path
   `git -C <worktree> diff --cached M -- <path>`; do not replace this with `git show M:<file>` /
   `git show T:<file>` full-version reads. Exit 12 is a real policy refusal, not a retry hint.
5. Classify every manifest path **and any additionally edited path** as `addition`, `correction`,
   `replacement` or `reject` (duplicate/unsuitable/instance-specific). For a replacement, name the
   old rule, the new rule and the reason; remove incompatible remnants. Generic illustrative paths
   and code citations are judged on their role, not vetoed by a path/date regex. Ordinary semantic
   conflicts are resolved autonomously — there is no daily human approval queue and no approve CLI.
6. Resolve and stage **only** in that candidate worktree: resolve genuine conflicts explicitly and
   stage every clean addition, deletion and empty file too (`git add -- <path>`). Never commit,
   amend, rebase, reset, push or switch branches there; never `-X ours`/`-X theirs`; never execute
   a candidate's own scripts. Tool code runs from the trusted maintainer baseline.
7. Write the review JSON (contracts §2.3: exact paths, source anchors, reasons, old→new
   replacements) and run `--record-review <cid> --review-file <path>`. It runs the fixed real
   checks (whitespace, staged syntax, package tests, validator, library audit) and persists the
   reviewed tree/digest. Exit 10 = required checks failed; repair and re-run, never bypass, delete
   or weaken a check to get green.
8. `--render-report <cid>` — deterministic payload under the store. Write those exact bytes as a
   plain file into the configured `report.path`: when the file already exists, compare and either
   confirm identical bytes (idempotent) or stop on a mismatch — never blind-overwrite. Read the
   file back exactly.
9. `--verify-report <cid>` — exact-byte comparison at the registered report root; a missing,
   altered or symlinked note blocks integration and keeps the candidate.
10. `--integrate <cid>` — exactly one merge commit with ordered parents M,T and the reviewed tree,
    non-force push, remote confirmation. A moved main is `stale`, never force-pushed.
11. Crash or uncertain push: `--reconcile <cid>` from the saved P. It never creates a second
    integration commit; receipt delivery is repaired separately.
12. `--render-result <cid>` — receipt payload; write those bytes as a plain file under `report.path`, read them
    back exactly, then `--verify-result <cid>` records `complete`. The immutable review note is
    never edited or backfilled; the outcome lives only in the result note.

Failure discipline: no commit on any error; a blocked candidate keeps its evidence and the monitor
line does not churn. Never force, reset or rebase any ref — `--refresh-strip` and `--reset-branch`
are retired and refuse with exit 12. Every mode's `--dry-run` is write-free (no fetch, ref,
worktree, lock or state write); it is safe to preview.

Telegram report ≤15 lines, including the usage fields above. Empty run: one line, silence
otherwise.

## Refactor worktree runbook (deliberate redesign, not transport)

A cross-file redesign is developed on its own `refactor/<slug>` branch in a worktree **outside**
every runtime skill discovery root. The branch is never transport work: it becomes a candidate only
through an explicit exact-tip submission. Resolve every variable below and get operator approval
before running anything — these are the future execution shape, not a claim that such a worktree
exists.

```bash
# Resolve/approve before use: SOURCE_REPO is the maintainer clone, REFACTOR_WORKTREE must be
# outside runtime roots, the vault and the maintainer checkout, and BRIEF is the JSON below.
export SOURCE_REPO=/path/to/maintainer-clone
export REFACTOR_WORKTREE=/path/to/refactor-skill-sync
export STORE=/path/to/skill-repo-sync
export SLUG=skill-sync

git -C "$SOURCE_REPO" fetch origin
git -C "$SOURCE_REPO" worktree add -b "refactor/$SLUG" "$REFACTOR_WORKTREE" origin/main

# Keep the branch current by merging integrated main. Never rebase integrated history.
git -C "$REFACTOR_WORKTREE" fetch origin
git -C "$REFACTOR_WORKTREE" merge origin/main

# Normal small commits during implementation, explicit paths only:
git -C "$REFACTOR_WORKTREE" add -- skills/demo/SKILL.md
git -C "$REFACTOR_WORKTREE" commit -m "refactor: rewrite the demo instruction"

# Backup push. This is NOT readiness and creates no candidate:
git -C "$REFACTOR_WORKTREE" push origin HEAD:refs/heads/refactor/$SLUG
```

The brief is the only review scope for readiness, and it has no command field:

```json
{
  "summary": "Rewrite the demo instruction on the refactor branch",
  "intended_replacements": [{
    "path": "skills/demo/SKILL.md",
    "old_quote": "Base instruction.",
    "new_instruction": "Refactored base instruction.",
    "reason": "The refactor replaces the one demo instruction."
  }],
  "validation_notes": "The exact submitted tip was reviewed; no other path changes."
}
```

Submit and capture on the maintainer side (exact full tip, never a branch name):

```bash
TIP=$(git -C "$REFACTOR_WORKTREE" rev-parse HEAD)
python3 "$SOURCE_REPO/skills/skill-library-maintenance/scripts/skill-repo-maintain.py" \
  --submit-refactor "refs/heads/refactor/$SLUG" --tip "$TIP" --brief "$BRIEF" \
  --store "$STORE" --repo "$SOURCE_REPO"
python3 .../skill-repo-maintain.py --capture-source "refs/heads/refactor/$SLUG" --store "$STORE" --repo "$SOURCE_REPO"
python3 .../skill-repo-maintain.py --pending --store "$STORE" --repo "$SOURCE_REPO"
```

Rules:

- **No rebase.** Merge `origin/main` into the branch; integrated history is never rewritten. If
  `--submit-refactor` refuses because main advanced, merge main, review the merged result and submit
  the new tip — no other recovery path is valid.
- **Backup is not readiness.** `--submit-refactor` is the only operation that creates a refactoring
  candidate; the monitor ignores every unsubmitted `refactor/*` branch and every stale submission
  (its captured main is no longer integrated main).
- **Final edits need a new submission.** Commit on the branch, push the new tip, submit again. The
  integration commit is parents `[M,T]` with `tree(P) == tree(T)` exactly, so an agent edit staged
  in the candidate worktree is refused (unlike transport's semantic curation) — it belongs on the
  branch and in a new exact tip.
- **Not a discovery root.** The refactor worktree must not be a runtime skills root, a report root
  or a live project directory; sweeps never stage or integrate it, and `prepare` refuses candidate
  worktrees inside those roots.
- **Trusted tool baseline.** Candidate workflow tool code runs from the trusted maintainer baseline,
  never from the refactor worktree's unreviewed new scripts. If the maintainer logic itself changes,
  finish the run and restart from verified `main`; never swap tool code midway through promotion.
- **Freeze is short and narrow.** Only the final promotion takes the existing maintainer lock.
  Preparation and a long review release it and re-check freshness later. While the lock is held a
  second maintainer action refuses, but contributors keep committing and pushing transport work; that
  new work remains pending after the refactor integration.
- **No implicit cleanup.** Nothing deletes the worktree, the `refactor/*` branch or its remote ref.
  Removal is a deliberate operator action after the integration is integrated.

## Periodic whole-skill review (bounded, one skill per run)

The candidate review only sees today's diff. A separate, slow cadence reads **one existing skill
per run** and looks for contradictions, duplication, stale claims, scope leaks and previously
accepted mistakes that no current candidate touches.

- **One skill per run, deterministic order.** Enumerate the owned packages in the configured
  repository (for example `skills/*/SKILL.md`), sort the directory names, and read the cursor from
  local maintainer state — `<store>/skill-review-cursor.json`, schema 1, `{"last": "<skill>"}` —
  never from memory or a skill body. The pure helper `next_skill(skills, last)` in the shared core
  returns the next name (sorted, de-duplicated; a deleted cursor resumes at its successor; after
  the last name it wraps). An empty inventory returns `None`; do not invent a package.
- **Bounded evidence.** Read the selected skill's `SKILL.md`, its referenced support files and the
  headings around the suspect rules. Do not review the whole library in one run.
- **Findings always produce a report**, even when no automatic fix is made: write the same
  per-candidate-style note under the configured reports hub with the finding, path/section, reason
  and proposed disposition.
- **Disposition.** A small, justified correction enters the normal source workflow (transport
  candidate, review, report, integrate). An architectural rewrite uses the explicit
  `refactor/<slug>` branch and exact-tip submission, never a giant automatic rewrite of `main`.
- **Schedule proposal, not a live job.** Weekly (`0 4 * * 0`, configurable at deployment) is the
  proposed cadence; installing or changing this job is a separate deployment action. The prompt is
  `assets/skill-review-cron-prompt.md.example`; the cursor file is read and updated by the agent,
  so no scheduler implementation exists in this skill.

## Instance pre-integration (the instance's own review run)

The maintainer cannot judge what is instance-specific — it lacks the context, and dropping such a
lesson loses it. A daily agent run on each installation — scheduled before its content should reach the
maintainer, because this run owns the push — cleans that installation's own pending transport
content:

0. Refresh by ancestry: `python3 {skills_repo}/skills/skill-library-maintenance/scripts/skill-repo-sync.py --sync-from-main --verbose`.
   It fast-forwards the transport branch when `HEAD` is an ancestor of `origin/main` (integrated main
   is newer), does nothing when main is already an ancestor of `HEAD`, and otherwise keeps
   divergent or dirty work for this run to merge deliberately. Never reset, rebase or autostash
   contributor work. If it reports `pre-integration merge required`, take the contributor lock for the
   short merge only:
   `skill-repo-sync.py --lock`, `git fetch origin`, `git merge --no-ff --no-commit origin/main`,
   resolve and review, `git commit`, then `skill-repo-sync.py --unlock` immediately — never hold the
   lock for the rest of the session. There is no implicit resume catch-up: this run or an explicit
   user trigger is the only start; a missed schedule waits for the next run.
1. Fetch; review the pending additions (`origin/main...HEAD` plus the `needs-pre-integration` markers in
   recent stage commits / `stage-report.json`) against `skill-governance`'s routing rule.
2. Instance-shaped (vault paths, host names, quotas, machine tables, session narration): remove the
   line from the canonical skill edit; when the lesson is worth keeping for this setup, write it
   into the *writing* profile's adaptation instead (profile-scoped — never another profile's). A
   generic core worth keeping survives as generic text.
3. Generic and durable: leave it — value and dedupe are the maintainer's judgement.
4. Screen the **whole unpublished history**, not just the final tree:
   `skill-repo-sync.py --screen-history HEAD` (exit 10 means forbidden paths or suspected credential
   patterns in an intermediate commit — diagnostics are path/category only and the matched value is
   never echoed). Record the agent's profile-scope classification for every unpublished commit in a
   JSON file and persist it bound to the exact tip:
   `skill-repo-sync.py --record-history-review <tip> --history-review <file>`.
5. Exactly one `pre-integration:` commit on the transport branch (explicit paths), then integrate
   **exactly the reviewed commit**, never the branch name:
   `skill-repo-sync.py --push-reviewed <tip>`. It re-runs the screen, refuses a missing or
   mismatched history review, pushes `<tip>:refs/heads/machine/<name>`, verifies the remote ref with
   `ls-remote` and records `last_pushed_tip` as metadata. A commit added after the review stays
   local until it is reviewed itself. Empty run: one line, no new commit — but push whatever
   reviewed commits already exist. Never touch `main`.

A laptop that wakes after the maintainer's run is always stale by design — the refresh
fast-forwards it when `HEAD` is an ancestor of `origin/main` (integrated main is newer), so that
is a non-event; when the branch has diverged the refresh preserves it and this run merges
deliberately. Never force.

The layering is deliberate: write-time routing rule (`skill-governance`) → this review run
(semantic, per profile) → staging scan (mechanical marker) → maintainer review pass (final
judge). The run exists because a routing rule alone is followed unreliably — leftovers otherwise
reach the maintainer, which can only drop them and lose the lesson.

## Manual integration (fallback: maintainer blocked, or a hotfix now)

Keep automated conflict handling abort-only; this sequence is the deliberate exception.

1. Inspect `git status --short --branch`, staged and unstaged diffs, upstream, and local identity.
   Commit authorized local work in coherent, explicitly staged groups before merging; do not sweep
   unrelated edits into a checkpoint.
2. `git fetch origin`; inspect the incoming diff. For overlap detection between two sides, diff
   **each side against the merge base** and intersect the file lists — a three-dot diff shows one
   side's changes, not the difference, so an overlap check built from it compares a side with itself.
3. Resolve each conflict so both valid lessons land, with one home per rule. Never use
   `-X ours`/`-X theirs` or a force-push. Compare both package versions and choose a SemVer
   increment beyond both when the result combines their changes.
4. Stage resolved paths explicitly; require an empty `git diff --name-only --diff-filter=U` and a
   clean `git diff --cached --check`. Enumerate changed packages from `git diff --cached --name-only`;
   validate every affected package and run its bundled tests.
5. Complete the merge with `git commit --no-edit`; verify `git merge-base --is-ancestor origin/main
   HEAD` after pushing, and reload changed skills to confirm runtime resolution.

Optional softening for the meta-skills only (`skill-governance`, `skill-builder`,
`skill-library-maintenance`): `.gitattributes` with `merge=union` makes purely additive list
edits merge without stopping. Price: a line both sides *rewrote* ends up duplicated and must be
cleaned up by hand — so it stays an option, not the default.

## Cross-machine deployment audit

When asked whether a machine is prepared for the sync stack, or whether every installation is on
the same version and has integrated its work, run this read-only checklist over SSH on each machine
and compare the results:

1. **Versions** — `SCRIPT_VERSION` in `scripts/skill-repo-sync.py`, `INSTALLER_VERSION` in
   `scripts/install-skill-repo-sync.py`, and the `version:` frontmatter of
   `skill-library-maintenance/SKILL.md`. Report drift between machines as a finding; the installer
   comment demands engine/installer parity, so a mismatch is a defect to name, not to normalize away.
2. **Wrapper** — `<hermes home>/bin/skill-repo-sync` exists and is executable.
3. **State** — `<hermes home>/skill-repo-sync.json` exists and names the machine; the engine's
   `--selfcheck --verbose` is the authoritative check (it reports `not installed` when the state
   file is missing).
4. **Hooks** — grep `<hermes home>/config.yaml` for `on_session_start` (it must point at the
   wrapper's `--sync-from-main --hook`); a v1 `on_skill_lifecycle` entry should be empty, not
   deleted silently. `hermes hooks list` and `hermes hooks doctor` confirm activation —
   configured is not activated.
5. **Cron** — `hermes cron list` shows the hourly staging sweep and, on the maintainer host, the
   monitor-gated maintainer job.
6. **Ledger** — `<hermes home>/skills/.curator_ledger.jsonl` exists and is non-empty.
7. **Git state** — `git status --short --branch` (ahead/behind, uncommitted files),
   `git log --oneline origin/machine/<name>..HEAD` (unpushed commits and which paths they touch),
   and `git push --dry-run origin HEAD:machine/<name>` (push capability without side effects).
8. **Staging dry-run** — `<wrapper> --stage --dry-run --verbose`: what the next sweep would bundle
   into the transport commit. On `main` it exits 12 (branch policy) and on `refactor/*` it reports
   the exclusion — both are the documented answer, not a missing plan.

Diagnosis:

- **Local stage commits growing while `origin/machine/<name>` is stale** → the pre-integration
  run has not pushed yet (normal overnight and between its runs) or its push failed; it retries at
  the next run without duplicating commits. Content findings do not block transport — the staging
  scan records them in `stage-report.json` and the candidate review (`validate_review`) surfaces
  instance-scope findings; final path/check/tree gates block integration. Suspect the missing
  pre-integration push first when `ahead N` grows, before credentials or connectivity.
- **Uncommitted changes no human made** → background-review sediment; attribute from the ledger
  before touching them (see the symptom note above).
- **A machine holds unpushed commits touching a file another machine has edited** → land the
  backlogged machine's transport branch first, then the other one's. The semantic reconciliation of
  the overlap belongs to the next maintainer pass, not to an ad-hoc merge on a machine.
- **A deployment note disagrees with the live checkout** → the checkout wins. Notes describing
  versions, paths, or install state are claims to verify against the scripts on disk, never state
  to trust; report the note as stale rather than adopting its numbers.

SSH and CLI pitfalls when auditing remote machines:

- Machine names in a project's machine table are logical names, not guaranteed SSH hostnames.
  Resolve through `known_hosts` variants (`<name>.lan`, `<name>.local`, `<name>.fritz.box`) and
  known IPs before declaring a machine unreachable; when nothing resolves, report "unreachable —
  need an access path" and stop. Never guess credentials or invent a hostname.
- `hermes` is typically absent from `PATH` in a non-interactive SSH session. Inspect hook
  configuration by reading `<hermes home>/config.yaml` directly; run `hermes hooks list`,
  `hermes hooks doctor`, and `hermes cron list` through a login shell or with the profile's PATH
  sourced when those are required.

## Diagnosing a stuck sync

When sync has silently stopped, rebuild causality from the ledger and git history before trusting
any explanation — a report or design draft names the most recent visible event, while a frozen
cursor date marks where the failure actually began.

1. Read the state file: compare `ledger_cursor` and its timestamp against the ledger's entry count
   and newest entry. A frozen cursor while entries keep arriving means runs have failed since the
   cursor date, not since the last visible error. A cursor behind the ledger with staging green is
   the opposite case — it self-heals on the next sweep.
2. `git log --format='%ci %s'` on the transport branch and on `main` separately. Stage commits
   growing locally while `origin/machine/<name>` is stale means the pre-integration run has not
   pushed yet (or its push failed), not staging failures.
   `main` unchanged while transport branches accumulate means the integration is failing — the
   branches stay consumable and nothing is lost.
3. Localize a chain break from staging-scan findings (`stage-report.json`): hash every pending
   entry's before/after values against the path's blob history (`git log --format=%h -- <path>`,
   then `git show <rev>:<path>`). The first entry whose before-hash matches neither the preceding
   entry's after-hash nor any blob at its time marks where a commit outside the ledger intervened.

Pitfalls:

- **A before/after hash chain assumes a single writer per branch.** Any commit made outside the
  ledger — audit, manual fix, merge — inserts a blob state the chain does not know. Under Stage &
  Integrate this surfaces as staging-scan findings and provenance gaps, not a transport stall — but
  the chain can no longer prove who changed a line across the break, so attribute such a change
  from the commit and the worktree, not from ledger entries alone.
- **The sweep refuses `main` even when clean, and excludes `refactor/*`.** A `main` checkout is
  never a staging target (exit 12, branch policy); a `refactor/*` branch is skipped untouched with
  a diagnostic. So a host that sits on `main` between integration runs must not be a registered
  sweep repo, and refactor worktrees are neither transport nor automatically ready. Do not "fix"
  either refusal by checking out a transport branch, which would silently assign main work to the
  machine branch; feature work on `main` gets checked out explicitly, once.
- **The sweep transports everything dirty.** It cannot tell an experiment from a finished edit:
  worktree debris rides into the next transport commit, and scratch directories inside the repo
  (`.integrate-scratch/`, pytest caches) belong in `.gitignore` or they are committed too. Keep
  the worktree free of debris; commit or stash work-in-progress deliberately.
- **A transport branch is not a place to keep work.** It is never reset, so commits not yet
  consumed stay visible and pending; land unfinished work as a `WIP` commit on the transport
  branch so the sweep and the maintainer see it, never as a side branch nobody watches.
- **`hermes cron run` is synchronous and its claimed execution outlives the CLI.** Killing the CLI
  does not stop the run — a re-fire starts a second copy of the job in the same working copy. Fire
  agent jobs in the background, or verify the execution has finished, before re-firing; the
  single-flight lock refuses the overlap only once the first run reached `--lock`.
- **Age and cron rows are not liveness evidence for the maintainer lock.** The lock lives at
  `<maintainer clone git-common-dir>/hermes-sync/maintainer.lock`, so it covers linked worktrees and
  alternate state stores; it has no TTL and never reads `executions.db`. A crashed run leaves the
  file visible with its owner token, pid, host and acquisition time. Recover with `--unlock` (the
  owner token recorded by `--lock`) from the same store; `--force-lock` refuses and names the
  stored token. Remove the lock manually only after you have observed on that host that the owning
  executor is gone — never because the file is old.

## Removing it

```bash
cp <hermes home>/cron/jobs.json "<backup dir>/cron-jobs-$(date +%Y%m%d-%H%M%S).json"
hermes hooks revoke <hermes home>/bin/skill-repo-sync
hermes config set hooks.on_session_start '[]'
hermes config set hooks.on_skill_lifecycle '[]'    # only if a v1 install left an entry
hermes cron remove <staging sweep job> [<maintainer job>]
rm <hermes home>/bin/skill-repo-sync <hermes home>/skill-repo-sync.json
```

The repository keeps its commits (including the transport branches); nothing else is left behind.
