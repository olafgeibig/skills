# Packet 00 — Safe execution baseline

**OpenSpec task group:** 0 in `../tasks.md`.
**Prerequisites:** None; execution authorization is a gate.

## Minimal context to read

- `README.md` (dispatch protocol).
- `../proposal.md` once if the worker has no change context.
- `../specs/skill-source-transport/spec.md`.
- `../specs/skill-refactor-integration/spec.md`.
- `../design.md`: Context, D2, Migration Plan.
- Contract scope: Inspect all files read-only; no implementation edits until explicit worktree authorization.

## Allowed changed files

- Planning/baseline handoff only; implementation roots require explicit approval first.

No other production/config/profile/vault files. Read predecessor definitions/usages before editing; if required interface changes cross ownership, return that dependency to the parent. Parent alone updates task checkboxes.

## Required behavior and traps

Capture actual HEAD/dirty paths and package test output. Explain sweep exposure: planning files are untracked in the runtime checkout. Do not start staging or checkout main. After authorization establish the isolated implementation worktree and explicitly carry planning artifacts; coordinate foreign dirty files instead of auto-committing them.

## Verification and handoff

Run each named regression node to prove its intended failure before implementation and pass after. Then run the affected test file and full package suite from the authorized worktree; exact commands are in README.md. Run `git diff --check`. Return changed paths, symbol/API deltas, actual test exit/pass results, source/ref/tree evidence where relevant, blockers and successor context. Do not commit/push, touch live jobs, archive, check global tasks, or claim an unavailable check passed.
