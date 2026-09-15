# Skill Structure and Format

## Package structure

Every skill is a directory containing `SKILL.md`:

```text
skill-name/
├── SKILL.md
├── references/
├── scripts/
├── assets/
└── templates/
```

Only `SKILL.md` is required. The Agent Skills specification recommends `scripts/`, `references/`, and `assets/`; other directories are permitted.

## `SKILL.md`

Use YAML frontmatter followed by Markdown instructions:

```yaml
---
name: skill-name
description: "Use when performing a clearly bounded task."
metadata:
  author: Example Author
  version: "1.0.0"
---

# Skill Name

## When to Use

## Procedure

## Pitfalls

## Verification
```

Use `references/metadata-requirements.md` for the complete field rules.

## Progressive disclosure

Structure the package around when information is needed:

1. `name` and `description` support discovery.
2. `SKILL.md` supplies the core procedure after activation.
3. Supporting files are loaded only when the task needs them.

Keep `SKILL.md` under 500 lines and preferably around 150–200. Move detailed methodology, large examples, command catalogs, and client-specific behavior into focused references.

## Supporting files

Use lowercase, intention-revealing names:

```text
references/frontmatter-rules.md
references/service-deployment.md
scripts/validate-output.js
assets/report-example.json
templates/report-template.md
```

Avoid vague names such as `reference.md`, `helpers.md`, or `misc.md`.

Reference files from the skill root:

```markdown
See `references/service-deployment.md` for the deployment procedure.
Run `scripts/validate-output.js` to validate the generated result.
```

Keep references one level deep where practical. A reference should not require a long chain of additional references to become useful.

## Scripts

Scripts must:

- be self-contained or document their dependencies;
- validate required inputs;
- produce useful error messages;
- avoid exposing secrets;
- have a verification command;
- follow the owning repository's language and platform policy.

The Agent Skills specification permits common scripting languages including Python, Bash, and JavaScript. A repository may impose a narrower rule.

## Client-specific behavior

Keep client rules separate from the portable structure:

- Hermes: `references/hermes-skills.md`
- Claude Code: `references/claude-code-skills.md`

Do not place a client-specific installation path into a generic template.
