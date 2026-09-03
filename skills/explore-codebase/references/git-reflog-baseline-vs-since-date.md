# Git change-set reconstruction: reflog baseline beats `--since`

When you need a reliable change set for “what changed since I cloned” (or “what changed since I last pulled”) across many repos, **do not rely on `git log --since=<date>`**.

Reason:
- `git log --since` uses commit timestamps (author/committer dates), not “when you fetched it”.
- A `git pull` can fast-forward to commits that were authored days/weeks earlier, so `--since=<clone_date>` can incorrectly report **0 commits** even though HEAD moved.

## Reliable baseline options

### A) Original clone baseline (per repo)

Use the local reflog:
- Find the reflog entry containing `clone:`.
- Baseline SHA = the SHA at that entry.

Commands:
- `git -C repos/<repo> reflog --date=iso | rg ' clone:'`
- `BASE=<sha-from-clone-line>`
- `git -C repos/<repo> rev-parse HEAD`
- `git -C repos/<repo> diff --name-status $BASE..HEAD`
- `git -C repos/<repo> diff --shortstat $BASE..HEAD`

This gives “diff vs original clone checkout”.

### B) Pre-pull vs post-pull baseline (if you forgot to record it)

Use reflog entries:
- `git -C repos/<repo> reflog -n 5 --date=iso`
- Identify the `pull --ff-only` entry.
- The line **before** it is the pre-pull state; the pull line is the post-pull state.

Then:
- `OLD=<sha-from-pre-pull-line>`
- `NEW=<sha-from-pull-line>`
- `git -C repos/<repo> diff --name-status $OLD..$NEW`

This gives “exactly what today’s pull changed” (best for security impact triage).

## Multi-repo tip

For security/interface analysis, use baseline B (pre-pull→post-pull) when possible.
If you need a stable long-term baseline, use A (clone baseline).

## Caveats

- Reflog can expire if configured aggressively.
- Shallow clones may lack older history; diff still works for reachable commits.
