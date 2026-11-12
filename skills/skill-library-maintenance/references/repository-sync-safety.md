# Shared Repository Safety

Rules for operating on a skill repository that another profile, another machine or another program
also touches. Applies to any deliberate operation that moves content between working tree, index,
commit and remote — not only to skill publication.

This is not a sync design. There is no unattended integration process in this library; every write
here is authorized and reviewed per `skill-development-lifecycle.md`.

## Establish the boundary before writing

```bash
git status --short --branch
git diff --name-status
git diff --cached --name-status
git remote -v
git branch -vv
```

Fetch only the intended remote, then compare the checkout with its intended integration branch. A
fetched revision is not an installed revision — read the runtime-loaded copy separately. Preserve
dirty work before merging or switching branches; never reset, rebase or stash it implicitly.

Identify the other writers before editing shared files: scheduled jobs, the background review, other
profiles and manual fixes. Correlate an unexpected change with paths, timestamps and mutation
details in `<HERMES_HOME>/skills/.curator_ledger.jsonl` before attributing it — neither the changed
skill's name nor `actor: curator` alone establishes provenance.

## Commit discipline

- Stage explicit paths. `git add .` and `-A` are how unrelated work gets swept into an authorized
  commit.
- A clean tree does not mean pushed, and a local commit does not prove its content is absent
  remotely — another branch may have merged or cherry-picked it. Report working tree, local
  commits, and integration separately.
- Quote commit messages so the shell cannot rewrite them: backticked identifiers inside double
  quotes are command substitution and vanish. Use single quotes or a heredoc when the message names
  code.
- Name the remote in scripted pushes. `git push <sha>:<ref>` parses the sha as an scp-style host and
  dies on DNS resolution; write `git push origin <sha>:<ref>`.
- Use `git mv` only for tracked paths. Keep destructive cleanup separate from read-only validation.
  Do not drop stashes or backups without explicit consent.

## Isolated probes

Any claim that a Git or lifecycle operation behaves safely needs a probe, not a reading.

1. Create a temporary directory under the session scratch root with
   `tempfile.TemporaryDirectory(dir=...)`.
2. Inside it, create a disposable Git repository, a separate Hermes home, and a local bare remote.
   Set the Git identity repository-locally.
3. Seed a minimal fixture — one committed skill, one appended change. Never use the live profile's
   state, and never guess a state schema.
4. Run the operation with `subprocess.run` and an explicit environment containing the isolated
   `HERMES_HOME`. Capture stdout, stderr and the return code.
5. Compare state files, `git status --porcelain`, `git diff --cached`, `HEAD` and the bare-remote
   refs **before and after**. An exit code alone cannot demonstrate non-mutation.
6. Keep every push inside the disposable local remote.

## What a green result does and does not prove

- A dry run that changes nothing is the baseline; a successful run is not.
- A green suite proves its own contract, not the intended one. Read what the tests assert as
  *required behavior* before trusting them — a suite can encode unsafe policy (automatic stale-lock
  deletion, blanket hook clearing, silent bootstrap, reset heuristics that discard unpushed work) as
  correct. When a fix changes that policy, rewrite the affected assertions explicitly with a
  rationale; deleting or weakening them to keep the suite green leaves the old policy as the tested
  contract.
- Prove the worktree, not the scratch: an apply step that writes per-file scratch artifacts can
  silently omit clean files, deletions or empty files and still exit 0. After every apply step
  assert `git status --porcelain`, the exact contents of every manifest path, and the remote refs
  against the expected result. Distinguish a deleted blob from an intentionally empty file by asking
  Git (`git cat-file -e <rev>:<path>`), never by scratch-file size.
- A zero exit code, a quiet hook or a present script is not evidence of activation. Read the
  effective configuration back.

## Consent and unattended operation

Inspect the exact hook delta. Prefer consent for individual `(event, command)` pairs over enabling
global `hooks_auto_accept`; a global opt-in also approves unrelated hooks. Verify the active Hermes
consent format against current documentation before changing an allowlist.

Do not treat lock state, adoption, pinning and write approval as one permission — they are four.

## Report precisely

Separate syntax validation, isolated behavioral tests, integration into the checkout, and activation
in the profile. State which revision was inspected, which assertions were exercised, and which
remain untested. Record durable acceptance rules here, not machine-specific backlog counts or
transient defects in a particular release.
