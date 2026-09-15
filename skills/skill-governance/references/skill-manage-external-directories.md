# `skill_manage` with external skill directories

Use this reference when skills are distributed across multiple `skills.external_dirs` repositories.

## Verified behavior

Hermes separates skill discovery from skill creation.

- `skills.external_dirs` adds read/discovery roots. Existing skills found there are mutable when filesystem permissions allow it.
- `skill_manage` actions `patch`, full-rewrite `patch`, `write_file`, `remove_file`, and foreground `delete` resolve an existing skill across the profile-local directory and all external directories, then operate on the resolved directory.
- `skill_manage(action="create")` does not choose an external root from the skill's ownership or frontmatter category. It writes beneath one base directory: the profile-local skills directory by default, or the single configured `skills.create_dir`.
- The `category` argument only adds a subdirectory below that one creation root. It does not select a repository.
- A profile-local skill with the same name takes precedence over an external skill and can shadow it.
- Autonomous Curator review treats external-directory skills as read-only. A foreground, user-directed `skill_manage` operation may update them.

## Consequence for multiple owned repositories

A single `skills.create_dir` works when all newly created skills belong under one canonical root. It cannot natively route each create operation among separate Personal, Bosch, Project, and third-party repositories.

Do not temporarily switch the global `skills.create_dir` for individual writes in a shared or long-lived runtime. Another concurrent task can observe the temporary value, and a failed workflow can leave creation pointed at the wrong repository.

## Preferred decision table

| Operation | Preferred mechanism | Reason |
| --- | --- | --- |
| Read an existing skill | `skill_view` | Resolves local and external roots and records read-before-write context. |
| Patch an existing owned external skill | `skill_manage(action="patch")` | Modifies the resolved source in place and retains native hooks. |
| Add a support file to an existing owned external skill | `skill_manage(action="write_file")` | Constrains the path and retains native hooks. |
| Create a skill when `skills.create_dir` is its canonical root | `skill_manage(action="create")` | Native creation, validation, ledger, and cache handling. |
| Create a skill for another canonical repository | Filesystem `write_file` in that repository | The target path is explicit; `skill_manage` has no per-call root selector. |
| Modify a third-party skill | Do not modify it | Route the learning according to governance. |

## Native `skill_manage` advantages

- Resolves an existing skill across configured roots.
- Provides targeted replacement and atomic multi-operation batches.
- Enforces skill structure and path constraints.
- Runs configured security scanning.
- Records mutation ledger and usage data.
- Clears the skill-system-prompt cache after successful writes.
- Supports approval staging and optional skill synchronization.

## Filesystem-tool advantages

- Makes the exact repository and path explicit.
- Supports several independently owned repositories without mutating global configuration.
- Fits normal Git review, diff, commit, and push workflows.
- Avoids accidentally creating a profile-local shadow.

## Filesystem-tool costs and compensating checks

Direct filesystem writes bypass `skill_manage` ledger, security scan, usage telemetry, prompt-cache invalidation, and batch rollback. Compensate by:

1. Reading repository and profile governance before writing.
2. Creating only inside the selected canonical repository.
3. Using targeted `patch` for existing files and `write_file` for new files.
4. Running the repository's skill validator.
5. Loading the skill with `skill_view` and checking `_source_path`.
6. Scanning all configured roots for duplicate skill names.
7. Starting a new session when inventory or prompt-cache refresh is required.

## Design gap

A future Hermes enhancement could add an explicit creation-root selector constrained to configured writable roots. Until then, a single `skills.create_dir` is intentional but insufficient for per-skill routing across multiple owned repositories.