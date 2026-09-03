# repos/ search cross-check: search_files vs rg --no-ignore

Context: In this DFT CSL workspace, `./repos/` is gitignored. Hermes `search_files` may or may not respect ignore rules consistently across versions/config.

Durable rule:
- You can start with `search_files` for convenience.
- If `search_files` returns 0 results (or fewer than expected) for a query under `./repos`, **do not treat that as evidence of absence**.
- Cross-check with ripgrep:

  rg --no-ignore -n "<pattern>" repos/<repo_dir>/

Example sanity check:
- Query: cps-dft-sqs-toyota
- `search_files` may return only a subset.
- `rg --no-ignore` provides a reliable ground truth search for gitignored paths.

Why:
- Avoids writing documentation based on false negative searches.
