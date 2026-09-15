# Skill Authoring Best Practices

## Keep the main skill focused

`SKILL.md` should contain only the guidance needed whenever the skill activates:

- when to use the skill;
- scope boundaries and key decisions;
- core procedure;
- important pitfalls;
- verification.

Move detailed background, extensive examples, client-specific behavior, and command catalogs into focused references.

## Write for execution

- Use direct instructions.
- Make commands complete and runnable.
- State required parameters and failure conditions.
- Verify outputs rather than describing expected success without execution.
- Remove background knowledge an capable agent already has.
- Do not include incident histories when a reusable rule is enough.

## Design the description carefully

The description is the main discovery signal. It should:

- state what the skill does;
- state when it should activate;
- distinguish the skill from adjacent capabilities;
- stay concise enough for the target client's prompt budget.

Good:

```yaml
description: "Use when creating or maintaining Agent Skills."
```

Weak:

```yaml
description: "A powerful skill helper for many workflows."
```

## Prefer one authoritative rule

Avoid duplicated values and duplicated procedures:

- one version field;
- one canonical repository;
- one primary procedure for a task;
- one client-specific reference per client.

Duplication creates drift and contradictory instructions.

## Follow the owning repository

The Agent Skills specification does not mandate:

- gerund names;
- a universal scripting language;
- a specific client installation path;
- semantic versioning;
- Hermes or Claude Code extensions.

Use repository rules for these choices and label them as repository or client conventions.

## Use tools proportionately

Prefer the tools already available in the target environment. Do not add a dependency or globally install a package when a built-in capability is sufficient.

When a helper script is justified:

- pin or document dependencies;
- keep it deterministic;
- handle malformed input;
- include a runnable verification;
- follow repository language policy.

## Keep examples trustworthy

Examples should be:

- complete enough to run;
- free of secrets and personal data;
- explicit about placeholders;
- tested when they are part of a delivered workflow;
- consistent with the surrounding instructions.

## Validate the package, not only frontmatter

A passing schema validator does not detect contradictory Markdown instructions. Review:

- `SKILL.md`;
- every linked reference;
- templates;
- scripts and dependencies;
- paths and client-specific assumptions.

Then run the portable validator and the target client's loading check.

## Common anti-patterns

- Treating a client extension as part of the base specification.
- Keeping stale product URLs as general authorities.
- Requiring a gerund name without a repository rule.
- Claiming `allowed-tools` is forbidden.
- Mandating Node.js or Python for all repositories.
- Copying an old client path into a generic skill.
- Adding verbose background instead of executable procedure.
- Updating the main file while leaving its template or references contradictory.
