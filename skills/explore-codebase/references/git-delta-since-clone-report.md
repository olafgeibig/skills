# Git delta since clone (multi-repo) — workflow + pitfalls

## When to use

Use when the user asks for a report like:
- “Git diff / delta since clone”
- “What changed since I originally cloned these repos?”
- “Summarize changes across all repos after a mass `git pull`”

## Key idea

In a workspace with many cloned repos under `./repos/`, you can compute a *time-based* delta anchored to the **local clone timestamp** as recorded in each repo’s **git reflog**.

This is useful because:
- it works without tags
- it’s anchored to the user’s local environment
- it supports cross-repo reporting

## Canonical steps (per repo)

1) Determine clone timestamp

```
git -C repos/<repo> reflog -n 20 --date=iso
```

Find the line containing `clone:` and extract the `{YYYY-MM-DD ...}` part.

Pitfall: `git reflog --reverse` is not reliable for finding the earliest clone event; reflog retention/ordering can differ. Prefer a direct scan of recent reflog entries.

2) Commit/activity summary since clone timestamp

```
# commits count
 git -C repos/<repo> log --since="<clone_dt>" --oneline --no-decorate | wc -l

# distinct files touched
 git -C repos/<repo> log --since="<clone_dt>" --name-only --pretty=format: \
   | sed '/^$/d' | sort -u | wc -l

# added/deleted lines (aggregate)
 git -C repos/<repo> log --since="<clone_dt>" --numstat --pretty=format: \
   | awk 'NF==3 {add+=$1; del+=$2} END {print add+0 "\t" del+0}'

# messaging-related subject scan (optional)
 git -C repos/<repo> log --since="<clone_dt>" --pretty=format:%s \
   | rg -i '(kafka|confluent|schema\s*registry|rabbitmq|amqp|cloudamqp)' \
   | head -n 20

# top files by frequency (optional)
 git -C repos/<repo> log --since="<clone_dt>" --name-only --pretty=format: \
   | sed '/^$/d' | sort | uniq -c | sort -nr | head -n 10
```

## Pitfalls

- Some repos may not show a `clone:` entry (reflog expired/disabled). Mark clone_date UNKNOWN and skip time-based stats.
- “0 commits since clone” can be correct even after `git pull` if the repo was already up to date.
- Do not paste secrets (URLs with embedded tokens) into the report.
