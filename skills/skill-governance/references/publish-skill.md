# Publishing a Skill

How reviewed bytes reach the canonical repository: an authorized, exactly scoped transfer that ends
with a verified commit and, only if authorized, a read-back from the remote.

## When to load

The review passed and the user authorized publication of the reviewed bytes. Without that
authorization, nothing in this file may run.

## Preconditions

- A review verdict exists and names the reviewed version.
- The reviewed package is unchanged since the review. If it changed, go back to the review.
- The canonical repository path, branch and package path are known; the working tree and index were
  inspected read-only before the commit.
- The user knows the commit will be local unless a push is separately authorized.

## Steps

1. **Confirm the target and the boundary.** Resolve the canonical checkout (`git -C <repo_dir>
   rev-parse --show-toplevel`). Read `git status --short --branch`. Unrelated dirty files stay
   untouched — they are not part of the publication and must survive it.
2. **If publishing a brand-new local skill, transfer the reviewed package first.** Write the
   reviewed files into the canonical package path (including any deletions if replacing a draft),
   then read the canonical package back and compare file for file. Disclose that a direct
   filesystem write into the canonical repository has no native `skill_manage` ledger entry (Git is
   the record).
   *(For existing skills edited in place in the canonical repo, the bytes are already there.)*
3. **Validate in place.** Run the package's validator and the library audit (commands in
   `references/audit-library.md`).
4. **Stage explicit paths only.** `git add -- <exact file paths>`, including removed paths and new
   files. Never `git add .`, `-A` or a directory wildcard across a shared tree. Inspect
   `git diff --cached --name-status` and `git diff --cached` and prove they equal the reviewed file
   list.
5. **Commit without a pathspec.** Once the index contains exactly the intended files, run the commit
   without `-- <path>`. Caveat: `git commit -- <path>` commits the **working-tree** content of every
   path under that pathspec, not just the index — an unrelated edit under the same directory rides
   along. If the index is right, a pathspec adds risk and no safety.
6. **Verify the commit, not the staging step.** `git show --name-only <sha>` must list exactly the
   reviewed paths. The staging step is what can be wrong; the commit is the evidence.
7. **Push only when separately authorized.** A local commit is a complete publication to the
   checkout, not to the remote. Name the remote explicitly: `git push origin <sha>:<ref>`; a bare
   `<sha>:<ref>` parses as an scp-style host and fails on DNS. Then read the remote back
   (`git ls-remote origin <ref>` and the commit's files) and compare the remote commit id with the
   local one. If the push fails, report the work as local and unpublished — a failed push is not
   completion.

A coupled change publishes as one commit: every skill in the phase is reviewed together, staged by
its own exact paths, and committed in the same commit.

Command hygiene, for every Git command prepared for the user or run:

- Quote the commit message. Backticked identifiers inside double quotes are command substitution and
  vanish from the message; use single quotes or a heredoc when the message names code.
- `git mv` only for tracked paths; keep destructive cleanup separate from read-only validation.
- Do not drop stashes, backups or archive copies without explicit consent.

## Boundary rules that are policy, not protection

- **No push without authorization.** The lock guard does not block `push`; the no-push rule is
  explicit policy, so nothing technical stops a mistake here. Treat authorization as the only gate.
- **Locked siblings block repository-root Git writes.** With any locked skill below the repository
  root, `git add` and `git commit` at that root are refused regardless of staged paths. Do not
  unlock siblings. Hand the user the exact prepared command sequence — `git add --` with the file
  list, `git diff --cached --check`, `git diff --cached --name-status`, `git diff --cached`, then the
  commit — and verify afterwards.
- **Do not re-lock while a local new-skill copy still exists.** The lock is keyed by name; locking
  before removing the local copy locks that copy and blocks its removal. Closing owns the order.
- **For a local new-skill phase, do not use the bare name as a target for publication.** While the
  local copy exists, `skill_manage` resolves the name locally. Publication addresses the canonical
  repository path explicitly.

## Verification

- The canonical package read back equals the reviewed package, file for file, including deletions.
- The committed tree contains exactly the reviewed paths and no unrelated file.
- The validator and the library audit pass on the committed tree.
- If pushed: the remote ref resolves to the same commit id and the same file list.
- The report separates: local commit, push, and any read-back that could not be performed.

## Stop and recovery

- A failed push leaves the work local: say so, name the exact commit and remote, and stop. Do not
  retry with a different remote, force, or a transport branch.
- A commit that contains an unrelated file: stop and report; do not amend or reset without the
  user's decision.
- A rejected pre-commit check: fix the staged set, never bypass with `--no-verify`.
- Three failed attempts on the same step: stop and report the real error.
