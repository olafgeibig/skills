---
change_id: 20261126-product-project
date: 2026-11-26
branch: main
baseline: none
status: draft
affected_skills:
  - product-project
---

# Change: Introduce `product-project` skill (`v0.1.0`)

> [!NOTE] Interim release — not yet formally reviewed
> This change marks an interim `0.1.0` release of `product-project` for practical burn-in. A formal `skill-governance` package review (`wf-review-skill.md`) is still pending.

## Goal Statement

Add a reusable `product-project` Projektskill (`Containertyp: vault`) in `personal/skills` separating timeless project knowledge (`knowledge/raw → distilled → kb`) from case-bound operational work (`cases/`, `activities/`, `artifacts/`, `product/`), with human review gates and TurboVault SQL-friendly scalar frontmatter relations.

## Summary

Created `skills/product-project/` (`v0.1.0`) with:

- `SKILL.md` — directory layout, timeless knowledge vs. case-bound work, simple & complex case model, review gates, scalar relations, archive isolation, and TurboVault SQL validation.
- `references/init-project.md` — setup and adoption workflow (`case_prefix`, hubs, `cs-project` boundary).
- `references/ingest-and-compile.md` — `inbox/` triage + timeless `raw → distilled → fact` delta-ingest.
- `references/case-workflow.md` — `simple` & `complex` cases, Jira-style `case_id`, `activities/raw` vs. `activities/`, `artifacts/`, and SQL-verified hand-maintained case log.
- `references/product-chain.md` — `requirement → concept → evaluation → spec` lifecycle for `complex` cases, `origin:`, team delivery tracking (`implementation_status`, `ticket`), and decision revision (`EVA-r2`).
- `references/archive-and-revise.md` — transition phase vs. archival trigger and hard isolation rules (`exclude_paths: ["archive/"]`, zero incoming links from active notes).
- `assets/` — 12 templates (`project-AGENTS.md`, `template-moc.md`, `template-utility.md`, `template-document.md`, `template-distilled.md`, `template-fact.md`, `template-case.md`, `template-artifact.md`, `template-requirement.md`, `template-concept.md`, `template-evaluation.md`, `template-spec.md`).

## Conceptual Deltas

- New `hermes-projects` Projekttyp `product-project` (`Containertyp: vault`) with `case_prefix` declared in project `AGENTS.md`.
- Timeless knowledge (`knowledge/`, no `case_id` prefix) is strictly separated from case-bound operational work (`cases/`, `activities/`, `artifacts/`, `product/`, all carrying scalar `case_id:`).
- Two case kinds: `simple` (`activities/` → `artifacts/`) and `complex` (`product/` chain + optional `activities/`/`artifacts/`).
- Case `## Log` is a hand-maintained dated bullet list (not auto-generated); completeness is verified via TurboVault SQL (`WHERE case_id = '<ID>'`).
- All product relations are one-directional scalar wikilinks (child → parent) for GlueSQL compatibility; SQL validation checks both `IS NULL` and empty string `''` for template placeholders; completed cases (`status: done`) stay in place and move to Completed Cases in `+<X>.md`.
- No `check.py` in v0.1.0; evaluate need after exercising real `simple` and `complex` project cycles.
