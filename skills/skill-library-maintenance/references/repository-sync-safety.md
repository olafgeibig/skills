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

A minimal cursor probe needs only one committed file, one appended change, one ledger entry naming that file, and an initial cursor. Run dry-run, compare the cursor, then run normally to prove the same entry remains actionable.

## 3. Behavioral acceptance matrix

| Case | Required result |
|---|---|
| Dry-run with a pending entry | Reports intended actions without changing cursor, config, index, HEAD, or remote refs. |
| Validation or safety gate blocks an entry | Leaves the entry retryable, either by retaining its cursor position or recording it in a durable pending queue. |
| Earlier blocked entry followed by a valid entry | Does not lose the blocked entry when acknowledging later work. |
| Manual and ledgered edits share a file | Stops for review or isolates approved changes; staging a whole path must not silently publish manual hunks. |
| Unrelated staged file exists | Refuses or isolates it; an ordinary commit can include pre-existing staged content outside the publisher's selected paths. |
| Unexpected branch or upstream | Stops before committing or pushing; enforces the configured policy rather than relying on prose. |
| Commit succeeds, push fails | Preserves retry information and reports publication as incomplete. |
| Pull fails in quiet or hook mode | Leaves an observable failure status or durable diagnostic; quiet output must not erase failure evidence. |
| No prior sync cursor exists | Makes backlog handling explicit before processing historical entries; old path membership does not authorize today's dirty content. |

Repeat a blocked case after correcting the fixture to verify actual retry, not just preservation of an integer cursor.

## 4. Consent and unattended operation

Inspect the exact hook configuration delta. Prefer consent for individual `(event, command)` pairs over enabling global `hooks_auto_accept`; a global opt-in also approves unrelated hooks. Verify the active Hermes consent format against current documentation before changing an allowlist.

Check the installed scheduler and hooks independently. Script presence does not prove either is enabled. After authorized installation, read back the exact configuration, registration, and state targets before claiming deployment success.

## 5. Report precisely

Separate syntax validation, isolated behavioral tests, integration into the checkout, and activation in the profile. State which revision was inspected, which assertions were exercised, and which remain untested. Record durable acceptance rules here, not machine-specific backlog counts or transient defects in a particular release.
