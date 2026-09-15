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

## Derived note

Use the working-note frontmatter with type derived and an accurate description. Recommended body:

```markdown
# {{Reusable conclusion}}

## Conclusion

{{Synthesis, not a copy of the inputs}}

## Rationale

{{Why the inputs support it; assumptions and contrary findings}}

## Implications and limits

{{How it informs the concept and where it does not apply}}

---

Based on:
- [[analysis-note]]
- [[research-note]]

Topics:
- [[INDEX]]
```

## Concept note

```markdown
---
description: "{{purpose and audience}}"
type: concept
status: draft
updated: {{actual date}}
topics: ["[[INDEX]]"]
---

# {{Concept title}}

## Purpose and scope

{{Problem, intended outcome, boundaries}}

## Proposed approach

{{Self-contained account of the concept}}

## Rationale and alternatives

{{Reasons and trade-offs with citations where needed}}

## Open points and limitations

{{Remaining uncertainties and decisions}}

---

Based on:
- [[derived-conclusion]]

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

## Main MoC

```markdown
---
description: "{{scope and navigation purpose}}"
type: moc
version: "0.1.0"
updated: {{actual date}}
topics: []
---

# {{Concept title}}

## Purpose and boundaries

{{What the vault develops and excludes}}

## Current iteration

{{Reason for version; changed, rechecked, deferred, blocked work}}

## Concept

- [[concept-note]] — {{brief description}}

## Conclusions

- [[derived-conclusion]] — {{brief description}}

## Working material

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
