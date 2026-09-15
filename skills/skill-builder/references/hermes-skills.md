# Hermes Agent Skills

Use this reference when Hermes Agent is the target runtime.

## Authorities

Portable format:

- https://agentskills.io/specification
- https://agentskills.io/skill-creation/best-practices

Hermes behavior:

- https://hermes-agent.nousresearch.com/docs/developer-guide/creating-skills
- https://hermes-agent.nousresearch.com/docs/user-guide/features/skills

The Agent Skills specification remains the base. Hermes documentation governs Hermes-only discovery, metadata, tools, and runtime behavior.

## Hermes extensions

Hermes supports nested metadata such as:

```yaml
metadata:
  author: Example Author
  version: "1.0.0"
  source: https://example.com/owner/repository
  hermes:
    category: personal
    tags:
      - skills
    related_skills:
      - skill-governance
```

`metadata.hermes` is a Hermes extension. The base specification documents `metadata` as additional metadata but does not define these nested Hermes keys.

Hermes bundled skills may also use native top-level fields such as:

```yaml
version: 1.0.0
author: Example Author
platforms:
  - macos
  - linux
```

Top-level `version`, `author`, and `platforms` are not fields defined by the portable Agent Skills specification. Use them only when the owning repository explicitly follows Hermes-native conventions.

Do not duplicate `version` or `author` at both levels.

## Location and ownership

Hermes can discover skills from profile-local storage and configured `skills.external_dirs`. Discovery does not decide ownership.

Before writing:

1. classify the skill as owned or third-party;
2. determine the canonical repository from profile and repository rules;
3. read the canonical repository's `AGENTS.md`;
4. check for same-name shadows in higher-precedence locations.

For the full ownership and routing rules, load `skill-governance`.

## Creating and editing

- Use `skill_manage` for an existing owned skill resolved from the profile or an external directory.
- Do not use `skill_manage(create)` unless its configured creation root is the intended canonical repository.
- When several external repositories exist and `skills.create_dir` cannot select among them, create the new package directly in the chosen canonical repository.
- Never edit a third-party skill directly.

After creation or movement, load the skill and inspect `_source_path`.

## Hermes validation

After portable validation:

1. Load the skill with `skill_view`.
2. Confirm `description`, `metadata`, tags, and related skills.
3. Confirm `_source_path` points to the canonical repository.
4. Confirm linked files appear and load successfully.
5. Check required commands, variables, and readiness.
6. Search configured roots for duplicate skill names.

A Hermes advisory linter may prefer Hermes-native top-level metadata even when the portable `skills-ref` validator accepts `metadata.version` and `metadata.author`. Treat that as a convention difference, not evidence that the portable fields are invalid.

## Prompt budget

Hermes may impose a stricter indexed-description budget than the Agent Skills limit. Keep the first 57 characters self-contained and trigger-focused where profile rules require it.

## Tool and platform declarations

Use Hermes-specific tool, environment, platform, or blueprint metadata only when the feature is required. Verify current Hermes documentation before adding it; do not copy stale examples from an older skill.
