---
name: skill-governance
description: "Use for skill ownership, locking, lifecycle, and audits."
version: "3.0.0"
author: Olaf Geibig
license: MIT
metadata:
  source: https://github.com/olafgeibig/skills
  hermes:
    category: personal
    tags:
      - skills
      - governance
      - lifecycle
      - git
      - audit
    related_skills:
      - skill-builder
---

# Skill Governance

Where does a skill live, who may change it, and how does it move through its lifecycle? This skill
owns skill categories, locking, routing, development, review, publication, updates, and library
audits. It does not teach how a package is written or structured (`skill-builder`).

## When to Use

- Deciding where a skill or learning belongs (`canonical`, `local`, `third-party`, `hermes`).
- Changing an existing canonical skill, creating a brand-new one, or promoting a local skill.
- Running review, publication, close/re-lock, checkout updates, or library audits.
- Checking whether the agent may edit a skill or must ask the user to unlock it first.

## The Four Skill Categories

| Category | Location | Control & Self-Improvement |
| --- | --- | --- |
| **Canonical** | External owned Git repositories (`skills.external_dirs`) | User-curated, Git-versioned, **locked by default**. Self-improvement off unless explicitly unlocked by the user (e.g. during burn-in). Every change reviewed before release. |
| **Local** | Profile-local `$HERMES_HOME/skills/local/` | Agent-created skills (self-improvement or user request) and brand-new skills before promotion. Self-improvement active by default. May be promoted to a canonical repo after review. |
| **Third-party** | External Git/`skills.sh` checkouts (`skills.external_dirs`), shared across profiles | **Read-only**, locked. Never edited (updates overwrite changes). Report proposed improvements in chat instead. |
| **Hermes** | Profile-local bundled & Marketplace-installed skills | Managed by Hermes as intended. User does not interfere. |

**Non-skill knowledge:** Project-specific content is not a skill — keep it in the project's own
files (e.g. `AGENTS.md`). Volatile instance state (prices, caps, quotas, model lists, dated probe
results) belongs in a dated note, never in a skill.

## Locking & Unlocking

A lock (`hermes curator lock <name>`) guards content — `skill_manage` and the file-write guard
refuse writes — without pinning a Git revision or blocking manual checkout updates.

- **Lock state is the gate.** If a skill is unlocked, the agent may edit it (including `/refine`).
  If it is locked, the agent reports the proposed change and does not write.
- **Unlocking is always the user's action.** `hermes curator unlock <skill>` accepts only **one**
  skill per invocation. Whenever an edit requires unlocking one or more skills, **always generate a
  ready-to-copy-paste block with one command per skill**:
  ```bash
  hermes curator unlock <skill-1>
  hermes curator unlock <skill-2>
  ```
  Wait until the user confirms they unlocked the skill(s). Never bulk-unlock, edit `.usage.json`
  or the ledger, or bypass a refused write.
- **Existing canonical skills are edited in place — never via a local shadow copy.** After the user
  unlocks the skill(s), edit directly in the canonical repository. For larger or multi-skill
  changes, work on a Git branch rather than `main`. When done and reviewed, re-lock.
- **Burn-in / self-improvement stays in place too.** If a newly created or heavily refactored
  canonical skill should learn from real usage (`/refine`), keep it **unlocked** in its canonical
  repository until stable — never copy it into `$HERMES_HOME/skills/` for learning.
- **No shadow or sidecar workarounds.** A lock is never evaded with a same-name shadow, sidecar,
  memory dump, or diary file.

## Routing a Learning or New Skill

1. **Search first** across `$HERMES_HOME/skills/`, every `skills.external_dirs` root, and the
   curator archive (`audit-skill-declarations.py --strict`, `hermes curator list-archived`).
   Restore an archived skill instead of recreating it.
2. **Route to one home:**
   - **Generic improvement to an own canonical skill** → the skill itself (edit directly if
     unlocked; otherwise report and output the copy-paste `hermes curator unlock` command).
   - **Generic improvement to a third-party skill** → report in chat; never edit.
   - **Agent-/environment-specific or new local skill** → `$HERMES_HOME/skills/local/<name>/`
     (real directory, never a symlink).
   - **Project-specific rule or fact** → the project's own files, not a skill.
   - **Volatile data** → a dated note, not a skill.
3. **Narrowing or extending an existing skill** becomes a delta inside the owning skill (or a
   report if third-party), never a parallel sibling skill.
4. **`Nothing to save` is a valid outcome.** Do not invent a skill or staging file just to record
   something.

## Lifecycle & Workflow Selector

**start → develop → review → publish → close/abandon → consume/update**

Load only the reference for the step in front of you:

| Trigger | Reference |
| --- | --- |
| Edit existing canonical skill(s) or start a brand-new skill | `references/develop-skill.md` |
| Review changed or new package(s) against baseline before release | `references/review-skill.md` |
| Commit / transfer / push reviewed bytes to canonical repo | `references/publish-skill.md` |
| Clean up local new-skill copy and re-lock canonical skill(s) | `references/close-development.md` |
| Update a consuming checkout to a newer released version | `references/update-library.md` |
| Run package audit, declaration audit, linter, or archive checks | `references/audit-library.md` |
| Forks, standing rules, `local/` placement, promotion signal | `references/ownership-and-scope.md` |
| `skill_manage` vs filesystem writes across `external_dirs` | `references/skill-manage-external-directories.md` |

## What the User Does

| Step | User action |
| --- | --- |
| Open | Name the skill(s)/intent; run the agent's copy-paste `hermes curator unlock ...` command; switch to a branch if needed. |
| Develop | Run `/refine` with a focus when a session produced a lesson worth keeping. |
| Review | Start or confirm the review; authorize publication of the reviewed bytes. |
| Publish | Run prepared Git staging/commit commands when locked siblings block repo-root Git; push or authorize push. |
| Update | Run prepared fast-forward command on a consuming checkout. |

## Verification

- Skill category confirmed (`canonical`, `local`, `third-party`, `hermes`); no third-party tree
  touched; no accidental local shadow created for an existing canonical skill.
- Copy-paste `hermes curator unlock <name>` command(s) (one per skill) provided whenever locked
  skills must be edited.
- Package format, frontmatter, and linter verified per `skill-builder`; library and declaration
  audits run via `references/audit-library.md`.
- Canonical skills re-locked after publication (unless intentionally left unlocked for burn-in).
