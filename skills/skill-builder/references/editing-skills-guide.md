# Editing Existing Skills

## Start with the actual package

1. Load the current `SKILL.md` from its resolved source.
2. Load each supporting file that may change.
3. Confirm ownership and canonical repository.
4. Read the repository's local rules.
5. State the concrete defect or improvement goal.

Do not edit an installed shadow when the canonical skill lives elsewhere.

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

Follow `skill-governance` and the owning repository:

- patch for corrections and small clarifications;
- minor for substantive additive guidance or new workflows;
- major for breaking scope or behavior changes.

Bump the version when the skill package changes, including behavior-bearing references and templates.

## Validation

After editing:

1. Run the package's Agent Skills validator.
2. Confirm all links resolve.
3. Run scripts or examples affected by the change.
4. Load the skill in the target client.
5. Confirm canonical source resolution and absence of shadows.
6. Inspect the repository diff and status.
7. Commit or publish only when authorized.

## Save and hand off changes across installations

Use this sequence when several installations develop the same skill repository and another checkout may contain unpublished commits:

1. Inspect `git status --short --branch`, `git diff --name-status`, `git diff --cached --name-status`, and `git remote -v`. Resolve unrelated staged changes before committing; do not sweep them into a skill commit.
2. Record the starting commit with `git rev-parse HEAD`. Create the requested branch with `git switch -c <branch>` before committing; preserve main and the existing worktree changes. Do not reset, rebase, or force-push another installation's work.
3. Validate each changed skill package. Stage only that skill's explicit paths with `git add -- <paths>`, including additions and deletions; run `git diff --cached --check` and inspect `git diff --cached --name-status` before each commit. Keep one skill's SKILL.md, version bump, and supporting files in the same commit.
4. Verify the resulting commit range from the recorded starting commit with `git log --oneline <base>..HEAD`, inspect `git show --stat <commit>` for each commit, and check `git status --short --branch`. Report unrelated remaining changes instead of claiming a clean worktree.
5. Push only when publication is authorized: `git push -u origin <branch>`. Verify the exact remote branch with `git ls-remote origin refs/heads/<branch>` and compare its SHA to `git rev-parse HEAD`. A request to create a branch and commit, or confirmation that the remote is correct, does not by itself authorize pushing or opening a PR.
6. Hand off the branch, commit IDs by skill, validation results, worktree state, and publication state. Distinguish tracked canonical changes from profile-local adaptations outside the repository. Let the receiving installation fetch and integrate the branch against its own unpublished work; do not claim that work has been synchronized or merged without verification there.

## Stop conditions

Do not edit when:

- the skill is third-party and direct changes are prohibited;
- ownership or target repository is unresolved;
- the proposed change is a project fact rather than reusable procedure;
- the evidence for a claimed tooling change is missing;
- the user requested review before modification.
