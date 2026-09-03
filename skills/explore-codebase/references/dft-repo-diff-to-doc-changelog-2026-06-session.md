# DFT repo diff → doc-impact changelog (session note)

Context
- In this workspace, agents often generate a per-repo diff report under `repo-util/<date>-git-diff.txt`.
- The user expects a *doc-impact* changelog that helps review existing documentation, not a dump of filenames.

Key requirements pattern
1) Use the diff report as the *primary evidence index*
- Cite `repo-util/<date>-git-diff.txt` as the evidence source for each change bucket.
- Do not copy a full file list into the changelog; keep it high-level.

2) Enrich only high-impact interface changes with *select code evidence*
- For claims like "Service X now consumes Kafka topicPattern Y", verify by opening the relevant consumer code and extracting:
  - exact `@KafkaListener(topicPattern=...)`
  - any topic constants from `KafkaTopics.java`
  - owner/tenant scoping rules (e.g., ownerId derived from topic prefix)

3) Keep doc guidance actionable
- For each change bucket, include:
  - “Impact” (why docs likely need updates)
  - “Evidence” (diff index + 1–3 key paths)
  - “Suggested doc updates” (which doc classes to revisit: architecture, interfaces, dataflows, deployment, threat/risk)

4) File write correctness: verify location
- After writing, always run `ls -la repo-util/` and confirm the file exists.
- If the user requested an absolute path, write to the absolute path and verify with `ls -la <absolute_dir>/`.

Common high-impact buckets (examples)
- New runtime messaging interfaces (Kafka consumers, AMQP publishers)
- New ingress controls (rate limiting, WAF changes, auth gateways)
- Tenant-management changes affecting authN/authZ, service accounts, ACL automation
- Deploy manifests/helm chart changes affecting public endpoints or trust boundaries

Anti-patterns
- Listing hundreds of changed files.
- Stating a new interface exists without verifying via code/config.
- Claiming a file was written without checking it is in the expected workspace directory.
