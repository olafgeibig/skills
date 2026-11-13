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
version: "1.0.0"
author: Example Author
platforms:
  - macos
  - linux
```

Top-level `version`, `author`, and `platforms` are not fields defined by the portable Agent Skills specification. This library uses the Hermes-native placement as its rule: `version`, `author` and `license` are top-level in every package, and `metadata` carries `source` and the `hermes` block. Field detail: `references/hermes-frontmatter.md`.

Do not duplicate `version` or `author` at both levels.

## Location and ownership

Hermes can discover skills from profile-local storage and configured `skills.external_dirs`. Discovery does not decide ownership.

Before writing:

1. Classify the skill as owned or third-party.
2. Read the target profile's live roots with `hermes -p <profile> config get skills.external_dirs` and `hermes -p <profile> config get skills.create_dir`; substitute the selected profile explicitly rather than relying on the shell's active profile.
3. Check the proposed directory's existence and resolve its repository with `git -C <directory> rev-parse --show-toplevel`. Keep existence, Git ownership, and Hermes discovery as separate checks: none implies the other two.
4. Search the confirmed roots for overlap and higher-precedence same-name shadows. If a file search returns unrelated directories instead of matching files, narrow it to a confirmed root or inspect a known candidate directly; do not repeat the unchanged query as evidence of absence.
5. If configured roots and an older skill's path disagree, use verified live configuration to present the destination choices. Do not silently create a missing shelf, initialize a repository, or alter discovery configuration merely to satisfy the older path.

For a skill shared across installations, verify discovery separately on each installation when accessible. Creation in one machine's external repository proves neither synchronization nor discovery on the other machine; report an unchecked consumer as unverified.

For the full ownership and routing rules, load `skill-governance`.

## Creating and editing

- Use `skill_manage` for an existing owned skill resolved from the profile or an external directory.
- For `skill_manage(action='patch')`, name the pair `old_string`/`new_string` and send no other fields on that op: the matcher reads those names, and an op carrying `content` or `old_text` is refused as a missing `old_string` however exact the snippet is.
- Do not use `skill_manage(create)` unless its configured creation root is the intended canonical repository. It is also never the way to start a working copy of an existing skill: it refuses a name that already resolves externally — copy the complete package with filesystem tools instead.
- When several external repositories exist and `skills.create_dir` cannot select among them, build the package profile-local and publish it into the chosen repository (`skill-library-maintenance` → `publish-skill.md`); a direct create is only for an unlocked project repository.
- Never edit a third-party skill directly.

After creation or movement, load the skill and inspect `_source_path`.

## Hermes validation

After portable validation:

1. Load the skill with `skill_view`.
2. Confirm `description`, `metadata`, tags, and related skills.
3. Confirm `_source_path` points to the expected source for the phase — the working copy while it is open, the canonical repository after close.
4. Confirm linked files appear and load successfully.
5. Check required commands, variables, and readiness.
6. Search configured roots for duplicate skill names, and treat a declared working copy of an owned skill as the expected exception rather than a defect.

The Hermes authoring linter expects top-level `version` and `author` and reports nested ones as missing; `skills-ref` therefore reports the accepted portability finding described in `references/hermes-frontmatter.md`.

## Prompt budget

Hermes indexes the first 57 characters of the description and shows an ellipsis beyond them, which is stricter than the Agent Skills limit. Author every description so those 57 characters carry the trigger on their own.

## Discovery gating (on-demand skills)

Every skill's name and description enter the system prompt's skill index on every model call, and a loaded body costs its full length. A skill that is expensive and only occasionally wanted should not be advertised there — and Hermes has no `manual-only` flag. Discovery gating comes from a dependency field instead:

```yaml
metadata:
  hermes:
    requires_tools:
      - manual-invocation      # a gate, not a dependency
```

`requires_tools` names tools the skill needs; an entry matching no available tool hides the skill from the prompt index entirely, while a `/skill-name` slash command and an explicit `skill_view(name)` still reach it. What it does not hide: `skills_list` still returns the skill to an agent that actively calls it. For a skill that must appear nowhere, the hard variant is `skills.disabled: [name]` in `config.yaml` plus a plugin in `$HERMES_HOME/plugins/<name>/` registering its own command.

Verify the gate by the absence it produces: confirm a comparable ungated skill is still listed in the prompt index while the gated one is gone, then confirm the slash command and `skill_view` still resolve it. A gate that hides nothing is indistinguishable from no gate until both checks are run.

## Tool and platform declarations

Use Hermes-specific tool, environment, platform, or blueprint metadata only when the feature is required. Verify current Hermes documentation before adding it; do not copy stale examples from an older skill.
