# Session note — CRG validation on a Java repo (DFT)

Goal: Verify Code Review Graph (CRG) works for Java repos in this workspace.

Repo used:
- /Users/GEO5BE4/work/Bosch/projects/dft/dft-csl/repos/dft-fuel-provider-service

Commands (via mcp-cli):

1) Tool discovery
- mcp-cli info code-review-graph

2) Build/update graph
- mcp-cli call code-review-graph build_or_update_graph_tool '{"repo_root":"/Users/GEO5BE4/work/Bosch/projects/dft/dft-csl/repos/dft-fuel-provider-service","full_rebuild":false}'

Observed outcome:
- status: ok
- fts_indexed: 865

3) Verify graph stats
- mcp-cli call code-review-graph list_graph_stats_tool '{"repo_root":"/Users/GEO5BE4/work/Bosch/projects/dft/dft-csl/repos/dft-fuel-provider-service"}'

Observed outcome (high-signal fields):
- Files: 173
- Total nodes: 865
- Total edges: 11752
- Languages: bash, java
- Embeddings: 0 nodes embedded (so semantic search may be empty)

Implication:
- CRG parsing and structural graph traversal works for Java code here.
- Use ripgrep alongside CRG when embeddings are not built.
