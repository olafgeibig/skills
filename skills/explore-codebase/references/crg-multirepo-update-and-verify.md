# CRG multi-repo update + verification (DFT workspace)

## When to use

- After running `git pull` across many repositories under `./repos/`.
- When a user doubts CRG updated because it was "too fast".
- When you need to ensure CRG indices are aligned with the current working tree.

## Key points

1) CRG incremental updates can be legitimately very fast.
- If only a few files changed (often `CHANGELOG.md`, `gradle.properties`, lockfiles), CRG will re-parse only those and finish quickly.

2) Verify with `last_updated`.
- Fast != wrong. The correct verification is `list_graph_stats_tool` and compare `last_updated` to the last `git pull` timestamp or to "now" after an update.

3) Update all CRG-registered repos via CRG registry.
- `list_repos_tool` returns the exact set of repos CRG tracks.
- Iterate those and call `build_or_update_graph_tool` per repo.

## Commands

Discover CRG tool schema:

- `mcp-cli info code-review-graph`

List CRG-registered repos:

- `mcp-cli call code-review-graph list_repos_tool '{}'`

Update one repo (incremental):

- `mcp-cli call code-review-graph build_or_update_graph_tool '{"repo_root":"repos/<repo>","full_rebuild":false}'`

Verify one repo:

- `mcp-cli call code-review-graph list_graph_stats_tool '{"repo_root":"repos/<repo>"}'`
  - Check `structuredContent.last_updated`.

## Recommended workflow

1) For the repo(s) in question:
   - Read `git reflog -n 2` to confirm a pull/fast-forward happened.

2) Check CRG `last_updated`.
   - If older than the pull, run `build_or_update_graph_tool`.

3) For "all repos":
   - Use `list_repos_tool` and update each repo.
   - Then spot-check a few repos' `last_updated` to ensure updates landed.

## Pitfalls

- CRG only updates repos you pass via `repo_root`. A global update needs a loop.
- Some repos may not be registered in CRG; those require filesystem search or explicit registration, depending on your CRG setup.
