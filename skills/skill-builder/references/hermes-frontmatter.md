# Hermes Frontmatter

How a `SKILL.md` frontmatter block is written in this library, how to audit a set for conformity,
and how to normalize a batch without touching a byte of body text.

## When to load

Repairing or validating frontmatter, normalizing a batch of skills, or when the authoring linter
reports a metadata, description-budget or dangling-reference finding.

## The rule: one placement for every root

`version`, `author` and `license` are **top-level**, in profile-local and repository packages alike.
Everything else that describes the skill sits under `metadata`.

```yaml
---
name: skill-name
description: "Use when doing one bounded thing."
version: "1.0.0"
author: Example Author
license: MIT
compatibility: Optional runtime requirement
metadata:
  source: https://example.com/owner/repository
  scope: standalone
  hermes:
    category: own
    tags:
      - topic
    related_skills:
      - neighbouring-skill
---
```

The portable agentskills.io layout differs: it defines top-level `name`, `description`, `license`,
`compatibility`, `allowed-tools` and `metadata`, and shows `author` and `version` under `metadata`.
That is the foreign standard; a package written to it passes `skills-ref`, and this library's packages
deliberately do not. `skills-ref` is a portability check, not a gate: its expected, accepted finding
on this frontmatter is `Unexpected fields in frontmatter: author, version`.

Three declaration rules that bite:

- Every list is a **block list** — a library convention, not a linter rule: the Hermes linter overlooks
  flow style, while `skills-ref` rejects it as `Found ugly disallowed JSONesque flow mapping`. PyYAML
  parses both, so a flow list reads as valid YAML and still fails portability.
- `description` stays within **57 characters**: one trigger sentence ending in a period. Hermes
  `create` refuses only above 60; past 60 the index shows 57 characters plus an ellipsis, so author to
  57 and the trigger stays whole. It is triage, not documentation: no code identifiers or backticks,
  no dates, no inline trigger lists, no commentary about sibling skills. Detail belongs in the body.
- `metadata` carries declaration, not history: no `created`/`updated` dates, no `supersedes` or
  `umbrella_of` narration. Dates go stale and a target that no longer exists is a dead link nothing
  checks; record history in the body or the repository.

`platforms:` is the one deliberate top-level exception: Hermes reads it as an OS gate even though the
strict specification does not know the field. Do not strip a working gate to silence a validator.

## Procedure: audit a set for conformity

Read-only first pass; the repair is a separate pass with its own backup, and the user decides which
findings get fixed.

1. Lint the whole set with the authoring linter — it is the cross-check for everything mechanical:

   ```bash
   cd ~/.hermes/hermes-agent && python3 - <<'EOF'
   import sys; sys.path.insert(0, ".")
   from tools.skill_linter import lint_skill
   from pathlib import Path
   root = Path.home() / ".hermes/skills/own"          # or any skill root
   for d in sorted(p for p in root.iterdir() if p.is_dir()):
       f = d / "SKILL.md"
       if f.exists():
           for x in lint_skill(f):                     # fields: severity, rule, message
               print(f"{d.name}: {x.severity} {x.rule} — {x.message}")
   EOF
   ```

   It reports missing metadata (`license`/`version`/`author`/`metadata.hermes.tags`), description
   length, dangling references, shell-utility prose, missing `## When to Use`, and oversized bodies.
2. Hand-check only what the linter misses: history junk in `metadata`, the description content
   criteria (word count, colon, backticks, trigger lists, multi-sentence), flow-style lists, and
   `name` ↔ directory mismatches.
3. Report one line per finding: skill name, file path, the rule violated — plus a replacement
   description (≤57 characters) for every over-budget one in the same pass.

## Procedure: normalize a batch in one pass

1. Dry-run first, per file: `python3 <skill-dir>/scripts/normalize-skill-frontmatter.py <path>
   --category own --scope standalone --bump patch --dry-run`. It promotes `version`/`author` to top
   level (correct in every root here), adds `metadata.hermes.category` and `metadata.scope` **only
   when you pass the flags**, converts flow lists to block lists, and bumps the version. Without the
   flags it adds no declaration and does not fail for the absence.
2. **A real run writes files directly, so it is limited to writable targets:** an open working copy
   of a skill in its development phase, or a profile-local package. A released canonical package is
   normalized inside its own phase — never by a batch run across the library. For such a package,
   apply the dry-run output through `skill_manage` as a frontmatter-block patch — `old_string` is the
   current block, `new_string` the dry-run block, per the route below.
3. Back the files up first (`cp -a` into a backup directory), run with `--backup-dir`, then verify
   the changed files with the authoring linter and the library audit.
4. Verify discovery, not just validity: `hermes skills list` must show the expected entries. A valid
   file the loader does not see is still broken.

### Route the batch through `skill_manage`, never around it

The pass may be computed by a script, but every write to an existing skill goes through
`skill_manage`: that is what validates the frontmatter, appends the ledger, and bumps `patch_count`.
Read the file inside the script and pass the exact current frontmatter block as `old_string` and the
rebuilt block as `new_string`; never hand-transcribe a long block and never rewrite the whole
`SKILL.md`. Then re-read and assert that the body after the closing `---` is byte-identical. Split the
pass in two halves: declarations (scriptable) and `description` text (hand-authored, one sentence,
≤57 characters).

## Pitfalls

- **Inline colons in `description` fail YAML parsing silently.** `description: … Trigger words: "X"`
  makes YAML read the list label as a nested key and abort with `mapping values are not allowed
  here`; a skill whose frontmatter fails to parse never loads and no error reaches the user. Keep the
  description colon-free (em dash), move the list into the body, or use a YAML literal block.
- **Split before parsing, re-attach after dumping.** Parse only the block between the `---` fences,
  never the whole file: `yaml.safe_load` over a body containing tables or horizontal rules either
  fails or silently eats content. Assert the body is byte-identical after the write.
- **Dump with `sort_keys=False, default_flow_style=False`.** Default sorting reshuffles
  `name`/`description`/`metadata`; leaving flow style on reintroduces the list style the validator
  rejects.
- **`create` does not write the category into the frontmatter** — the directory decides it
  (`category="own"` writes to `own/<name>/`). Declare `metadata.hermes.category` yourself so humans
  and audits see what the loader infers. Never pass a `category` while `skills.create_dir` already
  points at that directory: the two combine into `<dir>/<category>/<name>`.
- **A frontmatter pass fixes declarations, not content.** Duplicated H1s, duplicated tag blocks, stale
  cross-references and numbering gaps survive it — check the body separately, and re-read the saved
  file with its parsed frontmatter and body length before reporting success.
- **Verify `dangling-reference` and `missing references` findings before reporting them** — both
  resolve `references/<file>` against the reporting skill's own directory. A prose pointer to a
  *sibling skill's* file is flagged where it is written; write a cross-package pointer with the owning
  skill's package name (`skill-name/references/file.md`) or as prose without a bare path. Purely
  historical narration is not a defect.
- **`missing-section` wants the heading `## When to Use` by exactly that name.** `## Trigger`, `## When
  This Skill Activates` and `## When` are flagged the same as none at all. Rename the heading instead
  of writing new content.
- **Resolve `related_skills` against every skill root before calling a name dangling:** the profile
  `skills/` tree, `skills.external_dirs`, and the bundled `skills/`/`optional-skills/` trees.
- **A leftover `HERMES_HOME` turns every `skill_manage` patch into a fake cross-profile error.**
  `_resolve_active_profile_name()` derives the profile from `HERMES_HOME`, so a temporary home exported
  by an earlier probe makes the pass fail with `Skill 'X' not found in active profile`. Unset it (or
  point it at the real home) and confirm the resolved skills directory before re-running.

## Verification

- Every `version`, `author` and `license` is top-level; no value appears at both levels.
- Every list is a block list; every description is ≤57 characters and colon-free.
- The authoring linter reports no `missing-metadata` or `dangling-reference` finding.
- `skills-ref` shows only the expected portability finding, or is reported as not run.
- The body is byte-identical to the pre-normalization body.
