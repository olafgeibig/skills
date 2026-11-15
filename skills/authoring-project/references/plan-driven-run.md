# Plan-driven run

Use this reference when the user wants an agent to work autonomously through research, analysis and distillation toward a deliverable. The plan is the contract: the quality of an autonomous run is decided in the interview, not during execution. Ordinary single-note work does not need it.

Requires `grilling` (not the `grill-me` wrapper), `writing-for-agents` for writing the plan, `grounded-citations` for source ledgers, `handoff` for session changes, and `turbovault-use` when the vault is accessed through TurboVault. `deep-research` is optional, on explicit request only: it brings its own source registry, so name which one is authoritative before using it.

## Gates

The user decides at four gates; between them the agent runs without asking.

| Gate | When | User decides |
| --- | --- | --- |
| G1 | after the interview | the plan is approved |
| G2 | after the grounding steps | the findings stand; reviewer report read |
| G3 | after composition | the deliverable is `ready` |
| G4 | on explicit request | publication |

A step may add its own review point in the plan. At a gate the agent stops and puts the decision to the user with `clarify`.

## 1. Interview → brief and plan

Load `grilling` and interview until its frontier is empty and the user confirms shared understanding. Look up facts yourself (vault, files, sources); put only decisions to the user.

Write two support files, not content notes, under `system/`:

- `brief-<deliverable>.md` from the deliverable brief template in `references/note-templates.md`: the what and why.
- `plan.md` from `templates/plan.md`: the how, as steps.

Completion criterion: every step has every field of the template filled; the plan lets a fresh agent execute any single step from the briefing and that step alone. Details that exist in files are linked; details that exist nowhere go into the plan. Then G1.

## 2. Execution

The orchestrator is the main agent. Loop until a stop condition:

1. Pick every step whose dependencies are done. Independent steps run in parallel as subagents (`delegate_task`); a step that builds on another step's result waits.
2. Give each subagent a step spec as `context`: briefing, its step, paths of the inputs it needs, the vault's AGENTS.md path, the target note path. A subagent has no conversation memory and needs no handoff document.
3. A subagent writes only its own target note and returns the path, a short summary, and the hypothesis result if the step has one. It uses its own `grounded-citations` ledger (`--ledger <path>`), never the profile default.
4. Before marking a step done, the orchestrator reads the returned target and checks it against the step's acceptance criteria; a subagent summary alone does not establish that the artifact exists or supports its claims. Record separately what was written, statically checked, and actually exercised. Then update the plan (status, result), append to `system/log.md`, and maintain INDEX and MoCs. One writer for shared files avoids conflicts.
5. A step that needs a decision nobody has made goes to **Open decisions** in the plan; the orchestrator continues with unaffected steps and does not guess.

Stop when: all steps are done or blocked; the iteration budget in the plan is spent; or a gate is reached.

### Hypotheses

A step may state a hypothesis: an expectation derived from the material, falsifiable.

- Fix the kill criterion in the plan before the step runs; take the date from a tool.
- After the step, write the result into the plan: `confirmed`, `refuted` or `refined`, with its basis (for example `confirmed by documentation` when behaviour was not observed) and a link to the analysis that argues it.
- A refuted hypothesis stays in the plan. Its replacement is a new step; never rewrite a hypothesis after its result is known.
- A confirmed result needs a counter-review: a reviewer subagent searches for evidence that meets the kill criterion and records queries, sources checked and outcome, including an empty outcome, plus what was not checked.
- If a result invalidates later steps, list the proposed change under **Open consequences**. Affected later steps stay untouched until the next gate.

### Sources

Register sources at retrieval time with `grounded-citations`; keep source statements, interpretation and assumptions apart in the notes. Verbatim quotes belong in the `resource` note or next to the claim, checked with `quote` and `verify --evidence` when a claim is contested or high-stakes. There is no evidence note type; a claim resolves to an analysis, and the analysis to its resources.

### Review at the gates

At G2 and G3 an independent reviewer subagent, without the authoring context, receives the notes under review and their sources.

- Mechanical: frontmatter, links, reachability from INDEX, quotes present in their source.
- Semantic: per material statement `supported`, `overstated` or `unsupported`.

It writes a short report; the user reads the report and the flagged statements instead of every note. Follow the main skill's bottom-up review rules for every relevant content-note dependency, including research, analysis and distilled inputs, not only resources and deliverables. Set `checked` and `reviewed_for` only after the individual check actually ran; a gate decision or reviewer summary does not bulk-certify the dependency chain.

## 3. Autonomy

| The agent may alone | The user decides |
| --- | --- |
| create resources, research, analysis, distilled drafts | scope and brief |
| add steps within the approved scope | changing the approved scope |
| run reviewers, write the log | `ready` and publication |
| continue past a refuted hypothesis on unaffected steps | what a refutation means for the plan |

## 4. Session change

`handoff` is for changing the main session, not for subagents. It references plan and log by path and carries no content. The default output location is `$TMPDIR`; for a long run ask for `system/` instead.
