# Cross-check searches in gitignored repositories

Some projects place `repos/` under ignore rules. Search tools may handle ignored content differently, so a zero or unexpectedly small result set is not proof that a pattern is absent.

Durable rule:
- Start with `search_files` for convenience.
- If results are empty or narrower than expected, cross-check with ripgrep:

  `rg --no-ignore -n "<pattern>" repos/<repo>/`

Example (placeholders only): for `repos/<application-repo>/`, compare `search_files` with `rg --no-ignore` for `<example-pattern>`.

Use the actual repository path and query; do not infer absence from one search tool.
