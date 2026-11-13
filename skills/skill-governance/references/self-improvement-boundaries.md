# Self-Improvement Boundaries

Load this when self-improvement, a background review or a `/refine` run wants to change a skill: it
distinguishes a reported suggestion from an applied write and from release publication, and states
which consent has to exist for each.

## Three outcomes, not one

| Outcome | What it means | Where it lands |
|---|---|---|
| **Reported suggestion** | The finding is stated to the user with the exact target and the proposed rule; nothing is written. | The conversation; at most a note in the user's knowledge base if it is volatile data. |
| **Applied write** | The change is made in a writable target: an open working copy of an owned skill, a profile-local skill, or project content. It lands immediately unless the installation enables a write-approval gate; no release queue holds it. | The file itself, through `skill_manage` or a direct write to the intended repository. |
| **Release publication** | The reviewed bytes of a complete package are transferred into its canonical repository on explicit authorization. | The canonical package, then its commit; a push only when separately authorized. |

A reported suggestion is not a queue entry and creates no artifact. **`Nothing to save` is a valid
outcome** — no pitfall entry, ledger or fixed content template is prescribed for learning.

## A locked skill makes the run report

A locked skill refuses every write, including a `/refine` run or a background review. The run reports
the suggestion, naming the exact skill and the proposed change; it does not create an alternative name,
a sidecar, an adaptation, a memory entry or a diary to hold it. Unlocking is the user's action
(`skill-governance` → *Released Skills Are Locked*), and a released skill changes through its
development phase, not through a workaround.

## When `/refine` pays off

Run `/refine` deliberately, with a focus, when a session produced a lesson worth keeping: name the
skill and the behavior to capture. It captures lessons from one conversation; it is not the phase
review and it never certifies a package. It does not pay off for a one-off incident, a project fact,
volatile data, or a rule the target already states — those belong in project content, a dated note, or
nowhere.

What it can touch: any unlocked skill the run reaches — its focus is a prompt, not a technical per-skill
ACL, so read afterwards what it changed. What it cannot touch: a locked skill, a third-party source, a
released canonical package, or the canonical repository behind the phase review.

## The four consent layers

**Lock state** (may this content be edited at all), **adoption** (does the Curator manage this
package's lifecycle), **pinning** (does it survive lifecycle transitions and deletion) and **write
approval** (may this specific change land) are separate permissions; holding one implies none of the
others. A substantive change is approved as a coherent reviewed package or plan — individual
micro-edits inside that authorization do not need a second interview, but a later content change or a
wider scope does.

## No approval queue for skills

Nothing in this procedure stages a skill write for later approval. Automatic background review and the
write-approval gate are settings of one installation, not part of the generic rule; where they are
off, edits land at once and the phase review is the only check on what accumulated. Where a review
does want to replace or remove a memory entry, that proposal is staged under the memory queue — that
queue concerns memory, not skills.

## Verification

- The outcome is named correctly: suggestion reported, write applied in a permitted target, or
  publication separately authorized.
- A refused (locked) write produced a report, not a substitute artifact.
- `/refine` ran with a stated focus, and its changes were read afterwards.
- Consent layers were not conflated: an unlocked skill is not thereby approved for publication, and a
  published package is not thereby writable.
