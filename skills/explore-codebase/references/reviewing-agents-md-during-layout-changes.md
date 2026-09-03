# Session note: keeping AGENTS.md consistent during active edits

This session hit two durable workflow issues when reviewing/updating AGENTS.md:

1) Directory layout drift is common
- The user reorganized the repo layout mid-session (added `context/`, `compiled/`, `references/`, etc.).
- Initial conclusions based on older layout became wrong.

Recommended workflow before making claims about "where files live":
- Run a quick live listing:
  - `ls -la`
  - `find . -maxdepth 2 -type d | sort`
- Then align AGENTS.md to the observed structure.

2) `read_file` dedupe guard can block re-reading a file the user edited
- The file tool may refuse repeat reads of the same region and claim it is unchanged.

Bypass/verification workflow:
- Verify change via `stat` (mtime/size).
- Read via shell (`sed -n '1,200p AGENTS.md'`) to get the current content.
- Apply edits using `patch` (prefer targeted replace).

3) Skill-name confusion: display name vs slug
- Skills can be shown as "Explore Codebase" but addressed as `explore-codebase`.
- Prefer documenting the slug in AGENTS.md to reduce failures.

4) Wiki-skill naming mistakes happen
- If the user corrects a skill name (e.g., `vault-wiki` vs a typo), patch AGENTS.md immediately and avoid persisting incorrect names.
