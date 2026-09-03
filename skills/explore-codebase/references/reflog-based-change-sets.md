# Reflog-based change-set reconstruction (DFT multi-repo)

Use this when you ran a batch `git pull` over many repos and need a defensible “what changed” baseline.

## Why `git log --since=<clone_date>` is not sufficient

`--since` filters by commit timestamp. It can miss changes you *actually pulled* when:
- commits were created earlier than the clone timestamp but fetched later (fast-forward pulls older commits)
- author/commit timestamps are skewed
- you’re comparing across branches where timestamps don’t align with fetch/pull time

For security analysis / interface change tracking, you need a baseline that corresponds to your local state, not commit timestamps.

## Recommended baselines

### A) Current vs original clone (best when you need “diff vs what we started with”)

Per repo:
- baseline SHA: from `git reflog` entry containing `clone:`
- head SHA: `git rev-parse HEAD`
- diff:
  - `git diff --shortstat <baseline>..HEAD`
  - `git diff --name-status <baseline>..HEAD`

This gives a stable “since clone” change set.

### B) What did the last pull change? (best for “today’s update impact”)

Per repo:
- baseline SHA: previous HEAD from reflog, usually `HEAD@{1}`
- diff:
  - `git diff --shortstat HEAD@{1}..HEAD`
  - `git diff --name-status HEAD@{1}..HEAD`

This is the most honest way to answer: “did our batch pull change interfaces/security posture?”

## Script pattern

Automate this across `./repos/*`:
- detect git repos via presence of `.git/`
- for each repo, extract clone baseline from reflog (`clone:`)
- emit report (cap long lists)

Key constraints:
- do not write line-numbered output into tracked documentation
- do not modify repo state (read-only commands)
