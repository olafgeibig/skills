# Reviewing a Skill

How a development phase ends: one dedicated session reads the complete package against its
recorded baseline and either approves exact bytes for publication or names concrete findings.

## When to load

The learning in the phase is finished and the package should be reviewed, or the user judges the
skill to work and starts the review session. `/refine` is not this review: it captures lessons from
one conversation and never certifies a package.

## Preconditions

- The working copy is open, complete, and verified as the source (`skill_view` resolves it).
- The phase record holds the baseline: canonical commit, package path, intent, owner.
- Competing learning writes have stopped. Say so explicitly: no `/refine` runs and no edits during
  the review; if a background or automatic review is enabled in this profile, ask the user to pause
  it for the session and say why.

## Start prompt

Give this to the review session — a separate session, ideally a stronger model than the implementer:

> You are the review session for the development phase of `<skill>`. Read the working copy at
> `<path>` in full and compare it with its canonical baseline `<commit, or: none — new skill>`.
> Do not edit any other skill and do not publish anything. Produce: (1) a complete-package
> comparison against the baseline, not a diff summary; (2) every instance- or profile-specific fact,
> with a proposed generic rewording or its existing local home; (3) duplicates, contradictions and
> superseded rules; (4) findings on links, support files, scripts, tests, validators, frontmatter and
> version; (5) a verdict: ready to publish at version `<x>`, or blocked with concrete findings.

## Steps

1. **Stop the phase's writes.** Announce the review; the only edits allowed are those the review
   itself produces, and each one returns through the review before approval.
2. **Compare the complete package, not a diff.** Read every file of the working copy. For an existing
   skill, read the canonical package at the baseline commit for comparison — a `git diff` against
   that commit is an index, not the review. For a new skill there is no baseline: read the whole
   package on its own terms.
3. **Answer the required questions.** Does the change solve the intended problem, and was the
   affected workflow actually exercised? Are the instructions generic for the skill's intended
   consumers, or merely generalized wording wrapped around one installation? Are instance and
   profile specifics removed or held in their existing local home? Are duplicates, contradictory
   exceptions and superseded rules gone? Do links, scripts, tests and validators still work? Is the
   version appropriate, and is the package still compact enough to load?
4. **Reconcile same-skill canonical drift.** If the canonical package of this same skill changed
   during the phase, reconcile explicitly: adopt the change, supersede it, or report the conflict.
   Never merge silently. Updates to unrelated skills are not merged into this copy.
5. **Check dedupe and support files.** No normative rule twice, no reference chain deeper than
   needed, support files complete, no stale path or client assumption. Remove what no longer earns
   its place rather than accumulating a chronicle of incidents.
6. **Record the verdict.** In the phase record put: verdict, reviewed version, unresolved findings.
   Approval covers exactly the reviewed bytes; a later content change needs another review.

## Verification

- Every `references/...` path in the package resolves.
- The package validator reports no structural finding (see `references/audit-library.md` for the
  exact commands and what each gate proves).
- The library audit and declaration audit were run against the reviewed tree, after the last edit.
- The version is bumped once for the phase and matches the change's scope.
- The frontmatter follows the variant in `skill-builder` step 5.

## Stop and recovery

- Findings you cannot resolve stay findings: report the reviewed package as blocked with the exact
  list, never approve around them.
- A review that wants to change scope — split the skill, merge another skill, rename — is a new
  phase decision for the user, not a review-time edit.
- Three failed attempts on the same file: stop and report the real error.
- Do not publish from the review session, and do not let a passing review stand in for the user's
  publication approval.
