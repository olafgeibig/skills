# Verifying RabbitMQ / AMQP usage vs legacy (code + CRG call stacks)

Use this when asked: “Is RabbitMQ/CloudAMQP still in use, or is it legacy/debt? Maybe migrated to Kafka.”

Core rule: README is not evidence if the user disallows it.

## Evidence sources (preferred order)

1) **Runtime-reachability in code**
- Identify concrete publisher/consumer classes (e.g., Spring `RabbitTemplate`, `RabbitStreamTemplate`, `@RabbitListener`, AMQP client libs).
- Show they are reachable from non-test entrypoints:
  - REST controllers
  - schedulers
  - message listeners
  - startup hooks

2) **Call stacks via Code Review Graph (CRG)**
- Build/update graph for relevant software repos.
- Use `query_graph_tool` with `callers_of` recursively:
  - start at the AMQP send/consume method
  - follow callers to services
  - continue to controllers/schedulers
- Record at least one chain containing non-test nodes.

3) **Deployment manifests/config evidence**
- Look for env vars/config maps/secrets wiring (`RABBIT_MQ_*`, `spring.rabbitmq.*`, `amqp://`, `rabbitmq-stream://`).
- Treat as supporting evidence: config alone does not prove runtime use.

4) **Infrastructure secrets references (CloudAMQP)**
- ExternalSecret/SecretManager references containing `cloudamqp` prove credential plumbing exists for an environment.
- Still not proof that prod uses CloudAMQP unless prod manifests indicate it.

## Output expectations

- Be explicit whether the finding is:
  - **“used in runtime code paths”** (strongest), or
  - **“config/secret plumbing exists”** (supporting), or
  - **“library present but unreachable”** (likely legacy).

- Prefer short call-chain bullets:
  `Controller -> Service -> Publisher -> RabbitTemplate.convertAndSend`

## Pitfalls

- Don’t stop at dependency presence (gradle/npm) — it can be unused.
- Don’t conclude “not used” without checking call stacks and wiring.
- Beware tests: ensure at least one non-test caller exists in the chain.
