# Spec Delta

## Purpose

Keep local skill improvements safely staged and publish only the exact producer snapshot that has been reviewed, without disrupting separate refactoring worktrees.

## ADDED Requirements

### Requirement: Producer staging preserves unrelated work
The system SHALL stage only a registered transport checkout, refuse a pre-existing dirty index or active Git operation, and leave refactoring worktrees excluded. Failures SHALL preserve worktree bytes and leave staging retryable.

#### Scenario: Refactoring branch is not swept
- **WHEN** a sweep encounters `refactor/topic` with unfinished tracked edits
- **THEN** it reports exclusion and changes neither index, commits nor ledger cursor

#### Scenario: Unexpected main checkout
- **WHEN** a transport sweep encounters `main`, including clean main
- **THEN** it refuses with a branch-policy diagnostic rather than declaring healthy transport staging

#### Scenario: Stale ledger path and whitespace retry
- **WHEN** a missing never-tracked ledger path accompanies a valid edit, or a staged whitespace check fails
- **THEN** it records the stale-path skip without blocking valid work, and on failure undoes only its own index changes so correction and retry can succeed

### Requirement: Ledger acknowledgment uses a stable snapshot
The system SHALL advance the staging cursor only through entries observed for that staging attempt, after successful securing or explicit recorded skipping. New entries arriving during staging SHALL remain pending.

#### Scenario: Concurrent ledger append
- **WHEN** another writer appends an entry during a staging commit
- **THEN** the cursor does not acknowledge the new entry in that attempt

### Requirement: Producers refresh using ancestry and merges
The system SHALL fast-forward a clean transport when possible, do nothing when main is already its ancestor, and preserve divergent or dirty work for deliberate pre-consolidation merging. It MUST NOT reset, rebase or autostash producer work.

#### Scenario: Published contribution refresh
- **WHEN** the producer tip is an ancestor of published main
- **THEN** refresh fast-forwards without creating an unnecessary merge commit

#### Scenario: Divergent unpublished work
- **WHEN** new local work diverges from main
- **THEN** the session-start hook preserves it and reports that pre-consolidation must merge main; it does not launch an LLM or guess a conflict resolution

### Requirement: Producer publication is snapshot-bound
The system SHALL serialize producer index/publication operations and push the exact reviewed commit, not a branch name whose tip can advance after review. New commits SHALL remain unpublished until reviewed.

#### Scenario: Sweep commits after review
- **WHEN** local HEAD advances from reviewed T to T2 before the push
- **THEN** publication pushes T only and records T as the observed published tip

### Requirement: Install preserves consent and unrelated hooks
The installer SHALL require an explicit fresh-ledger bootstrap choice before mutation, preserve existing cursors on upgrade, append its exact session hook without replacing unrelated hooks, and leave global consent policy unchanged.

#### Scenario: Missing bootstrap choice
- **WHEN** a fresh install has no sync state and no explicit bootstrap option
- **THEN** it refuses before wrapper, state, config or file-mode writes

#### Scenario: Existing hook lists
- **WHEN** a profile already has other session-start or skill-lifecycle hooks
- **THEN** installation preserves those entries and neither blanket-clears lifecycle hooks nor enables global auto-accept

### Requirement: Source scope is checked before sharing
The source workflow SHALL exclude prohibited profile content and suspected credential material before transport push. Content already exposed in transport history SHALL block ordinary integration and trigger an exposure diagnostic without echoing sensitive values.

#### Scenario: Final tree removes prohibited historical content
- **WHEN** an unpublished source commit contains prohibited data even though its latest tree removed it
- **THEN** final-tree redaction is not treated as permission to share that history
