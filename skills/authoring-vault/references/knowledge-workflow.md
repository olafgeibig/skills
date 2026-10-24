# Knowledge workflow

Use this reference when planning multi-step knowledge work, deciding whether coverage is sufficient for an output, composing multiple deliverables, or refreshing work after an input changes. The core skill defines the artifact model; this reference gives phase gates without requiring every phase to produce a file.

## When to Use

- The subject has several aspects or unresolved gaps.
- A deliverable depends on multiple notes or needs a separate brief.
- An upstream change may affect downstream conclusions or outputs.

## Scope

**Inputs:** the request, project context, and existing notes.

**Work:** define the subject and boundaries, intended outputs and audiences, relevant aspects, and known unknowns. Identify decisions that still need an owner; do not turn an unconfirmed choice into a project decision.

**Exit check:** the scope is specific enough to guide research and deliverable briefs. Record exclusions and unresolved boundaries. Do not claim exhaustive coverage of an open-ended subject.

## Grounding

**Inputs:** scope, questions, existing knowledge, and available sources.

**Work:** use `resource` notes for concrete sources, `research` for findings across sources, `analysis` for evaluation or interpretation, and `idea` for proposals or assumptions. Combine roles as useful; none is a mandatory prerequisite for another. Preserve source provenance, reasoning, attribution, assumptions, and unresolved points at the level needed for later review. Keep source statements separate from inference and recommendation.

**Exit check:** the material findings and proposals needed for the intended outputs have identifiable support or are explicitly marked as uncertain, assumed, or unresolved. Continue grounding when a material gap remains.

## Distillation

**Inputs:** relevant grounding notes and the scope.

**Work:** produce bounded conclusions that are concise enough to reuse in documentation while retaining material qualifications, applicability, limits, and disagreement. Link actual inputs with `Based on:`. Avoid repeating all source detail or creating one note per heading by default.

**Exit check:** a reader can understand the conclusion, where it applies, what it does not establish, and which grounding supports it. Skip a separate distilled note when it would merely duplicate the grounding; link the direct inputs from the deliverable instead.

## Coverage and composition

Use each deliverable brief as the coverage checklist. Map required content to relevant distilled notes or, where distillation adds no value, to direct grounding inputs. Record gaps, exclusions, and unresolved decisions; do not fill them with invented facts.

A deliverable may:

- assemble selected distilled sections with light connective text; or
- rewrite the supported substance for a specific audience, structure, and format.

Both modes retain actual input links in `Based on:`. If one dependency list cannot make the mapping understandable, add a small section-to-input map in the local authoring source. Do not require claim-by-claim evidence machinery for ordinary knowledge work. Ordinary Markdown is the default: copied material is not a live embed and must be reviewed when its inputs change.

**Exit check:** the output is self-contained for its intended reader, addresses the brief's required content, respects exclusions, and states material limitations. A ready deliverable is not necessarily approved or published.

## Review and refresh

Review only the relevant dependency chain, in dependency order: sources/resources, dependent research/analysis/ideas, distilled conclusions, then deliverables. Inspect actual content and available history; matching dates or project versions alone do not prove freshness. Assess ideas for their relevance and assumptions, not as established facts.

When an input changes, trace its affected dependents. Remove `reviewed_for` from affected downstream notes and set affected deliverables to draft. Preserve their last genuine `checked` dates. Reassess changed inputs and revalidate affected dependents bottom-up before restoring review markers. Do not bulk-bump markers or review unrelated, deferred material just to move the whole vault in lockstep.

## Support files

Keep project operating instructions, compact orientation, publication procedures, topical templates, and optional deliverable briefs under `system/` when that layout suits the project. Link essential instructions from AGENTS so an agent can discover them without loading the whole vault.

- AGENTS states scope, language, boundaries, and read-before-work rules; keep it concise.
- Context summarizes the goal, subject, phase, essential framing, and pointers to detailed notes. If it contains factual claims, give it appropriate content-note metadata and actual source/dependency links. It is orientation, not independent evidence for its inputs.
- Publication instructions identify configured targets, authorized access procedures, platform-specific features, target-edit reconciliation, and read-back expectations. They do not themselves authorize a publication or store credentials.
- A topical template describes a useful project-specific note structure. It does not force empty notes or override the skill's core metadata/navigation rules without an explicit local decision.
- A deliverable brief describes the intended outcome, audience, boundaries, content and structure, required inputs and coverage, composition mode, intended target, acceptance criteria, and open decisions. Use one per deliverable when it adds clarity; an intended target is not a publication record.

Treat instructions, templates, and briefs as support material rather than content notes by default. Apply content-note metadata, MoC reachability, and review rules to a context note or brief only when the project deliberately treats it as a content note.

## Publication boundary

A local deliverable is the authoring source and maps one-to-one to a target artifact. Multiple deliverables can reuse the same inputs but have separate targets and publication histories. Do not create a new target merely for a new project iteration.

Publish only when explicitly requested and authorized for that target. Read the target before updating; reconcile target-side edits rather than overwriting uncertain changes. Render content using destination conventions, preserve necessary citations and limitations, and remove unresolved local-only links. After writing, read back the exact target. Only then record its actual locator, project version, and publication date on the local deliverable. Keep project version distinct from destination revision. An unsuccessful, inaccessible, or unverified publication is a limitation, not a completed record.

## Generic example

A team is preparing guidance about rotating a service credential.

1. **Scope:** the output is for service owners; it covers credential replacement and deployment activation, but not the identity provider's internal operations. The rotation window is an open decision.
2. **Grounding:** a resource note captures the provider's documented rotation procedure; research compares it with the deployed service configuration; analysis identifies restart requirements; an idea note records an optional phased rollout proposal as unapproved.
3. **Distillation:** one note states the supported rotation sequence and separately marks the rollout proposal and unresolved window.
4. **Composition:** an operations runbook assembles the verified steps; a short owner briefing rewrites the same findings for a different audience. Each deliverable links its actual inputs and has its own brief and target.
5. **Refresh:** if the provider procedure changes, recheck dependent research, the distilled sequence, and only the deliverables that use it. Do not update unrelated notes or claim the rollout proposal was approved.
