# Reviewing and patching AGENTS.md (project guidance)

When the user asks to review or fix `AGENTS.md`, treat it as an operational document that must be consistent with the actual repository layout and agent toolchain.

## Quick checklist

1) Verify directory layout matches reality
- Enumerate top-level folders (`find . -maxdepth 2 -type d`) and compare with the `Project directory layout` section.
- Watch for typos that create parallel trees (e.g. `refernces/` vs `references/`). Decide: rename directory vs document the typo. Prefer renaming to the canonical name.

2) Verify “project information” pointers
- Ensure paths point to existing files.
- If files moved (e.g. `docs/` -> `context/`), update links.

3) Verify tool usage rules are explicit and correct
- OpenViking resources (`viking://resources/**`): document that access must go via `ov` CLI (terminal) and the `openviking` skill; do not use `viking_*` tools for resources.
- Source repos under `repos/`: read-only.

4) Evidence model language
- Avoid overclaiming: `context/` is curated input, but not “hard evidence”.
- Explicitly separate hard evidence (repos, Bosch KB) vs soft (DFT KB/wiki/analysis).

5) Keep the doc easy to execute
- Use consistent directory notation (`dir/`).
- Use consistent naming of skills as actually installed (slug vs title).

## Tooling pitfall: stale reads during active edits
If the user edits `AGENTS.md` while you are reviewing it, `read_file` may be blocked/deduped. Work around with:
- `stat` to confirm mtime/size changed.
- `sed -n '1,200p AGENTS.md'` via terminal to get the current content.

Then apply patches and re-check for remaining typos with a targeted search.
