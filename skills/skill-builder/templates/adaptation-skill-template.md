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

# Example Skill Adaptation

## When to Use

Use only with the named source skill in this profile when the local environment requires the behavior below.

## Source Skill

- Skill: `example-skill`
- Upstream version or revision reviewed: unknown

## Local Delta

Describe only what this profile adds, narrows, or overrides. Do not copy the source skill.

## Prerequisites

List profile- or environment-specific requirements.

## Procedure

1. Apply the local adaptation.
2. Continue with the source skill's normal workflow.

## Verification

State the observable checks proving that the adaptation worked.

## Promotion Check

If the same rule applies to multiple profiles, reassess it for promotion to an owned canonical skill or an upstream contribution. Remove the local duplicate after successful promotion.
