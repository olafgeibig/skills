# Recover a repository change set from its clone baseline

## Why

When you forgot to record pre-pull SHAs, or when `git log --since=<date>` is misleading (commit timestamps older than clone date), reconstruct an evidence-led change set per repo:

- baseline = commit at `git reflog` entry containing `clone:`
- compare baseline..HEAD via `git diff --name-status` (+ `--shortstat`)

This yields a stable “what changed since original clone point” view.

## Optional helper pattern

If Project A provides a helper, pass the repository directory and output path explicitly (for example, `--repos-dir <repos-dir> --out <report-path>`). Do not assume a helper script exists in every project; the reusable method is the reflog baseline and commit-range comparison.

## Notes / pitfalls

- Requires reflog retention; if the clone entry is missing, baseline cannot be reconstructed.
- If a generated report caps long path lists, mark that as truncation and preserve a way to retrieve the full commit-range diff.
- For “what did the last pull change”, prefer `git diff HEAD@{1}..HEAD` when reflog includes the pull entry.
