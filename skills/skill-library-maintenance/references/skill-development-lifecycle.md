# Skill Development Lifecycle

How an owned skill changes: a deliberate development phase in one profile, a review, an authorized
publication to the canonical repository, and stable consumption by every other profile.

The old model — a standing contributor/maintainer pipeline that moved unreviewed work into `main`
on its own schedule — is retired. Its implementation is archived, not installed. Nothing here
describes automation that runs unattended.

Two invariants decide every case below:

- **Released skills are locked.** A lock stops an agent from mutating the content; it does not pin a
  Git revision and does not stop the user from updating the checkout.
- **One owner per skill at a time.** Different skills may develop on different machines; one skill
  has exactly one open development phase.

## 1. A new skill

Develop the method while solving a real problem. Extract it only once it is useful beyond that
conversation, and keep project facts and machine settings in their existing project or profile
homes instead of turning session narration into instructions.

1. Create the package in the profile's own local skills directory, complete with its references,
   scripts, templates and assets.
2. Use it on real work until the procedure stops changing.
3. Optional lifecycle management: `curator adopt` on the local package gives it stale/archive
   handling under the Curator; `pin` protects it from lifecycle transitions and deletion. Neither
   freezes content, and neither replaces review.
4. Review it as described in §4 before it is published for the first time.

A local package that has never been published is not an adaptation and needs no
`adapted_from`/`scope: standalone` declaration merely to look tidy — but an undeclared local skill
whose name overlaps a released one is a real finding for the declaration audit, so keep the name
distinct or record the intent.

## 2. An existing owned skill: open the development phase

1. **Choose one profile and record the baseline** in the development session's project note: source
   repository, package path, starting commit, the skill name, and the intended change. A second
   independent version of the same skill requires explicit reconciliation — no automation will
   merge it later.
2. **The user opens the skill.** Agent-side lock commands exist, but opening a released skill for
   development is the user's decision; a chat authorization does not silently unlock content.
3. **Copy the complete package** into `$HERMES_HOME/skills/own/<same-name>/` with filesystem tools.
   Copy the whole directory — references, scripts, templates, assets, tests. A package cut down to
   `SKILL.md` is broken, and its links will dangle.

   `skill_manage create` is **not** the copy operation: it refuses a name that already resolves
   externally. Keep the directory name and the frontmatter `name` unchanged, and create a real
   directory — not a symlink, which discovery does not reliably follow.

4. **Verify before the first edit, not after.** A version bump or a configuration change is not
   proof of what loads. Confirm that `skill_view` and the edit resolver both report the local path,
   and start a fresh session after switching the source so earlier loaded instructions do not
   masquerade as the new version.

Stop and ask when the name is bundled or hub-installed, or when a local version of that name
already exists: overwriting it discards someone's work.

## 3. Learning during the phase

User-directed edits and the configured background review may refine the local package. One owner
per skill; every other released skill stays locked and untouched.

Refine the method rather than append a chronicle:

- sharpen an existing rule instead of adding a near-duplicate beside it;
- replace an obsolete instruction and delete what it superseded;
- move conditional depth, long examples and troubleshooting behind focused references;
- keep the main file near the thresholds in `skill-builder`'s quality gates.

Opening one skill for development is not a global switch: it does not disable locks elsewhere, and
it is not permission for a background mechanism to edit every skill. It also does not open an
adaptation channel — see §7.

## 4. Finish learning and review

End uncontrolled writes first: stop editing, and pause the background review if it is enabled for
the pass. Then review the **complete package** against the recorded baseline, not a diff summary.

Required questions:

- Does the change solve the intended problem, and was the affected workflow actually exercised?
- Are the instructions generic for the skill's intended consumers, or merely generalized wording
  wrapped around one installation?
- Are instance-specific facts removed or held in their existing local home?
- Have duplicates, contradictory exceptions and superseded rules been removed?
- Do package links, scripts, tests and validators still work, and is the version appropriate?
- Is the package still compact enough to load without accumulating a history of incidents?

If canonical changes landed for **this same skill** during the phase, reconcile them explicitly.
Updates to unrelated skills do not need to be merged into the local package.

The approval covers exactly the reviewed bytes. Any later content change needs another review.

## 5. Publish deliberately

Only after the user authorizes publication.

1. Transfer only the reviewed package into the canonical repository. A new skill is added; an
   existing one is updated in place — never as a parallel identity.
2. Validate the package before and after the transfer.
3. Stage explicit paths. Unrelated dirty files in the checkout are not part of the publication.
4. Commit locally, then push only when authorized, and read the remote back. A failed push is not
   completion: the work stays local and unpublished, and must be reported that way.
5. Locks remain real guards. Authorization in chat does not bypass a content lock; the user
   performs any required unlock, and publication leaves the released skill locked again. Do not
   invent a hidden copier, a helper script or an alternate path to evade a guard.

**Naming caveat.** While a same-name local working copy is active, `skill_manage` resolves that
name locally. Do not use the bare name as if it targeted the external package. Publication is an
explicitly targeted repository operation, and its direct-write alternative has no ledger entry —
disclose that limitation instead of implying a rollback exists.

## 6. Close or abandon

- Verify the remote commit and the published package before retiring anything.
- Retain a recovery copy of the local package.
- Remove the working copy from active discovery only after verified publication, or after the user
  explicitly abandons the work.
- **Do not run `curator archive <same-name>` blindly after moving it.** Archive and usage state are
  keyed by name; archiving the local copy can hide or mislabel the released skill that now carries
  the same name. Leave `.usage.json` and the ledger under native management.
- Verify that `skill_view` now resolves the external released package, that its content is the
  published content, and that the final lock state is what was intended.

If publication or cleanup is incomplete, say so explicitly rather than declaring the profile back
on the release.

## 7. Stable update and the adaptation boundary

- The user updates a released checkout deliberately — normally a fast-forward — after confirming it
  is clean. No agent pulls, sweeps or integrates on its own schedule.
- A profile that is developing a skill keeps its working copy; an update must not overwrite it. That
  is a reconciliation case, not a fast-forward.
- A newly released skill needs its lock set in every consuming profile. The Git repository does not
  transport profile lock records.
- Nothing here is verified for a machine until it is checked there. Do not claim that other
  installations are migrated.
- **No automatic adaptation channel.** Released skills are locked; ordinary use must not produce a
  new, indefinitely growing pitfalls sidecar. Existing adaptations stay as they are — preserved, not
  promoted, not consolidated, not deleted as a side effect of this lifecycle. A concrete local
  requirement is a separate, bounded decision in its existing profile or project home.

## Lock and Git interaction

Repository-root Git mutation is treated as a write to every locked descendant: with **any** locked
skill below the repository root, `git add` and `git commit` at that root are refused regardless of
which paths are staged. Unlocking only the skill being edited is therefore not sufficient.

Consequences for this lifecycle:

- Finish local commits **before** a lock sweep, and expect the sweep to end the agent's ability to
  make further repository-wide Git changes.
- When the guard refuses, the **user** runs the blocked command in their own terminal. Do not
  bulk-unlock siblings, rewrite `.usage.json`, relocate the command to dodge the check, or hide the
  mutation inside a helper script. The guard is a policy control, not a sandbox against hostile
  code.
- Only the user can unlock. An agent may set locks through the supported CLI.

## Failure and restart

- Read the recorded state and the actual filesystem before resuming. A completed publication or
  commit is verified and reused, never repeated blind.
- Stop after roughly three failed attempts on the same file. Report the real error and the exact
  target.
- Never fix dirty-tree attribution with `restore`, `reset`, `rebase`, broad staging or a ledger
  deletion.
- A blocked gate is partial work, not success. Restore a paused background review before handing
  the work back, or state prominently that it is still off and why.
