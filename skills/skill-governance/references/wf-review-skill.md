# Reviewing a Skill

How a development phase ends: one dedicated session reads the complete package against its
recorded baseline and either approves exact bytes for publication or names concrete findings.

## When to load

The learning or editing is ready to be checked, or the user requests another review pass after
discussing updates. This workflow is **iterative**: if a review leads to further edits, update the
change doc (`./changes/YYYYMMDD-<slug>.md`), re-run validation and linter, and review again until
the user approves. `/refine` is not this review: it captures lessons from one conversation and
never certifies a package.

## Preconditions

- The changed package is complete and verified as the active source (`skill_view` resolves it).
- The baseline is known: the Git base commit/branch (for existing skills edited in place) or
  `baseline: none` in the phase record (for a brand-new skill).
- The change doc (`./changes/YYYYMMDD-<slug>.md`) exists and reflects the current state of the
  branch.
- Competing learning writes have stopped. Say so explicitly: no `/refine` runs and no edits during
  the review; if a background or automatic review is enabled in this profile, ask the user to pause
  it for the session and say why.

## Start prompt

Give this to the review session — a separate session, ideally a stronger model than the implementer:

> You are the review session for `<skill>`. Read the package at `<path>` in full and compare it with
> its baseline `<commit/branch, or: none — new skill>`.
> Do not edit any other skill and do not publish anything. Produce: (1) a complete-package
> comparison against the baseline, not a diff summary; (2) every instance- or profile-specific fact,
> with a proposed generic rewording or its existing local home; (3) duplicates, contradictions and
> superseded rules; (4) findings on links, support files, scripts, tests, validators, frontmatter and
> version; (5) a verdict: ready to publish at version `<x>`, or blocked with concrete findings.

## Steps

1. **Stop the phase's writes.** Announce the review; the only edits allowed are those the review
   itself produces, and each one returns through the review before approval.
2. **Compare the complete package, git diff, and change doc.** Read every file of the package,
   inspect `git diff <base>..HEAD` (plus unstaged changes), and read `./changes/YYYYMMDD-<slug>.md`.
   Check that the implementation matches the Goal Statement and that the change doc accurately
   describes all conceptual deltas. For a new skill there is no baseline: read the whole package on
   its own terms.
3. **Answer the required questions.** Does the change solve the intended problem, and was the
   affected workflow actually exercised? Are the instructions generic for the skill's intended
   consumers, or merely generalized wording wrapped around one installation? Are instance and
   profile specifics removed or held in their existing local home? *(Pay extra attention when the
   branch is `improve/*`: self-improvement runs easily pull in project- or instance-specific rules
   that must be stripped or generalized.)* Are duplicates, contradictory exceptions and superseded
   rules gone? Do links, scripts, tests and validators still work? Is the version appropriate, and
   is the package still compact enough to load?
4. **Reconcile same-skill canonical drift.** If the canonical package of this same skill changed
   during the phase, reconcile explicitly: adopt the change, supersede it, or report the conflict.
   Never merge silently. Updates to unrelated skills are not merged into this copy.
5. **Check dedupe and support files.** No normative rule twice, no reference chain deeper than
   needed, support files complete, no stale path or client assumption. Remove what no longer earns
   its place rather than accumulating a chronicle of incidents.
6. **Iterate or record the verdict.** If the review produces edits, apply them, update the change
   doc, re-run the linter and library audits, and repeat the check. When clean, record the verdict
   (ready to publish at version `<x>`, or blocked with concrete findings). Approval covers exactly
   the reviewed bytes; a later content change needs another review.

## Verification

- Every `references/...` path in the package resolves.
- The change doc matches the actual changes and goal.
- The package validator reports no structural finding (see `references/wf-audit-library.md` for
  the exact commands and what each gate proves).
- The library audit and declaration audit were run against the reviewed tree, after the last edit.
- The version is bumped once for the phase and matches the change's scope.
- The frontmatter follows the variant in `skill-builder` step 4.

## Stop and recovery

- Findings you cannot resolve stay findings: report the reviewed package as blocked with the exact
  list, never approve around them.
- A review that wants to change scope — split the skill, merge another skill, rename — is a new
  phase decision for the user, not a review-time edit.
- Three failed attempts on the same file: stop and report the real error.
- Do not publish from the review session, and do not let a passing review stand in for the user's
  publication approval.
