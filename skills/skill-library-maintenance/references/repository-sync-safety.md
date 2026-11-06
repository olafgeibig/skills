# Repository Sync Safety Review

Use when reviewing or enabling automation that pulls, commits, or publishes skill repositories.

## 1. Establish the integration boundary

Inspect the intended repository with:

```bash
git status --short --branch
git diff --name-status
git diff --cached --name-status
git remote -v
git branch -vv
```

Fetch only the intended remote, then compare the current checkout with its intended integration branch. Read the fetched script and the runtime-loaded skill separately: a fetched revision is not an installed revision. Preserve dirty work before merging or switching branches; do not reset or stash it implicitly.

Inspect the installer as well as the engine. Identify state files, ledger cursor initialization, hook commands, consent changes, scheduler entries, branch selection, upstream selection, and credential use before executing either component.

## 2. Build an isolated behavioral probe

1. Create a temporary directory under the session scratch root with `tempfile.TemporaryDirectory(dir=...)`.
2. Inside it, create a disposable Git repository, a separate Hermes home, and a local bare remote if publication needs testing. Set Git identity repository-locally.
3. Commit a minimal skill fixture, modify a tracked skill file, and seed the isolated ledger and sync configuration using the inspected implementation's schema. Never guess that schema or use the live profile's state.
4. Run the engine with `subprocess.run`, passing an explicit environment containing the isolated `HERMES_HOME`. Capture stdout, stderr, and return code.
5. Compare state-file bytes, ledger cursor, `git status --porcelain`, `git diff --cached`, HEAD, and bare-remote refs before and after. An exit code alone cannot demonstrate non-mutation.
6. Keep all pushes inside the disposable local remote. Do not run the installer against a live profile merely to discover its side effects.

A minimal probe needs only one committed file, one appended change, one ledger entry naming that file, and an initial cursor. Run dry-run and compare the cursor, then run `--stage` to prove the sweep bundles the change into one transport-branch commit and advances the cursor.

## 3. Behavioral acceptance matrix

| Case | Required result |
|---|---|
| Dry-run with pending work | Reports intended actions without changing cursor, config, index, HEAD, fetch state, or remote refs. |
| Missing sync state | Installer refuses unless the operator explicitly chooses `--bootstrap-current-ledger`; that baseline skips all historical entries. |
| Ledgered file change | `--stage` commits the path's current content with the ledger entry IDs in the commit trailers; the hash chain stays verifiable evidence for `--preflight`, never a hold on transport. |
| Multiple pending runs touch one file | The sweep commits the path's current content once — no per-run reconstruction (the ledger has no intermediate snapshots) and no hold on other paths. |
| Manual and ledgered edits share a file | Both ride along in the staging commit; attribution names the path and the ledger ids, not each change inside it. |
| Review gate finding (instance pointer, dangling reference, duplicate rule) | `--preflight` reports it visibly and the consolidation stays blocked; nothing reaches `main` unreviewed. |
| Unexpected branch | `--stage` refuses a dirty `main` checkout and no-ops on a clean one (the curator host's normal state); a transport branch runs only as `machine/<hostname>`. |
| Cursor behind the ledger | The next sweep advances it over the entries it bundles — a stale cursor self-heals instead of replaying old content. |
| Staging commit made, push fails | The commit is preserved and the retry pushes it without creating a duplicate. |
| Transport branch consumed upstream | `--sync-from-main` resets the local branch to `origin/main`; dirty worktree content is never discarded (observer-only). |
| Curator finds overlapping edits in two transport branches | Resolves to one home per rule and a SemVer increment beyond both; never `-X ours`/`-X theirs`, never a force-push of `main`. A resolution it cannot make stops the run before any `main` commit. |
| No prior sync cursor exists | Historical path membership never authorizes today's dirty content; bootstrap is an explicit skip-history choice. |

Repeat a blocked case after correcting the fixture to verify actual retry, not just preservation of an integer cursor. For push failure and conflict recovery, assert that the retry creates no duplicate review commit, the remote reaches the resolved local HEAD, and the cursor advances only after publication succeeds.

Preserve successful disposable-repository probes as bundled regression tests rather than leaving them as scratch commands; retry and cursor defects require a repeatable sequence of runs. Run `python3 -m pytest skills/skill-library-maintenance/tests -q` from the repository root after the final engine or installer edit. Treat the passing suite as behavioral evidence only; run the package validator and library audit separately before declaring the skill change complete.

## 4. Consent and unattended operation

Inspect the exact hook configuration delta. Prefer consent for individual `(event, command)` pairs over enabling global `hooks_auto_accept`; a global opt-in also approves unrelated hooks. Verify the active Hermes consent format against current documentation before changing an allowlist.

Check the installed scheduler and hooks independently. Script presence does not prove either is enabled. After authorized installation, read back the exact configuration, registration, and state targets before claiming deployment success.

## 5. Report precisely

Separate syntax validation, isolated behavioral tests, integration into the checkout, and activation in the profile. State which revision was inspected, which assertions were exercised, and which remain untested. Record durable acceptance rules here, not machine-specific backlog counts or transient defects in a particular release.
