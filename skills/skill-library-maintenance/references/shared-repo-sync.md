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
| `main` | the only long-lived branch; no per-installation branches |
| Publish trigger | `on_skill_lifecycle` shell hook → seconds after a successful skill mutation |
| Refresh trigger | `on_session_start` shell hook (`--pull-only`) + the hourly safety cron |
| What gets committed | **only paths named by the mutation ledger**; hand-written work in progress is never swept in |
| Commit granularity | one commit per review run (writes grouped by ≤120 s gap) so `git revert <sha>` is surgical |
| Commit message | names the skills whose files actually changed, plus `Review-Run: <timestamp>` |
| Conflict | `git rebase --abort`, a note in `.git/hermes-skill-sync-conflict.json`, report — **never** resolve by choosing a side |
| Gate before commit | instance pointers, dangling references, duplicate rules — flagged files are held back, never committed |
| Long sessions | the skill *index* is a start-of-session snapshot (prompt-cache invariant); skill *bodies* load from disk, so `/skill-name` always yields current content. Never pull mid-session to "fix" an index |

## Files

| Path | Role |
|---|---|
| `scripts/skill-repo-sync.py` | the engine; `SCRIPT_VERSION` in the header |
| `scripts/install-skill-repo-sync.py` | installer; `INSTALLER_VERSION` must match the engine |
| `<hermes home>/bin/skill-repo-sync` | stable wrapper the hooks call (a shell script that execs the engine) |
| `<hermes home>/skill-repo-sync.json` | state: repos, wrapper, engine path, ledger cursor, versions |
| `<hermes home>/skills/.curator_ledger.jsonl` | mutation ledger (written by Hermes, read here) |
| `<repo>/.git/hermes-skill-sync-report.json` | gate findings of the last blocked run |
| `<repo>/.git/hermes-skill-sync-conflict.json` | marker of an aborted rebase |

The wrapper path must stay constant: the hook consent pair is `(event, command)`, so changing the
command needs fresh consent. Update the engine in the repository — never the wrapper.

## Modes

```bash
python3 scripts/skill-repo-sync.py --version      # engine version
python3 scripts/skill-repo-sync.py --selfcheck    # install state, repos, wrapper, ledger cursor
python3 scripts/skill-repo-sync.py --safety       # default: commit ledger paths, pull --rebase, push
python3 scripts/skill-repo-sync.py --pull-only    # session-start refresh (fast-forward only)
python3 scripts/skill-repo-sync.py --audit        # report only: review commits since the last audit + defect scan
python3 scripts/skill-repo-sync.py --dry-run --verbose
```

Exit codes: `0` ok/no-op · `10` gate findings (flagged files held back) · `11` rebase conflict
(aborted, note written) · `12` other error · `13` not installed.

## Install (once per machine)

```bash
cd <repo>/skills/skill-library-maintenance/scripts
python3 install-skill-repo-sync.py --apply-config          # wrapper + state + config entries
hermes hooks list                                          # both entries, consent status
hermes hooks doctor                                        # exec bit, allowlist, stdout cleanliness
python3 skill-repo-sync.py --selfcheck --verbose
```

`--apply-config` writes `hooks_auto_accept: true` plus the two hook entries through
`hermes config set` (idempotent; it skips an entry that already names the wrapper). Additional
shared repos: repeat `--repo /path/to/other/repo` — the installer skips any repo without a remote,
because a repo nobody pushes to can never conflict.

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

## When it stops: resolving a conflict

A conflict means two installations changed the same region of the same file. The procedure:

1. `git fetch` and read both sides: `git log --oneline HEAD..origin/main` and the conflicting hunks.
2. Merge so **both lessons land** — one home per rule, order by what the rule governs. Never
   `-X ours`/`-X theirs`, never a force-push: that deletes the other installation's lesson silently.
3. Verify: `python3 scripts/audit-skill-declarations.py --strict`, the `skills-ref` validator for
   every touched skill, the fork's tests where one exists, and a re-read of the merged file.
4. Commit, push, delete the marker file, and re-run `--selfcheck`.

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
