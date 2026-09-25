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

Simple standing preferences or paths belong in profile `AGENTS.md`, not an adaptation skill. Use an adaptation only for reusable multi-step behavior that benefits from skill activation.

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

## Promotion

Before promotion:

1. Confirm that the rule is no longer profile-specific.
2. Remove names, local paths, dates, incidents, and environment-only assumptions.
3. Check whether the target skill already contains the rule.
4. Obtain required maintainer approval.
5. Update and validate the canonical skill.
6. Remove the duplicated rule from every affected adaptation after verification.
7. A generic rule must not stay in the adaptation merely because that is where it was discovered. Promotion is part of writing the finding down, not a later cleanup.

## Verification

- Path is below the active `$HERMES_HOME/skills/adaptations/`.
- `metadata.scope: standalone` is present when the skill is not a delta for a source skill (and `adapted_from` is absent).
- No generic rule lives only here — generic rules were promoted to the source skill.
- Name ends in `-adaptation` and identifies the source skill.
- `metadata.adapted_from` and `metadata.scope: profile-local` are present.
- `metadata.hermes.category` is `adaptations`.
- The source skill appears in `related_skills`.
- The body contains only local deltas.
- No same-name shadow exists in another skill root.
