# DFT docs: keep `mrt-based-architecture.md` consistent with `dft-interfaces-dataflow-architecture.puml`

Purpose: quick checklist to avoid drift between the narrative doc and the diagram.

## Checklist (diagram → doc coverage)

### External actors / entrypoints
- Portal UI hostnames present (dev/prod) and evidenced from HelmRelease values.
- Domain REST API hostnames present (dev/prod) and evidenced from HelmRelease values.
- API Viewer hostname present (dev/prod) and evidenced.

### Routing layer (boundary)
- If diagram shows an ingress/gateway, doc must mention *what* implements routing (Istio Gateways/VirtualServices).
- Include at least one VirtualService file as evidence showing host + gateway + path routing (e.g., `/docs`, `/api-docs`, `/apis/*`).

### Ingestion interfaces
- REST API ingestion explicitly called out (not only SFTP / workflows).
- SFTP: if diagram shows Transfer Family + S3 landing, doc must state Transfer Family explicitly and link evidence.
- SQS: document as inbound queue consumed by DFT; avoid asserting publisher identity without publisher-side evidence.

### Internal interfaces
- Argo → domain APIs (tokened REST) captured.
- Domain → MongoDB/S3/RabbitMQ/Kafka captured with clear “evidence basis” (runtime usage vs provisioning).

## Common pitfalls
- Forgetting the REST ingestion path because SFTP/Argo are more visible.
- Listing hostnames but not mentioning the routing primitive (VirtualService/Gateway), which is the real interface boundary.
- Treating queue names as proof of who publishes.
