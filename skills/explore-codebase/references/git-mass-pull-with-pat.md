# Git mass pull across ./repos with HTTPS + PAT

## Problem
When iterating over many repos under `./repos/*` and running `git pull`, some repos may fail with:

- `fatal: could not read Username for 'https://github.boschdevcloud.com': Device not configured`

This typically happens when the repo's `origin` remote is HTTPS without embedded credentials and no interactive credential helper is available.

## Working fix pattern (this session)
1) Load `GITHUB_PAT` from `./.env` (optional file).
2) For each repo under `./repos/*` that contains `.git/`:
   - Read `origin` URL via `git -C <repo> remote get-url origin`
   - If it matches `https://github.boschdevcloud.com/connected-powertrain-services/...` then set:
     - `origin = https://${GITHUB_PAT}@github.boschdevcloud.com/connected-powertrain-services/<repo_dir>.git`
   - Run `git -C <repo> pull --ff-only`

## Caveat / security note
This approach persists the token into the repo's `.git/config` (via `remote set-url`). It is functional, but may be undesirable.

If persistence is unacceptable, prefer a non-persistent approach (e.g., temporary `GIT_ASKPASS` / credential helper) and keep the remote URL clean.
