# vault-ops

`vault-ops` is a skill for working with markdown note vaults such as Obsidian.

The executable instructions live in `SKILL.md` and the files in `reference/`.

## Local Override Model

The skill provides default behavior for:

- selecting a vault
- navigating a vault
- writing regular notes
- writing Maps of Content (MoCs)

Each actual vault can override those defaults through its root `AGENTS.md` and any files referenced by that `AGENTS.md`.

## Optional Personal Convention

Some users keep agent-specific preferences in `TOOLS.md` or a similar host-environment file.

One possible convention is defining a preferred default vault there for a specific agent setup.

That convention is optional and informational only. It is not part of the executable contract of this skill and is intentionally not referenced by `SKILL.md`.
