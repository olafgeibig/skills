# DFT docs workflow: interfaces + dataflows + diagrams (session notes)

Context: DFT CSL documentation repo with:
- `src/` as working drafts
- `csl/` as deliverables (do not modify unless asked)
- `repos/` as read-only source repositories (gitignored)

## Patterns that worked well

### 1) Interface inventory (external vs internal)

Start from `src/architecture*.md` and `src/interfaces-*.md`, then validate against repos:
- Deploy manifests: `repos/dft-deploy/**` (Flux HelmReleases, VirtualService hosts)
- Helm charts: `repos/dft-helm-charts/**`
- Service repos: OpenAPI specs and config
- Argo Workflows: `repos/dft-argo-workflows/**`

Important: keep it evidence-led with concrete file paths.

### 2) SFTP ingest (Transfer Family) vs service-integrated polling

In this workspace both signals exist:
- Transfer Family + S3 landing bucket is evidenced in `src/dataflow-sftp-ingest.md` and repo automation.
- Service-integrated SFTP config exists (e.g., filling-station-service config).

Document as: SFTP endpoint is Transfer Family → S3 landing; downstream processing is Argo and/or service-integrated polling depending on integration.

### 3) SQS as external interface (OEM/partner events)

Repo evidence shows DFT consumes SQS via Argo Events:
- EventSource queue names include `cps-dft-sqs-toyota`
- Sensor triggers workflow submission

Document as:
- External interface: inbound SQS queue consumed by Argo Events.
- Producer identity is suggested by naming but must not be asserted without publisher-side evidence.

### 4) api-viewer placement and exposure

api-viewer is a user-facing Swagger UI deployed in-cluster:
- Deployed via dft-deploy HelmRelease
- Reverse proxies OpenAPI YAML from internal services (nginx config)

Place it as a public HTTPS interface for human users and link it to domain services for spec fetches.

### 5) Diagrams (PlantUML)

Keep a coarse-grained C4 Container diagram readable:
- Model trust boundaries explicitly (DFT workspace vs MRT managed services vs Bosch managed systems)
- For messaging/storage, connect domain services directly to managed services unless there is a strong reason to introduce intermediate containers.
- Add external actors for each external interface type (users, API clients, file senders, OEM/partners).

## Hygiene
- Do not copy secrets; cite file paths only.
- When updating numbering in `interfaces-evidence.md`, ensure headings remain unique (avoid duplicate E3).
