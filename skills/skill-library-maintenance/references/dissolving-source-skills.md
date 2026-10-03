# Dissolving Migration-Source Skills

A migration-source skill is a profile-local package whose rules were accumulated for later consolidation — typically an adaptation overlay that outgrew its owners. Dissolving it means: route every rule to its canonical owner skill, then retire the shell. This file is the long-form procedure behind the SKILL.md section.

## Freeze the source

- Snapshot: sha256 of `SKILL.md` and every supporting file, plus a heading anchor table (heading → line range). Anchors make later "where did this rule come from" checks cheap.
- The source is read-only for the whole operation — all writes go to the targets.
- A live source keeps moving (other sessions patch it): re-verify the hash at the start of every batch and once more before archiving. On mismatch, refresh the anchor table first, then continue with the new hash recorded in the ledger.

## Route map (the ledger)

One row per rule: source anchor | rule | target skill + file | line budget | status. Statuses: `open`, `carried`, `already-in-target` (0 budget — search the target first), `dropped` (reason required), `retargeted`. Update it after every batch; the ledger is the operation's memory across sessions.

- Budgets protect the targets from sprawl; exceeding a budget is an escalation, not an invitation to append.
- One rule per row, even when several rows share a target — it prevents silent scope drift.

## Translation rules (profile → canonical)

- Strip instance data: dates, handles, account/user/vault/project names, session anecdotes. What remains must hold for any user of the canonical skill.
- The target's conventions win: bullet style, terminology, language, heading depth. Regenerate wording — sources are usually code-switched and longer than needed; keep the meaning, not the phrasing.
- One rule per bullet; no meta narration ("we learned that…").

## Batches

Batch by target skill — one writer per file at a time; if a foreign session is mid-write on a target, defer that row (record it in the ledger) and guard the eventual write with a before/after hash check. Per batch:

1. Byte-level backup of every file the batch touches; for non-git targets the backup diff is the review baseline.
2. Implementer applies only the batch's rows; reports the exact diff and open uncertainties.
3. Task review (read-only, fresh context): fidelity to the source anchors, constraint compliance, diff scoped against the backup.
4. Integration review: whole-batch diff across all targets — coherence, ledger-row closure, no smuggled hunks.
5. Validate with the repository validator, bump the version (fix = patch, feat = minor), commit with a conventional message; no push unless authorized.

The Controller owns small wording micro-fixes (record them) and reconciles reviewer findings against the ledger; substantive defects go back through the implementer. Give reviewers the ledger rows for their batch — without them they will report deliberate cross-skill splits as "missing" findings.

## Conflict policy

- Default: source-faithful. The source's claim is the requirement, even when phrased differently.
- Exception: the source contradicts a canonical convention or preserves a loophole the convention forbids. Fix the target, record the divergence and its rationale in the ledger — never carry the contradiction silently, never silently drop the source's intent.
- Dropped elements stay listed with their anchor and reason so later audits do not re-litigate them.

## External references

Other skills often cite the source by pitfall number or section title, not by name — those citations break silently when rules move or retire. Sweep referrers before close-out:

- Keep surviving numbers stable. Retiring rules leaves gaps in the numbering — fine; renumbering breaks every external citation. Renumber only when no live referrer exists.
- Grep all roots for the source name and for the names of deleted support files — *all roots* means the profile tree **plus every `external_dirs` repo** (a skill promoted from profile-local to a repo moves with its referrers and is easy to miss); fix every hit at the referrer site — re-point promoted rules to their canonical home, and for retired rules drop the number while keeping the rule name. Content trees that cite skills (vault READMEs, concept docs) are referrer sites too — grep them in the same pass; they dangle silently past close-out.
- Minimal repairs only: drop a pre-existing mis-attribution rather than guessing a replacement number — never invent history. Historical texts (changelogs, session notes) keep their numbers; append a pointer to the canonical home where the reader needs to find it.
- Record the sweep in the ledger (hits, fixes) so the integration review can verify it.

## Close-out

- Every row closed — nothing left `open`.
- Re-verify the source hash; take `hermes curator backup --reason "<context>"`.
- `hermes curator archive <name>`; verify the archived copy: hash unchanged, `.usage.json` reads `state: archived`, the source directory is gone from its root.
- Re-run the declaration audit — the source's gap/overlap must disappear — and re-grep the roots for the retired name (excluding `.usage.json`, the ledger, and the archive itself): zero dangling references.
- Close the ledger: mark rows, add a version entry, list deferred items for the user.
