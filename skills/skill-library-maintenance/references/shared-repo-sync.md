# Shared skill repo: stage and curate (cross-installation sync)

Applies when the same skill repository is mounted on more than one Hermes installation
(`skills.external_dirs`). The design is **Stage & Curate**: no machine session ever writes `main`;
each installation stages its work onto a transport branch `machine/<hostname>`, and one nightly
curator consolidates every transport branch into a single `main` commit.

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
| `main` | exactly one writer: the nightly curator. Machine sessions, hooks and sweeps never touch it |
| Transport branch | `machine/<hostname>` per installation — a landing strip for commits, not a feature branch; reset to `main` after consumption, never merged back by hand |
| Staging trigger | hourly script-only cron → `--stage`: bundles the pending ledger paths **and** the dirty worktree into one commit on the transport branch, then pushes it |
| Refresh trigger | `on_session_start` shell hook (`--sync-from-main`): fetch; when the transport branch was consumed upstream, reset it to `origin/main` |
| Consolidation trigger | nightly curator cron on the curator host (agent run, model-pinned): reads every transport branch completely, writes one `main` commit, resets the consumed branches |
| Commit granularity | one staging commit per sweep (the ledger holds hashes, not intermediate contents — per-run commits are unreconstructable, so the sweep commits the current content per path, once); one curator commit per night |
| Commit message | names the skills whose files actually changed; ledger entry IDs ride in the trailers for attribution and recovery |
| Overlap | the curator's problem by design: one home per rule when two machines touched the same file; never `-X ours`/`-X theirs`, never a force-push of `main` |
| Gate before `main` | `--preflight`: instance pointers, dangling references, duplicate rules, ledger hash-chain findings — provenance and quality evidence; nothing reaches `main` unreviewed |
| Long sessions | the skill *index* is a start-of-session snapshot (prompt-cache invariant); skill *bodies* load from disk, so `/skill-name` always yields current content. Never pull mid-session to "fix" an index |

Two design facts the failure modes establish, worth keeping when this is next redesigned:

- Provenance must hold without old ledger entries matching current `HEAD` — the chain is evidence
  for the curator, never a hold on transport. The ledger selects and attributes paths; it cannot
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
| `scripts/skill-repo-consolidate.py` | the curator's helpers: `--collect`, `--preflight`, `--reset-branch` |
| `<hermes home>/bin/skill-repo-sync` | stable wrapper the hooks call (a shell script that execs the engine) |
| `<hermes home>/skill-repo-sync.json` | state: repos, wrapper, engine path, ledger cursor, versions |
| `<hermes home>/skills/.curator_ledger.jsonl` | mutation ledger (written by Hermes, read here) |

The wrapper path must stay constant: the hook consent pair is `(event, command)`, so changing the
command needs fresh consent. Update the engine in the repository — never the wrapper.

## Modes

```bash
python3 scripts/skill-repo-sync.py --version          # engine version
python3 scripts/skill-repo-sync.py --selfcheck        # install state, repos, wrapper, ledger cursor
python3 scripts/skill-repo-sync.py --stage            # hourly sweep: ledger paths + dirty worktree → one commit on machine/<name>, push
python3 scripts/skill-repo-sync.py --sync-from-main   # on_session_start: fetch; consumed transport branch → reset to origin/main
python3 scripts/skill-repo-consolidate.py --collect   # curator: the pending ledger paths for tonight's commit
python3 scripts/skill-repo-consolidate.py --preflight # curator: review gates over the planned content
python3 scripts/skill-repo-consolidate.py --reset-branch  # curator: reset a consumed transport branch to origin/main
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
   every hour · no_agent: true · script: <repo-root>/skill-repo-sync-stage.sh
   deliver: telegram (empty stdout sends nothing)
   ```

   The script must live where the job resolves it (a shell script at the repository root that execs
   the engine's `--stage`); a `--script` job resolves against the job's workdir, not the profile.

2. **Nightly curator** — the curator host only, an agent run:

   ```text
   nightly · skills: [skill-library-maintenance] · workdir: <repo> ·
   pinned --provider/--model · deliver: telegram · failure-deliver: telegram
   ```

   Pin the model (`hermes cron create/edit --provider <P> --model <M>`): an unpinned agent job
   resolves the config route at fire time and fails closed when `model.*` changes underneath it.
   Verify a job's recorded fields in `~/.hermes/cron/jobs.json` — `hermes cron status` shows the
   scheduler, not one job. Back `jobs.json` up before removing a job: its prompt often embeds
   procedure that exists nowhere else.

## Curator run book (what the nightly job must do)

1. `git fetch origin`; checkout `main`; fast-forward pull.
2. Per transport branch: read the **complete** diff against `main` (`git log/diff main...<branch>`),
   every file — a summary of a diff is not a review.
3. Decide each change: keep, rewrite, or drop-with-reason. Dedupe across branches — two machines
   editing the same file is the one real overlap; only intersecting files can conflict. One home per
   rule, and a SemVer increment beyond both sides when the result combines their changes.
4. `--collect` + `--preflight` over the planned content; zero gate findings before touching `main`.
5. Apply to the `main` working tree; bump each changed package.
6. **One** commit on `main` naming the packages and the source branches; push.
7. `--reset-branch` each consumed transport branch and push the resets. The reset is the only
   sanctioned force and is lease-guarded; it refuses to drop commits not already reachable from
   `main` (exact check: the script header).
8. Leave the checkout clean and report: consolidated, dropped (with reasons), deferred.

Failure discipline: no `main` commit and no resets on any error — the transport branches stay
consumable and the retry is the next night's run. Fix, then re-run; never force anything by hand.

## Manual integration (fallback: curator blocked, or a hotfix now)

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

## Diagnosing a stuck sync

When sync has silently stopped, rebuild causality from the ledger and git history before trusting
any explanation — a report or design draft names the most recent visible event, while a frozen
cursor date marks where the failure actually began.

1. Read the state file: compare `ledger_cursor` and its timestamp against the ledger's entry count
   and newest entry. A frozen cursor while entries keep arriving means runs have failed since the
   cursor date, not since the last visible error. A cursor behind the ledger with staging green is
   the opposite case — it self-heals on the next sweep.
2. `git log --format='%ci %s'` on the transport branch and on `main` separately. Stage commits
   growing locally while `origin/machine/<name>` is stale means push failures, not staging failures.
   `main` unchanged while transport branches accumulate means the consolidation is failing — the
   branches stay consumable and nothing is lost.
3. Localize a chain break from `--preflight` findings: hash every pending entry's before/after
   values against the path's blob history (`git log --format=%h -- <path>`, then
   `git show <rev>:<path>`). The first entry whose before-hash matches neither the preceding
   entry's after-hash nor any blob at its time marks where a commit outside the ledger intervened.

Pitfalls:

- **A before/after hash chain assumes a single writer per branch.** Any commit made outside the
  ledger — audit, manual fix, merge — inserts a blob state the chain does not know. Under Stage &
  Curate this surfaces as `--preflight` findings and provenance gaps, not a transport stall — but
  the chain can no longer prove who changed a line across the break, so attribute such a change
  from the commit and the worktree, not from ledger entries alone.
- **A clean `main` checkout is the curator host's normal state between runs; a dirty `main` is a
  decision.** The sweep and the session hook no-op on a clean `main` and refuse a dirty one — do not
  "fix" the refusal by checking out a transport branch, which would silently assign main work to
  the machine branch. Feature work on `main` gets checked out explicitly, once.
- **The sweep transports everything dirty.** It cannot tell an experiment from a finished edit:
  worktree debris rides into the next transport commit, and scratch directories inside the repo
  (`.consolidate-scratch/`, pytest caches) belong in `.gitignore` or they are committed too. Keep
  the worktree free of debris; commit or stash work-in-progress deliberately.
- **A transport branch is not a place to keep work.** It is reset after consumption — anything left
  uncommitted in the tree survives (the reset is branch-level), but commits not yet consumed do not:
  land unfinished work as a `WIP` commit on the transport branch so the sweep and the curator see it,
  never as a side branch nobody watches.

## Removing it

```bash
cp <hermes home>/cron/jobs.json ~/backups/cron-jobs-$(date +%Y%m%d-%H%M%S).json
hermes hooks revoke <hermes home>/bin/skill-repo-sync
hermes config set hooks.on_session_start '[]'
hermes config set hooks.on_skill_lifecycle '[]'    # only if a v1 install left an entry
hermes cron remove <staging sweep job> [<curator job>]
rm <hermes home>/bin/skill-repo-sync <hermes home>/skill-repo-sync.json
```

The repository keeps its commits (including the transport branches); nothing else is left behind.
