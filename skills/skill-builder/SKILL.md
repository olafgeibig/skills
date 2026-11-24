---
name: skill-builder
description: "Use when authoring, editing or validating a skill."
version: "2.0.0"
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
---

# Skill Builder

How is a skill package written, structured, and validated? This skill owns package format,
frontmatter, versioning, progressive disclosure, safe editing, and validation. For ownership,
categories, locking, routing, or release lifecycle, load `skill-governance`.

## When to Use

- Create a new `SKILL.md` package.
- Improve an existing skill's scope, trigger, workflow, references, templates, or scripts.
- Validate frontmatter, structure, size, and links.
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

### 1. Prepare target & boundary

1. Confirm ownership, category, and lock state via `skill-governance` before writing.
2. For an existing skill, load its current `SKILL.md` and every supporting file that will change.
3. Define the skill boundary:
   - the task or workflow the skill owns;
   - the situations that should trigger it;
   - adjacent skills it must not duplicate;
   - required tools or environment constraints;
   - concrete verification that proves the workflow works.
4. Decide whether the result targets portable Agent Skills, Hermes, Claude Code, or a documented combination.

Keep project facts in project content, not reusable skills.

### 2. Choose a valid name and description

- `name` must match the parent directory and satisfy the Agent Skills syntax rules.
- Follow the owning repository's naming convention. This repository prefers concise noun phrases; gerunds remain valid.
- `description` must state both what the skill does and when to use it.
- Keep the description within the 1024-character specification limit and any stricter client prompt budget (Hermes: 57 characters).
- Prefer one trigger-focused sentence over a keyword dump.

See `references/metadata-requirements.md` and `references/skill-quality-gates.md`.

### 3. Build the package (progressive disclosure)

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

- `SKILL.md` contains the trigger, decisions, core procedure, pitfalls, and verification.
- `references/` contains detailed methodology or client-specific behavior.
- `scripts/` contains executable helpers with documented dependencies and useful errors. Scripts run **in place** from the skill tree — do not design a copy-into-profile-directory mechanism.
- `assets/` or `templates/` contains material copied into outputs rather than loaded as instructions.

See `references/skill-structure-and-format.md` and `templates/skill-template.md`.

### 4. Write frontmatter in the Hermes variant

In this library, `version`, `author` and `license` sit at the top level for **every root**, and `metadata` carries the rest:

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
- `author` — human owner when attribution is maintained; `license` — license name or reference.
- `metadata.source` — owning repository URL when one exists; `metadata.hermes.tags` and `related_skills` — block lists.
- Never duplicate `author` or `version` at both levels.

**Version rules (semantic):** **patch** for typos, wording, metadata-only changes or small clarifications; **minor** for substantive additive guidance, new sections or new references; **major** for breaking changes in scope, workflow or expected behavior.

Field placement detail, description budget, and pitfalls: `references/hermes-frontmatter.md`.

### 5. Write actionable instructions

- State decisions and procedures as direct instructions.
- Include exact commands only when they are stable and necessary.
- Document required parameters, failure conditions, and verification.
- Do not include invented output, incomplete command placeholders, or untested claims.
- Keep `SKILL.md` under 500 lines; aim for roughly 150–200 when practical.
- Write rules, not incidents: imperative plus one clause of why.
- Reference steps must be literally executable — never nest a tool call inside another tool call's argument.

See `references/skill-best-practices.md`, `references/skill-quality-gates.md`, and `references/python-and-cli-patterns.md`.

### 6. Edit safely

For existing skills:

1. Identify the specific defect or missing capability.
2. Make the smallest coherent change that fixes it.
3. Update affected references and templates in the same change.
4. Remove contradictory legacy guidance.
5. Bump the version per step 4.
6. Re-read the saved file and verify its frontmatter.

**Read before write:** load `skill_view(name)` before patching `SKILL.md`, and `skill_view(name, file_path=...)` before overwriting a supporting file. Use targeted `patch`/`remove_file` over full rewrites. See `references/editing-skills-guide.md` for change classes and structural moves.

### 7. Validate the two gates

**Gate 1 — Hermes authoring linter:**

```bash
cd ~/.hermes/hermes-agent && venv/bin/python -c "from pathlib import Path; from tools.skill_linter import lint_skill; print(lint_skill(Path('<package>/SKILL.md')))"
```

Expect no `missing-metadata` and no `dangling-reference` finding.

**Gate 2 — Library audit:** run the package and declaration audits via `skill-governance` (`audit-library.md`).

**Optional portability check (`skills-ref`):**

```bash
bash skills/skill-builder/scripts/skills-ref.sh validate skills/<skill-name>
```

With the Hermes frontmatter variant its expected finding is `Unexpected fields in frontmatter: author, version`. Any other finding is a defect.

Then verify the target client (`skill_view`, `_source_path`, linked files, directory name == `name`, scripts execute).

## Client-Specific Rules

- **Hermes:** Load `references/hermes-skills.md` and `references/hermes-frontmatter.md`. For a profile-local setup skill, also load `references/profile-skill.md`.
- **Claude Code:** Load `references/claude-code-skills.md` only when Claude Code is the explicit target or source.

## Pitfalls

- Do not confuse validator acceptance with pure specification-only metadata; clients may accept extensions.
- Do not claim `allowed-tools` is forbidden; it is an experimental standard field with client-dependent support.
- Do not require gerund names; that is a style choice, not a specification rule.
- Do not update only `SKILL.md` when its bundled template or references contradict it.
- Do not treat the expected `skills-ref` frontmatter finding (`author, version`) as a defect to fix by moving fields.

## Verification

- Frontmatter follows the Hermes variant (top-level `version`, `author`, `license`).
- Package is internally consistent, within quality gates, and version-bumped.
- Hermes authoring linter and library audit pass; client loads the skill cleanly.
