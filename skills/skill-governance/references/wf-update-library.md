# Updating a Released Library

How a consuming profile or checkout moves to a newer released version without losing local work,
overwriting an open local phase, or bulk-unlocking from the agent.

## When to load

A consuming checkout or profile should move to a newer released version, or a released skill needs
its lock in a profile that does not have it yet. This is the steady-state path; it is not
development and it does not publish.

## Preconditions

- The target checkout is known: resolve it with `git -C <skill_dir> rev-parse --show-toplevel`
  starting from a fresh `skill_view` result. Discovery roots can be nested inside a checkout.
- You know which skills in this profile have an open local phase (e.g. a brand-new skill before
  close). An open local package must not be overwritten by an update; that is a reconciliation case.
- Read-only Git only until the guard question is settled.

## Read-only versus blocked Git

- **Allowed without any unlock:** `git fetch <remote>`, `git status`, `git diff`, `git log`,
  `git rev-parse`, `git ls-remote`. Use these to learn the real relationship between the checkout,
  its upstream and the remote.
- **Blocked while any locked skill sits below the repository root:** `git pull`, `git merge`,
  `git checkout`, `git switch`, `git reset`, `git add`, `git commit` — regardless of the paths
  involved. The guard treats repository-root Git mutation as a write to every locked descendant and
  inspects the whole command, so a compound command that mixes a guarded write with unrelated reads
  is refused in full. Split it; do not conclude the read-only parts failed.

## Steps

1. **Refuse a dirty checkout.** `git status --short --branch` must be clean before an update. Dirty
   work is preserved, never stashed, reset or committed as a side effect. If it is dirty, report the
   paths and stop: the owner decides what happens to them.
2. **Protect open local phases.** For any skill with a local package in `$HERMES_HOME/skills/`,
   the update must not touch it. A same-name local package shadows the canonical one, so the update
   changes the checkout without changing what loads — say that explicitly instead of claiming the
   profile was updated.
3. **Fetch, then compare.** `git fetch <remote>` only when the remote is the intended one; if the
   fetch fails, label the tracking ref as cached rather than claiming current remote state. Compare
   with `git rev-list --left-right --count HEAD...@{upstream}` and read the incoming commits before
   applying them.
4. **Apply or hand over the update.**
   - **Clean fast-forward, no locked skills blocking:** run `git -C <repo> merge --ff-only @{upstream}`.
   - **Clean fast-forward, locked siblings blocking:** hand the user the exact command
     (`git -C <repo> merge --ff-only @{upstream}`) and note that skills do not need to be unlocked
     for the user to run it.
   - **Divergence or conflicts:** stop, report the conflicting commits/files, and discuss
     resolution with the user. Default is for the user to run the merge/resolution commands without
     changing locks. If the user explicitly wants the agent to resolve conflicts directly, the user
     can run `python3 skills/skill-governance/scripts/bulk-lock.py unlock <skills-dir> -p <profile>`
     beforehand and
     `python3 skills/skill-governance/scripts/bulk-lock.py restore <skills-dir> -p <profile>`
     afterwards (restores only previously locked skills). Never bulk-unlock from the agent, and
     never rebase or force-push on your own.
5. **Verify afterwards, on the real path.** Re-run `git status`, `git log -1`, and the declaration
   and library audits. `skill_view` each affected skill from a fresh session and confirm the
   resolved path and the version that actually loads. A fetched revision is not an installed
   revision, and a successful pull is not an activated profile.
6. **Set new locks.** A newly released skill needs its lock in every consuming profile — Git does
   not carry profile lock records. Set it through the supported CLI and read the target back; do not
   infer lock state from the repository.

## Cases

- **Lost or mismatched source:** the checkout does not exist, resolves elsewhere, or does not match
  the recorded baseline. Stop and reconcile before any update; updating an unknown tree can destroy
  someone's work.
- **Divergence:** both counts non-zero means integration is a decision, not an update. Report it and
  let the user choose; no rebase, no force, no history cleanup.
- **A locked sibling blocks the command:** the operator runs it, you verify. A refusal is the guard
  working, not a broken tool.

## Verification

- The checkout is clean before and after, and `HEAD` is the intended released commit.
- No open local phase changed content; each still resolves locally.
- Audits report no new collision or unintended override.
- Every newly released skill's lock target reads back as its canonical package.

## Stop and recovery

- Dirty checkout: stop before touching anything.
- A pull that fails or leaves a conflicted state: report it, do not reset or abort on your own.
- Three failed attempts on the same command: stop and report the real error.
- Nothing here authorizes a push, a rollout, or a claim that another machine is updated.
