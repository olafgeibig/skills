# Publishing a Skill

How reviewed bytes reach the canonical repository: an authorized, exactly scoped transfer that ends
with a verified commit and, only if authorized, a read-back from the remote.

## When to load

The review passed and the user authorized publication of the reviewed bytes. Without that
authorization, nothing in this file may run.

## Preconditions

- A review verdict exists and names the reviewed version.
- The working copy is unchanged since the review. If it changed, go back to the review.
- The canonical repository path, branch and package path are known; the working tree and index were
  inspected read-only before the transfer.
- The user knows the commit will be local unless a push is separately authorized.

## Steps

1. **Confirm the target and the boundary.** Resolve the canonical checkout (`git -C <skill_dir>
   rev-parse --show-toplevel` on the canonical package, not the local copy). Read `git status
   --short --branch`. Unrelated dirty files stay untouched — they are not part of the publication
   and must survive it.
2. **Transfer exactly the reviewed package.** Write the reviewed files into the canonical package
   path, including deletions: a reference or template removed in review must be removed here too,
   or the publication is not the reviewed package. A new skill is added as a complete package; an
   existing one is updated in place under the same name — never as a parallel identity.
3. **Disclose the direct-write ledger caveat.** A filesystem write into the canonical repository has
   no native `skill_manage` ledger entry. Say so in the report; do not imply a native rollback
   exists. Git is the record for this transfer.
4. **Verify source and target.** Read the canonical package back and compare it with the reviewed
   copy: same file list, same content, no leftovers from the old version. Validate it in place with
   the package's validator and the library audit (commands in `references/audit-library.md`).
5. **Stage explicit paths only.** `git add -- <exact file paths>`, including removed paths and the
   files added since the baseline. Never `git add .`, `-A` or a directory wildcard across a shared
   tree. Inspect `git diff --cached --name-status` and `git diff --cached` and prove they equal the
   reviewed file list.
6. **Commit without a pathspec.** Once the index contains exactly the intended files, run the commit
   without `-- <path>`. Caveat: `git commit -- <path>` commits the **working-tree** content of every
   path under that pathspec, not just the index — an unrelated edit under the same directory rides
   along. If the index is right, a pathspec adds risk and no safety.
7. **Verify the commit, not the staging step.** `git show --name-only <sha>` must list exactly the
   reviewed paths. The staging step is what can be wrong; the commit is the evidence.
8. **Push only when separately authorized.** A local commit is a complete publication to the
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
- **Do not re-lock here.** The lock is keyed by name, and the same-name working copy still exists;
  locking now would lock that copy and block its removal. Closing owns the order.
- **Do not use the bare name as a target.** While the working copy is open, `skill_manage` resolves
  the name locally. Publication is an explicitly targeted repository operation.

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
