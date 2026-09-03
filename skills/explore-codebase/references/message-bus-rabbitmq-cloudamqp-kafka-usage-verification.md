# Message-bus usage verification (RabbitMQ / CloudAMQP / Kafka)

This reference captures a repeatable, evidence-led workflow for answering:

- “Is RabbitMQ/CloudAMQP still in use, or is it just legacy/debt?”
- “Did they fully migrate to Kafka?”

## Key rule

Do NOT accept README findings as evidence of runtime usage. README can be stale.

## Evidence tiers

1) Presence signals (weak / leads)
- Dependencies: `amqplib`, `pika`, `org.springframework.amqp`, `spring-rabbit(-stream)`, `com.rabbitmq.*`
- URLs/URIs: `amqp://`, `amqps://`, `rabbitmq-stream://`
- Config keys: `spring.rabbitmq.*`, `rabbitmq.*`, `RABBIT_MQ_*`
- Infra secrets: ExternalSecrets/SealedSecrets containing `cloudamqp` names/ARNs

2) Runtime usage signals (strong)
- A production call stack reaches a publish/consume method.
- Deployment manifests provide the connection parameters/secret references used by that code.

## Recommended workflow

### Step A — Find candidate code + config

- Run repo-wide search (cross-check ignores):
  - `rg --no-ignore -n "rabbitmq|cloudamqp|amqp://|amqps://|rabbitmq-stream://|spring\\.rabbitmq|org\\.springframework\\.amqp|RabbitTemplate|RabbitStreamTemplate|pika|amqplib" repos/`

Collect:
- exact file paths
- whether the hit is code vs config vs test

### Step B — Prove it’s executed (CRG call stacks)

For each candidate publisher/consumer method:

1) Build/update graph for that repo.
2) Use `query_graph_tool`:
   - `pattern=children_of` on the file/class to locate the exact qualified method name.
   - `pattern=callers_of` on that method.
3) If you only see `Test` callers: treat as non-production until proven otherwise.
4) If you see at least one non-test caller in main code:
   - chain `callers_of` upward until you reach an entrypoint:
     - REST controller method
     - scheduler
     - message listener
     - CLI/bootstrapping

Record the chain as evidence:
- leaf: publish/consume method
- intermediate services
- entrypoint

### Step C — Reconcile code vs runtime config

- Find corresponding deploy manifests (ConfigMaps/Helm values/K8s env vars) that provide:
  - Rabbit host/port/user/vhost
  - stream host/port/user/vhost
  - secret references (including cloudamqp secrets if applicable)

Interpretation guidance:
- Code publishes to BOTH Rabbit + Kafka:
  - likely intentional dual-publish migration pattern.
  - do NOT conclude Rabbit is unused.
- Config exists but there is no production call stack:
  - candidate legacy/debt.

### CloudAMQP-specific nuance

- Infra “cloudamqp” secret references prove provisioning exists.
- To claim CloudAMQP is actively used, also prove:
  - application code creates AMQP connections/publishers, AND
  - the deploy config binds that code to those secrets (env var/config key wiring).

## Output shape (for reports)

For each service/repo:
- Rabbit usage type: AMQP vs Rabbit Stream
- Proof of execution: call stack summary (entrypoint → … → publisher/consumer)
- Runtime wiring: deploy config keys/secret refs
- Migration notes: dual-publish to Kafka? yes/no
- Verdict: Active vs Candidate legacy
