---
name: skill-library-maintenance
description: "Use when auditing, developing or publishing skills."
license: MIT
metadata:
  version: "1.0.0"
  author: Olaf Geibig
  source: https://github.com/olafgeibig/skills
  hermes:
    category: personal
    tags:
      - skills
      - git
      - maintenance
      - audit
    related_skills:
      - skill-builder
      - skill-governance
---

# Skill Library Maintenance

Audit, integrate, and restructure Git-backed skill libraries without losing user work or confusing canonical sources with installed copies.

## When to Use

- Audit a repository containing multiple skills.
- Find oversized main files or descriptions that exceed client budgets.
- Detect dangling support-file references or stale client assumptions.
- Adopt or migrate a profile-local skill into a canonical owned repository.
- Split a generic skill into a core and domain or project overlays.
- Reconcile duplicate skill names across configured roots.
- Diagnose a stuck cross-installation repository sync.
- Install the sync on a machine, or determine which role this instance has.
- Dissolve a migration-source skill into its canonical owners and retire the shell.

Use `skill-builder` for the quality rules of one skill package. Use `skill-governance` for ownership, scope, sidecars, and canonical destinations. This skill applies those rules across a library.

## Repository Audit

Run the bundled read-only audit from the repository root:

```bash
python3 skills/skill-library-maintenance/scripts/audit-skill-library.py skills
```

Use JSON output for automation:

```bash
python3 skills/skill-library-maintenance/scripts/audit-skill-library.py skills --json
```

The audit reports:

- main `SKILL.md` line and word counts;
- description length;
- files over the preferred and hard thresholds;
- missing required discovery fields;
- name/directory mismatches;
- dangling references to package support files.

Reference tokens resolve against the SKILL.md's own package directory: a bare support-file path that belongs to another package is reported as `missing references` even though the file exists there. Prefix a cross-package pointer with the owning skill's package name, or write it as prose without a bare path — both forms audit clean, the bare form does not.

The audit does not edit files. Review findings using `skill-builder/references/skill-quality-gates.md` before refactoring.

## Declaration Audit (across roots)

`audit-skill-library.py` audits one repository's packages. This one audits the *runtime*: every root Hermes loads from — the profile-local directory plus each `skills.external_dirs` entry, discovered from the active profile's `config.yaml`.

```bash
python3 skills/skill-library-maintenance/scripts/audit-skill-declarations.py
python3 skills/skill-library-maintenance/scripts/audit-skill-declarations.py --strict --json
```

It reports:

- **name collisions** across roots — the loader fails closed on these, so the skill is unusable under its bare name;
- **undeclared profile-local skills** (neither `metadata.adapted_from` nor `metadata.scope: standalone`), scoped by `.usage.json` provenance so the list stays actionable: agent-created skills are listed in full, unattributed ones only when they overlap an external skill;
- **overlap candidates** — token similarity over name plus description, a review list rather than a verdict.

Exit code 1 on a collision; with `--strict`, also 1 when an agent-created skill is undeclared and overlaps an external skill.

## Maintenance Workflow

1. Discover repository root, branch, status, remotes, local identity, and all skill packages.
2. Load repository governance and the target skills before editing.
3. Run the library audit, the declaration audit, and the repository's Agent Skills validator.
4. Classify findings:
   - package-local quality problem;
   - generic rule in the wrong skill;
   - domain or project procedure in a generic skill;
   - profile-local adaptation in a shared repository;
   - unnamed adaptation — a profile-local skill that narrows or extends an external skill without declaring `adapted_from`;
   - obsolete or duplicate material.
5. Select the smallest coherent migration or refactor.
6. Update the main skill, references, templates, and scripts together.
7. Bump each changed package version.
8. Validate affected packages and rerun the library audit against the final edited tree; rerun affected checks after subsequent edits so earlier results do not certify a different artifact. Report schema validation, library audit, runtime loading, and behavioral tests separately: none substitutes for another. Expand wildcard support-file references before calling them dangling; inspect client-specific metadata compatibility before changing a package merely to satisfy a generic validator.
9. Verify resolved source paths and duplicate names in the target runtime.
10. Stage only intended paths; commit and push only when authorized.
11. Re-verify content claims — including verification tables — against their sources on user signal or at least once per quarter; structural audits alone do not catch stale or false content.

Renaming a skill is create + delete — `skill_manage` has no rename, and the new record starts fresh in `.usage.json`: `patch_count`, `use_count`, `created_by`, and a set pin do not carry over.
Check `pinned` before renaming: a pinned skill cannot be deleted by `skill_manage` — unpin first and re-pin under the new name afterwards.
Rename when the skill's content stays valid but its identity or scope changes; archive when the skill is superseded and its content lives on elsewhere.
After any rename or dissolve, sweep the old name from all five locations: the repo skill directory, installed/profile copies, sibling skills (`related_skills` and body mentions), bundles, and lock files (`$HERMES_HOME/skills/.hub/lock.json`, `$HERMES_HOME/skills.lock.json`).
Verify the old name no longer resolves — `skill_view` must fail — before declaring the rename complete.

Answer questions about a skill's history with evidence from runtime telemetry and the ledger, not from memory.

## Canonical and Installed Copies

- A Git-backed owned repository is the source of truth for its skills.
- Profile-local or external discovery paths do not change ownership.
- A profile-local same-name skill shadows an external canonical skill. That is allowed only as the explicitly opened, temporary working copy described in `references/skill-development-lifecycle.md` — never as an accidental second copy.
- Never edit a third-party checkout directly.
- Do not call a profile-local skill committed merely because it exists on disk.

### Answering “committed and pushed?”

1. Start from the `skill_dir` returned by a fresh `skill_view`; resolve the actual checkout with `git -C <skill_dir> rev-parse --show-toplevel`. Do not guess the repository root from a parent directory's name — discovery roots may be nested inside the checkout.
2. At that root, run `git status --short --branch` and `git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}'`. Fetch the upstream remote before comparing; if fetching fails, label the tracking ref as cached rather than claiming current remote state.
3. Run `git rev-list --left-right --count HEAD...@{upstream}` and `git log --oneline '@{upstream}..HEAD'`. The first count is local-only commits, the second remote-only commits; inspect the commits before attributing them to particular skills.
4. Report working-tree cleanliness, local commits, and integration separately. A clean tree does not mean pushed; local-only commits do not prove their content is absent remotely, since another branch may have merged or cherry-picked it.
5. If both counts are nonzero, report divergence and the need for integration. A status question authorizes inspection, not a merge, rebase, commit, or push; integration is a deliberate, user-authorized operation, never a follow-up to a question.

When migrating a skill:

1. Validate the source package.
2. Sweep the content for what must not travel into a shared copy: instance pointers (vault and note paths that do not resolve on every consumer of the repository, local script paths, machine-specific hosts or endpoints) and any data kind the skill routes to a dated note (`skill-governance` → *Volatile Data Has a Note, Not a Skill*). Procedure and mechanics travel; the pointers become a profile-local skill per setup, and the data stays in each setup's dated note — never fork the skill itself.
3. Create the destination explicitly in the canonical repository and adapt the frontmatter to that repository's convention (`hermes.category`, `metadata.source` = the repository URL, author and version style as the sibling skills declare them) — a package that keeps its profile-local frontmatter (`category: own`, no `source`) arrives mislabeled in the shared repo.
4. Validate the destination before removing the source.
5. Remove the old copy only after ownership and path verification.
6. Load the skill and confirm `_source_path` resolves to the destination.
7. Search all configured roots for remaining duplicates.

## Shared Repository Operations

A skill repository that more than one profile, machine or program touches needs the same discipline
whether the operation is a publication, a dissolve or a manual fix:

- Establish the boundary first: working tree, index, remotes, tracking branch — and identify the
  other writers (scheduled jobs, the background review, other profiles, manual fixes) before editing
  shared files.
- Stage explicit paths. Never `git add .`/`-A` across a shared tree.
- Probe Git and lifecycle claims in a disposable repository with its own `HERMES_HOME` and a local
  bare remote. `references/repository-sync-safety.md` has the recipe and the rules for what a green
  result does and does not prove.
- Report syntax validation, isolated tests, integration into the checkout and activation in the
  profile separately. None substitutes for another.

There is no unattended integration process in this library. A standing contributor/maintainer
pipeline that moves unreviewed work into `main` on its own schedule is not part of this workflow:
skill changes go through the lifecycle in `references/skill-development-lifecycle.md`.

## Archived Skills

`hermes curator archive <name>` moves a skill to `$HERMES_HOME/skills/.archive/<name>/` and marks its record `state: archived`. Treat that directory as live inventory whenever a capability is requested or a name looks missing:

- `.archive/` is excluded from discovery (`_SCAN_SKIP_PARTS` in `agent/skill_commands.py`), so `skills_list` and `skill_view` never see it and `hermes curator status` does not count those skills.
- `hermes curator list-archived` is the inventory; `hermes curator restore <name>` is the only way back — CLI-only, ledgered as actor `user`. No pass, job, or `skill_manage` action restores anything.
- Verify a requested archive by matching the complete package's before/after file hashes, checking that the active source is gone, confirming the name in `hermes curator list-archived`, and reading `hermes curator ledger --skill <name> --limit 5`. Expect `skill_view` to fail; do not require an archived row in `hermes curator usage --json`, because that report can omit archived packages.
- `restore` refuses a hub-installed name, and a bundled name unless `curator.prune_builtins: true`; a restored bundled skill cannot be pinned, so it is archived again once idle past `archive_after_days` — it survives only while it keeps being used.
- A record that still reads `state: active` while the directory lives only under `.archive/` is cosmetic: report rows are guarded on a locally resolvable directory, so such a record never re-enters the state machine.
- Prefer `restore` over re-creation — the archive copy is the complete artifact, a new skill is a thinner duplicate with a new provenance.

## Developing and Publishing an Owned Skill

Released owned skills are locked. A change is developed deliberately in one profile, reviewed, and
published on authorization — not accumulated as an unreviewed sidecar, and not integrated by a
standing pipeline.

The model in one line: **develop locally → use and refine → review → publish → consume a stable
version.**

- The canonical repository stays the source of truth and keeps serving every profile through
  `skills.external_dirs`. Profiles do not each receive a permanent copy of the whole library.
- Only the skill currently being developed is copied — as a **complete package**, with the same
  directory and skill name — into the developing profile's local skills directory. Profile-local
  resolution shadows that skill's external counterpart only; every other released skill keeps
  loading from the checkout and keeps receiving updates.
- That working copy is temporary, and it is neither an adaptation nor a second canonical source: it
  has an owner, a recorded canonical baseline and an explicit end. After verified publication, or a
  deliberate abandonment, it leaves active discovery and the profile resolves the released package
  again.
- Learning during the phase sharpens the method. It does not append a chronological ledger of
  pitfalls, and it does not open an adaptation channel.
- Publication is an explicitly authorized operation: the reviewed bytes, explicit Git paths,
  validation, a local commit, then a separately authorized push with a read-back. Locks are real
  guards — a chat authorization does not bypass a content lock.

Opening the phase, the order of operations, the lock/Git interaction, the review questions, the
close-out procedure and the stable update path: `references/skill-development-lifecycle.md`.

## Background Review During Library Work

The background review (`auxiliary.background_review`, on by default) runs after every turn with the instruction to update the skill library, and it writes into the same files — shared repositories included. During larger work it turns each edit into a two-writer race: files change mid-pass, versions bump on their own, routing rows appear, and both sides' additions duplicate in the same region.

- **Before a larger pass — refactoring or splitting a skill, dissolving an adaptation into its canonical owner — disable it and tell the user:** `hermes config set auxiliary.background_review.enabled false`. Say why, so the missing review updates later are not a surprise.
- **After verifying and committing, turn it back on:** `hermes config set auxiliary.background_review.enabled true`. Leaving it off silently stops the review-driven updates the library otherwise receives.
- Small, single-file edits do not need the toggle; re-read the file immediately before patching instead.
- Before a review write into a shared-repository skill, apply `skill-governance`'s scope rules at
  write time: instance-shaped lessons go to the profile's adaptation or the project files, generic
  ones to the canonical package.
- If a pass ran with the review on, check `<HERMES_HOME>/skills/.curator_ledger.jsonl` for `actor: curator` entries whose `evidence.session_id` matches the session before treating a change as your own.
- A missed toggle is diagnosable afterwards: background-pass writes arrive as `actor: curator` ledger entries. Grep the ledger for the session id and review what landed before committing shared files.

## Protect Existing Work

- Inspect uncommitted changes before writing.
- Do not stage unrelated files.
- Use `git mv` only for tracked paths.
- Keep destructive cleanup separate from read-only validation.
- Do not drop stashes or backups without explicit consent.
- Quote commit messages so the shell cannot rewrite them: backticked identifiers inside double quotes are executed as command substitution and vanish from the message — single quotes or a heredoc whenever the message names code.
- Name the remote in scripted pushes: `git push <sha>:<ref>` without one parses the sha as an scp-style host and dies on DNS resolution — write `git push origin <sha>:<ref>`.
- Treat `.DS_Store` and similar OS metadata as a separate cleanup decision.

## Refactoring Large Skills

Use the thresholds from `skill-builder/references/skill-quality-gates.md`:

- up to 200 main-file lines: preferred;
- 201–250: acceptable when cohesive;
- 251–350: review for extraction;
- 351–500: require an explicit reason;
- over 500: split unless a documented exception applies.

Do not split by line count alone. Keep activation-critical decisions in `SKILL.md`; move conditional procedures, client-specific behavior, long examples, and troubleshooting into focused references. Disable the background review for the pass — see §Background Review During Library Work.

## Domain Extraction

Extract material from a generic skill when it assumes a named organization, project, lifecycle, taxonomy, or repository layout.

A correct extraction has all of these:

- the generic core remains independently useful;
- the overlay has a clear trigger and owns its references;
- no duplicate normative rule remains;
- the core links to the overlay instead of reproducing it;
- project facts remain outside both skills.

## Dissolving Migration-Source Skills

A migration-source skill is a profile-local package whose rules were accumulated for later integration — an adaptation overlay that outgrew its owners. Dissolve it: route every rule to its canonical owner, then retire the shell. Keep a route-map ledger (plan file) with one row per rule — source anchor, target file, line budget, status — and update it after every batch.

1. Freeze the source (hash + heading anchors) and re-verify before every batch: a live source keeps moving under other sessions.
2. Search before carrying — an `already-in-target` row costs 0 lines; budgets stop target sprawl; a rule that contradicts a canonical convention is fixed in the target with the divergence recorded, never carried silently.
3. Batch by target skill; for non-git targets a byte-level backup diff is the review baseline; implementer → task review → integration review → validate → bump → commit.
4. Archive only when every row is closed: re-check the hash, `hermes curator backup`, `hermes curator archive`, verify complete-package hashes + archive inventory + absent active source as described under Archived Skills, then re-run the declaration audit and the dangling-reference search (names, retired numbers, deleted support files).

Disable the background review for the pass before the first batch — see §Background Review During Library Work.

See `./references/dissolving-source-skills.md` for the full procedure.

## Verification

- Library audit completes without hard errors.
- Every changed package passes its validator.
- Main files and descriptions meet or deliberately justify thresholds.
- Support-file references resolve.
- Canonical and profile-local changes remain separated.
- Resolved skill paths point to intended repositories.
- Git status contains only intended changes.
- Integrated remotes match local commits when pushing was authorized.
