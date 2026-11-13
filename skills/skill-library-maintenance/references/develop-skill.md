# Developing a Skill

How a new skill, or a change to a released one, gets a known target and an isolated working copy
without disturbing consumers.

## When to load

A new skill should be written, or a released skill needs a change and no development phase is
open yet. Load it for the opening steps only; review and publication are separate workflows.

## Preconditions

- Ownership is settled per `skill-governance`: an owned canonical skill, a profile-local skill, a
  project skill, or a third-party source. A third-party checkout is read-only — stop and report.
- You know the canonical repository and package path, or you know that this is a new skill with no
  canonical existence yet.
- The current lock state is read before you ask anything (`hermes curator status`, or the refusal
  text of the write you attempted). Only a locked skill needs the user; the rule is in
  `skill-governance` → *Released Skills Are Locked* — name the exact skill, state why, and wait.
- No Git write is attempted in this phase. Repository-root Git mutation stays blocked while any
  sibling in the repository is locked; that is expected and belongs to publication, not here.

## Steps

1. **Fix the phase shape.** One phase covers one skill, or one coupled change across several named
   skills. A coupled change is still one phase: it names every skill, and each gets its own working
   copy and its own baseline; the phase is reviewed and published as a unit.
2. **Record the baseline before the first edit.** In the open-development-phases table in the
   user's knowledge base (the profile skill names that path), record: skill name, canonical commit
   or `none`, package path, profile, intent, one owner, and the prior lock state. There is no other
   state file and no per-workflow ledger.
3. **Check for existing local work before copying.** If a package of that name already resolves
   locally and is not this phase's copy, stop. Find its owner: an abandoned working copy, a
   profile-local skill that shadows the canonical one, or a foreign session's work. Do not
   overwrite it. Either the user adopts it as this phase (then record the baseline against it) or
   it is preserved untouched and the phase does not start.
4. **Open the skill (existing skill).** The user unlocks it. Then copy the **complete package** into
   `$HERMES_HOME/skills/own/<same-name>/` with filesystem tools: references, scripts, templates,
   assets, tests. Keep the directory name and the frontmatter `name` unchanged. Do not use
   `skill_manage create` — it refuses a name that already resolves externally — and do not use a
   symlink, which discovery does not reliably follow.
5. **Start a new skill locally (new skill).** Create the full package in the profile's local skills
   directory and use it on real work until the procedure stops changing. Its baseline is `none`: it
   has no canonical commit, no released bytes and no lock, and review comes before its first
   publication. A genuinely new skill declares `metadata.scope: standalone` and names the skills it
   borders in `related_skills`; a skill that narrows or specializes an existing one is not a new
   skill — route the delta to the owning skill per `skill-governance`.
6. **Verify the source before the first edit, not after.** `skill_view` and the edit resolver must
   both report the local working copy. Start a fresh session after the switch so earlier loaded
   instructions cannot masquerade as the new version. For an existing skill the declaration audit
   should now report exactly one local override for that name and no collision.
7. **Learn in a bounded way.** Sharpen an existing rule instead of adding a near-duplicate; replace
   an obsolete instruction and delete what it superseded; move conditional depth, long examples and
   troubleshooting behind focused references; keep the main file inside the quality gates in
   `skill-builder/references/skill-quality-gates.md`. Bump the version once for the phase at review
   time (rule: `skill-builder` step 5), not on every edit.
8. **Run `/refine` deliberately, with a focus.** It pays off when a session produced a lesson worth
   keeping: name the skill and the behaviour to capture. Its focus is a prompt, not a technical
   per-skill ACL — a run may touch any unlocked skill, so read afterwards what it changed. A locked
   skill makes it report the suggestion instead of writing; that is the intended state, not a
   reason to create an alternative name.

## Verification

- The phase record exists and names one owner, one baseline and the prior lock state.
- The working copy is the complete package and `skill_view` resolves it locally.
- No second package with that name exists outside the copy.
- The declaration audit reports the expected override (existing skill) or a declared standalone
  local skill (new skill), with no collision.
- Edited files stay within the quality gates; the version bump matches the phase's scope.

## Stop and recovery

- The name is bundled or hub-installed, or a local package of that name already exists: stop and
  ask; do not overwrite.
- The canonical package cannot be found or does not match the recorded baseline: treat the source as
  lost or mismatched, stop and reconcile before editing. A wrong baseline makes the later review
  certify the wrong thing.
- Three failed attempts on the same file: stop, report the real error and the exact target.
- A refused write on a locked skill is a gate, not a bug. Do not bulk-unlock, edit `.usage.json` or
  the ledger, relocate the command or hide the write in a helper.
