---
name: skill-library-maintenance
description: "Use when auditing, developing or publishing skills."
version: "2.0.0"
author: Olaf Geibig
license: MIT
metadata:
  source: https://github.com/olafgeibig/skills
  hermes:
    category: personal
    tags:
      - skills
      - git
      - maintenance
      - audit
    related_skills:
      - skill-builder
      - skill-governance
---

# Skill Library Maintenance

Which state is a skill in, and how does it reach the next one? This skill owns the lifecycle
around a canonical skill package: opening a development phase, ending it with a review,
publishing the reviewed bytes, closing or abandoning the phase, and updating a consuming
library. It does not teach how a package is written (`skill-builder`) and it does not decide
where knowledge belongs or who may write it (`skill-governance`).

## When to Use

- A released skill needs a change: open, run and close a development phase.
- A new skill should become a released canonical skill.
- A phase is ready for review, publication, closing or deliberate abandonment.
- A consuming checkout or profile should move to a newer released version.
- The library needs evidence: size, links, collisions, overrides, legacy metadata, archives.

Loading this file alone is enough to know which state the skill is in and which single workflow
to request next. It is not enough to run a workflow, and it does not replace the ownership rules.

## Invariants

- **Stable locked canonical source.** A released owned skill lives in the canonical repository and
  is locked. The lock guards content; it does not pin a Git revision and does not stop the user
  from updating a checkout.
- **One temporary complete working copy.** A phase copies exactly one skill — the whole package,
  same directory and name, with references, scripts, templates, assets and tests — into the
  developing profile. Never a partial package, never a symlink, never a second canonical copy.
- **Recorded baseline and owner.** Before the first edit the phase records its canonical source,
  package path, starting commit (or "none" for a new skill), intent, profile, one owner and the
  prior lock state. That record lives in the open-development-phases table in the user's knowledge
  base; the profile skill names its path.
- **Reviewed bytes.** A phase ends in a dedicated review of the complete package against that
  baseline. Publication approval covers exactly the reviewed bytes; a later content change needs
  another review.
- **Explicit publication.** Transfer into the canonical repository is an authorized operation with
  validation, explicit paths, a local commit, and a separately authorized push read back from the
  remote. Nothing publishes by itself.
- **Protected unrelated work.** Dirty files, foreign changes, sibling locks and other writers are
  preserved. No reset, stash, rebase, broad staging or ledger surgery; one writer per file.

## Lifecycle

**start → develop → review → publish → close/abandon → consume/update**

- **Start** opens one phase for one skill, or for one coupled change across several named skills.
  A new skill begins as ordinary local work: its baseline is "none", it pretends to no canonical
  existence, and review comes before its first publication.
- **Develop** is use on real work plus bounded learning in the open working copy.
- **Review** is a dedicated session comparing the complete package with the baseline.
- **Publish** transfers the reviewed bytes on explicit authorization.
- **Close/abandon** removes the copy while it is unlocked, verifies the source again, and restores
  the lock on the canonical package.
- **Consume/update** moves a released checkout to a newer version deliberately.

## Workflow Selector

| Trigger | Reference | Expected outcome |
|---|---|---|
| A new skill for the canonical library, or an existing skill needs a change, and no phase is open | `references/develop-skill.md` | One known development target, isolated from consumers |
| Learning is finished and the package is ready for the dedicated review session | `references/review-skill.md` | An explicitly reviewed package, or concrete unresolved findings |
| Review passed and the user authorized publication of the reviewed bytes | `references/publish-skill.md` | Verified publication, or clearly unpublished local work |
| Publication is verified or the phase is abandoned; the copy must leave discovery and the lock must return | `references/close-development.md` | External source active again, or a clearly blocked close |
| A consuming checkout or profile should move to a newer released version | `references/update-library.md` | Known released checkout without losing local work |
| Library evidence is needed: audits, collisions, overrides, legacy fields, archive inventory | `references/audit-library.md` | Evidence, not an automatic migration |

Load only the reference for the action in front of you; read the next one when the action actually
reaches it. The lifecycle is a sequence of states, not a reading list, and no workflow requires a
sibling workflow preloaded.

## Boundaries

- **No automatic canonical learning.** Edits and `/refine` change an unlocked working copy at once;
  on an installation without a write-approval gate nothing is queued, and nothing writes itself into
  a released package. A locked skill makes the write report instead.
- **No adaptation workaround.** A lock is never evaded with a same-name variant, a sidecar, a
  temporary parallel skill or an adaptation package. Legacy `adapted_from` metadata is readable
  history, not permission to create another skill.
- **Third-party sources unchanged.** An external checkout is read-only; taking one over as a
  maintained fork is a separate, explicit request, not a learning escape.
- **No unattended integration.** No pipeline, scheduled job or background pass moves unreviewed
  work into the canonical branch. Restructuring a package is development of that package, not an
  alternative release path.
- **Unlock stays the user's action.** The rule is stated once, in `skill-governance` → *Released
  Skills Are Locked*; this skill names the exact package that must be opened and waits.

## Verification by Phase

- **Open:** `skill_view` and the edit resolver report the local working copy; the copy is complete;
  no second same-name package exists; the phase record is written.
- **Develop:** affected checks are re-run after each edit, links resolve, the main file stays within
  the quality gates, the version is bumped once for the phase.
- **Review:** the complete package is compared with the baseline; instance specifics are gone;
  duplicates and superseded rules are removed; package validator and library audit pass.
- **Publish:** the staged set equals the reviewed file list; the commit contains exactly those
  paths; a push, if authorized, is read back from the remote.
- **Close:** the name resolves to the canonical package again, its content is the published
  content, the lock target is the canonical directory, and no local override is reported.
- **Update:** the checkout was clean before and after; `HEAD` is the intended released commit; no
  open working copy was overwritten.

## What the User Does

| When | User action |
|---|---|
| Open | Name the skill and the intent; unlock it. |
| Develop | Run `/refine` with a focus when a session produced a lesson worth keeping. |
| Review | Start the review session; authorize publication of the reviewed bytes. |
| Publish | Run the prepared staging and commit commands; push or authorize the push. |
| Update | Run the prepared update command on a consuming checkout. |
| Archive | Run the archive command for a locked local skill. |

Everything else, including re-locking at close, is the agent's.
