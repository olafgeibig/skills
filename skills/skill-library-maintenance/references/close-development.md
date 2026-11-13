# Closing a Development Phase

How a phase ends with the external source active again: the working copy leaves discovery while it
is still unlocked, the source is read back, and the lock returns to the canonical package. Two
branches end here — published and abandoned — and they share the same order.

## When to load

Publication is verified, or the phase is deliberately abandoned. Not before: a phase whose review
is unresolved or whose publication is unverified is still open.

## Preconditions

- The phase record exists and states the intended ending.
- For a published phase: the canonical commit is verified and the canonical package contains the
  reviewed bytes.
- For an abandoned phase: the user has decided to abandon, and the disposition of the local work is
  explicit — preserved, or discarded with the user's explicit approval.
- The working copy is still unlocked. If it was locked early, report and stop rather than working
  around it; unlocking is the user's action (`skill-governance` → *Released Skills Are Locked*).

## Order that matters

A lock is keyed by skill **name**. While a same-name working copy exists, locking the name locks the
copy and then blocks its removal. So: copy first, lock last.

**Before any deletion, resolve the name.** The tool must report the **local working copy**, never the
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
3. **Remove the working copy from active discovery while it is unlocked**, after the resolved-path
   check above. `skill_manage delete <name>` in the foreground is **not** archival: it recursively
   deletes the package. That is
   acceptable here only because the reviewed package is already preserved in its verified canonical
   destination and a recovery copy exists. Never use it as an archive step.
4. **Read the source back.** `skill_view` must resolve the canonical package again, its content must
   be the published content, and the declaration audit must report no local override for that name.
5. **Set the lock last, then read the target back.** Use the supported CLI for the canonical name;
   the locked directory must be the canonical package directory, not a path that no longer exists.
   A successful command is not the evidence — the read-back is.

## Abandoned branch

1. **Preserve a recoverable complete copy first.** Unless the user explicitly approves discarding the
   work, write a tarball of the complete local package outside discovery (a plain archive, not
   `hermes curator archive`) and verify it against the package — file list and hashes. A partial copy
   is not recovery.
2. **Remove the working copy while it is unlocked**, as above — deletion, after preservation and the
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
