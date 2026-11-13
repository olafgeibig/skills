# Auditing the Library

Evidence about a skill library: size, links, name collisions, overrides, legacy metadata, validation
and archive inventory. Audits are read-only gates. They never migrate, restructure or create
anything.

## When to load

Library-wide evidence is needed — before a phase, before a publication, after an update, or when a
capability seems missing. For a single package's authoring quality while writing, use
`skill-builder` instead.

## Preconditions

- The repository root and the configured roots are known; audits do not guess a root from a parent
directory's name.
- Read-only access to the checkout. A locked package can still be audited; locking guards writes.

## Package audit (one repository)

From the repository root:

```bash
python3 -B skills/skill-library-maintenance/scripts/audit-skill-library.py skills --json
```

It reports main-file line and word counts, description length, files over the preferred and hard
thresholds, missing discovery fields, name/directory mismatches, and dangling references to package
support files.

Interpretation limits:

- Reference tokens resolve against the `SKILL.md`'s own package directory. A bare support-file path
  that belongs to another package is reported as `missing references` even though the file exists
  there; write a cross-package pointer with the owning skill's package name, or as prose without a
  bare path.
- A passing package audit is structural. It does not read instructions, and it does not prove the
  workflow works.
- Size thresholds are in `skill-builder/references/skill-quality-gates.md`; a line count alone is
  never a reason to split.

## Declaration audit (all roots)

This audits the runtime: the profile-local directory plus every `skills.external_dirs` entry
discovered from the active profile's configuration.

```bash
python3 -B skills/skill-library-maintenance/scripts/audit-skill-declarations.py --strict --json
```

Useful flags: `--root PATH[:LABEL]` (repeatable, explicit roots), `--threshold` (overlap threshold,
default 0.10), `--all` (include Hermes-managed bundled and hub-installed skills).

What the rows mean:

- **Name collisions across roots** — the loader fails closed, so the skill is unusable under its
  bare name. Exit code 1.
- **Local overrides** (`LOCAL OVERRIDES`) — exactly one profile-local hit plus exactly one external
  hit of the same name, printed with both paths. Runtime resolves the local package, so this is not
  a collision and does not fail the run. It is legitimate only while a development phase is open.
  Two local copies, two external copies, or a pair ambiguous on either side stay collisions.
- **Undeclared profile-local skills** (neither legacy `metadata.adapted_from` nor `metadata.scope:
  standalone`), scoped by `.usage.json` provenance so the list stays actionable: agent-created
  skills are listed in full, unattributed ones only when they overlap an external skill.
- **Overlap candidates** — token similarity over name plus description. A review list, not a verdict.

Exit code 1 on a collision; overrides alone exit 0. Under `--strict`, also 1 when an agent-created
skill is undeclared and overlaps an external skill. An overlap requires review and an explicit
development decision — it is never a reason to create or rename a skill into an adaptation.

## Legacy metadata

A package may carry `metadata.adapted_from` or `metadata.scope` from an older convention. The audit
reads it and reports it; reading it proves readability, not permission to create a new adaptation.
Do not add `adapted_from` to an ordinary working copy to silence a diagnostic, and do not derive a
new skill from a legacy field. A legacy marker is history, not an instruction.

## Validator and gates

- **Hermes authoring linter** is the structural gate. Run it from the installed source directory:

  ```bash
  cd ~/.hermes/hermes-agent && venv/bin/python -c "from pathlib import Path; from tools.skill_linter import lint_skill; print(lint_skill(Path('<package>/SKILL.md')))"
  ```

  Use the installed source directory when Hermes lives elsewhere; the interpreter must be that
  source's own `venv`. The pass criteria are defined in `skill-builder` step 8.
- **`skills-ref`** is a portability check, not a gate:

  ```bash
  bash skills/skill-builder/scripts/skills-ref.sh validate skills/<package>
  ```

  Field placement and the accepted result are defined in `skill-builder` step 5 and step 8; this
  audit only runs the check. If it cannot run, report it as not run — never as a pass.
- **Package tests**, where the package ships them:

  ```bash
  python3 -B -m pytest -p no:cacheprovider skills/<package>/tests -q
  ```

Report each gate separately. A schema pass does not certify the content, and the library audit does
not substitute for either.

## Archive inventory and recovery

`hermes curator archive <name>` is the supported archive path for a curator-eligible, profile-local
skill. It moves the directory and keeps a complete package; external canonical packages are refused
as read-only, and hub-installed or protected built-ins are refused as such.

Mechanics to state precisely:

- The destination is `$HERMES_HOME/skills/.archive/<name>` — flattened under the skill **name**, not
  the original directory name. On a collision the destination becomes
  `<directory-name>-<YYYYMMDDHHMMSS>` inside the same archive root, so read the actual path from the
  command instead of assuming it.
- `.archive/` is excluded from discovery: `skills_list` and `skill_view` never see it, and
  `hermes curator status` does not count those skills.
- `hermes curator list-archived` is the inventory; `hermes curator ledger --skill <name> --limit 5`
  shows the operation. Do not require an archived row in `hermes curator usage --json`, which can
  omit archived packages.
- `hermes curator restore <name>` is the only way back, CLI-only and ledgered as actor `user`. It
  restores to the flat `$HERMES_HOME/skills/<name>` path and does **not** rebuild `adaptations/` or
  any other category nesting. Restoring the original category path is a separate operator decision,
  never an automatic step.
- `restore` refuses a name that now collides with a hub-installed skill, and a bundled skill unless
  `curator.prune_builtins` is enabled. It also refuses when the destination path already exists.

Verification of any archive or restore:

1. Hash the complete package before and after; every file must match.
2. Confirm the active source is gone (archive) or present with the restored content (restore).
3. Confirm the name in `hermes curator list-archived` and read the ledger entry.
4. Expect `skill_view` to fail after archiving, and to resolve the flat path after restoring.
5. Prefer restore over re-creation: the archive copy is the complete artifact.

## Scoped diagnostics and limits

- Audit results describe the tree you ran them on. Re-run after every edit; an earlier result does
  not certify a later artifact.
- An override reports runtime precedence, never permission: it says which copy wins, not that
  opening it was authorized.
- An overlap is a prompt for a deliberate owner/development decision. It is not a migration order.
- Audits never edit files and never create adaptations, overlays or substitute skills.

## Verification

- Package audit completes without hard errors.
- Declaration audit: no unintended collision; overrides only for open phases.
- Hermes linter reports no structural finding; `skills-ref` shows only the expected frontmatter
  finding.
- Archive inventory and hashes match where an archive operation was part of the task.

## Stop and recovery

- Roots missing or unreadable: report which root failed; do not substitute a guessed path.
- A collision in a released tree: stop and report; do not resolve it by deleting one of the copies.
- An audit that cannot run: report it as not run. Never convert an unrun check into a pass.
