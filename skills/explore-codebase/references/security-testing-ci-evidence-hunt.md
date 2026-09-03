# CI/CD security-testing evidence hunt (repos/)

This is a reusable checklist for answering: **"What security testing/scanning exists in the codebase today?"**

## Goal

Produce *hard evidence* (repo-relative file paths + brief behavior summary) for:
- SAST/code quality
- DAST/runtime scanning
- dependency/vulnerability scanning
- IaC/K8s posture scans
- OSS/compliance scans
- notifications + gating behavior

## Recommended search strategy

1) Start broad (fast):
- `search_files(path="repos", pattern=..., target="content")`

2) If results are unexpectedly empty, cross-check with ripgrep:
- `rg --no-ignore -n "<pattern>" repos/`

3) Confirm by reading the exact files:
- `.github/workflows/*.yml|yaml`
- shared actions: `.github/actions/**/action.yaml` or custom action folders

## Marker patterns

SAST / code quality:
- `sonarqube|sonar\\.projectKey|sonarsource/sonarqube-|org\\.sonarqube|qualitygate`

DAST / runtime scanning:
- `OWASP ZAP|zaproxy|zap-x\\.sh|owasp-.*dast|ZAP_BLOCKING_RISK_CODES|frontend-authenticated-plan\\.yaml`

Vulnerability scanning:
- `trivy|aquasecurity/trivy-action|grype|syft|anchore|snyk|scanner`

IaC/K8s posture:
- `trivy config|pluto detect-files|kube-score|kube-linter|kustomize|helm`

OSS/SCA/compliance:
- `fosslens|sbom|cyclonedx|dependency-track|license`

Secrets scanning:
- `gitleaks|trufflehog|detect-secrets|secret scan`

## Evidence quality rules

- Do **not** claim a control exists based only on `CHANGELOG.md` mentions.
- Prefer a workflow, action, script, or config that actually executes the control.
- Always capture:
  - trigger (PR/push/schedule)
  - scope (repo/paths/targets)
  - tool + version (pinned if present)
  - gating behavior (fail build? quality gate?)
  - reporting/notification behavior (PR comment? Teams?)

## Session example (DFT)

Concrete examples observed in DFT repos (file paths):
- Trivy FS scan in portal PR checks: `repos/dft-portal/.github/workflows/pr-checks.yaml`
- Trivy FS scan in reusable Java PR checks: `repos/dft-github-actions/.github/workflows/java-pr-checks.yaml`
- Trivy config scan for deploy manifests: `repos/dft-deploy/.github/workflows/manifest-scan.yml`
- Pluto deprecation scan for deploy manifests: `repos/dft-deploy/.github/workflows/manifest-scan.yml`
- OWASP ZAP API scan: `repos/*/.github/workflows/owasp-dast-passive.yaml` + shared action in `repos/dft-github-actions/actions/owasp/api-scan/action.yaml`
- OWASP ZAP authenticated full frontend scan: `repos/dft-portal/.github/workflows/owasp-zap-full-frontend.yml`
