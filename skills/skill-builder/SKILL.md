---
name: skill-builder
description: "Use when authoring or validating a skill package."
version: "1.0.0"
author: Olaf Geibig
license: MIT
compatibility: Requires network access for current documentation and uv for bundled skills-ref validation
metadata:
  source: https://github.com/olafgeibig/skills
  hermes:
    category: personal
    tags:
      - skills
      - authoring
      - validation
      - hermes
    related_skills:
      - skill-governance
      - skill-library-maintenance
---

# Skill Builder

How is a package written and changed? This skill owns the format, frontmatter, versioning, safe
editing and validation of a skill package. It does not decide where knowledge belongs or who may
write it (`skill-governance`), and it does not run the release lifecycle (`skill-library-maintenance`).

## When to Use

- Create a new `SKILL.md` package.
- Improve an existing skill's scope, trigger, workflow, references, templates, or scripts.
- Validate frontmatter and package structure.
- Convert reusable agent instructions into a skill.
- Decide whether a field or workflow is portable, Hermes-specific, or Claude Code-specific.

## Authorities

Refresh these sources whenever format requirements may have changed:

- https://agentskills.io/specification
- https://agentskills.io/skill-creation/best-practices
- https://agentskills.io/skill-creation/optimizing-descriptions
- https://agentskills.io/skill-creation/using-scripts

Treat these as the portable base. Client-specific behavior belongs in local references:

- `references/hermes-skills.md` — Hermes discovery, extensions, locations, tools, and validation.
- `references/hermes-frontmatter.md` — this library's frontmatter variant, field placement, description budget, audit and normalize procedures.
- `references/claude-code-skills.md` — Claude Code-specific locations and agent-to-skill conversion.

Do not present client extensions as fields defined by the base specification.

## Workflow

### 1. Determine ownership and target

Before writing:

1. Identify the owner and canonical repository.
2. Read its `AGENTS.md` or equivalent local rules.
3. Load `skill-governance` for ownership, routing, permission and the unlock rule.
4. For an existing skill, load its current `SKILL.md` and every supporting file that will change.
5. Decide whether the result targets portable Agent Skills, Hermes, Claude Code, or a documented combination.

Do not infer ownership from a frontmatter category. Do not create an accidental or undeclared shadow of a canonical external skill. An existing owned skill that has been released is not edited in place: its change happens in an explicitly opened development phase with a complete working copy (whole package, same directory and name, recorded baseline, one owner). Opening, reviewing, publishing and closing that phase is `skill-library-maintenance`: open with `develop-skill.md`, then `review-skill.md`, `publish-skill.md`, `close-development.md`. The working copy is the only legitimate same-name local package; a locked source is not a reason to create an adaptation, a variant name or a second package.

For an external target, verify three independent properties before writing: the directory exists, its Git root is the intended canonical repository, and the target profile actually discovers it. A familiar project shelf is not necessarily a repository or a configured skill source. Resolve conflicting paths from live configuration rather than copying a path from an older skill; use `references/hermes-skills.md` for the checks. If the destination remains a user decision, ask once with the verified alternatives and do not treat a timeout as approval.

### 2. Define the skill boundary

Write down:

- the task or workflow the skill owns;
- the situations that should trigger it;
- adjacent skills it must not duplicate;
- required tools or environment constraints;
- the concrete verification that proves the workflow works.

Before writing, run the routing gate in `skill-governance`: search for an overlapping skill and pick one of the declared forms — a delta in the owning skill, a genuinely standalone skill that declares `metadata.scope: standalone`, or, when the target is an existing owned skill, an explicitly opened working copy of it. A profile-local skill that quietly overlaps or narrows an existing one is a defect, not a new skill.

Keep project facts in project content, not reusable skills.

### 3. Choose a valid name and description

- `name` must match the parent directory and satisfy the Agent Skills syntax rules.
- Follow the owning repository's naming convention. This repository prefers concise noun phrases; gerunds remain valid.
- `description` must state both what the skill does and when to use it.
- Keep the description within the 1024-character specification limit and any stricter client prompt budget.
- Prefer one trigger-focused sentence over a keyword dump.

See `references/metadata-requirements.md` for the field matrix and examples. Apply the package-size and consistency checks in `references/skill-quality-gates.md`.

### 4. Build the package

Minimum package:

```text
skill-name/
└── SKILL.md
```

Add only what the workflow needs:

```text
skill-name/
├── SKILL.md
├── references/
├── scripts/
├── assets/
└── templates/
```

The specification defines `scripts/`, `references/`, and `assets/`; additional directories such as `templates/` are permitted. Keep references one level deep where practical.

Use progressive disclosure:

- `SKILL.md` contains the trigger, decisions, core procedure, pitfalls, and verification.
- `references/` contains detailed methodology or client-specific behavior.
- `scripts/` contains executable helpers with documented dependencies and useful errors. Scripts run **in place** from the skill tree — do not design a copy-into-profile-directory mechanism: a copy drifts from the checked-out version and needs its own version sync. A generated artifact outside the skill is justified only where a stable path is required by something external (a byte-stable hook wrapper whose consent records its mtime; a thin shim a scheduler insists on loading from a fixed directory), and it must be rendered from a `templates/` file that carries no logic.
- `assets/` or `templates/` contains material copied into outputs rather than loaded as instructions.

See `references/skill-structure-and-format.md` and `templates/skill-template.md`.

### 5. Write frontmatter in the Hermes variant

The rule in this library: `version`, `author` and `license` sit at the top level for **every root** — profile-local and repository packages alike — and `metadata` carries the rest.

```yaml
---
name: skill-name
description: "Use when performing a clearly bounded task."
version: "1.0.0"
author: Example Author
license: MIT
metadata:
  source: https://example.com/owner/repository
  hermes:
    category: personal
    tags:
      - topic
---
```

- `version` — semantic version string, quoted; bump it whenever the skill or its supporting behavior changes.
- `author` — the human owner when attribution is maintained; `license` — license name or reference.
- `metadata.source` — the owning repository URL when one exists; `metadata.hermes.tags` and `related_skills` — block lists.
- Never duplicate `author` or `version` at both levels.

**The agentskills.io layout is the foreign standard here**: it places `author` and `version` under `metadata`, so a package built that way fails `skills-ref` on exactly those two fields. Field-by-field comparison: `references/hermes-frontmatter.md`.

Version rules (semantic): **patch** for a typo, wording, metadata-only change or small clarification; **minor** for substantive additive guidance, new sections or new references; **major** for a breaking change in scope, workflow or expected behavior. Every content change bumps the version; inside a development phase bump once, at review time, rather than on every edit.

Field placement detail, the description budget, audit and normalize procedures, and pitfalls: `references/hermes-frontmatter.md`.

### 6. Write actionable instructions

- State decisions and procedures as direct instructions.
- Include exact commands only when they are stable and necessary.
- Document required parameters, failure conditions, and verification.
- Do not include invented output, incomplete command placeholders, or untested claims.
- Use the scripting language and tool policy of the owning repository. This repository prefers Python for Hermes-adjacent tooling; that is not an Agent Skills specification rule.
- Keep `SKILL.md` under 500 lines; aim for roughly 150–200 when practical.
- Write rules, not incidents: imperative plus one clause of why. Never add a dated batch or diary file to hold findings for later sorting — classify each finding in the session it arises (`skill-governance` → Capture Discipline).

See `references/skill-best-practices.md` and `references/skill-quality-gates.md`. For repository-approved Python helpers, see `references/python-and-cli-patterns.md`.

### 7. Edit safely

For existing skills:

1. Identify the specific defect or missing capability.
2. Make the smallest coherent change that fixes it.
3. Update affected references and templates in the same change.
4. Remove contradictory legacy guidance.
5. Bump the version per step 5.

**Hard write rules:**

- **Read before write (enforced).** `skill_view(name)` before patching an existing `SKILL.md`; `skill_view(name, file_path=...)` before overwriting an existing supporting file. Content quoted earlier in the transcript does not count — a fresh load is required.
- Use `skill_manage` for existing skills resolved from the profile or an external directory: it patches in place with native validation, ledger, cache invalidation and security hooks. Use `write_file` for supporting files and targeted `patch`/`remove_file` over full rewrites.
- While a same-name working copy is open, the bare name resolves to that copy — it is not the released package.
- `skill_manage(action="create")` writes only to the profile-local skills directory or the single configured `skills.create_dir`. Use it when that resolved root is the intended one. A skill destined for the released canonical library is built profile-local and published through the maintenance lifecycle (`skill-library-maintenance` → `develop-skill.md`, `publish-skill.md`); only an unlocked owned repository (a project skill) is written in place.
- **Reference steps must be literally executable.** Never nest a tool call inside another tool call's argument (`write(content=fetch(url))`); split nested operations into sequential steps.
- Re-read the saved file and verify its frontmatter.
- **Never edit a third-party skill's `SKILL.md`** — report the proposed change instead.

**A released skill changes through the maintenance lifecycle, not by patching the canonical file:** open the phase (`skill-library-maintenance` → `develop-skill.md`), review the complete package (`review-skill.md`), publish the reviewed bytes (`publish-skill.md`), close and re-lock (`close-development.md`). This skill supplies authoring quality; it carries no second handoff or publication runbook.

Ordinary Git safety still applies when you prepare a change: preserve unrelated dirty work byte-for-byte, stage explicit paths, keep one coupled change per commit, and work on local `main` only when the user has explicitly chosen it. Commit, push and PR creation are separate authorization scopes, and there is no autonomous pull/push/transport-branch model.

See `references/editing-skills-guide.md` for change classes, structural moves and versioning.

### 8. Validate the two gates

**The Hermes authoring linter is the structural gate.** From the installed source:

```bash
cd ~/.hermes/hermes-agent && venv/bin/python -c "from pathlib import Path; from tools.skill_linter import lint_skill; print(lint_skill(Path('<package>/SKILL.md')))"
```

Expect no `missing-metadata` and no `dangling-reference` finding.

**The library audit is the second gate:** the package audit and the declaration audit, with commands and interpretation in `skill-library-maintenance` → `audit-library.md`. It catches cross-package support-file pointers that the linter accepts.

**`skills-ref` is an optional portability check, not a gate:**

```bash
bash skills/skill-builder/scripts/skills-ref.sh validate skills/<skill-name>
```

With the Hermes frontmatter variant its expected and accepted finding is exactly `Unexpected fields in frontmatter: author, version`. Any other finding is a defect. If it cannot run, report it as not run — never as a pass.

Then verify the target client:

- Hermes: load with `skill_view`, confirm `_source_path` for the **phase** — the working copy while it is active, the canonical package after close — plus linked files, metadata, and readiness.
- Other clients: use their current discovery or validation mechanism.

Also verify:

- the directory name equals `name`;
- every referenced file exists;
- no unintended duplicate shadows the canonical package (an explicitly opened working copy is the intended exception);
- scripts execute successfully when present;
- changed examples and commands were exercised;
- repository status contains only intended changes.

A validator proves frontmatter and structural conformance; it does not prove that every instruction in supporting Markdown is current or correct. Run both gates over the touched tree after the last edit.

## Client-Specific Rules

### Hermes

Load `references/hermes-skills.md` before creating or editing a Hermes skill, and `references/hermes-frontmatter.md` for the field rules. They define:

- `metadata.hermes` extensions and Hermes-native top-level fields;
- external-directory and `skill_manage` behavior;
- runtime validation and source-path checks;
- discovery gating for a skill that must stay out of the prompt index.

Load `references/profile-skill.md` when the deliverable is a profile-local skill: what belongs in it (host and profile facts, paths, external-directory roles, installation settings, pointers to the installation's notes) and what does not.

### Claude Code

Load `references/claude-code-skills.md` only when Claude Code is the explicit target or source. Its paths and sub-agent concepts must not leak into generic or Hermes workflows.

## Pitfalls

- Do not confuse validator acceptance with pure specification-only metadata; clients may accept extensions.
- Do not claim `allowed-tools` is forbidden; it is an experimental standard field with client-dependent support.
- Do not require gerund names; that is a style choice, not a specification rule.
- Do not impose Node.js, Python, or another language universally; follow the target repository.
- Do not retain old client documentation URLs as standards authorities.
- Do not update only `SKILL.md` when its bundled template or references contradict it.
- Do not treat a `skills-ref` frontmatter finding as a defect to fix by moving fields: the Hermes variant is the rule, and the finding is the accepted portability result.
- Do not create an adaptation package, a `<source>-adaptation` sibling or a variant name to work around a locked or third-party source.

## Verification

Before finishing:

- Official Agent Skills references are current.
- Ownership and canonical location are confirmed.
- Frontmatter follows the Hermes variant: top-level `version`, `author`, `license`.
- Client extensions are explicitly labeled.
- Any new profile-local skill declares `metadata.scope: standalone`; no adaptation package and no unnamed local delta was created.
- No staging, batch, or diary file was created, and any added rule was first searched against its target.
- A released canonical skill changed only through its development phase, with the reviewed package approved before publication.
- The entire changed package is internally consistent.
- The Hermes authoring linter and the library audit pass; `skills-ref` shows only the expected portability finding.
- Client loading and source resolution pass.
- Version is bumped and repository state is verified.
