---
name: plantuml-syntax
description: Authoritative reference for PlantUML diagram syntax. Provides UML and non-UML diagram types, syntax patterns, examples, and setup guidance for generating accurate PlantUML diagrams.
allowed-tools: Read, Glob, Grep
---

# PlantUML Syntax Reference

## Practical guidance (how to use this skill in this environment)

When generating architecture/interface diagrams for this workspace, prefer:

- C4-PlantUML includes for readable system-level diagrams:
  - `!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Container.puml`
  - Use `System_Boundary` to represent operational ownership boundaries (e.g., "DFT Kubernetes workspace", "MRT managed services", "Bosch managed systems").

- Keep diagrams coarse-grained. If the user asks to remove intermediate boxes (e.g., avoid modelling "Kafka (platform)" as an in-cluster container), connect producers/consumers directly to the managed service nodes.

- Converting a C4 Container diagram to a plain PlantUML component diagram:
  - If the user asks for a *component diagram* (often meaning “PlantUML component syntax”, not “C4 component-level”), translate `Person/System_Ext/Container` into `actor/component/database` and translate `System_Boundary` into `package`.
  - Keep the same identifiers and relationship labels/protocols.
  - Prefer `skinparam componentStyle rectangle` for legibility.

- For browser-based public validation architectures, prefer a C4 Container diagram with:
  - one container for the combined public validation application when web UI and validation API do not need to be split,
  - a separate backend boundary,
  - a separate isolated validation-data boundary,
  - a one-way replication relationship labelled explicitly as push/publish,
  - and a short note stating there is no runtime path back into the backend.

- Avoid dense note blocks unless explicitly requested; clarity/legibility beats exhaustiveness.


## Practical C4-style diagrams (guidance)

When using C4-PlantUML for architecture/dataflow diagrams:
- Start with a C4 Container diagram for readability.
- Prefer direct relationships to real external systems over introducing extra “platform containers” that duplicate them.
  - Example: connect application services directly to "RabbitMQ service" / "Kafka service" instead of adding separate in-boundary containers like "RabbitMQ" or "Kafka (platform)" unless you need to model an in-cluster broker.
- Keep diagrams uncluttered:
  - Avoid long note blocks by default; use short captions or a separate evidence document.
  - Label relationships with protocols (HTTPS, SFTP, gRPC, AMQP, Kafka).

(These are conventions for clarity, not PlantUML limitations.)

## Overview

PlantUML is a Java-based tool that creates diagrams from text descriptions. It supports comprehensive UML diagrams and many non-UML diagram types.

**Key advantages:**

- Most comprehensive diagram support (15+ types)
- Mature C4 model integration with icons/sprites
- Extensive customization options
- Battle-tested (since 2009)

**Requirements:**

- Java Runtime Environment (JRE)
- GraphViz (for some diagram types)
- Or use Docker: `docker run -p 8080:8080 plantuml/plantuml-server`

---

## Diagram Types Quick Reference

### UML Diagrams

| Type | Keywords | Best For |
| --- | --- | --- |
| Sequence | `@startuml` | Interactions, API flows, protocols |
| Use Case | `@startuml` | Requirements, user stories |
| Class | `@startuml` | OOP design, domain models |
| Activity | `@startuml` | Workflows, processes |
| Component | `@startuml` | System structure |
| Deployment | `@startuml` | Infrastructure, deployment |
| State | `@startuml` | State machines |

### Non-UML Diagrams

| Type | Keywords | Best For |
| --- | --- | --- |
| JSON | `@startjson` | JSON structure visualization |
| YAML | `@startyaml` | YAML structure visualization |
| Wireframe | `@startsalt` | UI mockups |
| Gantt | `@startgantt` | Project timelines |
| MindMap | `@startmindmap` | Hierarchical ideas |
| WBS | `@startwbs` | Work breakdown |
| ER | `@startuml` | Database schemas |
| C4 | `@startuml` with C4 include | Software architecture |

---

## Basic Syntax

## Practical C4 Usage Notes (House Style)

When generating PlantUML architecture diagrams for documentation:
- Prefer C4-PlantUML includes (Context/Container) for readable, coarse-grained diagrams.
- Default to *containers* and *managed services*, not deeply detailed components.
- If a platform service is already modeled as an external managed service (e.g., "RabbitMQ service", "Kafka service"), avoid adding duplicate in-cluster containers unless the user explicitly wants that indirection. Connect application containers directly to the managed service nodes.
- Avoid `note` blocks inside the diagram by default; they reduce legibility. Put caveats in surrounding documentation instead.


All PlantUML diagrams are wrapped in start/end tags:

```plantuml
@startuml
' Your diagram code here
@enduml
```

**Comments:**

- Single line: `' This is a comment`
- Block: `/' This is a block comment '/`

**Title and captions:**

```plantuml
@startuml
title My Diagram Title
caption This is a caption
header Page Header
footer Page Footer

' Diagram content
@enduml
```

---

## Quick Reference Card

### Sequence

```plantuml
@startuml
participant A
participant B
A -> B: Message
A <-- B: Response
@enduml
```

### Class

```plantuml
@startuml
class Name {
    - private
    + public
    + method()
}
A <|-- B : extends
A *-- B : contains
@enduml
```

### Activity

```plantuml
@startuml
start
:Action;
if (condition?) then (yes)
    :True path;
else (no)
    :False path;
endif
stop
@enduml
```

### State

```plantuml
@startuml
[*] --> State1
State1 --> State2 : event
State2 --> [*]
@enduml
```

### Component

```plantuml
@startuml
[Component1] --> [Component2]
database DB
Component2 --> DB
@enduml
```

---

## References

For detailed syntax and complete examples, see:

| Reference | Content | When to Load |
| --- | --- | --- |
| [sequence.md](references/sequence.md) | Participants, arrows, activation, groups, notes | Creating sequence diagrams |
| [class.md](references/class.md) | Classes, visibility, relationships, cardinality | Creating class diagrams |
| [activity.md](references/activity.md) | Conditions, swimlanes, fork/join | Creating activity diagrams |
| [state-component.md](references/state-component.md) | State machines, components, deployment | Creating state/component diagrams |
| [c4.md](references/c4.md) | C4 context, container, component diagrams | Creating C4 architecture diagrams |
| [special-diagrams.md](references/special-diagrams.md) | ER, JSON, MindMap, Gantt | Creating non-UML diagrams |
| [dft-interfaces-dataflow-notes.md](references/dft-interfaces-dataflow-notes.md) | Workspace-specific patterns for DFT interface/dataflow diagrams (ownership boundaries, SQS-triggered Argo, Transfer Family→S3 landing) | When drawing DFT system-level diagrams |


## File Extensions

| Extension | Description |
| --- | --- |
| `.puml` | Standard PlantUML file |
| `.plantuml` | Alternative extension |
| `.pu` | Short extension |
| `.iuml` | Include file |

---

## Test Scenarios

### Scenario 1: Creating a sequence diagram

**Query:** "Create a PlantUML sequence diagram for user authentication"

**Expected:** Skill activates, provides sequence syntax with participants, arrows, and alt/else blocks

### Scenario 2: Creating a class diagram

**Query:** "Generate a PlantUML class diagram for an e-commerce domain"

**Expected:** Skill activates, provides class syntax with relationships and cardinality

### Scenario 3: Creating a C4 diagram

**Query:** "Create a C4 container diagram in PlantUML"

**Expected:** Skill activates, directs to c4.md reference for includes and syntax

---

**Last Updated:** 2025-12-28
**PlantUML Version:** 1.2024.6

## Version History

- **v1.1.0** (2025-12-28): Refactored to progressive disclosure - extracted content to references/
- **v1.0.0** (2025-12-26): Initial release
