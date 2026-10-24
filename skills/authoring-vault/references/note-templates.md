# Note templates

Replace all `{{...}}` placeholders with real project information. Obtain dates from a tool. Omit inapplicable sections; never fabricate findings to fill a template. Example wikilinks must be adapted to actual files. Use unique filenames when possible.

## Working note

Choose research, analysis, or idea. Research reports cross-source findings, analysis evaluates, idea proposes and identifies assumptions. Add checked/reviewed_for only after a real review.

```markdown
---
description: "{{what this note contributes}}"
type: analysis
updated: {{actual date}}
topics: ["[[INDEX]]"]
---

# {{Focused subject}}

## Question

{{Question or proposal}}

## Findings

{{Separate observations, interpretation, and unverified ideas}}

## Open points

{{Material uncertainties}}

---

Based on:
- [[source-note]]

Topics:
- [[INDEX]]
```

An independent idea may omit Based on. A research note links its actual resources; an analysis links the material evaluated.

## Resource note

One authoritative source per note. Local source_uri/snapshot paths are relative to this note, not the root. Include checked/reviewed_for only after checking the actual source.

```markdown
---
description: "{{source scope and relevance}}"
type: resource
updated: {{actual content-change date}}
topics: ["[[INDEX]]"]
source_uri: "{{actual source locator}}"
---

# {{Source title}}

Source: [{{Source title}}]({{actual source locator}})

## Relevant content

{{Faithful summary with section references or citations where useful}}

## Limitations

{{Coverage, retrieval limitations, and context}}

---

Topics:
- [[INDEX]]
```

Optional frontmatter after verification:

```yaml
source_version: "{{source-provided revision}}"
snapshot: "../resources/{{snapshot filename}}"
checked: {{actual successful review date}}
reviewed_for: "{{project version actually reviewed}}"
```

Omit unavailable fields. A stored snapshot is not proof the live source remains unchanged.

## Distilled note

Use the working-note frontmatter with type distilled and an accurate description. Recommended body:

```markdown
# {{Reusable conclusion}}

## Conclusion

{{Synthesis, not a copy of the inputs}}

## Rationale

{{Why the inputs support it; assumptions and contrary findings}}

## Implications and limits

{{What this conclusion informs and where it does not apply}}

---

Based on:
- [[analysis-note]]
- [[research-note]]

Topics:
- [[INDEX]]
```

## Deliverable note

Use type deliverable and set status to draft until the output is reviewed for its audience, format, scope, and supporting inputs. Adapt the body to the target; a Docupedia page, report, slide deck, or destination vault need not share one heading structure.

```markdown
---
description: "{{purpose, audience, and output format}}"
type: deliverable
status: draft
updated: {{actual date}}
topics: ["[[INDEX]]"]
---

# {{Deliverable title}}

{{Self-contained output tailored to the intended audience and format}}

---

Based on:
- [[distilled-conclusion]]

Topics:
- [[INDEX]]
```

After verified publication only, insert before Topics:

```markdown
Deliverable: [{{Target title}}]({{verified target locator}})

Published version: {{published project version}}
Published on: {{actual publication date}}
```

Keep this historical record unchanged after local edits until another publication succeeds. Use an actual encoded external locator, not these placeholders.

## Project support templates

Support instructions, templates, and briefs under `system/` are not content notes by default; omit frontmatter and Topics footers unless the project deliberately treats the file as a content note. Keep them discoverable from AGENTS and/or INDEX.

### Project context

Use a factual context note to orient agents to the purpose, subject, current phase, scope, essential framing, and links to detailed material. When maintained as a content note, use the required metadata and a suitable existing type; a synthesized overview may use `distilled`. Link its actual sources or inputs and keep detailed evidence in the source notes.

```markdown
---
description: "{{project purpose, subject, and current boundaries}}"
type: distilled
updated: {{actual content-change date}}
topics: ["[[INDEX]]"]
---

# Project Context: {{Subject}}

## Purpose and phase

{{Why the project exists and what phase it is in}}

## Essential context

{{Only framing facts and boundaries needed before specialized work}}

## Where to look next

- [[detailed-note]] — {{what it contains}}

---

Based on:
- [[source-or-research-note]]

Topics:
- [[INDEX]]
```

Do not treat this summary as independent evidence for claims derived from its inputs. Keep operating rules in AGENTS or other support instructions, not mixed into factual context without a clear reason.

### Deliverable brief

Use one brief per deliverable when purpose, scope, required coverage, or structure needs more definition than the deliverable itself can carry. A brief is support material, not a blank-heading template or publication record.

```markdown
# Brief: {{Deliverable name}}

## Intended result

{{What the deliverable should enable or explain}}

## Audience and format

{{Who will use it and how}}

## Scope

- Include: {{required subjects or questions}}
- Exclude: {{out-of-scope material}}

## Content and structure

{{Required content and preferred organization}}

## Inputs and coverage

- Required inputs: {{actual note links}}
- Coverage check: {{what must be addressed and what may remain open}}

## Composition mode

{{Assemble selected material or rewrite it for this audience}}

## Intended target

{{Planned destination, or not yet decided; not a verified publication}}

## Acceptance criteria

- {{Observable condition for a complete, supported output}}

## Open decisions

- {{Unresolved choice, or None}}
```

### Publication instructions

Configure this file locally; never include credentials or imply authorization that has not been granted.

```markdown
# Publication Instructions

## Target and access

- Platform and target mapping: {{configured target or not configured}}
- Authorized access procedure/backend: {{approved route or not available}}
- Required approval: {{who or what authorizes this publication}}

## Platform-specific requirements

- Preserve: {{macros, layout, metadata, or other target features}}
- Render/link rules: {{destination-specific requirements}}

## Update and verification

- Read the target before updating and reconcile target-side changes.
- If changes cannot safely be distinguished, stop for reconciliation.
- Read back the exact target after writing.
- Record a verified publication only after successful read-back.
```

## Main MoC

```markdown
---
description: "{{scope and navigation purpose}}"
type: moc
version: "0.1.0"
updated: {{actual date}}
topics: []
---

# {{Project title}}

## Purpose and boundaries

{{What the vault develops and excludes}}

## Current iteration

{{Reason for version; changed, rechecked, deferred, blocked work}}

## Deliverables

- [[deliverable-note]] — {{brief description and target}}

## Distilled knowledge

- [[distilled-conclusion]] — {{brief description}}

## Analysis and working material

- [[analysis-note]] — {{brief description}}
```

Only link files that exist; start smaller when empty. Add a Deferred section when useful. Replace inventory groups with topic MoCs as needed, retaining full reachability. Root has no Topics footer.

## Topic MoC

```markdown
---
description: "{{aspect this MoC helps explore}}"
type: moc
updated: {{actual date}}
topics: ["[[INDEX]]"]
---

# {{Topic label}}

{{Short orientation}}

## Key notes

- [[relevant-note]] — {{brief description}}

---

Topics:
- [[INDEX]]
```

Name the file +{{Topic label}}.md; omit plus in the heading. Parent MoC links to it; children link back in both topic representations. Sub-MoCs can have a topic MoC parent instead of INDEX.
