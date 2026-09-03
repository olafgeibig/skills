# REPOS.jsonl format gotcha (DFT CSL workspace)

In this workspace, `REPOS.jsonl` is **not strict JSONL** (one JSON object per line).

Observed shape:
- It is a concatenation of pretty-printed JSON objects.
- Each object spans multiple lines.
- There is no enclosing `[` `]` array.

Implication:
- This fails with naive JSONL parsing:
  - `for line in open('REPOS.jsonl'): json.loads(line)`

Safe approaches:

1) Treat it as navigation text
- Use `read_file` to inspect.
- Or search for repo names/keys:
  - `rg '"repo_dir"' REPOS.jsonl`

2) Parse as a stream of JSON objects (programmatic)
- Use a streaming decoder that repeatedly calls `raw_decode` on the remaining buffer.

Why this matters
- Several skills assume strict JSONL; without this note, agents can waste time or produce incorrect automation.
