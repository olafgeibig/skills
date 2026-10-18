# Shared skill repo: publishing and cross-installation sync

Applies when the same skill repository is mounted on more than one Hermes installation
(`skills.external_dirs`). It keeps the repositories current without a manual `git pull` and without
uncommitted review sediment, and it bounds what a conflict can cost.

## The problem this solves

The **background review** writes lessons into skills directly through `skill_manage` — including
skills that live in a shared, git-versioned repository. Two consequences, both observed:

1. Nothing publishes those writes: they sit in the working tree until someone commits them. Left
   alone for days, they collide with whatever the other installation pushed.
2. Two installations editing the same file is the only real conflict source, and it is a *file*
   property, not a frequency property: branches do not remove it, they defer it into a larger merge.

Symptoms worth recognising: `git status` shows changes to `skill-governance` / `skill-builder` /
`skill-library-maintenance` that no human made. Attribute them from the mutation ledger
(`<hermes home>/skills/.curator_ledger.jsonl`), not from the ledger's `actor` field — review writes
are also recorded as `actor: curator`.

## Architecture (what must stay true)

| Piece | Rule |
|---|---|
| `main` | the only long-lived automation branch; every write operation requires `main` tracking `origin/main` |
| Publish trigger | `on_skill_lifecycle` shell hook → seconds after a successful skill mutation |
| Refresh trigger | `on_session_start` shell hook (`--pull-only`) + the hourly safety cron |
| What gets committed | only ledger paths whose before/after SHA-256 chain matches the `HEAD` blob and worktree; staged or unrelated changes stop the run |
| Commit granularity | one commit per review run when each path has one pending run; multiple pending runs touching the same file are held because the ledger has no intermediate content snapshots |
| Commit message | names the skills whose files actually changed, plus `Review-Run: <timestamp>` and `Ledger-Entries: <ids>` for retry/recovery |
| Conflict | fetch, rebase onto `origin/main`, abort an actual conflicted rebase, write a marker — never resolve by choosing a side; ordinary fetch/push errors are not conflicts |
| Gate before commit | instance pointers, dangling references, duplicate rules, and exact ledger hash validation; a blocked run stays pending |
| Long sessions | the skill *index* is a start-of-session snapshot (prompt-cache invariant); skill *bodies* load from disk, so `/skill-name` always yields current content. Never pull mid-session to "fix" an index |

## Platforms

Written for Linux and macOS alike — an installation may be either, and the two home layouts differ.

- Nothing is hardcoded: the Hermes home comes from `$HERMES_HOME` (falling back to `~/.hermes`),
  repositories are resolved with `git rev-parse --show-toplevel`, and every absolute path is
  recorded per machine in the state file.
- The gate's instance-pointer patterns cover `/home/<user>` **and** `/Users/<user>`, so a rule that
  leaks a local path is caught whichever installation writes it.
- Both hook events and the cron jobs are Hermes-level features — nothing goes into `crontab` or
  `launchd`.
- The wrapper execs `python3` from `PATH`; a missing one falls back to the interpreter that ran the
  installer, and `--python` pins an explicit binary. Relevant on macOS: without the Xcode command
  line tools there is no `python3`, and a Homebrew python may sit outside the PATH a hook inherits.
- Every git call runs with `GIT_TERMINAL_PROMPT=0` and `GIT_SSH_COMMAND=ssh -oBatchMode=yes`, so an
  unattended hook fails fast instead of stalling on a credential or key-passphrase prompt (the
  common macOS case when the key is not in the ssh-agent).
- Paths are used exactly as git reports them — no case assumptions, which matters on a
  case-insensitive APFS volume.

## Files

| Path | Role |
|---|---|
| `scripts/skill-repo-sync.py` | the engine; `SCRIPT_VERSION` in the header |
| `scripts/install-skill-repo-sync.py` | installer; `INSTALLER_VERSION` must match the engine |
| `<hermes home>/bin/skill-repo-sync` | stable wrapper the hooks call (a shell script that execs the engine) |
| `<hermes home>/skill-repo-sync.json` | state: repos, wrapper, engine path, ledger cursor, versions |
| `<hermes home>/skills/.curator_ledger.jsonl` | mutation ledger (written by Hermes, read here) |
| `<repo git-dir>/hermes-skill-sync-report.json` | gate/hash findings of the last blocked run |
| `<repo git-dir>/hermes-skill-sync-conflict.json` | marker of an aborted conflicted rebase |

The wrapper path must stay constant: the hook consent pair is `(event, command)`, so changing the
command needs fresh consent. Update the engine in the repository — never the wrapper.

## Modes

```bash
python3 scripts/skill-repo-sync.py --version      # engine version
python3 scripts/skill-repo-sync.py --selfcheck    # install state, repos, wrapper, ledger cursor
python3 scripts/skill-repo-sync.py --safety       # default: verify ledger hashes, commit, fetch origin, rebase if needed, push
python3 scripts/skill-repo-sync.py --pull-only    # session-start refresh (main/origin/main, fast-forward only)
python3 scripts/skill-repo-sync.py --audit        # report only: review commits since the last audit + defect scan
python3 scripts/skill-repo-sync.py --selfcheck --verbose
python3 scripts/skill-repo-sync.py --dry-run --verbose  # no state, index, commit, report, or remote writes
```

Exit codes: `0` ok/no-op · `10` gate findings (flagged files held back) · `11` rebase conflict
(aborted, note written) · `12` other error · `13` not installed.

## Install (once per machine)

Treat installation as a separate approval from fetching, merging, or reviewing the repository.
First pass the disposable-repository acceptance checks in `repository-sync-safety.md` against
this revision. Inspect installer configuration writes before running it; do not enable global
hook auto-accept merely to approve this publisher. Resolve historical-ledger bootstrap explicitly
so first activation cannot publish old or mixed manual edits by surprise.

```bash
cd <repo>/skills/skill-library-maintenance/scripts
python3 install-skill-repo-sync.py --bootstrap-current-ledger --apply-config
hermes hooks list
hermes hooks doctor
python3 skill-repo-sync.py --selfcheck --verbose
python3 -m pytest ../tests -q
```

For a fresh install, `--bootstrap-current-ledger` explicitly places the cursor at the current ledger end; it skips historical entries rather than publishing them. Review any old uncommitted work separately. On an existing install, omit this flag so the saved cursor is preserved. The installer refuses repositories not on `main` tracking `origin/main`.

`--apply-config` writes only the two hook entries through `hermes config set`; it never changes `hooks_auto_accept`. Approve the exact `(event, command)` pairs through Hermes' normal consent flow. For headless setup, use a verified exact-pair allowlist; do not enable global auto-accept. Additional shared repos: repeat `--repo /path/to/other/repo` — each must be on `main` tracking `origin/main` and have a remote.

The installer rewrites the wrapper only when its content actually changes: the hook consent records
the script's mtime, so a needless rewrite would show up in `hermes hooks doctor` as "script modified
since approval". If the wrapper *is* rewritten, refresh the consent —
`hermes hooks revoke <wrapper>` and approve again on the next start (or re-record the pair
programmatically) — and re-run `doctor` until it reports all hooks healthy.

The engine is stdlib-only Python 3.9+; the wrapper defaults to `python3` (pin a different
interpreter with `--python`).

## Cron (per machine, two jobs)

1. **Hourly safety** — catches anything the hook missed (hook disabled, process killed mid-write,
   a push that failed and backed off). Script-only, quiet on success:

   ```text
   every hour · no_agent: true · script: <repo>/skills/skill-library-maintenance/scripts/skill-repo-sync.py --safety
   deliver: telegram (empty stdout sends nothing)
   ```

2. **Monthly audit** — report only, never edits: review commits since the last audit plus a
   whole-repo defect scan. Run it with this skill loaded, so the follow-up session can act on it:

   ```text
   every 30 days · skills: [skill-library-maintenance] · prompt:
     "Run `python3 <repo>/skills/skill-library-maintenance/scripts/skill-repo-sync.py --audit --verbose`,
      then review the reported review commits for rules that are duplicated, non-generic (instance
      pointers) or dangling. Fix what is wrong in the repository, commit, push, and update the audit
      marker file `<repo>/.git/hermes-skill-sync-audit` with the current HEAD."
   ```

## Integrating remote lessons and resolving conflicts

Use this sequence for an explicit manual integration; keep automated conflict handling abort-only.
A temporary existing work branch is not a reason to create a permanent per-installation branch.

1. Inspect `git status --short --branch`, staged and unstaged diffs, upstream, and local identity. Commit authorized local work in coherent, explicitly staged groups before merging; do not sweep unrelated edits into a checkpoint.
2. `git fetch origin`; inspect `git log --oneline HEAD..origin/main` and the incoming diff. Merge `origin/main` into the existing work branch when preserving local commits is intended; fetching alone does not integrate remote lessons.
3. Resolve each conflict so both valid lessons land, with one home per rule. Never use `-X ours`/`-X theirs` or a force-push. Compare both package versions and choose a SemVer increment beyond both when the result combines their changes.
4. Stage resolved paths explicitly. Require an empty `git diff --name-only --diff-filter=U` and a clean `git diff --cached --check`. Enumerate changed packages from `git diff --cached --name-only`; validate every affected package and run its bundled tests. Separate compatibility findings from merge regressions.
5. Complete the merge with `git commit --no-edit`. Verify `git status --short --branch`, `git rev-list --parents -n 1 HEAD`, and `git merge-base --is-ancestor origin/main HEAD`. Reload changed skills to confirm runtime resolution.
6. Push only when authorized; verify the exact remote branch SHA afterward. Report local integration, remote publication, and automation activation as separate outcomes.

### Recovering a publisher conflict

The engine aborts a conflicted rebase and leaves its local review commit plus a conflict marker. Manually fetch and inspect both sides; merge both lessons, validate the affected skills, and commit the resolution. Then rerun `skill-repo-sync.py --safety`: it recognizes the committed ledger-entry IDs, skips replaying the review content, fetches `origin`, and pushes the resolved merge. A successful push clears the conflict marker and allows the ledger cursor to advance. Verify the marker is gone, the remote SHA matches local `HEAD`, and `--selfcheck` passes. Do not remove the marker or force-push to conceal an unresolved conflict.

Optional softening for the meta-skills only (`skill-governance`, `skill-builder`,
`skill-library-maintenance`): `.gitattributes` with `merge=union` makes purely additive list
edits merge without stopping. Price: a line both sides *rewrote* ends up duplicated and must be
cleaned up by hand — so it stays an option, not the default.

## Removing it

```bash
hermes hooks revoke /home/<user>/.hermes/bin/skill-repo-sync
hermes config set hooks.on_skill_lifecycle '[]'
hermes config set hooks.on_session_start '[]'
rm <hermes home>/bin/skill-repo-sync <hermes home>/skill-repo-sync.json
```

The repository keeps its commits; nothing else is left behind.
