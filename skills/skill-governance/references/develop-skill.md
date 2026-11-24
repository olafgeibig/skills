# Developing a Skill

How a new skill, or a change to an existing canonical skill, is opened without disturbing
consumers or creating unnecessary local shadows.

## When to load

A new skill should be written, or a released skill needs a change and no development phase is
open yet. Load it for the opening steps only; review and publication are separate workflows.

## Preconditions

- Ownership is settled per `skill-governance`: an owned canonical skill, a profile-local skill, or a
  third-party source. A third-party checkout is read-only — stop and report.
- You know the canonical repository and package path, or you know that this is a new skill with no
  canonical existence yet.
- The current lock state is read before you ask anything (`hermes curator status`, or the refusal
  text of the write you attempted). For any locked skill(s) that must be edited, generate a
  copy-paste block with one `hermes curator unlock <skill>` command per skill and wait for the user.

## Branch A — Editing existing canonical skill(s)

Use this for single-skill fixes as well as coupled multi-skill changes or refactors. **Never copy
existing canonical skills into `$HERMES_HOME/skills/`.**

1. **Choose the Git baseline.** For small single-skill edits, working on the active branch (or a
   branch the user chose) is fine. For larger or multi-skill changes, create/check out a dedicated
   Git branch in the canonical repository before editing.
2. **Unlock the target skill(s).** Provide a copy-paste block with one command per skill (the CLI
   accepts only one skill name per call):
   ```bash
   hermes curator unlock <skill-1>
   hermes curator unlock <skill-2>
   ```
   Wait until the user runs it. Note: while any sibling skill in the same repository remains locked,
   repository-root Git commands (`git add`, `git commit`, `git checkout`, `git merge`) are guarded
   for the agent and either run on the user's prepared branch or are executed by the user.
3. **Edit in place.** Patch/edit directly in the canonical repository (`skill_manage` or filesystem
   tools on the canonical package path).
4. **Burn-in / self-improvement.** If a newly created or massively refactored skill should learn
   from real usage (`/refine`), leave it **unlocked** in the canonical repository until stable —
   do not create a local shadow copy. Re-lock when burn-in is complete.

## Branch B — Starting a brand-new canonical skill

A brand-new skill has no canonical existence yet (`baseline: none`). Start it profile-local (or
directly on a branch in the canonical repo if the user prefers):

1. **Record the baseline before the first edit.** In the open-development-phases table in the
   user's knowledge base (the profile skill names that path), record: skill name, `baseline: none`,
   target canonical repository/path, profile, intent, one owner, and lock state.
2. **Check for existing same-name packages before creating.** If a package of that name already
   resolves anywhere (local or external), stop and reconcile with the user.
3. **Create the skill locally.** Use `skill_manage(action="create", category="local")` (or create
   the complete package in `$HERMES_HOME/skills/local/<name>/`) and use it on real work until the
   procedure stops changing. Name neighboring skills in `related_skills`; a skill that narrows or
   specializes an existing one is not a new skill — route the delta to the owning skill per
   `skill-governance`.
4. **Verify the source.** `skill_view` and the edit resolver must report the local package, with no
   collision in the declaration audit.

## Learning rules (both branches)

- **Learn in a bounded way.** Sharpen an existing rule instead of adding a near-duplicate; replace
  an obsolete instruction and delete what it superseded; move conditional depth, long examples and
  troubleshooting behind focused references; keep the main file inside the quality gates in
  `skill-builder/references/skill-quality-gates.md`. Bump the version once for the phase at review
  time (rule: `skill-builder` step 5), not on every edit.
- **Run `/refine` deliberately, with a focus.** It pays off when a session produced a lesson worth
  keeping: name the skill and the behaviour to capture. Its focus is a prompt, not a technical
  per-skill ACL — a run may touch any unlocked skill, so read afterwards what it changed. A locked
  skill makes it report the suggestion instead of writing; that is the intended state, not a
  reason to create an alternative name.

## Verification

- **Existing skill:** target skill(s) are unlocked, edited directly in the canonical repo (on a Git
  branch for larger/multi-skill changes), and no same-name shadow exists in `$HERMES_HOME/skills/`.
- **New local skill:** phase record exists (`baseline: none`), `skill_view` resolves it locally, no
  collision exists.
- Edited files stay within the quality gates; the version bump matches the phase's scope.

## Stop and recovery

- The name is bundled or hub-installed, or an unintended local package of that name already exists:
  stop and ask; do not overwrite.
- Three failed attempts on the same file: stop, report the real error and the exact target.
- A refused write on a locked skill is a gate, not a bug. Do not bulk-unlock, edit `.usage.json` or
  the ledger, relocate the command or hide the write in a helper.
