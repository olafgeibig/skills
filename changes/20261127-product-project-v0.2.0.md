---
change_id: 20261127-product-project-v0.2.0
date: 2026-11-27
branch: edit/product-project-v0.2.0
status: draft
affected_skills:
  - product-project (0.1.0 -> 0.2.1)
---

# Change: Upgrade `product-project` to `v0.2.1` (Epistemic Workflows & Topic-First KB)

## Goal Statement

Upgrade the `product-project` skill (`v0.1.0` → `v0.2.1`) per `EKB-001 SPEC Epistemic Workflows for product-project` and initial burn-in refinements to add unified body `## Citations` / `## Quellen` provenance, user-owned `knowledge/masterdata/`, `grill-me` Project Knowledge onboarding, direct topic-first `raw → kb` compilation with 4-way Delta-Compile and horizontal KB linkage, two-trigger Case-to-KB flows (`Promote` + `Close`), two-tier epistemic verification (`delegate_task` verifier subagent + Tier-1 fallback), and 100% TurboVault-native Lint.

## Summary

Updated `/Users/GEO5BE4/work/skills/personal/skills/skills/product-project` across `v0.2.0` (commit `cc6569e`) and `v0.2.1` (current branch state):

- `SKILL.md` — bumped `version: "0.2.1"`, standardized Project Knowledge vs. Case Knowledge, integrated `knowledge/masterdata/`, added `status: incomplete` for truncated/paywall `knowledge/raw/` captures, removed legacy activity types and frontmatter source arrays, added 10 calibrated Hard Rules (including topic-first `kb/fact` cutting and horizontal cross-linking), routed to 6 `references/*.md` files, and enforced `AND path NOT LIKE 'projects/<x>/archive/%'` on SQL checks.
- `references/init-project.md` — added `knowledge/masterdata/` setup/adoption guidance and §4 Project Knowledge Onboarding via `grill-me`.
- `references/ingest-and-compile.md` — full redesign with 9-row triage routing, `masterdata/` rules, `status: incomplete` truncated/paywall guard, direct `knowledge/raw/ → knowledge/kb/` as the default path (reserving `knowledge/distilled/` for very large/unstructured sources or cross-source `analysis`), unified `## Citations` / `## Quellen` provenance with passage anchors, topic-first cutting + alias canonicalization + companion-source bundling, 4-way Delta-Compile (confirm/expand/contradict/new), post-compile horizontal enrichment (`## Related` / `## Verwandte Fakten`), and Tier-2 pre-review grounding checks.
- `references/case-workflow.md` — updated `activities/raw/` (`YYYY-MM-DD <Title>.md`) vs. `activities/` (`<CASE-ID> YYYY-MM-DD <Title>.md`) naming, note-inflation brake, artifact `## Citations` / `## Quellen`, mid-case `Promote to KB`, and `State-Delta-Compile` case closure.
- `references/product-chain.md` — added optional constraint check on `evaluation`, Tier-2 grounding check on `spec`, and explicit `active` vs. `implemented` KB feedback distinction.
- `references/archive-and-revise.md` — explicitly protected `done` cases and `activities/raw/` originals from archival and added SQL archive exclusion.
- `references/verify-and-lint.md` — added Part 1 (Two-Tier Epistemic Verification with explicit-only atomic decomposition, strict scope/subject/meaning matching in `true | false | null`, Exhaustion Rule ban, $N=3$ stagnation stop, isolated `delegate_task` contract, Tier-1 fallback) and Part 2 (100% TurboVault-native 10-check deterministic lint — including Check 9 for MoC index completeness, horizontal `kb/fact` linkage, and `get_links`-based unprocessed `raw/` discovery — plus semantic pass).
- `assets/` — added `template-masterdata.md` and updated 11 templates (`template-fact.md` with `## Verwandte Fakten` / topic-first guidance, `template-distilled.md`, `template-document.md`, `template-artifact.md`, `template-case.md`, `template-requirement.md`, `template-concept.md`, `template-evaluation.md`, `template-spec.md`, `template-moc.md`, `project-AGENTS.md`).

## Conceptual Deltas

- **Project Knowledge vs. Case Knowledge:** Clear boundary between timeless `knowledge/` (including `masterdata/`) and `case_id`-tagged work across all 5 Case Knowledge folders.
- **Topic-first direct KB compilation & horizontal graph:** Structured timeless sources compile directly `raw → kb` by default (skipping redundant `distilled/` wrappers), `kb/fact` notes are cut by topic/concept/component with alias canonicalization and horizontal links (`## Related` / `## Verwandte Fakten`), and truncated/paywall inputs stop at `status: incomplete`.
- **Unified body provenance:** Removed frontmatter source arrays and purged `meeting` / `correspondence` types; all derived notes use `extract | research | analysis` (+ `note` in `activities/`) and Obsidian `[[Wikilinks]]` under `## Citations` / `## Quellen`.
- **Calibrated review gate:** Pure additive citation confirmations (`## Citations` / `## Quellen` + `as_of:` bump) preserve `reviewed` + `reviewed_on:`; contradictions against `reviewed` facts move to `status: disputed` instead of overwriting.
- **Grounding-first verification & TurboVault-native lint:** Replaced external scripts with an isolated Tier-2 verifier subagent (`mode: grounding` primary with strict scope/meaning matching, `mode: constraints` on demand) and 10 scoped TurboVault-native SQL + `get_links` + `query_tasks` + `graph_report` lint checks.
