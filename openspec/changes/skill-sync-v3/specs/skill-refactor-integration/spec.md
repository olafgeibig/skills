# Spec Delta

## Purpose

Allow deliberate cross-file skill redesign on isolated refactoring branches while ongoing self-improvement continues and only a finished, reviewed exact tip can enter main.

## ADDED Requirements

### Requirement: Refactoring development is isolated
A large deliberate change SHALL use a separate `refactor/<slug>` worktree outside runtime skill discovery. Normal sweeps SHALL NOT stage or publish that worktree. Developers SHALL merge main into it without rebasing published history.

#### Scenario: Backup push during unfinished redesign
- **WHEN** the developer pushes an unfinished refactoring branch for backup
- **THEN** neither that push nor a commit message makes it an automatic consolidation candidate

### Requirement: Readiness requires explicit exact-tip submission
Only an explicitly submitted refactoring ref, exact commit and replacement brief SHALL become a refactoring candidate. The submitted tip SHALL contain captured main; later edits SHALL require a new exact-tip submission.

#### Scenario: Main advanced after submission
- **WHEN** published main advanced beyond the main included by the submitted tip
- **THEN** integration requires merging current main into the refactor branch, renewed checks and a new submission rather than silently extending old approval

### Requirement: Refactoring cannot bypass readiness through transport
Transport candidates SHALL reject known unpublished refactoring ancestry and side-parent imports not already published in main. This cooperative provenance check SHALL NOT be described as protection against every hidden cherry-pick or malicious writer.

#### Scenario: Indirect unsubmitted refactor import
- **WHEN** a transport merges an unpublished refactoring tip or fast-forwards to a known unfinished refactor commit
- **THEN** ordinary transport capture refuses rather than consuming it as an incidental self-improvement

### Requirement: Refactoring publication preserves exact reviewed tip
The integration commit SHALL have ordered parents M,T and a tree exactly equal to the reviewed submitted refactoring tip. Any required content change SHALL be committed and resubmitted before publication, not improvised during promotion.

#### Scenario: Helpful extra fix after final review
- **WHEN** the candidate tree differs from the submitted refactoring tree
- **THEN** publication refuses and requires a newly reviewed tip

### Requirement: Integration freeze is narrow and owned
The final freeze SHALL use the same short publisher lock as normal publication and SHALL NOT stop unrelated producer editing, staging or source pushes. A long preparation or review SHALL release the freeze and retry final freshness checks later.

#### Scenario: Producer advances during final integration
- **WHEN** refactoring holds the main publisher lock while another producer commits and pushes new work
- **THEN** the producer continues, another publisher waits, and the new transport work remains pending after the refactoring integration

### Requirement: Refactoring has an independent completion review
The finished implementation SHALL pass the stronger reviewing assistant's independent concept/spec/code and executed acceptance review before rollout. This one-time implementation gate SHALL NOT become a daily human candidate approval requirement.

#### Scenario: Cheaper implementer reports success
- **WHEN** the implementation worker says the refactoring is complete
- **THEN** the reviewer checks actual files, Git parents/trees and real test output rather than accepting the worker narrative alone
