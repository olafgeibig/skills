# C4 PlantUML house style: interface + dataflow diagrams

Use this when asked to produce a diagram like "interfaces + dataflow" from existing docs.

## Default diagram type
- Prefer C4 Container diagram (`C4_Container.puml`).
- Keep it coarse: boundary + 4–10 nodes.

## Modeling rules
- External actors: "Human users", "External clients/partners", "File senders".
- System boundary: DFT on MRT (Kubernetes tenant). Include:
  - Portal (Web UI)
  - Ingress/Gateway (Istio)
  - Domain services (grouped unless asked to split)
  - Argo Workflows (if it calls APIs)
  - Secrets wiring (ExternalSecrets) if relevant to the interface story
- Managed services: CIAM/IdP, MongoDB, S3, RabbitMQ, Kafka.

## Connection rules
- Label protocols: HTTPS, SFTP, gRPC, HTTP, AMQP/Streams, Kafka, S3 API.
- Connect domain services directly to managed messaging services when clarity is prioritized.
- Avoid mid-layer "platform" containers (e.g., "Kafka (platform)") unless they represent an actual runtime component you need to discuss.

## Legibility defaults
- No `note` blocks unless the user asks.
- Prefer short relation labels over long descriptions.
- If there is a known evidence gap, keep it out of the diagram; place it in adjacent markdown docs.
