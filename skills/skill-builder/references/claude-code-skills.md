# Claude Code Skill Special Cases

Use this reference only when Claude Code is the explicit target or when converting a Claude Code-specific agent definition. Do not apply these paths or concepts to generic Agent Skills or Hermes skills.

## Portable authority

Use the current Agent Skills documentation as the format authority:

- https://agentskills.io/specification
- https://agentskills.io/skill-creation/best-practices
- https://agentskills.io/skill-creation/optimizing-descriptions

Client-specific behavior may change independently. Verify current Claude Code behavior at execution time rather than relying on historical documentation links bundled with this skill.

## Client-specific locations

Claude Code commonly distinguishes user-level and project-level skill locations. Confirm the current client documentation before writing because location and precedence are client behavior, not Agent Skills specification requirements.

Never reuse a Claude-specific path as the default for Hermes or another client.

## Converting a Claude Code agent definition

A Claude Code agent definition may include client fields such as model selection or tool restrictions. To convert reusable instructions into an Agent Skill:

1. Identify the reusable capability and activation conditions.
2. Preserve domain knowledge, procedures, examples, and verification.
3. Remove agent-only orchestration fields that the target skill client does not support.
4. Rewrite the description to state what the skill does and when it should activate.
5. Choose a specification-valid name using the target repository's convention; gerund form is optional.
6. Move detailed material into focused references.
7. Add client-specific fields only after verifying current target-client support.
8. Validate against the Agent Skills specification and then in the target client.

## Do not assume

Do not assume that:

- every skill inherits all tools;
- `allowed-tools` is forbidden;
- agent `model` or `tools` fields map directly to skill frontmatter;
- Claude Code paths apply to Hermes;
- a noun agent name must become a gerund skill name;
- old Claude documentation URLs remain authoritative.

## Conversion checklist

- [ ] Source agent instructions were read completely.
- [ ] Reusable capability is separated from agent orchestration.
- [ ] Name follows Agent Skills syntax and target repository style.
- [ ] Description covers capability and trigger.
- [ ] Client-only fields were removed or explicitly mapped.
- [ ] Supporting files use portable relative paths.
- [ ] Portable validation passes.
- [ ] Target-client loading and invocation were tested.
