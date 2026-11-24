# Closing a Development Phase

How a phase ends with the canonical skill active and (unless intentionally left unlocked for
burn-in) locked again.

## When to load

Publication is verified, or the phase is deliberately abandoned. Not before: a phase whose review
is unresolved or whose publication is unverified is still open.

## Branch A — Existing canonical skill(s) edited in place

There is no local copy to remove; edits live directly in the canonical checkout.

### Published

1. **Verify the canonical state.** Confirm `git status --short --branch` is clean for the published
   paths, `HEAD` is the verified commit (or merged into `main`), and `skill_view` resolves the
   canonical package with the published content.
2. **Re-lock (unless intentionally kept unlocked for burn-in).** Output copy-paste
   `hermes curator lock <skill>` commands (one per skill) — or
   `python3 skills/skill-governance/scripts/bulk-lock.py restore <skills-dir>` if the user
   temporarily bulk-unlocked the repo. Read `hermes curator status` back to verify.

### Abandoned

Unpublished edits live directly in the active canonical checkout — **re-locking alone does NOT
revert them.**

1. **Decide disposition with the user.** Ask explicitly whether to preserve the unpublished work
   (keep the `edit/*` / `improve/*` branch unmerged, or save a `git diff` patch outside skill
   discovery) or discard it completely.
2. **Restore the intended canonical state.** Prepare the exact user-executed Git commands (repo-root
   Git mutations are guarded while sibling skills are locked):
   - If on an `edit/*` or `improve/*` branch: commit or discard working-tree changes per step 1,
     then `git -C <repo> switch main` (and optionally delete the abandoned branch if discarding).
   - If edits were made directly on `main`: `git -C <repo> checkout -- <exact paths>` and remove
     any untracked files belonging solely to the abandoned phase.
3. **Verify the active source.** Confirm `git status --short --branch` and `skill_view` resolve the
   canonical package at its intended pre-phase content.
4. **Restore the prior lock state.** Output copy-paste `hermes curator lock <skill>` commands for
   each skill that was locked before the phase, then read `hermes curator status` back.

## Branch B — Brand-new skill developed profile-local

For a brand-new skill developed in `$HERMES_HOME/skills/local/<name>/`, the local copy leaves
discovery while it is still unlocked, the canonical source is read back, and the lock is set on
the canonical package last. Two branches end here — published and abandoned — and they share the
same order.

### Preconditions (Branch B)

- The phase record exists and states the intended ending.
- For a published phase: the canonical commit is verified and the canonical package contains the
  reviewed bytes.
- For an abandoned phase: the user has decided to abandon, and the disposition of the local work is
  explicit — preserved, or discarded with the user's explicit approval.
- The local copy is still unlocked. If it was locked early, generate the copy-paste
  `hermes curator unlock <name>` command and wait rather than working around it.

## Order that matters

A lock is keyed by skill **name**. While a same-name local copy exists, locking the name locks the
copy and then blocks its removal. So: copy first, lock last.

**Before any deletion, resolve the name.** The tool must report the **local copy**, never the
canonical package. The canonical package is unlocked during the phase, so once the copy is gone the
bare name resolves there — a repeated `skill_manage delete` would recursively delete the checkout.
Prove the resolved path, then delete once.

## Published branch

1. **Prove the canonical destination.** Read the canonical package back and compare it with the
   reviewed copy, file for file, including deletions. If the remote was part of the publication,
   read the remote commit id and file list back. A local commit that was never pushed is a verified
   local publication and must be called that.
2. **Keep a recovery copy.** Write a tarball of the complete local package outside skill discovery
   (a plain archive, never `hermes curator archive`, which is a lifecycle operation on the name) and
   verify it against the package — file list and hashes — before deleting anything.
3. **Remove the local copy from active discovery while it is unlocked**, after the resolved-path
   check above. `skill_manage delete <name>` in the foreground is **not** archival: it recursively
   deletes the package. That is
   acceptable here only because the reviewed package is already preserved in its verified canonical
   destination and a recovery copy exists. Never use it as an archive step.
4. **Read the source back.** `skill_view` must resolve the canonical package again, its content must
   be the published content, and the declaration audit must report no local override for that name.
5. **Set the lock last (unless left unlocked for burn-in), then read the target back.** Use the
   supported CLI for the canonical name; the locked directory must be the canonical package
   directory, not a path that no longer exists. A successful command is not the evidence — the
   read-back is.

## Abandoned branch

1. **Preserve a recoverable complete copy first.** Unless the user explicitly approves discarding the
   work, write a tarball of the complete local package outside discovery (a plain archive, not
   `hermes curator archive`) and verify it against the package — file list and hashes. A partial copy
   is not recovery.
2. **Remove the local copy while it is unlocked**, as above — deletion, after preservation and the
   resolved-path check.
3. **Read the source back.** For a released skill, `skill_view` must resolve the canonical package;
   closing the phase must have left it as it was. Abandonment after a deliberate canonical update is
   allowed: if the canonical package was deliberately updated during the phase, it legitimately
   differs from the phase-start baseline — record which commit is now active and why; what must not
   differ is the canonical package versus itself before and after this cleanup. For a new skill there
   is no canonical package to resolve: the name must resolve to nothing, and the recovery tarball is
   the only artifact left.
4. **Restore the prior lock state** recorded at open, then read the target back. A new skill never
   had one: record that no lock is set and do not invent one. There is no remote commit to check and
   no published content to compare.

## Verification

- `skill_view` resolves the canonical package and nothing else under that name — for a released
  skill. For a new skill it resolves nothing, and no lock entry exists under that name.
- The declaration audit reports no override for the name.
- The lock target read back is the canonical package directory (released skill); a new skill has no
  lock target to read.
- A recovery archive exists for every package that was deleted, and its hashes match.
- The phase record is closed with: ending, canonical commit (or "abandoned"), recovery location,
  lock state.

## Stop and recovery

- **Restart from state, not from memory.** Read what still exists — local copy, canonical target,
  recovery archive, lock target — before continuing an interrupted close; a half-run close is a state
  to inspect, never a sequence to replay.
- Do not run `hermes curator archive <same-name>` after the copy has been removed or moved: archive
  and usage state are keyed by name, and archiving can hide or mislabel the released skill that now
  carries the name. Leave `.usage.json` and the ledger under native management.
- Cleanup incomplete — copy still resolvable, source not read back, lock target wrong: report the
  phase as blocked. Never declare the profile back on the release.
- The copy cannot be removed because it is locked: stop and ask the user to unlock. Do not bulk
  unlock, rewrite state files, or delete the path behind the tool's back.
- Three failed attempts on the same step: stop and report the real error and the exact path.
