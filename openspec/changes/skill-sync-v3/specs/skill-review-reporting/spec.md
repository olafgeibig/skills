# Spec Delta

## Purpose

Make autonomous canonical skill review inspectable and correctable through scoped evidence, readable reports and optional user feedback, without a daily human approval queue.

## ADDED Requirements

### Requirement: Semantic review is autonomous and scope-aware
The agent SHALL assess usefulness, duplication, consistency and canonical scope, classifying additions, corrections and deliberate replacements. Illustrative paths and code SHALL be distinguished from instance-specific instructions; ordinary semantic conflicts SHALL NOT require daily human approval.

#### Scenario: Generic illustrative example
- **WHEN** a proposed lesson uses a clearly illustrative path or code citation
- **THEN** it is judged on its role and scope rather than vetoed solely by a path or date regex, preferring neutral example names where appropriate

#### Scenario: Intentional rule replacement
- **WHEN** a proposed change deliberately replaces an existing instruction
- **THEN** review names the old and new rules and reason, removes incompatible remnants and validates the coherent replacement

### Requirement: Decisions retain provenance and rejection reasons
Every affected input path and additional edited path SHALL be covered by evidence-backed decisions. Rejected lessons SHALL remain inspectable with exact source anchors and reasons; retaining source history SHALL NOT be presented as erasing prohibited data.

#### Scenario: Good lesson is rejected by mistake
- **WHEN** a lesson is rejected
- **THEN** its source and reason remain in the report so later feedback or a fresh proposal can reconsider it without relying on recurrence

### Requirement: Reports bind the exact reviewed candidate
Before publication the system SHALL store and verify an immutable review report bound to M,T,policy,decisions and final tree at the configured permitted vault destination. Publication outcomes SHALL be recorded separately in an idempotent receipt, never backfilled into the approved report.

#### Scenario: Report absent or altered
- **WHEN** the rendered review cannot be read back exactly at its configured destination
- **THEN** publication remains blocked with preserved candidate evidence

#### Scenario: Receipt delivery fails after publication
- **WHEN** P was published but result-note delivery fails
- **THEN** receipt delivery is retried without changing the immutable review or republishing P

### Requirement: Feedback is optional and current-state based
The system SHALL accept report-specific feedback in a normal chat, resolve ambiguity when needed, and prepare a correction against the current skill state. It SHALL NOT require manual digest transcription, infer approval from silence, or blindly restore historical bytes.

#### Scenario: Feedback on an older report
- **WHEN** the user dictates a correction referring to an older report after subsequent skill edits
- **THEN** the agent reads the report and current skill and preserves unrelated later changes in its correction

### Requirement: Review context is bounded and usage is visible
Runtime review SHALL start from a manifest, complete changed hunks including deletions, conflict packets and bounded section context. Additional reads SHALL be targeted; usage reports SHALL distinguish measured, estimated and unavailable counters. No specific token ceiling SHALL be claimed before pilot measurement.

#### Scenario: Small daily contribution
- **WHEN** one small candidate is reviewed
- **THEN** the runtime does not load the entire implementation plan or repeatedly compare full base/main/source files by default

#### Scenario: Context or review budget insufficient
- **WHEN** a complete review cannot finish within its configured turn/context budget
- **THEN** it records incomplete review and preserves progress rather than publishing unchecked content or restarting an unlimited full-file loop

### Requirement: Periodic review examines existing instructions
A bounded periodic review SHALL inspect existing canonical skill content, not only new diffs, for contradictions, duplication and past mistakes. Small corrections SHALL enter normal review; broad redesign SHALL enter the explicit refactoring path.

#### Scenario: Existing bad rule outside today's diff
- **WHEN** whole-skill review identifies a previously integrated bad instruction
- **THEN** it reports or proposes a correction even though that instruction is absent from today's candidate diff

### Requirement: Report destination respects profile boundaries
Reports SHALL be written only to an explicitly configured permitted vault/profile destination and SHALL exclude prohibited profile context and secret values. A source registry or branch label SHALL NOT be claimed as a hard data-access boundary.

#### Scenario: Unapproved mixed-trust source
- **WHEN** a source is not permitted for the private report destination
- **THEN** content rendering and publication are blocked with a non-sensitive diagnostic
