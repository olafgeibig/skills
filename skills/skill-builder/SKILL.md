---
name: skill-builder
description: "Use when creating or maintaining Agent Skills."
license: MIT
compatibility: Requires network access for current documentation and uv for bundled skills-ref validation
metadata:
  source: https://github.com/olafgeibig/skills
  version: "0.4.0"
  author: Olaf Geibig
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

Create and maintain Agent Skills using the portable Agent Skills specification as the base. Apply client-specific conventions only when the target repository or runtime requires them.

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
- `references/claude-code-skills.md` — Claude Code-specific locations and agent-to-skill conversion.

Do not present client extensions as fields defined by the base specification.

## Workflow

### 1. Determine ownership and target

Before writing:

1. Identify the owner and canonical repository.
2. Read its `AGENTS.md` or equivalent local rules.
3. Load `skill-governance` for ownership, routing, read-before-write, and versioning.
4. For an existing skill, load its current `SKILL.md` and every supporting file that will change.
5. Decide whether the result targets portable Agent Skills, Hermes, Claude Code, or a documented combination.

Do not infer ownership from a frontmatter category. Do not create a profile-local shadow of a canonical external skill.

### 2. Define the skill boundary

Write down:

- the task or workflow the skill owns;
- the situations that should trigger it;
- adjacent skills it must not duplicate;
- required tools or environment constraints;
- the concrete verification that proves the workflow works.

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
- `scripts/` contains executable helpers with documented dependencies and useful errors.
- `assets/` or `templates/` contains material copied into outputs rather than loaded as instructions.

See `references/skill-structure-and-format.md` and `templates/skill-template.md`.

### 5. Write portable frontmatter deliberately

Portable baseline:

```yaml
---
name: skill-name
description: "Use when performing a clearly bounded task."
license: MIT
metadata:
  author: Example Author
  version: "1.0.0"
  source: https://example.com/owner/repository
---
```

The specification defines `name`, `description`, `license`, `compatibility`, `metadata`, and experimental `allowed-tools` at the top level. It shows `author` and `version` under `metadata`.

Do not duplicate `author` or `version` at multiple levels. Use the owning repository's single authoritative convention.

Hermes-specific nested metadata and Hermes-native top-level fields are documented in `references/hermes-skills.md`.

### 6. Write actionable instructions

- State decisions and procedures as direct instructions.
- Include exact commands only when they are stable and necessary.
- Document required parameters, failure conditions, and verification.
- Do not include invented output, incomplete command placeholders, or untested claims.
- Use the scripting language and tool policy of the owning repository. This repository prefers Python for Hermes-adjacent tooling; that is not an Agent Skills specification rule.
- Keep `SKILL.md` under 500 lines; aim for roughly 150–200 when practical.

See `references/skill-best-practices.md` and `references/skill-quality-gates.md`. For repository-approved Python helpers, see `references/python-and-cli-patterns.md`.

### 7. Edit safely

For existing skills:

1. Identify the specific defect or missing capability.
2. Make the smallest coherent change that fixes it.
3. Update affected references and templates in the same change.
4. Remove contradictory legacy guidance.
5. Bump the skill version according to `skill-governance` and the repository convention.

See `references/editing-skills-guide.md`.

### 8. Validate both layers

Run the bundled reference validator from the owning repository root:

```bash
bash skills/skill-builder/scripts/skills-ref.sh validate skills/<skill-name>
```

Adjust the path for other repository layouts.

Then verify the target client:

- Hermes: load with `skill_view`, confirm `_source_path`, linked files, metadata, and readiness.
- Other clients: use their current discovery or validation mechanism.

Also verify:

- the directory name equals `name`;
- every referenced file exists;
- no duplicate skill shadows the canonical package;
- scripts execute successfully when present;
- changed examples and commands were exercised;
- repository status contains only intended changes.

The reference validator proves frontmatter and structural conformance. It does not prove that every instruction in supporting Markdown is current or correct.

## Client-Specific Rules

### Hermes

Load `references/hermes-skills.md` before creating or editing a Hermes skill. It defines:

- `metadata.hermes` extensions;
- Hermes-native top-level extensions;
- profile-local adaptations and `templates/adaptation-skill-template.md`;
- external-directory and `skill_manage` behavior;
- runtime validation and source-path checks.

### Claude Code

Load `references/claude-code-skills.md` only when Claude Code is the explicit target or source. Its paths and sub-agent concepts must not leak into generic or Hermes workflows.

## Pitfalls

- Do not confuse validator acceptance with pure specification-only metadata; clients may accept extensions.
- Do not claim `allowed-tools` is forbidden; it is an experimental standard field with client-dependent support.
- Do not require gerund names; that is a style choice, not a specification rule.
- Do not impose Node.js, Python, or another language universally; follow the target repository.
- Do not retain old client documentation URLs as standards authorities.
- Do not update only `SKILL.md` when its bundled template or references contradict it.

## Verification

Before finishing:

- Official Agent Skills references are current.
- Ownership and canonical location are confirmed.
- Frontmatter uses one documented convention.
- Client extensions are explicitly labeled.
- The entire changed package is internally consistent.
- `skills-ref` validation passes.
- Client loading and source resolution pass.
- Version is bumped and repository state is verified.
