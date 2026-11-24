# `skill_manage` with external skill directories

Use this reference when skills are distributed across multiple `skills.external_dirs` repositories, or
when a write targets a skill that resolves outside the profile-local tree.

## Verified behavior

Hermes separates skill discovery from skill creation.

- `skills.external_dirs` adds read/discovery roots. Existing skills found there are mutable when filesystem permissions allow it.
- `skill_manage` actions `patch`, full-rewrite `patch`, `write_file`, `remove_file`, and foreground `delete` resolve an existing skill across the profile-local directory and all external directories, then operate on the resolved directory.
- `skill_manage(action="create")` does not choose an external root from the skill's ownership or frontmatter category. It writes beneath one base directory: the profile-local skills directory by default, or the single configured `skills.create_dir`.
- The `category` argument only adds a subdirectory below that one creation root. It does not select a repository.
- A profile-local skill with the same name takes precedence over an external skill and can shadow it.
- That precedence is legitimate only briefly during publication/close of a brand-new skill (`references/develop-skill.md`), never for editing an existing canonical skill. While a local copy exists, the bare name resolves to it, so publication must address the canonical repository explicitly with filesystem tools.
- Autonomous Curator review treats external-directory skills as read-only. A foreground, user-directed `skill_manage` operation may update them.
- Curator lifecycle verbs split by target location: `curator lock` works and persists on an external root just as on a profile-local skill, while `curator adopt` and the maintenance lifecycle (stale/archive, consolidation, Curator snapshots) are profile-local only. Locks guard skill writes per profile; they do not pin a Git revision or stop filesystem-level changes.

## Technical reach is not permission

The API can technically patch a file in an external repository whenever filesystem permissions allow it.
For an **existing canonical skill**, the user unlocks it (`hermes curator unlock <name>`) and edits happen directly in the canonical repository (on a Git branch for larger or multi-skill changes). For a **brand-new canonical skill**, build it profile-local first (or on a branch in the canonical repo) and publish after review. A third-party skill is never written. Read the class and the lock state before choosing an operation, and report the proposed change when neither permits a write.

## Consequence for multiple owned repositories

A single `skills.create_dir` works when all newly created skills belong under one canonical root. It cannot natively route each create operation among separate personal, project, and third-party repositories.

Do not temporarily switch the global `skills.create_dir` for individual writes in a shared or long-lived runtime. Another concurrent task can observe the temporary value, and a failed workflow can leave creation pointed at the wrong repository.

## Preferred decision table

| Operation | Preferred mechanism | Reason |
| --- | --- | --- |
| Read an existing skill | `skill_view` | Resolves local and external roots and records read-before-write context. |
| Patch an existing owned external skill (unlocked) | `skill_manage(action="patch")` | Modifies the resolved canonical source in place and retains native hooks. Use a Git branch in the canonical repo for larger or multi-skill changes. |
| Add a support file in an unlocked owned external skill | `skill_manage(action="write_file")` | Constrains the path and retains native hooks. |
| Edit a locked owned external skill | Report the proposed change and ask the user to unlock it | Locked skills cannot be patched; never create a local shadow copy to bypass the lock. |
| Create a skill when `skills.create_dir` points at a **project** repository | `skill_manage(action="create")` | Native creation, validation, ledger, and cache handling. |
| Create a skill inside an unlocked owned repository | Filesystem `write_file` in that repository (e.g. on a branch) | The target path is explicit; `skill_manage` has no per-call root selector. |
| Create a brand-new skill destined for the released canonical library | Build it profile-local (`baseline: none`), review it, publish the reviewed bytes | Avoids polluting the canonical repo before the procedure stabilizes. |
| Publish a reviewed local new skill into the canonical repository | Filesystem writes in that repository, then validate and commit explicit paths | The bare name resolves to the local copy; `skill_manage` would edit the local copy. |
| Modify a third-party skill | Do not modify it | Never written; report the learning per `skill-governance`. |

## Native `skill_manage` advantages

- Resolves an existing skill across configured roots.
- Provides targeted replacement and atomic multi-operation batches.
- Enforces skill structure and path constraints.
- Runs configured security scanning.
- Records mutation ledger and usage data.
- Clears the skill-system-prompt cache after successful writes.
- Supports approval staging when `skills.write_approval` is enabled.

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
4. Running the package's gates (Hermes linter and library audit).
5. Loading the skill with `skill_view` and checking `_source_path`.
6. Scanning all configured roots for duplicate skill names.
7. Starting a new session when inventory or prompt-cache refresh is required.

## Design gap

A future Hermes enhancement could add an explicit creation-root selector constrained to configured writable roots. Until then, a single `skills.create_dir` is intentional but insufficient for per-skill routing across multiple owned repositories.
