# Shared skill repo: stage and consolidate (cross-installation sync)

Applies when the same skill repository is mounted on more than one Hermes installation
(`skills.external_dirs`). The design is **Stage & Consolidate**: no machine session ever writes `main`;
each installation stages its work onto a transport branch `machine/<hostname>`, and one monitor-gated
consolidator consumes the transport branches one per pass, one `main` commit per consumed branch.

## The problem this solves

The background review writes lessons into skills through `skill_manage` — including skills in a
shared, git-versioned repository — and every installation accumulates manual edits beside them.
Left alone, those writes collide across machines. The previous design (a per-mutation publisher
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
| `main` | exactly one writer: the consolidator. Machine sessions, hooks and sweeps never touch it |
| Transport branch | `machine/<hostname>` per installation — a landing strip for commits, not a feature branch; reset to `main` after consumption, never merged back by hand |
| Staging trigger | hourly script-only cron → `--stage`: bundles the pending ledger paths **and** the dirty worktree into ONE LOCAL commit on the transport branch — the push belongs to the pre-consolidation run (what lands on a transport branch is always pre-consolidated) |
| Instance pre-consolidation | daily agent run per installation before the consolidator: reviews that installation's own pending additions, moves instance-shaped lessons out of canonical edits into the *writing* profile's adaptation, leaves generic content for the consolidator — then pushes the branch: it is the only pusher |
| Refresh trigger | `on_session_start` shell hook (`--sync-from-main`): fetch; when the transport branch was consumed upstream, reset it to `origin/main` |
| Monitor gate | `--monitor-script` netto-pending gate: a cheap script prints the byte-stable pending report (`--pending`) each tick; the exact-bytes hash suppresses unchanged output entirely — wake-on-change, the agent never runs idle |
| Consolidation trigger | monitor-gated (e.g. every 30 min) consolidator cron on the consolidator host (agent run, model-pinned; the monitor gate suppresses the run while no transport branch has news — no idle LLM runs): one `machine/<host>` branch per pass (smallest diff first), a mechanical 3-way merge map per file (`git merge-file --diff3`), one `main` commit per consumed branch, then the branch reset |
| Conflict packets | what the agent actually sees for a conflict: ours/base/theirs ± 10 lines of context — auto-merged files are done and never opened; never a whole diff or a whole file |
| Commit granularity | one staging commit per sweep (the ledger holds hashes, not intermediate contents — per-run commits are unreconstructable, so the sweep commits the current content per path, once); one consolidator commit per consumed branch |
| Commit message | names the skills whose files actually changed; ledger entry IDs ride in the trailers for attribution and recovery |
| Overlap | the consolidator's problem by design: one home per rule when two machines touched the same file; never `-X ours`/`-X theirs`, never a force-push of `main` |
| Review pass | after `--apply-decisions`, over the merged net diff — run book step 4.e owns the rule (duplicates, contradictions, one home per rule, defensive drop of instance-shaped leftovers); the why: git merges duplicates and contradictions cleanly, so they never arrive as conflicts |
| Gate before `main` | `--preflight` and the review pass: instance pointers, dangling references, duplicate rules, ledger hash-chain findings — provenance and quality evidence; nothing reaches `main` unreviewed |
| Long sessions | the skill *index* is a start-of-session snapshot (prompt-cache invariant); skill *bodies* load from disk, so `/skill-name` always yields current content. Never pull mid-session to "fix" an index |

Two design facts the failure modes establish, worth keeping when this is next redesigned:

- Provenance must hold without old ledger entries matching current `HEAD` — the chain is evidence
  for the consolidator, never a hold on transport. The ledger selects and attributes paths; it cannot
  certify content against a moving `HEAD`.
- Semantic review gates canonical writes even when git reports no conflict: duplication, scope leaks
  and contradictory rules arrive conflict-free. Hash integrity proves provenance, not quality —
  `--preflight` plus the review gate in `skill-governance` is the quality side.

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
| `scripts/skill-repo-sync.py` | the engine (staging + session-start sync); `SCRIPT_VERSION` in the header |
| `scripts/install-skill-repo-sync.py` | installer; `INSTALLER_VERSION` must match the engine |
| `scripts/skill-repo-consolidate.py` | the consolidator's helpers: `--pending`, `--refresh-strip`, `--note-pushed`, `--collect`, `--preflight`, `--merge-map`, `--apply-decisions`, `--lock`/`--unlock`, `--reset-branch` |
| `<hermes home>/bin/skill-repo-sync` | stable wrapper the hooks call (a shell script that execs the engine) |
| `<hermes home>/scripts/skill-repo-sync-stage.sh` | generated staging shim for the hourly `no_agent` job, rendered from `../assets/stage-sweep-script.sh.example` |
| `<hermes home>/scripts/skill-repo-consolidate-monitor.sh` | generated monitor shim for the consolidator job's `--monitor-script` gate (prints `--pending`), rendered from `../assets/consolidate-monitor-script.sh.example` |
| `<hermes home>/skill-repo-sync.json` | state: repos, wrapper, engine path, ledger cursor, versions |
| `<hermes home>/skills/.curator_ledger.jsonl` | mutation ledger (written by Hermes, read here) |

The wrapper path must stay constant: the hook consent pair is `(event, command)`, so changing the
command needs fresh consent. Update the engine in the repository — never the wrapper. The wrapper
execs the engine **from the checked-out worktree**, so a branch switch silently swaps the engine
version underneath live hooks and crons: keep the checkout on the transport branch between runs,
and verify `--version` after any checkout.

The wrapper, the staging shim and the monitor shim are the **only generated artifacts** of this
sync, and each exists for exactly one stable path: hook consent binds to the wrapper's
`(event, command)` pair, and `hermes cron create --script` / `--monitor-script` resolve scripts
under `<hermes home>/scripts/`. Everything else is called directly from the repository tree
(`python3 {skills_repo}/skills/skill-library-maintenance/scripts/skill-repo-consolidate.py …`);
the helper imports the engine beside itself (`_engine_candidates`), so there is no
`SKILL_REPO_SYNC_ENGINE` export and no copy of the scripts under `<hermes home>/scripts/`.
Logic lives in the repository — update it there, never a copy.

## Modes

```bash
python3 scripts/skill-repo-sync.py --version          # engine version
python3 scripts/skill-repo-sync.py --selfcheck        # install state, repos, wrapper, ledger cursor
python3 scripts/skill-repo-sync.py --stage            # hourly sweep: ledger paths + dirty worktree → one LOCAL commit on machine/<name> (push = pre-consolidation)
python3 scripts/skill-repo-sync.py --sync-from-main   # on_session_start: fetch; consumed transport branch → reset to origin/main
python3 {skills_repo}/skills/skill-library-maintenance/scripts/skill-repo-consolidate.py --pending   # monitor gate: byte-stable pending report on stdout (the wake-on-change signal)
python3 {skills_repo}/skills/skill-library-maintenance/scripts/skill-repo-consolidate.py --refresh-strip # pre-consolidation step 0: replay never-pushed commits onto the refreshed strip
python3 {skills_repo}/skills/skill-library-maintenance/scripts/skill-repo-consolidate.py --note-pushed  # after each successful pre-consolidation push: record the pushed tip
python3 {skills_repo}/skills/skill-library-maintenance/scripts/skill-repo-consolidate.py --lock / --unlock  # consolidator: single-flight guard for one run
python3 {skills_repo}/skills/skill-library-maintenance/scripts/skill-repo-consolidate.py --collect   # consolidator: the pending ledger paths for tonight's commit
python3 {skills_repo}/skills/skill-library-maintenance/scripts/skill-repo-consolidate.py --preflight # consolidator: review gates over the planned content
python3 {skills_repo}/skills/skill-library-maintenance/scripts/skill-repo-consolidate.py --merge-map <host>        # consolidator: 3-way map + conflict packets (needs --outdir)
python3 {skills_repo}/skills/skill-library-maintenance/scripts/skill-repo-consolidate.py --apply-decisions <file>  # consolidator: resolve conflict blocks (needs --outdir)
python3 {skills_repo}/skills/skill-library-maintenance/scripts/skill-repo-consolidate.py --reset-branch  # consolidator: reset a consumed transport branch to origin/main
```

Both scripts accept `--dry-run` (no state, index, commit, or remote writes) and `--verbose`. Exit
codes are listed in the engine header; the ones behavior is pinned to by tests: `0` ok/no-op,
`12` policy refusal or error (wrong branch, dirty `main`), `13` not installed.

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
python3 skill-repo-sync.py --selfcheck --verbose
python3 -m pytest ../tests -q
```

For a fresh install, `--bootstrap-current-ledger` explicitly places the cursor at the current
ledger end; it skips historical entries rather than transporting them. On an existing install,
omit this flag so the saved cursor is preserved.

`--apply-config` writes only the `on_session_start` hook entry through `hermes config set`; it
never changes `hooks_auto_accept`, and a v1 install's `on_skill_lifecycle` entry is left emptied,
not silently deleted. Approve the exact `(event, command)` pair through Hermes' normal consent
flow. For headless setup, use a verified exact-pair allowlist; do not enable global auto-accept.
Additional shared repos: repeat `--repo /path/to/other/repo`.

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

2. **Consolidator** — the consolidator host only, an agent run on a monitor-gated schedule
   (e.g. every 30 min — the monitor script's byte-stable pending report wakes the agent only
   when it changes):

   ```text
   every 30 min · monitor-script: skill-repo-consolidate-monitor.sh · skills: [skill-library-maintenance] · workdir: <repo> ·
   pinned --provider/--model · deliver: telegram · failure-deliver: telegram
   ```

   Pin the model (`hermes cron create/edit --provider <P> --model <M>`): an unpinned agent job
   resolves the config route at fire time and fails closed when `model.*` changes underneath it.
   Verify a job's recorded fields in `~/.hermes/cron/jobs.json` — `hermes cron status` shows the
   scheduler, not one job. Back `jobs.json` up before removing a job: its prompt often embeds
   procedure that exists nowhere else.

3. **Daily instance pre-consolidation** — every installation with a shared checkout, an agent run:

   ```text
   daily, before the consolidator · skills: [skill-governance, skill-library-maintenance] ·
   workdir: <repo> · pinned --provider/--model · deliver: telegram
   ```

   On a machine with several profiles this job runs **per profile** — each reviews only its own
   sessions' writes (attribution via `evidence.session_id`) and routes into its own adaptation.

## Consolidator run book (v2.1 — hunk-gated, one branch per pass)

Budget: ≤35 assistant turns per run. Never read a whole `machine-*.diff` or a whole skill
file — the merge map gives you conflict packets; more context only via `read_file` with
`offset`/`limit`, one window per file per run. Resolving conflict packets is the primary job;
the review pass below covers what git merged cleanly, because duplicates and contradictions
between sources are not conflicts to git. The cron prompt carries a compact copy of the hard
limits; this run book stays the authoritative procedure.

All helper calls below mean the script invoked **directly from the repository tree** —
`python3 {skills_repo}/skills/skill-library-maintenance/scripts/skill-repo-consolidate.py <mode>`
— never a copy under `<hermes home>/scripts/` and never a `SKILL_REPO_SYNC_ENGINE` export: the
helper imports the engine beside itself (`_engine_candidates`).

1. Single-flight: `python3 {skills_repo}/skills/skill-library-maintenance/scripts/skill-repo-consolidate.py --lock` (exit 12 → report one line and stop).
   A failed run keeps the lock on purpose; `--force-lock` is a deliberate human decision. The lock
   is created atomically (`O_CREAT|O_EXCL`), and the execution-claim check ignores claims younger
   than 60 s: a cron claim is recorded with the *dispatcher's* pid, never the executor's lineage,
   so identity matching cannot find "self" and a pid-based check refuses every run.
2. `git fetch origin --prune`; checkout `main`; `git reset --hard origin/main`.
3. `--collect --outdir <scratch>` → read `collect.json` only (sizes, files, overlaps).
4. For each non-empty `machine/<host>`, smallest shortstat first — one branch per pass:
   a. `--merge-map <host>` → `merge-map.json` + `conflict-packets.json`. Auto-merged files
      are done; do not open them.
   b. `--preflight` → instance pointers / dangling refs are repair orders for your edit.
   c. Review set per branch — everything gets a semantic look, nothing gets a whole file:
      conflict packets, `needs-pre-consolidation` items, and the added-hunk digest (`added-hunks.json`,
      clean files' additions as heading + new lines). Decide per `skill-governance` (worth
      keeping? instance-specific → reject with reason? already in the target — sharpen the
      existing spot? synthesize across sources?). Output: `decisions.json` (`file`, `block`,
      `action: ours|theirs|synthesize/drop`, `text` for synthesize) plus one SemVer bump per
      touched skill.
   d. `--apply-decisions decisions.json --outdir <scratch>` → resolved files in the worktree.
   e. Review pass over the merged net diff (`git diff origin/main -- <changed files>`):
      duplicate rules across files and sources (same rule restated differently), contradictions
      between sources, one home per rule (sharpen the existing spot instead of a second bullet),
      and defensively DROP instance-shaped leftovers (vault paths, host names, quotas) with
      line + reason in the report. Fix everything in place before validation.
   f. `audit-skill-library.py skills --json` (summary.errors == 0) and `--preflight` (0 findings).
   g. ONE commit per branch: `consolidator: consolidate <skills> from machine/<host> (YYYY-MM-DD)`;
      body: taken over / corrected / dropped with reason; trailer `Consolidator: <model used>`.
      Commit prefix `consolidator:` (never `curator:` — that name belongs to the Hermes
      Skill Curator subsystem).
   h. `git push origin main`; `--reset-branch <host> --confirm-consumed` (must exit 0).
5. `--unlock`; Telegram report ≤15 lines. Empty run: one line, silence otherwise.

Failure discipline: no commit on any error, the lock stays set (anti-double-fire), report
and stop. Never force anything except `--reset-branch`. Never `-X ours`/`-X theirs`.

## Instance pre-consolidation (the instance's own review run)

The consolidator cannot judge what is instance-specific — it lacks the context, and dropping such a
lesson loses it. A daily agent run on each installation — scheduled before its content should reach the
consolidator, because this run owns the push — cleans that installation's own pending transport
content:

0. Refresh-Strip: `python3 {skills_repo}/skills/skill-library-maintenance/scripts/skill-repo-consolidate.py --refresh-strip`
   (exit 12 → one line and stop: the replay conflict is a review or operator decision, never a
   force). The strip follows main on its own — rebase onto the strip, never onto main, because
   the strip may carry not-yet-consumed commits.
1. Fetch; review the pending additions (`origin/main...HEAD` plus the `needs-pre-consolidation` markers in
   recent stage commits / `stage-report.json`) against `skill-governance`'s routing rule.
2. Instance-shaped (vault paths, host names, quotas, machine tables, session narration): remove the
   line from the canonical skill edit; when the lesson is worth keeping for this setup, write it
   into the *writing* profile's adaptation instead (profile-scoped — never another profile's). A
   generic core worth keeping survives as generic text.
3. Generic and durable: leave it — value and dedupe are the consolidator's judgement.
4. Exactly one `pre-consolidation:` commit on the transport branch (explicit paths), then
   `git push origin machine/<name>` and
   `python3 {skills_repo}/skills/skill-library-maintenance/scripts/skill-repo-consolidate.py --note-pushed`
   (records the pushed tip so the next refresh-strip replays only what came after it) —
   ALWAYS, even when nothing needed cleaning: this run owns the
   push, and nothing reaches the consolidator without it. Empty run: one line, no new commit — but
   push whatever local commits already exist. Never touch `main`.

A laptop that wakes after the consolidator's run is always stale by design — the refresh-strip
makes that a non-event; the case to remember is a rejected push after a branch reset: refresh-strip
first, never force.

The layering is deliberate: write-time routing rule (`skill-governance`) → this review run
(semantic, per profile) → staging scan (mechanical marker) → consolidator review pass (final
judge). The run exists because a routing rule alone is followed unreliably — leftovers otherwise
reach the consolidator, which can only drop them and lose the lesson.

## Manual integration (fallback: consolidator blocked, or a hotfix now)

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
the same version and has published its work, run this read-only checklist over SSH on each machine
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
5. **Cron** — `hermes cron list` shows the hourly staging sweep and, on the consolidator host, the
   monitor-gated consolidator job.
6. **Ledger** — `<hermes home>/skills/.curator_ledger.jsonl` exists and is non-empty.
7. **Git state** — `git status --short --branch` (ahead/behind, uncommitted files),
   `git log --oneline origin/machine/<name>..HEAD` (unpushed commits and which paths they touch),
   and `git push --dry-run origin HEAD:machine/<name>` (push capability without side effects).
8. **Staging dry-run** — `<wrapper> --stage --dry-run --verbose`: what the next sweep would bundle
   into the transport commit.

Diagnosis:

- **Local stage commits growing while `origin/machine/<name>` is stale** → the pre-consolidation
  run has not pushed yet (normal overnight and between its runs) or its push failed; it retries at
  the next run without duplicating commits. Content findings do not block transport — they surface
  in the consolidator's `--preflight` at consolidation time (instance-pointer, dangling-reference).
  Suspect the missing pre-consolidation push first when `ahead N` grows, before credentials or
  connectivity.
- **Uncommitted changes no human made** → background-review sediment; attribute from the ledger
  before touching them (see the symptom note above).
- **A machine holds unpushed commits touching a file another machine has edited** → land the
  backlogged machine's transport branch first, then the other one's. The semantic reconciliation of
  the overlap belongs to the next consolidator pass, not to an ad-hoc merge on a machine.
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
   growing locally while `origin/machine/<name>` is stale means the pre-consolidation run has not
   pushed yet (or its push failed), not staging failures.
   `main` unchanged while transport branches accumulate means the consolidation is failing — the
   branches stay consumable and nothing is lost.
3. Localize a chain break from `--preflight` findings: hash every pending entry's before/after
   values against the path's blob history (`git log --format=%h -- <path>`, then
   `git show <rev>:<path>`). The first entry whose before-hash matches neither the preceding
   entry's after-hash nor any blob at its time marks where a commit outside the ledger intervened.

Pitfalls:

- **A before/after hash chain assumes a single writer per branch.** Any commit made outside the
  ledger — audit, manual fix, merge — inserts a blob state the chain does not know. Under Stage &
  Consolidate this surfaces as `--preflight` findings and provenance gaps, not a transport stall — but
  the chain can no longer prove who changed a line across the break, so attribute such a change
  from the commit and the worktree, not from ledger entries alone.
- **A clean `main` checkout is the consolidator host's normal state between runs; a dirty `main` is a
  decision.** The sweep and the session hook no-op on a clean `main` and refuse a dirty one — do not
  "fix" the refusal by checking out a transport branch, which would silently assign main work to
  the machine branch. Feature work on `main` gets checked out explicitly, once.
- **The sweep transports everything dirty.** It cannot tell an experiment from a finished edit:
  worktree debris rides into the next transport commit, and scratch directories inside the repo
  (`.consolidate-scratch/`, pytest caches) belong in `.gitignore` or they are committed too. Keep
  the worktree free of debris; commit or stash work-in-progress deliberately.
- **A transport branch is not a place to keep work.** It is reset after consumption — uncommitted
  tree content survives (the reset is branch-level), but commits not yet consumed do not: land
  unfinished work as a `WIP` commit on the transport branch so the sweep and the consolidator see it,
  never as a side branch nobody watches.
- **`hermes cron run` is synchronous and its claimed execution outlives the CLI.** Killing the CLI
  does not stop the run — a re-fire starts a second copy of the job in the same working copy. Fire
  agent jobs in the background, or verify the execution has finished, before re-firing; the
  single-flight lock refuses the overlap only once the first run reached `--lock`.
- **A single-flight guard cannot identify its own run by pid in `executions.db`.** The recorded pid
  is the dispatcher's (the firing session for a manual run, the scheduler otherwise), never the
  executor's lineage — exclude your own claim by age (a fresh claim is this run) and make the lock
  file the primary guard via atomic create (`O_CREAT|O_EXCL`); a pid-matched guard refuses every
  run at startup.

## Removing it

```bash
cp <hermes home>/cron/jobs.json "<backup dir>/cron-jobs-$(date +%Y%m%d-%H%M%S).json"
hermes hooks revoke <hermes home>/bin/skill-repo-sync
hermes config set hooks.on_session_start '[]'
hermes config set hooks.on_skill_lifecycle '[]'    # only if a v1 install left an entry
hermes cron remove <staging sweep job> [<consolidator job>]
rm <hermes home>/bin/skill-repo-sync <hermes home>/skill-repo-sync.json
```

The repository keeps its commits (including the transport branches); nothing else is left behind.
