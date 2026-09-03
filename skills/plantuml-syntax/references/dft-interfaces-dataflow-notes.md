# DFT workspace patterns: interfaces + dataflow diagrams (session notes)

This note captures durable patterns discovered while producing interface/dataflow diagrams in the DFT CSL workspace.

## Key modelling choices that improved clarity

1) Separate ownership boundaries explicitly

- Use distinct System_Boundary blocks for:
  - DFT Kubernetes workspace (workloads)
  - MRT managed services (platform-provided deps)
  - Bosch managed systems (enterprise services like CIAM)

This avoids implying that Bosch-wide identity is operated by the MRT tenant.

2) SFTP ingest should be modelled as termination + storage, not just “service polls SFTP”

Evidence in this workspace shows:
- External party uploads via SFTP
- SFTP endpoint is implemented as AWS Transfer Family
- Transfer Family maps home directories into an S3 landing bucket (e.g., cps-dft-system-sftp)

Downstream processing may be:
- Argo Workflows reading from the landing bucket and calling DFT APIs
- and/or service-integrated polling ingest (service has SFTP_HOST etc.)

Diagram guidance:
- Model: External sender -> Transfer Family (SFTP) -> S3 landing bucket
- Only add extra processing components (e.g., Lambda OCR) if separately validated.

3) Argo Workflows trigger modes to represent

- Scheduled runs via CronWorkflow
- Event-triggered runs via Argo Events using AWS SQS EventSource + Sensor:
  - SQS message -> Sensor -> submit Workflow (workflowTemplateRef)

Diagram guidance:
- Model: SQS -> Argo Workflows (trigger)

## Evidence pointers (repos)

- Argo Events / SQS:
  - repos/dft-argo-workflows/argo-workflows/fuel-events/sensors/*.yaml

- CronWorkflows:
  - repos/dft-argo-workflows/argo-workflows/fuel-events/workflows/*.yaml

- Transfer Family user management + S3 bucket mapping:
  - repos/dft-github-actions/actions/sftp-management/new-user.js

- Landing bucket used by workflows:
  - Many cron workflows reference: s3://cps-dft-system-sftp/...
