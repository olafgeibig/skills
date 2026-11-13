# Editing Existing Skills

## Start with the actual package

1. Load the current `SKILL.md` from its resolved source.
2. Load each supporting file that may change.
3. Confirm ownership and canonical repository.
4. Read the repository's local rules.
5. State the concrete defect or improvement goal.

Do not edit an installed shadow when the canonical skill lives elsewhere. A released owned skill is developed in an explicitly opened working copy instead — complete package, recorded baseline, published or abandoned before it leaves discovery (`skill-library-maintenance` → `develop-skill.md`).

## Classify the change

Common change classes:

- **Trigger correction** — description is too broad, too narrow, or ambiguous.
- **Procedure correction** — instructions are wrong, incomplete, or unverifiable.
- **Structure improvement** — main file is too large or supporting files are poorly organized.
- **Client separation** — portable and client-specific rules are mixed.
- **Metadata correction** — fields use the wrong convention or conflict.
- **Tooling update** — commands, APIs, or dependencies changed.

Fix the class of defect, not only one visible sentence.

## Make a coherent edit

- Keep the change bounded to the stated goal.
- Update references and templates that encode the same rule.
- Remove obsolete instructions instead of adding exceptions around them.
- Preserve valid project or repository conventions.
- Do not introduce unrelated refactors.

## Description changes

Before changing a description:

1. List representative requests that should activate the skill.
2. Identify adjacent skills that should not activate.
3. Write one concise statement covering capability and trigger.
4. Check the Agent Skills limit and the target client's prompt budget.

Do not require a fixed phrase or a minimum keyword count unless the owning repository does.

## Structural changes

Move content out of `SKILL.md` when it is:

- detailed background;
- a large example library;
- client-specific behavior;
- a long command catalog;
- a reusable template.

Keep the core workflow and verification in `SKILL.md`. Use clear links to every supporting file.

## Client-specific changes

If behavior differs by client:

- keep the portable base in `SKILL.md`;
- put Hermes behavior in `references/hermes-skills.md`;
- put Claude Code behavior in `references/claude-code-skills.md`;
- load the relevant reference only when that client is the target.

Do not allow one client's path, frontmatter, or agent model to become a universal rule.

## Versioning

Follow the version rules in `SKILL.md` step 5:

- patch for corrections and small clarifications;
- minor for substantive additive guidance or new workflows;
- major for breaking scope or behavior changes.

Bump the version when the skill package changes, including behavior-bearing references and templates.

## Validation

After editing:

1. Run the Hermes authoring linter and, for a multi-skill repository, the library audit (`skill-library-maintenance` → `audit-library.md`).
2. Confirm all links resolve.
3. Run scripts or examples affected by the change.
4. Load the skill in the target client.
5. Confirm source resolution for the phase — the working copy while it is open, the canonical package after close — and the absence of any unintended shadow.
6. Inspect the repository diff and status.
7. Commit or publish only when authorized.

## Authoring ends at the maintenance workflow

This guide covers the authoring side of a change: reading the package, classifying the defect, making
a coherent edit and validating it. It is not a second publication runbook.

When the edited skill is a released owned skill, the change is a development phase; when it is a new
canonical skill, review comes before its first publication. Either way the procedure is in
`skill-library-maintenance`: `develop-skill.md` for the working copy and baseline,
`review-skill.md` for the complete-package review, `publish-skill.md` for the
authorized transfer and commit, `close-development.md` for removal of the copy and the
final lock, and `update-library.md` for a consuming checkout.

When the user has explicitly chosen to work on the local `main`, do not force a feature branch:
preserve unrelated dirty work byte-for-byte, stage explicit paths, and report the local commits as
unpublished. Commit, push and PR creation are separate authorization scopes; there is no autonomous
pull, push or transport-branch model.

## Stop conditions

Do not edit when:

- the skill is third-party and direct changes are prohibited;
- ownership or target repository is unresolved;
- the proposed change is a project fact rather than reusable procedure;
- the evidence for a claimed tooling change is missing;
- the user requested review before modification.
