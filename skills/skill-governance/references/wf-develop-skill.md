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

## Branch A — Editing or improving existing canonical skill(s)

Use this for targeted edits (single-skill or multi-skill refactors) as well as burn-in /
self-improvement phases. **Never copy existing canonical skills into `$HERMES_HOME/skills/`.**

1. **Clarify the intent and choose the branch.** Ask the user what the change or improvement aims
   to achieve, then pick the branch prefix:
   - `edit/<slug>` — targeted edit or refactor.
   - `improve/<slug>` — burn-in / self-improvement phase where selected canonical skill(s) stay
     unlocked to learn from real usage (`/refine`).
   For larger or multi-skill changes (and always for `improve/*`), create/check out the branch in
   the canonical repository before editing.
2. **Create the change doc.** Create `./changes/YYYYMMDD-<slug>.md` in the canonical repository
   with frontmatter (`change_id`, `date`, `branch`, `status: draft`, `affected_skills`) and three
   sections: **Goal Statement**, **Summary**, and **Conceptual Deltas** (abstract enough for a
   later session to update concept docs without reading the raw diff). The `branch` prefix
   (`edit/...` vs `improve/...`) records the change type — no separate `kind` field is needed.
3. **Unlock the target skill(s).** Provide a copy-paste block with one command per skill (the CLI
   accepts only one skill name per call):
   ```bash
   hermes curator unlock <skill-1>
   hermes curator unlock <skill-2>
   ```
   Wait until the user runs it. Note: while any sibling skill in the same repository remains locked,
   repository-root Git commands (`git add`, `git commit`, `git checkout`, `git merge`) are guarded
   for the agent — default is for the user to run those Git commands directly without changing
   locks. Only if the user deliberately wants the agent to run repo-wide Git commands or conflict
   resolution may the user run
   `python3 skills/skill-governance/scripts/bulk-lock.py unlock <skills-dir> -p <profile>`
   beforehand and
   `python3 skills/skill-governance/scripts/bulk-lock.py restore <skills-dir> -p <profile>`
   afterwards (restores only the previously locked skills; never invoked by the agent).
4. **Edit or learn in place.** Patch/edit directly in the canonical repository (`skill_manage` or
   filesystem tools on the canonical package path). For `improve/*` burn-in, leave the skill(s)
   unlocked in place until stable — never create a local shadow copy. Keep the change doc updated
   as decisions evolve.

## Branch B — Starting a brand-new canonical skill

A brand-new skill has no canonical existence yet (`baseline: none`). Start it profile-local (or
directly on a branch in the canonical repo if the user prefers):

1. **Create the change doc (`baseline: none`).** Create `./changes/YYYYMMDD-<slug>.md` in the
   target canonical repository (or note the target repo and intent locally until ready) with
   `baseline: none` so the later review has a clear goal statement.
2. **Check for existing same-name packages before creating.** If a package of that name already
   resolves anywhere (local or external), stop and reconcile with the user.
3. **Create the skill locally (verify `skills.create_dir` first).** Check
   `hermes config get skills.create_dir` before creating.
   - If `skills.create_dir` is unset (or points at `$HERMES_HOME/skills`), use
     `skill_manage(action="create", category="local")` to create `$HERMES_HOME/skills/local/<name>/`.
   - If `skills.create_dir` points to another directory or repository, do **not** use
     `skill_manage(action="create")` (it would write into that configured root instead of
     profile-local). Create the complete package directly at `$HERMES_HOME/skills/local/<name>/`
     with filesystem tools (`write_file`).
   Use the skill on real work until the procedure stops changing. Name neighboring skills in
   `related_skills`; a skill that narrows or specializes an existing one is not a new skill — route
   the delta to the owning skill per `skill-governance`.
4. **Verify the source.** `skill_view` and the edit resolver must report the local package, with no
   collision in the declaration audit.

## Learning rules (both branches)

- **Learn in a bounded way.** Sharpen an existing rule instead of adding a near-duplicate; replace
  an obsolete instruction and delete what it superseded; move conditional depth, long examples and
  troubleshooting behind focused references; keep the main file inside the quality gates in
  `skill-builder/references/skill-quality-gates.md`. Bump the version once for the phase at review
  time (rule: `skill-builder` step 4), not on every edit.
- **Run `/refine` deliberately, with a focus.** It pays off when a session produced a lesson worth
  keeping: name the skill and the behaviour to capture. Its focus is a prompt, not a technical
  per-skill ACL — a run may touch any unlocked skill, so read afterwards what it changed. A locked
  skill makes it report the suggestion instead of writing; that is the intended state, not a
  reason to create an alternative name.

## Verification

- **Existing skill:** intent recorded in `./changes/YYYYMMDD-<slug>.md`, target skill(s) unlocked,
  edited directly in the canonical repo (on `edit/<slug>` or `improve/<slug>`), and no same-name
  shadow exists in `$HERMES_HOME/skills/`.
- **New local skill:** phase record exists (`baseline: none`), `skill_view` resolves it locally, no
  collision exists.
- Edited files stay within the quality gates; the version bump matches the phase's scope.

## Stop and recovery

- The name is bundled or hub-installed, or an unintended local package of that name already exists:
  stop and ask; do not overwrite.
- Three failed attempts on the same file: stop, report the real error and the exact target.
- A refused write on a locked skill is a gate, not a bug. Do not bulk-unlock, edit `.usage.json` or
  the ledger, relocate the command or hide the write in a helper.
