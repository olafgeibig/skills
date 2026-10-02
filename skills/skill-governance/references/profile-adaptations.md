# Profile-Local Adaptations

Use this reference when a rule cannot be written to its source skill because the source is third-party, or when behavior is genuinely specific to one Hermes profile or environment.

## Canonical location

Store an adaptation under the active profile:

```text
$HERMES_HOME/skills/adaptations/<source-skill>-adaptation/SKILL.md
```

The default skill name is `<source-skill>-adaptation`. Use a bundle adaptation only when several source skills form one inseparable operating unit. Do not create generic catch-all improvement bundles.

Profile-local adaptations are not stored in an owned canonical skill repository or inside the third-party source tree. Do not create a nested Git repository for an individual adaptation.

### Standalone profile-local skills

A profile-local skill that is not a delta for a source skill must declare itself: `metadata.scope: standalone` plus `metadata.hermes.related_skills` naming the skills it borders. Without that declaration it is indistinguishable from an unnamed adaptation — which is how a local delta ends up invisible to its owning skill.

Find both cases with the audit:

```bash
python3 skills/skill-library-maintenance/scripts/audit-skill-declarations.py
```

### Rule reach

These rules bind the artifact, not the label. A profile-local skill that *functions* as a local delta, overlay, or improvement bundle is subject to them whether or not it declares itself an adaptation. Semantic overlap with a source skill is what makes a skill an adaptation; the name only makes it reviewable.

## Scope

An adaptation contains only the local delta:

- why the behavior is specific to this profile or environment;
- which source skill it adapts;
- which behavior it adds, narrows, or overrides;
- prerequisites and verification;
- optionally, the upstream version or revision last reviewed.

Do not copy the source skill. Link it through `related_skills` and write only what differs.

No staging area. Never add a dated batch or diary file (`new-pitfalls-<date>-batch.md` in the skill's own directory) to hold findings for later sorting — classify each finding in the session it arises and route it. Chronology of discovery is not knowledge; the rule must stand without the story.

Simple standing preferences or paths belong in a plain profile-local skill (`$HERMES_HOME/skills/own/<name>/`, `metadata.scope: standalone`, as a real directory — a symlinked skill directory is not discovered), not in an adaptation. Use an adaptation only for a delta against a source skill; use either only for reusable multi-step behavior that benefits from skill activation. A profile `AGENTS.md` is not a destination: Hermes loads `AGENTS.md` from the working-directory tree only and never reads `$HERMES_HOME/AGENTS.md`.

## Frontmatter

```yaml
---
name: example-skill-adaptation
description: "Use with example-skill in this profile."
metadata:
  author: Example Author
  version: "0.1.0"
  adapted_from: example-skill
  scope: profile-local
  hermes:
    category: adaptations
    related_skills:
      - example-skill
---
```

Use `skill-builder/templates/adaptation-skill-template.md` when creating the package.

## Profile independence

Do not synchronize adaptations automatically between profiles. Different profiles may legitimately use different tools, safety boundaries, output formats, and workflows.

The same rule appearing independently in multiple profiles is a promotion signal. Reassess whether it is actually generic and belongs in an owned canonical skill or should be proposed upstream.

## Override-only discipline

A profile-local skill that covers one area or topic of an owned skill stays override-only: it keeps topic- or environment-specific facts, overrides, and pitfalls, and references the owning skill for general conventions, mechanics, and pitfalls. Decision rule: if removing a fact would make the skill unusable for its purpose, it stays; if removing it only shifts a lookup to the owning skill, it goes.

When an owning skill that was unavailable for a stretch becomes accessible again, audit any profile-local skill that may have absorbed duplicated content during the gap:

1. Tag every section as `STAYS` (specific to this skill), `DELETES` (already covered by the owning skill), or `PENDING` (unclear).
2. Propose the slim-down as a diff and wait for approval — the audit is interpretive.
3. After approval: apply, state the override-only contract in the skill preamble, bump the version (minor for a discipline change, patch for content), and add a changelog entry.

When the local skill happens to be the more detailed one, do not merge the two — pull the local skill back to override-only and let the owning skill be authoritative.

## Promotion

Before promotion:

1. Confirm that the rule is no longer profile-specific — and that it is not merely project-born: a method developed for one project stays in that project skill until a second, independent consumer appears.
2. Remove names, local paths, dates, incidents, and environment-only assumptions.
3. Search the target skill for the rule; a restatement of an existing rule is not a promotion.
4. Propose the delta — target file, verbatim rule text, why it is generic, the dedupe search, and what gets retired — and wait for approval. See the review gate in `skill-governance`.
5. Write, validate, and bump the canonical skill's version.
6. Remove the duplicated rule from every affected adaptation after verification.
7. A generic rule must not stay in the adaptation merely because that is where it was discovered. Promotion is part of writing the finding down, not a later cleanup.

## Verification

- Path is below the active `$HERMES_HOME/skills/adaptations/`.
- `metadata.scope: standalone` is present when the skill is not a delta for a source skill (and `adapted_from` is absent).
- No generic rule lives only here — generic rules were promoted to the source skill.
- No project-born method was promoted on its first occurrence — one consumer is not a promotion signal.
- Name ends in `-adaptation` and identifies the source skill.
- `metadata.adapted_from` and `metadata.scope: profile-local` are present.
- `metadata.hermes.category` is `adaptations`.
- The source skill appears in `related_skills`.
- The body contains only local deltas.
- No same-name shadow exists in another skill root.
- No dated batch or diary file was created here, and any promoted rule was removed from this adaptation after the canonical write.
