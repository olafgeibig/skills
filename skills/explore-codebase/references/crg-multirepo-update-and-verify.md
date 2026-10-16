# Code Review Graph index refresh and verification

## When to use

- After materializing a new commit-pinned repository snapshot or refreshing source checkouts.
- When verifying that graph indexes match the exact commits used for code analysis.
- When updating one project-scoped set or all globally registered repositories.

## Key points

1. Incremental updates can legitimately be fast; they re-parse only changed files and affected dependents.
2. Verify freshness with `last_updated`, and verify commit alignment with `_graph.built_at_sha` and `head_matches_build` when those fields are returned.
3. For project-scoped snapshot work, take the target set from the active repo snapshot and inventory classification; do not update unrelated globally registered repositories.
4. Keep project inventory separate from the CRG workset: deployment/IaC repos can remain in scope while being excluded from source-code graph indexing.
5. Use `list_repos_tool` to discover the global CRG registry. For a known project repo, pass its explicit `repo_root`; registry omission alone does not prove path-based stats or updates are unsupported.

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
  - Check `structuredContent._graph.built_at_sha` equals the selected manifest commit and `structuredContent._graph.head_matches_build` is `true`, when returned.
  - A detached snapshot may report `built_on_branch: HEAD`; verify the commit SHA rather than expecting a named local branch.

## Recommended workflow

1. Select the exact active repository set from the snapshot manifest. For project-scoped refreshes, include only repositories classified for source-code analysis; do not broaden the run to unrelated global CRG entries.
2. For each target, inspect its current graph stats and compare the indexed commit with the manifest commit. If they differ, run `build_or_update_graph_tool` with `full_rebuild: false` and the explicit repo root.
3. Verify the result: no build errors, `last_updated` reflects the update, and the indexed SHA matches the selected manifest commit (`head_matches_build: true` when returned).
4. For a global "all registered repos" update, use `list_repos_tool` and iterate that registry separately from project-scoped snapshot work.
5. When a repository checkout is removed, do not assume its stored graph or registry entry is also removed. Use an explicit supported CRG management operation if available; never delete CRG database files manually.

## Pitfalls

- CRG only updates repos you pass via `repo_root`; a global update needs an explicit loop.
- Do not infer that an index matches a snapshot from `last_updated` alone; compare its recorded build SHA with the manifest commit.
- Some repositories may not be globally registered. For known project paths, test the explicit `repo_root` operation before concluding that no graph is available; do not claim they are registered unless `list_repos_tool` confirms it.
- Removing a checkout, removing a registry entry, and deleting stored graph data are separate operations. Do not assume one performs the others.
