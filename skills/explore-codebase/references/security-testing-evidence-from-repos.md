# Security testing evidence discovery in repositories (SAST/DAST/scanning)

Purpose: A repeatable checklist to collect **hard evidence** from repos/ about what security testing and scanning is *actually implemented*.

This is intentionally tool-agnostic and evidence-led: it points to repository artifacts (workflow files, actions, configs) rather than documentation claims.

## 1) What to collect (evidence items)

For each security-testing mechanism you claim exists, capture:

- Repo + file path
- Trigger: PR/push/schedule/workflow_run
- Environment: dev/prod/etc.
- Test target: API/openapi, frontend URL, container image, dependencies
- Enforcement: gating / fail conditions / thresholds
- Notification: Teams webhook, etc.
- Output artifacts: reports, uploaded artifacts, summary markdown

## 2) Minimal discovery commands

### Enumerate workflows

```
find repos -path '*/.github/workflows/*' -type f \( -name '*.yml' -o -name '*.yaml' \)
```

### Search for common security-testing markers

SAST:
- `sonarqube|sonar\.projectKey|sonarsource/sonarqube-scan-action|org\.sonarqube`

DAST / OWASP ZAP:
- `OWASP ZAP|zaproxy|zap-|owasp-dast|DAST`

Container/image scanning:
- `trivy|grype|syft|anchore|snyk|dockle|container scan|docker scan`

SBOM / OSS scanning:
- `sbom|cyclonedx|fosslens|dependency-track`

## 3) Reliability pitfall

If search results look suspiciously empty, cross-check with ripgrep while ignoring ignore rules:

```
rg --no-ignore -n '<pattern>' repos
```

Do not conclude “not present” from a single search tool.

## 4) Evidence extraction template (copy/paste)

For each workflow:

- **Workflow name**:
- **File**:
- **Trigger**:
- **Environment**:
- **Target**:
- **Credentials/Secrets used** (name only; do not copy secrets):
- **Blocking/Gating**:
- **Notification**:
- **Artifacts/Reports**:

## 5) Illustrative examples (Project A; placeholders only)

- An application repo may run static analysis and wait for a quality gate.
- A scheduled workflow may scan an API using an OpenAPI definition.
- A frontend scan may use an authenticated test plan and enforce blocking thresholds.
- A registry publish workflow is not, by itself, evidence of vulnerability scanning.
- An OSS/license scan is distinct from container-image scanning.

These are example patterns, not claims about any repository. Confirm each control in the actual workflow, action, or configuration.
