# DFT: Evidence-led repo diff -> doc-impact changelog

Use when
- User provides a multi-repo diff report (e.g. `repo-util/YYYYMMDD-git-diff.txt`) and asks what docs need updates.
- Goal: produce an agent-facing changelog that points reviewers to which documents/sections likely need changes.

Inputs
- Diff report with per-repo baseline + name-status.

Outputs
- `repo-util/<date>-changelog.md` (agent-facing)

Workflow
1) Verify the diff report exists and is the authoritative evidence index.
   - Treat it as the index; do not copy the full file list into the changelog.

2) Extract “high impact” changes from the diff report
   - New interfaces: new consumer/listener classes (KafkaListener, SQS, HTTP endpoints), new ingress resources.
   - New platform controls: rate limiting, auth/issuer changes, secret wiring changes.
   - Operational workflows: new GitHub Actions/workflows, new scripts.

3) For each high-impact item, verify at least one concrete claim from the code/config
   - Examples:
     - Kafka: read `KafkaTopics.java` or grep `@KafkaListener` for `topicPattern`.
     - Ingress: read the added YAML (e.g. EnvoyFilter) and capture key parameters (token bucket).
   - Keep this verification minimal: 1-3 key files, not exhaustive enumeration.

4) Write the changelog in a consistent structure
   - Scope + evidence policy (diff report as primary index).
   - Section 1: High-impact changes (interfaces + ingress).
   - Section 2: Platform-level changes (shared libs, tenant automation).
   - Section 3: Other changes to validate (deploy/helm charts/UI scripts).
   - Section 4: No-change repos (from `diff_shortstat: <none>`).

5) Add “Suggested doc updates” per item
   - Reference document classes, not specific pages unless known:
     - architecture, interfaces, dataflows, deployment, threat/risk.

Pitfalls
- Don’t claim “publishing” when you only saw consumers; label correctly (consumer vs producer).
- Keep secrets out. Point to file paths, not values.
- Avoid absolute paths in the written changelog; use repo-relative paths.
- Verify file actually exists under `repo-util/` before telling the user it was created.

Verification
- After writing: list `repo-util/` and confirm the changelog file is present.
- Report exact path.
