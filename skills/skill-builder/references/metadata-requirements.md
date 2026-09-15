# Frontmatter and Metadata Requirements

## Portable Agent Skills fields

The Agent Skills specification defines these top-level fields:

| Field | Required | Purpose |
|---|---:|---|
| `name` | yes | Skill identifier; must match the parent directory |
| `description` | yes | What the skill does and when to use it |
| `license` | no | License name or bundled license reference |
| `compatibility` | no | Product, environment, package, or network requirements |
| `metadata` | no | Additional metadata |
| `allowed-tools` | no | Experimental pre-approved tool declaration |

Author and version appear in the official example under `metadata`:

```yaml
metadata:
  author: example-org
  version: "1.0.0"
  source: https://example.com/example-org/example-skills
```

Keep version strings quoted. Do not duplicate a value at both the top level and under `metadata`.

## Client extensions

A client may accept additional fields or richer metadata values. Those fields are extensions, not portable guarantees.

For Hermes extensions, use `references/hermes-skills.md`. For Claude Code-specific behavior, use `references/claude-code-skills.md`.

## Name

A valid name:

- contains 1–64 lowercase letters, digits, or hyphens;
- does not start or end with a hyphen;
- does not contain consecutive hyphens;
- matches the parent directory.

The specification does not require gerund names. Follow the owning repository's convention. This repository prefers concise noun phrases such as `vault-ops`, `skill-governance`, and `skill-builder`.

## Description

A valid description:

- contains 1–1024 characters;
- explains what the skill does and when it applies;
- contains terms that distinguish it from adjacent skills;
- fits any stricter client prompt budget.

Preferred form:

```yaml
description: "Use when creating or maintaining Agent Skills."
```

Avoid keyword dumps, marketing language, and lists of every possible edge case.

## Compatibility

Use `compatibility` only for actual runtime requirements:

```yaml
compatibility: Requires network access and git 2.40+
```

Do not list optional tools as mandatory.

## Allowed tools

`allowed-tools` is experimental and client support varies. Add it only when the target client supports it and pre-approval is intentional. Otherwise omit it.

## Portable example

```yaml
---
name: document-review
description: "Use when reviewing documents for structural and factual issues."
license: MIT
metadata:
  author: Example Author
  version: "1.0.0"
  source: https://example.com/example-org/example-skills
---
```

## Validation checklist

- [ ] Directory name equals `name`.
- [ ] Name satisfies syntax and length constraints.
- [ ] Description explains both capability and trigger.
- [ ] Description fits specification and client budgets.
- [ ] Portable values are placed under `metadata`.
- [ ] Client extensions are documented as extensions.
- [ ] `author` and `version` have one authoritative location.
- [ ] `allowed-tools` is intentional if present.
- [ ] YAML uses spaces and parses correctly.
