---
name: lightrag-deep-research
description: |
  Deep research workflow over an internal LightRAG knowledge base (no web search). Use when you need an
  in-depth investigation with a structured plan, iterative sub-questions, evidence gathering via LightRAG
  queries (local/global/hybrid/mix/naive), synthesis, and KB-citations. Best for: architecture/security
  research, incident retrospectives, design decisions, policy interpretation, and any question that should
  be answered primarily from your organization’s knowledge base.
---

# LightRAG Deep Research

Implement a “deep research” pattern, but **replace web search** with **LightRAG KB search**.

Goals:
- Create a research plan (sub-questions, assumptions, scope).
- Run **multiple** LightRAG queries to gather evidence.
- Synthesize with **KB citations** so the user can verify.
- Be explicit about gaps / missing KB coverage.

## Inputs to clarify (ask if missing)
- The **research question** (what decision or deliverable is needed?).
- Desired **depth** (quick / standard / deep).
- Constraints: time, doc type, timeframe, system/component scope.
- Preferred KB server alias (if multiple).

## Workflow (deterministic)

### 1) Restate + scope
- Restate the question in one sentence.
- State assumptions and what is **in scope / out of scope**.

### 2) Decompose into sub-questions
- Produce 5–12 sub-questions depending on depth.
- Tag each as: *context*, *facts*, *decision criteria*, *risks*, *open items*.

### 3) Evidence gathering (LightRAG)
Use the existing `lightrag` skill script to query LightRAG repeatedly.

- Prefer `hybrid` or `mix` for broad discovery; use `local` for grounded retrieval; use `global` to explore wider connections.
- For each sub-question:
  - Run at least 1 query; for high-impact items run 2–3 variations with different phrasings.
  - Capture the returned **context** and also keep a short **citation stub** (query + mode + timestamp + server alias).

Commands (use the existing LightRAG skill script):
- Query and return response: `python3 ~/.agents/skills/lightrag/scripts/query_lightrag.py query "<text>" --mode hybrid`
- Query and return only context: `python3 ~/.agents/skills/lightrag/scripts/query_lightrag.py query "<text>" --mode hybrid --only-context`

### 4) Synthesis
Gate: do **not** write the final answer until you have gathered enough evidence.
- Default minimum: **5 distinct LightRAG queries** (unless the question is trivial or the user asked for a quick answer).
- Summarize key findings.
- Highlight agreement vs. contradictions.
- Identify what is *supported by the KB* vs. *inferred*.

### 5) Output
Use this structure:

```markdown
## Executive Summary

## Research Plan (what was asked / how investigated)

## Key Findings
- Finding … [KB-1]

## Detailed Analysis
### Subtopic …

## Risks / Caveats

## Gaps & Next Steps

## KB Citations
[KB-1] server=<alias> mode=<mode> query="..." (context excerpt)
```

Notes:
- KB citations are not “paper citations”; they are reproducible retrieval references.
- Keep excerpts short; prefer linking to internal doc titles/ids when present in context.

## When to stop
Stop evidence gathering when:
- Additional queries repeat the same context,
- or remaining open questions cannot be answered from the KB.

## Bundled resources
None. This skill is intentionally composable: it instructs how to use the existing `lightrag` skill/scripts.
