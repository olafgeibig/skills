# Security testing evidence discovery in DFT repos (SAST/DAST/scanning)

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

## 5) Session examples (typical for DFT)

Examples to look for in DFT-class repos:
- SonarQube workflow files (SAST; quality gate waiting)
- OWASP ZAP API scan using OpenAPI specs (scheduled; uses Keycloak client credentials)
- OWASP ZAP full frontend scan (scheduled; authenticated scan plan; enforces blocking risk codes)
- Registry/ECR-related workflows (mirror/publish) — note: presence of ECR workflows is not proof of vulnerability scanning
- OSS/license scanning workflows (e.g. Fosslens) — note: this is not a container scan
