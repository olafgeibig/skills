# repo-diff-vs-clone (DFT) — reconstruct change set after batch git pull

## Why

When you forgot to record pre-pull SHAs, or when `git log --since=<date>` is misleading (commit timestamps older than clone date), reconstruct an evidence-led change set per repo:

- baseline = commit at `git reflog` entry containing `clone:`
- compare baseline..HEAD via `git diff --name-status` (+ `--shortstat`)

This yields a stable “what changed since original clone point” view.

## Helper script (in this workspace)

Path:
- `bin/repo-diff-vs-clone.sh`

Output:
- `analysis/git-diff-vs-clone-report.txt`

Usage:
- `bin/repo-diff-vs-clone.sh`
- `bin/repo-diff-vs-clone.sh --repos-dir ./repos --out analysis/git-diff-vs-clone-report.txt`

## Notes / pitfalls

- Requires reflog retention; if the clone entry is missing, baseline cannot be reconstructed.
- The report truncates `git diff --name-status` per repo to keep the file readable.
- For “what did the last pull change”, prefer `git diff HEAD@{1}..HEAD` when reflog includes the pull entry.
