---
name: {{BUNDLE_NAME}}-improvements
description: "Container for agent-discovered optimizations to the {{BUNDLE_NAME}} bundle — {{SKILL_NAMES}}"
metadata:
  version: "0.1.0"
  source: https://github.com/olafgeibig/skills
  hermes:
    tags: [template, improvement, bundle]
---

# {{BUNDLE_NAME}} Improvements

This skill collects all improvements discovered while working with
{{SKILL_LIST}}. Core skills remain untouched.

## Edit Rules

1. **Always write to this skill, never to the core skills.**
2. **Edit existing files directly** when improving known patterns.
3. **Create a new file** only for genuinely new, standalone topics.
4. **Abstract:** Remove or generalize concrete session details
   (dates, paths, task names, personal names).
5. **Document triggers:** Every entry clearly states when it's relevant.
6. **No duplicates:** Before creating, check if the topic already exists.
7. **Profile-specific entries** go into `profile-<name>.md`.

## Changelog

Every change must be logged in `CHANGELOG.md`:
- New entries: "added pitfalls.md: XYZ workflow"
- Edits: "updated pitfalls.md: clarified XYZ rule"
- New files: "created profile-<name>.md"

One line per change. Keep it scannable.

## Commit Rules

After every change:

```bash
git add -A && git commit -m "update: <what changed>"
```

No exceptions. This is how the user reviews your work.

## When to Load

- **Always** when the `{{BUNDLE_NAME}}` bundle is loaded, this skill is in context.
- **Without bundle:** Load via `skill_view("{{BUNDLE_NAME}}-improvements")`.
- **Explicitly:** When the user says "save that" or "remember this for later."

## References

| File | Description | Trigger |
|------|-------------|---------|
| `references/pitfalls.md` | Recurring errors and fixes | Always at session start |
| `references/workflows.md` | New or optimized workflows | When a task matches a known pattern |
