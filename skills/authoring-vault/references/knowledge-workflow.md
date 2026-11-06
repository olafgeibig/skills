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

## Inventory existing documents and conversions

1. Enumerate the actual source directory and conversion directory, then read the existing inventory and resource MoC. Match originals to conversions by inspected filenames; preserve both files unchanged. Read enough of each new conversion to describe its role accurately, distinguishing a main document from its annexes rather than counting them as independent statements.
2. Add each requested source/conversion pair to the existing inventory and a short, descriptive entry to the appropriate MoC section. Keep sensitive identifiers and financial figures out of navigation unless needed to distinguish documents. Use the date stated inside the source for its description; a filename date may differ and must not be silently corrected.
3. Update root navigation and the iteration reason under the core version rules. Keep this inventory-only scope separate from analysis or confirmation of benefits, rights, and current applicability.
4. Validate mappings programmatically: parse every Markdown link in each inventory row, URL-decode targets, resolve them from the inventory's directory, and check original and conversion files independently. Select rows by their links or parsed columns, not by whether the visible label contains a file extension; descriptive labels otherwise disappear from the count.
5. Compare the enumerated originals and mapped originals as sets; report missing mappings, duplicate mappings, and broken targets separately. Use Unicode normalization for comparison where needed, while preserving literal filenames and link targets. Check directory-entry spelling and case explicitly; existence checks on a case-insensitive filesystem can accept a non-portable link.
6. Check table column counts and MoC links as well as file existence. Build edits from raw Markdown, not the line-numbered read-tool presentation; an extra leading pipe creates an empty table column even when every link resolves. Report the verified scope and counts, not a whole-vault or visual-rendering guarantee.

## Grounding

**Inputs:** scope, questions, existing knowledge, and available sources.

**Work:** use `resource` notes for concrete sources, `research` for findings across sources, `analysis` for evaluation or interpretation, and `idea` for proposals or assumptions. Combine roles as useful; none is a mandatory prerequisite for another. Preserve source provenance, reasoning, attribution, assumptions, and unresolved points at the level needed for later review. Keep source statements separate from inference and recommendation.

**Exit check:** the material findings and proposals needed for the intended outputs have identifiable support or are explicitly marked as uncertain, assumed, or unresolved. Continue grounding when a material gap remains.

## Source-based option analyses

Use this recipe when comparing personal or organizational options whose availability depends on contracts, policies, agreements, or program conditions.

1. Read the resource MoC and relevant existing analyses; select the actual source notes for each requested option before drafting. Reuse shared evidence, but keep independently useful options in separate notes with reciprocal comparison links rather than duplicating their full contents.
2. Establish applicability separately from content: identify source authority, covered organization/location/persons, effective period, and amendments or successor rules. Distinguish an individual contract, a governing agreement, a local presentation, and an oral explanation. Keep legal employer, contractual work location, current organizational assignment, and the agreement's covered establishment separate; organizational membership alone does not establish coverage by another location's agreement. Report what each establishes; do not promote examples or an approval still being requested into an entitlement.
3. Extract the decision-critical conditions: entry criteria, deadlines, duration, cash-flow components, exclusions, side activities, insurance or other continuing obligations, and termination consequences. Read the enclosing section and employee-group/model headings before assigning a condition; neighboring program sections can use similar labels while covering different populations. Keep general eligibility, an enforceable entitlement, and discretionary program admission distinct. Label each quota by its population, denominator, and period, and each deadline by its application route; an annual admission quota is not a simultaneous-participation cap, and a program deadline is not necessarily the deadline for asserting a contractual right. For tables or diagrams whose text conversion obscures their structure, inspect the original local document. Distinguish physical PDF page numbers from printed slide numbers in citations, because they may diverge.
4. Check personal milestones and time windows with a computation tool. Keep the calculated milestone separate from the governing rule: reaching an age or service anniversary does not itself establish eligibility, credited service, or the effective benefit start. Check expiry, transitional effects, and successor agreements before extending a source's conditions into the future.
5. Draft a compact decision note: short conclusion, applicability and baseline, mechanics and conditions, benefits/risks, unresolved questions, and concrete next steps. Put source links beside material conditions and list actual inputs under `Based on:`. Treat unexplained neighboring program names as unresolved rather than inventing a distinction. Do not equate gross lump sums, net-income reference values, or illustrated benefits with guaranteed spendable income.
6. State the minimum evidence needed for a reliable comparison: written availability/approval, an individualized calculation with explicit assumptions, and confirmation from the authority responsible for disputed consequences. Keep unavailable figures as gaps rather than fabricating a scenario. Preserve the option of continuing the current arrangement as the baseline when relevant.
7. Validate metadata, navigation, and link resolution separately from substantive applicability. Report static checks as static checks; they do not prove entitlement, current law, or visual rendering.

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
