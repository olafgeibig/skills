---
name: skill-library-maintenance
description: "Use when auditing or restructuring a skill library."
license: MIT
metadata:
  version: "0.5.0"
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
      - hermes-profile-operations
---

# Skill Library Maintenance

Audit, consolidate, and restructure Git-backed skill libraries without losing user work or confusing canonical sources with installed copies.

## When to Use

- Audit a repository containing multiple skills.
- Find oversized main files or descriptions that exceed client budgets.
- Detect dangling support-file references or stale client assumptions.
- Adopt or migrate a profile-local skill into a canonical owned repository.
- Split a generic skill into a core and domain or project overlays.
- Reconcile duplicate skill names across configured roots.

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
8. Validate affected packages and rerun the library audit.
9. Verify resolved source paths and duplicate names in the target runtime.
10. Stage only intended paths; commit and push only when authorized.

Renaming a skill is create + delete — `skill_manage` has no rename, and the new record starts fresh in `.usage.json`: `patch_count`, `use_count`, `created_by`, and a set pin do not carry over.
Check `pinned` before renaming: a pinned skill cannot be deleted by `skill_manage` — unpin first and re-pin under the new name afterwards.

Answer questions about a skill's history with evidence from runtime telemetry and the ledger, not from memory.

## Canonical and Installed Copies

- A Git-backed owned repository is the source of truth for its skills.
- Profile-local or external discovery paths do not change ownership.
- A profile-local same-name skill can shadow an external canonical skill.
- Never edit a third-party checkout directly.
- Do not call a profile-local skill committed merely because it exists on disk.

When migrating a skill:

1. Validate the source package.
2. Create the destination explicitly in the canonical repository.
3. Validate the destination before removing the source.
4. Remove the old copy only after ownership and path verification.
5. Load the skill and confirm `_source_path` resolves to the destination.
6. Search all configured roots for remaining duplicates.

## Archived Skills

`hermes curator archive <name>` moves a skill to `$HERMES_HOME/skills/.archive/<name>/` and marks its record `state: archived`. Treat that directory as live inventory whenever a capability is requested or a name looks missing:

- `.archive/` is excluded from discovery (`_SCAN_SKIP_PARTS` in `agent/skill_commands.py`), so `skills_list` and `skill_view` never see it and `hermes curator status` does not count those skills.
- `hermes curator list-archived` is the inventory; `hermes curator restore <name>` is the only way back — CLI-only, ledgered as actor `user`. No pass, job, or `skill_manage` action restores anything.
- `restore` refuses a hub-installed name, and a bundled name unless `curator.prune_builtins: true`; a restored bundled skill cannot be pinned, so it is archived again once idle past `archive_after_days` — it survives only while it keeps being used.
- A record that still reads `state: active` while the directory lives only under `.archive/` is cosmetic: report rows are guarded on a locally resolvable directory, so such a record never re-enters the state machine.
- Prefer `restore` over re-creation — the archive copy is the complete artifact, a new skill is a thinner duplicate with a new provenance.

## Protect Existing Work

- Inspect uncommitted changes before writing.
- Do not stage unrelated files.
- Use `git mv` only for tracked paths.
- Keep destructive cleanup separate from read-only validation.
- Do not drop stashes or backups without explicit consent.
- Treat `.DS_Store` and similar OS metadata as a separate cleanup decision.

## Refactoring Large Skills

Use the thresholds from `skill-builder/references/skill-quality-gates.md`:

- up to 200 main-file lines: preferred;
- 201–250: acceptable when cohesive;
- 251–350: review for extraction;
- 351–500: require an explicit reason;
- over 500: split unless a documented exception applies.

Do not split by line count alone. Keep activation-critical decisions in `SKILL.md`; move conditional procedures, client-specific behavior, long examples, and troubleshooting into focused references.

## Domain Extraction

Extract material from a generic skill when it assumes a named organization, project, lifecycle, taxonomy, or repository layout.

A correct extraction has all of these:

- the generic core remains independently useful;
- the overlay has a clear trigger and owns its references;
- no duplicate normative rule remains;
- the core links to the overlay instead of reproducing it;
- project facts remain outside both skills.

## Verification

- Library audit completes without hard errors.
- Every changed package passes its validator.
- Main files and descriptions meet or deliberately justify thresholds.
- Support-file references resolve.
- Canonical and profile-local changes remain separated.
- Resolved skill paths point to intended repositories.
- Git status contains only intended changes.
- Published remotes match local commits when pushing was authorized.
