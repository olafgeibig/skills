# Spec Delta

## Purpose

Integrate exactly reviewed source snapshots into shared skill main history while preserving concurrent source work and recovering safely from interrupted publication.

## ADDED Requirements

### Requirement: Candidate identity binds immutable inputs
The system SHALL capture and pin full fetched main M and source T commits, repository identity, source identity and policy version. The same inputs SHALL identify the same candidate; a different main SHALL require a new review.

#### Scenario: Source advances after capture
- **WHEN** a source moves from T to descendant T2 during review
- **THEN** the candidate continues to represent T only and T2 remains available for a later candidate

### Requirement: Consumption is an ancestry fact
A source tip SHALL count as consumed only when it is an ancestor of published main. An unacknowledged empty-diff or wholly rejected contribution SHALL receive a documented merge acknowledgment rather than silently disappearing.

#### Scenario: Empty-diff source
- **WHEN** T has the same tree as M but is not its ancestor
- **THEN** T remains pending until a reported integration commit acknowledges it

### Requirement: Preparation uses an isolated complete merge tree
The system SHALL prepare outside runtime discovery checkouts and preserve all supported clean and conflict-resolved additions, deletions, empty files, renames and executable text modes. Unsupported artifacts and unresolved technical conflicts SHALL block promotion.

#### Scenario: Clean new file and deletion
- **WHEN** a source adds one file and deletes another without conflicts
- **THEN** both effects appear in the final staged tree, not only in scratch artifacts

#### Scenario: Genuine conflicting edits
- **WHEN** both main and source change the same original instruction
- **THEN** the conflict is exposed for explicit agent resolution with no blanket keep-ours default

### Requirement: Final artifact is the publication gate
The system SHALL validate the actual staged tree, complete decision coverage, evidence and required checks. Incoming warnings SHALL be distinct from final validation; a repaired incoming finding SHALL be able to pass the final gate.

#### Scenario: Incoming instance instruction is generalized
- **WHEN** review replaces an incoming instance-specific instruction with valid generic text
- **THEN** the final gate evaluates the corrected result rather than repeatedly vetoing the original source diff

### Requirement: Publication preserves reviewed tree and parents
A promoted normal candidate SHALL produce a merge commit P with exactly ordered parents M,T and exactly the validated tree. Main publication MUST NOT use force, and transport branches MUST NOT be reset.

#### Scenario: Concurrent T2 survives publication
- **WHEN** P integrates T while the remote source already contains T2
- **THEN** T2 remains unchanged and later integration does not duplicate T's already acknowledged content

#### Scenario: Main moves before push
- **WHEN** published main no longer equals captured M
- **THEN** the candidate is stale and is not force-pushed or silently reapproved

### Requirement: Publication is recoverable and idempotent
The system SHALL persist exact result P before pushing, verify the remote result, and reconcile uncertain outcomes using saved P and published ancestry. Missing local outcome or report delivery SHALL NOT cause a duplicate integration commit.

#### Scenario: Crash after successful push
- **WHEN** P reached main but the process failed before recording success
- **THEN** reconciliation recognizes P, repairs state and retries receipt delivery without publishing a second merge

### Requirement: Publisher locking covers the common repository
One owned publisher lock SHALL cover every linked worktree of the publisher repository regardless of state-store path. Expiry by age alone and unrelated cron executions SHALL NOT authorize breaking or refusing that lock.

#### Scenario: Alternate worktrees compete
- **WHEN** two configured stores refer to linked worktrees of one publisher clone
- **THEN** their promotions contend on the same ownership-checked lock while a separate producer clone remains writable

### Requirement: Dry runs and health signals are honest
Dry runs SHALL leave state, files, index, local and remote refs unchanged, including fetch state. Monitor errors SHALL produce an observable stable error signal rather than healthy empty success; unchanged blocked candidates SHALL NOT cause unlimited retries.

#### Scenario: Remote fetch unavailable
- **WHEN** the pending monitor cannot read the remote
- **THEN** it emits a stable unhealthy signal and a diagnostic without inventing a successful empty result
