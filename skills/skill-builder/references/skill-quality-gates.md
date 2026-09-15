# Skill Quality Gates

Use these checks for one skill package. Repository-wide maintenance should reuse these thresholds rather than define competing ones.

## Main-file size

Line count is a diagnostic, not a substitute for judgment:

| `SKILL.md` size | Default action |
|---:|---|
| Up to 200 lines | Preferred range |
| 201–250 lines | Accept when cohesive |
| 251–350 lines | Review for thematic extraction |
| 351–500 lines | Require an explicit reason to remain inline |
| Over 500 lines | Split unless a documented exception applies |

Also consider density. A 250-line file with long paragraphs and large tables may cost more context than a sparse 350-line procedure.

Keep information in the main file when it is required on every activation: trigger, scope, decisions, critical invariants, core procedure, pitfalls, and verification.

Move information to references when it is conditional, client-specific, a long example set, a command catalog, detailed troubleshooting, or a specialized sub-workflow.

## Description quality

The Agent Skills specification permits up to 1024 characters. Hermes may expose only a much shorter prefix in its prompt index.

For this repository:

- keep the description at or below 57 characters where practical;
- make the first 57 characters a complete trigger statement;
- move enumerated use cases into `## When to Use`;
- avoid marketing language and keyword dumps.

A longer description is acceptable only when the target client demonstrably preserves and needs it.

## Reference quality

Do not optimize total package size blindly; references are loaded on demand. Instead verify:

- one coherent topic per reference;
- intention-revealing lowercase filename;
- no reference chain deeper than necessary;
- no duplicated normative rule;
- no stale client path or documentation URL;
- large references split when they contain independent workflows.

## Package consistency

A schema validator does not read instructions semantically. Review the whole package for:

- contradictions between `SKILL.md`, references, templates, and scripts;
- dead or renamed links;
- client-specific behavior presented as portable;
- outdated commands and product names;
- templates that omit required repository metadata;
- examples that violate current safety or tool-use rules.

## Validation sequence

1. Measure main-file lines and description length.
2. Run the Agent Skills validator.
3. Resolve every linked support file.
4. Scan the package for stale names, URLs, paths, and contradictory phrases.
5. Run affected scripts and examples.
6. Load the skill in the target client.
7. Verify canonical source path and duplicate-name absence.
8. Inspect the repository diff and status.

The validator passing is necessary but not sufficient.
